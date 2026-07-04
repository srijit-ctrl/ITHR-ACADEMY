import { Link } from "react-router-dom";
import { Check, ArrowRight, Building2, Users, User } from "lucide-react";

const INDIVIDUAL = [
    {
        name: "Explorer",
        price: "Free",
        period: "forever",
        description: "For learners exploring agentic AI.",
        features: [
            "Modules 1–5 of every course",
            "Aletheia AI Tutor (20 messages/mo)",
            "Public certificate verification",
            "Community access",
        ],
        cta: "Start free",
        ctaHref: "/register",
        testId: "plan-explorer",
    },
    {
        name: "Practitioner",
        price: "$29",
        period: "/month",
        annual: "or $290/year — save $58",
        description: "For working professionals earning credentials.",
        featured: true,
        features: [
            "All courses, all modules (1–15)",
            "Unlimited Aletheia AI Tutor",
            "All Foundation & Practitioner certifications",
            "Downloadable digital badges",
            "Priority email support",
        ],
        cta: "Start 7-day trial",
        ctaHref: "/register",
        testId: "plan-practitioner",
    },
    {
        name: "Professional Track",
        price: "$499",
        period: "one-time",
        description: "For senior technologists pursuing advanced certifications.",
        features: [
            "Everything in Practitioner (12 mo)",
            "Advanced + Architect certifications",
            "Live capstone review by ITHR faculty",
            "AI Career Advisor sessions",
            "Alumni network access",
        ],
        cta: "Enroll",
        ctaHref: "/register",
        testId: "plan-professional",
    },
];

const ENTERPRISE = [
    {
        name: "Team",
        seats: "10 – 100 seats",
        price: "$18",
        period: "/seat/month",
        description: "For departments piloting agentic AI upskilling.",
        features: [
            "Full catalog access",
            "Basic team dashboard",
            "SSO (Google, Microsoft)",
            "Quarterly business reviews",
            "Standard support (48h SLA)",
        ],
        testId: "plan-team",
    },
    {
        name: "Enterprise",
        seats: "100 – 5,000 seats",
        price: "Contact",
        period: "sales",
        featured: true,
        description: "For organizations formalizing an AI competency function.",
        features: [
            "Everything in Team",
            "AI Skills Passport for every employee",
            "Enterprise AI Readiness Index",
            "Departmental maturity dashboards",
            "Role-based learning paths (HR, Finance, Sales, Ops)",
            "Real-time Course Intelligence updates",
            "Full SSO/SCIM/LDAP",
            "Priority support (8h SLA)",
        ],
        testId: "plan-enterprise",
    },
    {
        name: "Global",
        seats: "5,000+ seats",
        price: "Custom",
        period: "engagement",
        description: "For Fortune 500 workforce-scale transformation.",
        features: [
            "Everything in Enterprise",
            "White-label branding on the portal",
            "Bespoke certification tracks",
            "Dedicated ITHR Customer Success",
            "24×7 support + 99.99% SLA",
            "On-site executive briefings",
            "Custom integrations & API tier",
        ],
        testId: "plan-global",
    },
];

