import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Building2, Users, Award, TrendingUp, Copy, Loader2, ArrowRight, Settings, Sparkles, BarChart3 } from "lucide-react";
import { OrgAnalyticsPanel } from "@/components/AnalyticsPanels";
import { toast } from "sonner";
import HeroBlobs from "@/components/HeroBlobs";
import StatCard from "@/components/enterprise/StatCard";
import SeatEditorModal from "@/components/enterprise/SeatEditorModal";
import MemberList from "@/components/enterprise/MemberList";
import EnterpriseSidebar from "@/components/enterprise/EnterpriseSidebar";

/**
 * Enterprise Portal shell — composes MemberList, SeatEditorModal, EnterpriseSidebar,
 * and OrgAnalyticsPanel. Owns the top-level dashboard load + post-checkout seat
 * fulfillment redirect handling.
 */
export default function EnterprisePortal() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [dashboard, setDashboard] = useState(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [copied, setCopied] = useState(false);

    // Seat editor state (hoisted so both the modal + summary widgets read consistent values)
    const [showSeatEditor, setShowSeatEditor] = useState(false);
    const [seatTarget, setSeatTarget] = useState(0);
    const [seatPreview, setSeatPreview] = useState(null);
    const [seatBusy, setSeatBusy] = useState(false);

    const [billing, setBilling] = useState([]);
    const [showAnalytics, setShowAnalytics] = useState(false);

    const load = ({ silent = false } = {}) => {
        if (!silent) setLoading(true);
        api.get("/enterprise/organizations/dashboard")
            .then((r) => setDashboard(r.data))
            .catch((e) => {
                if (e.response?.status === 404) setNotFound(true);
                else setDashboard(null);
            })
            .finally(() => setLoading(false));
    };

    useEffect(() => { load(); }, []);

    // Load billing events once we know the org exists + caller is owner
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
    }, [searchParams, setSearchParams]);

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

    const { organization: org, summary, members: _members, departments, top_courses, membership } = dashboard;
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
                                <button
                                    onClick={() => setShowAnalytics((v) => !v)}
                                    data-testid="toggle-analytics"
                                    className={`text-xs ${showAnalytics ? "btn-primary" : "btn-outline"}`}
                                >
                                    <BarChart3 className="w-3 h-3" /> {showAnalytics ? "Hide analytics" : "View analytics"}
                                </button>
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
                <SeatEditorModal
                    open={showSeatEditor}
                    org={org}
                    summary={summary}
                    seatTarget={seatTarget}
                    setSeatTarget={setSeatTarget}
                    seatPreview={seatPreview}
                    setSeatPreview={setSeatPreview}
                    seatBusy={seatBusy}
                    setSeatBusy={setSeatBusy}
                    onClose={() => setShowSeatEditor(false)}
                    onSuccess={() => load({ silent: true })}
                />

                {/* Analytics panel — collapsed by default */}
                {showAnalytics && isAdmin && (
                    <div className="mb-10">
                        <OrgAnalyticsPanel />
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
                    <div className="lg:col-span-8">
                        <MemberList dashboard={dashboard} isAdmin={isAdmin} onReload={() => load({ silent: true })} />
                    </div>
                    <div className="lg:col-span-4">
                        <EnterpriseSidebar
                            departments={departments}
                            topCourses={top_courses}
                            isOwner={isOwner}
                            billing={billing}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
