import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Eraser, Loader2, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";

/** Detects test/dummy data in THIS environment's DB and purges it in one click. */
export default function DataHygienePanel() {
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [purging, setPurging] = useState(false);
    const [confirming, setConfirming] = useState(false);

    const load = useCallback(() => {
        setLoading(true);
        api.get("/admin/data-hygiene")
            .then((r) => setReport(r.data))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => { load(); }, [load]);

    const runPurge = async () => {
        setPurging(true);
        try {
            const res = await api.post("/admin/data-hygiene/purge");
            toast.success(`Purged ${res.data.deleted_users} test users + cascades. ${res.data.remaining_users} real users remain.`);
            setConfirming(false);
            load();
            setTimeout(() => window.location.reload(), 1200);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Purge failed");
        } finally {
            setPurging(false);
        }
    };

    if (loading) {
        return <div className="card-flat p-5 flex items-center gap-2 text-sm text-muted-foreground" data-testid="hygiene-loading"><Loader2 className="w-4 h-4 animate-spin" /> Scanning for test data…</div>;
    }
    if (!report) return null;

    const cascadeTotal = Object.values(report.cascade || {}).reduce((a, b) => a + b, 0);

    if (report.victims === 0) {
        return (
            <div className="card-flat p-5 flex items-center gap-3" data-testid="hygiene-clean">
                <ShieldCheck className="w-5 h-5 text-success shrink-0" />
                <div>
                    <div className="text-sm font-medium">Data hygiene: clean</div>
                    <div className="text-xs text-muted-foreground">No test/dummy accounts detected — every number on this dashboard is real.</div>
                </div>
            </div>
        );
    }

    return (
        <div className="card-flat p-5 border-warning/50" data-testid="hygiene-panel">
            <div className="flex items-start gap-3">
                <Eraser className="w-5 h-5 text-warning shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">
                        {report.victims} test account{report.victims !== 1 ? "s" : ""} detected
                        <span className="text-muted-foreground font-normal"> · {cascadeTotal} linked records ({report.orphaned_orgs} empty org{report.orphaned_orgs !== 1 ? "s" : ""})</span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 truncate">
                        e.g. {(report.victim_preview || []).slice(0, 3).join(", ")}
                    </div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-2">
                        {Object.entries(report.cascade || {}).filter(([, v]) => v > 0).map(([k, v]) => `${k}:${v}`).join("  ")}
                    </div>
                </div>
                {!confirming ? (
                    <button onClick={() => setConfirming(true)} data-testid="hygiene-purge-btn" className="btn-outline text-sm shrink-0">
                        <Trash2 className="w-4 h-4" /> Purge test data
                    </button>
                ) : (
                    <div className="flex items-center gap-2 shrink-0">
                        <button onClick={runPurge} disabled={purging} data-testid="hygiene-purge-confirm" className="btn-primary text-sm bg-destructive border-destructive">
                            {purging ? <Loader2 className="w-4 h-4 animate-spin" /> : "Yes, delete permanently"}
                        </button>
                        <button onClick={() => setConfirming(false)} data-testid="hygiene-purge-cancel" className="btn-outline text-sm">Cancel</button>
                    </div>
                )}
            </div>
        </div>
    );
}
