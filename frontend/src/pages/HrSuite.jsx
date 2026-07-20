import { Link } from "react-router-dom";
import { useState } from "react";
import { ArrowRight, Check, Sparkles, Users, Layers, BookOpen, Workflow, Building2 } from "lucide-react";
import HeroBlobs from "@/components/HeroBlobs";
import EnterpriseLeadModal from "@/components/enterprise/EnterpriseLeadModal";

/**
 * /hr-suite — Dedicated marketing + pricing page for the HR Transformation
 * portfolio. Separates two purchase paths from the generic /pricing page:
 *
 *   1. TALENT OPS BUNDLE (flagship)  — a curated 4-course + Copilot bundle
 *      for HR/People-Ops teams at a flat annual price. High conversion,
 *      easy to buy.
 *
 *   2. HR TRANSFORMATION STACK (ladder) — 3 tiers (Starter / Growth /
 *      Enterprise-HR) sized by seat count, each stacking additional Aletheia
 *      workflows. Sales-led ("Request a quote"), no Stripe.
 *
 * All CTAs funnel to /enterprise (existing intake form) with a query param
 * indicating which bundle/tier so the sales team knows the intent.
 */

const TALENT_OPS_COURSES = [
    { slug: "talent-acquisition-agentic-ai", title: "Talent Acquisition Agentic AI", modules: 15 },
    { slug: "compensation-analytics-ai", title: "Compensation Analytics AI", modules: 15 },
    { slug: "performance-enablement-ai", title: "Performance Enablement AI", modules: 15 },
    { slug: "hr-copilot-blueprint", title: "HR Copilot Blueprint", modules: 15 },
];

const HR_TIERS = [
    {
        name: "Starter",
        seats: "Up to 25 seats",
        seatCount: 25,
        price: "$14,900",
        period: "annual",
        best: false,
        description: "Bring HR into the agentic era. Perfect for HRBP pods running their first AI pilot.",
        includes: [
            "2 flagship HR courses (of your choice)",
            "Aletheia AI Tutor · unlimited",
            "Cohort dashboard + progress reports",
            "Public credential verification",
            "Email support",
        ],
        aletheia: [
            "Job-description drafting workflow",
            "Compensation benchmarking workflow",
        ],
        testId: "hr-tier-starter",
        contactRef: "hr-starter",
    },
    {
        name: "Growth",
        seats: "Up to 100 seats",
        seatCount: 100,
        price: "$39,900",
        period: "annual",
        best: true,
        description: "For HR leaders transforming the full talent lifecycle across a mid-size org.",
        includes: [
            "Full Talent Ops Bundle (4 flagship HR courses)",
            "All HR-specialised modules included",
            "Aletheia AI Tutor · unlimited",
            "Enterprise Passport (skills graph)",
            "Success manager · quarterly business reviews",
            "SAML SSO",
        ],
        aletheia: [
            "Talent Acquisition Copilot",
            "Compensation & pay-equity analytics",
            "Performance-review coach",
            "Onboarding orchestration workflow",
        ],
        testId: "hr-tier-growth",
        contactRef: "hr-growth",
    },
    {
        name: "Enterprise-HR",
        seats: "500+ seats · unlimited",
        seatCount: null,
        price: "Custom",
        period: "annual",
        best: false,
        description: "For CHROs building an AI-native people function across regions and business units.",
        includes: [
            "Everything in Growth",
            "Bespoke curriculum authored with your L&D team",
            "Private LLM / VPC deployment options",
            "HRIS integrations (Workday / SuccessFactors / SAP)",
            "White-label credential issuance",
            "Dedicated CSM + 24×7 support",
            "SOC 2 audit access + custom DPAs",
        ],
        aletheia: [
            "All Growth workflows",
            "Custom Aletheia workflows authored by ITHR",
            "API access to Aletheia agent runtime",
        ],
        testId: "hr-tier-enterprise",
        contactRef: "hr-enterprise",
    },
];

