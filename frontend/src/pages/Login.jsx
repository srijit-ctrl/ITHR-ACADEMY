import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function googleSignIn() {
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function Login() {
    const { login, verifyMfa } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [err, setErr] = useState("");
    const [loading, setLoading] = useState(false);
    const [challengeToken, setChallengeToken] = useState(null);
    const [mfaCode, setMfaCode] = useState("");
    const showPasswordResetBanner = location.state?.passwordReset === true;

    const submit = async (e) => {
        e.preventDefault();
        setErr("");
        setLoading(true);
        try {
            const result = await login(email, password);
            if (result?.mfaRequired) {
                setChallengeToken(result.challengeToken);
                return;
            }
            const redirect = location.state?.from || "/dashboard";
            navigate(redirect);
        } catch (e) {
            setErr(e.response?.data?.detail || "Sign-in failed.");
        } finally {
            setLoading(false);
        }
    };

    const submitMfa = async (e) => {
        e.preventDefault();
        setErr("");
        setLoading(true);
        try {
            await verifyMfa(challengeToken, mfaCode);
            navigate(location.state?.from || "/dashboard");
        } catch (e) {
            setErr(e.response?.data?.detail || "Verification failed.");
        } finally {
            setLoading(false);
        }
    };

    if (challengeToken) {
        return (
            <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16 pattern-dots">
                <div className="w-full max-w-md" data-testid="mfa-challenge">
                    <div className="overline mb-4">Two-factor authentication</div>
                    <h1 className="font-serif text-4xl tracking-tighter leading-none mb-3">Enter your code.</h1>
                    <p className="text-muted-foreground mb-8">Open your authenticator app and enter the 6-digit code — or use one of your backup codes.</p>
                    <form onSubmit={submitMfa} className="space-y-4">
                        <input
                            type="text"
                            autoFocus
                            value={mfaCode}
                            onChange={(e) => setMfaCode(e.target.value)}
                            required
                            data-testid="mfa-code-input"
                            className="w-full bg-surface border border-border rounded-sm px-4 py-3 font-mono text-center text-2xl tracking-[0.5em] focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                            placeholder="000000"
                            maxLength={16}
                        />
                        {err && (
                            <div data-testid="mfa-error" className="flex items-center gap-2 text-sm text-brand bg-brand/5 border border-brand/20 rounded-sm px-4 py-2">
                                <AlertCircle className="w-4 h-4" /> {err}
                            </div>
                        )}
                        <button type="submit" disabled={loading || !mfaCode.trim()} data-testid="mfa-submit" className="btn-primary w-full">
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify & sign in"}
                        </button>
                        <button type="button" onClick={() => { setChallengeToken(null); setMfaCode(""); setErr(""); }} data-testid="mfa-back" className="text-sm text-muted-foreground hover:text-brand w-full">
                            ← Back to sign in
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16 pattern-dots">
            <div className="w-full max-w-md">
                <div className="overline mb-4">Welcome back</div>
                <h1 className="font-serif text-4xl tracking-tighter leading-none mb-3">Sign in</h1>
                <p className="text-muted-foreground mb-8">Access your dashboard, courses, and certifications.</p>

                {showPasswordResetBanner && (
                    <div data-testid="login-reset-banner" className="flex items-start gap-2 text-sm text-success bg-success/5 border border-success/20 rounded-sm px-4 py-2.5 mb-6">
                        <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                        <span>Your password has been reset. Sign in with your new password.</span>
                    </div>
                )}

                <button
                    onClick={googleSignIn}
                    type="button"
                    data-testid="login-google"
                    className="w-full flex items-center justify-center gap-3 border border-border bg-surface hover:border-foreground rounded-sm px-4 py-3 mb-6 font-medium transition-colors"
                >
                    <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                    Continue with Google
                </button>

                <div className="flex items-center gap-3 mb-6">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">or</span>
                    <div className="flex-1 h-px bg-border" />
                </div>

                <form onSubmit={submit} className="space-y-4">
                    <div>
                        <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">Email</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            data-testid="login-email"
                            className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                            placeholder="you@company.com"
                        />
                    </div>
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Password</label>
                            <Link
                                to="/forgot-password"
                                data-testid="login-forgot-password"
                                className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand hover:underline"
                            >
                                Forgot?
                            </Link>
                        </div>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            data-testid="login-password"
                            className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                        />
                    </div>

                    {err && (
                        <div data-testid="login-error" className="flex items-center gap-2 text-sm text-brand bg-brand/5 border border-brand/20 rounded-sm px-4 py-2">
                            <AlertCircle className="w-4 h-4" /> {err}
                        </div>
                    )}

                    <button type="submit" disabled={loading} data-testid="login-submit" className="btn-primary w-full">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Sign in"}
                    </button>
                </form>

                <div className="mt-8 text-sm text-muted-foreground">
                    New to the academy?{" "}
                    <Link to="/register" data-testid="login-to-register" className="text-brand hover:underline">Create an account</Link>
                </div>
            </div>
        </div>
    );
}
