import { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { KeyRound, Ban, CheckCircle2, Trash2, UserCog, Eye, Loader2, LineChart } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

/**
 * One user row inside the SuperAdmin Users tab. Contains all Tier-1
 * control actions: reset-password / suspend-reactivate / role-change /
 * delete / impersonate. Modal confirmations for destructive ops.
 */
const ROLES = ["learner", "instructor", "admin", "super_admin"];

export default function UserControlRow({ u, onChanged, onOpen }) {
    const { user: self, beginImpersonation } = useAuth();
    const navigate = useNavigate();
    const [busy, setBusy] = useState(false);
    const [showRoleMenu, setShowRoleMenu] = useState(false);

    const isSelf = self?.id === u.id;
    const isSuperAdmin = u.role === "super_admin";
    const isSuspended = !!u.is_suspended;

    const call = async (fn, successMsg) => {
        setBusy(true);
        try {
            await fn();
            if (successMsg) toast.success(successMsg);
            onChanged?.();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Action failed");
        } finally {
            setBusy(false);
        }
    };

    const resetPw = () => {
        if (!window.confirm(`Reset password for ${u.email}? A temp password will be shown once.`)) return;
        call(async () => {
            const res = await api.post(`/admin/users/${u.id}/reset-password`);
            const pw = res.data.temp_password;
            window.prompt(`Temp password for ${u.email} (share securely, one-time view):`, pw);
        }, "Password reset");
    };

    const toggleSuspend = () => {
        if (isSuspended) {
            call(() => api.post(`/admin/users/${u.id}/reactivate`), `Reactivated ${u.email}`);
        } else {
            if (!window.confirm(`Suspend ${u.email}? They will be unable to log in until reactivated.`)) return;
            call(() => api.post(`/admin/users/${u.id}/suspend`), `Suspended ${u.email}`);
        }
    };

    const changeRole = (newRole) => {
        if (newRole === u.role) { setShowRoleMenu(false); return; }
        const warning = newRole === "super_admin"
            ? "Promote to SUPER ADMIN? They will have full platform control. Continue?"
            : `Change role of ${u.email} from ${u.role} to ${newRole}?`;
        if (!window.confirm(warning)) { setShowRoleMenu(false); return; }
        call(async () => {
            await api.post(`/admin/users/${u.id}/role`, { role: newRole });
            setShowRoleMenu(false);
        }, `Role changed to ${newRole}`);
    };

    const deleteUser = () => {
        if (!window.confirm(`⚠ DELETE ${u.email}? This cascade-removes enrollments, certificates, quiz attempts, and org memberships. This is IRREVERSIBLE.`)) return;
        if (window.prompt(`Type the user's email to confirm delete:`) !== u.email) {
            toast.error("Email did not match. Cancelled.");
            return;
        }
        call(() => api.delete(`/admin/users/${u.id}`), `Deleted ${u.email}`);
    };

    const impersonate = () => {
        const reason = window.prompt(`Impersonate ${u.email}? Enter a short reason for the audit log (e.g. "user reported broken lesson"):`, "");
        if (reason === null) return; // cancelled
        call(async () => {
            const res = await api.post(`/admin/users/${u.id}/impersonate`, { reason: reason || "not provided" });
            beginImpersonation({ token: res.data.token, user: res.data.user, actorEmail: self?.email });
            toast.success(`Now impersonating ${u.email}`);
            navigate("/dashboard");
        });
    };

    return (
        <div
            className={`grid grid-cols-12 gap-3 p-4 items-center text-sm ${isSuspended ? "bg-destructive/5" : ""}`}
            data-testid={`user-row-${u.id}`}
        >
            <div className="col-span-3">
                <button
                    type="button"
                    onClick={() => onOpen && onOpen(u.id)}
                    data-testid={`user-progress-${u.id}`}
                    className="text-left group"
                    title="View learning progress (360°)"
                >
                    <div className="font-serif text-base leading-tight flex items-center gap-2 group-hover:text-brand transition-colors">
                        {u.full_name || "(no name)"}
                        {isSelf && <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-brand">you</span>}
                        {isSuspended && <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-destructive">suspended</span>}
                    </div>
                    <div className="text-xs text-muted-foreground truncate group-hover:text-brand/70 transition-colors">{u.email} · view progress</div>
                </button>
            </div>
            <div className="col-span-2 text-xs relative">
                <button
                    onClick={() => !isSelf && setShowRoleMenu((s) => !s)}
                    disabled={busy || isSelf}
                    data-testid={`role-btn-${u.id}`}
                    className={`badge-mono ${isSuperAdmin ? "border-brand text-brand" : ""} ${isSelf ? "" : "hover:border-brand cursor-pointer"}`}
                >
                    {u.role || "learner"}
                </button>
                {showRoleMenu && !isSelf && (
                    <div className="absolute top-full mt-1 left-0 bg-background border border-border rounded-sm shadow-md z-10 min-w-[140px]" data-testid={`role-menu-${u.id}`}>
                        {ROLES.map((r) => (
                            <button
                                key={r}
                                onClick={() => changeRole(r)}
                                disabled={busy}
                                data-testid={`role-set-${u.id}-${r}`}
                                className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-surface-alt ${r === u.role ? "text-brand" : ""}`}
                            >
                                {r}
                            </button>
                        ))}
                    </div>
                )}
            </div>
            <div className="col-span-2 text-xs">{u.organization || <span className="text-muted-foreground">—</span>}</div>
            <div className="col-span-2 text-xs text-muted-foreground">
                {u.created_at ? new Date(u.created_at).toLocaleDateString("en-US", { year: "2-digit", month: "short", day: "numeric" }) : "—"}
            </div>
            <div className="col-span-3 text-right">
                {busy ? (
                    <Loader2 className="w-4 h-4 animate-spin inline-block text-muted-foreground" data-testid={`user-busy-${u.id}`} />
                ) : (
                    <div className="flex items-center justify-end gap-1">
                        <IconBtn onClick={() => onOpen && onOpen(u.id)} title="View progress (360°)" testid={`view-360-${u.id}`}><LineChart className="w-3.5 h-3.5" /></IconBtn>
                        <IconBtn onClick={resetPw} disabled={isSelf} title="Reset password" testid={`reset-pw-${u.id}`}><KeyRound className="w-3.5 h-3.5" /></IconBtn>
                        <IconBtn onClick={toggleSuspend} disabled={isSelf} title={isSuspended ? "Reactivate" : "Suspend"} testid={`suspend-btn-${u.id}`}>
                            {isSuspended ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> : <Ban className="w-3.5 h-3.5" />}
                        </IconBtn>
                        <IconBtn onClick={impersonate} disabled={isSelf || isSuperAdmin || isSuspended} title="Impersonate" testid={`impersonate-btn-${u.id}`}>
                            <Eye className="w-3.5 h-3.5" />
                        </IconBtn>
                        <IconBtn onClick={deleteUser} disabled={isSelf} title="Delete user" testid={`delete-btn-${u.id}`}>
                            <Trash2 className="w-3.5 h-3.5 text-destructive" />
                        </IconBtn>
                    </div>
                )}
            </div>
        </div>
    );
}

function IconBtn({ children, onClick, disabled, title, testid }) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            data-testid={testid}
            title={title}
            className="p-1.5 text-muted-foreground hover:text-brand disabled:opacity-30 disabled:pointer-events-none"
        >
            {children}
        </button>
    );
}
