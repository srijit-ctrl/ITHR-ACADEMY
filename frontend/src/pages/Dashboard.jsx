import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Award, BookOpen, TrendingUp, Flame, Sparkles, ExternalLink, Loader2 } from "lucide-react";

export default function Dashboard() {
    const { user } = useAuth();
    const [stats, setStats] = useState(null);
    const [enrollments, setEnrollments] = useState([]);
    const [certificates, setCertificates] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            api.get("/dashboard/stats"),
            api.get("/enrollments"),
            api.get("/certificates"),
        ]).then(([s, e, c]) => {
            setStats(s.data);
            setEnrollments(e.data);
            setCertificates(c.data);
        }).finally(() => setLoading(false));
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
                </div>
                <div className="md:col-span-4 grid grid-cols-2 gap-3">
                    <StatCard icon={BookOpen} label="Enrollments" value={stats?.enrollments || 0} testId="stat-enrollments" />
                    <StatCard icon={Award} label="Certificates" value={stats?.certificates || 0} testId="stat-certificates" />
                    <StatCard icon={TrendingUp} label="XP" value={stats?.xp || 0} testId="stat-xp" />
                    <StatCard icon={Flame} label="Day streak" value={stats?.streak_days || 0} testId="stat-streak" />
                </div>
            </div>

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
                <section>
                    <h2 className="font-serif text-3xl tracking-tight mb-6">Your certificates</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
