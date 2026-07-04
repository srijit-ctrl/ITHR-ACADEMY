import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Award, ArrowRight } from "lucide-react";
import HeroBlobs from "@/components/HeroBlobs";

const TIER_COLORS = [
    "color-card-blue", "color-card-teal", "color-card-purple", "color-card-orange",
    "color-card-gold", "color-card-navy", "color-card-blue", "color-card-purple",
];

export default function Certifications() {
    const [paths, setPaths] = useState([]);
    useEffect(() => { api.get("/catalog/certification-paths").then((r) => setPaths(r.data.paths)); }, []);

    return (
        <div>
            {/* Hero — aiilm blob style */}
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="gold" />
                <div className="relative container-page py-20 md:py-24 text-center max-w-3xl mx-auto z-10">
                    <span className="section-kicker">Certification Ladder</span>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-6">
                        Eight tiers.<br />
                        One <span className="italic text-brand">global standard</span>.
                    </h1>
                    <p className="text-lg text-muted-foreground leading-relaxed">
                        Our certifications are the reference credential for agentic AI competence &mdash; recognized by hiring managers, procurement teams, and boards across 400+ enterprises.
                    </p>
                </div>
            </section>

            {/* Colored ladder cards */}
            <section className="container-page py-20">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {paths.map((p, i) => (
                        <div
                            key={p.slug}
                            className={`color-card ${TIER_COLORS[i % TIER_COLORS.length]}`}
                            data-testid={`cert-path-${p.slug}`}
                        >
                            <div className="color-card-kicker">
                                <Award className="w-3 h-3 inline mr-1" /> Tier {p.level}
                            </div>
                            <div className="font-serif text-3xl md:text-4xl tracking-tight mb-3 leading-none">
                                {p.title}
                            </div>
                            <p className="text-sm opacity-90 leading-relaxed flex-1">{p.description}</p>
                            <div className="mt-6">
                                <Link
                                    to="/courses"
                                    data-testid={`cert-explore-${p.slug}`}
                                    className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.2em] opacity-90 hover:opacity-100"
                                >
                                    View courses <ArrowRight className="w-3 h-3" />
                                </Link>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* Renewal callout */}
            <section className="section-warm-mint py-20">
                <div className="container-page text-center max-w-2xl mx-auto">
                    <span className="section-kicker">Renewal & CE</span>
                    <h2 className="font-serif text-3xl md:text-4xl tracking-tight mb-4">Credentials that stay current.</h2>
                    <p className="text-muted-foreground leading-relaxed">
                        Agentic AI moves fast. Every credential requires 20 CE credits every two years to remain active &mdash; earned through advanced modules, capstones, or verified enterprise projects.
                    </p>
                </div>
            </section>
        </div>
    );
}
