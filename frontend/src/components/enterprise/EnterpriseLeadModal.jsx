import { useEffect, useMemo, useState } from "react";
import { X, Loader2, Send, Check, Building2 } from "lucide-react";
import { api } from "@/lib/api";

const BUNDLE_LABEL = {
    "talent-ops-bundle": "Talent Ops Bundle",
    "hr-starter": "HR Transformation · Starter",
    "hr-growth": "HR Transformation · Growth",
    "hr-enterprise": "HR Transformation · Enterprise-HR",
    "hr-consult": "HR Transformation · Consultation",
    generic: "Enterprise consultation",
};

/**
 * Reusable enterprise-lead capture. Two modes:
 *   - Modal (default) — controlled by `open` + `onClose` props.
 *   - Inline form via `<EnterpriseLeadForm bundle=… />` further below.
 *
 * On submit the payload POSTs to /api/leads/enterprise which:
 *   1) Persists to Mongo (enterprise_leads collection).
 *   2) Fires a Slack alert (fire-and-forget, no-op when webhook unset).
 *   3) Auto-replies via Resend inside one working-day promise.
 *
 * Always displays a "Thanks — we'll be in touch" success state after
 * submit so the visitor never sees a blank state.
 */
export default function EnterpriseLeadModal({ open, onClose, bundle = "generic", sourceUrl }) {
    if (!open) return null;
    return (
        <div
            className="fixed inset-0 z-50 bg-foreground/60 flex items-center justify-center p-4 overflow-y-auto"
            onClick={onClose}
            data-testid="enterprise-lead-modal"
        >
            <div
                className="card-flat max-w-xl w-full bg-surface my-8"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-start justify-between p-6 border-b border-border">
                    <div>
                        <div className="overline mb-1 text-brand">Talk to us</div>
                        <h3 className="font-serif text-2xl leading-tight">
                            {BUNDLE_LABEL[bundle] || "Enterprise consultation"}
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Reply within one working day. No hard sell — just answers.
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-surface-alt rounded-sm"
                        data-testid="enterprise-lead-modal-close"
                        aria-label="Close"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="p-6">
                    <EnterpriseLeadForm bundle={bundle} sourceUrl={sourceUrl} onDone={onClose} />
                </div>
            </div>
        </div>
    );
}


/**
 * Inline form — used on /enterprise or dropped anywhere on the marketing
 * site. Pre-fills bundle from parent, tracks source_url automatically.
 */
export function EnterpriseLeadForm({ bundle = "generic", sourceUrl, onDone }) {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [company, setCompany] = useState("");
    const [role, setRole] = useState("");
    const [seats, setSeats] = useState("");
    const [message, setMessage] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [done, setDone] = useState(false);
    const [error, setError] = useState("");

    const source = useMemo(() => sourceUrl || (typeof window !== "undefined" ? window.location.href : ""), [sourceUrl]);

    // Auto-clear the "done" state if the parent re-opens the modal for a fresh submission.
    useEffect(() => {
        setDone(false);
        setError("");
    }, [bundle]);

    const canSend = name.trim() && email.includes("@") && company.trim() && !submitting;

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);
        try {
            const payload = {
                name: name.trim(),
                email: email.trim().toLowerCase(),
                company: company.trim(),
                role: role.trim() || undefined,
                seats: seats ? parseInt(seats, 10) : undefined,
                bundle: bundle || "generic",
                message: message.trim() || undefined,
                source_url: source,
            };
            await api.post("/leads/enterprise", payload);
            setDone(true);
        } catch (err) {
            const detail = err?.response?.data?.detail;
            setError(typeof detail === "string" ? detail : "Could not submit — please try again or email enterprise@ithr.online");
        } finally {
            setSubmitting(false);
        }
    };

    if (done) {
        return (
            <div data-testid="enterprise-lead-success" className="text-center py-6">
                <div className="w-12 h-12 rounded-full bg-brand/10 flex items-center justify-center mx-auto mb-4">
                    <Check className="w-6 h-6 text-brand" />
                </div>
                <h4 className="font-serif text-xl mb-2">Thanks &mdash; we&rsquo;ve got your message.</h4>
                <p className="text-sm text-muted-foreground mb-6 max-w-sm mx-auto">
                    A confirmation email is on its way. Someone from the ITHR Academy team will reply inside one working day.
                </p>
                {onDone && (
                    <button onClick={onDone} className="btn-outline text-sm" data-testid="enterprise-lead-success-close">
                        Close
                    </button>
                )}
            </div>
        );
    }

    return (
        <form onSubmit={submit} className="space-y-4" data-testid="enterprise-lead-form">
            <div className="grid md:grid-cols-2 gap-4">
                <Field label="Full name" required>
                    <input
                        type="text"
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Priya Iyer"
                        data-testid="lead-name"
                        className={inputCls}
                    />
                </Field>
                <Field label="Work email" required>
                    <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="priya@company.com"
                        data-testid="lead-email"
                        className={inputCls}
                    />
                </Field>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
                <Field label="Company" required>
                    <input
                        type="text"
                        required
                        value={company}
                        onChange={(e) => setCompany(e.target.value)}
                        placeholder="Acme Corp"
                        data-testid="lead-company"
                        className={inputCls}
                    />
                </Field>
                <Field label="Role (optional)">
                    <input
                        type="text"
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                        placeholder="Head of People Ops"
                        data-testid="lead-role"
                        className={inputCls}
                    />
                </Field>
            </div>
            <Field label="Approx seats needed (optional)">
                <input
                    type="number"
                    min="1"
                    max="100000"
                    value={seats}
                    onChange={(e) => setSeats(e.target.value.replace(/[^\d]/g, ""))}
                    placeholder="25"
                    data-testid="lead-seats"
                    className={inputCls}
                />
            </Field>
            <Field label="What are you exploring? (optional)">
                <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    rows={4}
                    placeholder="A short note about your goals, timeline, and any constraints…"
                    data-testid="lead-message"
                    maxLength={2000}
                    className={`${inputCls} leading-relaxed resize-y`}
                />
                <div className="text-[10px] text-muted-foreground text-right mt-1">
                    {message.length}/2000
                </div>
            </Field>
            {error && (
                <div className="text-sm text-destructive" data-testid="lead-error">
                    {error}
                </div>
            )}
            <div className="flex items-center justify-between gap-3 pt-2 border-t border-border">
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5" />
                    Bundle: <code className="text-brand normal-case">{BUNDLE_LABEL[bundle] || "Enterprise consultation"}</code>
                </div>
                <button
                    type="submit"
                    disabled={!canSend}
                    data-testid="lead-submit"
                    className="btn-primary"
                >
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Send inquiry</>}
                </button>
            </div>
        </form>
    );
}

const inputCls =
    "w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand";

function Field({ label, required, children }) {
    return (
        <div>
            <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">
                {label}
                {required && <span className="text-destructive"> *</span>}
            </label>
            {children}
        </div>
    );
}
