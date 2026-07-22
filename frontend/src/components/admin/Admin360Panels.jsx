import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { Loader2, X, AlertTriangle, RotateCw } from "lucide-react";

function Drawer({ title, subtitle, onClose, children, testId }) {
    return (
        <>
            <div className="fixed inset-0 bg-black/50 z-50" onClick={onClose} />
            <div className="sa-drawer p-6" data-testid={testId}>
                <div className="flex items-start justify-between mb-6">
                    <div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.2em] sa-gold mb-1">{subtitle}</div>
                        <h3 className="font-serif text-2xl tracking-tight">{title}</h3>
                    </div>
                    <button onClick={onClose} data-testid={`${testId}-close`} className="p-2 hover:bg-surface-alt rounded-md"><X className="w-4 h-4" /></button>
                </div>
                {children}
            </div>
        </>
    );
}

const Stat = ({ label, value }) => (
    <div className="card-flat rounded-lg p-3">
        <div className="font-serif text-xl leading-none">{value}</div>
        <div className="text-[9px] font-mono uppercase tracking-[0.14em] text-muted-foreground mt-1.5">{label}</div>
    </div>
);

const Section = ({ title, children }) => (
    <div className="mb-6">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-2">{title}</div>
        {children}
    </div>
);

const DrawerError = ({ onRetry }) => (
    <div className="flex flex-col items-start gap-3 py-6" data-testid="drawer360-error">
        <div className="flex items-center gap-2 text-destructive text-sm">
            <AlertTriangle className="w-4 h-4" /> Couldn&apos;t load this record.
        </div>
        <p className="text-xs text-muted-foreground">The request failed or timed out. Please try again.</p>
        <button onClick={onRetry} data-testid="drawer360-retry" className="btn-outline text-xs px-3 py-1.5">
            <RotateCw className="w-3.5 h-3.5" /> Retry
        </button>
    </div>
);

export function Org360Drawer({ orgId, onClose, onOpenUser }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState(false);
    const load = useCallback(() => {
        setError(false);
        setData(null);
        api.get(`/admin/org360/${orgId}`, { timeout: 20000 })
            .then((r) => setData(r.data))
            .catch(() => setError(true));
    }, [orgId]);
    useEffect(() => { load(); }, [load]);

    if (error) return <Drawer title="Unavailable" subtitle="Organization 360" onClose={onClose} testId="org360"><DrawerError onRetry={load} /></Drawer>;
    if (!data) return <Drawer title="Loading…" subtitle="Organization 360" onClose={onClose} testId="org360"><Loader2 className="w-5 h-5 animate-spin" /></Drawer>;
    const o = data.organization;
    return (
        <Drawer title={o.name} subtitle="Organization 360" onClose={onClose} testId="org360">
            <div className="grid grid-cols-3 gap-2 mb-6">
                <Stat label="Members" value={data.member_count} />
                <Stat label="Seats" value={`${o.seats_used ?? 0}/${o.seat_count ?? 0}`} />
                <Stat label="Enrollments" value={data.stats.enrollments} />
                <Stat label="Completions" value={data.stats.completions} />
                <Stat label="Avg progress" value={`${data.stats.avg_progress}%`} />
                <Stat label="AI sessions" value={data.stats.ai_sessions} />
            </div>
            <Section title="Profile">
                <div className="text-xs text-muted-foreground space-y-1 font-mono">
                    <div>Tenant ID: {o.id}</div>
                    <div>Domain: @{o.domain || "—"} · Industry: {o.industry || "—"}</div>
                    <div>Tier: {o.subscription_tier || "—"} · Invite: {o.invite_code}</div>
                    <div>Created: {(o.created_at || "").slice(0, 10)}</div>
                </div>
            </Section>
            <Section title={`Members (${data.member_count})`}>
                <div className="space-y-1">
                    {data.members.map((m) => (
                        <button key={m.user_id} onClick={() => onOpenUser(m.user_id)} data-testid={`org360-member-${m.user_id}`}
                            className="w-full text-left card-flat rounded-md px-3 py-2 hover:border-primary transition-colors">
                            <div className="text-sm">{m.user?.full_name || "—"} <span className="text-[10px] font-mono text-muted-foreground ml-1">{m.role || m.user?.role}</span></div>
                            <div className="text-xs text-muted-foreground">{m.user?.email}</div>
                        </button>
                    ))}
                </div>
            </Section>
        </Drawer>
    );
}

