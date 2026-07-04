import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Compass, ArrowRight, Clock, Users, Award, Loader2 } from "lucide-react";

export default function Paths() {
    const [paths, setPaths] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get("/paths").then((r) => setPaths(r.data.paths || [])).finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;

    return (
        <div className="container-page py-16">
            <div className="max-w-3xl mb-14">
                <div className="overline mb-4 fine-rule pl-4">Role-based tracks</div>
                <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-6">
                    Start with your role.<br />Ship in your context.
                </h1>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    Seven curated tracks blend the ITHR credential ladder with role-specific outcomes.
                    Enroll once &mdash; you&apos;re on a sequenced program with mentor support, adaptive assessments, and a verifiable credential at the end.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-testid="paths-grid">
                {paths.map((p, i) => (
                    <Link
                        key={p.slug}
                        to={`/paths/${p.slug}`}
                        data-testid={`path-card-${p.slug}`}
                        className="card-flat p-8 group hover:border-brand transition-colors"
                    >
                        <div className="flex items-start justify-between mb-5">
                            <span className="badge-mono">{String(i + 1).padStart(2, "0")} · {p.role}</span>
                            <Compass className="w-5 h-5 text-brand" />
                        </div>
                        <h2 className="font-serif text-3xl tracking-tight leading-tight mb-3">{p.title}</h2>
                        <p className="text-sm text-muted-foreground leading-relaxed mb-6 line-clamp-2">{p.subtitle}</p>
                        <div className="grid grid-cols-3 gap-3 pt-5 border-t border-border text-[11px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                            <div><Clock className="w-3 h-3 inline mr-1" />{p.estimated_weeks}w</div>
                            <div><Users className="w-3 h-3 inline mr-1" />{p.course_count} courses</div>
                            <div className="text-brand"><Award className="w-3 h-3 inline mr-1" />Credential</div>
                        </div>
                        <div className="mt-5 flex items-center gap-2 text-xs text-brand font-mono uppercase tracking-[0.15em] opacity-0 group-hover:opacity-100 transition-opacity">
                            Explore track <ArrowRight className="w-3 h-3" />
                        </div>
                    </Link>
                ))}
            </div>
        </div>
    );
}
