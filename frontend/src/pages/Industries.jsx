import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ArrowRight } from "lucide-react";

const INDUSTRY_META = {
    "Manufacturing": { hero: "https://images.unsplash.com/photo-1565043666747-69f6646db940?w=1200&q=80", tagline: "Predictive maintenance, digital twins, and autonomous quality." },
    "Healthcare": { hero: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1200&q=80", tagline: "HIPAA-safe clinical agents, from intake to discharge." },
    "Banking": { hero: "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&q=80", tagline: "From claims processing to fair-lending compliance." },
    "Insurance": { hero: "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=1200&q=80", tagline: "Underwriting agents and end-to-end claims automation." },
    "Retail": { hero: "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200&q=80", tagline: "Personalization, dynamic pricing, supply chain intelligence." },
    "Logistics": { hero: "https://images.unsplash.com/photo-1494412574745-eafd6de2edaf?w=1200&q=80", tagline: "Route optimization and exception handling at scale." },
    "Government": { hero: "https://images.unsplash.com/photo-1526661934280-676cef25bc9b?w=1200&q=80", tagline: "FedRAMP-ready, sovereign, and mission-focused." },
    "Education": { hero: "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=1200&q=80", tagline: "AI tutors and adaptive learning platforms." },
};

export default function Industries() {
    const [industries, setIndustries] = useState([]);
    useEffect(() => { api.get("/catalog/industries").then((r) => setIndustries(r.data.industries)); }, []);

    return (
        <div className="container-page py-16">
            <div className="mb-16 max-w-3xl">
                <div className="overline mb-4 fine-rule pl-4">Industry Tracks</div>
                <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-5">
                    Curriculum built for<br />
                    <span className="italic text-brand">your industry.</span>
                </h1>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    Every industry has its own agentic AI patterns, regulations, and case studies. Choose a track curated by domain experts and enterprise practitioners.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {industries.map((ind, i) => {
                    const meta = INDUSTRY_META[ind] || {};
                    return (
                        <Link
                            key={ind}
                            to={`/courses?industry=${encodeURIComponent(ind)}`}
                            data-testid={`industry-card-${ind.toLowerCase().replace(/\s+/g, "-").replace(/&/g, "and")}`}
                            className="card-sharp overflow-hidden flex flex-col"
                        >
                            <div className="aspect-[16/10] relative bg-surface-alt overflow-hidden">
                                {meta.hero && <img src={meta.hero} alt="" className="w-full h-full object-cover" />}
                                <div className="absolute inset-0 bg-foreground/50" />
                                <div className="absolute inset-0 p-6 flex flex-col justify-end">
                                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/80 mb-2">Track · {String(i + 1).padStart(2, "0")}</div>
                                    <div className="font-serif text-3xl text-white leading-none">{ind}</div>
                                </div>
                            </div>
                            <div className="p-6 flex-1 flex flex-col">
                                <p className="text-sm text-muted-foreground mb-4 flex-1">
                                    {meta.tagline || `Specialized agentic AI curriculum for ${ind} — case studies, workflows, and capstone projects.`}
                                </p>
                                <div className="text-sm text-brand font-medium inline-flex items-center gap-1">
                                    Explore courses <ArrowRight className="w-4 h-4" />
                                </div>
                            </div>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
