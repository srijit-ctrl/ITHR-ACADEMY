import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
    BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis,
    CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Loader2, Users, TrendingUp, GraduationCap, Award, DollarSign, Zap, Globe2 } from "lucide-react";

const BRAND_TEAL = "#00a897";
const BRAND_NAVY = "#0d1321";
const BRAND_GOLD = "#d4a836";
const BAND_COLORS = ["#00a897", "#0d1321", "#d4a836", "#5b7ba8", "#c8a55b", "#7d8ba0"];

function formatCurrency(n) {
    return `$${(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function Kpi({ icon: Icon, label, value, tone = "default", testId, onClick, linkLabel }) {
    const toneCls = tone === "green" ? "text-brand" : tone === "red" ? "text-destructive" : "text-foreground";
    const clickable = typeof onClick === "function";
    return (
        <div
            className={`card-flat p-5 ${clickable ? "cursor-pointer transition-colors hover:border-brand/60" : ""}`}
            data-testid={testId}
            onClick={onClick}
            role={clickable ? "button" : undefined}
        >
            <div className="flex items-center justify-between mb-3">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{label}</div>
                <Icon className={`w-3.5 h-3.5 ${toneCls}`} />
            </div>
            <div className={`font-serif text-3xl leading-none ${toneCls}`}>{value}</div>
            {clickable && (
                <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-brand mt-2">{linkLabel || "view"} →</div>
            )}
        </div>
    );
}

function LlmHealthPill({ status }) {
    const green = status === "green";
    return (
        <div className="card-flat p-5" data-testid="kpi-llm-health">
            <div className="flex items-center justify-between mb-3">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">LLM key</div>
                <Zap className={`w-3.5 h-3.5 ${green ? "text-brand" : "text-destructive"}`} />
            </div>
            <div className="flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${green ? "bg-brand animate-pulse" : "bg-destructive"}`} />
                <span className="font-serif text-2xl">{green ? "Healthy" : "Down"}</span>
            </div>
        </div>
    );
}

function Card({ title, children, testId, className = "" }) {
    return (
        <div className={`card-flat p-5 ${className}`} data-testid={testId}>
            <div className="overline mb-4">{title}</div>
            {children}
        </div>
    );
}

