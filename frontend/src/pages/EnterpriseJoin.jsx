import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Loader2, ArrowRight } from "lucide-react";

export default function EnterpriseJoin() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const [code, setCode] = useState(params.get("code") || "");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await api.post("/enterprise/organizations/join", { invite_code: code.trim() });
            navigate("/enterprise/portal");
        } catch (e) {
            setError(e.response?.data?.detail || "Failed to join");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container-narrow py-20">
            <div className="max-w-md mx-auto text-center">
                <div className="overline mb-4">Enterprise Portal</div>
                <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none mb-4">Join your team</h1>
                <p className="text-muted-foreground mb-8">Enter the invite code shared by your organization administrator.</p>

                <form onSubmit={submit} className="space-y-4 text-left">
                    <input
                        type="text"
                        value={code}
                        onChange={(e) => setCode(e.target.value.toUpperCase())}
                        placeholder="ABCD1234"
                        required
                        data-testid="join-code-input"
                        className="w-full bg-surface border border-border rounded-sm px-4 py-3 font-mono text-lg text-center tracking-[0.3em] focus:outline-none focus:border-brand"
                    />
                    {error && <div className="text-sm text-destructive text-center" data-testid="join-error">{error}</div>}
                    <button type="submit" disabled={loading || !code.trim()} data-testid="join-submit" className="btn-primary w-full">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Join organization <ArrowRight className="w-4 h-4" /></>}
                    </button>
                </form>
            </div>
        </div>
    );
}
