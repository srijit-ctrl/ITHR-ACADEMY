import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import HeroBlobs from "@/components/HeroBlobs";
import { ShieldCheck, FileText, Lock, ScrollText, Loader2 } from "lucide-react";

/**
 * Shared renderer for the four legal / policy pages.
 *
 * Markdown source lives under `src/content/legal/*.md`. Each doc contains
 * `{{ PLACEHOLDER }}` tokens (e.g. `{{ CONTACT_EMAIL }}`). We substitute
 * them at render time with real ITHR values so counsel can keep editing
 * the markdown as a single source of truth without changing code.
 */
const PLACEHOLDERS = {
    EFFECTIVE_DATE: "5 February 2026",
    CONTACT_EMAIL: "hello@ithr.online",
    LEGAL_EMAIL: "legal@ithr.online",
    BILLING_EMAIL: "billing@ithr.online",
    PRIVACY_EMAIL: "privacy@ithr.online",
    SECURITY_EMAIL: "security@ithr.online",
    ENTERPRISE_EMAIL: "enterprise@ithr.online",
    SOC2_TARGET: "Q4 2026",
    ISO_TARGET: "Q2 2027",
    ISO_42001_TARGET: "Q3 2027",
};

// Markdown source files live under /public/legal/ (served as static assets).
// This avoids CRA/webpack loader configuration for .md files.
const DOC_URLS = {
    disclaimer: "/legal/disclaimer.md",
    terms: "/legal/terms.md",
    security: "/legal/security.md",
    compliance: "/legal/compliance.md",
    privacy: "/legal/privacy.md",
};

const DOCS = {
    disclaimer: { title: "Disclaimer", icon: FileText, kicker: "Legal" },
    terms: { title: "Terms of Service", icon: ScrollText, kicker: "Legal" },
    security: { title: "Cyber Security", icon: Lock, kicker: "Security" },
    compliance: { title: "Compliance", icon: ShieldCheck, kicker: "Compliance" },
    privacy: { title: "Privacy Policy", icon: ShieldCheck, kicker: "Privacy" },
};

const NAV = [
    { key: "privacy", path: "/privacy", label: "Privacy Policy" },
    { key: "disclaimer", path: "/legal/disclaimer", label: "Disclaimer" },
    { key: "terms", path: "/legal/terms", label: "Terms" },
    { key: "security", path: "/legal/security", label: "Cyber Security" },
    { key: "compliance", path: "/legal/compliance", label: "Compliance" },
];

function fillPlaceholders(raw) {
    return raw.replace(/\{\{\s*([A-Z0-9_]+)\s*\}\}/g, (m, k) => PLACEHOLDERS[k] ?? m);
}

export default function LegalDoc({ docKey }) {
    const location = useLocation();
    const [markdown, setMarkdown] = useState("");
    const doc = DOCS[docKey];

    useEffect(() => {
        const url = DOC_URLS[docKey];
        if (!url) return;
        fetch(url)
            .then((r) => r.text())
            .then((text) => setMarkdown(fillPlaceholders(text)))
            .catch(() => setMarkdown("_Could not load document._"));
    }, [docKey]);

    if (!doc) return <div className="container-page py-24 text-center text-muted-foreground">Document not found.</div>;

    const Icon = doc.icon;

    return (
        <div>
            <section className="relative overflow-hidden bg-surface-alt/40 border-b border-border">
                <HeroBlobs variant="cool" />
                <div className="relative container-narrow py-16 z-10">
                    <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.25em] text-brand mb-4">
                        <Icon className="w-3.5 h-3.5" /> {doc.kicker}
                    </div>
                    <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none" data-testid="legal-doc-title">
                        {doc.title}
                    </h1>
                </div>
            </section>

            <div className="container-narrow py-12 grid grid-cols-1 md:grid-cols-12 gap-8">
                {/* Sub-nav */}
                <aside className="md:col-span-3">
                    <nav className="sticky top-24 card-flat p-4 space-y-1" data-testid="legal-doc-nav">
                        {NAV.map((n) => (
                            <Link
                                key={n.key}
                                to={n.path}
                                data-testid={`legal-nav-${n.key}`}
                                className={`block px-3 py-2 text-sm rounded-sm transition-colors ${
                                    location.pathname === n.path
                                        ? "bg-brand/10 text-brand font-medium"
                                        : "text-muted-foreground hover:bg-surface-alt hover:text-foreground"
                                }`}
                            >
                                {n.label}
                            </Link>
                        ))}
                        <div className="border-t border-border mt-3 pt-3">
                            <Link
                                to="/trust"
                                className="block px-3 py-2 text-sm text-muted-foreground hover:text-foreground rounded-sm hover:bg-surface-alt transition-colors"
                            >
                                Trust Center
                            </Link>
                        </div>
                    </nav>
                </aside>

                <article
                    className="md:col-span-9 legal-prose text-base leading-relaxed max-w-none"
                    data-testid="legal-doc-body"
                >
                    {markdown ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
                    ) : (
                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                    )}
                </article>
            </div>
        </div>
    );
}
