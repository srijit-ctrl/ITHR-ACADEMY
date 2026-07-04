import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ArrowRight, Award, Clock, ArrowLeft, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function PathDetail() {
    const { slug } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [path, setPath] = useState(null);
    const [loading, setLoading] = useState(true);
    const [enrolling, setEnrolling] = useState(false);

    useEffect(() => {
        api.get(`/paths/${slug}`).then((r) => setPath(r.data)).finally(() => setLoading(false));
    }, [slug]);

    const enroll = async () => {
        if (!user) return navigate("/login");
        setEnrolling(true);
        try {
            const res = await api.post(`/paths/${slug}/enroll`);
            toast.success(`Enrolled in ${res.data.enrolled} new courses (${res.data.already_enrolled} already active).`);
            navigate("/dashboard");
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Enrollment failed");
        } finally { setEnrolling(false); }
    };

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;
    if (!path) return <div className="container-page py-24 text-center">Path not found.</div>;

    return (
        <div className="container-page py-14">
            <Link to="/paths" className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-brand flex items-center gap-1 mb-6">
                <ArrowLeft className="w-3 h-3" /> All paths
            </Link>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
                <div className="lg:col-span-8">
                    <div className="overline mb-4 fine-rule pl-4">{path.role}</div>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-6">{path.title}</h1>
                    <p className="text-lg text-muted-foreground leading-relaxed mb-8">{path.subtitle}</p>

                    <div className="card-flat p-6 mb-10">
                        <div className="overline mb-4">Outcomes</div>
                        <ul className="space-y-3">
                            {path.outcomes?.map((o, i) => (
                                <li key={i} className="flex gap-3 text-sm">
                                    <CheckCircle2 className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                    <span>{o}</span>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="overline mb-4">The curriculum</div>
                    <ol className="space-y-4">
                        {path.courses?.map((c, i) => (
                            <li key={c.slug} className="card-sharp p-5 flex items-start gap-5" data-testid={`path-course-${c.slug}`}>
                                <span className="font-mono text-xs text-brand shrink-0 pt-1">{String(i + 1).padStart(2, "0")}</span>
                                <div className="flex-1 min-w-0">
                                    <Link to={`/courses/${c.slug}`} className="font-serif text-xl leading-tight hover:text-brand transition-colors">
                                        {c.title}
                                    </Link>
                                    <p className="text-sm text-muted-foreground line-clamp-2 mt-1">{c.subtitle}</p>
                                    <div className="mt-3 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                                        {c.difficulty} · {c.duration_hours}h · {c.category}
                                    </div>
                                </div>
                                {c.has_full_content && (
                                    <span className="badge-brand hidden md:inline-block shrink-0">Full content</span>
                                )}
                            </li>
                        ))}
                    </ol>
                </div>

                <aside className="lg:col-span-4 lg:sticky lg:top-24 lg:self-start">
                    <div className="card-flat p-7 space-y-5">
                        <div>
                            <div className="overline mb-2">Program</div>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Duration</div>
                                    <div className="font-serif text-lg flex items-center gap-1"><Clock className="w-4 h-4" />{path.estimated_weeks}w</div>
                                </div>
                                <div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Courses</div>
                                    <div className="font-serif text-lg">{path.courses?.length}</div>
                                </div>
                            </div>
                        </div>

                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Target credential</div>
                            <div className="font-serif text-lg flex items-center gap-2"><Award className="w-4 h-4 text-brand" />{path.target_credential}</div>
                        </div>

                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Best for</div>
                            <p className="text-sm text-muted-foreground leading-relaxed">{path.audience}</p>
                        </div>

                        <button
                            onClick={enroll}
                            disabled={enrolling}
                            data-testid="enroll-path"
                            className="btn-primary w-full"
                        >
                            {enrolling ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Enroll in track <ArrowRight className="w-4 h-4" /></>}
                        </button>

                        <p className="text-xs text-muted-foreground">
                            Enrolling enrolls you in every course in this track. Progress is tracked from your dashboard.
                        </p>
                    </div>
                </aside>
            </div>
        </div>
    );
}
