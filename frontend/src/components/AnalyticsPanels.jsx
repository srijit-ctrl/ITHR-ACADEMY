import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid, Cell } from "recharts";
import { api } from "@/lib/api";
import { Loader2, TrendingUp, Award, Users, Building2, BookOpen, Star } from "lucide-react";

/**
 * Two shared analytics panels — one platform-wide (super-admin), one org-scoped
 * (enterprise admin). They fetch from separate endpoints but the sub-widgets
 * (day-series line, top-N bar, funnel bar) are reused.
 */

const TIME_RANGES = [
    { key: 7, label: "7d" },
    { key: 30, label: "30d" },
    { key: 90, label: "90d" },
];

const CHART_COLOR = "hsl(var(--brand))";
const CHART_COLOR_ALT = "hsl(var(--brand-teal, 179 65% 40%))";
const CHART_AXIS = "hsl(var(--muted-foreground))";
const CHART_GRID = "hsl(var(--border))";

// Module-level chart-config constants — extracted from inline JSX props so
// they aren't re-created on every render (avoids unnecessary recharts
// reconciliation of chart internals).
const AXIS_STYLE = { fontSize: 11, fill: CHART_AXIS };
const AXIS_LINE_STYLE = { stroke: CHART_GRID };
const TICK_LINE_STYLE = { stroke: CHART_GRID };
const TOOLTIP_CONTENT_STYLE = { background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 2, fontSize: 12 };
const CHART_MARGIN_SM = { top: 4, right: 8, left: -8, bottom: 4 };
const CHART_MARGIN_FUNNEL = { top: 4, right: 32, left: 24, bottom: 4 };
const CHART_MARGIN_BAR = { top: 4, right: 8, left: -8, bottom: 24 };
const LINE_DOT_ACTIVE = { r: 3, fill: CHART_COLOR };

function useAnalytics(endpoint, days) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState(null);
    useEffect(() => {
        setLoading(true);
        setErr(null);
        api
            .get(`${endpoint}?days=${days}`)
            .then((r) => setData(r.data))
            .catch((e) => setErr(e.response?.data?.detail || "Failed to load analytics"))
            .finally(() => setLoading(false));
    }, [endpoint, days]);
    return { data, loading, err };
}

function RangeSwitcher({ days, setDays, testId }) {
    return (
        <div className="inline-flex bg-surface border border-border rounded-sm p-0.5 gap-0.5" data-testid={testId}>
            {TIME_RANGES.map((r) => (
                <button
                    key={r.key}
                    onClick={() => setDays(r.key)}
                    data-testid={`${testId}-${r.label}`}
                    className={`px-3 py-1 text-xs font-mono uppercase tracking-[0.15em] rounded-sm transition-colors ${
                        days === r.key ? "bg-brand text-white" : "text-muted-foreground hover:text-foreground"
                    }`}
                >
                    {r.label}
                </button>
            ))}
        </div>
    );
}

function StatPip({ label, value, icon: Icon, testId }) {
    return (
        <div className="card-flat p-4" data-testid={testId}>
            {Icon && <Icon className="w-4 h-4 text-brand mb-2" />}
            <div className="font-serif text-3xl leading-none">{value}</div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1.5">{label}</div>
        </div>
    );
}

function TrendCard({ title, series, color, testId }) {
    const total = series?.reduce((s, p) => s + p.count, 0) || 0;
    return (
        <div className="card-flat p-5" data-testid={testId}>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{title}</div>
                    <div className="font-serif text-2xl mt-0.5">{total}</div>
                </div>
                <TrendingUp className="w-4 h-4 text-muted-foreground" />
            </div>
            <div className="h-40 -mx-2">
                <ResponsiveContainer>
                    <LineChart data={series || []}>
                        <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="date" stroke={CHART_AXIS} tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} minTickGap={20} />
                        <YAxis stroke={CHART_AXIS} tick={{ fontSize: 10 }} allowDecimals={false} width={28} />
                        <Tooltip
                            contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
                            labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 500 }}
                        />
                        <Line type="monotone" dataKey="count" stroke={color || CHART_COLOR} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

