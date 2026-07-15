import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ArrowDownRight, ArrowUpRight, Download, Loader2, RefreshCw } from "lucide-react";

const fmtVal = (v, format) => {
    if (format === "usd") return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    if (format === "pct") return `${v}%`;
    return Number(v).toLocaleString();
};

export default function CommandCenter({ onNavigate, onOpenUser, onOpenOrg }) {
    const [data, setData] = useState(null);
    const [days, setDays] = useState(30);
    const [loading, setLoading] = useState(true);

    const load = (d = days) => {
        setLoading(true);
        api.get(`/admin/command-center?days=${d}`)
            .then((r) => setData(r.data))
            .catch(() => {})
            .finally(() => setLoading(false));
    };
    useEffect(() => { load(days); /* eslint-disable-next-line */ }, [days]);

    const exportCsv = () => {
        if (!data) return;
        const rows = [["KPI", "Value", "Previous period", "Delta %", "Definition"]];
        data.kpis.forEach((k) => rows.push([k.label, k.value, k.prev_value ?? "", k.delta_pct ?? "", k.definition]));
        const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
        a.download = `ithr-command-center-${days}d.csv`;
        a.click();
    };

    return (
        <div data-testid="command-center">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <div>
                    <h2 className="font-serif text-2xl tracking-tight">Executive Command Centre</h2>
                    <div className="text-[11px] font-mono text-muted-foreground mt-1">
                        {data ? `Last refreshed ${new Date(data.generated_at).toLocaleTimeString()} · comparing vs prior ${days}d` : "Loading…"}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <select value={days} onChange={(e) => setDays(Number(e.target.value))} data-testid="cc-date-range"
                        className="bg-surface border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-primary">
                        <option value={7}>Last 7 days</option>
                        <option value={30}>Last 30 days</option>
                        <option value={90}>Last 90 days</option>
                    </select>
                    <button onClick={() => load()} data-testid="cc-refresh" title="Refresh" className="border border-border hover:border-primary rounded-md p-2.5">
                        <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                    </button>
                    <button onClick={exportCsv} data-testid="cc-export" className="flex items-center gap-2 border border-border hover:border-primary rounded-md px-3 py-2 text-sm">
                        <Download className="w-3.5 h-3.5" /> CSV
                    </button>
                </div>
            </div>
            {!data ? (
                <div className="card-flat p-16 text-center rounded-lg"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>
            ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
                    {data.kpis.map((k) => <KpiCard key={k.key} k={k} onNavigate={onNavigate} />)}
                </div>
            )}
        </div>
    );
}

function KpiCard({ k, onNavigate }) {
    const delta = k.delta_pct;
    return (
        <button
            onClick={() => k.drill && onNavigate(k.drill)}
            data-testid={`kpi-${k.key}`}
            title={k.definition}
            className="card-flat rounded-lg p-4 text-left hover:border-primary transition-colors group"
        >
            <div className="text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground mb-2 leading-tight">{k.label}</div>
            <div className="flex items-end justify-between gap-2">
                <div className="font-serif text-2xl xl:text-3xl leading-none">{fmtVal(k.value, k.format)}</div>
                {delta !== undefined && delta !== null && (
                    <div className={`flex items-center gap-0.5 text-xs font-mono ${delta >= 0 ? "sa-kpi-up" : "sa-kpi-down"}`}>
                        {delta >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        {Math.abs(delta)}%
                    </div>
                )}
            </div>
            {k.prev_value !== undefined && (
                <div className="text-[10px] text-muted-foreground mt-2 font-mono">prev: {fmtVal(k.prev_value, k.format)}</div>
            )}
        </button>
    );
}
