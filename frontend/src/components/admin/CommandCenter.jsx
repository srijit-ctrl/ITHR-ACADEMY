import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
    Users, TrendingUp, DollarSign, Award, GraduationCap, Bot, MessageCircle,
    Building2, ArrowDownRight, ArrowUpRight, Download, Loader2, RefreshCw, Send,
    Sparkles, Radar, Zap, KeyRound, ShieldAlert
} from "lucide-react";
import ActivityFeedPanel from "./ActivityFeedPanel";

/* --------------------------------------------------------------------------
 * KPI presentation — accent + icon inferred from the KPI key. Any KPI not
 * mapped here falls back to teal/BarChart3.
 * ------------------------------------------------------------------------ */
const KPI_META = {
    total_users:            { accent: "teal",   icon: Users },
    new_users:              { accent: "teal",   icon: Users },
    dau:                    { accent: "blue",   icon: TrendingUp },
    mau:                    { accent: "blue",   icon: TrendingUp },
    active_users:           { accent: "blue",   icon: TrendingUp },
    total_orgs:             { accent: "navy",   icon: Building2 },
    seats_purchased:        { accent: "navy",   icon: Building2 },
    seats_used:             { accent: "navy",   icon: Building2 },
    new_enrollments:        { accent: "violet", icon: GraduationCap },
    completions:            { accent: "violet", icon: GraduationCap },
    completion_rate:        { accent: "violet", icon: GraduationCap },
    assessment_attempts:    { accent: "gold",   icon: Award },
    pass_rate:              { accent: "gold",   icon: Award },
    certificates_issued:    { accent: "gold",   icon: Award },
    total_certs:            { accent: "gold",   icon: Award },
    verifications:          { accent: "gold",   icon: Award },
    ai_sessions:            { accent: "blue",   icon: Bot },
    ai_active_users:        { accent: "blue",   icon: Bot },
    revenue:                { accent: "teal",   icon: DollarSign },
    referral_signups:       { accent: "teal",   icon: MessageCircle },
    suspended_users:        { accent: "rose",   icon: ShieldAlert },
    mfa_users:              { accent: "navy",   icon: KeyRound },
};

const fmtVal = (v, format) => {
    if (format === "usd") return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    if (format === "pct") return `${v}%`;
    return Number(v).toLocaleString();
};

/* Deterministic mini bar chart from a KPI. Adds sparkle without pretending
 * we have a full timeseries per KPI on this endpoint. */
function MiniBars({ seed = 5, delta = 0 }) {
    const bars = useMemo(() => {
        const s = Math.abs(seed || 1);
        const arr = [];
        for (let i = 0; i < 12; i++) {
            const wave = 0.35 + 0.5 * Math.abs(Math.sin(s + i * 0.9));
            const trend = delta >= 0 ? i / 20 : -i / 22;
            arr.push(Math.max(0.14, Math.min(1, wave + trend)));
        }
        return arr;
    }, [seed, delta]);
    return (
        <div className="flex items-end gap-[3px] h-8 mt-2 opacity-80" aria-hidden>
            {bars.map((b, i) => (
                <span
                    key={i}
                    style={{ height: `${Math.round(b * 100)}%` }}
                    className="w-[4px] rounded-[2px] bg-gradient-to-t from-current to-transparent"
                />
            ))}
        </div>
    );
}

