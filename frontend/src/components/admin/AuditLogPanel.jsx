import { useEffect, useState } from "react";
import { api, API_BASE } from "@/lib/api";
import { Download, Loader2, ScrollText, RefreshCcw } from "lucide-react";

/**
 * Audit log tab — reads /api/admin/audit-log with optional action filter.
 * Also exposes a CSV export at /api/admin/audit-log/export.csv.
 *
 * The log covers every mutating super-admin action: suspend, reactivate,
 * role change, delete, impersonation, org create/delete, password resets.
 */
const ACTION_FILTERS = [
    { value: "", label: "All actions" },
    { value: "user.suspend", label: "User · Suspend" },
    { value: "user.reactivate", label: "User · Reactivate" },
    { value: "user.role_change", label: "User · Role change" },
    { value: "user.delete", label: "User · Delete" },
    { value: "user.impersonate", label: "User · Impersonate" },
];

export default function AuditLogPanel() {
    const [rows, setRows] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [action, setAction] = useState("");

    const load = async () => {
        setLoading(true);
        try {
            const res = await api.get(`/admin/audit-log${action ? `?action=${encodeURIComponent(action)}` : ""}`);
            setRows(res.data.rows || []);
            setTotal(res.data.total || 0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); /* eslint-disable-next-line */ }, [action]);

    return (
        <div data-testid="audit-log-panel">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
                <ScrollText className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl leading-none">Audit log <span className="text-xs font-mono text-muted-foreground ml-2">{total} entries</span></h2>
                <div className="ml-auto flex items-center gap-2">
                    <select
                        value={action}
                        onChange={(e) => setAction(e.target.value)}
                        data-testid="audit-action-filter"
                        className="bg-surface-alt border border-border rounded-sm text-xs px-2 py-1.5"
                    >
                        {ACTION_FILTERS.map((f) => (
                            <option key={f.value} value={f.value}>{f.label}</option>
                        ))}
                    </select>
                    <button
                        onClick={load}
                        data-testid="audit-refresh"
                        className="p-1.5 border border-border rounded-sm text-muted-foreground hover:text-brand"
                        title="Refresh"
                    >
                        <RefreshCcw className="w-3.5 h-3.5" />
                    </button>
                    <a
                        href={`${API_BASE}/admin/audit-log/export.csv${action ? `?action=${encodeURIComponent(action)}` : ""}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid="audit-export-csv"
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.15em] border border-border rounded-sm hover:border-brand hover:text-brand"
                    >
                        <Download className="w-3 h-3" /> Export CSV
                    </a>
                </div>
            </div>

            {loading ? (
                <div className="py-16 flex items-center justify-center text-muted-foreground">
                    <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading audit log…
                </div>
            ) : rows.length === 0 ? (
                <div className="card-flat p-10 text-center text-sm text-muted-foreground">No audit entries yet. Actions will appear here once you suspend, delete, or impersonate a user.</div>
            ) : (
                <div className="card-flat divide-y divide-border" data-testid="audit-log-rows">
                    <div className="grid grid-cols-12 gap-3 p-3 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                        <div className="col-span-2">When</div>
                        <div className="col-span-3">Actor</div>
                        <div className="col-span-2">Action</div>
                        <div className="col-span-3">Target</div>
                        <div className="col-span-2">IP</div>
                    </div>
                    {rows.map((r) => (
                        <div key={r.id} className="grid grid-cols-12 gap-3 p-3 items-start text-sm" data-testid={`audit-row-${r.id}`}>
                            <div className="col-span-2 text-xs text-muted-foreground font-mono">{r.created_at?.slice(0, 19).replace("T", " ")}</div>
                            <div className="col-span-3 text-xs">
                                <div className="truncate">{r.actor_email}</div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-[0.15em]">{r.actor_role}</div>
                            </div>
                            <div className="col-span-2 text-xs">
                                <span className={`badge-mono ${r.action.startsWith("user.delete") || r.action.startsWith("user.impersonate") ? "border-destructive text-destructive" : ""}`}>{r.action}</span>
                            </div>
                            <div className="col-span-3 text-xs truncate" title={r.target_label}>
                                {r.target_label || <span className="text-muted-foreground">—</span>}
                                {r.meta && Object.keys(r.meta).length > 0 && (
                                    <div className="text-[10px] text-muted-foreground truncate mt-0.5">
                                        {r.action === "user.role_change" && r.meta.from && (
                                            <>{r.meta.from} → {r.meta.to}{r.meta.reason ? ` · ${r.meta.reason}` : ""}</>
                                        )}
                                        {r.action === "user.impersonate" && r.meta.reason && (
                                            <>reason: {r.meta.reason}</>
                                        )}
                                    </div>
                                )}
                            </div>
                            <div className="col-span-2 text-xs text-muted-foreground font-mono truncate">{r.ip || "—"}</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
