import { Link, useSearchParams } from "react-router-dom";
import { useMemo, useState } from "react";
import { Building2, Users, TrendingUp, ShieldCheck, Zap, Award, ArrowRight, Check } from "lucide-react";
import HeroBlobs from "@/components/HeroBlobs";
import EnterpriseLeadModal, { EnterpriseLeadForm } from "@/components/enterprise/EnterpriseLeadModal";

const CAPABILITIES = [
    { icon: Users, title: "AI Skills Passport", desc: "A portable, verifiable record of AI competencies for every employee — accepted across the organization." },
    { icon: TrendingUp, title: "AI Readiness Index", desc: "Benchmark your workforce and every department against industry cohorts. Prioritize investment where ROI is highest." },
    { icon: Zap, title: "Role-Based Learning Paths", desc: "Curated tracks for HR, Finance, Sales, Procurement, Manufacturing — mapped to competency frameworks." },
    { icon: Award, title: "Manager Dashboards", desc: "Team-level analytics on progress, skill gaps, and certification status. Renewal credits keep credentials current." },
    { icon: Building2, title: "Enterprise Identity", desc: "SSO across Azure AD, Google Workspace, Okta. SCIM for automated provisioning. LDAP for hybrid deployments." },
    { icon: ShieldCheck, title: "Compliance-Ready", desc: "Designed to align with GDPR, SOC 2, ISO 27001, and FERPA controls. Audit trails on every credential. Current attestation status is published on our Trust page." },
];

const PLANS = [
    { name: "Team", seats: "Up to 100 seats", price: "Contact sales", features: ["Core learning + certification", "Enterprise SSO", "Team dashboards", "Standard support"] },
    { name: "Enterprise", seats: "100–5,000 seats", price: "Custom", featured: true, features: ["Everything in Team", "AI Readiness Index", "Skills Passport", "Role-based learning paths", "Manager analytics", "Priority support"] },
    { name: "Global", seats: "5,000+ seats", price: "Custom", features: ["Everything in Enterprise", "White-label branding", "Custom certification tracks", "Dedicated CSM", "SLA & premium support"] },
];

export default function Enterprise() {
    const [params] = useSearchParams();
    const initialBundle = useMemo(() => (params.get("bundle") || "generic"), [params]);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalBundle, setModalBundle] = useState(initialBundle);
    const openLead = (ref) => {
        setModalBundle(ref || "generic");
        setModalOpen(true);
    };

    return (
        <div>
            <EnterpriseLeadModal
                open={modalOpen}
                onClose={() => setModalOpen(false)}
                bundle={modalBundle}
                sourceUrl={typeof window !== "undefined" ? window.location.href : "/enterprise"}
            />
            {/* Hero — aiilm blob style */}
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="warm" />
                <div className="relative container-page py-20 md:py-28 z-10">
                    <div className="max-w-4xl mx-auto text-center">
                        <span className="section-kicker">For Enterprise</span>
                        <h1 className="font-serif text-5xl md:text-7xl tracking-tighter leading-[1.02] mb-6">
                            From LMS to <span className="italic text-brand">workforce transformation.</span>
                        </h1>
                        <p className="text-lg md:text-xl text-muted-foreground leading-relaxed mb-10 max-w-2xl mx-auto">
                            The ITHR Academy Enterprise Tier gives you more than courses. You get an organization-wide capability system &mdash; passports, readiness diagnostics, role-based paths, and dashboards that show where AI fluency sits in your business.
                        </p>
                        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-14">
                            <button
                                type="button"
                                onClick={() => openLead(initialBundle)}
                                data-testid="enterprise-book-demo"
                                className="btn-primary"
                            >
                                Book a demo <ArrowRight className="w-4 h-4" />
                            </button>
                            <Link to="/courses" data-testid="enterprise-see-catalog" className="btn-outline">See the catalog</Link>
                        </div>

                        {/* Stat pips */}
                        <div className="flex flex-wrap justify-center gap-x-14 gap-y-6 pt-8 border-t border-border">
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none text-brand">15</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Modules per track</div>
                            </div>
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none text-brand">3</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Difficulty levels</div>
                            </div>
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none text-brand">24</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Courses in catalog</div>
                            </div>
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none text-brand">100%</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Publicly verifiable</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Capabilities */}
            <section className="container-page py-24">
                <div className="text-center max-w-2xl mx-auto mb-16">
                    <span className="section-kicker">Layer II · Premium</span>
                    <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight">
                        Six capabilities beyond the LMS.
                    </h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {CAPABILITIES.map((c) => (
                        <div key={c.title} className="step-card" data-testid={`capability-${c.title.toLowerCase().replace(/\s+/g, "-")}`}>
                            <c.icon className="w-6 h-6 text-brand mb-5" />
                            <div className="font-serif text-xl leading-tight mb-3">{c.title}</div>
                            <p className="text-sm text-muted-foreground leading-relaxed">{c.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Pricing — colored blocks */}
            <section className="section-warm-mint py-24">
                <div className="container-page">
                    <div className="text-center max-w-2xl mx-auto mb-14">
                        <span className="section-kicker">Enterprise Plans</span>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight">
                            Priced by seats. Delivered as outcomes.
                        </h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                        {PLANS.map((p, i) => (
                            <div
                                key={p.name}
                                className={`color-card ${["color-card-blue", "color-card-purple", "color-card-navy"][i]}`}
                                data-testid={`plan-${p.name.toLowerCase()}`}
                            >
                                <div className="color-card-kicker">{p.seats}</div>
                                <div className="font-serif text-3xl md:text-4xl tracking-tight mb-2 leading-none">{p.name}</div>
                                <div className="text-lg opacity-80 mb-5">{p.price}</div>
                                <ul className="space-y-2 text-sm mb-6 flex-1 opacity-95">
                                    {p.features.map((f) => (
                                        <li key={f} className="flex gap-2"><Check className="w-4 h-4 mt-0.5 shrink-0 opacity-80" />{f}</li>
                                    ))}
                                </ul>
                                <button
                                    type="button"
                                    onClick={() => openLead("generic")}
                                    data-testid={`plan-${p.name.toLowerCase()}-cta`}
                                    className="inline-flex items-center gap-1.5 rounded-full px-5 py-2 bg-white/20 backdrop-blur hover:bg-white/30 text-sm font-semibold transition-colors self-start"
                                >
                                    Contact sales <ArrowRight className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Inline lead form — deep-linked from /hr-suite?bundle= */}
            <section className="container-page py-24" data-testid="enterprise-inline-lead">
                <div className="max-w-3xl mx-auto">
                    <div className="text-center mb-10">
                        <span className="section-kicker">Talk to us</span>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight">
                            Tell us what you&rsquo;re <span className="italic text-brand">building.</span>
                        </h2>
                        <p className="text-muted-foreground mt-4 max-w-xl mx-auto">
                            Send us a note. Someone from the ITHR Academy team replies inside one working day. No auto-responder loop, no drip-marketing follow-ups — just a real conversation.
                        </p>
                    </div>
                    <div className="card-flat p-8">
                        <EnterpriseLeadForm bundle={initialBundle} sourceUrl={typeof window !== "undefined" ? window.location.href : "/enterprise"} />
                    </div>
                </div>
            </section>
        </div>
    );
}
