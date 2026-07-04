import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Check, ArrowRight, Building2, User, Loader2 } from "lucide-react";
import HeroBlobs from "@/components/HeroBlobs";

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
        packageId: null,
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
        cta: "Subscribe monthly",
        packageId: "practitioner_monthly",
        secondaryCta: "Save 17% — pay annual",
        secondaryPackageId: "practitioner_annual",
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
        cta: "Enroll for $499",
        packageId: "professional_track",
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
        packageId: "team_monthly_per_seat",
        variableQuantity: true,
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
        contact: true,
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
        contact: true,
    },
];

export default function Pricing() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [processingId, setProcessingId] = useState(null);
    const [teamSeats, setTeamSeats] = useState(25);
    const [error, setError] = useState("");

    const handleCheckout = async (packageId, quantity = 1) => {
        setError("");
        if (!user) {
            navigate("/login", { state: { from: "/pricing" } });
            return;
        }
        if (!packageId) {
            navigate("/register");
            return;
        }
        setProcessingId(packageId);
        try {
            const res = await api.post("/checkout/session", {
                package_id: packageId,
                origin_url: window.location.origin,
                quantity,
            });
            if (res.data.url) {
                window.location.href = res.data.url;
            } else {
                setError("No checkout URL returned");
                setProcessingId(null);
            }
        } catch (e) {
            setError(e.response?.data?.detail || "Checkout failed. Please try again.");
            setProcessingId(null);
        }
    };

    return (
        <div>
            {/* Hero — aiilm blob style */}
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="cool" />
                <div className="relative container-page py-20 md:py-24 text-center max-w-3xl mx-auto z-10">
                    <span className="section-kicker">Pricing</span>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-6">
                        Pricing that <span className="italic text-brand">scales</span> with your ambition.
                    </h1>
                    <p className="text-lg text-muted-foreground leading-relaxed">
                        Free for exploration. Fair for professionals. Bespoke for enterprises. Every plan includes ITHR&apos;s real-time curriculum intelligence &mdash; courses that refresh as the field moves.
                    </p>
                </div>
            </section>

            {error && (
                <div className="container-page pt-6">
                    <div className="card-flat p-4 border-destructive text-destructive text-sm" data-testid="pricing-error">{error}</div>
                </div>
            )}

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
                            {p.featured && <div className="absolute -top-3 left-8 badge-brand bg-background">Most popular</div>}
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

                            <button
                                onClick={() => handleCheckout(p.packageId)}
                                disabled={processingId === p.packageId}
                                data-testid={`${p.testId}-cta`}
                                className={p.featured ? "btn-primary w-full" : "btn-outline w-full"}
                            >
                                {processingId === p.packageId ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <>{p.cta} <ArrowRight className="w-4 h-4" /></>
                                )}
                            </button>

                            {p.secondaryPackageId && (
                                <button
                                    onClick={() => handleCheckout(p.secondaryPackageId)}
                                    disabled={processingId === p.secondaryPackageId}
                                    data-testid={`${p.testId}-annual-cta`}
                                    className="mt-3 text-xs font-mono uppercase tracking-[0.15em] text-brand hover:text-brand-hover"
                                >
                                    {processingId === p.secondaryPackageId ? "…" : p.secondaryCta}
                                </button>
                            )}
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
                                {p.featured && <div className="absolute -top-3 left-8 badge-brand bg-background">Recommended</div>}
                                <div className="font-serif text-3xl leading-none mb-1">{p.name}</div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-4">{p.seats}</div>
                                <p className="text-sm text-muted-foreground mb-6">{p.description}</p>
                                <div className="mb-6">
                                    <span className="font-serif text-4xl">{p.price}</span>
                                    <span className="text-muted-foreground text-sm ml-2">{p.period}</span>
                                </div>

                                {p.variableQuantity && (
                                    <div className="mb-6">
                                        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-2">Team size (seats)</label>
                                        <input
                                            type="number"
                                            min={10}
                                            max={100}
                                            value={teamSeats}
                                            onChange={(e) => setTeamSeats(Math.max(10, Math.min(100, parseInt(e.target.value) || 10)))}
                                            data-testid="team-seats-input"
                                            className="w-full px-3 py-2 bg-surface border border-border rounded-sm text-sm focus:outline-none focus:border-brand"
                                        />
                                        <div className="text-xs text-muted-foreground mt-2">
                                            First month: <b className="text-foreground">${(teamSeats * 18).toFixed(2)}</b>
                                        </div>
                                    </div>
                                )}

                                <ul className="space-y-2 text-sm mb-8 flex-1">
                                    {p.features.map((f) => (
                                        <li key={f} className="flex gap-2"><Check className="w-4 h-4 text-brand mt-0.5 shrink-0" />{f}</li>
                                    ))}
                                </ul>

                                {p.contact ? (
                                    <a href="mailto:enterprise@ithr.tech" data-testid={`${p.testId}-cta`} className={p.featured ? "btn-primary w-full" : "btn-outline w-full"}>
                                        Contact ITHR <ArrowRight className="w-4 h-4" />
                                    </a>
                                ) : (
                                    <button
                                        onClick={() => handleCheckout(p.packageId, teamSeats)}
                                        disabled={processingId === p.packageId}
                                        data-testid={`${p.testId}-cta`}
                                        className="btn-primary w-full"
                                    >
                                        {processingId === p.packageId ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                            <>Start team subscription <ArrowRight className="w-4 h-4" /></>
                                        )}
                                    </button>
                                )}
                            </div>
                        ))}
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
