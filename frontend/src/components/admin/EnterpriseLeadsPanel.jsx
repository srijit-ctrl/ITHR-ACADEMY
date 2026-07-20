import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, Inbox, ExternalLink, Slack, AlertCircle, Filter } from "lucide-react";
import { toast } from "sonner";

const STATUS_OPTIONS = ["new", "contacted", "qualified", "closed_won", "closed_lost"];
const STATUS_COLOR = {
    new: "bg-brand/10 text-brand border-brand/30",
    contacted: "bg-blue-500/10 text-blue-700 border-blue-500/30",
    qualified: "bg-purple-500/10 text-purple-700 border-purple-500/30",
    closed_won: "bg-green-500/10 text-green-700 border-green-500/30",
    closed_lost: "bg-muted text-muted-foreground border-border",
};
const BUNDLE_LABEL = {
    "talent-ops-bundle": "Talent Ops",
    "hr-starter": "HR · Starter",
    "hr-growth": "HR · Growth",
    "hr-enterprise": "HR · Enterprise",
    "hr-consult": "HR · Consult",
    generic: "Enterprise",
};

/**
 * Enterprise lead inbox for the Super-Admin console. Reads from
 * /api/admin/leads/enterprise and lets the operator move a lead through
 * the CRM funnel (new → contacted → qualified → closed_won/lost).
 *
 * Shows a "Slack webhook not configured" banner when SLACK_WEBHOOK_URL
 * is blank in the backend .env, so operators know incoming leads only
 * appear here (no Slack ping).
 */
export default function EnterpriseLeadsPanel() {
    const [leads, setLeads] = useState([]);
    const [count, setCount] = useState(0);
    const [slackOk, setSlackOk] = useState(true);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");

    const load = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const q = filter === "all" ? "" : `&status=${filter}`;
            const res = await api.get(`/admin/leads/enterprise?limit=200${q}`);
            setLeads(res.data.leads || []);
            setCount(res.data.count || 0);
            setSlackOk(!!res.data.slack_configured);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load leads");
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => { load(); }, [load]);

    const changeStatus = async (leadId, newStatus) => {
        try {
            await api.post(`/admin/leads/enterprise/${leadId}/status`, { status: newStatus });
            toast.success(`Marked as ${newStatus.replace("_", " ")}`);
            load(true);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Status update failed");
        }
    };

    return (
        <div data-testid="enterprise-leads-panel">
            <div className="mb-6 flex items-center gap-3">
                <Inbox className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl">Enterprise leads</h2>
                <span className="text-xs font-mono text-muted-foreground">({count})</span>
            </div>

            {!slackOk && (
                <div
                    data-testid="slack-not-configured"
                    className="mb-6 card-flat p-4 border-l-4 border-amber-500 bg-amber-500/5 flex items-start gap-3"
                >
                    <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                    <div className="text-sm">
                        <div className="font-semibold text-amber-800">Slack webhook not configured</div>
                        <div className="text-muted-foreground">
                            New leads land here but no ping fires. Set <code className="font-mono text-brand">SLACK_WEBHOOK_URL</code> in <code className="font-mono">backend/.env</code> and restart the backend to enable real-time alerts.
                        </div>
                    </div>
                </div>
            )}

            {slackOk && (
                <div
                    data-testid="slack-configured"
                    className="mb-6 card-flat p-3 border-l-4 border-green-500 bg-green-500/5 flex items-center gap-2 text-sm"
                >
                    <Slack className="w-4 h-4 text-green-600" />
                    <span>Slack webhook configured — new leads ping <code className="font-mono text-brand">#sales</code> in real time.</span>
                </div>
            )}

            <div className="flex items-center gap-2 mb-4">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <select
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    data-testid="leads-filter"
                    className="bg-surface border border-border rounded-sm px-3 py-1.5 text-sm"
                >
                    <option value="all">All leads</option>
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                </select>
            </div>

            {loading ? (
                <div className="card-flat p-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
            ) : leads.length === 0 ? (
                <div className="card-flat p-8 text-center text-sm text-muted-foreground">
                    No enterprise leads yet. Submissions from <code className="font-mono text-brand">/enterprise</code> and <code className="font-mono text-brand">/hr-suite</code> land here.
                </div>
            ) : (
                <div className="card-flat divide-y divide-border" data-testid="leads-table">
                    <div className="grid grid-cols-12 gap-3 p-4 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                        <div className="col-span-3">Contact</div>
                        <div className="col-span-2">Company</div>
                        <div className="col-span-2">Bundle · seats</div>
                        <div className="col-span-2">Received</div>
                        <div className="col-span-1">Delivery</div>
                        <div className="col-span-2 text-right">Status</div>
                    </div>
                    {leads.map((l) => (
                        <div key={l.id} className="grid grid-cols-12 gap-3 p-4 items-center text-sm" data-testid={`lead-row-${l.id}`}>
                            <div className="col-span-3">
                                <div className="font-serif text-base leading-tight">{l.name}</div>
                                <a href={`mailto:${l.email}?subject=Re:%20${l.bundle}%20-%20ITHR%20Academy`} className="text-xs text-brand hover:underline font-mono break-all inline-flex items-center gap-1">
                                    {l.email} <ExternalLink className="w-3 h-3" />
                                </a>
                                {l.role && <div className="text-[10px] text-muted-foreground mt-0.5">{l.role}</div>}
                            </div>
                            <div className="col-span-2 text-xs">{l.company}</div>
                            <div className="col-span-2 text-xs">
                                <div className="font-mono">{BUNDLE_LABEL[l.bundle] || l.bundle}</div>
                                {l.seats && <div className="text-[10px] text-muted-foreground">{l.seats} seats</div>}
                            </div>
                            <div className="col-span-2 text-[11px] text-muted-foreground">
                                {l.created_at ? new Date(l.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—"}
                            </div>
                            <div className="col-span-1 flex flex-col gap-1 text-[10px]">
                                <span className={l.slack_delivered ? "text-green-600" : "text-muted-foreground"}>
                                    Slack: {l.slack_delivered ? "✓" : "—"}
                                </span>
                                <span className={l.confirmation_email_sent ? "text-green-600" : "text-muted-foreground"}>
                                    Email: {l.confirmation_email_sent ? "✓" : "—"}
                                </span>
                            </div>
                            <div className="col-span-2 text-right">
                                <select
                                    value={l.status || "new"}
                                    onChange={(e) => changeStatus(l.id, e.target.value)}
                                    data-testid={`lead-status-${l.id}`}
                                    className={`text-xs border rounded-sm px-2 py-1 ${STATUS_COLOR[l.status] || STATUS_COLOR.new}`}
                                >
                                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                                </select>
                            </div>
                            {l.message && (
                                <div className="col-span-12 text-xs text-muted-foreground leading-relaxed border-l-2 border-border pl-3 mt-2 italic">
                                    &ldquo;{l.message.length > 300 ? l.message.slice(0, 300) + "…" : l.message}&rdquo;
                                </div>
                            )}
                            {l.last_note && (
                                <div className="col-span-12 text-xs text-brand pl-3 mt-1">
                                    Note: {l.last_note}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
