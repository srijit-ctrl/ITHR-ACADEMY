import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, CheckCircle2, XCircle, Send, MessageCircle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

/**
 * Super Admin — WhatsApp operations panel.
 *
 * Minimum viable ops surface required by the brief:
 *   • Opt-in rate + integration-configured state
 *   • Per-template configuration state (which SIDs are still pending Meta)
 *   • Recent-send status breakdown (sent/delivered/failed/skipped_*)
 *   • Failed-send list with error codes (63018 rate limit, 63003 invalid
 *     number, etc.) for triage
 *   • Trigger a broadcast for a course slug (dry-run + live)
 */
export function WhatsAppAdminPanel() {
    const [data, setData] = useState(null);
    const [slug, setSlug] = useState("");
    const [busy, setBusy] = useState(false);
    const [lastResult, setLastResult] = useState(null);

    const load = () => api.get("/admin/whatsapp/overview").then((r) => setData(r.data)).catch(() => {});
    useEffect(() => { load(); }, []);

    if (!data) return <div className="p-8 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>;

    const doBroadcast = async (dryRun) => {
        if (!slug.trim()) { toast.error("Enter a course slug first."); return; }
        setBusy(true);
        try {
            const r = await api.post(`/admin/whatsapp/broadcast/new-course?course_slug=${encodeURIComponent(slug.trim())}&dry_run=${dryRun}`);
            setLastResult(r.data);
            toast.success(dryRun ? `Dry run — audience ${r.data.audience_size}` : `Broadcast complete. See counts below.`);
            if (!dryRun) load();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Broadcast failed.");
        } finally { setBusy(false); }
    };

    const statusEntries = Object.entries(data.recent_sends_status_breakdown || {}).sort((a, b) => b[1] - a[1]);

    return (
        <div className="space-y-6" data-testid="whatsapp-admin-panel">
            <div className="flex items-baseline justify-between mb-2">
                <div className="flex items-center gap-2">
                    <MessageCircle className="w-4 h-4 text-brand" />
                    <h2 className="font-serif text-2xl tracking-tight">WhatsApp operations</h2>
                </div>
                <span className={`text-[10px] font-mono uppercase tracking-[0.15em] flex items-center gap-1 ${data.integration_configured ? "text-brand" : "text-destructive"}`}>
                    {data.integration_configured ? <><CheckCircle2 className="w-3 h-3" /> Integration configured</> : <><XCircle className="w-3 h-3" /> Missing Twilio credentials</>}
                </span>
            </div>

            {/* KPI cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="whatsapp-kpi-cards">
                <Kpi label="Opt-in rate" value={`${data.opt_in_rate_pct}%`} sub={`${data.opted_in} of ${data.total_users} users`} />
                <Kpi label="Sent (last 200)" value={statusEntries.reduce((n, [_, v]) => n + v, 0)} sub={`Statuses: ${statusEntries.length}`} />
                <Kpi label="Failed sends" value={data.failed_sends?.length || 0} sub="With error code" />
            </div>

            {/* Template readiness */}
            <div className="card-flat p-6" data-testid="whatsapp-templates-status">
                <div className="flex items-center gap-2 mb-3">
                    <ShieldCheck className="w-3.5 h-3.5 text-brand" />
                    <h3 className="font-serif text-lg tracking-tight">Content templates</h3>
                </div>
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-b border-border">
                            <th className="text-left py-2 pr-4">Template key</th>
                            <th className="text-left py-2">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.templates.map((t) => (
                            <tr key={t.key} className="border-b border-border/40" data-testid={`whatsapp-template-${t.key}`}>
                                <td className="py-2.5 pr-4 font-mono text-xs">{t.key}</td>
                                <td className="py-2.5">
                                    {t.configured ? (
                                        <span className="inline-flex items-center gap-1 text-brand text-xs"><CheckCircle2 className="w-3.5 h-3.5" /> Configured</span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 text-muted-foreground text-xs"><XCircle className="w-3.5 h-3.5" /> Awaiting Meta approval + env var</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Broadcast trigger — new course */}
            <div className="card-flat p-6" data-testid="whatsapp-broadcast-form">
                <div className="flex items-center gap-2 mb-3">
                    <Send className="w-3.5 h-3.5 text-brand" />
                    <h3 className="font-serif text-lg tracking-tight">Broadcast — new course published</h3>
                </div>
                <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
                    Sends the <span className="font-mono">new_course</span> template to every opted-in learner. Idempotent — a repeat call for the same course won't re-send to previously-notified users. Rate-limited to 80 msg/s per Twilio sender.
                </p>
                <div className="flex flex-wrap gap-2">
                    <input
                        value={slug}
                        onChange={(e) => setSlug(e.target.value)}
                        placeholder="course-slug e.g. agentic-ai-foundations"
                        data-testid="whatsapp-broadcast-slug"
                        className="flex-1 min-w-[240px] text-sm bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                    />
                    <button onClick={() => doBroadcast(true)} disabled={busy} data-testid="whatsapp-broadcast-dry-run" className="btn-outline text-xs">
                        {busy ? "…" : "Dry run"}
                    </button>
                    <button onClick={() => doBroadcast(false)} disabled={busy} data-testid="whatsapp-broadcast-send" className="btn-primary text-xs">
                        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Send"}
                    </button>
                </div>
                {lastResult && (
                    <pre className="mt-4 bg-surface border border-border rounded-sm px-3 py-2 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap" data-testid="whatsapp-broadcast-result">
{JSON.stringify(lastResult, null, 2)}
                    </pre>
                )}
            </div>

            {/* Status breakdown */}
            {statusEntries.length > 0 && (
                <div className="card-flat p-6" data-testid="whatsapp-status-breakdown">
                    <h3 className="font-serif text-lg tracking-tight mb-3">Recent send status</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {statusEntries.map(([s, n]) => (
                            <div key={s} className="border border-border rounded-sm px-3 py-2">
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground truncate">{s}</div>
                                <div className="font-serif text-xl">{n}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Failed sends */}
            {data.failed_sends?.length > 0 && (
                <div className="card-flat p-6" data-testid="whatsapp-failed-sends">
                    <h3 className="font-serif text-lg tracking-tight mb-3">Failed sends</h3>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-b border-border">
                                <th className="text-left py-2">To</th>
                                <th className="text-left py-2">Template</th>
                                <th className="text-left py-2">Error</th>
                                <th className="text-left py-2">When</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.failed_sends.map((r, i) => (
                                <tr key={i} className="border-b border-border/40">
                                    <td className="py-2 font-mono text-xs">{r.to || "—"}</td>
                                    <td className="py-2 text-xs">{r.template_key}</td>
                                    <td className="py-2 text-xs">
                                        {r.error_code ? <span className="font-mono text-destructive">{r.error_code}</span> : "—"}
                                        {r.error_message && <span className="text-muted-foreground ml-2">{r.error_message}</span>}
                                    </td>
                                    <td className="py-2 text-xs text-muted-foreground font-mono">{(r.sent_at || "").slice(0, 16).replace("T", " ")}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

function Kpi({ label, value, sub }) {
    return (
        <div className="card-flat p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2">{label}</div>
            <div className="font-serif text-3xl leading-none">{value}</div>
            {sub && <div className="text-[11px] text-muted-foreground mt-2">{sub}</div>}
        </div>
    );
}
