import { useState } from "react";
import { Loader2, UserPlus, X } from "lucide-react";

/**
 * Modal for admins to create a user directly with a temp password. Owns its
 * own form state; on submit, delegates to `onSubmit(payload)` which returns
 * a boolean. If the submit succeeds the modal closes itself.
 */
export default function CreateUserModal({
    org, onClose, onSubmit, err, loading, seatsRemaining,
}) {
    const [email, setEmail] = useState("");
    const [fullName, setFullName] = useState("");
    const [department, setDepartment] = useState("");
    const [role, setRole] = useState("member");

    const handleSubmit = async (e) => {
        e.preventDefault();
        const ok = await onSubmit({ email, full_name: fullName, department, role });
        if (ok) onClose();
    };

    return (
        <div className="fixed inset-0 z-50 bg-foreground/40 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="create-user-modal">
                <div className="p-6 border-b border-border flex items-start justify-between">
                    <div>
                        <div className="overline mb-1">Add team member</div>
                        <h3 className="font-serif text-2xl">Create user directly</h3>
                        <p className="text-xs text-muted-foreground mt-1">A temp password will be shown once. Share it with the user via a secure channel.</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-surface-alt rounded-sm"><X className="w-4 h-4" /></button>
                </div>
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">
                            Email <span className="text-destructive">*</span>
                        </label>
                        <input
                            type="email" required value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder={org.domain ? `employee@${org.domain}` : "employee@company.com"}
                            data-testid="new-user-email"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                        />
                        {org.domain && (
                            <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand mt-1">Must be @{org.domain}</p>
                        )}
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">
                            Full name <span className="text-destructive">*</span>
                        </label>
                        <input
                            type="text" required value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            data-testid="new-user-name"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Department</label>
                            <input
                                type="text" value={department}
                                onChange={(e) => setDepartment(e.target.value)}
                                placeholder="HR / Finance / Sales…"
                                data-testid="new-user-dept"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Role</label>
                            <select
                                value={role}
                                onChange={(e) => setRole(e.target.value)}
                                data-testid="new-user-role"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                            >
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                    </div>
                    {err && <div className="text-sm text-destructive" data-testid="create-user-error">{err}</div>}
                    <div className="flex gap-3 justify-end pt-2">
                        <button type="button" onClick={onClose} className="btn-outline">Cancel</button>
                        <button type="submit" disabled={loading || seatsRemaining <= 0} data-testid="submit-create-user" className="btn-primary">
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><UserPlus className="w-4 h-4" /> Create user</>}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
