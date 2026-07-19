import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";
import { AlertCircle, Loader2, Sparkles, Ticket } from "lucide-react";
import { toast } from "sonner";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function googleSignIn() {
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function Register() {
    const { register } = useAuth();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [form, setForm] = useState({
        full_name: "",
        email: "",
        password: "",
        organization: "",
        title: "",
        referral_code: (searchParams.get("ref") || "").toUpperCase(),
    });
    const [err, setErr] = useState("");
    const [loading, setLoading] = useState(false);
    const [seats, setSeats] = useState(null);

    useEffect(() => {
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/trust/founding-seats`)
            .then((r) => setSeats(r.data))
            .catch(() => {});
    }, []);

    const handle = (k) => (e) => setForm({ ...form, [k]: e.target.value });

    const submit = async (e) => {
        e.preventDefault();
        setErr("");
        setLoading(true);
        try {
            const payload = { ...form };
            if (!payload.referral_code.trim()) delete payload.referral_code;
            const u = await register(payload);
            if (form.referral_code.trim()) {
                const code = form.referral_code.trim().toUpperCase();
                if (u?.paid_via_referral) {
                    toast.success(`Founding Member #${u.referral_seq} of 500 — payment waived, full access unlocked. Check your inbox for access details.`);
                } else if (code.startsWith("ITHR-")) {
                    toast.success("Referral applied — your first course (incl. certificate) is free once you enroll!");
                } else {
                    toast.info("Referral code valid, but the first-500 cap has been reached — a standard account was created.");
                }
            }
            navigate("/dashboard");
        } catch (e) {
            setErr(e.response?.data?.detail || "Registration failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16 pattern-dots">
            <div className="w-full max-w-md">
                <div className="overline mb-4">Create your account</div>
                <h1 className="font-serif text-4xl tracking-tighter leading-none mb-3">Begin your credential.</h1>
                <p className="text-muted-foreground mb-8">Free forever for the first five modules of any course.</p>

                {seats && seats.remaining > 0 && (
                    <div
                        data-testid="register-seat-counter"
                        className="mb-8 rounded-xl border border-brand/40 bg-gradient-to-br from-brand/5 via-transparent to-brand/5 px-4 py-3.5"
                    >
                        <div className="flex items-center gap-2 mb-2">
                            <Sparkles className="w-3.5 h-3.5 text-brand" />
                            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand font-semibold">
                                Founding 500 · Live counter
                            </span>
                        </div>
                        <div className="flex items-baseline justify-between mb-2">
                            <span className="text-xs text-muted-foreground">Seats claimed</span>
                            <span className="font-mono text-sm" data-testid="register-seat-count">
                                <b className="text-brand text-base">{seats.claimed}</b>
                                <span className="text-muted-foreground"> / {seats.total}</span>
                            </span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden bg-border/60">
                            <div
                                className="h-full rounded-full transition-[width] duration-1000 ease-out"
                                style={{
                                    width: `${Math.max(2, (seats.claimed / seats.total) * 100)}%`,
                                    background: "linear-gradient(90deg, #C6A15A, #E4CE9A)",
                                }}
                            />
                        </div>
                        <p className="mt-2 text-[11px] text-muted-foreground">
                            Only <b className="text-brand">{seats.remaining}</b> free seats left — full course + certificate.
                        </p>
                    </div>
                )}

                <button
                    onClick={googleSignIn}
                    type="button"
                    data-testid="register-google"
                    className="w-full flex items-center justify-center gap-3 border border-border bg-surface hover:border-foreground rounded-sm px-4 py-3 mb-6 font-medium transition-colors"
                >
                    <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                    Sign up with Google
                </button>

                <div className="flex items-center gap-3 mb-6">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">or</span>
                    <div className="flex-1 h-px bg-border" />
                </div>

                <form onSubmit={submit} className="space-y-4">
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">Full name</label>
                        <input value={form.full_name} onChange={handle("full_name")} required data-testid="register-name" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand" placeholder="Amelia Sterling" />
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">Work email</label>
                        <input type="email" value={form.email} onChange={handle("email")} required data-testid="register-email" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand" placeholder="you@company.com" />
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">Password</label>
                        <input type="password" value={form.password} onChange={handle("password")} required minLength={6} data-testid="register-password" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">Organization</label>
                            <input value={form.organization} onChange={handle("organization")} data-testid="register-org" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand" placeholder="Acme Bank" />
                        </div>
                        <div>
                            <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">Title</label>
                            <input value={form.title} onChange={handle("title")} data-testid="register-title" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand" placeholder="Director" />
                        </div>
                    </div>
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2 flex items-center gap-1.5">
                            <Ticket className="w-3 h-3 text-brand" /> Referral code <span className="normal-case tracking-normal">(optional — first 500 get full paid access)</span>
                        </label>
                        <input value={form.referral_code} onChange={handle("referral_code")} data-testid="register-referral" className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand font-mono uppercase" placeholder="FOUNDING500" />
                    </div>

                    {err && (
                        <div data-testid="register-error" className="flex items-center gap-2 text-sm text-brand bg-brand/5 border border-brand/20 rounded-sm px-4 py-2">
                            <AlertCircle className="w-4 h-4" /> {err}
                        </div>
                    )}

                    <button type="submit" disabled={loading} data-testid="register-submit" className="btn-primary w-full">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create account & begin"}
                    </button>
                </form>

                <div className="mt-8 text-sm text-muted-foreground">
                    Already have an account?{" "}
                    <Link to="/login" data-testid="register-to-login" className="text-brand hover:underline">Sign in</Link>
                </div>
            </div>
        </div>
    );
}
