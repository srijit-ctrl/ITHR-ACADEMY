import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, Search, ShieldOff, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const Loading = () => <div className="card-flat rounded-lg p-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>;

/* ================= Learning Funnel ================= */

export function LearningFunnelPanel() {
    const [data, setData] = useState(null);
    useEffect(() => { api.get("/admin/learning-funnel").then((r) => setData(r.data)).catch(() => {}); }, []);
    if (!data) return <Loading />;
    const max = Math.max(...data.stages.map((s) => s.count), 1);
    return (
        <div data-testid="learning-funnel">
            <h2 className="font-serif text-2xl tracking-tight mb-6">Learning Funnel</h2>
            <div className="card-flat rounded-lg p-6 mb-8">
                {data.stages.map((s, i) => (
                    <div key={s.stage} className="flex items-center gap-3 mb-2.5" data-testid={`funnel-stage-${i}`}>
                        <div className="w-36 text-xs font-mono text-muted-foreground text-right shrink-0">{s.stage}</div>
                        <div className="flex-1 h-7 bg-surface-alt rounded-sm overflow-hidden">
                            <div className="h-full rounded-sm flex items-center px-2 text-[11px] font-mono text-white"
                                style={{ width: `${Math.max((s.count / max) * 100, 4)}%`, background: `linear-gradient(90deg,#2E7DFF,#1E5FD0)` }}>
                                {s.count.toLocaleString()}
                            </div>
                        </div>
                        <div className="w-14 text-xs font-mono text-muted-foreground shrink-0">
                            {i > 0 && data.stages[i - 1].count > 0 ? `${Math.round((s.count / data.stages[i - 1].count) * 100)}%` : ""}
                        </div>
                    </div>
                ))}
            </div>
            <h3 className="font-serif text-lg mb-3">Per-course drop-off</h3>
            <div className="card-flat rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead><tr className="text-left text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground border-b border-border">
                        <th className="p-3">Course</th><th>Enrolled</th><th>Started</th><th>Completed</th><th>Credentialed</th><th>Avg progress</th><th>Drop-off</th>
                    </tr></thead>
                    <tbody>
                        {data.courses.map((c) => (
                            <tr key={c.course_id} className="border-b border-border/50" data-testid={`funnel-course-${c.course_id}`}>
                                <td className="p-3 max-w-[280px] truncate">{c.title}</td>
                                <td>{c.enrolled}</td><td>{c.started}</td><td>{c.completed}</td><td>{c.credentialed}</td>
                                <td>{c.avg_progress}%</td>
                                <td className={c.dropoff_pct > 70 ? "sa-kpi-down font-mono" : "font-mono"}>{c.dropoff_pct}%</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/* ================= Assessment Analytics ================= */

export function AssessmentAnalyticsPanel() {
    const [data, setData] = useState(null);
    useEffect(() => { api.get("/admin/assessment-analytics").then((r) => setData(r.data)).catch(() => {}); }, []);
    if (!data) return <Loading />;
    if (data.total === 0) return (
        <div data-testid="assessment-analytics">
            <h2 className="font-serif text-2xl tracking-tight mb-6">Assessment Quality</h2>
            <div className="card-flat rounded-lg p-12 text-center text-sm text-muted-foreground" data-testid="assessments-empty">No assessment attempts recorded yet — analytics will populate as learners take exams.</div>
        </div>
    );
    const s = data.summary;
    const cards = [
        ["Attempts", s.attempts], ["Pass rate", `${s.pass_rate}%`], ["Avg score", s.avg_score],
        ["Median score", s.median_score], ["First-attempt pass", `${s.first_attempt_pass_rate}%`],
        ["Avg attempts to pass", s.avg_attempts_to_pass ?? "—"],
    ];
    return (
        <div data-testid="assessment-analytics">
            <h2 className="font-serif text-2xl tracking-tight mb-6">Assessment Quality</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-8">
                {cards.map(([l, v]) => (
                    <div key={l} className="card-flat rounded-lg p-4">
                        <div className="font-serif text-2xl leading-none">{v}</div>
                        <div className="text-[9px] font-mono uppercase tracking-[0.14em] text-muted-foreground mt-2">{l}</div>
                    </div>
                ))}
            </div>
            <h3 className="font-serif text-lg mb-3">By course</h3>
            <div className="card-flat rounded-lg overflow-x-auto mb-8">
                <table className="w-full text-sm">
                    <thead><tr className="text-left text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground border-b border-border">
                        <th className="p-3">Course</th><th>Attempts</th><th>Pass rate</th><th>Avg score</th><th>Avg duration</th>
                    </tr></thead>
                    <tbody>
                        {data.per_course.map((c) => (
                            <tr key={c.course_id} className="border-b border-border/50">
                                <td className="p-3 max-w-[280px] truncate">{c.title}</td>
                                <td>{c.attempts}</td>
                                <td className={c.pass_rate < 40 ? "sa-kpi-down font-mono" : "font-mono"}>{c.pass_rate}%</td>
                                <td>{c.avg_score}</td><td>{c.avg_duration_min}m</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <h3 className="font-serif text-lg mb-3">Recent attempts</h3>
            <div className="card-flat rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead><tr className="text-left text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground border-b border-border">
                        <th className="p-3">Learner</th><th>Course</th><th>Score</th><th>Result</th><th>When</th>
                    </tr></thead>
                    <tbody>
                        {data.recent.map((a) => (
                            <tr key={a.id} className="border-b border-border/50">
                                <td className="p-3">{a.user_name}</td>
                                <td className="max-w-[240px] truncate">{a.course_title}</td>
                                <td className="font-mono">{a.score}</td>
                                <td>{a.passed ? <span className="sa-kpi-up">pass</span> : <span className="sa-kpi-down">fail</span>}</td>
                                <td className="text-xs text-muted-foreground font-mono">{(a.attempted_at || "").slice(0, 16).replace("T", " ")}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/* ================= Credential Manager ================= */

export function CredentialManagerPanel() {
    const [data, setData] = useState(null);
    const [q, setQ] = useState("");
    const load = (query = q) => api.get(`/admin/credentials?q=${encodeURIComponent(query)}`).then((r) => setData(r.data)).catch(() => {});
    useEffect(() => { load(""); /* eslint-disable-next-line */ }, []);

    const revoke = async (id) => {
        const reason = window.prompt("Revocation reason (required, audit-logged):");
        if (!reason) return;
        try {
            await api.post(`/admin/credentials/${id}/revoke`, { reason });
            toast.success("Credential revoked");
            load();
        } catch (e) { toast.error(e.response?.data?.detail || "Revoke failed"); }
    };
    const restore = async (id) => {
        try {
            await api.post(`/admin/credentials/${id}/restore`);
            toast.success("Credential restored");
            load();
        } catch (e) { toast.error(e.response?.data?.detail || "Restore failed"); }
    };

    if (!data) return <Loading />;
    return (
        <div data-testid="credential-manager">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <div>
                    <h2 className="font-serif text-2xl tracking-tight">Credential Management</h2>
                    <div className="text-[11px] font-mono text-muted-foreground mt-1">{data.total} issued · {data.revoked} revoked</div>
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()}
                            placeholder="Search name, course, cert ID…" data-testid="cred-search"
                            className="bg-surface border border-border rounded-md pl-9 pr-3 py-2 text-sm w-64 focus:outline-none focus:border-primary" />
                    </div>
                    <button onClick={() => load()} data-testid="cred-search-btn" className="border border-border hover:border-primary rounded-md px-3 py-2 text-sm">Search</button>
                </div>
            </div>
            <div className="card-flat rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                    <thead><tr className="text-left text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground border-b border-border">
                        <th className="p-3">Recipient</th><th>Course</th><th>Cert ID</th><th>Score</th><th>Issued</th><th>Verifies</th><th>Status</th><th></th>
                    </tr></thead>
                    <tbody>
                        {data.credentials.map((c) => (
                            <tr key={c.certificate_id} className="border-b border-border/50" data-testid={`cred-row-${c.certificate_id}`}>
                                <td className="p-3">{c.user_name}</td>
                                <td className="max-w-[220px] truncate">{c.course_title}</td>
                                <td className="font-mono text-xs">{c.certificate_id}</td>
                                <td className="font-mono">{c.score}</td>
                                <td className="text-xs text-muted-foreground">{(c.issued_at || "").slice(0, 10)}</td>
                                <td className="font-mono">{c.verifications}</td>
                                <td>{c.revoked ? <span className="sa-kpi-down text-xs">revoked</span> : <span className="sa-kpi-up text-xs">active</span>}</td>
                                <td className="text-right pr-3">
                                    {c.revoked ? (
                                        <button onClick={() => restore(c.certificate_id)} data-testid={`cred-restore-${c.certificate_id}`} title="Restore" className="p-1.5 border border-border hover:border-primary rounded-md"><ShieldCheck className="w-3.5 h-3.5" /></button>
                                    ) : (
                                        <button onClick={() => revoke(c.certificate_id)} data-testid={`cred-revoke-${c.certificate_id}`} title="Revoke" className="p-1.5 border border-border hover:border-red-500 hover:text-red-500 rounded-md"><ShieldOff className="w-3.5 h-3.5" /></button>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {data.credentials.length === 0 && <tr><td colSpan={8} className="p-8 text-center text-muted-foreground text-sm">No credentials match.</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/* ================= AI Ops ================= */

export function AiOpsPanel() {
    const [data, setData] = useState(null);
    const [days, setDays] = useState(30);
    useEffect(() => { setData(null); api.get(`/admin/ai-ops?days=${days}`).then((r) => setData(r.data)).catch(() => {}); }, [days]);
    if (!data) return <Loading />;
    const s = data.summary;
    const maxDaily = Math.max(...data.daily.map((d) => d.sessions), 1);
    const satisfaction = s.satisfaction_pct == null ? "—" : `${s.satisfaction_pct}%`;
    const cards = [
        ["Conversations (period)", s.sessions], ["All-time conversations", s.all_time_sessions],
        ["Active AI users", s.active_users], ["Messages", s.messages],
        ["Avg msgs / convo", s.avg_msgs_per_session],
        ["Satisfaction", satisfaction],
        ["Est. cost (USD)*", `$${s.est_cost_usd}`],
    ];
    return (
        <div data-testid="ai-ops">
            <div className="flex items-center justify-between mb-6">
                <h2 className="font-serif text-2xl tracking-tight">Aletheia · AI Operations</h2>
                <select value={days} onChange={(e) => setDays(Number(e.target.value))} data-testid="aiops-range"
                    className="bg-surface border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-primary">
                    <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
                </select>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3 mb-2">
                {cards.map(([l, v]) => (
                    <div key={l} className="card-flat rounded-lg p-4">
                        <div className="font-serif text-xl leading-none">{v}</div>
                        <div className="text-[9px] font-mono uppercase tracking-[0.12em] text-muted-foreground mt-2">{l}</div>
                    </div>
                ))}
            </div>
            <div className="text-[10px] text-muted-foreground mb-8">
                * Cost figure is a heuristic estimate (~$6 / 1M tokens on {s.est_tokens.toLocaleString()} est. tokens) — not billing data.
                Satisfaction reflects actual learner thumbs (up ÷ (up + down)); coverage is {s.rating_coverage_pct}% of messages rated.
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                <div className="card-flat rounded-lg p-5" data-testid="aiops-ratings-block">
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">Learner ratings</div>
                    <div className="flex items-baseline gap-6">
                        <div>
                            <div className="font-serif text-2xl leading-none text-brand" data-testid="aiops-ratings-up">
                                ▲ {s.ratings_up}
                            </div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mt-1.5">Thumbs up</div>
                        </div>
                        <div>
                            <div className="font-serif text-2xl leading-none text-destructive" data-testid="aiops-ratings-down">
                                ▼ {s.ratings_down}
                            </div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mt-1.5">Thumbs down</div>
                        </div>
                        <div>
                            <div className="font-serif text-2xl leading-none">
                                {s.ratings_total}
                            </div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mt-1.5">Total rated</div>
                        </div>
                    </div>
                    {s.ratings_total > 0 && (
                        <div className="mt-4 h-1.5 rounded-full overflow-hidden bg-border/60">
                            <div
                                className="h-full"
                                style={{
                                    width: `${(s.ratings_up / s.ratings_total) * 100}%`,
                                    background: "linear-gradient(90deg, #C6A15A, #E4CE9A)",
                                }}
                            />
                        </div>
                    )}
                </div>
                <div className="card-flat rounded-lg p-5 lg:col-span-2" data-testid="aiops-negative-reasons">
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">
                        Latest thumbs-down reasons ({(data.recent_negative_reasons || []).length})
                    </div>
                    {(data.recent_negative_reasons || []).length === 0 ? (
                        <div className="text-xs text-muted-foreground italic">No negative feedback with reasons in this period.</div>
                    ) : (
                        <ul className="space-y-2 max-h-40 overflow-y-auto pr-1">
                            {data.recent_negative_reasons.map((r, i) => (
                                <li key={i} className="text-xs border-l-2 border-destructive/60 pl-3 py-0.5">
                                    <div className="text-foreground">{r.reason}</div>
                                    <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{(r.at || "").slice(0, 16).replace("T", " ")}</div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="card-flat rounded-lg p-5">
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-4">Conversations per day</div>
                    <div className="flex items-end gap-1 h-32">
                        {data.daily.map((d) => (
                            <div key={d.date} title={`${d.date}: ${d.sessions}`} className="flex-1 rounded-t-sm" style={{ height: `${(d.sessions / maxDaily) * 100}%`, minHeight: 3, background: "#2E7DFF" }} />
                        ))}
                        {data.daily.length === 0 && <div className="text-xs text-muted-foreground">No activity in period.</div>}
                    </div>
                </div>
                <div className="card-flat rounded-lg p-5">
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-4">Top conversation topics</div>
                    {data.top_topics.map((t) => (
                        <div key={t.topic} className="flex items-center justify-between text-sm py-1.5 border-b border-border/40">
                            <span className="truncate mr-2">{t.topic}</span>
                            <span className="font-mono text-xs text-muted-foreground shrink-0">{t.sessions}</span>
                        </div>
                    ))}
                    {data.top_topics.length === 0 && <div className="text-xs text-muted-foreground">No conversations in period.</div>}
                </div>
            </div>
        </div>
    );
}
