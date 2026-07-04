import { useEffect, useState, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ArrowLeft, ArrowRight, CheckCircle2, Circle, Award, Loader2 } from "lucide-react";
import InlineTutor from "@/components/InlineTutor";

export default function LessonViewer() {
    const { slug, moduleId, lessonId } = useParams();
    const navigate = useNavigate();
    const [course, setCourse] = useState(null);
    const [enrollment, setEnrollment] = useState(null);
    const [loading, setLoading] = useState(true);
    const [completing, setCompleting] = useState(false);

    useEffect(() => {
        Promise.all([
            api.get(`/courses/${slug}`),
            api.get("/enrollments"),
        ]).then(([courseRes, enrRes]) => {
            setCourse(courseRes.data);
            const e = enrRes.data.find((x) => x.course?.slug === slug);
            setEnrollment(e?.enrollment || null);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, [slug]);

    const { module, lesson, allLessons, currentIndex } = useMemo(() => {
        if (!course) return {};
        const m = course.modules?.find((x) => x.id === moduleId);
        const l = m?.lessons?.find((x) => x.id === lessonId);
        const all = [];
        course.modules?.forEach((mm) => mm.lessons?.forEach((ll) => all.push({ moduleId: mm.id, module: mm, lesson: ll })));
        const idx = all.findIndex((x) => x.lesson.id === lessonId);
        return { module: m, lesson: l, allLessons: all, currentIndex: idx };
    }, [course, moduleId, lessonId]);

    const completedSet = new Set(enrollment?.completed_lessons || []);
    const isCompleted = completedSet.has(lessonId);

    const markComplete = async () => {
        setCompleting(true);
        try {
            const res = await api.post("/lessons/complete", {
                course_id: course.id,
                lesson_id: lessonId,
                module_id: moduleId,
            });
            setEnrollment((prev) => ({
                ...(prev || {}),
                completed_lessons: [...new Set([...(prev?.completed_lessons || []), lessonId])],
                progress_pct: res.data.progress_pct,
            }));
        } finally { setCompleting(false); }
    };

    const goNext = () => {
        const next = allLessons?.[currentIndex + 1];
        if (next) navigate(`/learn/${slug}/${next.moduleId}/${next.lesson.id}`);
    };
    const goPrev = () => {
        const prev = allLessons?.[currentIndex - 1];
        if (prev) navigate(`/learn/${slug}/${prev.moduleId}/${prev.lesson.id}`);
    };

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;
    if (!course || !module || !lesson) return <div className="container-page py-24 text-center">Lesson not found. <Link to="/courses" className="text-brand underline">Back to catalog</Link></div>;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[calc(100vh-4rem)]">
            {/* Sidebar */}
            <aside className="lg:col-span-3 border-r border-border bg-surface-alt/30 p-6 lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)] lg:overflow-y-auto">
                <Link to={`/courses/${slug}`} data-testid="back-to-course" className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-brand flex items-center gap-1 mb-6">
                    <ArrowLeft className="w-3 h-3" /> Back to course
                </Link>

                <div className="font-serif text-xl leading-tight mb-1">{course.title}</div>
                <div className="text-xs text-muted-foreground font-mono uppercase tracking-[0.15em] mb-6">
                    Progress: {Math.round(enrollment?.progress_pct || 0)}%
                </div>
                <div className="h-1 bg-border mb-8">
                    <div className="h-full bg-brand transition-all duration-500" style={{ width: `${enrollment?.progress_pct || 0}%` }} />
                </div>

                <nav className="space-y-6">
                    {course.modules?.map((m) => (
                        <div key={m.id}>
                            <div className="flex items-center gap-2 mb-2">
                                <span className="font-mono text-[10px] text-brand">M{String(m.number).padStart(2, "0")}</span>
                                <span className="font-serif text-sm leading-tight">{m.title}</span>
                            </div>
                            <ul className="space-y-0.5 pl-6">
                                {m.lessons?.map((l) => (
                                    <li key={l.id}>
                                        <Link
                                            to={`/learn/${slug}/${m.id}/${l.id}`}
                                            data-testid={`sidebar-lesson-${l.id}`}
                                            className={`flex items-center gap-2 py-1.5 text-xs transition-colors ${l.id === lessonId ? "text-brand font-medium" : "text-muted-foreground hover:text-foreground"}`}
                                        >
                                            {completedSet.has(l.id) ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> : <Circle className="w-3.5 h-3.5" />}
                                            <span className="flex-1 leading-tight">{l.title}</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </nav>
            </aside>

            {/* Content */}
            <main className="lg:col-span-9 p-8 md:p-14 max-w-4xl">
                <div className="mb-6">
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand mb-3">Module {String(module.number).padStart(2, "0")} · Lesson {lesson.duration_min} min</div>
                    <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none">{lesson.title}</h1>
                </div>

                <article className="prose-lesson">
                    {lesson.content.split(/\n\n+/).map((para, i) => (
                        <p key={i} dangerouslySetInnerHTML={{
                            __html: para
                                .replace(/^### (.+)$/gm, '<h3>$1</h3>')
                                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                                .replace(/`([^`]+)`/g, '<code>$1</code>')
                                .replace(/\n/g, '<br/>'),
                        }} />
                    ))}
                </article>

                {lesson.code_sample && (
                    <div className="mt-8 border border-border">
                        <div className="bg-surface-alt px-4 py-2 border-b border-border text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Code sample</div>
                        <pre className="p-5 bg-foreground text-background font-mono text-xs leading-relaxed overflow-x-auto"><code>{lesson.code_sample}</code></pre>
                    </div>
                )}

                {lesson.key_takeaways?.length > 0 && (
                    <div className="mt-10 card-flat p-6 bg-surface-alt/40">
                        <div className="overline mb-4">Key Takeaways</div>
                        <ul className="space-y-2">
                            {lesson.key_takeaways.map((t, i) => (
                                <li key={i} className="flex gap-3 text-sm">
                                    <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                    <span>{t}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Inline AI Tutor (Aletheia) — contextual to this lesson */}
                <InlineTutor courseSlug={slug} lesson={lesson} moduleTitle={module.title} />

                {/* Actions */}
                <div className="mt-14 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pt-8 border-t border-border">
                    <button onClick={goPrev} disabled={currentIndex <= 0} data-testid="prev-lesson" className="btn-outline disabled:opacity-40">
                        <ArrowLeft className="w-4 h-4" /> Previous
                    </button>

                    <button
                        onClick={markComplete}
                        disabled={isCompleted || completing}
                        data-testid="mark-complete"
                        className={isCompleted ? "btn-outline text-success border-success" : "btn-primary"}
                    >
                        {completing ? <Loader2 className="w-4 h-4 animate-spin" /> : isCompleted ? <><CheckCircle2 className="w-4 h-4" /> Completed</> : "Mark as complete"}
                    </button>

                    {currentIndex < (allLessons?.length || 0) - 1 ? (
                        <button onClick={goNext} data-testid="next-lesson" className="btn-primary">
                            Next lesson <ArrowRight className="w-4 h-4" />
                        </button>
                    ) : (
                        <Link to={`/quiz/${slug}`} data-testid="go-to-quiz" className="btn-primary">
                            <Award className="w-4 h-4" /> Take certification exam
                        </Link>
                    )}
                </div>
            </main>
        </div>
    );
}