export default function KpiDashboard({ onNavigate }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [tsMetric, setTsMetric] = useState("signups");
    const [tsDays, setTsDays] = useState(30);
    const [tsData, setTsData] = useState(null);
    const [tsLoading, setTsLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get("/admin/dashboard");
            setData(res.data);
        } catch (e) {
            console.debug("[KpiDashboard] load failed:", e?.message);
        } finally {
            setLoading(false);
        }
    }, []);

    const loadTs = useCallback(async () => {
        setTsLoading(true);
        try {
            const res = await api.get(`/admin/dashboard/timeseries?metric=${tsMetric}&days=${tsDays}`);
            setTsData(res.data);
        } catch (e) {
            console.debug("[KpiDashboard] ts load failed:", e?.message);
        } finally {
            setTsLoading(false);
        }
    }, [tsMetric, tsDays]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { loadTs(); }, [loadTs]);

    const langData = useMemo(
        () => (data?.language_distribution || []).map((l) => ({ name: l.language, value: l.count })),
        [data]
    );
    const bandData = useMemo(
        () => (data?.band_distribution || []).map((b) => ({ name: b.band, value: b.count })),
        [data]
    );

    if (loading || !data) {
        return (
            <div className="flex items-center justify-center py-24 text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading dashboard…
            </div>
        );
    }

    const k = data.kpis;

    return (
        <div className="space-y-6" data-testid="kpi-dashboard">
            {/* KPI Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4" data-testid="kpi-row">
                <Kpi icon={Users} label="Total users" value={k.total_users.toLocaleString()} testId="kpi-total-users" onClick={() => onNavigate?.("users")} linkLabel="users" />
                <Kpi icon={TrendingUp} label="Active 7d" value={k.active_7d.toLocaleString()} testId="kpi-active-7d" onClick={() => onNavigate?.("sessions")} linkLabel="sessions" />
                <Kpi icon={TrendingUp} label="Active 30d" value={k.active_30d.toLocaleString()} testId="kpi-active-30d" onClick={() => onNavigate?.("sessions")} linkLabel="sessions" />
                <Kpi icon={GraduationCap} label="Enrollments" value={k.enrollments_total.toLocaleString()} testId="kpi-enrollments" onClick={() => setTsMetric("enrollments")} linkLabel="time series" />
                <Kpi icon={Award} label="Exam pass rate" value={`${k.exam_pass_rate}%`} testId="kpi-pass-rate" onClick={() => setTsMetric("exam_attempts")} linkLabel="attempts" />
                <Kpi icon={DollarSign} label="Revenue (paid)" value={formatCurrency(k.revenue_total)} testId="kpi-revenue" onClick={() => setTsMetric("orders")} linkLabel="orders" />
                <LlmHealthPill status={k.llm_key_health} />
            </div>

            {/* Signups + Enrollments line */}
            <Card title="Signups + enrollments · last 30d" testId="chart-signups-enrollments">
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data.signups_enrollments_30d}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e0e6ed" />
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                            <Tooltip />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Line type="monotone" dataKey="signups" stroke={BRAND_TEAL} strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="enrollments" stroke={BRAND_NAVY} strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </Card>

            {/* Two-col: top courses bar + geo card */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="Top courses by enrollment" testId="chart-top-courses">
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data.top_courses} layout="vertical" margin={{ left: 24, right: 12 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#e0e6ed" />
                                <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                                <YAxis
                                    type="category"
                                    dataKey="title"
                                    tick={{ fontSize: 10 }}
                                    width={140}
                                    tickFormatter={(t) => (t?.length > 22 ? t.slice(0, 22) + "…" : t)}
                                />
                                <Tooltip />
                                <Bar
                                    dataKey="enrollments"
                                    fill={BRAND_TEAL}
                                    cursor="pointer"
                                    onClick={(d) => d?.slug && window.open(`/courses/${d.slug}`, "_blank")}
                                />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-2">Click a bar to open the course page</div>
                </Card>

                <Card title="Global reach · last 30d" testId="geo-card">
                    <div className="flex items-center gap-6 mb-4">
                        <div>
                            <div className="font-serif text-3xl text-brand">{data.geo.countries}</div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">countries</div>
                        </div>
                        <div>
                            <div className="font-serif text-3xl">{data.geo.cities}</div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">cities</div>
                        </div>
                        <div>
                            <div className="font-serif text-3xl">{data.geo.logins_30d}</div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">logins</div>
                        </div>
                        <Globe2 className="ml-auto w-6 h-6 text-brand" />
                    </div>
                    <div className="border-t border-border pt-3">
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2">Top countries</div>
                        {(data.geo.top_countries || []).length === 0 && (
                            <div className="text-xs text-muted-foreground italic">No login data yet — will populate as users log in.</div>
                        )}
                        {(data.geo.top_countries || []).map((c) => (
                            <div key={c.country} className="flex items-center justify-between py-1.5 text-sm">
                                <span><span className="text-lg mr-2">{c.flag}</span>{c.country}</span>
                                <span className="text-muted-foreground font-mono text-xs">{c.count}</span>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            {/* Two-col: band pie + language pie */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="Band distribution (enrollments by difficulty)" testId="chart-band">
                    <div className="h-56">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={bandData} dataKey="value" nameKey="name" outerRadius={80} label={(e) => e.name}>
                                    {bandData.map((entry) => <Cell key={entry.name} fill={BAND_COLORS[bandData.indexOf(entry) % BAND_COLORS.length]} />)}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </Card>

                <Card title="Language distribution (logins · last 30d)" testId="chart-language">
                    <div className="h-56">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={langData} dataKey="value" nameKey="name" outerRadius={80} label={(e) => e.name}>
                                    {langData.map((entry) => <Cell key={entry.name} fill={BAND_COLORS[langData.indexOf(entry) % BAND_COLORS.length]} />)}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>

            {/* Time series on demand */}
            <Card title="Time series on demand" testId="chart-timeseries">
                <div className="flex items-center gap-3 mb-4">
                    <select
                        value={tsMetric}
                        onChange={(e) => setTsMetric(e.target.value)}
                        data-testid="ts-metric"
                        className="bg-surface border border-border rounded-sm px-2 py-1 text-xs"
                    >
                        <option value="signups">Signups</option>
                        <option value="enrollments">Enrollments</option>
                        <option value="exam_attempts">Exam attempts</option>
                        <option value="orders">Orders</option>
                    </select>
                    <div className="flex items-center gap-1">
                        {[7, 30, 90].map((d) => (
                            <button
                                key={d}
                                onClick={() => setTsDays(d)}
                                data-testid={`ts-range-${d}`}
                                className={`px-2 py-1 text-[10px] font-mono uppercase tracking-[0.15em] ${
                                    tsDays === d ? "bg-brand text-white" : "text-muted-foreground hover:text-foreground"
                                }`}
                            >
                                {d}d
                            </button>
                        ))}
                    </div>
                    {tsLoading && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
                </div>
                <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={tsData?.series || []}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e0e6ed" />
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                            <Tooltip />
                            <Line type="monotone" dataKey="count" stroke={BRAND_GOLD} strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </Card>
        </div>
    );
}
