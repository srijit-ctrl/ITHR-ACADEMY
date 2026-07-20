import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ArrowRight, Sparkles, Radio, Zap } from "lucide-react";
import CourseCard from "@/components/CourseCard";
import TryALesson from "@/components/TryALesson";
import InauguralFlasher from "@/components/InauguralFlasher";

const HERO_IMG = "https://images.unsplash.com/photo-1526314114033-349ef6f72220?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODl8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBhcmNoaXRlY3R1cmFsJTIwbGlicmFyeXxlbnwwfHx8fDE3ODMxNTI1NTV8MA&ixlib=rb-4.1.0&q=85";
const ENTERPRISE_IMG = "https://images.pexels.com/photos/7698712/pexels-photo-7698712.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

const PARTNERS = ["Anthropic", "OpenAI", "Google DeepMind", "Microsoft", "AWS", "IBM", "Salesforce", "Palantir"];

const CERT_TIERS = [
    { title: "Foundation", tier: "I", desc: "For all professionals entering the agentic AI economy.", color: "color-card-blue" },
    { title: "Practitioner", tier: "II", desc: "Hands-on credential for those building production agents.", color: "color-card-teal" },
    { title: "Professional", tier: "III", desc: "Advanced credential with capstone project.", color: "color-card-purple" },
    { title: "Architect", tier: "IV", desc: "System-design credential for senior technologists.", color: "color-card-orange" },
    { title: "Enterprise Leader", tier: "V", desc: "For CXOs steering organization-wide transformation.", color: "color-card-gold" },
    { title: "Chief AI Officer", tier: "VI", desc: "The definitive CAIO credential.", color: "color-card-navy" },
];