function TopList({ title, items, valueKey, labelKey, secondaryLabel, icon: Icon, testId }) {
    if (!items || items.length === 0) {
        return (
            <div className="card-flat p-5" data-testid={testId}>
                <div className="flex items-center gap-2 mb-3">
                    {Icon && <Icon className="w-4 h-4 text-muted-foreground" />}
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{title}</div>
                </div>
                <p className="text-sm text-muted-foreground">No data in this window yet.</p>
            </div>
        );
    }
    const max = Math.max(...items.map((i) => i[valueKey] || 0), 1);
    return (
        <div className="card-flat p-5" data-testid={testId}>
            <div className="flex items-center gap-2 mb-4">
                {Icon && <Icon className="w-4 h-4 text-muted-foreground" />}
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{title}</div>
            </div>
            <ol className="space-y-3">
                {items.map((it, idx) => (
                    <li key={it.id || it.slug || it.user_id || it.name || idx} className="text-sm">
                        <div className="flex items-baseline justify-between gap-3">
                            <div className="min-w-0 flex-1">
                                <div className="font-medium truncate">{it[labelKey]}</div>
                                {secondaryLabel && <div className="text-xs text-muted-foreground truncate">{secondaryLabel(it)}</div>}
                            </div>
                            <div className="font-mono text-sm text-brand shrink-0">{it[valueKey]}</div>
                        </div>
                        <div className="mt-1.5 h-1 bg-surface-alt rounded-full overflow-hidden">
                            <div
                                className="h-full bg-brand"
                                style={{ width: `${((it[valueKey] || 0) / max) * 100}%` }}
                            />
                        </div>
                    </li>
                ))}
            </ol>
        </div>
    );
}

