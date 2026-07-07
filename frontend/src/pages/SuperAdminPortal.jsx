import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Shield, Building2, Users, Plus, Copy, Trash2, KeyRound, Loader2, X, BarChart3, Mail, Send, ScrollText } from "lucide-react";
import { toast } from "sonner";
import { PlatformAnalyticsPanel } from "@/components/AnalyticsPanels";
import ActivityFeedPanel from "@/components/admin/ActivityFeedPanel";
import KpiDashboard from "@/components/admin/KpiDashboard";
import UserControlRow from "@/components/admin/UserControlRow";
import AuditLogPanel from "@/components/admin/AuditLogPanel";
import TrafficPanel from "@/components/admin/TrafficPanel";
import AlertsPanel from "@/components/admin/AlertsPanel";
import SessionsPanel from "@/components/admin/SessionsPanel";
import GlobalSearchBar from "@/components/admin/GlobalSearchBar";
import VideoQuizPanel from "@/components/admin/VideoQuizPanel";

/**
 * Super-Admin console.
 *
 * Deliberately unlinked from the public site chrome — the URL /admin is
 * only shared with ITHR internal operators. All requests are gated by the
 * backend `get_current_super_admin` guard, so a stray visit without the
 * correct role returns 403.
 */
export default function SuperAdminPortal() {
    const { user, loading } = useAuth();
    const [orgs, setOrgs] = useState([]);
    const [users, setUsers] = useState([]);
    const [totalUsers, setTotalUsers] = useState(0);
    const [busy, setBusy] = useState(false);
    const [showCreate, setShowCreate] = useState(false);
    const [tempCreds, setTempCreds] = useState(null); // {email, temp_password, org_name}
    const [tab, setTab] = useState("analytics");

    const loadAll = useCallback(async () => {
        setBusy(true);
        try {
            const [o, u] = await Promise.all([
                api.get("/admin/orgs"),
                api.get("/admin/users?limit=100"),
            ]);
            setOrgs(o.data.organizations || []);
            setUsers(u.data.users || []);
            setTotalUsers(u.data.total || 0);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load admin data");
        } finally {
            setBusy(false);
        }
    }, []);

    useEffect(() => {
        if (user?.role === "super_admin") loadAll();
    }, [user, loadAll]);

    if (loading) return <FullScreenLoader />;
    if (!user) return <Navigate to="/login" replace />;
    if (user.role !== "super_admin") return <Navigate to="/dashboard" replace />;

    const handleDeleteOrg = async (orgId, orgName) => {
        if (!window.confirm(`Delete "${orgName}"? Members become detached from the org (users are kept).`)) return;
        try {
            await api.delete(`/admin/orgs/${orgId}`);
            toast.success(`Deleted ${orgName}`);
            loadAll();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Delete failed");
        }
    };

    const handleResetPassword = async (userId, userEmail) => {
        if (!window.confirm(`Force-reset password for ${userEmail}?`)) return;
        try {
            const res = await api.post(`/admin/users/${userId}/reset-password`);
            setTempCreds({
                email: res.data.email,
                temp_password: res.data.temp_password,
                headline: "Password reset",
                subhead: "Share this temp password with the user via a secure channel.",
            });
        } catch (e) {
            toast.error(e.response?.data?.detail || "Reset failed");
        }
    };

    return (
        <div className="min-h-screen">
            {/* Very intentionally minimal chrome — this is an operator surface. */}
            <div className="container-page py-10">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.25em] text-brand-teal">
                            <Shield className="w-3.5 h-3.5" /> Internal · Super Admin
                        </div>
                        <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none mt-2">
                            ITHR Operator Console
                        </h1>
                        <p className="text-muted-foreground mt-2 text-sm">
                            Provision enterprise orgs, manage their first admin user, and act on password / access requests.
                        </p>
                    </div>
                    <div className="text-right text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">
                        <div>Signed in as</div>
                        <div className="text-foreground mt-1">{user.email}</div>
                    </div>
                </div>

                {/* Stat row */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
                    <StatCard label="Enterprise orgs" value={orgs.length} icon={Building2} testId="stat-orgs" />
                    <StatCard label="Total users" value={totalUsers} icon={Users} testId="stat-users" />
                    <StatCard label="Total seats issued" value={orgs.reduce((s, o) => s + (o.seat_count || 0), 0)} icon={Users} testId="stat-seats" />
                </div>

                {/* Tabs */}
                <div className="border-b border-border mb-6 flex gap-1 items-end flex-wrap">
                    <TabButton active={tab === "analytics"} onClick={() => setTab("analytics")} label="Overview" count={""} testId="tab-analytics" />
                    <TabButton active={tab === "traffic"} onClick={() => setTab("traffic")} label="Traffic" count={""} testId="tab-traffic" />
                    <TabButton active={tab === "orgs"} onClick={() => setTab("orgs")} label="Organizations" count={orgs.length} testId="tab-orgs" />
                    <TabButton active={tab === "users"} onClick={() => setTab("users")} label="Users" count={totalUsers} testId="tab-users" />
                    <TabButton active={tab === "sessions"} onClick={() => setTab("sessions")} label="Sessions" count={""} testId="tab-sessions" />
                    <TabButton active={tab === "emails"} onClick={() => setTab("emails")} label="Send email" count={""} testId="tab-emails" />
                    <TabButton active={tab === "audit"} onClick={() => setTab("audit")} label="Audit log" count={""} testId="tab-audit" />
                    <TabButton active={tab === "videoquiz"} onClick={() => setTab("videoquiz")} label="Video quizzes" count={""} testId="tab-videoquiz" />
                    <div className="ml-auto pb-2">
                        <GlobalSearchBar onNavigateUser={() => setTab("users")} />
                    </div>
                </div>

                {tab === "analytics" && (
                    <div className="space-y-6">
                        <AlertsPanel />
                        <KpiDashboard />
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div className="lg:col-span-2">
                                <PlatformAnalyticsPanel />
                            </div>
                            <div className="lg:col-span-1">
                                <ActivityFeedPanel />
                            </div>
                        </div>
                    </div>
                )}

                {tab === "traffic" && <TrafficPanel />}
                {tab === "sessions" && <SessionsPanel />}
                {tab === "videoquiz" && <VideoQuizPanel />}

                {tab === "orgs" && (
                    <div>
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="font-serif text-2xl">Enterprise organizations</h2>
                            <button
                                onClick={() => setShowCreate(true)}
                                data-testid="create-org-btn"
                                className="btn-primary text-sm"
                            >
                                <Plus className="w-4 h-4" /> New enterprise org
                            </button>
                        </div>
                        <OrgTable orgs={orgs} onDelete={handleDeleteOrg} busy={busy} />
                    </div>
                )}

                {tab === "users" && (
                    <UserTable users={users} totalUsers={totalUsers} onChanged={loadAll} />
                )}

                {tab === "emails" && <EmailDispatchPanel />}

                {tab === "audit" && <AuditLogPanel />}
            </div>

            {showCreate && (
                <CreateOrgModal
                    onClose={() => setShowCreate(false)}
                    onCreated={(res) => {
                        setTempCreds({
                            email: res.admin.email,
                            temp_password: res.admin.temp_password,
                            headline: `Org "${res.organization.name}" created`,
                            subhead: `Domain is @${res.organization.domain}. Share the temp password with the admin via a secure channel.`,
                        });
                        setShowCreate(false);
                        loadAll();
                    }}
                />
            )}

            {tempCreds && <TempCredsModal creds={tempCreds} onClose={() => setTempCreds(null)} />}
        </div>
    );
}

