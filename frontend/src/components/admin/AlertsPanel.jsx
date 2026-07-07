import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AlertTriangle, Info, Loader2 } from "lucide-react";

/**
 * Unified alerts feed for the Overview tab. Renders real signals from
 * /api/admin/alerts (suspended users, impersonations, deletions, traffic
 * drops, orphan enrollments) + stubbed placeholders for billing/storage
 * pending Tier-4 backing systems.
 */
export default function AlertsPanel() {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get("/admin/alerts")
            .then((r) => setAlerts(r.data.alerts || []))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="card-flat p-6 flex items-center gap-2 text-sm text-muted-foreground" data-testid="alerts-loading"><Loader2 className="w-4 h-4 animate-spin" /> Loading alerts…</div>;

    if (alerts.length === 0) {
        return (
            <div className="card-flat p-6 text-sm text-muted-foreground text-center" data-testid="alerts-empty">
                All quiet on the platform.
            </div>
        );
    }

    return (
        <div className="card-flat p-6" data-testid="alerts-panel">
            <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-brand" />
                <h3 className="font-serif text-lg">Alerts <span className="text-xs font-mono text-muted-foreground ml-2">{alerts.length}</span></h3>
            </div>
            <div className="divide-y divide-border">
                {alerts.map((a) => (
                    <div key={a.id} className={`py-3 flex items-start gap-3 ${a.stubbed ? "opacity-60" : ""}`} data-testid={`alert-${a.id}`}>
                        {a.severity === "warn"
                            ? <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
                            : <Info className="w-4 h-4 text-brand-sky shrink-0 mt-0.5" />}
                        <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium flex items-center gap-2">
                                {a.title}
                                {a.stubbed && <span className="badge-mono text-[9px] py-0">Stub</span>}
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">{a.description}</div>
                        </div>
                        {a.link && (
                            <a
                                href={a.link}
                                data-testid={`alert-${a.id}-link`}
                                className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand hover:underline shrink-0"
                            >
                                view →
                            </a>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
