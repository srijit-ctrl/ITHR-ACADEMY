import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { MessageCircle, Loader2, Check, Bell, ShieldCheck } from "lucide-react";

/**
 * Learner-facing WhatsApp opt-in / opt-out card.
 *
 * Meta policy rules the shape of this component:
 *   • The checkbox MUST be unchecked by default.
 *   • The user MUST take an explicit action to opt in.
 *   • Opting out must stop future sends immediately (backend enforces).
 *
 * Rendered as a section on the learner dashboard alongside Referrals so
 * existing users can turn it on later — not only at registration.
 */
export function WhatsAppOptInPanel() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [state, setState] = useState({ whatsapp_opt_in: false, whatsapp_number: "", integration_configured: false });
    const [checkbox, setCheckbox] = useState(false);
    const [numberInput, setNumberInput] = useState("");

    useEffect(() => {
        api.get("/whatsapp/status")
            .then((r) => {
                setState(r.data);
                setCheckbox(!!r.data.whatsapp_opt_in);
                setNumberInput(r.data.whatsapp_number || "");
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const saveOptIn = async () => {
        setSaving(true);
        try {
            const r = await api.post("/whatsapp/opt-in", {
                opt_in: true,
                whatsapp_number: numberInput.trim(),
                source: "account_settings",
            });
            setState({ ...state, whatsapp_opt_in: true, whatsapp_number: r.data.whatsapp_number });
            toast.success("You're opted in — we'll only WhatsApp you about your courses.");
        } catch (err) {
            toast.error(err.response?.data?.detail || "Couldn't save. Check the number format (e.g. +9715XXXXXXXX).");
            setCheckbox(false);
        } finally {
            setSaving(false);
        }
    };

    const saveOptOut = async () => {
        setSaving(true);
        try {
            await api.post("/whatsapp/opt-in", { opt_in: false, source: "account_settings" });
            setState({ ...state, whatsapp_opt_in: false, whatsapp_number: "" });
            setNumberInput("");
            toast.success("Opted out — you'll receive no further WhatsApp messages.");
        } catch {
            toast.error("Couldn't save. Try again in a moment.");
            setCheckbox(true);
        } finally {
            setSaving(false);
        }
    };

    const toggle = (next) => {
        setCheckbox(next);
        if (next && !state.whatsapp_opt_in) return;  // opt-in requires number save click
        if (!next && state.whatsapp_opt_in) saveOptOut();
    };

    if (loading) return (
        <section className="card-flat p-6"><Loader2 className="w-4 h-4 animate-spin text-muted-foreground" /></section>
    );

    return (
        <section className="card-flat p-6 md:p-7" data-testid="whatsapp-opt-in-panel">
            <div className="flex items-baseline justify-between mb-4">
                <div className="flex items-center gap-2">
                    <MessageCircle className="w-4 h-4 text-brand" />
                    <h3 className="font-serif text-xl tracking-tight">Course reminders on WhatsApp</h3>
                </div>
                {state.whatsapp_opt_in && (
                    <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand flex items-center gap-1" data-testid="whatsapp-opt-in-status">
                        <Check className="w-3 h-3" /> Enabled
                    </span>
                )}
            </div>

            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
                Optional. Get course launches, lesson reminders, and certificate confirmations sent to your WhatsApp — never marketing, never resold. You can turn this off any time and future sends stop immediately.
            </p>

            <label className="flex items-start gap-3 cursor-pointer mb-4">
                <input
                    type="checkbox"
                    checked={checkbox}
                    onChange={(e) => toggle(e.target.checked)}
                    data-testid="whatsapp-opt-in-checkbox"
                    className="mt-1 w-4 h-4 rounded border-border accent-brand"
                />
                <span className="text-sm">
                    Send me course reminders and updates via WhatsApp.
                </span>
            </label>

            {checkbox && !state.whatsapp_opt_in && (
                <div className="space-y-3" data-testid="whatsapp-number-form">
                    <input
                        type="tel"
                        value={numberInput}
                        onChange={(e) => setNumberInput(e.target.value)}
                        placeholder="+9715XXXXXXXX"
                        data-testid="whatsapp-number-input"
                        className="w-full text-sm bg-surface border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                    />
                    <button
                        type="button"
                        onClick={saveOptIn}
                        disabled={saving || !numberInput.trim()}
                        data-testid="whatsapp-opt-in-save"
                        className="btn-primary"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Bell className="w-4 h-4" /> Save & opt in</>}
                    </button>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                        Include your country code (UAE numbers are <span className="font-mono">+971</span>). We never text you without an approved WhatsApp template.
                    </p>
                </div>
            )}

            {state.whatsapp_opt_in && (
                <div className="flex items-center justify-between border-t border-border/60 pt-3 mt-3 text-xs">
                    <span className="text-muted-foreground">
                        Sending to <b className="font-mono text-foreground">{state.whatsapp_number}</b>
                    </span>
                    <button
                        type="button"
                        onClick={saveOptOut}
                        disabled={saving}
                        data-testid="whatsapp-opt-out-button"
                        className="text-[10px] font-mono uppercase tracking-[0.15em] text-destructive hover:underline"
                    >
                        {saving ? "…" : "Opt out"}
                    </button>
                </div>
            )}

            {!state.integration_configured && (
                <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground/70 mt-3 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" /> WhatsApp is not yet live — opt-in is captured and will activate once Meta approves our templates.
                </p>
            )}
        </section>
    );
}
