"""ITHR super-admin **Automation Builder** — MVP rules engine.

A stored automation is: **trigger** + optional **conditions** + one or more
**actions**. Rules are enabled/disabled from the UI. When an application
event fires (e.g. new enterprise lead), `run_automations_for_trigger(trigger,
payload)` is invoked and each matching rule executes its actions.

Sprint scope (Feb 2026):
- Triggers wired: `enterprise_lead_created`, `certificate_issued`,
  `module_5_completed`, `alert_high_severity`.
- Actions wired: `send_slack_message`, `mark_lead_status`, `create_audit_entry`,
  `dispatch_pod`.
- Extensibility: adding a new trigger = call `run_automations_for_trigger()`
  from the event site. Adding a new action = extend `_ACTION_HANDLERS`.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_super_admin
from core import db, now_iso

router = APIRouter(prefix="/api/admin/automations", tags=["admin-automations"])


# ---------------------------------------------------------------------------
# Registry of supported triggers + actions
# ---------------------------------------------------------------------------
SUPPORTED_TRIGGERS = {
    "enterprise_lead_created": {"label": "New enterprise lead received", "fields": ["bundle", "seats", "email"]},
    "certificate_issued":      {"label": "Certificate issued to a learner", "fields": ["user_id", "course_slug"]},
    "module_5_completed":      {"label": "Learner completes module 5", "fields": ["user_id", "course_id"]},
    "alert_high_severity":     {"label": "New high-severity alert fires", "fields": ["key", "title"]},
    "user_signup":             {"label": "New user signs up", "fields": ["user_id", "email"]},
}

SUPPORTED_ACTIONS = {
    "send_slack_message":  {"label": "Send a Slack message", "params": ["text"]},
    "mark_lead_status":    {"label": "Mark enterprise lead status", "params": ["status", "note"]},
    "create_audit_entry":  {"label": "Write to audit log", "params": ["action", "detail"]},
    "dispatch_pod":        {"label": "Dispatch an Agent OS pod", "params": ["pod_id", "input"]},
}

CONDITION_OPS = ["equals", "contains", "gt", "lt", "in"]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class Condition(BaseModel):
    field: str = Field(..., min_length=1, max_length=80)
    op: str = Field(..., pattern="^(equals|contains|gt|lt|in)$")
    value: str | int | float | list | None = None


class Action(BaseModel):
    action: str
    params: dict = Field(default_factory=dict)


class AutomationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    trigger: str
    conditions: list[Condition] = Field(default_factory=list)
    actions: list[Action] = Field(..., min_length=1)
    enabled: bool = True


class AutomationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    conditions: list[Condition] | None = None
    actions: list[Action] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Serialisation / persistence helpers
# ---------------------------------------------------------------------------
def _serialise(row: dict) -> dict:
    row = {**row}
    row.pop("_id", None)
    return row


async def _get_rule(rule_id: str) -> dict:
    row = await db.admin_automations.find_one({"id": rule_id})
    if not row:
        raise HTTPException(404, "Automation not found")
    return _serialise(row)


def _validate_trigger_and_actions(trigger: str, actions: list[Action]) -> None:
    if trigger not in SUPPORTED_TRIGGERS:
        raise HTTPException(400, f"Unsupported trigger: {trigger}. Choose from: {list(SUPPORTED_TRIGGERS)}")
    for a in actions:
        if a.action not in SUPPORTED_ACTIONS:
            raise HTTPException(400, f"Unsupported action: {a.action}. Choose from: {list(SUPPORTED_ACTIONS)}")


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------
@router.get("/meta")
async def automation_meta(_sa: str = Depends(get_current_super_admin)):
    """UI helper: the trigger + action catalog the builder renders."""
    return {
        "triggers": SUPPORTED_TRIGGERS,
        "actions": SUPPORTED_ACTIONS,
        "condition_ops": CONDITION_OPS,
    }


@router.get("")
async def list_automations(_sa: str = Depends(get_current_super_admin)):
    rows = []
    async for r in db.admin_automations.find({}).sort("created_at", -1):
        rows.append(_serialise(r))
    return {"automations": rows}


@router.post("")
async def create_automation(payload: AutomationCreate, sa_id: str = Depends(get_current_super_admin)):
    _validate_trigger_and_actions(payload.trigger, payload.actions)
    row = {
        "id": uuid.uuid4().hex,
        "name": payload.name,
        "description": payload.description,
        "trigger": payload.trigger,
        "conditions": [c.model_dump() for c in payload.conditions],
        "actions": [a.model_dump() for a in payload.actions],
        "enabled": payload.enabled,
        "created_at": now_iso(),
        "created_by": sa_id,
        "run_count": 0,
        "last_run_at": None,
    }
    await db.admin_automations.insert_one(row)
    return _serialise(row)


@router.patch("/{rule_id}")
async def update_automation(rule_id: str, payload: AutomationUpdate, _sa: str = Depends(get_current_super_admin)):
    existing = await _get_rule(rule_id)
    changes = {}
    if payload.name is not None: changes["name"] = payload.name
    if payload.description is not None: changes["description"] = payload.description
    if payload.enabled is not None: changes["enabled"] = payload.enabled
    if payload.conditions is not None:
        changes["conditions"] = [c.model_dump() for c in payload.conditions]
    if payload.actions is not None:
        actions_list = payload.actions or []
        _validate_trigger_and_actions(existing["trigger"], actions_list)
        changes["actions"] = [a.model_dump() for a in actions_list]
    if changes:
        await db.admin_automations.update_one({"id": rule_id}, {"$set": {**changes, "updated_at": now_iso()}})
    return await _get_rule(rule_id)


@router.delete("/{rule_id}")
async def delete_automation(rule_id: str, _sa: str = Depends(get_current_super_admin)):
    await _get_rule(rule_id)
    await db.admin_automations.delete_one({"id": rule_id})
    return {"ok": True}


@router.post("/{rule_id}/toggle")
async def toggle_automation(rule_id: str, _sa: str = Depends(get_current_super_admin)):
    row = await _get_rule(rule_id)
    new_state = not row.get("enabled", False)
    await db.admin_automations.update_one({"id": rule_id}, {"$set": {"enabled": new_state, "updated_at": now_iso()}})
    return {"id": rule_id, "enabled": new_state}


class AutomationTestRequest(BaseModel):
    payload: dict = Field(default_factory=dict)
    dry_run: bool = True


@router.post("/{rule_id}/test")
async def test_automation(rule_id: str, req: AutomationTestRequest, _sa: str = Depends(get_current_super_admin)):
    """Run a single rule against a synthetic payload (dry_run defaults to True)."""
    row = await _get_rule(rule_id)
    if not row.get("enabled", False) and not req.dry_run:
        raise HTTPException(400, "Automation is disabled — enable it or use dry_run=true.")
    result = await _run_rule(row, req.payload or {}, dry_run=req.dry_run)
    return {"rule_id": rule_id, "dry_run": req.dry_run, "result": result}


@router.get("/{rule_id}/runs")
async def rule_runs(rule_id: str, limit: int = 20, _sa: str = Depends(get_current_super_admin)):
    limit = max(1, min(limit, 100))
    rows = []
    async for r in db.admin_automation_runs.find({"rule_id": rule_id}, {"_id": 0}).sort("run_at", -1).limit(limit):
        rows.append(r)
    return {"runs": rows}


# ---------------------------------------------------------------------------
# Rules engine core
# ---------------------------------------------------------------------------
def _eval_condition(c: dict, payload: dict) -> bool:
    field, op, value = c.get("field"), c.get("op"), c.get("value")
    actual = payload.get(field)
    try:
        if op == "equals":
            return actual == value
        if op == "contains":
            return value is not None and str(value).lower() in str(actual or "").lower()
        if op == "gt":
            return actual is not None and float(actual) > float(value)
        if op == "lt":
            return actual is not None and float(actual) < float(value)
        if op == "in":
            return actual in (value or [])
    except Exception:
        return False
    return False


async def _dispatch_action(action_kind: str, params: dict, payload: dict) -> dict:
    """Resolve param placeholders {{field}} from payload, then execute the action."""
    def _resolve(v):
        if isinstance(v, str) and "{{" in v:
            out = v
            for k, val in payload.items():
                out = out.replace("{{" + k + "}}", str(val))
            return out
        return v
    resolved = {k: _resolve(v) for k, v in (params or {}).items()}

    if action_kind == "send_slack_message":
        try:
            from slack_service import send_slack_text  # type: ignore
            ok = await send_slack_text(resolved.get("text", "(no text)"))
            return {"action": action_kind, "ok": bool(ok), "resolved": resolved}
        except Exception as e:  # pragma: no cover
            return {"action": action_kind, "ok": False, "error": str(e)[:200], "resolved": resolved}

    if action_kind == "mark_lead_status":
        lead_id = payload.get("lead_id") or payload.get("id")
        if not lead_id:
            return {"action": action_kind, "ok": False, "error": "no lead_id in payload"}
        await db.enterprise_leads.update_one(
            {"id": lead_id},
            {"$set": {"status": resolved.get("status", "contacted"), "last_note": resolved.get("note"),
                      "status_updated_at": now_iso(), "status_updated_by": "automation"}},
        )
        return {"action": action_kind, "ok": True, "lead_id": lead_id}

    if action_kind == "create_audit_entry":
        await db.admin_audit_log.insert_one({
            "id": uuid.uuid4().hex,
            "actor_id": "automation",
            "action": resolved.get("action", "automation.custom"),
            "target_type": "system",
            "target_id": None,
            "detail": resolved.get("detail", ""),
            "meta": {"payload": payload},
            "created_at": now_iso(),
        })
        return {"action": action_kind, "ok": True}

    if action_kind == "dispatch_pod":
        try:
            from agent_os.orchestrator import dispatch  # type: ignore
            pod_id = resolved.get("pod_id")
            if not pod_id:
                return {"action": action_kind, "ok": False, "error": "no pod_id"}
            input_str = resolved.get("input") or "{}"
            try:
                pod_input = json.loads(input_str) if isinstance(input_str, str) else input_str
            except Exception:
                pod_input = {"raw": input_str}
            run = await dispatch(pod_id=pod_id, input_payload=pod_input, triggered_by="automation")
            run_dict = run if isinstance(run, dict) else getattr(run, "model_dump", lambda: {})()
            return {"action": action_kind, "ok": True, "run_id": run_dict.get("id")}
        except Exception as e:  # pragma: no cover
            return {"action": action_kind, "ok": False, "error": str(e)[:200]}

    return {"action": action_kind, "ok": False, "error": "unknown_action"}


async def _run_rule(rule: dict, payload: dict, *, dry_run: bool) -> dict:
    """Execute one rule against a payload. Returns per-action outcomes."""
    conditions = rule.get("conditions") or []
    matched = all(_eval_condition(c, payload) for c in conditions)
    if not matched:
        return {"matched": False, "condition_count": len(conditions), "actions": []}

    outcomes = []
    for a in rule.get("actions", []):
        if dry_run:
            outcomes.append({"action": a.get("action"), "ok": True, "dry_run": True, "params": a.get("params")})
        else:
            outcomes.append(await _dispatch_action(a.get("action"), a.get("params", {}), payload))

    # Log run
    run_row = {
        "id": uuid.uuid4().hex,
        "rule_id": rule.get("id"),
        "trigger": rule.get("trigger"),
        "payload": payload,
        "matched": matched,
        "dry_run": dry_run,
        "outcomes": outcomes,
        "run_at": now_iso(),
    }
    await db.admin_automation_runs.insert_one(run_row)
    if not dry_run:
        await db.admin_automations.update_one(
            {"id": rule.get("id")},
            {"$inc": {"run_count": 1}, "$set": {"last_run_at": now_iso()}},
        )
    return {"matched": True, "actions": outcomes, "run_id": run_row["id"]}


async def run_automations_for_trigger(trigger: str, payload: dict) -> list[dict]:
    """Public event-site hook — call this from application code.

    Fire-and-forget from the caller if desired: wrap with `asyncio.create_task`.
    Returns list of per-rule outcomes for inspection / testing.
    """
    if trigger not in SUPPORTED_TRIGGERS:
        return []
    outs = []
    async for row in db.admin_automations.find({"trigger": trigger, "enabled": True}):
        try:
            outs.append(await _run_rule(_serialise(row), payload, dry_run=False))
        except Exception as e:  # pragma: no cover
            outs.append({"rule_id": row.get("id"), "error": str(e)[:200]})
    return outs


async def ensure_indexes():
    await db.admin_automations.create_index([("trigger", 1), ("enabled", 1)])
    await db.admin_automation_runs.create_index([("rule_id", 1), ("run_at", -1)])
    # Alert-automation dedupe marker — unique key so concurrent /alerts-center
    # polls can't both dispatch the same alert_high_severity event.
    await db.admin_alert_automation_fired.create_index("key", unique=True)
    # Starter-rule idempotency guard — one rule per seed_key.
    await db.admin_automations.create_index("seed_key", unique=True, sparse=True)


# ---------------------------------------------------------------------------
# Starter automations — one per trigger, idempotent, all use create_audit_entry
# so they're safe to enable in production without side effects. Admins can
# swap the action in the UI (e.g. to send_slack_message) once they're ready.
# ---------------------------------------------------------------------------
STARTER_AUTOMATIONS = [
    {
        "seed_key": "starter.user_signup.audit",
        "name": "Log new signups to audit trail",
        "description": "Writes an audit entry every time a new user signs up (email/password or Google). Swap the action to send_slack_message when you're ready to notify your team.",
        "trigger": "user_signup",
        "conditions": [],
        "actions": [{
            "action": "create_audit_entry",
            "params": {
                "action": "automation.user_signup",
                "detail": "New signup: {{full_name}} · {{email}} · via {{auth_provider}}",
            },
        }],
    },
    {
        "seed_key": "starter.certificate_issued.audit",
        "name": "Log certificate issuance",
        "description": "Writes an audit entry every time a learner earns a certificate. Extend with a Slack celebration or LinkedIn share prompt.",
        "trigger": "certificate_issued",
        "conditions": [],
        "actions": [{
            "action": "create_audit_entry",
            "params": {
                "action": "automation.certificate_issued",
                "detail": "Certificate {{certificate_id}} issued for {{course_title}} · score {{score}}%",
            },
        }],
    },
    {
        "seed_key": "starter.module_5_completed.audit",
        "name": "Track module-5 milestones",
        "description": "Fires when a learner clears module 5 of any course — the founding-cohort perk trigger. Great for cohort-milestone celebrations.",
        "trigger": "module_5_completed",
        "conditions": [],
        "actions": [{
            "action": "create_audit_entry",
            "params": {
                "action": "automation.module_5_completed",
                "detail": "Learner {{user_id}} completed module 5 of {{course_title}}",
            },
        }],
    },
    {
        "seed_key": "starter.alert_high_severity.audit",
        "name": "Escalate high-severity alerts",
        "description": "Writes an audit entry the moment a new high-severity platform alert opens. Swap to send_slack_message to page your ops channel.",
        "trigger": "alert_high_severity",
        "conditions": [],
        "actions": [{
            "action": "create_audit_entry",
            "params": {
                "action": "automation.alert_high_severity",
                "detail": "HIGH severity · {{key}} · {{title}} · {{detail}}",
            },
        }],
    },
    {
        "seed_key": "starter.enterprise_lead_created.audit",
        "name": "Log new enterprise leads",
        "description": "Writes an audit entry for every new enterprise lead submission. Extend with a Slack sales-channel ping + mark_lead_status auto-triage.",
        "trigger": "enterprise_lead_created",
        "conditions": [],
        "actions": [{
            "action": "create_audit_entry",
            "params": {
                "action": "automation.enterprise_lead_created",
                "detail": "New lead · {{company}} · {{bundle}} · {{seats}} seats · {{email}}",
            },
        }],
    },
]


async def seed_starter_automations() -> int:
    """Idempotently insert the 5 starter rules. Returns the number newly seeded.

    Each rule has a unique `seed_key` and is only inserted when missing so
    subsequent restarts / redeploys don't duplicate. Rules are seeded
    ENABLED — admins can flip off from the UI if they don't want them running.
    """
    seeded = 0
    for tpl in STARTER_AUTOMATIONS:
        existing = await db.admin_automations.find_one({"seed_key": tpl["seed_key"]})
        if existing:
            continue
        row = {
            "id": uuid.uuid4().hex,
            "seed_key": tpl["seed_key"],
            "name": tpl["name"],
            "description": tpl["description"],
            "trigger": tpl["trigger"],
            "conditions": tpl["conditions"],
            "actions": tpl["actions"],
            "enabled": True,
            "created_at": now_iso(),
            "created_by": "system.starter",
            "run_count": 0,
            "last_run_at": None,
        }
        try:
            await db.admin_automations.insert_one(row)
            seeded += 1
        except Exception:
            # Duplicate-key race is fine — another worker seeded it.
            pass
    return seeded