function StatCard({ label, value, icon: Icon, testId }) {
    return (
        <div className="card-flat p-5" data-testid={testId}>
            <Icon className="w-4 h-4 mb-2 text-muted-foreground" />
            <div className="font-serif text-3xl leading-none">{value}</div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-2">{label}</div>
        </div>
    );
}

function TabButton({ active, onClick, label, count, testId }) {
    return (
        <button
            onClick={onClick}
            data-testid={testId}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                active ? "border-brand text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
        >
            {label} <span className="ml-1 text-[10px] font-mono text-muted-foreground">{count}</span>
        </button>
    );
}

function OrgTable({ orgs, onDelete, busy }) {
    if (busy) return <div className="card-flat p-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>;
    if (orgs.length === 0) return <div className="card-flat p-8 text-center text-sm text-muted-foreground">No enterprise organizations yet. Click &quot;New enterprise org&quot; to provision one.</div>;
    return (
        <div className="card-flat divide-y divide-border" data-testid="orgs-table">
            <div className="grid grid-cols-12 gap-3 p-4 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                <div className="col-span-4">Name</div>
                <div className="col-span-2">Domain</div>
                <div className="col-span-2">Industry</div>
                <div className="col-span-2">Seats</div>
                <div className="col-span-1">Invite</div>
                <div className="col-span-1 text-right">Actions</div>
            </div>
            {orgs.map((o) => (
                <div key={o.id} className="grid grid-cols-12 gap-3 p-4 items-center text-sm" data-testid={`org-row-${o.slug}`}>
                    <div className="col-span-4">
                        <div className="font-serif text-base leading-tight">{o.name}</div>
                        <div className="text-xs text-muted-foreground">{o.slug}</div>
                    </div>
                    <div className="col-span-2 font-mono text-xs">@{o.domain || "—"}</div>
                    <div className="col-span-2 text-xs">{o.industry || "—"}</div>
                    <div className="col-span-2 text-xs"><b>{o.seats_used}</b> / {o.seat_count}</div>
                    <div className="col-span-1 font-mono text-xs text-brand">{o.invite_code}</div>
                    <div className="col-span-1 text-right">
                        <button
                            onClick={() => onDelete(o.id, o.name)}
                            data-testid={`delete-org-${o.slug}`}
                            className="p-1.5 text-muted-foreground hover:text-destructive"
                            title="Delete organization"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

function UserTable({ users, totalUsers, onChanged }) {
    return (
        <div>
            <h2 className="font-serif text-2xl mb-4">All users <span className="text-xs font-mono text-muted-foreground">({users.length} of {totalUsers} shown)</span></h2>
            <div className="card-flat divide-y divide-border" data-testid="users-table">
                <div className="grid grid-cols-12 gap-3 p-4 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                    <div className="col-span-3">Name / Email</div>
                    <div className="col-span-2">Role</div>
                    <div className="col-span-2">Organization</div>
                    <div className="col-span-2">Joined</div>
                    <div className="col-span-3 text-right">Actions</div>
                </div>
                {users.map((u) => (
                    <UserControlRow key={u.id} u={u} onChanged={onChanged} />
                ))}
            </div>
        </div>
    );
}

function CreateOrgModal({ onClose, onCreated }) {
    const [name, setName] = useState("");
    const [adminEmail, setAdminEmail] = useState("");
    const [adminName, setAdminName] = useState("");
    const [industry, setIndustry] = useState("");
    const [seatCount, setSeatCount] = useState(25);
    const [submitting, setSubmitting] = useState(false);
    const [err, setErr] = useState("");

    const domainPreview = useMemo(() => {
        const at = adminEmail.indexOf("@");
        return at >= 0 ? adminEmail.slice(at + 1).toLowerCase() : "";
    }, [adminEmail]);

    const submit = async (e) => {
        e.preventDefault();
        setErr("");
        setSubmitting(true);
        try {
            const res = await api.post("/admin/orgs", {
                name, admin_email: adminEmail, admin_full_name: adminName,
                industry: industry || null, seat_count: parseInt(seatCount, 10) || 25,
            });
            onCreated(res.data);
        } catch (e) {
            setErr(e.response?.data?.detail || "Provisioning failed");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-foreground/40 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-xl w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="create-org-modal">
                <div className="flex items-center justify-between p-6 border-b border-border">
                    <div>
                        <div className="overline mb-1">New enterprise</div>
                        <h3 className="font-serif text-2xl">Provision org + admin</h3>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-surface-alt rounded-sm"><X className="w-4 h-4" /></button>
                </div>
                <form onSubmit={submit} className="p-6 space-y-4">
                    <Field label="Company name" required>
                        <input type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Corp" data-testid="org-name-input"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                    </Field>
                    <Field label="Admin email (defines org domain)" required>
                        <input type="email" required value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} placeholder="cto@acme.com" data-testid="admin-email-input"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                        {domainPreview && (
                            <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand mt-1">
                                All future users must have @{domainPreview} emails.
                            </p>
                        )}
                    </Field>
                    <Field label="Admin full name" required>
                        <input type="text" required value={adminName} onChange={(e) => setAdminName(e.target.value)} placeholder="Priya Iyer" data-testid="admin-name-input"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                    </Field>
                    <div className="grid grid-cols-2 gap-4">
                        <Field label="Industry">
                            <input type="text" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Technology" data-testid="industry-input"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                        </Field>
                        <Field label="Initial seat count">
                            <input type="number" min="10" max="5000" value={seatCount} onChange={(e) => setSeatCount(e.target.value)} data-testid="seat-count-input"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand" />
                        </Field>
                    </div>
                    {err && <div className="text-sm text-destructive">{err}</div>}
                    <div className="flex gap-3 justify-end pt-2">
                        <button type="button" onClick={onClose} className="btn-outline">Cancel</button>
                        <button type="submit" disabled={submitting} data-testid="submit-create-org" className="btn-primary">
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Plus className="w-4 h-4" /> Provision</>}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function Field({ label, required, children }) {
    return (
        <div>
            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">
                {label}{required && <span className="text-destructive"> *</span>}
            </label>
            {children}
        </div>
    );
}

/**
 * One-time credentials modal — shown right after provisioning or a password reset.
 * The temp password is displayed once and never persisted client-side beyond the
 * lifetime of this modal.
 */
function TempCredsModal({ creds, onClose }) {
    const [copied, setCopied] = useState(false);
    const copy = () => {
        navigator.clipboard.writeText(`Email: ${creds.email}\nTemp password: ${creds.temp_password}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <div className="fixed inset-0 z-50 bg-foreground/60 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="temp-creds-modal">
                <div className="flex items-start justify-between p-6 border-b border-border">
                    <div>
                        <div className="overline mb-1 text-brand">{creds.headline}</div>
                        <p className="text-sm text-muted-foreground max-w-sm">{creds.subhead}</p>
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
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Temp password (shown once)</div>
                            <div className="font-mono text-base break-all select-all" data-testid="temp-creds-password">{creds.temp_password}</div>
                        </div>
                    </div>
                    <div className="flex gap-3 justify-end">
                        <button onClick={copy} data-testid="copy-temp-creds" className="btn-outline">
                            <Copy className="w-4 h-4" /> {copied ? "Copied" : "Copy both"}
                        </button>
                        <button onClick={onClose} data-testid="close-temp-creds" className="btn-primary">Done</button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function FullScreenLoader() {
    return (
        <div className="min-h-screen flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-brand" />
        </div>
    );
}


/**
 * Admin-driven transactional emails (complaint response + validity expiration).
 * Welcome/cert/invite/payment/verify-alert emails fire automatically —
 * these are the two that need a human in the loop.
 */
function EmailDispatchPanel() {
    const [kind, setKind] = useState("complaint");
    const [email, setEmail] = useState("");
    const [fullName, setFullName] = useState("");
    // Complaint fields
    const [ticketRef, setTicketRef] = useState("");
    const [responseText, setResponseText] = useState("");
    const [agentName, setAgentName] = useState("The ITHR Support Team");
    // Expiration fields
    const [credential, setCredential] = useState("");
    const [expiresOn, setExpiresOn] = useState("");
    const [renewalUrl, setRenewalUrl] = useState("");

    const [sending, setSending] = useState(false);

    const canSend = email.includes("@") && (
        kind === "complaint" ? (ticketRef && responseText) : (credential && expiresOn)
    );

    const send = async () => {
        setSending(true);
        try {
            if (kind === "complaint") {
                await api.post("/admin/emails/complaint-response", {
                    email, full_name: fullName, ticket_ref: ticketRef,
                    response_text: responseText, agent_name: agentName,
                });
            } else {
                await api.post("/admin/emails/validity-expiration", {
                    email, full_name: fullName, credential_or_plan: credential,
                    expires_on: expiresOn, renewal_url: renewalUrl || undefined,
                });
            }
            toast.success(`Email sent to ${email}`);
            setTicketRef(""); setResponseText(""); setCredential(""); setExpiresOn(""); setRenewalUrl("");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Send failed");
        } finally { setSending(false); }
    };

    return (
        <div data-testid="email-dispatch-panel">
            <div className="mb-6 flex items-center gap-3">
                <Mail className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl">Manual email dispatch</h2>
            </div>
            <p className="text-sm text-muted-foreground mb-6 max-w-2xl">
                Automated lifecycle emails (welcome, cert-earned, payment, credential-verified) fire without action.
                These two are human-driven — send them to a specific user when a support ticket needs a written response,
                or when a credential/subscription is about to expire.
            </p>

            <div className="flex gap-1 mb-6 border-b border-border">
                <button
                    onClick={() => setKind("complaint")}
                    data-testid="email-kind-complaint"
                    className={`px-4 py-2 text-sm border-b-2 -mb-px ${kind === "complaint" ? "border-brand text-foreground" : "border-transparent text-muted-foreground"}`}
                >
                    Complaint / Support response
                </button>
                <button
                    onClick={() => setKind("expiration")}
                    data-testid="email-kind-expiration"
                    className={`px-4 py-2 text-sm border-b-2 -mb-px ${kind === "expiration" ? "border-brand text-foreground" : "border-transparent text-muted-foreground"}`}
                >
                    Validity expiration
                </button>
            </div>

            <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div>
                    <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Recipient email</label>
                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                        data-testid="email-recipient"
                        className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" placeholder="learner@company.com" />
                </div>
                <div>
                    <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Full name (auto-lookup if blank)</label>
                    <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                        data-testid="email-fullname"
                        className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                </div>
            </div>

            {kind === "complaint" && (
                <div className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Ticket reference</label>
                            <input value={ticketRef} onChange={(e) => setTicketRef(e.target.value)}
                                data-testid="email-ticket-ref"
                                placeholder="TKT-1234"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand" />
                        </div>
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Signed by</label>
                            <input value={agentName} onChange={(e) => setAgentName(e.target.value)}
                                data-testid="email-agent-name"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                        </div>
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Response body (line breaks preserved)</label>
                        <textarea value={responseText} onChange={(e) => setResponseText(e.target.value)}
                            data-testid="email-response-text"
                            rows={6}
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm leading-relaxed focus:outline-none focus:border-brand"
                            placeholder="Thank you for reaching out. We have looked into this and…" />
                    </div>
                </div>
            )}

            {kind === "expiration" && (
                <div className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Credential / plan name</label>
                            <input value={credential} onChange={(e) => setCredential(e.target.value)}
                                data-testid="email-credential"
                                placeholder="Practitioner tier"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                        </div>
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Expires on</label>
                            <input value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)}
                                data-testid="email-expires-on"
                                placeholder="March 15, 2026"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                        </div>
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">Renewal URL (optional — defaults to /pricing)</label>
                        <input value={renewalUrl} onChange={(e) => setRenewalUrl(e.target.value)}
                            data-testid="email-renewal-url"
                            placeholder="https://…"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand" />
                    </div>
                </div>
            )}

            <div className="mt-6 flex justify-end">
                <button
                    onClick={send}
                    disabled={!canSend || sending}
                    data-testid="email-send"
                    className="btn-primary"
                >
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Send email</>}
                </button>
            </div>
        </div>
    );
}
