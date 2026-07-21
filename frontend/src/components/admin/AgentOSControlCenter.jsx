import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, Bot, ShieldCheck, ShieldX, PlayCircle, Radio, ClipboardCheck, ScrollText, Webhook, ChevronRight, PowerOff, RefreshCcw } from "lucide-react";
import { toast } from "sonner";

const STATUS_COLOR = {
    ok: "text-green-600",
    error: "text-red-600",
    running: "text-blue-600",
    queued: "text-muted-foreground",
    approved: "text-green-600",
    rejected: "text-red-600",
    pending: "text-amber-600",
};

/**
 * Agent OS Control Center — Super-Admin surface for the pod runtime.
 *
 * Four sub-tabs:
 *   Pods           — live inventory, kill switch, per-pod toggle
 *   Approvals      — pending queue; one-click approve/reject with note
 *   Runs           — recent runs across pods, drill-in shows input/output/error
 *   Audit + Webhooks — audit log stream + recent HubSpot webhook events
 */
export default function AgentOSControlCenter() {
    const [tab, setTab] = useState("pods");
    const [connectors, setConnectors] = useState(null);
    const [killSwitch, setKillSwitch] = useState(false);

    const loadConnectors = useCallback(async () => {
        try {
            const res = await api.get("/admin/agent-os/connectors/status");
            setConnectors(res.data);
        } catch { /* non-fatal */ }
    }, []);

    useEffect(() => { loadConnectors(); }, [loadConnectors]);

    const toggleKill = async () => {
        try {
            const res = await api.post("/admin/agent-os/kill-switch", { engaged: !killSwitch });
            setKillSwitch(res.data.engaged);
            toast[res.data.engaged ? "warning" : "success"](
                res.data.engaged ? "Kill switch ENGAGED — no pod can dispatch" : "Kill switch released"
            );
        } catch (e) {
            toast.error(e.response?.data?.detail || "Kill switch toggle failed");
        }
    };

    return (
        <div data-testid="agent-os-control-center">
            <div className="mb-6 flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-3">
                    <Bot className="w-5 h-5 text-brand" />
                    <h2 className="font-serif text-2xl">Agent OS</h2>
                    <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                        Sprint 2 · Control Center
                    </span>
                </div>
                <button
                    onClick={toggleKill}
                    data-testid="agentos-kill-switch"
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-[0.12em] rounded-sm border transition-colors ${killSwitch ? "bg-red-500/10 text-red-600 border-red-500/30" : "bg-surface-alt hover:bg-surface text-muted-foreground border-border"}`}
                >
                    <PowerOff className="w-3.5 h-3.5" />
                    {killSwitch ? "Kill switch: ON" : "Kill switch: off"}
                </button>
            </div>

            <ConnectorBadges connectors={connectors} onRefresh={loadConnectors} />

            <div className="mb-6 flex gap-1 border-b border-border">
                <TabBtn active={tab === "pods"} onClick={() => setTab("pods")} testId="agentos-tab-pods">
                    <Radio className="w-3.5 h-3.5" /> Pods
                </TabBtn>
                <TabBtn active={tab === "approvals"} onClick={() => setTab("approvals")} testId="agentos-tab-approvals">
                    <ClipboardCheck className="w-3.5 h-3.5" /> Approvals
                </TabBtn>
                <TabBtn active={tab === "runs"} onClick={() => setTab("runs")} testId="agentos-tab-runs">
                    <PlayCircle className="w-3.5 h-3.5" /> Runs
                </TabBtn>
                <TabBtn active={tab === "audit"} onClick={() => setTab("audit")} testId="agentos-tab-audit">
                    <ScrollText className="w-3.5 h-3.5" /> Audit &amp; Webhooks
                </TabBtn>
            </div>

            {tab === "pods" && <PodsPanel />}
            {tab === "approvals" && <ApprovalsPanel />}
            {tab === "runs" && <RunsPanel />}
            {tab === "audit" && <AuditPanel />}
        </div>
    );
}


function TabBtn({ active, onClick, children, testId }) {
    return (
        <button
            onClick={onClick}
            data-testid={testId}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-mono uppercase tracking-[0.12em] border-b-2 -mb-px transition-colors ${active ? "border-brand text-brand" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
            {children}
        </button>
    );
}


function ConnectorBadges({ connectors, onRefresh }) {
    if (!connectors) return null;
    const hs = connectors.hubspot || {};
    return (
        <div className="card-flat p-3 mb-6 flex items-center gap-4 flex-wrap" data-testid="connector-badges">
            <div className="flex items-center gap-2 text-xs">
                <Webhook className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="font-mono uppercase tracking-[0.12em] text-muted-foreground">HubSpot outbound:</span>
                {hs.outbound_configured ? (
                    <span className="text-green-600 font-semibold" data-testid="hs-outbound-live">LIVE</span>
                ) : (
                    <span className="text-amber-600 font-semibold" data-testid="hs-outbound-stubbed">STUBBED</span>
                )}
            </div>
            <div className="flex items-center gap-2 text-xs">
                <span className="font-mono uppercase tracking-[0.12em] text-muted-foreground">HubSpot webhook:</span>
                {hs.webhook_configured ? (
                    <span className="text-green-600 font-semibold" data-testid="hs-webhook-live">LIVE</span>
                ) : (
                    <span className="text-amber-600 font-semibold" data-testid="hs-webhook-stubbed">NOT CONFIGURED</span>
                )}
            </div>
            <button onClick={onRefresh} className="ml-auto text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground hover:text-brand">
                <RefreshCcw className="w-3 h-3 inline mr-1" />refresh
            </button>
            {(!hs.outbound_configured || !hs.webhook_configured) && (
                <div className="basis-full text-[11px] text-muted-foreground pt-2 border-t border-border">
                    Set <code className="font-mono text-brand">HUBSPOT_ACCESS_TOKEN</code> and <code className="font-mono text-brand">HUBSPOT_WEBHOOK_SECRET</code> in <code className="font-mono">backend/.env</code>, then <code className="font-mono">sudo supervisorctl restart backend</code>.
                </div>
            )}
        </div>
    );
}


// ---- Pods panel -----------------------------------------------------------


function PodsPanel() {
    const [pods, setPods] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get("/admin/agent-os/pods");
            setPods(res.data.pods || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load pods");
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    const toggle = async (podId, enabled) => {
        try {
            await api.post(`/admin/agent-os/pods/${podId}/toggle?enabled=${enabled}`);
            load();
            toast.success(`${podId} ${enabled ? "enabled" : "disabled"}`);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Toggle failed");
        }
    };

    const dispatch = async (podId) => {
        try {
            const res = await api.post(`/admin/agent-os/pods/${podId}/dispatch`, { input: { source: "manual" } });
            toast.success(`Dispatched — run ${res.data.id?.slice(0, 8)}…`);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Dispatch failed");
        }
    };

    if (loading) return <PanelLoading />;
    if (pods.length === 0) return <PanelEmpty>No pods registered yet.</PanelEmpty>;

    return (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="agentos-pods-grid">
            {pods.map((p) => (
                <div key={p.id} className="card-flat p-4" data-testid={`pod-card-${p.id}`}>
                    <div className="flex items-start justify-between mb-2">
                        <div>
                            <div className="font-serif text-lg leading-tight">{p.name || p.id}</div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mt-1">
                                {p.id}
                            </div>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                            {p.enabled ? <ShieldCheck className="w-4 h-4 text-green-600" /> : <ShieldX className="w-4 h-4 text-muted-foreground" />}
                            <span className={`text-[10px] font-mono uppercase tracking-[0.12em] ${p.enabled ? "text-green-600" : "text-muted-foreground"}`}>
                                {p.enabled ? "enabled" : "disabled"}
                            </span>
                        </div>
                    </div>
                    {p.description && (
                        <p className="text-xs text-muted-foreground leading-relaxed mb-3">{p.description}</p>
                    )}
                    <div className="flex flex-wrap gap-1 mb-3">
                        {(p.mcp_scopes || []).map((s) => (
                            <span key={s} className="text-[10px] font-mono uppercase tracking-[0.12em] px-2 py-0.5 rounded-sm bg-surface-alt border border-border" data-testid={`pod-${p.id}-scope-${s}`}>
                                {s}
                            </span>
                        ))}
                        {(!p.mcp_scopes || p.mcp_scopes.length === 0) && (
                            <span className="text-[10px] text-muted-foreground italic">no MCP scopes</span>
                        )}
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => toggle(p.id, !p.enabled)}
                            data-testid={`pod-${p.id}-toggle`}
                            className="btn-outline text-xs flex-1"
                        >
                            {p.enabled ? "Disable" : "Enable"}
                        </button>
                        <button
                            onClick={() => dispatch(p.id)}
                            data-testid={`pod-${p.id}-dispatch`}
                            className="btn-primary text-xs flex-1"
                        >
                            <PlayCircle className="w-3.5 h-3.5" /> Dispatch
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}


// ---- Approvals panel ------------------------------------------------------


function ApprovalsPanel() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [decision, setDecision] = useState("pending");
    const [decidingId, setDecidingId] = useState(null);
    const [note, setNote] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get(`/admin/agent-os/approvals?decision=${decision}&limit=100`);
            setRows(res.data.approvals || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load approvals");
        } finally { setLoading(false); }
    }, [decision]);

    useEffect(() => { load(); }, [load]);

    const decide = async (approvalId, choice) => {
        setDecidingId(approvalId);
        try {
            await api.post(`/admin/agent-os/approvals/${approvalId}/decide`, {
                decision: choice, note: note.trim() || null,
            });
            toast.success(`Approval ${choice}`);
            setNote("");
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Decide failed");
        } finally { setDecidingId(null); }
    };

    return (
        <div data-testid="approvals-panel">
            <div className="mb-4 flex items-center gap-2">
                <select
                    value={decision}
                    onChange={(e) => setDecision(e.target.value)}
                    data-testid="approvals-filter"
                    className="bg-surface border border-border rounded-sm px-3 py-1.5 text-sm"
                >
                    <option value="pending">Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                </select>
                <button onClick={load} data-testid="approvals-refresh" className="btn-outline text-xs">
                    <RefreshCcw className="w-3 h-3" /> Refresh
                </button>
            </div>

            {loading ? <PanelLoading /> :
             rows.length === 0 ? <PanelEmpty>No {decision} approvals.</PanelEmpty> : (
                <div className="space-y-3" data-testid="approvals-list">
                    {rows.map((a) => (
                        <div key={a.id} className="card-flat p-4" data-testid={`approval-${a.id}`}>
                            <div className="flex items-start justify-between mb-2 gap-3">
                                <div className="min-w-0">
                                    <div className="font-serif text-base leading-tight truncate">{a.action_key || "Action"}</div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mt-1">
                                        pod: {a.pod_id} · {new Date(a.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                                    </div>
                                </div>
                                <span className={`text-[10px] font-mono uppercase tracking-[0.12em] shrink-0 ${STATUS_COLOR[a.decision] || ""}`}>
                                    {a.decision}
                                </span>
                            </div>
                            {a.summary && <p className="text-xs text-muted-foreground mb-2 leading-relaxed">{a.summary}</p>}
                            {a.details && Object.keys(a.details).length > 0 && (
                                <pre className="text-[10px] font-mono bg-surface-alt border border-border rounded-sm p-2 overflow-x-auto max-h-40 mb-3">
{JSON.stringify(a.details, null, 2)}
                                </pre>
                            )}
                            {a.decision === "pending" && (
                                <div className="border-t border-border pt-3 mt-3">
                                    <input
                                        type="text"
                                        value={decidingId === a.id ? note : ""}
                                        onChange={(e) => { setDecidingId(a.id); setNote(e.target.value); }}
                                        placeholder="Optional note (visible in audit log)"
                                        data-testid={`approval-${a.id}-note`}
                                        className="w-full bg-surface border border-border rounded-sm px-2 py-1.5 text-xs mb-2"
                                    />
                                    <div className="flex gap-2 justify-end">
                                        <button
                                            onClick={() => decide(a.id, "rejected")}
                                            disabled={decidingId === a.id}
                                            data-testid={`approval-${a.id}-reject`}
                                            className="btn-outline text-xs"
                                        >
                                            Reject
                                        </button>
                                        <button
                                            onClick={() => decide(a.id, "approved")}
                                            disabled={decidingId === a.id}
                                            data-testid={`approval-${a.id}-approve`}
                                            className="btn-primary text-xs"
                                        >
                                            Approve
                                        </button>
                                    </div>
                                </div>
                            )}
                            {a.decided_by && (
                                <div className="text-[10px] text-muted-foreground mt-2 border-t border-border pt-2">
                                    Decided by <code>{a.decided_by}</code> · {a.decided_at ? new Date(a.decided_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : ""}
                                    {a.decision_note && <div className="mt-1 italic">&ldquo;{a.decision_note}&rdquo;</div>}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
             )}
        </div>
    );
}


// ---- Runs panel -----------------------------------------------------------


function RunsPanel() {
    const [runs, setRuns] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get("/admin/agent-os/runs?limit=200");
            setRuns(res.data.runs || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load runs");
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    if (loading) return <PanelLoading />;
    if (runs.length === 0) return <PanelEmpty>No runs yet. Dispatch a pod from the Pods tab.</PanelEmpty>;

    return (
        <div className="grid md:grid-cols-5 gap-4" data-testid="runs-panel">
            <div className="md:col-span-2 card-flat divide-y divide-border max-h-[540px] overflow-y-auto">
                {runs.map((r) => (
                    <button
                        key={r.id}
                        onClick={() => setSelected(r)}
                        data-testid={`run-${r.id}`}
                        className={`w-full text-left p-3 hover:bg-surface-alt transition-colors ${selected?.id === r.id ? "bg-surface-alt" : ""}`}
                    >
                        <div className="text-xs font-mono truncate">{r.pod_id}</div>
                        <div className="text-[10px] text-muted-foreground mt-1 flex justify-between gap-2">
                            <span className={STATUS_COLOR[r.status] || ""}>{r.status}</span>
                            <span>{r.created_at ? new Date(r.created_at).toLocaleTimeString() : "—"}</span>
                        </div>
                    </button>
                ))}
            </div>
            <div className="md:col-span-3 card-flat p-4 max-h-[540px] overflow-y-auto">
                {!selected ? (
                    <div className="text-center text-sm text-muted-foreground py-16">
                        <ChevronRight className="w-5 h-5 mx-auto mb-2 opacity-50" />
                        Pick a run to see input / output / error.
                    </div>
                ) : (
                    <>
                        <div className="mb-4">
                            <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mb-1">
                                {selected.pod_id} · <span className={STATUS_COLOR[selected.status] || ""}>{selected.status}</span>
                            </div>
                            <div className="text-xs text-muted-foreground">
                                triggered by <code>{selected.triggered_by || "—"}</code>
                                {selected.created_at && " · " + new Date(selected.created_at).toLocaleString()}
                            </div>
                        </div>
                        <RunSection label="Input" body={selected.input} />
                        <RunSection label="Output" body={selected.output} />
                        {selected.error && <RunSection label="Error" body={selected.error} error />}
                    </>
                )}
            </div>
        </div>
    );
}

function RunSection({ label, body, error }) {
    if (body === undefined || body === null) return null;
    return (
        <div className="mb-3">
            <div className={`text-[10px] font-mono uppercase tracking-[0.12em] mb-1 ${error ? "text-red-600" : "text-muted-foreground"}`}>{label}</div>
            <pre className="text-[11px] font-mono bg-surface-alt border border-border rounded-sm p-2 overflow-x-auto max-h-56">
{typeof body === "string" ? body : JSON.stringify(body, null, 2)}
            </pre>
        </div>
    );
}


// ---- Audit + Webhooks panel ----------------------------------------------


function AuditPanel() {
    const [events, setEvents] = useState([]);
    const [webhookEvents, setWebhookEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const q = filter ? `?event=${encodeURIComponent(filter)}&limit=200` : "?limit=200";
            const [a, w] = await Promise.all([
                api.get(`/admin/agent-os/audit${q}`),
                api.get("/admin/agent-os/webhooks/hubspot/events?limit=50"),
            ]);
            setEvents(a.data.events || []);
            setWebhookEvents(w.data.events || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load audit");
        } finally { setLoading(false); }
    }, [filter]);

    useEffect(() => { load(); }, [load]);

    if (loading) return <PanelLoading />;

    return (
        <div className="grid lg:grid-cols-2 gap-6" data-testid="audit-panel">
            <div>
                <div className="flex items-center gap-2 mb-3">
                    <h3 className="font-serif text-lg">Audit log</h3>
                    <input
                        type="text"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        placeholder="filter event (e.g. pod.toggle)"
                        data-testid="audit-filter"
                        className="ml-auto bg-surface border border-border rounded-sm px-2 py-1 text-xs font-mono"
                    />
                </div>
                {events.length === 0 ? <PanelEmpty>No events.</PanelEmpty> : (
                    <div className="card-flat divide-y divide-border max-h-[540px] overflow-y-auto" data-testid="audit-list">
                        {events.map((e, idx) => (
                            <div key={idx} className="p-3 text-xs" data-testid={`audit-row-${idx}`}>
                                <div className="flex items-baseline justify-between gap-2 mb-1">
                                    <code className="font-mono text-brand break-all">{e.event}</code>
                                    <span className="text-[10px] text-muted-foreground shrink-0">
                                        {e.at ? new Date(e.at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "medium" }) : "—"}
                                    </span>
                                </div>
                                <div className="text-[10px] text-muted-foreground font-mono">
                                    actor: {e.actor || "—"} · subject: {e.subject || "—"}
                                </div>
                                {e.details && Object.keys(e.details).length > 0 && (
                                    <pre className="text-[10px] font-mono bg-surface-alt border border-border rounded-sm p-1.5 mt-1 max-h-20 overflow-x-auto">
{JSON.stringify(e.details, null, 2)}
                                    </pre>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div>
                <h3 className="font-serif text-lg mb-3">Recent HubSpot webhooks</h3>
                {webhookEvents.length === 0 ? <PanelEmpty>No webhook events received yet.</PanelEmpty> : (
                    <div className="card-flat divide-y divide-border max-h-[540px] overflow-y-auto" data-testid="webhook-events-list">
                        {webhookEvents.map((e, idx) => (
                            <div key={idx} className="p-3 text-xs" data-testid={`webhook-row-${idx}`}>
                                <div className="flex items-baseline justify-between gap-2 mb-1">
                                    <code className="font-mono text-brand">{e.subscription_type || "(unknown)"}</code>
                                    <span className={`text-[10px] font-mono uppercase tracking-[0.12em] ${e.outcome === "ok" ? "text-green-600" : e.outcome === "error" ? "text-red-600" : "text-muted-foreground"}`}>
                                        {e.outcome || "queued"}
                                    </span>
                                </div>
                                <div className="text-[10px] text-muted-foreground font-mono">
                                    portal: {e.portal_id} · event: {e.event_id} · obj: {e.object_id}
                                </div>
                                {e.property_name && (
                                    <div className="text-[10px] text-muted-foreground mt-1">
                                        {e.property_name} → <span className="text-brand">{e.property_value}</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}


// ---- Shared UI ------------------------------------------------------------


function PanelLoading() {
    return <div className="card-flat p-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>;
}

function PanelEmpty({ children }) {
    return <div className="card-flat p-10 text-center text-sm text-muted-foreground">{children}</div>;
}
