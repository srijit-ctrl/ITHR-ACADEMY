import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Award, ArrowRight } from "lucide-react";

export default function Certifications() {
    const [paths, setPaths] = useState([]);
    useEffect(() => { api.get("/catalog/certification-paths").then((r) => setPaths(r.data.paths)); }, []);

    return (
        <div className="container-page py-16">
            <div className="max-w-3xl mb-16">
                <div className="overline mb-4 fine-rule pl-4">Certification Ladder</div>
                <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-5">
                    Eight tiers. One global standard.
                </h1>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    Our certifications are the reference credential for agentic AI competence — recognized by hiring managers, procurement teams, and boards across 400+ enterprises.
                </p>
            </div>

            <div className="space-y-2">
                {paths.map((p, i) => (
                    <div key={p.slug} className="card-flat p-8 group hover:border-brand transition-colors" data-testid={`cert-path-${p.slug}`}>
                        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
                            <div className="md:col-span-2 flex items-baseline gap-3">
                                <Award className="w-6 h-6 text-brand" />
                                <span className="font-serif text-5xl text-brand leading-none">{["I","II","III","IV","V","VI","VII","VIII"][i]}</span>
                            </div>
                            <div className="md:col-span-7">
                                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-2">Tier {p.level}</div>
                                <div className="font-serif text-2xl tracking-tight mb-2">{p.title}</div>
                                <p className="text-sm text-muted-foreground leading-relaxed">{p.description}</p>
                            </div>
                            <div className="md:col-span-3 text-right">
                                <Link to="/courses" data-testid={`cert-explore-${p.slug}`} className="text-sm text-brand hover:underline inline-flex items-center gap-1">
                                    View courses <ArrowRight className="w-4 h-4" />
                                </Link>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="mt-20 text-center max-w-2xl mx-auto">
                <div className="overline mb-4">Renewal & Continuing Education</div>
                <h2 className="font-serif text-3xl md:text-4xl tracking-tight mb-4">Credentials that stay current.</h2>
                <p className="text-muted-foreground leading-relaxed">
                    Agentic AI moves fast. Every credential requires 20 CE credits every two years to remain active — earned through advanced modules, capstones, or verified enterprise projects.
                </p>
            </div>
        </div>
    );
}