export default function Pricing() {
    return (
        <div>
            {/* Hero */}
            <section className="border-b border-border">
                <div className="container-page py-20 md:py-24 text-center max-w-3xl mx-auto">
                    <div className="overline mb-4">Pricing</div>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-5">
                        Pricing that <span className="italic text-brand">scales</span> with your ambition.
                    </h1>
                    <p className="text-lg text-muted-foreground leading-relaxed">
                        Free for exploration. Fair for professionals. Bespoke for enterprises. Every plan includes ITHR's real-time curriculum intelligence — courses that refresh as the field moves.
                    </p>
                </div>
            </section>

            {/* Individual */}
            <section className="container-page py-20">
                <div className="flex items-center gap-3 mb-10">
                    <User className="w-5 h-5 text-brand" />
                    <div>
                        <div className="overline">For Individuals</div>
                        <h2 className="font-serif text-3xl tracking-tight mt-1">Learners & Professionals</h2>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {INDIVIDUAL.map((p) => (
                        <div
                            key={p.name}
                            data-testid={p.testId}
                            className={`card-flat p-8 relative flex flex-col ${p.featured ? "border-brand border-2 md:-my-2 md:py-10" : ""}`}
                        >
                            {p.featured && <div className="absolute -top-3 left-8 badge-crimson bg-background">Most popular</div>}
                            <div className="font-serif text-3xl leading-none mb-2">{p.name}</div>
                            <p className="text-sm text-muted-foreground mb-6">{p.description}</p>
                            <div className="mb-2">
                                <span className="font-serif text-5xl">{p.price}</span>
                                <span className="text-muted-foreground text-sm ml-2">{p.period}</span>
                            </div>
                            {p.annual && <div className="text-xs text-brand font-mono uppercase tracking-[0.15em] mb-6">{p.annual}</div>}
                            {!p.annual && <div className="mb-6" />}

                            <ul className="space-y-2 text-sm mb-8 flex-1">
                                {p.features.map((f) => (
                                    <li key={f} className="flex gap-2"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" />{f}</li>
                                ))}
                            </ul>

                            <Link to={p.ctaHref} data-testid={`${p.testId}-cta`} className={p.featured ? "btn-primary w-full" : "btn-outline w-full"}>
                                {p.cta} <ArrowRight className="w-4 h-4" />
                            </Link>
                        </div>
                    ))}
                </div>
            </section>

            {/* Enterprise */}
            <section className="border-t border-border bg-surface-alt/50 py-20">
                <div className="container-page">
                    <div className="flex items-center gap-3 mb-10">
                        <Building2 className="w-5 h-5 text-brand" />
                        <div>
                            <div className="overline">For Organizations</div>
                            <h2 className="font-serif text-3xl tracking-tight mt-1">Enterprise Plans</h2>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {ENTERPRISE.map((p) => (
                            <div
                                key={p.name}
                                data-testid={p.testId}
                                className={`card-flat p-8 relative flex flex-col ${p.featured ? "border-brand border-2" : ""}`}
                            >
                                {p.featured && <div className="absolute -top-3 left-8 badge-crimson bg-background">Recommended</div>}
                                <div className="font-serif text-3xl leading-none mb-1">{p.name}</div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-4">{p.seats}</div>
                                <p className="text-sm text-muted-foreground mb-6">{p.description}</p>
                                <div className="mb-6">
                                    <span className="font-serif text-4xl">{p.price}</span>
                                    <span className="text-muted-foreground text-sm ml-2">{p.period}</span>
                                </div>

                                <ul className="space-y-2 text-sm mb-8 flex-1">
                                    {p.features.map((f) => (
                                        <li key={f} className="flex gap-2"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" />{f}</li>
                                    ))}
                                </ul>

                                <a href="mailto:enterprise@ithr.tech" data-testid={`${p.testId}-cta`} className={p.featured ? "btn-primary w-full" : "btn-outline w-full"}>
                                    Contact ITHR <ArrowRight className="w-4 h-4" />
                                </a>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Real-time Intelligence value prop */}
            <section className="container-page py-20">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
                    <div className="lg:col-span-6">
                        <div className="overline mb-4 fine-rule pl-4">Every plan includes</div>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight mb-6">
                            Real-time Course<br />
                            <span className="italic text-brand">Intelligence.</span>
                        </h2>
                        <p className="text-lg text-muted-foreground leading-relaxed mb-6">
                            Agentic AI moves weekly. Every ITHR course carries a live freshness score and is monitored by our AI Intelligence Desk — a Claude-powered agent that scans model releases, regulation, and enterprise deployments to keep your curriculum current.
                        </p>
                        <ul className="space-y-3 mb-8">
                            <li className="flex gap-3 text-sm"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span><b>6-hour signal briefings</b> — auto-generated intelligence on the industry.</span></li>
                            <li className="flex gap-3 text-sm"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span><b>Course freshness scores</b> — every course rated for currency, monthly.</span></li>
                            <li className="flex gap-3 text-sm"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" /><span><b>AI-suggested lesson updates</b> — Aletheia proposes new modules as the field evolves.</span></li>
                        </ul>
                        <Link to="/intelligence" data-testid="pricing-see-intelligence" className="btn-primary">
                            See today's briefing <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                    <div className="lg:col-span-6">
                        <div className="card-flat p-8 space-y-4 bg-foreground text-background">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-brand rounded-full animate-pulse" />
                                <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand">Live · ITHR Intelligence Desk</span>
                            </div>
                            <div className="font-serif text-2xl leading-tight">Anthropic ships MCP 2.0 with signed capability manifests</div>
                            <div className="text-sm opacity-80">Recommendation: Refresh Module 3 ("The Agent Development Stack") within 30 days. Update MCP tool-signature lessons.</div>
                            <div className="flex items-center gap-3 text-[10px] font-mono uppercase tracking-[0.15em] opacity-60">
                                <span>Impact: High</span><span>·</span><span>Category: Framework</span><span>·</span><span>Generated 2h ago</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* FAQ / Trust */}
            <section className="border-t border-border py-20">
                <div className="container-page grid grid-cols-1 md:grid-cols-3 gap-10">
                    <div>
                        <div className="overline mb-3">Guarantee</div>
                        <h3 className="font-serif text-xl mb-2">14-day money-back</h3>
                        <p className="text-sm text-muted-foreground">Not sure? Try any paid plan risk-free for 14 days.</p>
                    </div>
                    <div>
                        <div className="overline mb-3">Volume Discounts</div>
                        <h3 className="font-serif text-xl mb-2">Save with scale</h3>
                        <p className="text-sm text-muted-foreground">Automatic pricing tiers at 250, 1,000, and 2,500+ seats.</p>
                    </div>
                    <div>
                        <div className="overline mb-3">Procurement</div>
                        <h3 className="font-serif text-xl mb-2">Invoice + PO</h3>
                        <p className="text-sm text-muted-foreground">Net-30 invoicing available for all Enterprise plans.</p>
                    </div>
                </div>
            </section>
        </div>
    );
}