// ------------------- SUPER-ADMIN --------------------------------------
export function PlatformAnalyticsPanel() {
    const [days, setDays] = useState(30);
    const { data, loading, err } = useAnalytics("/admin/analytics", days);

    if (loading && !data) return <div className="card-flat p-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>;
    if (err) return <div className="card-flat p-6 text-sm text-destructive">{err}</div>;
    if (!data) return null;

    const founderPct = data.founder_perk.cap ? Math.round((data.founder_perk.claimed / data.founder_perk.cap) * 100) : 0;

    return (
        <div className="space-y-6" data-testid="platform-analytics-panel">
            <div className="flex items-center justify-between">
                <h2 className="font-serif text-2xl">Platform analytics</h2>
                <RangeSwitcher days={days} setDays={setDays} testId="platform-range" />
            </div>

            {/* Top row: 4 stat pips */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatPip label="Total users" value={data.totals.users} icon={Users} testId="analytics-total-users" />
                <StatPip label="Enterprise orgs" value={data.totals.orgs} icon={Building2} testId="analytics-total-orgs" />
                <StatPip label="Certs issued (all-time)" value={data.totals.certs_all_time} icon={Award} testId="analytics-total-certs" />
                <StatPip label="Seats issued" value={data.totals.seats_issued} icon={Users} testId="analytics-total-seats" />
            </div>

            {/* Founder progress */}
            <div className="card-flat p-5" data-testid="founder-perk-progress">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Founding Member perk</div>
                        <div className="font-serif text-2xl mt-0.5">{data.founder_perk.claimed} / {data.founder_perk.cap}</div>
                        <div className="text-xs text-muted-foreground mt-1">
                            {data.founder_perk.remaining} codes remaining · {data.founder_perk.first_course_locked} locked to a first course · {data.founder_perk.cert_used} certs redeemed
                        </div>
                    </div>
                    <Star className="w-5 h-5 text-brand" />
                </div>
                <div className="h-2 bg-surface-alt rounded-full overflow-hidden">
                    <div className="h-full bg-brand transition-all" style={{ width: `${founderPct}%` }} />
                </div>
            </div>

            {/* Trend charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <TrendCard title={`Signups (last ${days}d)`} series={data.signups_per_day} color={CHART_COLOR} testId="signups-trend" />
                <TrendCard title={`Certs issued (last ${days}d)`} series={data.certs_per_day} color={CHART_COLOR_ALT} testId="certs-trend" />
            </div>

            {/* Top lists */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <TopList
                    title={`Top orgs by certs (last ${days}d)`}
                    items={data.top_orgs_by_certs}
                    valueKey="certs"
                    labelKey="name"
                    secondaryLabel={(o) => o.slug}
                    icon={Building2}
                    testId="top-orgs-list"
                />
                <TopList
                    title={`Top courses by enrollment (last ${days}d)`}
                    items={data.top_courses_by_enrollment}
                    valueKey="enrollments"
                    labelKey="title"
                    secondaryLabel={(c) => c.category || c.slug}
                    icon={BookOpen}
                    testId="top-courses-list"
                />
            </div>

            {/* Active users */}
            <div className="grid grid-cols-3 gap-3">
                <StatPip label="Active 24h" value={data.active_users.last_24h} testId="active-24h" />
                <StatPip label="Active 7d" value={data.active_users.last_7d} testId="active-7d" />
                <StatPip label="Active 30d" value={data.active_users.last_30d} testId="active-30d" />
            </div>
        </div>
    );
}

// ------------------- ENTERPRISE ADMIN ----------------------------------
export function OrgAnalyticsPanel() {
    const [days, setDays] = useState(30);
    const { data, loading, err } = useAnalytics("/enterprise/organizations/analytics", days);

    if (loading && !data) return <div className="card-flat p-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>;
    if (err) return <div className="card-flat p-6 text-sm text-destructive">{err}</div>;
    if (!data) return null;

    const funnelMax = Math.max(...(data.funnel || []).map((f) => f.count), 1);

    return (
        <div className="space-y-6" data-testid="org-analytics-panel">
            <div className="flex items-center justify-between">
                <h2 className="font-serif text-2xl">Team analytics</h2>
                <RangeSwitcher days={days} setDays={setDays} testId="org-range" />
            </div>

            {/* Totals */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatPip label="Team members" value={data.totals.members} icon={Users} testId="org-total-members" />
                <StatPip label={`Enrolments (${days}d)`} value={data.totals.enrollments_window} icon={BookOpen} testId="org-enrolments-window" />
                <StatPip label={`Certs (${days}d)`} value={data.totals.certs_window} icon={Award} testId="org-certs-window" />
                <StatPip label="Certs (all-time)" value={data.totals.certs_all_time} icon={Award} testId="org-certs-all-time" />
            </div>

            {/* Trends */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <TrendCard title={`Enrolments (last ${days}d)`} series={data.enrollments_per_day} color={CHART_COLOR} testId="org-enrolments-trend" />
                <TrendCard title={`Certifications issued (last ${days}d)`} series={data.certs_per_day} color={CHART_COLOR_ALT} testId="org-certs-trend" />
            </div>

            {/* Top courses + Top learners */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <TopList
                    title={`Top courses (last ${days}d)`}
                    items={data.top_courses}
                    valueKey="enrollments"
                    labelKey="title"
                    secondaryLabel={(c) => c.category || c.slug}
                    icon={BookOpen}
                    testId="org-top-courses"
                />
                <TopList
                    title="Top learners (window enrolments + all-time certs)"
                    items={data.top_learners}
                    valueKey="certs_all_time"
                    labelKey="full_name"
                    secondaryLabel={(u) => `${u.email} · ${u.enrollments_window} enrolments · ${u.avg_progress}% avg progress`}
                    icon={Users}
                    testId="org-top-learners"
                />
            </div>

            {/* Department leaderboard */}
            <TopList
                title="Department leaderboard (cert coverage %)"
                items={data.departments}
                valueKey="cert_coverage_pct"
                labelKey="name"
                secondaryLabel={(d) => `${d.members} members · ${d.certs} certs · ${d.avg_progress}% avg progress`}
                icon={Building2}
                testId="org-dept-leaderboard"
            />

            {/* Completion funnel */}
            <div className="card-flat p-5" data-testid="org-funnel">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-4">Completion funnel (all-time)</div>
                <div className="h-56">
                    <ResponsiveContainer>
                        <BarChart data={data.funnel} layout="vertical" margin={{ top: 4, right: 32, left: 24, bottom: 4 }}>
                            <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" horizontal={false} />
                            <XAxis type="number" stroke={CHART_AXIS} tick={{ fontSize: 11 }} allowDecimals={false} />
                            <YAxis dataKey="stage" type="category" stroke={CHART_AXIS} tick={{ fontSize: 12 }} width={90} />
                            <Tooltip
                                contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
                            />
                            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                                {data.funnel.map((entry, i) => (
                                    <Cell key={entry.stage} fill={CHART_COLOR} opacity={0.4 + (entry.count / funnelMax) * 0.6} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