export default function Landing() {
    const [featured, setFeatured] = useState([]);

    useEffect(() => {
        api.get("/courses").then((res) => setFeatured(res.data.slice(0, 6))).catch(() => { });
    }, []);

    return (
        <div className="min-h-screen">
            <InauguralFlasher />
            {/* HERO — aiilm-inspired centered with soft blobs */}
            <section className="relative overflow-hidden bg-white pattern-dots">
                {/* Floating soft blobs (aiilm signature) */}
                <div className="blob blob-yellow" style={{ width: 340, height: 340, top: 40, right: -60 }} />
                <div className="blob blob-pink"   style={{ width: 260, height: 260, top: 350, left: 240 }} />
                <div className="blob blob-blue"   style={{ width: 240, height: 240, bottom: -40, left: -40, animationDelay: "3s" }} />
                <div className="blob blob-purple" style={{ width: 280, height: 280, top: 200, right: 220, animationDelay: "6s" }} />

                {/* Faint diamond pattern */}
                <div className="absolute inset-0 opacity-[0.04] pointer-events-none" style={{
                    backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 60 60'><g stroke='%231f2430' fill='none' stroke-width='1'><path d='M30 4l26 26-26 26L4 30z'/></g></svg>\")",
                }} />

                <div className="relative container-page pt-14 pb-20 md:pt-20 md:pb-28 z-10">
                    <div className="max-w-4xl mx-auto text-center">
                        <div className="mt-3 inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground" data-testid="hero-uae-badge">
                            <svg viewBox="0 0 12 6" aria-hidden="true" className="w-4 h-2.5 rounded-[2px] shadow-sm">
                                <rect x="0" y="0" width="12" height="6" fill="#000" />
                                <rect x="0" y="0" width="12" height="4" fill="#FFF" />
                                <rect x="0" y="0" width="12" height="2" fill="#00732F" />
                                <rect x="0" y="0" width="3" height="6" fill="#FF0000" />
                            </svg>
                            Made in the UAE · for the world
                        </div>
                        <h1 className="font-serif text-5xl sm:text-6xl lg:text-[80px] tracking-tighter leading-[1.02] font-medium mb-8">
                            Where the world&apos;s workforce learns to <span className="italic text-brand">command</span> AI.
                        </h1>
                        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed mb-10">
                            The <span className="text-foreground font-semibold">ITHR Academy</span> is a credentialing platform for enterprise workforces &mdash; six tiers, twenty industries, one standard, refreshed continuously.
                        </p>
                        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-14">
                            <Link to="/courses" data-testid="hero-browse-catalog" className="btn-primary text-base">
                                <Sparkles className="w-4 h-4" /> Browse the catalog
                                <ArrowRight className="w-4 h-4" />
                            </Link>
                            <Link to="/intelligence" data-testid="hero-see-intelligence" className="btn-outline text-base">
                                <Radio className="w-4 h-4" /> See today&apos;s intelligence
                            </Link>
                        </div>

                        {/* Structural stat pips — only claim what is factually verifiable */}
                        <div className="flex flex-wrap justify-center gap-x-14 gap-y-6 pt-8 border-t border-border">
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none">6</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Credential tiers</div>
                            </div>
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none">24</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Courses in catalog</div>
                            </div>
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none">15</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Modules per course</div>
                            </div>
                            <div className="text-left">
                                <div className="font-serif text-3xl leading-none">100%</div>
                                <div className="text-xs text-muted-foreground mt-1.5 font-mono uppercase tracking-[0.15em]">Publicly verifiable</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* CURRICULUM SOURCES — realistic phrasing */}
            <section className="border-b border-border py-10 bg-surface-alt/40">
                <div className="container-page">
                    <div className="overline mb-6 text-center">Curriculum curated by public research &amp; standards from</div>
                    <div className="flex flex-wrap justify-center items-center gap-x-10 gap-y-4 text-lg font-serif text-muted-foreground/80">
                        {PARTNERS.map((p) => (
                            <span key={p} className="italic">{p}</span>
                        ))}
                    </div>
                    <div className="mt-4 text-center text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground/70">
                        Independently authored by ITHR · not affiliated with the organizations above
                    </div>
                </div>
            </section>

            {/* HOW IT WORKS — aiilm-style numbered steps */}
            <section className="section-warm-mint py-24">
                <div className="container-page">
                    <div className="text-center max-w-2xl mx-auto mb-16">
                        <span className="section-kicker">Three ways in</span>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight">
                            How the Academy works.
                        </h2>
                        <p className="mt-4 text-muted-foreground text-lg">
                            Anchor to a role, learn with a tutor, and prove your competency — in weeks, not years.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {[
                            {
                                num: "01", icon: "🧭", title: "Anchor to your role",
                                desc: "Pick a role-based track — Product Manager, Engineer, Risk Officer, HR, Banking, Healthcare, Executive — and let the curriculum sequence itself for you.",
                            },
                            {
                                num: "02", icon: "🎯", title: "Learn with an AI Tutor",
                                desc: "Aletheia sits inside every lesson to explain, quiz, and coach. Solon, your career mentor, plans your next credential and 90-day project.",
                            },
                            {
                                num: "03", icon: "🏅", title: "Prove it. Publicly.",
                                desc: "Pass adaptive assessments to earn cryptographically-verifiable credentials. Share a public AI Skills Passport on LinkedIn or your résumé.",
                            },
                        ].map((s) => (
                            <div key={s.num} className="step-card" data-testid={`how-step-${s.num}`}>
                                <div className="step-num">{s.num}</div>
                                <div className="text-4xl mb-4">{s.icon}</div>
                                <h3 className="font-serif text-2xl tracking-tight mb-3">{s.title}</h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* TRY-A-LESSON — anonymous streaming demo */}
            <TryALesson />

            {/* FEATURED COURSES */}
            <section className="container-page py-24">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-10 mb-12">
                    <div className="md:col-span-8">
                        <span className="section-kicker">Featured Curriculum</span>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none">
                            Rigorous coursework.<br />
                            Written by practitioners.
                        </h2>
                    </div>
                    <div className="md:col-span-4 md:pt-6 flex items-end">
                        <Link to="/courses" data-testid="see-all-courses" className="text-sm font-medium text-brand hover:text-brand-hover inline-flex items-center gap-1">
                            See the full catalog <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
                    {featured.map((c) => <CourseCard key={c.id} course={c} testIdPrefix="landing-course" />)}
                </div>
            </section>

            {/* CERTIFICATION LADDER */}
            <section className="section-warm-cream border-y border-border py-24">
                <div className="container-page">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-10 mb-14">
                        <div className="md:col-span-6">
                            <span className="section-kicker">The Certification Ladder</span>
                            <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none">
                                Six tiers.<br />
                                From analyst to <span className="italic text-brand">CAIO</span>.
                            </h2>
                        </div>
                        <div className="md:col-span-6 md:pt-6">
                            <p className="text-muted-foreground text-lg leading-relaxed">
                                A stepped progression that lets every employee prove AI competency at the level their role demands — and gives every organization a common language for AI fluency across departments and geographies.
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {CERT_TIERS.map((t) => (
                            <div key={t.title} className={`color-card ${t.color}`} data-testid={`cert-tier-${t.title.toLowerCase().replace(/\s+/g, "-")}`}>
                                <div className="color-card-kicker">Tier {t.tier}</div>
                                <div className="font-serif text-3xl md:text-4xl tracking-tight mb-3 leading-none">{t.title}</div>
                                <p className="text-sm opacity-90 leading-relaxed">{t.desc}</p>
                                <div className="mt-auto pt-6 flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.2em] opacity-80">
                                    <ArrowRight className="w-3 h-3" /> Enroll path
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ENTERPRISE CTA */}
            <section className="container-page py-24">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-10 items-center">
                    <div className="md:col-span-6">
                        <div className="aspect-[4/5] overflow-hidden border border-border">
                            <img src={ENTERPRISE_IMG} alt="Corporate learners" className="w-full h-full object-cover" />
                        </div>
                    </div>
                    <div className="md:col-span-6">
                        <div className="overline mb-4 fine-rule pl-4">For Enterprise</div>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none mb-6">
                            An AI Skills Passport<br />
                            for every employee.
                        </h2>
                        <p className="text-lg text-muted-foreground leading-relaxed mb-6">
                            Beyond courses and certificates: your organization gets an AI Readiness Index, departmental maturity scores, role-based learning paths for HR, Finance, Sales, Procurement, Manufacturing — and manager dashboards that surface capability gaps before they cost you.
                        </p>
                        <ul className="space-y-3 mb-8">
                            {[
                                "Organization-wide AI competency analytics",
                                "SSO across Azure AD, Google Workspace, Okta",
                                "Custom certification tracks per business unit",
                                "Renewal credits keep credentials current",
                            ].map((item) => (
                                <li key={item} className="flex items-start gap-3 text-sm">
                                    <Sparkles className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                                    {item}
                                </li>
                            ))}
                        </ul>
                        <Link to="/enterprise" data-testid="enterprise-cta" className="btn-ink">
                            Explore for teams <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                </div>
            </section>

            {/* AI TUTOR CTA */}
            <section className="border-t border-border grain">
                <div className="container-page py-24 max-w-4xl">
                    <div className="text-center">
                        <div className="overline mb-6">Meet Aletheia</div>
                        <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight mb-6">
                            Every learner gets a<br />
                            <span className="italic text-brand">tutor of their own.</span>
                        </h2>
                        <p className="text-lg text-muted-foreground leading-relaxed mb-8 max-w-2xl mx-auto">
                            Aletheia is our resident AI tutor — a scholarly, Socratic guide available around the clock. She explains, quizzes, coaches, and adapts to your pace. Powered by Claude Sonnet 4.5.
                        </p>
                        <Link to="/register" data-testid="ai-tutor-cta-register" className="btn-primary">
                            Get your tutor <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                </div>
            </section>

            {/* REAL-TIME INTELLIGENCE — light teal instead of black */}
            <section className="section-warm-mint border-t border-border">
                <div className="container-page py-24 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
                    <div className="lg:col-span-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Radio className="w-4 h-4 text-brand animate-pulse" />
                            <span className="section-kicker mb-0">ITHR Intelligence Desk</span>
                        </div>
                        <h2 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1.02] mb-6">
                            Curriculum that <span className="italic text-brand">refreshes itself.</span>
                        </h2>
                        <p className="text-lg text-muted-foreground leading-relaxed mb-8 max-w-xl">
                            Agentic AI moves weekly. ITHR&apos;s Intelligence Desk — a Claude-powered analyst agent — scans the frontier every 6 hours and pushes signals into your curriculum. Model releases, regulation, enterprise deployments: nothing goes stale.
                        </p>
                        <div className="flex gap-3">
                            <Link to="/intelligence" data-testid="landing-intel-cta" className="btn-primary">
                                See today&apos;s briefing <ArrowRight className="w-4 h-4" />
                            </Link>
                            <Link to="/pricing" data-testid="landing-pricing-cta" className="btn-outline">
                                See pricing
                            </Link>
                        </div>
                    </div>

                    <div className="lg:col-span-6 space-y-3">
                        {[
                            { impact: "Critical", cat: "Regulation", title: "EU AI Act Article 6 obligations take effect for enterprise deployers", action: "Refresh Module 11 within 14 days" },
                            { impact: "High", cat: "Model Release", title: "Anthropic ships Claude 4.6 with 500k-token task budgets", action: "Add coverage in Module 4 (LLMs Powering Agents)" },
                            { impact: "Medium", cat: "Framework", title: "MCP 2.0 adds signed capability manifests", action: "Update MCP examples in Module 3" },
                        ].map((s) => (
                            <div key={s.title} className="bg-surface border border-border rounded-2xl p-5 hover:border-brand hover:-translate-y-0.5 transition-all">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">{s.cat}</span>
                                    <span className={`text-[10px] font-mono uppercase tracking-[0.15em] px-2 py-0.5 rounded-full ${s.impact === "Critical" ? "bg-destructive text-white" : s.impact === "High" ? "bg-brand text-white" : "bg-surface-alt"}`}>{s.impact}</span>
                                </div>
                                <div className="font-serif text-lg leading-tight mb-2">{s.title}</div>
                                <div className="text-xs text-muted-foreground flex items-center gap-2"><Zap className="w-3 h-3 text-brand" />{s.action}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    );
}
