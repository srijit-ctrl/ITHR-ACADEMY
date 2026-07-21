import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Clock, BookOpen, Award, Lock, CheckCircle2, ArrowRight, Loader2, Bell, Check, Download, FileText, Presentation } from "lucide-react";
import { CourseIntroHero } from "@/components/CourseIntro";
import CoursePreviewButton from "@/components/CoursePreviewButton";
import { toast } from "sonner";

/** Human-readable tier structure derived from the course's own modules,
 *  never hardcoded. Modules carry a `level` (1=Free, 2=Premium, 3=Certification).
 *  Falls back to "N modules" for coming-soon courses that don't yet have
 *  the full 3-tier ladder in place. */
function tierBreakdown(modules) {
    const counts = { 1: 0, 2: 0, 3: 0 };
    (modules || []).forEach((m) => {
        const lvl = Number(m.level) || 1;
        if (counts[lvl] != null) counts[lvl] += 1;
    });
    const tiersPresent = Object.values(counts).filter((n) => n > 0).length;
    const total = (modules || []).length;
    if (!total) return null;
    if (tiersPresent >= 2) return `${total} module${total === 1 ? "" : "s"} across ${tiersPresent} tier${tiersPresent === 1 ? "" : "s"}`;
    return `${total} module${total === 1 ? "" : "s"}`;
}

