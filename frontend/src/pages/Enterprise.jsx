import { Link } from "react-router-dom";
import { Building2, Users, TrendingUp, ShieldCheck, Zap, Award, ArrowRight, Check } from "lucide-react";

const CAPABILITIES = [
    { icon: Users, title: "AI Skills Passport", desc: "A portable, verifiable record of AI competencies for every employee — accepted across the organization." },
    { icon: TrendingUp, title: "AI Readiness Index", desc: "Benchmark your workforce and every department against industry cohorts. Prioritize investment where ROI is highest." },
    { icon: Zap, title: "Role-Based Learning Paths", desc: "Curated tracks for HR, Finance, Sales, Procurement, Manufacturing — mapped to competency frameworks." },
    { icon: Award, title: "Manager Dashboards", desc: "Team-level analytics on progress, skill gaps, and certification status. Renewal credits keep credentials current." },
    { icon: Building2, title: "Enterprise Identity", desc: "SSO across Azure AD, Google Workspace, Okta. SCIM for automated provisioning. LDAP for hybrid deployments." },
    { icon: ShieldCheck, title: "Compliance-Ready", desc: "GDPR, SOC 2 Type II, ISO 27001, and FERPA aligned. Audit trails on every credential." },
];

const PLANS = [
    { name: "Team", seats: "Up to 100 seats", price: "Contact sales", features: ["Core learning + certification", "Enterprise SSO", "Team dashboards", "Standard support"] },
    { name: "Enterprise", seats: "100–5,000 seats", price: "Custom", featured: true, features: ["Everything in Team", "AI Readiness Index", "Skills Passport", "Role-based learning paths", "Manager analytics", "Priority support"] },
    { name: "Global", seats: "5,000+ seats", price: "Custom", features: ["Everything in Enterprise", "White-label branding", "Custom certification tracks", "Dedicated CSM", "SLA & premium support"] },
];

export default function Enterprise() {
    return (
        <div>
            {/* Hero */}
            <section className="border-b border-border">
                <div className="container-page py-20 md:py-28 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
                    <div className="lg:col-span-7">
                        <div className="overline mb-4 fine-rule pl-4">For Enterprise</div>
                        <h1 className="font-serif text-5xl md:text-7xl tracking-tighter leading-[1.02] mb-6">
                            From LMS to<br />
                            <span className="italic text-brand">workforce transformation.</span>
                        </h1>
                        <p className="text-lg md:text-xl text-muted-foreground leading-relaxed mb-8 max-w-2xl">
                            The Agentic AI Academy Enterprise Tier gives you more than courses. You get an organization-wide capability system — passports, readiness diagnostics, role-based paths, and dashboards that show where AI fluency sits in your business.
                        </p>
                        <div className="flex flex-col sm:flex-row gap-3">
                            <a href="mailto:enterprise@agenticai.academy" data-testid="enterprise-book-demo" className="btn-primary">Book a demo <ArrowRight className="w-4 h-4" /></a>
                            <Link to="/courses" data-testid="enterprise-see-catalog" className="btn-outline">See the catalog</Link>
                        </div>
                    </div>
                    <div className="lg:col-span-5">
                        <div className="card-flat p-8 space-y-4">
                            <div className="overline">Trusted by</div>
                            <div className="font-serif text-4xl leading-none">400+ Enterprises</div>
                            <div className="h-px bg-border" />
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                <div><div className="font-serif text-3xl text-brand">2.3×</div><div className="text-muted-foreground">Higher AI ROI</div></div>
                                <div><div className="font-serif text-3xl text-brand">68%</div><div className="text-muted-foreground">Faster upskilling</div></div>
                                <div><div className="font-serif text-3xl text-brand">128k</div><div className="text-muted-foreground">Certified in 2026</div></div>
                                <div><div className="font-serif text-3xl text-brand">99.9%</div><div className="text-muted-foreground">Platform SLA</div></div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Capabilities */}
            <section className="container-page py-24">
                <div className="max-w-2xl mb-16">
                    <div className="overline mb-4 fine-rule pl-4">Layer II — Premium Tier</div>
                    <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight">
                        Six capabilities beyond the LMS.
                    </h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {CAPABILITIES.map((c) => (
                        <div key={c.title} className="card-flat p-8" data-testid={`capability-${c.title.toLowerCase().replace(/\s+/g, "-")}`}>
                            <c.icon className="w-6 h-6 text-brand mb-5" />
                            <div className="font-serif text-xl leading-tight mb-3">{c.title}</div>
                            <p className="text-sm text-muted-foreground leading-relaxed">{c.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Pricing */}
            <section className="border-t border-border bg-surface-alt/40 py-24">
                <div className="container-page">
                    <div className="text-center max-w-2xl mx-auto mb-14">
                        <div className="overline mb-4">Enterprise Plans</div>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight">
                            Priced by seats. Delivered as outcomes.
                        </h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                        {PLANS.map((p) => (
                            <div
                                key={p.name}
                                className={`card-flat p-8 relative ${p.featured ? "border-brand border-2" : ""}`}
                                data-testid={`plan-${p.name.toLowerCase()}`}
                            >
                                {p.featured && <div className="absolute -top-3 left-8 badge-crimson bg-background">Most popular</div>}
                                <div className="font-serif text-3xl leading-none mb-1">{p.name}</div>
                                <div className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mb-6">{p.seats}</div>
                                <div className="text-2xl mb-6">{p.price}</div>
                                <ul className="space-y-2 text-sm mb-8">
                                    {p.features.map((f) => (
                                        <li key={f} className="flex gap-2"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" />{f}</li>
                                    ))}
                                </ul>
                                <a href="mailto:enterprise@agenticai.academy" className={p.featured ? "btn-primary w-full" : "btn-outline w-full"}>Contact sales</a>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    );
}