export function User360Drawer({ userId, onClose }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState(false);
    const load = useCallback(() => {
        setError(false);
        setData(null);
        api.get(`/admin/user360/${userId}`, { timeout: 20000 })
            .then((r) => setData(r.data))
            .catch(() => setError(true));
    }, [userId]);
    useEffect(() => { load(); }, [load]);

    if (error) return <Drawer title="Unavailable" subtitle="Learner 360" onClose={onClose} testId="user360"><DrawerError onRetry={load} /></Drawer>;
    if (!data) return <Drawer title="Loading…" subtitle="Learner 360" onClose={onClose} testId="user360"><Loader2 className="w-5 h-5 animate-spin" /></Drawer>;
    const u = data.user;
    return (
        <Drawer title={u.full_name || u.email} subtitle="Learner 360" onClose={onClose} testId="user360">
            <div className="grid grid-cols-3 gap-2 mb-6">
                <Stat label="Enrollments" value={data.enrollments.length} />
                <Stat label="Credentials" value={data.certificates.length} />
                <Stat label="AI sessions" value={data.ai_sessions} />
                <Stat label="Referrals" value={data.referrals_made} />
                <Stat label="XP" value={u.xp ?? 0} />
                <Stat label="Streak" value={`${u.streak_days ?? 0}d`} />
            </div>
            <Section title="Account">
                <div className="text-xs text-muted-foreground space-y-1 font-mono">
                    <div>{u.email} · role: {u.role}{u.is_suspended ? " · SUSPENDED" : ""}</div>
                    <div>Auth: {u.auth_provider || "password"} · MFA: {u.mfa_enabled ? "enabled" : "off"}</div>
                    <div>Org: {u.organization || "—"} · Joined {(u.created_at || "").slice(0, 10)}</div>
                    {u.referral_code && <div>Referral code: {u.referral_code}</div>}
                </div>
            </Section>
            <Section title={`Enrollments (${data.enrollments.length})`}>
                <div className="space-y-1">
                    {data.enrollments.map((e) => (
                        <div key={e.id} className="card-flat rounded-md px-3 py-2 flex items-center justify-between gap-2">
                            <div className="text-sm truncate">{e.course_title}</div>
                            <div className="text-xs font-mono shrink-0">{e.completed ? <span className="sa-kpi-up">complete</span> : `${Math.round(e.progress_pct || 0)}%`}</div>
                        </div>
                    ))}
                    {data.enrollments.length === 0 && <div className="text-xs text-muted-foreground">No enrollments yet.</div>}
                </div>
            </Section>
            <Section title={`Credentials (${data.certificates.length})`}>
                <div className="space-y-1">
                    {data.certificates.map((c) => (
                        <div key={c.certificate_id || c.id} className="card-flat rounded-md px-3 py-2">
                            <div className="text-sm">{c.course_title || c.course_id}</div>
                            <div className="text-[10px] font-mono text-muted-foreground">{c.certificate_id} · {(c.issued_at || "").slice(0, 10)}</div>
                        </div>
                    ))}
                    {data.certificates.length === 0 && <div className="text-xs text-muted-foreground">No credentials issued.</div>}
                </div>
            </Section>
            <Section title="Recent logins">
                <div className="text-xs text-muted-foreground space-y-1 font-mono">
                    {data.recent_logins.map((l, i) => (
                        <div key={i}>{(l.created_at || "").slice(0, 16).replace("T", " ")} · {l.city || "?"}, {l.country || "?"}</div>
                    ))}
                    {data.recent_logins.length === 0 && <div>No login records.</div>}
                </div>
            </Section>
            <Section title="Admin audit trail">
                <div className="text-xs text-muted-foreground space-y-1 font-mono">
                    {data.audit_trail.map((a, i) => (
                        <div key={i}>{(a.created_at || "").slice(0, 16).replace("T", " ")} · {a.action} {a.target_label ? `→ ${a.target_label}` : ""}</div>
                    ))}
                    {data.audit_trail.length === 0 && <div>No audit entries.</div>}
                </div>
            </Section>
        </Drawer>
    );
}
