import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Clock, BookOpen, Award, Lock, CheckCircle2, ArrowRight, Loader2 } from "lucide-react";
import { CourseIntroHero } from "@/components/CourseIntro";
import CoursePreviewButton from "@/components/CoursePreviewButton";

export default function CourseDetail() {
    const { slug } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const [course, setCourse] = useState(null);
    const [loading, setLoading] = useState(true);
    const [enrolled, setEnrolled] = useState(false);
    const [enrolling, setEnrolling] = useState(false);

    useEffect(() => {
        api.get(`/courses/${slug}`).then((r) => { setCourse(r.data); setLoading(false); }).catch(() => setLoading(false));
        if (user) {
            api.get("/enrollments").then((r) => {
                const isEnrolled = r.data.some((e) => e.course?.slug === slug);
                setEnrolled(isEnrolled);
            });
        }
    }, [slug, user]);

    const handleEnroll = async () => {
        if (!user) { navigate("/login", { state: { from: `/courses/${slug}` } }); return; }
        setEnrolling(true);
        try {
            await api.post(`/courses/${slug}/enroll`);
            setEnrolled(true);
            if (course.modules?.length > 0 && course.modules[0].lessons?.length > 0) {
                navigate(`/learn/${slug}/${course.modules[0].id}/${course.modules[0].lessons[0].id}`);
            }
        } finally { setEnrolling(false); }
    };

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;
    if (!course) return <div className="container-page py-24 text-center">Course not found. <Link to="/courses" className="text-brand underline">Back to catalog</Link></div>;

    const hasFull = course.modules && course.modules.length > 0;
    const firstLesson = hasFull && course.modules[0]?.lessons?.[0];

    return (
        <div>
            {/* Hero */}
            <section className="border-b border-border relative overflow-hidden">
                {(course.hero_url || course.thumbnail_url || course.intro_video_url) && (
                    <>
                        <div className="absolute inset-0">
                            <CourseIntroHero course={course} />
                        </div>
                        <div className="absolute inset-0 bg-background/95 backdrop-blur-[2px]" />
                    </>
                )}
                <div className="relative container-page py-16 md:py-24 grid grid-cols-1 lg:grid-cols-12 gap-10">
                    <div className="lg:col-span-8">
                        <div className="flex flex-wrap items-center gap-3 mb-6">
                            <span className="badge-crimson">{course.category}</span>
                            <span className="badge-mono">{course.difficulty}</span>
                            {course.industries?.slice(0, 3).map((ind) => <span key={ind} className="badge-mono">{ind}</span>)}
                        </div>
                        <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1.02] mb-4">{course.title}</h1>
                        <p className="text-xl text-muted-foreground italic mb-6">{course.subtitle}</p>
                        <div className="mb-8">
                            <CoursePreviewButton course={course} variant="pill" />
                        </div>
                        <p className="text-base leading-relaxed max-w-3xl mb-8">{course.description}</p>

                        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground border-t border-border pt-6">
                            <span className="flex items-center gap-2"><Clock className="w-4 h-4" /><b className="text-foreground">{course.duration_hours}h</b> total</span>
                            <span className="flex items-center gap-2"><BookOpen className="w-4 h-4" />{course.modules?.length || 15} modules</span>
                            <span className="flex items-center gap-2" data-testid="course-detail-freshness">
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 border border-brand bg-brand/5 text-brand text-[10px] font-mono uppercase tracking-[0.15em]">
                                    <span className="w-1.5 h-1.5 bg-brand rounded-full animate-pulse" />
                                    Freshness {course.freshness_score ?? 100}
                                </span>
                                <span className="text-xs">
                                    {course.days_since_review === 0
                                        ? "Refreshed today"
                                        : course.days_since_review == null || course.days_since_review > 500
                                        ? "New"
                                        : `Refreshed ${course.days_since_review}d ago`}
                                </span>
                            </span>
                        </div>
                    </div>

                    <aside className="lg:col-span-4">
                        <div className="card-flat p-8 sticky top-24">
                            <div className="overline mb-3">Certification Track</div>
                            <div className="font-serif text-2xl leading-tight mb-1">ITHR Academy Editorial Team</div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-6">Course authored & reviewed by ITHR</div>

                            {enrolled ? (
                                <Link to={firstLesson ? `/learn/${slug}/${course.modules[0].id}/${firstLesson.id}` : "/dashboard"} data-testid="continue-learning" className="btn-primary w-full mb-3">
                                    Continue learning <ArrowRight className="w-4 h-4" />
                                </Link>
                            ) : (
                                <button
                                    onClick={handleEnroll}
                                    disabled={enrolling}
                                    data-testid="enroll-button"
                                    className="btn-primary w-full mb-3"
                                >
                                    {enrolling ? <Loader2 className="w-4 h-4 animate-spin" /> : (hasFull ? "Enroll — Modules 1-5 free" : "Notify me when live")}
                                </button>
                            )}
                            {hasFull && course.quiz?.length > 0 && enrolled && (
                                <Link to={`/quiz/${slug}`} data-testid="take-quiz-link" className="btn-outline w-full">
                                    <Award className="w-4 h-4" /> Attempt certification exam
                                </Link>
                            )}

                            <div className="mt-8 space-y-3 text-sm">
                                <div className="flex items-start gap-3"><CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span>15 modules across 3 tiers</span></div>
                                <div className="flex items-start gap-3"><CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span>Hands-on labs & capstone project</span></div>
                                <div className="flex items-start gap-3"><CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span>Verified digital credential upon passing</span></div>
                                <div className="flex items-start gap-3"><CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span>Personal AI tutor throughout</span></div>
                            </div>
                        </div>
                    </aside>
                </div>
            </section>

            {/* Learning Objectives + Syllabus */}
            <section className="container-page py-20 grid grid-cols-1 lg:grid-cols-12 gap-16">
                <div className="lg:col-span-5">
                    <div className="overline mb-4 fine-rule pl-4">What you'll master</div>
                    <h2 className="font-serif text-3xl tracking-tight mb-6">Learning objectives</h2>
                    <ul className="space-y-4">
                        {(course.learning_objectives?.length ? course.learning_objectives : [
                            "Deep understanding of the course subject and its enterprise applications",
                            "Practical skills through labs and exercises",
                            "Ability to articulate business impact to executive stakeholders",
                        ]).map((o, i) => (
                            <li key={`objective-${i}-${o.slice(0, 24)}`} className="flex gap-4">
                                <span className="font-mono text-xs text-brand pt-1">{String(i + 1).padStart(2, "0")}</span>
                                <span className="text-base">{o}</span>
                            </li>
                        ))}
                    </ul>

                    {course.skills_gained?.length > 0 && (
                        <>
                            <div className="overline mt-12 mb-3">Skills gained</div>
                            <div className="flex flex-wrap gap-2">
                                {course.skills_gained.map((s) => <span key={s} className="badge-mono">{s}</span>)}
                            </div>
                        </>
                    )}
                </div>

                <div className="lg:col-span-7">
                    <div className="overline mb-4 fine-rule pl-4">Curriculum</div>
                    <h2 className="font-serif text-3xl tracking-tight mb-6">{course.modules?.length || 15}-module program</h2>

                    {hasFull ? (
                        <div className="space-y-2">
                            {course.modules.map((m) => (
                                <details key={m.id} className="card-flat" data-testid={`module-${m.number}`}>
                                    <summary className="flex items-center gap-4 p-5 cursor-pointer hover:bg-surface-alt/50 transition-colors list-none">
                                        <span className="font-mono text-xs text-brand w-10">{String(m.number).padStart(2, "0")}</span>
                                        <span className={`badge-mono ${m.level === 1 ? "text-success" : m.level === 3 ? "text-brand" : ""}`}>
                                            {m.level === 1 ? "Free" : m.level === 2 ? "Premium" : "Certification"}
                                        </span>
                                        <span className="flex-1 font-serif text-lg leading-tight">{m.title}</span>
                                        <span className="text-xs text-muted-foreground hidden sm:inline">{m.lessons?.length || 5} lessons</span>
                                    </summary>
                                    <div className="px-5 pb-5 pl-[3.75rem] border-t border-border">
                                        <p className="text-sm text-muted-foreground my-4">{m.summary}</p>
                                        <ul className="space-y-1.5">
                                            {m.lessons?.map((l, i) => (
                                                <li key={l.id} className="flex items-center gap-3 text-sm py-1.5">
                                                    <span className="font-mono text-[10px] text-muted-foreground w-6">{i + 1}.</span>
                                                    <span className="flex-1">{l.title}</span>
                                                    <span className="text-xs text-muted-foreground">{l.duration_min}m</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </details>
                            ))}
                        </div>
                    ) : (
                        <div className="card-flat p-8">
                            <div className="flex items-start gap-4">
                                <Lock className="w-5 h-5 text-muted-foreground mt-1 shrink-0" />
                                <div>
                                    <p className="font-serif text-lg mb-2">Full curriculum in preparation</p>
                                    <p className="text-sm text-muted-foreground">This course follows the standard 15-module structure: Modules 1–5 free (Fundamentals), 6–10 Premium (Applied), 11–15 Certification (Advanced + Capstone). Full lesson content publishes soon. Enroll to secure early access.</p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
}
