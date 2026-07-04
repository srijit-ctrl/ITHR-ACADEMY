import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Building2, Loader2, ArrowRight } from "lucide-react";

const INDUSTRIES = ["Banking", "Healthcare", "Manufacturing", "Retail", "Insurance", "Government", "Professional Services", "Technology", "Other"];

export default function EnterpriseSetup() {
    const navigate = useNavigate();
    const [form, setForm] = useState({ name: "", industry: "Technology", seat_count: 25, domain: "" });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await api.post("/enterprise/organizations", { ...form, seat_count: parseInt(form.seat_count) });
            navigate("/enterprise/portal");
        } catch (e) {
            setError(e.response?.data?.detail || "Failed to create organization");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container-narrow py-16">
            <div className="max-w-lg mx-auto">
                <Building2 className="w-8 h-8 text-brand mb-4" />
                <div className="overline mb-3">Enterprise Portal</div>
                <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none mb-4">Create your organization</h1>
                <p className="text-muted-foreground mb-8">Set up your team's workspace. You can invite up to 5,000 employees and see everyone's progress in one place.</p>

                <form onSubmit={submit} className="space-y-4">
                    <Field label="Organization name" required>
                        <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="setup-name" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand" placeholder="Acme Bank" />
                    </Field>

                    <Field label="Industry">
                        <select value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} data-testid="setup-industry" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand">
                            {INDUSTRIES.map((i) => <option key={i}>{i}</option>)}
                        </select>
                    </Field>

                    <Field label="Email domain (optional)">
                        <input type="text" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} data-testid="setup-domain" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand" placeholder="acme.com" />
                    </Field>

                    <Field label="Initial seat count" hint="10 – 5000. You can adjust anytime.">
                        <input type="number" min={10} max={5000} value={form.seat_count} onChange={(e) => setForm({ ...form, seat_count: e.target.value })} required data-testid="setup-seats" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand" />
                    </Field>

                    {error && <div className="text-sm text-destructive" data-testid="setup-error">{error}</div>}

                    <button type="submit" disabled={loading} data-testid="setup-submit" className="btn-primary w-full">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Create organization <ArrowRight className="w-4 h-4" /></>}
                    </button>
                </form>
            </div>
        </div>
    );
}

function Field({ label, hint, required, children }) {
    return (
        <div>
            <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">
                {label}{required && " *"}
            </label>
            {children}
            {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
        </div>
    );
}