export default function HrSuite() {
    const [leadOpen, setLeadOpen] = useState(false);
    const [leadBundle, setLeadBundle] = useState("generic");
    const openLead = (ref) => {
        setLeadBundle(ref || "generic");
        setLeadOpen(true);
    };

    return (
        <div data-testid="hr-suite-page">
            <EnterpriseLeadModal
                open={leadOpen}
                onClose={() => setLeadOpen(false)}
                bundle={leadBundle}
                sourceUrl={typeof window !== "undefined" ? window.location.href : "/hr-suite"}
            />
            {/* Hero */}
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="cool" />
                <div className="relative container-page py-20 md:py-24 text-center max-w-3xl mx-auto z-10">
                    <span className="section-kicker">HR Transformation Suite</span>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-6">
                        Turn your HR function into an <span className="italic text-brand">AI-native</span> one.
                    </h1>
                    <p className="text-lg text-muted-foreground leading-relaxed">
                        Four flagship HR courses. Aletheia workflows for the messy stuff — job descriptions, comp bands, performance reviews, onboarding. Delivered as one annual programme for your people team.
                    </p>
                </div>
            </section>

            {/* Talent Ops Bundle — Flagship */}
            <section className="container-page py-16">
                <div className="flex items-center gap-3 mb-8">
                    <Sparkles className="w-5 h-5 text-brand" />
                    <div>
                        <div className="overline">Flagship bundle</div>
                        <h2 className="font-serif text-3xl tracking-tight mt-1">The Talent Ops Bundle</h2>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 items-stretch">
                    {/* Left — pitch + price */}
                    <div className="lg:col-span-2 card-flat p-8 border-brand border-2 flex flex-col relative" data-testid="talent-ops-bundle-card">
                        <div className="absolute -top-3 left-8 badge-brand bg-background">Most-picked bundle</div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-4">50 seats · 12 months</div>
                        <div className="font-serif text-4xl leading-none mb-3">Talent Ops Bundle</div>
                        <p className="text-sm text-muted-foreground mb-6">Everything an HR/People-Ops team needs to ship agentic AI across the talent lifecycle — in one annual package.</p>
                        <div className="mb-2">
                            <span className="font-serif text-5xl">$24,900</span>
                            <span className="text-muted-foreground text-sm ml-2">/ year · flat</span>
                        </div>
                        <div className="text-xs text-muted-foreground mb-6">≈ $498 / seat / year — no per-seat maths, no surprises.</div>
                        <button
                            type="button"
                            onClick={() => openLead("talent-ops-bundle")}
                            data-testid="talent-ops-cta"
                            className="btn-primary w-full justify-center mb-3"
                        >
                            Reserve the bundle <ArrowRight className="w-4 h-4" />
                        </button>
                        <Link
                            to="/verify"
                            className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-brand text-center"
                        >
                            Or verify a credential first
                        </Link>
                    </div>

                    {/* Right — what's inside */}
                    <div className="lg:col-span-3 card-flat p-8">
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3 flex items-center gap-1.5">
                            <BookOpen className="w-3.5 h-3.5" /> Four flagship HR courses
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
                            {TALENT_OPS_COURSES.map((c) => (
                                <Link
                                    key={c.slug}
                                    to={`/courses/${c.slug}`}
                                    className="card-sharp p-4 hover:border-brand transition-colors block"
                                    data-testid={`talent-ops-course-${c.slug}`}
                                >
                                    <div className="font-serif text-lg leading-tight">{c.title}</div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-2">{c.modules} modules · Aletheia included</div>
                                </Link>
                            ))}
                        </div>

                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3 flex items-center gap-1.5">
                            <Workflow className="w-3.5 h-3.5" /> Aletheia HR workflows unlocked
                        </div>
                        <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                            {[
                                "Job description generator",
                                "Compensation benchmarking",
                                "Performance-review coach",
                                "Onboarding orchestration",
                                "Interview scorecard drafter",
                                "Skills-graph mapping (Passport)",
                            ].map((it) => (
                                <li key={it} className="flex items-start gap-2">
                                    <Check className="w-4 h-4 text-brand shrink-0 mt-0.5" />
                                    <span>{it}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            </section>

            {/* HR Transformation Stack (3-tier) */}
            <section className="container-page py-16">
                <div className="flex items-center gap-3 mb-8">
                    <Layers className="w-5 h-5 text-brand" />
                    <div>
                        <div className="overline">HR Transformation Stack</div>
                        <h2 className="font-serif text-3xl tracking-tight mt-1">Choose a tier that fits your org.</h2>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {HR_TIERS.map((t) => (
                        <div
                            key={t.name}
                            data-testid={t.testId}
                            className={`card-flat p-8 relative flex flex-col ${t.best ? "border-brand border-2 md:-my-2 md:py-10" : ""}`}
                        >
                            {t.best && <div className="absolute -top-3 left-8 badge-brand bg-background">Recommended</div>}
                            <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">
                                <Users className="w-3 h-3" /> {t.seats}
                            </div>
                            <div className="font-serif text-3xl leading-none mb-2">{t.name}</div>
                            <p className="text-sm text-muted-foreground mb-6">{t.description}</p>
                            <div className="mb-6">
                                <span className="font-serif text-4xl">{t.price}</span>
                                <span className="text-muted-foreground text-sm ml-2">/ {t.period}</span>
                            </div>

                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2">Learning</div>
                            <ul className="mb-5 space-y-1.5 text-sm">
                                {t.includes.map((f) => (
                                    <li key={f} className="flex items-start gap-2">
                                        <Check className="w-4 h-4 text-brand shrink-0 mt-0.5" />
                                        <span>{f}</span>
                                    </li>
                                ))}
                            </ul>

                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2 flex items-center gap-1"><Workflow className="w-3 h-3" /> Aletheia workflows</div>
                            <ul className="mb-8 space-y-1.5 text-sm">
                                {t.aletheia.map((w) => (
                                    <li key={w} className="flex items-start gap-2">
                                        <Sparkles className="w-3.5 h-3.5 text-brand shrink-0 mt-1" />
                                        <span>{w}</span>
                                    </li>
                                ))}
                            </ul>

                            <button
                                type="button"
                                onClick={() => openLead(t.contactRef)}
                                data-testid={`${t.testId}-cta`}
                                className={`w-full justify-center inline-flex items-center gap-2 py-2.5 px-4 rounded-sm text-sm font-medium transition-colors mt-auto ${t.best ? "btn-primary" : "border border-border bg-surface-alt hover:border-brand hover:text-brand"}`}
                            >
                                {t.price === "Custom" ? "Design my programme" : "Request a quote"}
                                <ArrowRight className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            </section>

            {/* Enterprise CTA row */}
            <section className="container-page py-16">
                <div className="card-flat p-10 md:p-14 text-center" data-testid="hr-suite-final-cta">
                    <Building2 className="w-8 h-8 text-brand mx-auto mb-4" />
                    <h3 className="font-serif text-3xl md:text-4xl leading-tight mb-3">Not sure which fits?</h3>
                    <p className="text-muted-foreground max-w-2xl mx-auto mb-6">Talk to our team for a 20-minute HR AI readiness call. We&apos;ll map your headcount, current stack, and target outcomes to the right bundle — no obligation.</p>
                    <button
                        type="button"
                        onClick={() => openLead("hr-consult")}
                        data-testid="hr-suite-consult-cta"
                        className="btn-primary inline-flex"
                    >
                        Book a readiness call <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            </section>
        </div>
    );
}
