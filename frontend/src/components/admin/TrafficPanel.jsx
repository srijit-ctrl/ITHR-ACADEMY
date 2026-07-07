import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Globe, MapPin, TrendingUp, Users, Eye, Loader2 } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function TrafficPanel() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get("/admin/traffic/summary")
            .then((r) => setData(r.data))
            .catch(() => setData(null))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="py-16 flex items-center justify-center text-muted-foreground" data-testid="traffic-loading"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading traffic…</div>;
    if (!data) return <div className="card-flat p-10 text-center text-sm text-muted-foreground">Could not load traffic data.</div>;

    const t = data.totals;

    return (
        <div className="space-y-6" data-testid="traffic-panel">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Stat label="Today · pageviews" value={t.today_pageviews.toLocaleString()} icon={<Eye className="w-4 h-4" />} testid="traffic-today-pv" />
                <Stat label="Today · unique visitors" value={t.today_unique_visitors.toLocaleString()} icon={<Users className="w-4 h-4" />} testid="traffic-today-uv" accent />
                <Stat label="Last 7d · unique visitors" value={t.seven_day_unique_visitors.toLocaleString()} icon={<TrendingUp className="w-4 h-4" />} testid="traffic-7d-uv" />
                <Stat label="Last 30d · unique visitors" value={t.thirty_day_unique_visitors.toLocaleString()} icon={<Globe className="w-4 h-4" />} testid="traffic-30d-uv" />
            </div>

            {/* Daily chart */}
            <div className="card-flat p-6">
                <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-brand" />
                    <h3 className="font-serif text-lg">Daily traffic · last 30 days</h3>
                </div>
                {(data.daily_last_30d || []).length === 0 ? (
                    <div className="text-sm text-muted-foreground py-6 text-center">No traffic recorded yet. Data starts collecting from today's visitors.</div>
                ) : (
                    <ResponsiveContainer width="100%" height={220}>
                        <LineChart data={data.daily_last_30d}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                            <XAxis dataKey="day" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                            <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                            <Tooltip contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
                            <Line type="monotone" dataKey="unique_visitors" name="Unique visitors" stroke="hsl(var(--brand))" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="views" name="Pageviews" stroke="hsl(var(--brand-navy))" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <ListCard
                    icon={<Globe className="w-4 h-4 text-brand" />}
                    title="Top countries · last 30d"
                    rows={data.top_countries}
                    render={(row) => (
                        <>
                            <span className="text-lg mr-2">{row.flag}</span>
                            <span className="flex-1 text-sm">{row.country || "Unknown"}</span>
                            <span className="text-xs font-mono text-muted-foreground">{row.unique_visitors}</span>
                        </>
                    )}
                    testid="traffic-countries"
                />
                <ListCard
                    icon={<MapPin className="w-4 h-4 text-brand" />}
                    title="Top cities · last 7d"
                    rows={data.top_cities}
                    render={(row) => (
                        <>
                            <span className="text-lg mr-2">{row.flag}</span>
                            <span className="flex-1 text-sm">{row.city || "Unknown"}, <span className="text-muted-foreground">{row.country}</span></span>
                            <span className="text-xs font-mono text-muted-foreground">{row.unique_visitors}</span>
                        </>
                    )}
                    testid="traffic-cities"
                />
            </div>

            <ListCard
                icon={<Eye className="w-4 h-4 text-brand" />}
                title="Top pages · last 7d"
                rows={data.top_pages}
                render={(row) => (
                    <>
                        <span className="flex-1 text-sm font-mono truncate" title={row.path}>{row.path}</span>
                        <span className="text-xs text-muted-foreground mr-3">{row.unique_visitors} uniques</span>
                        <span className="text-xs font-mono text-foreground">{row.views} views</span>
                    </>
                )}
                testid="traffic-pages"
            />
        </div>
    );
}

function Stat({ label, value, icon, accent, testid }) {
    return (
        <div className={`card-flat p-5 ${accent ? "border-brand border-2" : ""}`} data-testid={testid}>
            <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2">
                {icon} {label}
            </div>
            <div className="font-serif text-3xl leading-none">{value}</div>
        </div>
    );
}

function ListCard({ icon, title, rows, render, testid }) {
    return (
        <div className="card-flat p-6" data-testid={testid}>
            <div className="flex items-center gap-2 mb-4">
                {icon}
                <h3 className="font-serif text-lg">{title}</h3>
                <span className="text-xs font-mono text-muted-foreground ml-auto">{(rows || []).length}</span>
            </div>
            {(rows || []).length === 0 ? (
                <div className="text-xs text-muted-foreground py-4">No data yet.</div>
            ) : (
                <div className="divide-y divide-border">
                    {rows.map((row) => {
                        const key = row.path || row.city || row.country || row.hour || row.day || JSON.stringify(row);
                        return (
                            <div key={key} className="flex items-center py-2">{render(row)}</div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