export default function CourseDetail() {
    const { slug } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const [course, setCourse] = useState(null);
    const [loading, setLoading] = useState(true);
    const [enrolled, setEnrolled] = useState(false);
    const [enrolling, setEnrolling] = useState(false);
    const [waitlisted, setWaitlisted] = useState(false);
    const [joiningWaitlist, setJoiningWaitlist] = useState(false);

    const [enrollWhatsapp, setEnrollWhatsapp] = useState(false);
    const [enrollWhatsappNumber, setEnrollWhatsappNumber] = useState("");

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
            // Optional WhatsApp opt-in submitted alongside the enrollment.
            // Failures here must NEVER block the enrollment success path —
            // learner can always opt in later from the dashboard.
            if (enrollWhatsapp && enrollWhatsappNumber.trim()) {
                api.post("/whatsapp/opt-in", {
                    opt_in: true,
                    whatsapp_number: enrollWhatsappNumber.trim(),
                    source: "enrollment_form",
                }).catch(() => {});
            }
            setEnrolled(true);
            if (course.modules?.length > 0 && course.modules[0].lessons?.length > 0) {
                navigate(`/learn/${slug}/${course.modules[0].id}/${course.modules[0].lessons[0].id}`);
            }
        } finally { setEnrolling(false); }
    };

    const handleWaitlist = async () => {
        if (!user) { navigate("/login", { state: { from: `/courses/${slug}` } }); return; }
        setJoiningWaitlist(true);
        try {
            const r = await api.post(`/courses/${slug}/waitlist`);
            setWaitlisted(true);
            toast.success(r.data.already_joined ? "You're already on this waitlist." : "You're on the list — we'll email you when it launches.");
        } catch (err) {
            toast.error(err.response?.data?.detail || "Couldn't join the waitlist. Try again in a moment.");
        } finally {
            setJoiningWaitlist(false);
        }
    };

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;
    if (!course) return <div className="container-page py-24 text-center">Course not found. <Link to="/courses" className="text-brand underline">Back to catalog</Link></div>;

    const isComingSoon = course.status === "coming_soon";
    const hasFull = !isComingSoon && course.modules && course.modules.length > 0;
    const firstLesson = hasFull && course.modules[0]?.lessons?.[0];
    const tierText = tierBreakdown(course.modules);
    const totalLessons = (course.modules || []).reduce((n, m) => n + (m.lessons?.length || 0), 0);

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
                            {isComingSoon && (
                                <span
                                    data-testid="course-coming-soon-badge"
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1 border border-brand bg-brand/10 text-brand text-[10px] font-mono uppercase tracking-[0.15em]"
                                >
                                    <Bell className="w-3 h-3" /> Coming soon
                                </span>
                            )}
                            <span className="badge-crimson">{course.category}</span>
                            <span className="badge-mono">{course.difficulty}</span>
                            {course.industries?.slice(0, 3).map((ind) => <span key={ind} className="badge-mono">{ind}</span>)}
                        </div>
                        <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1.02] mb-4">{course.title}</h1>
                        <p className="text-xl text-muted-foreground italic mb-6">{course.subtitle}</p>
                        {!isComingSoon && (
                            <div className="mb-8">
                                <CoursePreviewButton course={course} variant="pill" />
                            </div>
                        )}
                        <p className="text-base leading-relaxed max-w-3xl mb-8">{course.description}</p>

                        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground border-t border-border pt-6">
                            <span className="flex items-center gap-2"><Clock className="w-4 h-4" /><b className="text-foreground">{course.duration_hours}h</b> total</span>
                            <span className="flex items-center gap-2"><BookOpen className="w-4 h-4" />{course.modules?.length || 0} modules</span>
                            {!isComingSoon && (
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
                            )}
                        </div>
                    </div>

                    <aside className="lg:col-span-4">
                        <div className="card-flat p-8 sticky top-24" data-testid={`course-sidebar-${course.status || "published"}`}>
                            {isComingSoon ? (
                                <>
                                    <div className="overline mb-3">Waitlist</div>
                                    <div className="font-serif text-2xl leading-tight mb-1">Not yet enrollable</div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-6">Curriculum in preparation · Editorial team</div>
                                </>
                            ) : (
                                <>
                                    <div className="overline mb-3">Certification Track</div>
                                    <div className="font-serif text-2xl leading-tight mb-1">ITHR Academy Editorial Team</div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-6">Course authored &amp; reviewed by ITHR</div>
                                </>
                            )}

                            {isComingSoon ? (
                                <button
                                    onClick={handleWaitlist}
                                    disabled={joiningWaitlist || waitlisted}
                                    data-testid="waitlist-button"
                                    className="btn-primary w-full mb-3"
                                >
                                    {waitlisted ? (
                                        <><Check className="w-4 h-4" /> On the list</>
                                    ) : joiningWaitlist ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <><Bell className="w-4 h-4" /> Notify me when live</>
                                    )}
                                </button>
                            ) : enrolled ? (
                                <Link to={firstLesson ? `/learn/${slug}/${course.modules[0].id}/${firstLesson.id}` : "/dashboard"} data-testid="continue-learning" className="btn-primary w-full mb-3">
                                    Continue learning <ArrowRight className="w-4 h-4" />
                                </Link>
                            ) : (
                                <>
                                    <label className="flex items-start gap-2 mb-3 cursor-pointer text-xs text-muted-foreground leading-relaxed" data-testid="enrollment-whatsapp-optin-row">
                                        <input
                                            type="checkbox"
                                            checked={enrollWhatsapp}
                                            onChange={(e) => setEnrollWhatsapp(e.target.checked)}
                                            data-testid="enrollment-whatsapp-checkbox"
                                            className="mt-0.5 w-3.5 h-3.5 rounded border-border accent-brand shrink-0"
                                        />
                                        <span>Send me course reminders and updates via WhatsApp <span className="opacity-60">(optional)</span></span>
                                    </label>
                                    {enrollWhatsapp && (
                                        <input
                                            type="tel"
                                            value={enrollWhatsappNumber}
                                            onChange={(e) => setEnrollWhatsappNumber(e.target.value)}
                                            placeholder="+9715XXXXXXXX"
                                            data-testid="enrollment-whatsapp-number"
                                            className="w-full text-xs bg-surface border border-border rounded-sm px-3 py-1.5 mb-3 focus:outline-none focus:border-brand"
                                        />
                                    )}
                                    <button
                                        onClick={handleEnroll}
                                        disabled={enrolling}
                                        data-testid="enroll-button"
                                        className="btn-primary w-full mb-3"
                                    >
                                        {enrolling ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enroll — Modules 1-5 free"}
                                    </button>
                                </>
                            )}
                            {hasFull && course.quiz?.length > 0 && enrolled && (
                                <Link to={`/quiz/${slug}`} data-testid="take-quiz-link" className="btn-outline w-full">
                                    <Award className="w-4 h-4" /> Attempt certification exam
                                </Link>
                            )}

                            <div className="mt-8 space-y-3 text-sm">
                                {tierText && (
                                    <div className="flex items-start gap-3">
                                        <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                        <span data-testid="course-sidebar-modules">{tierText}</span>
                                    </div>
                                )}
                                {!isComingSoon && totalLessons > 0 && (
                                    <div className="flex items-start gap-3">
                                        <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                        <span>{totalLessons} lessons · Hands-on labs</span>
                                    </div>
                                )}
                                {!isComingSoon && (
                                    <div className="flex items-start gap-3">
                                        <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                        <span>Verified digital credential upon passing</span>
                                    </div>
                                )}
                                {!isComingSoon && (
                                    <div className="flex items-start gap-3">
                                        <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                        <span>Personal AI tutor throughout</span>
                                    </div>
                                )}
                                {isComingSoon && (
                                    <p className="text-xs text-muted-foreground leading-relaxed" data-testid="course-sidebar-coming-soon-copy">
                                        We publish curriculum only when it clears our editorial review. Join the waitlist and we'll email you the moment this course goes live — no enrollment or payment is accepted until then.
                                    </p>
                                )}
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
                    {course.learning_objectives?.length > 0 ? (
                        <ul className="space-y-4" data-testid="course-objectives">
                            {course.learning_objectives.map((o, i) => (
                                <li key={`objective-${i}-${o.slice(0, 24)}`} className="flex gap-4">
                                    <span className="font-mono text-xs text-brand pt-1">{String(i + 1).padStart(2, "0")}</span>
                                    <span className="text-base">{o}</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-sm text-muted-foreground leading-relaxed" data-testid="course-objectives-empty">
                            Detailed learning objectives will be published when this course launches. Join the waitlist to receive the full syllabus the day it becomes available.
                        </p>
                    )}

                    {course.skills_gained?.length > 0 && (
                        <>
                            <div className="overline mt-12 mb-3">Skills gained</div>
                            <div className="flex flex-wrap gap-2">
                                {course.skills_gained.map((s) => <span key={s} className="badge-mono">{s}</span>)}
                            </div>
                        </>
                    )}

                    {course.resources?.length > 0 && (
                        <>
                            <div className="overline mt-12 mb-3">Course materials</div>
                            <div className="space-y-3" data-testid="course-resources">
                                {course.resources.map((r) => (
                                    <ResourceRow
                                        key={r.id || r.filename}
                                        resource={r}
                                        courseSlug={course.slug}
                                        enrolled={enrolled}
                                    />
                                ))}
                            </div>
                        </>
                    )}
                </div>

                <div className="lg:col-span-7">
                    <div className="overline mb-4 fine-rule pl-4">Curriculum</div>
                    <h2 className="font-serif text-3xl tracking-tight mb-6">
                        {course.modules?.length ? `${course.modules.length}-module program` : "Curriculum coming soon"}
                    </h2>

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
                        <div className="card-flat p-8" data-testid="course-curriculum-placeholder">
                            <div className="flex items-start gap-4">
                                <Lock className="w-5 h-5 text-muted-foreground mt-1 shrink-0" />
                                <div>
                                    <p className="font-serif text-lg mb-2">Full curriculum in preparation</p>
                                    <p className="text-sm text-muted-foreground">
                                        This course is being written now by the ITHR editorial team. Join the waitlist and we'll notify you the moment the full syllabus, hands-on labs, and certification exam are live. No enrollment is accepted until publication.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
}

/**
 * ResourceRow — one downloadable course asset (PPTX / PDF / etc).
 *
 * Access rules mirror the backend:
 *   - `public` resources → anyone can download (no auth check triggered).
 *   - Non-public resources → learner must be enrolled OR the backend returns
 *     403; we gate the download button client-side so the CTA is honest.
 */
function ResourceRow({ resource, courseSlug, enrolled }) {
    const [busy, setBusy] = useState(false);
    const locked = !resource.public && !enrolled;

    const kindIcon =
        resource.kind === "presentation" ? Presentation :
        resource.kind === "pdf"          ? FileText     :
        FileText;
    const KindIcon = kindIcon;

    const sizeLabel = resource.size_bytes
        ? `${(resource.size_bytes / 1024 / 1024).toFixed(1)} MB`
        : null;

    const download = async () => {
        if (locked) {
            toast.info("Enrol in this course to unlock materials.");
            return;
        }
        setBusy(true);
        try {
            const res = await api.get(
                `/courses/${courseSlug}/resources/${encodeURIComponent(resource.filename)}`,
                { responseType: "blob" },
            );
            const url = URL.createObjectURL(res.data);
            const a = document.createElement("a");
            a.href = url;
            a.download = resource.download_name || resource.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast.success("Downloaded — check your Downloads folder");
        } catch (e) {
            const status = e?.response?.status;
            if (status === 403) toast.error("Enrol in this course to unlock materials.");
            else if (status === 404) toast.error("Resource missing — please contact support.");
            else toast.error(e?.response?.data?.detail || "Download failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="card-flat p-4 flex items-center gap-4"
            data-testid={`course-resource-${resource.id || resource.filename}`}
        >
            <div className="w-11 h-11 rounded-lg flex items-center justify-center shrink-0"
                 style={{ background: "linear-gradient(135deg, #00A78B 0%, #2E7FC1 100%)", color: "#fff" }}>
                <KindIcon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <div className="font-serif text-base leading-tight truncate">{resource.title}</div>
                    {locked && (
                        <span className="badge-mono text-muted-foreground inline-flex items-center gap-1">
                            <Lock className="w-3 h-3" /> Enrolled only
                        </span>
                    )}
                </div>
                {resource.description && (
                    <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{resource.description}</div>
                )}
                <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1.5">
                    {resource.kind === "presentation" ? "PowerPoint deck" : resource.kind?.toUpperCase() || "File"}
                    {sizeLabel && <span> · {sizeLabel}</span>}
                </div>
            </div>
            <button
                onClick={download}
                disabled={busy}
                data-testid={`course-resource-download-${resource.id || resource.filename}`}
                className="btn-primary shrink-0 inline-flex items-center gap-2 disabled:opacity-60"
                title={locked ? "Enrol to download" : "Download"}
            >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                <span className="hidden sm:inline">{locked ? "Locked" : "Download"}</span>
            </button>
        </div>
    );
}

