import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AlertTriangle, BellRing, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";

const SEV = {
    high: "border-l-[#E2574C] text-[#E2574C]",
    medium: "border-l-[#C9A227] text-[#C9A227]",
    low: "border-l-[#2E7DFF] text-[#2E7DFF]",
};

export default function AlertCenter({ onNavigate }) {
    const [alerts, setAlerts] = useState(null);

    const load = () => api.get("/admin/alerts-center").then((r) => setAlerts(r.data.alerts)).catch(() => {});
    useEffect(() => { load(); }, []);

    const act = async (key, action) => {
        try {
            await api.post(`/admin/alerts-center/${key}/${action}`, action === "resolve" ? { note: "" } : undefined);
            toast.success(action === "ack" ? "Acknowledged" : "Resolved");
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Action failed");
        }
    };

    if (!alerts) return <div className="card-flat rounded-lg p-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>;

    return (
        <div data-testid="alert-center">
            <div className="flex items-center gap-2 mb-5">
                <BellRing className="w-4 h-4 sa-gold" />
                <h2 className="font-serif text-2xl tracking-tight">Alert &amp; Action Centre</h2>
                <span className="text-[11px] font-mono text-muted-foreground ml-2">{alerts.length} open signal{alerts.length === 1 ? "" : "s"}</span>
            </div>
            {alerts.length === 0 ? (
                <div className="card-flat rounded-lg p-12 text-center text-sm text-muted-foreground" data-testid="alerts-empty">
                    <Check className="w-6 h-6 mx-auto mb-3 sa-kpi-up" />
                    All clear — no active platform signals.
                </div>
            ) : (
                <div className="space-y-2">
                    {alerts.map((a) => (
                        <div key={a.key} data-testid={`alert-${a.key}`}
                            className={`card-flat rounded-lg border-l-4 p-4 flex flex-wrap items-center gap-3 ${SEV[a.severity] || SEV.low}`}>
                            <AlertTriangle className="w-4 h-4 shrink-0" />
                            <div className="flex-1 min-w-[220px]">
                                <div className="text-sm font-medium text-foreground flex items-center gap-2">
                                    {a.title}
                                    <span className="text-[9px] font-mono uppercase tracking-[0.15em] opacity-80">{a.severity}</span>
                                    {a.status === "acknowledged" && <span className="text-[9px] font-mono uppercase text-muted-foreground">· acked</span>}
                                </div>
                                <div className="text-xs text-muted-foreground mt-0.5">{a.detail}</div>
                            </div>
                            <div className="flex gap-2">
                                {a.drill && (
                                    <button onClick={() => onNavigate(a.drill)} data-testid={`alert-drill-${a.key}`} className="text-xs border border-border hover:border-primary rounded-md px-2.5 py-1.5 text-foreground">Investigate</button>
                                )}
                                {a.status !== "acknowledged" && (
                                    <button onClick={() => act(a.key, "ack")} data-testid={`alert-ack-${a.key}`} className="text-xs border border-border hover:border-primary rounded-md px-2.5 py-1.5 text-foreground">Acknowledge</button>
                                )}
                                <button onClick={() => act(a.key, "resolve")} data-testid={`alert-resolve-${a.key}`} className="text-xs bg-primary text-primary-foreground rounded-md px-2.5 py-1.5">Resolve</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
