import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
    ShieldCheck, Lock, Server, FileText, KeyRound, Users, Eye, AlertCircle,
    ArrowRight, CheckCircle2, Clock, MapPin, Mail, Download, Package, Loader2
} from "lucide-react";
import HeroBlobs from "@/components/HeroBlobs";
import { api, API_BASE } from "@/lib/api";
import { toast } from "sonner";

/**
 * Public Trust Page — realistic-only claims.
 * Every item is labelled Live / In progress / Planned so no misleading claim is made.
 * Anchored on ITHR Technologies Consulting LLC as a UAE-domiciled issuer.
 */

const STATUS = {
    live: { label: "Live", cls: "bg-success/10 text-success border-success/30" },
    progress: { label: "In progress", cls: "bg-brand-sky/15 text-brand-navy border-brand-sky/40" },
    planned: { label: "Planned", cls: "bg-muted text-muted-foreground border-border" },
};

function StatusPill({ status }) {
    const s = STATUS[status];
    return (
        <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full border text-[10px] font-mono uppercase tracking-[0.15em] ${s.cls}`}
            data-testid={`status-${status}`}
        >
            {s.label}
        </span>
    );
}

const CONTROLS = [
    {
        icon: Lock, title: "Transport encryption (TLS)",
        detail: "All traffic to the Academy is served over HTTPS with modern cipher suites and HSTS on the production domain.",
        status: "live",
    },
    {
        icon: KeyRound, title: "Password hashing (bcrypt)",
        detail: "Learner passwords are stored as bcrypt hashes (12 rounds). Plaintext passwords are never logged or written to disk.",
        status: "live",
    },
    {
        icon: ShieldCheck, title: "JWT session tokens with expiry",
        detail: "Sign-in issues short-lived signed JSON Web Tokens; server verifies signature and expiry on every /api/* request.",
        status: "live",
    },
    {
        icon: Users, title: "Role-based access control",
        detail: "Enterprise dashboards enforce owner / admin / member roles on every server endpoint — checks are not client-side only.",
        status: "live",
    },
    {
        icon: Eye, title: "Public credential verification",
        detail: "Every credential exposes a public /verify/{id} endpoint and a scannable QR — no login required to check authenticity.",
        status: "live",
    },
    {
        icon: FileText, title: "Server-rendered PDF certificates",
        detail: "Certificate PDFs are produced by our servers with an embedded verification QR — screenshots cannot be silently altered.",
        status: "live",
    },
    {
        icon: AlertCircle, title: "Abuse rate-limiting on public demo",
        detail: "The anonymous try-a-lesson endpoint is rate-limited per IP to prevent token-farming and cost-abuse.",
        status: "live",
    },
    {
        icon: Server, title: "MFA + SSO (Azure AD / Okta / Google Workspace)",
        detail: "Enterprise single sign-on with MFA enforcement and SCIM auto-deprovisioning.",
        status: "planned",
    },
    {
        icon: Lock, title: "Envelope encryption at rest (KMS)",
        detail: "Managed keys for the production database, object storage, and backups. Available once we cut over from the current shared-cloud environment.",
        status: "planned",
    },
    {
        icon: MapPin, title: "UAE data residency (AWS me-central-1 / Azure UAE)",
        detail: "The MVP runs in a shared cloud region today. UAE-resident production is the next infrastructure milestone before enterprise onboarding.",
        status: "progress",
    },
    {
        icon: FileText, title: "SOC 2 Type I readiness",
        detail: "Controls are being written up and evidence collected. We are not yet SOC 2 attested and do not claim to be.",
        status: "progress",
    },
    {
        icon: FileText, title: "ISO/IEC 27001 certification",
        detail: "On the roadmap. We reference ISO 27001 controls in our internal build but hold no certificate today.",
        status: "planned",
    },
    {
        icon: Users, title: "UAE PDPL registration + designated DPO",
        detail: "The UAE Personal Data Protection Law applies to our UAE learners; we are preparing formal registration and appointing a Data Protection Officer.",
        status: "progress",
    },
    {
        icon: AlertCircle, title: "Independent penetration test (CREST)",
        detail: "First external pen-test is scheduled ahead of enterprise general availability.",
        status: "planned",
    },
];

const SUB_PROCESSORS = [
    { name: "MongoDB", purpose: "Primary database (learners, courses, credentials)", region: "Cloud region — see notes below", status: "live" },
    { name: "Anthropic", purpose: "AI Tutor (Aletheia) + AI Mentor (Solon) + curriculum-signal drafting", region: "Vendor default", status: "live" },
    { name: "Stripe", purpose: "Payment processing (subscriptions, one-time, per-seat)", region: "Vendor default; test key today", status: "live" },
    { name: "Google (Emergent-managed OAuth)", purpose: "Sign in with Google", region: "Google infrastructure", status: "live" },
    { name: "Resend", purpose: "Transactional + weekly digest emails", region: "Vendor default", status: "planned (key not yet provisioned)" },
    { name: "AWS (me-central-1)", purpose: "Production compute, storage, KMS, WAF", region: "UAE (Dubai / Etihad DC)", status: "planned" },
];

const ISSUER_PILLARS = [
    { title: "A real legal entity", detail: "Credentials are issued by ITHR Technologies Consulting LLC, a UAE-registered consulting firm.", status: "live" },
    { title: "Documented pass rubric", detail: "Every course lists its assessment format, passing threshold, and question style. Nothing is hidden.", status: "live" },
    { title: "Public verification registry", detail: "Every issued credential is independently checkable at /verify/{id} — no login required.", status: "live" },
    { title: "QR-anchored PDF certificates", detail: "The QR on every certificate resolves to the same public verification page.", status: "live" },
    { title: "Named authors on every course", detail: "Publishing credits to be shown on each course landing page.", status: "progress" },
    { title: "External academic advisory board", detail: "A small external review board to oversee courseware quality and appeals.", status: "planned" },
    { title: "Cryptographic signature + W3C Verifiable Credential format", detail: "Adds tamper-evident signatures interoperable with digital wallets.", status: "planned" },
    { title: "Personnel-certification-body accreditation (ISO/IEC 17024)", detail: "The strongest international recognition for the issuer itself.", status: "planned" },
];

export default function Trust() {
    const [buildInfo, setBuildInfo] = useState({ version: null, ts: null });
    const [packLoading, setPackLoading] = useState(false);

    useEffect(() => {
        api.get("/health").then((r) => setBuildInfo({
            version: r.data?.version || "MVP",
            ts: r.data?.timestamp || new Date().toISOString(),
        })).catch(() => {});
    }, []);

    const downloadProcurementPack = async () => {
        setPackLoading(true);
        try {
            const res = await fetch(`${API_BASE}/trust/procurement-pack`);
            if (!res.ok) throw new Error(`Download failed (HTTP ${res.status})`);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `ITHR-Academy-Procurement-Pack-${new Date().toISOString().slice(0, 10)}.zip`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast.success("Procurement pack downloaded.");
        } catch (e) {
            toast.error(e?.message || "Could not generate the pack. Please retry in a moment.");
        } finally {
            setPackLoading(false);
        }
    };

    return (
        <div>
            {/* Hero */}
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="cool" />
                <div className="relative container-page pt-16 pb-14 z-10">
                    <div className="max-w-3xl">
                        <span className="section-kicker" data-testid="trust-kicker">Trust · Security · Compliance</span>
                        <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mt-4 mb-6">
                            Built openly. Verified <span className="italic text-brand">honestly</span>.
                        </h1>
                        <p className="text-lg text-muted-foreground leading-relaxed max-w-2xl">
                            Every claim on this page is labelled <b className="text-success">Live</b>, <b className="text-brand-navy">In progress</b>, or <b>Planned</b>. If it isn&apos;t Live, we won&apos;t pretend otherwise.
                        </p>
                        <div className="mt-6 flex flex-wrap gap-3 text-xs">
                            <button
                                onClick={downloadProcurementPack}
                                disabled={packLoading}
                                data-testid="download-procurement-pack"
                                className="btn-primary text-xs"
                            >
                                {packLoading ? (
                                    <><Loader2 className="w-3 h-3 animate-spin" /> Generating pack…</>
                                ) : (
                                    <><Package className="w-3 h-3" /> Generate procurement pack</>
                                )}
                            </button>
                            <Link to="/verify" data-testid="trust-verify-cta" className="btn-outline text-xs">
                                <ShieldCheck className="w-3 h-3" /> Verify a credential
                            </Link>
                            <a href="mailto:security@ithr.ae" data-testid="trust-contact-security" className="btn-outline text-xs">
                                <Mail className="w-3 h-3" /> Contact security team
                            </a>
                        </div>
                        <p className="mt-3 text-[11px] text-muted-foreground max-w-lg">
                            The pack is a ZIP with a one-page security fact-sheet, sub-processor register, DPA template, and full compliance dossier — everything a vendor-review team typically asks for on day one.
                        </p>
                    </div>
                </div>
            </section>

            {/* Made in UAE strip */}
            <section className="border-t border-b border-border bg-white" data-testid="uae-strip">
                <div className="container-page py-8 flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-4">
                        <UAEFlag className="w-10 h-7 rounded-sm shadow-sm shrink-0" />
                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-brand-teal">Designed &amp; engineered in the United Arab Emirates</div>
                            <div className="font-serif text-lg">Made in the UAE — for the world.</div>
                        </div>
                    </div>
                    <div className="text-xs text-muted-foreground font-mono uppercase tracking-[0.15em]">
                        Operated by ITHR Technologies Consulting LLC
                    </div>
                </div>
            </section>

            {/* Issuer identity */}
            <section className="section-warm-mint py-16">
                <div className="container-page grid grid-cols-1 md:grid-cols-3 gap-10">
                    <div>
                        <span className="section-kicker">Who issues credentials</span>
                        <h2 className="font-serif text-3xl md:text-4xl tracking-tight mt-3 mb-3 leading-tight">
                            Every credential is signed by a real UAE company.
                        </h2>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                            The Academy is operated end-to-end by <span className="text-foreground font-medium">ITHR Technologies Consulting LLC</span> — a UAE-registered consulting firm. We stand behind every certificate we issue, in our own name.
                        </p>
                    </div>
                    <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {ISSUER_PILLARS.map((p, i) => (
                            <div key={p.title} className="card-flat p-4" data-testid={`issuer-pillar-${i}`}>
                                <div className="flex items-start justify-between gap-3 mb-2">
                                    <div className="font-serif text-base leading-tight">{p.title}</div>
                                    <StatusPill status={p.status} />
                                </div>
                                <div className="text-xs text-muted-foreground leading-relaxed">{p.detail}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Security controls */}
            <section className="py-20 bg-white">
                <div className="container-page">
                    <div className="max-w-2xl mb-10">
                        <span className="section-kicker">Security controls</span>
                        <h2 className="font-serif text-3xl md:text-4xl tracking-tight mt-3 mb-3">What is protecting your data today.</h2>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                            Below is the honest picture: what is running in production right now, what we are actively working on, and what is still on the roadmap.
                        </p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {CONTROLS.map((c, i) => (
                            <div key={c.title} className="card-flat p-5" data-testid={`control-${i}`}>
                                <div className="flex items-start justify-between gap-3 mb-3">
                                    <c.icon className="w-5 h-5 text-brand" />
                                    <StatusPill status={c.status} />
                                </div>
                                <div className="font-serif text-lg leading-tight mb-2">{c.title}</div>
                                <div className="text-xs text-muted-foreground leading-relaxed">{c.detail}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Data residency */}
            <section className="py-20 section-warm-mint">
                <div className="container-page grid grid-cols-1 md:grid-cols-2 gap-10">
                    <div>
                        <span className="section-kicker">Data residency</span>
                        <h2 className="font-serif text-3xl md:text-4xl tracking-tight mt-3 mb-3">Where your data lives today — and where it is going.</h2>
                        <p className="text-sm text-muted-foreground leading-relaxed mb-4">
                            The MVP is deployed on a managed Kubernetes cluster in a shared cloud region. That is fit for demonstration and pilot workloads, not for regulated production. The next infrastructure milestone is to migrate to a <b className="text-foreground">UAE-resident production environment</b> so that customer and learner data remains within the United Arab Emirates.
                        </p>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                            Enterprise customers with strict data-residency requirements can request the migration timeline and DPA terms before onboarding.
                        </p>
                    </div>
                    <div className="card-flat p-6 space-y-4" data-testid="residency-status">
                        <div className="flex items-start gap-3">
                            <Clock className="w-5 h-5 text-brand-navy mt-0.5" />
                            <div>
                                <div className="font-serif text-lg">Today</div>
                                <div className="text-sm text-muted-foreground">Shared managed-Kubernetes cluster, MongoDB primary. Suitable for pilots.</div>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <MapPin className="w-5 h-5 text-brand mt-0.5" />
                            <div>
                                <div className="font-serif text-lg">Next</div>
                                <div className="text-sm text-muted-foreground">AWS <span className="font-mono">me-central-1</span> (UAE) with MongoDB Atlas in-region, KMS at rest, TLS 1.3 in transit.</div>
                            </div>
                        </div>
                        <div className="flex items-start gap-3">
                            <CheckCircle2 className="w-5 h-5 text-success mt-0.5" />
                            <div>
                                <div className="font-serif text-lg">Guarantee once migrated</div>
                                <div className="text-sm text-muted-foreground">Customer data never leaves UAE borders. Backups and DR are also UAE-resident.</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Sub-processors */}
            <section className="py-20 bg-white">
                <div className="container-page">
                    <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
                        <div>
                            <span className="section-kicker">Sub-processors</span>
                            <h2 className="font-serif text-3xl md:text-4xl tracking-tight mt-3">Who we rely on to run the Academy.</h2>
                        </div>
                        <div className="text-xs text-muted-foreground font-mono uppercase tracking-[0.15em]">Updated on any change</div>
                    </div>
                    <div className="card-flat overflow-hidden" data-testid="subprocessors-table">
                        <div className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-border text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground bg-surface-alt">
                            <div className="col-span-3">Sub-processor</div>
                            <div className="col-span-5">Purpose</div>
                            <div className="col-span-3">Region / notes</div>
                            <div className="col-span-1 text-right">Status</div>
                        </div>
                        {SUB_PROCESSORS.map((s, i) => (
                            <div key={s.name} className="grid grid-cols-12 gap-4 px-5 py-4 border-b border-border last:border-b-0 items-center text-sm" data-testid={`subproc-${i}`}>
                                <div className="col-span-3 font-serif text-base">{s.name}</div>
                                <div className="col-span-5 text-sm text-muted-foreground">{s.purpose}</div>
                                <div className="col-span-3 text-xs text-muted-foreground">{s.region}</div>
                                <div className="col-span-1 text-right text-[10px] font-mono uppercase tracking-[0.15em]">{s.status}</div>
                            </div>
                        ))}
                    </div>
                    <p className="text-xs text-muted-foreground mt-4 max-w-3xl leading-relaxed">
                        We do not sell learner data, and we do not use enterprise customer data to train third-party AI models. If a sub-processor changes, this page is the source of truth.
                    </p>
                </div>
            </section>

            {/* What we do NOT claim */}
            <section className="py-20 section-warm-mint">
                <div className="container-page max-w-3xl">
                    <span className="section-kicker">What we do not claim</span>
                    <h2 className="font-serif text-3xl md:text-4xl tracking-tight mt-3 mb-4">Honest limits.</h2>
                    <ul className="space-y-3 text-sm text-muted-foreground leading-relaxed" data-testid="honest-limits">
                        <li>· We are <b className="text-foreground">not yet SOC 2 attested</b>. Any footer badge, brochure, or reseller deck that says otherwise is incorrect — please tell us so we can fix it.</li>
                        <li>· We do <b className="text-foreground">not yet hold ISO/IEC 27001</b> certification.</li>
                        <li>· We do <b className="text-foreground">not yet hold ISO/IEC 17024</b> personnel-certification-body accreditation. Our credentials are trustworthy because of our public verification registry, published rubric, and legal entity behind them — not because of an external body.</li>
                        <li>· Data does <b className="text-foreground">not yet reside inside UAE borders</b> in production. The MVP runs in a shared cloud region. UAE residency is the next infrastructure milestone.</li>
                        <li>· Payments today use a <b className="text-foreground">Stripe test key</b>. Real transactions require the live-key cutover.</li>
                    </ul>
                    <p className="mt-6 text-sm text-muted-foreground">
                        We prefer to publish this candid list rather than let a procurement questionnaire discover it. When any of the above changes, this page is updated the same day.
                    </p>
                </div>
            </section>

            {/* Report + contact */}
            <section className="py-20 bg-white">
                <div className="container-page grid grid-cols-1 md:grid-cols-3 gap-10">
                    <div className="card-flat p-6" data-testid="report-security">
                        <AlertCircle className="w-5 h-5 text-brand mb-3" />
                        <div className="font-serif text-xl mb-2">Report a security issue</div>
                        <p className="text-sm text-muted-foreground mb-4">
                            Responsible-disclosure researchers are welcome. Please email us before public disclosure.
                        </p>
                        <a href="mailto:security@ithr.ae" className="btn-outline text-xs">
                            <Mail className="w-3 h-3" /> security@ithr.ae
                        </a>
                    </div>
                    <div className="card-flat p-6" data-testid="dsar-contact">
                        <FileText className="w-5 h-5 text-brand mb-3" />
                        <div className="font-serif text-xl mb-2">Data-subject requests</div>
                        <p className="text-sm text-muted-foreground mb-4">
                            Access, correction, portability, or deletion — we aim to respond within 30 calendar days.
                        </p>
                        <a href="mailto:privacy@ithr.ae" className="btn-outline text-xs">
                            <Mail className="w-3 h-3" /> privacy@ithr.ae
                        </a>
                    </div>
                    <div className="card-flat p-6" data-testid="dpa-request">
                        <Download className="w-5 h-5 text-brand mb-3" />
                        <div className="font-serif text-xl mb-2">Request a DPA</div>
                        <p className="text-sm text-muted-foreground mb-4">
                            The DPA template ships inside the procurement pack. Executed DPAs are exchanged during procurement.
                        </p>
                        <button
                            onClick={downloadProcurementPack}
                            disabled={packLoading}
                            data-testid="dpa-download-pack"
                            className="btn-outline text-xs"
                        >
                            {packLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Package className="w-3 h-3" />}
                            Download procurement pack
                        </button>
                    </div>
                </div>
            </section>

            {/* Build info footer */}
            <section className="border-t border-border bg-surface-alt/40 py-6" data-testid="trust-buildinfo">
                <div className="container-page flex items-center justify-between flex-wrap gap-3 text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                    <div>Trust page · Last generated on page load · {buildInfo.ts ? new Date(buildInfo.ts).toISOString().slice(0, 10) : "—"}</div>
                    <Link to="/verify" className="hover:text-brand inline-flex items-center gap-1.5" data-testid="trust-verify-footer">
                        Verify a credential <ArrowRight className="w-3 h-3" />
                    </Link>
                </div>
            </section>
        </div>
    );
}

/**
 * Minimal UAE flag rendered as SVG so we don't depend on external assets.
 * Ratio 2:1, official proportions.
 */
function UAEFlag({ className }) {
    return (
        <svg viewBox="0 0 12 6" className={className} aria-label="Flag of the United Arab Emirates" role="img">
            <rect x="0" y="0" width="12" height="6" fill="#000000" />
            <rect x="0" y="0" width="12" height="4" fill="#FFFFFF" />
            <rect x="0" y="0" width="12" height="2" fill="#00732F" />
            <rect x="0" y="0" width="3" height="6" fill="#FF0000" />
        </svg>
    );
}
