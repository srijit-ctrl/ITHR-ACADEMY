import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Activity, Ban, Loader2, MapPin, RefreshCcw } from "lucide-react";
import { toast } from "sonner";

/**
 * Sessions panel — shows the 50 most recent logins in the last 24h.
 * The "Force logout" button simply suspends the user (which invalidates
 * both fresh logins and refresh-token exchanges — no separate token store
 * needed). Suspended users can be reactivated from the Users tab.
 */
export default function SessionsPanel() {
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        setLoading(true);
        try {
            const r = await api.get("/admin/sessions/recent");
            setSessions(r.data.sessions || []);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const forceLogout = async (s) => {
        if (!window.confirm(`Suspend ${s.email}? They will be logged out immediately and unable to log in until reactivated.`)) return;
        try {
            await api.post(`/admin/users/${s.user_id}/suspend`);
            toast.success(`${s.email} suspended · session invalidated`);
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    return (
        <div data-testid="sessions-panel">
            <div className="flex items-center gap-3 mb-4">
                <Activity className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl leading-none">Active sessions <span className="text-xs font-mono text-muted-foreground ml-2">{sessions.length} in last 24h</span></h2>
                <button onClick={load} className="ml-auto p-1.5 border border-border rounded-sm text-muted-foreground hover:text-brand" data-testid="sessions-refresh"><RefreshCcw className="w-3.5 h-3.5" /></button>
            </div>

            {loading ? (
                <div className="py-16 flex items-center justify-center text-muted-foreground"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
            ) : sessions.length === 0 ? (
                <div className="card-flat p-10 text-center text-sm text-muted-foreground">No logins in the last 24 hours.</div>
            ) : (
                <div className="card-flat divide-y divide-border">
                    <div className="grid grid-cols-12 gap-3 p-3 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                        <div className="col-span-3">User</div>
                        <div className="col-span-3">Location</div>
                        <div className="col-span-2">Last login</div>
                        <div className="col-span-3">Client</div>
                        <div className="col-span-1 text-right">Actions</div>
                    </div>
                    {sessions.map((s) => (
                        <div key={s.user_id} className={`grid grid-cols-12 gap-3 p-3 items-center text-sm ${s.is_suspended ? "bg-destructive/5" : ""}`} data-testid={`session-row-${s.user_id}`}>
                            <div className="col-span-3">
                                <div className="text-sm font-medium truncate">{s.full_name || s.email}</div>
                                <div className="text-xs text-muted-foreground truncate">{s.email} · <span className="text-brand">{s.role}</span></div>
                            </div>
                            <div className="col-span-3 text-xs flex items-start gap-1">
                                <MapPin className="w-3 h-3 mt-0.5 shrink-0 text-muted-foreground" />
                                <div>
                                    <div>{s.city || "Unknown"}, {s.country || "—"}</div>
                                    <div className="text-[10px] font-mono text-muted-foreground">{s.ip}</div>
                                </div>
                            </div>
                            <div className="col-span-2 text-xs text-muted-foreground">
                                <div>{new Date(s.last_login_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</div>
                                <div className="text-[10px] font-mono">{s.count_24h}× today</div>
                            </div>
                            <div className="col-span-3 text-[11px] text-muted-foreground truncate" title={s.user_agent}>{s.user_agent}</div>
                            <div className="col-span-1 text-right">
                                {!s.is_suspended && (
                                    <button
                                        onClick={() => forceLogout(s)}
                                        data-testid={`session-force-logout-${s.user_id}`}
                                        className="p-1.5 text-muted-foreground hover:text-destructive"
                                        title="Force logout (suspend)"
                                    >
                                        <Ban className="w-3.5 h-3.5" />
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
