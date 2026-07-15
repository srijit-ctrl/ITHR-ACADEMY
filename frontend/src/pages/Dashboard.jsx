import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Award, BookOpen, TrendingUp, Flame, Sparkles, ExternalLink, Loader2, Building2, Compass, ArrowRight, Star, Copy } from "lucide-react";
import { toast } from "sonner";
import CredentialImpressions from "@/components/CredentialImpressions";
import { ReferralPanel } from "@/components/ReferralPanel";

export default function Dashboard() {
    const { user } = useAuth();
    const [stats, setStats] = useState(null);
    const [enrollments, setEnrollments] = useState([]);
    const [certificates, setCertificates] = useState([]);
    const [nextBest, setNextBest] = useState(null);
    const [recs, setRecs] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            api.get("/dashboard/stats"),
            api.get("/enrollments"),
            api.get("/certificates"),
            api.get("/recommendations").catch(() => ({ data: { recommendations: [] } })),
            api.get("/recommendations/next-best").catch(() => ({ data: { recommendation: null } })),
        ]).then(([s, e, c, r, nb]) => {
            setStats(s.data);
            setEnrollments(e.data);
            setCertificates(c.data);
            setRecs(r.data.recommendations || []);
            setNextBest(nb.data.recommendation || null);
        }).catch((err) => {
            console.error("dashboard load failed:", err);
        }).finally(() => setLoading(false));
        // user is auth-context-derived; API endpoints resolve user from JWT — no need to react to
        // user identity changing (a logout unmounts this page).
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;

    return (
        <div className="container-page py-12">
            {/* Header */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8 mb-12">
                <div className="md:col-span-8">
                    <div className="overline mb-4 fine-rule pl-4">Welcome back</div>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none">
                        {user?.full_name.split(" ")[0]}.
                    </h1>
                    <p className="mt-4 text-muted-foreground text-lg max-w-xl">
                        {enrollments.length === 0
                            ? "Your learning journey begins with a single enrollment. Explore the catalog."
                            : "Pick up where you left off, or begin something new."}
                    </p>
                    {user?.founding_member_seq && (
                        <FoundingMemberBadge
                            seq={user.founding_member_seq}
                            code={user.signup_discount_code}
                            hasClaimedCourse={!!user.founding_course_id}
                            certUsed={!!user.founding_cert_used}
                        />
                    )}
                </div>
                <div className="md:col-span-4 grid grid-cols-2 gap-3">
                    <StatCard icon={BookOpen} label="Enrollments" value={stats?.enrollments || 0} testId="stat-enrollments" />
                    <StatCard icon={Award} label="Certificates" value={stats?.certificates || 0} testId="stat-certificates" />
                    <StatCard icon={TrendingUp} label="XP" value={stats?.xp || 0} testId="stat-xp" />
                    <StatCard icon={Flame} label="Day streak" value={stats?.streak_days || 0} testId="stat-streak" />
                    <Link to="/enterprise/portal" data-testid="dashboard-enterprise-link" className="card-flat p-4 col-span-2 flex items-center justify-between hover:border-brand transition-colors">
                        <div className="flex items-center gap-3">
                            <Building2 className="w-4 h-4 text-brand" />
                            <div>
                                <div className="font-serif text-sm leading-none">Enterprise Portal</div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">Team dashboard · Invites · Seats</div>
                            </div>
                        </div>
                        <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    </Link>
                    <Link to="/mentor" data-testid="dashboard-mentor-link" className="card-flat p-4 col-span-2 flex items-center justify-between hover:border-brand transition-colors">
                        <div className="flex items-center gap-3">
                            <Compass className="w-4 h-4 text-brand" />
                            <div>
                                <div className="font-serif text-sm leading-none">Meet Solon · Career Mentor</div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">Personalized credential roadmap</div>
                            </div>
                        </div>
                        <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    </Link>
                    <Link to="/passport" data-testid="dashboard-passport-link" className="card-flat p-4 col-span-2 flex items-center justify-between hover:border-brand transition-colors">
                        <div className="flex items-center gap-3">
                            <Award className="w-4 h-4 text-brand" />
                            <div>
                                <div className="font-serif text-sm leading-none">AI Skills Passport</div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">Portable · verifiable · shareable</div>
                            </div>
                        </div>
                        <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    </Link>
                </div>
            </div>

            <ReferralPanel />

            {/* Next-best recommendation banner */}
            {nextBest && (
                <section className="mb-14" data-testid="dashboard-nextbest">
                    <div className="cert-beam">
                        <div className="bg-surface p-8 md:p-10 grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
                            <div className="md:col-span-2 flex md:justify-start">
                                <div className="w-14 h-14 bg-foreground text-background flex items-center justify-center">
                                    <Sparkles className="w-6 h-6" />
                                </div>
                            </div>
                            <div className="md:col-span-7">
                                <div className="overline mb-2">Solon recommends · Next best step</div>
                                <div className="font-serif text-2xl md:text-3xl tracking-tight leading-tight mb-3">
                                    {nextBest.course.title}
                                </div>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {nextBest.rationale}
                                </p>
                            </div>
                            <div className="md:col-span-3 md:text-right space-y-2">
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                                    {nextBest.course.difficulty} · {nextBest.course.duration_hours}h
                                </div>
                                <Link
                                    to={`/courses/${nextBest.course.slug}`}
                                    data-testid="nextbest-cta"
                                    className="btn-primary inline-flex"
                                >
                                    Explore <ArrowRight className="w-4 h-4" />
                                </Link>
                            </div>
                        </div>
                    </div>
                </section>
            )}

            {/* Enrollments */}
            <section className="mb-16">
                <div className="flex items-end justify-between mb-6">
                    <h2 className="font-serif text-3xl tracking-tight">Your courses</h2>
                    <Link to="/courses" data-testid="explore-more-courses" className="text-sm text-brand hover:underline">Explore more →</Link>
                </div>

                {enrollments.length === 0 ? (
                    <div className="card-flat p-12 text-center">
                        <Sparkles className="w-8 h-8 text-brand mx-auto mb-4" />
                        <p className="font-serif text-2xl mb-2">Enroll in your first course</p>
                        <p className="text-muted-foreground mb-6">Free access to the first five modules of every course.</p>
                        <Link to="/courses" data-testid="empty-explore-catalog" className="btn-primary">Browse catalog</Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {enrollments.map(({ enrollment, course }) => (
                            <Link
                                key={enrollment.id}
                                to={`/courses/${course.slug}`}
                                data-testid={`dashboard-enrollment-${course.slug}`}
                                className="card-sharp p-6 flex gap-5 items-start"
                            >
                                <div className="w-24 h-24 shrink-0 overflow-hidden border border-border">
                                    <img src={course.thumbnail_url} alt="" className="w-full h-full object-cover" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">{course.category}</div>
                                    <div className="font-serif text-lg leading-tight mb-3 line-clamp-2">{course.title}</div>
                                    <div className="h-1 bg-border">
                                        <div className="h-full bg-brand" style={{ width: `${enrollment.progress_pct}%` }} />
                                    </div>
                                    <div className="mt-2 text-xs text-muted-foreground flex justify-between">
                                        <span>{Math.round(enrollment.progress_pct)}% complete</span>
                                        {enrollment.completed ? <span className="text-success font-mono uppercase tracking-wider">Certified</span> : <span>Continue →</span>}
                                    </div>
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </section>

            {/* Certificates */}
            {certificates.length > 0 && (
                <section className="mb-14">
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
                        <div className="lg:col-span-8">
                            <h2 className="font-serif text-3xl tracking-tight mb-6">Your certificates</h2>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {certificates.map((c) => (
                                    <div key={c.id} className="cert-beam" data-testid={`dashboard-cert-${c.certificate_id}`}>
                                        <div className="bg-surface p-6">
                                            <Award className="w-6 h-6 text-brand mb-4" />
                                            <div className="font-serif text-xl leading-tight mb-2">{c.course_title}</div>
                                            <div className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mb-4">{c.certificate_id}</div>
                                            <div className="text-sm mb-4">Score: <b>{c.score}%</b></div>
                                            <Link to={`/certificate/${c.certificate_id}`} data-testid={`view-cert-${c.certificate_id}`} className="text-sm text-brand inline-flex items-center gap-1 hover:underline">
                                                View credential <ExternalLink className="w-3 h-3" />
                                            </Link>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="lg:col-span-4">
                            <CredentialImpressions />
                        </div>
                    </div>
                </section>
            )}

            {/* Broader recommendations */}
            {recs.length > 1 && (
                <section data-testid="dashboard-recs">
                    <div className="flex items-end justify-between mb-6">
                        <div>
                            <div className="overline mb-2">Recommended for you</div>
                            <h2 className="font-serif text-3xl tracking-tight">More courses tuned to your posture</h2>
                        </div>
                        <Link to="/courses" className="text-sm text-brand hover:underline">All courses →</Link>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        {recs.slice(1, 7).map((r) => (
                            <Link
                                key={r.course.id}
                                to={`/courses/${r.course.slug}`}
                                data-testid={`rec-${r.course.slug}`}
                                className="card-sharp p-5 group"
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <span className="badge-mono">{r.course.category}</span>
                                    <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand">Match {Math.round(r.score)}</span>
                                </div>
                                <div className="font-serif text-lg leading-tight mb-2 line-clamp-2">{r.course.title}</div>
                                <p className="text-sm text-muted-foreground line-clamp-2">{r.course.subtitle}</p>
                                <div className="mt-4 flex items-center justify-between text-[11px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                                    <span>{r.course.difficulty} · {r.course.duration_hours}h</span>
                                    <span className="text-brand opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1">Open <ArrowRight className="w-3 h-3" /></span>
                                </div>
                            </Link>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}

function StatCard({ icon: Icon, label, value, testId }) {
    return (
        <div className="card-flat p-4" data-testid={testId}>
            <Icon className="w-4 h-4 text-brand mb-2" />
            <div className="font-serif text-2xl leading-none">{value}</div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">{label}</div>
        </div>
    );
}

function FoundingMemberBadge({ seq, code, hasClaimedCourse, certUsed }) {
    const copy = () => {
        navigator.clipboard.writeText(code);
        toast.success("Founding-member code copied");
    };
    const statusLine = certUsed
        ? "You've already redeemed your free certificate. Thank you for being a founder."
        : hasClaimedCourse
            ? "Your first-course perk is locked in. Complete it to claim your free certificate."
            : "Enroll in your first course to lock in modules 6–15 unlocked + a free certificate on that course.";

    return (
        <div className="mt-6 border-2 border-brand bg-brand/5 rounded-sm p-5 max-w-xl" data-testid="founding-member-badge">
            <div className="flex items-start gap-4">
                <div className="w-11 h-11 shrink-0 rounded-full bg-brand text-white flex items-center justify-center">
                    <Star className="w-5 h-5 fill-current" />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand mb-1">
                        Founding Member · #{seq} of 500
                    </div>
                    <div className="font-sans font-semibold text-lg leading-tight">Thanks for being early.</div>
                    <p className="text-sm text-muted-foreground mt-1">{statusLine}</p>
                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                        <code
                            className="font-mono text-sm bg-surface border border-border px-3 py-1.5 rounded-sm select-all"
                            data-testid="founding-member-code"
                        >
                            {code}
                        </code>
                        <button
                            onClick={copy}
                            data-testid="founding-member-code-copy"
                            className="p-1.5 hover:bg-surface-alt rounded-sm text-muted-foreground hover:text-brand"
                            title="Copy code"
                        >
                            <Copy className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
