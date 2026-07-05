import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Building2, Users, Award, TrendingUp, Copy, Plus, Loader2, ArrowRight, Trash2, Settings, Receipt, Sparkles, UserPlus, X } from "lucide-react";
import { toast } from "sonner";
import HeroBlobs from "@/components/HeroBlobs";

export default function EnterprisePortal() {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const [dashboard, setDashboard] = useState(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("member");
    const [inviteDept, setInviteDept] = useState("");
    const [inviting, setInviting] = useState(false);
    const [inviteError, setInviteError] = useState("");
    const [copied, setCopied] = useState(false);
    const [showSeatEditor, setShowSeatEditor] = useState(false);
    const [seatTarget, setSeatTarget] = useState(0);
    const [seatPreview, setSeatPreview] = useState(null);
    const [seatBusy, setSeatBusy] = useState(false);
    const [billing, setBilling] = useState([]);
    // Direct user-creation flow (admin creates user with temp password)
    const [showCreateUser, setShowCreateUser] = useState(false);
    const [newUserEmail, setNewUserEmail] = useState("");
    const [newUserName, setNewUserName] = useState("");
    const [newUserDept, setNewUserDept] = useState("");
    const [newUserRole, setNewUserRole] = useState("member");
    const [createUserErr, setCreateUserErr] = useState("");
    const [creatingUser, setCreatingUser] = useState(false);
    const [tempCreds, setTempCreds] = useState(null); // {email, temp_password}

    const load = () => {
        setLoading(true);
        api.get("/enterprise/organizations/dashboard")
            .then((r) => setDashboard(r.data))
            .catch((e) => {
                if (e.response?.status === 404) setNotFound(true);
                else setDashboard(null);
            })
            .finally(() => setLoading(false));
    };

    useEffect(() => { load(); }, []);

    // Load billing events once we know the org exists
    useEffect(() => {
        if (dashboard && dashboard.membership?.role === "owner") {
            api.get("/enterprise/organizations/billing")
                .then((r) => setBilling(r.data.events || []))
                .catch(() => {});
        }
    }, [dashboard]);

    // Handle post-checkout redirect to fulfill seat purchase
    useEffect(() => {
        const sid = searchParams.get("session_id");
        if (!sid) return;
        api.post(`/enterprise/organizations/seats/fulfill/${sid}`)
            .then((r) => {
                if (r.data.fulfilled) toast.success(`Seat purchase complete — you now have ${r.data.seat_count} seats.`);
                else toast.error("Seat purchase not yet confirmed. Try refreshing in a moment.");
                setSearchParams({}, { replace: true });
                load();
            })
            .catch(() => {
                toast.error("Could not verify checkout — refresh in a moment.");
                setSearchParams({}, { replace: true });
            });
    }, [searchParams]);

    // Live preview of seat change
    useEffect(() => {
        if (!showSeatEditor || !dashboard) return;
        const timeout = setTimeout(() => {
            api.post("/enterprise/organizations/seats/preview", { seat_count: seatTarget })
                .then((r) => setSeatPreview(r.data))
                .catch(() => setSeatPreview(null));
        }, 200);
        return () => clearTimeout(timeout);
    }, [seatTarget, showSeatEditor, dashboard]);

    const applySeatChange = async () => {
        setSeatBusy(true);
        try {
            const res = await api.post("/enterprise/organizations/seats", {
                seat_count: seatTarget,
                origin_url: window.location.origin,
            });
            if (res.data.action === "checkout" && res.data.checkout_url) {
                window.location.href = res.data.checkout_url;
                return;
            }
            if (res.data.action === "credit") {
                toast.success(res.data.message);
            } else {
                toast.info("No change applied.");
            }
            setShowSeatEditor(false);
            load();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Seat update failed");
        } finally { setSeatBusy(false); }
    };

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
            load();
        } catch (e) {
            setInviteError(e.response?.data?.detail || "Invite failed");
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
            load();
        } catch (e) {
            setCreateUserErr(e.response?.data?.detail || "Create failed");
        } finally {
            setCreatingUser(false);
        }
    };

    const removeMember = async (memberId) => {
        if (!window.confirm("Remove this team member?")) return;
        try {
            await api.delete(`/enterprise/organizations/members/${memberId}`);
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    const copyInviteCode = () => {
        navigator.clipboard.writeText(dashboard.organization.invite_code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;

    if (notFound) return (
        <div className="container-narrow py-20 text-center">
            <Building2 className="w-12 h-12 text-brand mx-auto mb-6" />
            <div className="overline mb-4">Enterprise Portal</div>
            <h1 className="font-serif text-5xl tracking-tighter leading-none mb-4">No organization yet.</h1>
            <p className="text-muted-foreground mb-8">Create your organization to invite team members and unlock team analytics.</p>
            <div className="flex gap-3 justify-center">
                <Link to="/enterprise/setup" data-testid="setup-org-cta" className="btn-primary">
                    Create organization <ArrowRight className="w-4 h-4" />
                </Link>
                <Link to="/enterprise/join" data-testid="join-org-cta" className="btn-outline">
                    Join with invite code
                </Link>
            </div>
        </div>
    );

    if (!dashboard) return <div className="container-page py-24 text-center text-muted-foreground">Could not load organization data.</div>;

    const { organization: org, summary, members, departments, top_courses, membership } = dashboard;
    const isAdmin = membership.role === "owner" || membership.role === "admin";
    const isOwner = membership.role === "owner";

    return (
        <div>
            {/* Hero with blobs */}
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="cool" />
                <div className="relative container-page pt-12 pb-8 z-10">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
                        <div className="md:col-span-8">
                            <span className="section-kicker">{org.industry || "Enterprise"} · {membership.role.toUpperCase()}</span>
                            <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none" data-testid="org-name">{org.name}</h1>
                            <p className="mt-4 text-muted-foreground max-w-xl">
                                {summary.seats_used} of {summary.seat_count} seats active · {summary.total_certificates} certifications earned by your team
                            </p>
                            <div className="mt-5 flex gap-3 flex-wrap">
                                <Link to="/patches" data-testid="portal-patches-link" className="btn-outline text-xs">
                                    <Sparkles className="w-3 h-3" /> Curriculum patches
                                </Link>
                                {isOwner && (
                                    <button
                                        onClick={() => { setShowSeatEditor(true); setSeatTarget(org.seat_count); }}
                                        data-testid="manage-seats"
                                        className="btn-outline text-xs"
                            >
                                <Settings className="w-3 h-3" /> Manage seats
                            </button>
                        )}
                    </div>
                </div>
                <div className="md:col-span-4">
                    <div className="card-flat p-5">
                        <div className="overline mb-2">Invite Code</div>
                        <div className="flex items-center gap-2">
                            <code className="font-mono text-lg text-brand flex-1" data-testid="invite-code">{org.invite_code}</code>
                            <button onClick={copyInviteCode} data-testid="copy-invite-code" className="p-2 hover:bg-surface-alt rounded-sm">
                                <Copy className="w-4 h-4" />
                            </button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">{copied ? "Copied!" : "Share with employees to onboard"}</p>
                    </div>
                </div>
            </div>
            </div>
            </section>

            <div className="container-page pb-12">

            {/* Seat editor modal */}
            {showSeatEditor && (
                <div className="fixed inset-0 z-50 bg-foreground/40 flex items-center justify-center p-4" onClick={() => setShowSeatEditor(false)}>
                    <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="seat-editor">
                        <div className="p-6 border-b border-border">
                            <div className="overline mb-2">Manage seats</div>
                            <h3 className="font-serif text-2xl">Adjust your team plan</h3>
                        </div>
                        <div className="p-6 space-y-5">
                            <div>
                                <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Seat count (min 10)</label>
                                <input
                                    type="number"
                                    min={10}
                                    max={5000}
                                    value={seatTarget}
                                    onChange={(e) => setSeatTarget(parseInt(e.target.value || 0))}
                                    data-testid="seat-target"
                                    className="mt-1 w-full bg-surface-alt border border-border rounded-sm px-4 py-2 text-lg focus:outline-none focus:border-brand"
                                />
                                <p className="text-xs text-muted-foreground mt-1">Currently: {org.seat_count} · In use: {summary.seats_used}</p>
                            </div>

                            {seatPreview && seatPreview.action !== "noop" && (
                                <div className={`border p-4 ${seatPreview.action === "checkout" ? "border-brand bg-brand/5" : "border-border bg-surface-alt"}`} data-testid="seat-preview">
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-1">
                                        {seatPreview.action === "checkout" ? "Charge summary" : "Credit note"}
                                    </div>
                                    <p className="text-sm">{seatPreview.message}</p>
                                </div>
                            )}

                            <div className="flex gap-3 justify-end pt-2">
                                <button onClick={() => setShowSeatEditor(false)} className="btn-outline">Cancel</button>
                                <button
                                    onClick={applySeatChange}
                                    disabled={seatBusy || seatTarget === org.seat_count}
                                    data-testid="apply-seat-change"
                                    className="btn-primary"
                                >
                                    {seatBusy ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                        seatPreview?.action === "checkout" ? "Proceed to checkout" :
                                        seatPreview?.action === "credit" ? "Apply reduction" : "Apply"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Readiness Index */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
                <StatCard label="Readiness Index" value={`${summary.readiness_index}`} unit="/ 100" icon={TrendingUp} accent testId="stat-readiness" />
                <StatCard label="Certifications" value={summary.total_certificates} icon={Award} testId="stat-certs" />
                <StatCard label="Avg Progress" value={`${summary.avg_progress}%`} icon={TrendingUp} testId="stat-progress" />
                <StatCard label="Cert Coverage" value={`${summary.cert_coverage_pct}%`} icon={Users} testId="stat-coverage" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
                {/* Members */}
                <div className="lg:col-span-8">
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

                    {/* Add-user modal */}
                    {isAdmin && showCreateUser && (
                        <div className="fixed inset-0 z-50 bg-foreground/40 flex items-center justify-center p-4" onClick={() => setShowCreateUser(false)}>
                            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="create-user-modal">
                                <div className="p-6 border-b border-border flex items-start justify-between">
                                    <div>
                                        <div className="overline mb-1">Add team member</div>
                                        <h3 className="font-serif text-2xl">Create user directly</h3>
                                        <p className="text-xs text-muted-foreground mt-1">A temp password will be shown once. Share it with the user via a secure channel.</p>
                                    </div>
                                    <button onClick={() => setShowCreateUser(false)} className="p-2 hover:bg-surface-alt rounded-sm"><X className="w-4 h-4" /></button>
                                </div>
                                <form onSubmit={createUserDirect} className="p-6 space-y-4">
                                    <div>
                                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Email <span className="text-destructive">*</span></label>
                                        <input type="email" required value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)}
                                            placeholder={org.domain ? `employee@${org.domain}` : "employee@company.com"}
                                            data-testid="new-user-email"
                                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                                        {org.domain && (
                                            <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand mt-1">Must be @{org.domain}</p>
                                        )}
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Full name <span className="text-destructive">*</span></label>
                                        <input type="text" required value={newUserName} onChange={(e) => setNewUserName(e.target.value)}
                                            data-testid="new-user-name"
                                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Department</label>
                                            <input type="text" value={newUserDept} onChange={(e) => setNewUserDept(e.target.value)}
                                                placeholder="HR / Finance / Sales…"
                                                data-testid="new-user-dept"
                                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                                        </div>
                                        <div>
                                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Role</label>
                                            <select value={newUserRole} onChange={(e) => setNewUserRole(e.target.value)}
                                                data-testid="new-user-role"
                                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand">
                                                <option value="member">Member</option>
                                                <option value="admin">Admin</option>
                                            </select>
                                        </div>
                                    </div>
                                    {createUserErr && <div className="text-sm text-destructive" data-testid="create-user-error">{createUserErr}</div>}
                                    <div className="flex gap-3 justify-end pt-2">
                                        <button type="button" onClick={() => setShowCreateUser(false)} className="btn-outline">Cancel</button>
                                        <button type="submit" disabled={creatingUser || summary.seats_remaining <= 0} data-testid="submit-create-user" className="btn-primary">
                                            {creatingUser ? <Loader2 className="w-4 h-4 animate-spin" /> : <><UserPlus className="w-4 h-4" /> Create user</>}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}

                    {/* Temp creds shown once after user creation */}
                    {tempCreds && (
                        <div className="fixed inset-0 z-50 bg-foreground/60 flex items-center justify-center p-4" onClick={() => setTempCreds(null)}>
                            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="temp-creds-modal">
                                <div className="p-6 border-b border-border flex items-start justify-between">
                                    <div>
                                        <div className="overline mb-1 text-brand">User created</div>
                                        <h3 className="font-serif text-2xl">{tempCreds.name}</h3>
                                        <p className="text-xs text-muted-foreground mt-1">Share this temp password over a secure channel — it will not be shown again.</p>
                                    </div>
                                    <button onClick={() => setTempCreds(null)} className="p-2 hover:bg-surface-alt rounded-sm"><X className="w-4 h-4" /></button>
                                </div>
                                <div className="p-6 space-y-4">
                                    <div className="bg-brand/5 border border-brand p-4 rounded-sm space-y-2">
                                        <div>
                                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Email</div>
                                            <div className="font-mono text-sm break-all" data-testid="temp-creds-email">{tempCreds.email}</div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Temp password</div>
                                            <div className="font-mono text-base break-all select-all" data-testid="temp-creds-password">{tempCreds.temp_password}</div>
                                        </div>
                                    </div>
                                    <div className="flex gap-3 justify-end">
                                        <button
                                            onClick={() => {
                                                navigator.clipboard.writeText(`Email: ${tempCreds.email}\nTemp password: ${tempCreds.temp_password}`);
                                                toast.success("Credentials copied");
                                            }}
                                            data-testid="copy-temp-creds"
                                            className="btn-outline"
                                        >
                                            <Copy className="w-4 h-4" /> Copy both
                                        </button>
                                        <button onClick={() => setTempCreds(null)} data-testid="close-temp-creds" className="btn-primary">Done</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Invite */}
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
                </div>

                {/* Sidebar — Departments + Top Courses */}
                <div className="lg:col-span-4 space-y-8">
                    <div>
                        <h2 className="font-serif text-xl tracking-tight mb-4">Departments</h2>
                        <div className="card-flat">
                            {departments.length === 0 ? (
                                <div className="p-6 text-sm text-muted-foreground">No departments yet — assign departments when inviting.</div>
                            ) : departments.map((d) => (
                                <div key={d.name} className="p-4 border-b border-border last:border-b-0" data-testid={`dept-${d.name}`}>
                                    <div className="flex justify-between items-baseline mb-2">
                                        <div className="font-serif text-base">{d.name}</div>
                                        <div className="text-xs text-muted-foreground">{d.members} people</div>
                                    </div>
                                    <div className="h-1 bg-border">
                                        <div className="h-full bg-brand" style={{ width: `${Math.min(100, d.avg_progress)}%` }} />
                                    </div>
                                    <div className="flex justify-between text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                                        <span>{d.avg_progress}% avg progress</span>
                                        <span>{d.certificates} certs</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div>
                        <h2 className="font-serif text-xl tracking-tight mb-4">Top courses</h2>
                        <div className="space-y-2">
                            {top_courses.length === 0 ? (
                                <div className="card-flat p-6 text-sm text-muted-foreground">No enrollments yet</div>
                            ) : top_courses.map((c) => (
                                <Link key={c.id} to={`/courses/${c.slug}`} className="card-flat p-4 flex gap-3 items-center hover:border-brand transition-colors" data-testid={`top-course-${c.slug}`}>
                                    <div className="w-14 h-14 shrink-0 overflow-hidden border border-border">
                                        <img src={c.thumbnail_url} alt="" className="w-full h-full object-cover" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{c.category}</div>
                                        <div className="font-serif text-sm leading-tight truncate">{c.title}</div>
                                    </div>
                                    <div className="text-xs font-mono text-brand">{c.enrolled_count}×</div>
                                </Link>
                            ))}
                        </div>
                    </div>

                    {isOwner && billing.length > 0 && (
                        <div>
                            <h2 className="font-serif text-xl tracking-tight mb-4 flex items-center gap-2">
                                <Receipt className="w-4 h-4 text-brand" /> Billing history
                            </h2>
                            <div className="card-flat divide-y divide-border" data-testid="billing-history">
                                {billing.slice(0, 5).map((b) => (
                                    <div key={b.id} className="p-4 text-xs" data-testid={`billing-event-${b.id}`}>
                                        <div className="flex items-baseline justify-between gap-2 mb-1">
                                            <span className="font-mono uppercase tracking-[0.15em] text-brand">
                                                {b.type === "prorated_credit" ? "Credit" : "Seats"}
                                            </span>
                                            <span className="text-muted-foreground">
                                                {new Date(b.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                            </span>
                                        </div>
                                        <div className="font-serif text-sm">
                                            {b.type === "prorated_credit"
                                                ? `-${b.seats_removed} seats · $${b.amount.toFixed(2)} credit`
                                                : `+${b.seats_added} seats · $${b.amount.toFixed(2)}`}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
        </div>
    );
}

function StatCard({ label, value, unit, icon: Icon, accent, testId }) {
    return (
        <div className={`card-flat p-5 ${accent ? "border-brand border-2" : ""}`} data-testid={testId}>
            <Icon className={`w-4 h-4 mb-2 ${accent ? "text-brand" : "text-muted-foreground"}`} />
            <div className="font-serif text-3xl leading-none">
                {value}<span className="text-sm text-muted-foreground">{unit}</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-2">{label}</div>
        </div>
    );
}
