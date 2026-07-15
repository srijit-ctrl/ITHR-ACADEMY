import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, ToggleLeft } from "lucide-react";
import { toast } from "sonner";

const FLAG_META = {
    registrations: { label: "New registrations", desc: "Allow new user signups (email + Google)" },
    referrals: { label: "Referral program", desc: "Referral codes, rewards and the dashboard panel" },
    ai_tutor: { label: "AI tutor", desc: "Aletheia & course tutor chat (drawer + inline)" },
    chat_quiz: { label: "In-chat quiz mode", desc: "'Quiz me' inside the tutor chat" },
    voice_io: { label: "Voice features", desc: "Whisper transcription + TTS playback" },
    checkout: { label: "Checkout / payments", desc: "Stripe checkout session creation" },
    intelligence_desk: { label: "Intelligence desk", desc: "AI industry-signal briefings" },
};

export default function FeatureFlagsPanel() {
    const [flags, setFlags] = useState(null);
    const [saving, setSaving] = useState("");

    useEffect(() => {
        api.get("/admin/flags").then((r) => setFlags(r.data)).catch(() => {});
    }, []);

    const toggle = async (name) => {
        const next = !flags[name];
        setSaving(name);
        try {
            const r = await api.put("/admin/flags", { [name]: next });
            setFlags(r.data);
            toast.success(`${FLAG_META[name]?.label || name} ${next ? "enabled" : "disabled"}`);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Update failed");
        } finally {
            setSaving("");
        }
    };

    if (!flags) return <div className="py-12"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></div>;

    return (
        <div className="card-flat p-6" data-testid="feature-flags-panel">
            <div className="flex items-center gap-2 mb-2">
                <ToggleLeft className="w-4 h-4 text-brand" />
                <h3 className="font-serif text-xl tracking-tight">Feature flags</h3>
            </div>
            <p className="text-xs text-muted-foreground mb-6">Toggles take effect within ~15 seconds. Backend endpoints return 403 while disabled; key UI surfaces hide automatically.</p>
            <div className="space-y-1">
                {Object.keys(FLAG_META).map((name) => (
                    <div key={name} className="flex items-center justify-between py-3 border-b border-border/50" data-testid={`flag-row-${name}`}>
                        <div>
                            <div className="text-sm font-medium">{FLAG_META[name].label}</div>
                            <div className="text-xs text-muted-foreground">{FLAG_META[name].desc}</div>
                        </div>
                        <button
                            onClick={() => toggle(name)}
                            disabled={saving === name}
                            data-testid={`flag-toggle-${name}`}
                            role="switch"
                            aria-checked={flags[name] !== false}
                            className={`relative w-11 h-6 rounded-full transition-colors ${flags[name] !== false ? "bg-brand" : "bg-border"}`}
                        >
                            <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${flags[name] !== false ? "translate-x-5" : "translate-x-0.5"}`} style={{ left: 0 }} />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
