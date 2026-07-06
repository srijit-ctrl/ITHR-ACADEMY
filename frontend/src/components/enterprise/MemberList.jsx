import { useState } from "react";
import { api } from "@/lib/api";
import { Copy, Loader2, Plus, Trash2, UserPlus, X } from "lucide-react";
import { toast } from "sonner";

/**
 * Members table + admin flows (invite by email, create user directly, remove member).
 * State is kept locally where possible; parent controls only the reload trigger.
 */
export default function MemberList({ dashboard, isAdmin, onReload }) {
    const { organization: org, summary, members } = dashboard;

    // Invite by email
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("member");
    const [inviteDept, setInviteDept] = useState("");
    const [inviting, setInviting] = useState(false);
    const [inviteError, setInviteError] = useState("");

    // Direct user-creation (admin creates user with temp password)
    const [showCreateUser, setShowCreateUser] = useState(false);
    const [newUserEmail, setNewUserEmail] = useState("");
    const [newUserName, setNewUserName] = useState("");
    const [newUserDept, setNewUserDept] = useState("");
    const [newUserRole, setNewUserRole] = useState("member");
    const [createUserErr, setCreateUserErr] = useState("");
    const [creatingUser, setCreatingUser] = useState(false);
    const [tempCreds, setTempCreds] = useState(null);

    const invite = async (e) => {
        e.preventDefault();
        setInviteError("");
        setInviting(true);
        try {
            await api.post("/enterprise/organizations/invites", {
                email: inviteEmail, role: inviteRole, department: inviteDept || null,
            });
            setInviteEmail("");
            setInviteDept("");
            onReload();
        } catch (e2) {
            setInviteError(e2.response?.data?.detail || "Invite failed");
        } finally {
            setInviting(false);
        }
    };

    const createUserDirect = async (e) => {
        e.preventDefault();
        setCreateUserErr("");
        setCreatingUser(true);
        try {
            const res = await api.post("/enterprise/organizations/users", {
                email: newUserEmail,
                full_name: newUserName,
                department: newUserDept || null,
                role: newUserRole,
            });
            setTempCreds({
                email: res.data.user.email,
                temp_password: res.data.temp_password,
                name: res.data.user.full_name,
            });
            setNewUserEmail("");
            setNewUserName("");
            setNewUserDept("");
            setShowCreateUser(false);
            onReload();
        } catch (e2) {
            setCreateUserErr(e2.response?.data?.detail || "Create failed");
        } finally {
            setCreatingUser(false);
        }
    };

    const removeMember = async (memberId) => {
        if (!window.confirm("Remove this team member?")) return;
        try {
            await api.delete(`/enterprise/organizations/members/${memberId}`);
            onReload();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    return (
        <>
            <div className="flex items-center justify-between mb-4">
                <h2 className="font-serif text-2xl tracking-tight">Team members</h2>
                <span className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">{summary.seats_used}/{summary.seat_count} seats</span>
            </div>

            <div className="card-flat divide-y divide-border">
                {members.map((m) => (
                    <div key={m.id} className="grid grid-cols-12 gap-4 p-4 items-center" data-testid={`member-row-${m.user_id}`}>
                        <div className="col-span-5">
                            <div className="font-serif text-base leading-tight">{m.full_name}</div>
                            <div className="text-xs text-muted-foreground">{m.email}</div>
                            {m.department && <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">{m.department}</div>}
                        </div>
                        <div className="col-span-2 text-xs">
                            <span className={`badge-mono ${m.role === "owner" ? "border-brand text-brand" : ""}`}>{m.role}</span>
                        </div>
                        <div className="col-span-4 text-xs text-muted-foreground grid grid-cols-3 gap-2">
                            <div><b className="text-foreground">{m.stats.enrollments}</b><br/>courses</div>
                            <div><b className="text-foreground">{m.stats.certificates}</b><br/>certs</div>
                            <div><b className="text-foreground">{m.stats.avg_progress}%</b><br/>avg</div>
                        </div>
                        <div className="col-span-1 text-right">
                            {isAdmin && m.role !== "owner" && (
                                <button onClick={() => removeMember(m.id)} data-testid={`remove-member-${m.user_id}`} className="p-1.5 text-muted-foreground hover:text-destructive">
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {isAdmin && showCreateUser && (
                <CreateUserModal
                    org={org}
                    onClose={() => setShowCreateUser(false)}
                    onSubmit={createUserDirect}
                    values={{ email: newUserEmail, name: newUserName, dept: newUserDept, role: newUserRole }}
                    setters={{ setEmail: setNewUserEmail, setName: setNewUserName, setDept: setNewUserDept, setRole: setNewUserRole }}
                    err={createUserErr}
                    loading={creatingUser}
                    seatsRemaining={summary.seats_remaining}
                />
            )}

            {tempCreds && (
                <TempCredsModal creds={tempCreds} onClose={() => setTempCreds(null)} />
            )}

            {isAdmin && (
                <div className="mt-8">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-serif text-xl">Add team members</h3>
                        <button
                            type="button"
                            onClick={() => setShowCreateUser(true)}
                            data-testid="open-create-user"
                            className="btn-outline text-xs"
                            disabled={summary.seats_remaining <= 0}
                        >
                            <UserPlus className="w-3.5 h-3.5" /> Create user directly
                        </button>
                    </div>
                    <form onSubmit={invite} className="card-flat p-6 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <input type="email" required placeholder="employee@company.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} data-testid="invite-email" className="bg-surface border border-border rounded-sm px-3 py-2 text-sm md:col-span-2 focus:outline-none focus:border-brand" />
                            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} data-testid="invite-role" className="bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand">
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                        <input type="text" placeholder="Department (optional) — HR, Finance, Sales…" value={inviteDept} onChange={(e) => setInviteDept(e.target.value)} data-testid="invite-department" className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                        {inviteError && <div className="text-sm text-destructive">{inviteError}</div>}
                        <button type="submit" disabled={inviting || summary.seats_remaining <= 0} data-testid="send-invite" className="btn-primary">
                            {inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Plus className="w-4 h-4" /> Send invite</>}
                        </button>
                        {summary.seats_remaining <= 0 && <div className="text-xs text-warning">No seats available — increase seat count in settings.</div>}
                    </form>
                </div>
            )}
        </>
    );
}


function CreateUserModal({ org, onClose, onSubmit, values, setters, err, loading, seatsRemaining }) {
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
                <form onSubmit={onSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Email <span className="text-destructive">*</span></label>
                        <input type="email" required value={values.email} onChange={(e) => setters.setEmail(e.target.value)}
                            placeholder={org.domain ? `employee@${org.domain}` : "employee@company.com"}
                            data-testid="new-user-email"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                        {org.domain && (
                            <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand mt-1">Must be @{org.domain}</p>
                        )}
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Full name <span className="text-destructive">*</span></label>
                        <input type="text" required value={values.name} onChange={(e) => setters.setName(e.target.value)}
                            data-testid="new-user-name"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Department</label>
                            <input type="text" value={values.dept} onChange={(e) => setters.setDept(e.target.value)}
                                placeholder="HR / Finance / Sales…"
                                data-testid="new-user-dept"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                        </div>
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Role</label>
                            <select value={values.role} onChange={(e) => setters.setRole(e.target.value)}
                                data-testid="new-user-role"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand">
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


function TempCredsModal({ creds, onClose }) {
    const copyBoth = () => {
        navigator.clipboard.writeText(`Email: ${creds.email}\nTemp password: ${creds.temp_password}`);
        toast.success("Credentials copied");
    };
    return (
        <div className="fixed inset-0 z-50 bg-foreground/60 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="temp-creds-modal">
                <div className="p-6 border-b border-border flex items-start justify-between">
                    <div>
                        <div className="overline mb-1 text-brand">User created</div>
                        <h3 className="font-serif text-2xl">{creds.name}</h3>
                        <p className="text-xs text-muted-foreground mt-1">Share this temp password over a secure channel — it will not be shown again.</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-surface-alt rounded-sm"><X className="w-4 h-4" /></button>
                </div>
                <div className="p-6 space-y-4">
                    <div className="bg-brand/5 border border-brand p-4 rounded-sm space-y-2">
                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Email</div>
                            <div className="font-mono text-sm break-all" data-testid="temp-creds-email">{creds.email}</div>
                        </div>
                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Temp password</div>
                            <div className="font-mono text-base break-all select-all" data-testid="temp-creds-password">{creds.temp_password}</div>
                        </div>
                    </div>
                    <div className="flex gap-3 justify-end">
                        <button onClick={copyBoth} data-testid="copy-temp-creds" className="btn-outline">
                            <Copy className="w-4 h-4" /> Copy both
                        </button>
                        <button onClick={onClose} data-testid="close-temp-creds" className="btn-primary">Done</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
