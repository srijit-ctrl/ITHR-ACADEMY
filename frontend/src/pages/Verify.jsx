import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ShieldCheck, XCircle, Search, Loader2 } from "lucide-react";

export default function Verify() {
    const { certId } = useParams();
    const [query, setQuery] = useState(certId || "");
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const verify = async (id) => {
        setLoading(true);
        setError("");
        setResult(null);
        try {
            const res = await api.get(`/certificates/verify/${id}`);
            setResult(res.data.certificate);
        } catch (e) {
            setError("No credential found with that ID.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (certId) verify(certId);
    }, [certId]);

    return (
        <div className="container-narrow py-20">
            <div className="text-center mb-12">
                <div className="overline mb-4">Public Verification Portal</div>
                <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-4">Verify a credential</h1>
                <p className="text-muted-foreground text-lg">Enter any Agentic AI Academy credential ID to verify its authenticity.</p>
            </div>

            <form onSubmit={(e) => { e.preventDefault(); verify(query.trim()); }} className="flex gap-3 mb-8">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="e.g. EAIA-2026-ABC123"
                        data-testid="verify-input"
                        className="w-full pl-10 pr-4 py-3 border border-border bg-surface rounded-sm font-mono focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                    />
                </div>
                <button type="submit" disabled={loading || !query.trim()} data-testid="verify-submit" className="btn-primary">
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify"}
                </button>
            </form>

            {error && (
                <div data-testid="verify-error" className="card-flat p-8 text-center">
                    <XCircle className="w-8 h-8 text-brand mx-auto mb-4" />
                    <p className="font-serif text-xl mb-2">Credential not found</p>
                    <p className="text-sm text-muted-foreground">{error}</p>
                </div>
            )}

            {result && (
                <div className="cert-beam" data-testid="verify-success">
                    <div className="bg-surface p-10">
                        <div className="flex items-center gap-3 mb-8">
                            <ShieldCheck className="w-8 h-8 text-success" />
                            <div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-success">Verified Credential</div>
                                <div className="font-serif text-xl">Authentic · Issued by Agentic AI Academy</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-sm">
                            <div>
                                <div className="overline mb-2">Awarded to</div>
                                <div className="font-serif text-2xl">{result.user_name}</div>
                            </div>
                            <div>
                                <div className="overline mb-2">Credential</div>
                                <div className="font-serif text-2xl">{result.course_title}</div>
                            </div>
                            <div>
                                <div className="overline mb-2">Score</div>
                                <div className="font-mono text-lg">{result.score}%</div>
                            </div>
                            <div>
                                <div className="overline mb-2">Issued</div>
                                <div className="font-mono text-lg">{new Date(result.issued_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</div>
                            </div>
                            <div className="md:col-span-2">
                                <div className="overline mb-2">Credential ID</div>
                                <div className="font-mono text-lg">{result.certificate_id}</div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className="mt-16 text-center text-sm text-muted-foreground">
                Employers and partners can integrate verification into applicant tracking via our{" "}
                <Link to="/enterprise" className="text-brand hover:underline">enterprise API</Link>.
            </div>
        </div>
    );
}