function KpiCard({ k, onNavigate }) {
    const meta = KPI_META[k.key] || { accent: "teal", icon: TrendingUp };
    const Icon = meta.icon;
    const delta = k.delta_pct;
    const clickable = Boolean(k.drill && onNavigate);
    const seed = String(k.key).length + Number(k.value || 0);
    return (
        <button
            onClick={clickable ? () => onNavigate(k.drill) : undefined}
            data-testid={`kpi-${k.key}`}
            title={k.definition}
            className={`sa-kpi accent-${meta.accent} ${clickable ? "cursor-pointer" : "cursor-default"}`}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="sa-kpi__label">
                    <span className="sa-kpi__label-icon"><Icon className="w-3.5 h-3.5" /></span>
                    <span className="truncate">{k.label}</span>
                </div>
                {delta !== undefined && delta !== null && (
                    <span className={`sa-kpi__delta ${delta >= 0 ? "up" : "down"}`}>
                        {delta >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        {Math.abs(delta)}%
                    </span>
                )}
            </div>
            <div className="sa-kpi__value">{fmtVal(k.value, k.format)}</div>
            <div className={`sa-sparkline ${meta.accent === "teal" ? "text-teal-500" : meta.accent === "blue" ? "text-blue-500" : meta.accent === "gold" ? "text-amber-500" : meta.accent === "rose" ? "text-rose-500" : meta.accent === "violet" ? "text-violet-500" : "text-slate-500"}`}>
                <MiniBars seed={seed} delta={delta || 0} />
            </div>
            {k.prev_value !== undefined && (
                <div className="sa-kpi__prev">prev {fmtVal(k.prev_value, k.format)}</div>
            )}
        </button>
    );
}

const QUICK_ACTIONS = [
    { key: "campaigns", label: "Email campaign", icon: Send,      tab: "campaigns" },
    { key: "emails",    label: "Send email",     icon: Send,      tab: "emails" },
    { key: "agentos",   label: "Dispatch pod",   icon: Zap,       tab: "agentos" },
    { key: "aiops",     label: "AI operations",  icon: Bot,       tab: "aiops" },
    { key: "leads",     label: "New leads",      icon: MessageCircle, tab: "leads" },
    { key: "audit",     label: "Audit log",      icon: Radar,     tab: "audit" },
];

/* --------------------------------------------------------------------------
 * Command Centre 2.0
 * ------------------------------------------------------------------------ */
export default function CommandCenter({ onNavigate }) {
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
    useEffect(() => { load(days); }, [days]);

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
        <div data-testid="command-center" className="space-y-6">
            {/* Hero header */}
            <div className="sa-glass-hero p-6 lg:p-7">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-brand">Command Centre</span>
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-brand/10 text-brand text-[10px] font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" /> LIVE
                            </span>
                        </div>
                        <h1 className="font-serif text-3xl lg:text-4xl leading-tight tracking-tight max-w-3xl">
                            Executive pulse across learners, revenue &amp; AI operations.
                        </h1>
                        <p className="text-sm text-muted-foreground mt-2">
                            {data ? (
                                <>Last refreshed <b>{new Date(data.generated_at).toLocaleTimeString()}</b> · comparing vs prior {days} days.</>
                            ) : "Loading real-time telemetry…"}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <select value={days} onChange={(e) => setDays(Number(e.target.value))} data-testid="cc-date-range"
                            className="bg-white/70 backdrop-blur border border-border rounded-full px-4 py-2 text-sm focus:outline-none focus:border-brand">
                            <option value={7}>Last 7 days</option>
                            <option value={30}>Last 30 days</option>
                            <option value={90}>Last 90 days</option>
                        </select>
                        <button onClick={() => load()} data-testid="cc-refresh" title="Refresh"
                            className="sa-icon-btn">
                            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                        </button>
                        <button onClick={exportCsv} data-testid="cc-export"
                            className="sa-quick-action">
                            <Download className="icon" /> CSV
                        </button>
                    </div>
                </div>

                {/* Quick actions */}
                <div className="sa-quick-actions mt-6" data-testid="cc-quick-actions">
                    {QUICK_ACTIONS.map((a) => {
                        const Icon = a.icon;
                        return (
                            <button
                                key={a.key}
                                onClick={() => onNavigate?.(a.tab)}
                                data-testid={`cc-quick-${a.key}`}
                                className="sa-quick-action"
                            >
                                <Icon className="icon" /> {a.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Two-column: KPI grid + right-side live activity */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div className="xl:col-span-2">
                    {!data ? (
                        <div className="sa-glass p-16 text-center">
                            <Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" />
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="cc-kpi-grid">
                            {data.kpis.map((k) => <KpiCard key={k.key} k={k} onNavigate={onNavigate} />)}
                        </div>
                    )}
                </div>
                <div className="xl:col-span-1">
                    <ActivityFeedPanel />
                </div>
            </div>
        </div>
    );
}
