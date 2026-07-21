import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
    Sparkles, Plus, Trash2, X, Play, Loader2, ToggleLeft, ToggleRight,
    Zap, ArrowRight, ChevronDown, ChevronRight, ClipboardList
} from "lucide-react";

/* ==========================================================================
 * AutomationBuilder — visual rules engine UI for the super-admin.
 * Trigger → Conditions → Actions. Wired to /api/admin/automations/*.
 * ========================================================================== */
export default function AutomationBuilder() {
    const [meta, setMeta] = useState(null);
    const [rules, setRules] = useState([]);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [expandedRule, setExpandedRule] = useState(null);

    const loadAll = useCallback(async () => {
        setLoading(true);
        try {
            const [mResp, rResp] = await Promise.all([
                api.get("/admin/automations/meta"),
                api.get("/admin/automations"),
            ]);
            setMeta(mResp.data);
            setRules(rResp.data.automations || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load automations");
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { loadAll(); }, [loadAll]);

    const toggle = async (id) => {
        try {
            const res = await api.post(`/admin/automations/${id}/toggle`);
            setRules((prev) => prev.map((r) => r.id === id ? { ...r, enabled: res.data.enabled } : r));
            toast.success(`Automation ${res.data.enabled ? "enabled" : "disabled"}`);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Toggle failed");
        }
    };

    const remove = async (id, name) => {
        if (!window.confirm(`Delete automation "${name}"?`)) return;
        try {
            await api.delete(`/admin/automations/${id}`);
            setRules((prev) => prev.filter((r) => r.id !== id));
            if (expandedRule === id) setExpandedRule(null);
            toast.success("Automation removed");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Delete failed");
        }
    };

    const testRule = async (rule) => {
        try {
            // Build a synthetic payload from the trigger's declared fields.
            const triggerMeta = meta?.triggers?.[rule.trigger];
            const payload = {};
            (triggerMeta?.fields || []).forEach((f) => { payload[f] = `sample-${f}`; });
            const res = await api.post(`/admin/automations/${rule.id}/test`, { payload, dry_run: true });
            const result = res.data.result || {};
            if (result.matched === false) {
                toast.warning(`Dry-run · conditions did NOT match (${result.condition_count || 0} condition(s))`);
            } else {
                toast.success(`Dry-run OK · ${result.actions?.length || 0} action(s) would fire`);
            }
        } catch (e) {
            toast.error(e.response?.data?.detail || "Test failed");
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-24">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div data-testid="automation-builder" className="space-y-6">
            <div className="sa-glass-hero p-6 lg:p-7 flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-brand">Automations</span>
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-brand/10 text-brand text-[10px] font-semibold">
                            <Sparkles className="w-3 h-3" /> RULES ENGINE
                        </span>
                    </div>
                    <h1 className="font-serif text-3xl lg:text-4xl leading-tight tracking-tight max-w-3xl">
                        Wire platform events to actions — no code required.
                    </h1>
                    <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
                        A rule fires when its <b>trigger</b> is emitted by the platform, its <b>conditions</b> all match, and every configured <b>action</b> is dispatched.
                        Toggle a rule off any time. Use <i>Test</i> for a dry-run against a synthetic payload.
                    </p>
                </div>
                <button
                    onClick={() => setCreating(true)}
                    data-testid="automation-create-btn"
                    className="sa-quick-action"
                >
                    <Plus className="icon" /> New automation
                </button>
            </div>

            {rules.length === 0 && (
                <div className="sa-glass p-12 text-center" data-testid="automation-empty">
                    <div className="inline-flex w-14 h-14 rounded-2xl items-center justify-center mb-3 mx-auto"
                         style={{ background: "linear-gradient(135deg, #00A78B 0%, #2E7FC1 100%)", color: "#fff" }}>
                        <Zap className="w-6 h-6" />
                    </div>
                    <div className="font-serif text-2xl mb-1">No automations yet</div>
                    <p className="text-sm text-muted-foreground max-w-md mx-auto">
                        Try: <i>New enterprise lead → Slack the sales channel</i> · <i>High-severity alert → Log to audit trail</i>.
                    </p>
                </div>
            )}

            {rules.map((r) => (
                <RuleCard
                    key={r.id}
                    rule={r}
                    meta={meta}
                    expanded={expandedRule === r.id}
                    onExpand={() => setExpandedRule(expandedRule === r.id ? null : r.id)}
                    onToggle={() => toggle(r.id)}
                    onDelete={() => remove(r.id, r.name)}
                    onTest={() => testRule(r)}
                    onReload={loadAll}
                />
            ))}

            {creating && meta && (
                <NewAutomationModal
                    meta={meta}
                    onClose={() => setCreating(false)}
                    onCreated={(row) => {
                        setRules((prev) => [row, ...prev]);
                        setCreating(false);
                        toast.success(`Automation "${row.name}" created`);
                    }}
                />
            )}
        </div>
    );
}

function RuleCard({ rule, meta, expanded, onExpand, onToggle, onDelete, onTest, onReload }) {
    const triggerLabel = meta?.triggers?.[rule.trigger]?.label || rule.trigger;
    return (
        <div className="sa-glass p-5" data-testid={`automation-row-${rule.id}`}>
            <div className="flex items-start justify-between gap-4">
                <button onClick={onExpand} className="text-left flex-1 min-w-0" data-testid={`automation-expand-${rule.id}`}>
                    <div className="flex items-center gap-2 mb-1">
                        {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        <span className="font-serif text-lg leading-tight">{rule.name}</span>
                        <span className={`text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-full ${rule.enabled ? "bg-brand/10 text-brand" : "bg-slate-100 text-muted-foreground"}`}>
                            {rule.enabled ? "ACTIVE" : "DISABLED"}
                        </span>
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center gap-2 flex-wrap">
                        <Zap className="w-3 h-3 text-brand" />
                        <span>{triggerLabel}</span>
                        <ArrowRight className="w-3 h-3" />
                        <span>{rule.conditions?.length || 0} condition(s)</span>
                        <ArrowRight className="w-3 h-3" />
                        <span>{rule.actions?.length || 0} action(s)</span>
                        {rule.run_count > 0 && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100">
                                {rule.run_count} run{rule.run_count === 1 ? "" : "s"}
                            </span>
                        )}
                    </div>
                    {rule.description && <div className="text-xs text-muted-foreground mt-1.5 italic">{rule.description}</div>}
                </button>
                <div className="flex items-center gap-1 shrink-0">
                    <button onClick={onTest} className="sa-icon-btn" title="Dry-run test" data-testid={`automation-test-${rule.id}`}>
                        <Play className="w-4 h-4" />
                    </button>
                    <button onClick={onToggle} className="sa-icon-btn" title={rule.enabled ? "Disable" : "Enable"} data-testid={`automation-toggle-${rule.id}`}>
                        {rule.enabled ? <ToggleRight className="w-4 h-4 text-brand" /> : <ToggleLeft className="w-4 h-4" />}
                    </button>
                    <button onClick={onDelete} className="sa-icon-btn hover:!text-destructive" title="Delete" data-testid={`automation-delete-${rule.id}`}>
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {expanded && (
                <div className="mt-4 pt-4 border-t border-border grid grid-cols-1 md:grid-cols-3 gap-4 text-sm" data-testid={`automation-detail-${rule.id}`}>
                    <StagePanel title="Trigger" tone="teal">
                        <div className="font-mono text-xs uppercase text-muted-foreground">{rule.trigger}</div>
                        <div className="mt-1">{triggerLabel}</div>
                    </StagePanel>
                    <StagePanel title="Conditions" tone="blue">
                        {rule.conditions?.length === 0 && <div className="text-xs text-muted-foreground italic">Always run when the trigger fires.</div>}
                        {rule.conditions?.map((c, i) => (
                            <div key={i} className="text-xs font-mono py-1">
                                <span className="text-brand">{c.field}</span> <span className="text-muted-foreground">{c.op}</span> <span>{JSON.stringify(c.value)}</span>
                            </div>
                        ))}
                    </StagePanel>
                    <StagePanel title="Actions" tone="gold">
                        {rule.actions?.map((a, i) => (
                            <div key={i} className="text-xs mb-1.5">
                                <div className="font-mono uppercase text-muted-foreground">{a.action}</div>
                                <div className="whitespace-pre-wrap break-all">{JSON.stringify(a.params, null, 0)}</div>
                            </div>
                        ))}
                    </StagePanel>
                    <div className="md:col-span-3">
                        <RunsSubPanel ruleId={rule.id} onReload={onReload} />
                    </div>
                </div>
            )}
        </div>
    );
}

function StagePanel({ title, children, tone }) {
    const border = tone === "teal" ? "border-l-[3px] border-l-teal-500" : tone === "blue" ? "border-l-[3px] border-l-blue-500" : "border-l-[3px] border-l-amber-500";
    return (
        <div className={`bg-white/60 backdrop-blur rounded-lg p-3 border border-border ${border}`}>
            <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-2">{title}</div>
            {children}
        </div>
    );
}

function RunsSubPanel({ ruleId }) {
    const [runs, setRuns] = useState(null);
    const [loading, setLoading] = useState(false);
    const load = useCallback(async () => {
        setLoading(true);
        try {
            const r = await api.get(`/admin/automations/${ruleId}/runs?limit=10`);
            setRuns(r.data.runs || []);
        } catch { /* silent */ } finally { setLoading(false); }
    }, [ruleId]);
    useEffect(() => { load(); }, [load]);
    return (
        <div>
            <div className="flex items-center gap-2 mb-2">
                <ClipboardList className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Recent runs</span>
                {loading && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
            </div>
            {(!runs || runs.length === 0) && <div className="text-xs text-muted-foreground italic">No runs recorded yet.</div>}
            {runs && runs.map((r) => (
                <div key={r.id} className="text-xs font-mono py-1 flex items-center gap-2 border-b border-border last:border-b-0">
                    <span className={`w-1.5 h-1.5 rounded-full ${r.matched ? "bg-teal-500" : "bg-slate-400"}`} />
                    <span className="text-muted-foreground">{r.run_at?.slice(0, 19)}</span>
                    <span>{r.dry_run ? "dry-run" : "live"}</span>
                    <span>· {r.outcomes?.filter((o) => o.ok).length || 0}/{r.outcomes?.length || 0} actions ok</span>
                </div>
            ))}
        </div>
    );
}

/* ==========================================================================
 * NewAutomationModal — trigger picker → conditions builder → actions builder.
 * ========================================================================== */
function NewAutomationModal({ meta, onClose, onCreated }) {
    const [step, setStep] = useState(1); // 1 = base, 2 = conditions, 3 = actions
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [trigger, setTrigger] = useState(Object.keys(meta.triggers)[0]);
    const [conditions, setConditions] = useState([]);
    const [actions, setActions] = useState([{ action: Object.keys(meta.actions)[0], params: {} }]);
    const [submitting, setSubmitting] = useState(false);

    const triggerFields = useMemo(() => meta.triggers[trigger]?.fields || [], [meta, trigger]);

    const addCondition = () => setConditions((prev) => [...prev, { field: triggerFields[0] || "", op: "equals", value: "" }]);
    const removeCondition = (i) => setConditions((prev) => prev.filter((_, idx) => idx !== i));
    const updateCondition = (i, patch) => setConditions((prev) => prev.map((c, idx) => idx === i ? { ...c, ...patch } : c));

    const addAction = () => setActions((prev) => [...prev, { action: Object.keys(meta.actions)[0], params: {} }]);
    const removeAction = (i) => setActions((prev) => prev.filter((_, idx) => idx !== i));
    const updateAction = (i, patch) => setActions((prev) => prev.map((a, idx) => idx === i ? { ...a, ...patch } : a));
    const updateActionParam = (i, key, val) => setActions((prev) => prev.map((a, idx) => idx === i ? { ...a, params: { ...a.params, [key]: val } } : a));

    const submit = async () => {
        if (name.trim().length < 2) { toast.error("Give the automation a name."); return; }
        if (actions.length === 0) { toast.error("Add at least one action."); return; }
        setSubmitting(true);
        try {
            const res = await api.post("/admin/automations", {
                name: name.trim(),
                description: description.trim(),
                trigger,
                conditions,
                actions,
                enabled: true,
            });
            onCreated(res.data);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Create failed");
        } finally { setSubmitting(false); }
    };

    return (
        <div className="fixed inset-0 z-[70] bg-slate-900/50 backdrop-blur-sm flex items-start justify-center pt-[6vh] px-4" onClick={onClose}>
            <div className="sa-glass-hero w-full max-w-[720px] rounded-2xl overflow-hidden" onClick={(e) => e.stopPropagation()} data-testid="automation-new-modal">
                <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                    <div>
                        <div className="text-[10px] font-mono uppercase tracking-widest text-brand mb-1">Step {step} of 3</div>
                        <div className="font-serif text-2xl leading-tight">
                            {step === 1 ? "Name your automation" : step === 2 ? "Add conditions (optional)" : "Configure actions"}
                        </div>
                    </div>
                    <button onClick={onClose} className="sa-icon-btn" data-testid="automation-modal-close"><X className="w-4 h-4" /></button>
                </div>

                <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
                    {step === 1 && (
                        <>
                            <Field label="Name" required>
                                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Slack ops on new enterprise lead"
                                       data-testid="automation-name-input"
                                       className="w-full bg-white/80 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                            </Field>
                            <Field label="Description (optional)">
                                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="Ping the sales channel + auto-mark high-seat leads as priority."
                                          data-testid="automation-description-input"
                                          className="w-full bg-white/80 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand resize-none" />
                            </Field>
                            <Field label="Trigger" required>
                                <select value={trigger} onChange={(e) => { setTrigger(e.target.value); setConditions([]); }} data-testid="automation-trigger-select"
                                        className="w-full bg-white/80 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand">
                                    {Object.entries(meta.triggers).map(([k, v]) => (
                                        <option key={k} value={k}>{v.label} ({k})</option>
                                    ))}
                                </select>
                                <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1">
                                    Payload fields: {triggerFields.join(", ") || "—"}
                                </div>
                            </Field>
                        </>
                    )}

                    {step === 2 && (
                        <div className="space-y-3">
                            <div className="text-xs text-muted-foreground">
                                Leave empty to run on every trigger. Combine fields with operators: equals, contains, gt, lt, in.
                            </div>
                            {conditions.map((c, i) => (
                                <div key={i} className="flex gap-2 items-center" data-testid={`condition-row-${i}`}>
                                    <select value={c.field} onChange={(e) => updateCondition(i, { field: e.target.value })}
                                            className="bg-white/80 border border-border rounded-lg px-2 py-2 text-sm">
                                        {triggerFields.map((f) => <option key={f} value={f}>{f}</option>)}
                                    </select>
                                    <select value={c.op} onChange={(e) => updateCondition(i, { op: e.target.value })}
                                            className="bg-white/80 border border-border rounded-lg px-2 py-2 text-sm">
                                        {meta.condition_ops.map((op) => <option key={op} value={op}>{op}</option>)}
                                    </select>
                                    <input value={c.value ?? ""} onChange={(e) => updateCondition(i, { value: e.target.value })} placeholder="value"
                                           className="flex-1 bg-white/80 border border-border rounded-lg px-2 py-2 text-sm" />
                                    <button onClick={() => removeCondition(i)} className="sa-icon-btn"><Trash2 className="w-3.5 h-3.5" /></button>
                                </div>
                            ))}
                            <button onClick={addCondition} data-testid="add-condition-btn" className="sa-quick-action">
                                <Plus className="icon" /> Add condition
                            </button>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="space-y-4">
                            {actions.map((a, i) => (
                                <div key={i} className="bg-white/60 backdrop-blur rounded-lg p-3 border border-border" data-testid={`action-row-${i}`}>
                                    <div className="flex items-center gap-2 mb-2">
                                        <select value={a.action} onChange={(e) => updateAction(i, { action: e.target.value, params: {} })}
                                                data-testid={`action-select-${i}`}
                                                className="flex-1 bg-white/80 border border-border rounded-lg px-2 py-2 text-sm">
                                            {Object.entries(meta.actions).map(([k, v]) => <option key={k} value={k}>{v.label} ({k})</option>)}
                                        </select>
                                        {actions.length > 1 && (
                                            <button onClick={() => removeAction(i)} className="sa-icon-btn"><Trash2 className="w-3.5 h-3.5" /></button>
                                        )}
                                    </div>
                                    {(meta.actions[a.action]?.params || []).map((pKey) => (
                                        <div key={pKey} className="mb-2">
                                            <label className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground block mb-1">{pKey}</label>
                                            <input
                                                value={a.params[pKey] || ""}
                                                onChange={(e) => updateActionParam(i, pKey, e.target.value)}
                                                data-testid={`action-param-${i}-${pKey}`}
                                                placeholder={pKey === "text" ? "New lead from {{company}} — {{email}} · {{bundle}}" : `${pKey}…`}
                                                className="w-full bg-white/80 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand"
                                            />
                                        </div>
                                    ))}
                                    <div className="text-[10px] font-mono text-muted-foreground">
                                        Tip: reference the trigger payload with <code className="text-brand">{"{{field}}"}</code>.
                                    </div>
                                </div>
                            ))}
                            <button onClick={addAction} data-testid="add-action-btn" className="sa-quick-action">
                                <Plus className="icon" /> Add action
                            </button>
                        </div>
                    )}
                </div>

                <div className="px-5 py-3 border-t border-border flex items-center justify-between">
                    <button onClick={() => setStep(Math.max(1, step - 1))} disabled={step === 1} className="text-sm text-muted-foreground disabled:opacity-40">Back</button>
                    {step < 3 && (
                        <button
                            onClick={() => setStep(step + 1)}
                            disabled={step === 1 && name.trim().length < 2}
                            data-testid="automation-next-btn"
                            className="sa-quick-action"
                        >
                            Next <ArrowRight className="icon" />
                        </button>
                    )}
                    {step === 3 && (
                        <button onClick={submit} disabled={submitting} data-testid="automation-submit-btn" className="sa-quick-action">
                            {submitting ? <Loader2 className="icon animate-spin" /> : <Sparkles className="icon" />}
                            Create automation
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

function Field({ label, required, children }) {
    return (
        <div>
            <label className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground block mb-1.5">
                {label}{required && <span className="text-destructive"> *</span>}
            </label>
            {children}
        </div>
    );
}
