import { useState } from "react";
import { Loader2, Plus, UserPlus } from "lucide-react";

/**
 * Invite-by-email form + "Create user directly" button. Presentational — all
 * side-effects live in `useMemberActions`.
 */
export default function InviteForm({
    seatsRemaining, onInvite, inviting, inviteError, onOpenCreateUser,
}) {
    const [email, setEmail] = useState("");
    const [role, setRole] = useState("member");
    const [department, setDepartment] = useState("");

    const handleSubmit = async (e) => {
        e.preventDefault();
        const ok = await onInvite({ email, role, department });
        if (ok) {
            setEmail("");
            setDepartment("");
        }
    };

    const noSeats = seatsRemaining <= 0;

    return (
        <div className="mt-8">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-serif text-xl">Add team members</h3>
                <button
                    type="button"
                    onClick={onOpenCreateUser}
                    data-testid="open-create-user"
                    className="btn-outline text-xs"
                    disabled={noSeats}
                >
                    <UserPlus className="w-3.5 h-3.5" /> Create user directly
                </button>
            </div>
            <form onSubmit={handleSubmit} className="card-flat p-6 space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <input
                        type="email" required
                        placeholder="employee@company.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        data-testid="invite-email"
                        className="bg-surface border border-border rounded-sm px-3 py-2 text-sm md:col-span-2 focus:outline-none focus:border-brand"
                    />
                    <select
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                        data-testid="invite-role"
                        className="bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand"
                    >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                <input
                    type="text"
                    placeholder="Department (optional) — HR, Finance, Sales…"
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    data-testid="invite-department"
                    className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand"
                />
                {inviteError && <div className="text-sm text-destructive">{inviteError}</div>}
                <button
                    type="submit"
                    disabled={inviting || noSeats}
                    data-testid="send-invite"
                    className="btn-primary"
                >
                    {inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Plus className="w-4 h-4" /> Send invite</>}
                </button>
                {noSeats && <div className="text-xs text-warning">No seats available — increase seat count in settings.</div>}
            </form>
        </div>
    );
}
