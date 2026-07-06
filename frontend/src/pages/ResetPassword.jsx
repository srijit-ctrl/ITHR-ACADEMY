import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, ShieldCheck } from "lucide-react";

/**
 * Reset password page — reads token from ?token= query string, validates the
 * two-password form client-side, then POSTs to /api/auth/reset-password.
 * On success redirects to /login with a success toast-like banner.
 */
export default function ResetPassword() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const token = searchParams.get("token") || "";

    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [showPw, setShowPw] = useState(false);
    const [loading, setLoading] = useState(false);
    const [err, setErr] = useState("");
    const [done, setDone] = useState(false);

    useEffect(() => {
        if (!token) setErr("This reset link is missing its token. Please request a new one.");
    }, [token]);

    const rules = useMemo(() => ({
        length: password.length >= 8,
        upper: /[A-Z]/.test(password),
        digit: /\d/.test(password),
        match: password.length > 0 && password === confirm,
    }), [password, confirm]);

    const allValid = rules.length && rules.upper && rules.digit && rules.match;

    const submit = async (e) => {
        e.preventDefault();
        if (!allValid || !token) return;
        setErr("");
        setLoading(true);
        try {
            await api.post("/auth/reset-password", { token, new_password: password });
            setDone(true);
            // Auto-redirect after 2.5s so success is legible
            setTimeout(() => navigate("/login", { state: { passwordReset: true } }), 2500);
        } catch (e2) {
            const detail = e2?.response?.data?.detail;
            if (Array.isArray(detail)) {
                setErr(detail.map((d) => d.msg || String(d)).join(", "));
            } else {
                setErr(detail || "Something went wrong. Please try again.");
            }
        } finally {
            setLoading(false);
        }
    };

    if (done) {
        return (
            <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16">
                <div className="w-full max-w-md text-center" data-testid="reset-success">
                    <div className="w-14 h-14 mx-auto mb-6 bg-success/10 text-success rounded-full flex items-center justify-center">
                        <CheckCircle2 className="w-7 h-7" />
                    </div>
                    <div className="overline mb-4">Password updated</div>
                    <h1 className="font-serif text-4xl tracking-tighter leading-none mb-4">
                        You&apos;re all set.
                    </h1>
                    <p className="text-muted-foreground mb-8">
                        Redirecting you to sign in…
                    </p>
                    <Link to="/login" data-testid="reset-to-login" className="btn-primary">
                        Sign in now
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16">
            <div className="w-full max-w-md">
                <div className="w-11 h-11 mb-5 bg-brand/10 text-brand rounded-sm flex items-center justify-center">
                    <ShieldCheck className="w-5 h-5" />
                </div>
                <div className="overline mb-4">Set a new password</div>
                <h1 className="font-serif text-4xl tracking-tighter leading-none mb-3">
                    Choose a strong one.
                </h1>
                <p className="text-muted-foreground mb-8">
                    Your new password needs at least 8 characters, one uppercase letter, and one number.
                </p>

                <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
                    <div>
                        <label htmlFor="reset-pw" className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">
                            New password
                        </label>
                        <div className="relative">
                            <input
                                id="reset-pw"
                                type={showPw ? "text" : "password"}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                autoComplete="new-password"
                                data-testid="reset-password-input"
                                className="w-full bg-surface border border-border rounded-sm px-4 py-3 pr-11 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPw((v) => !v)}
                                aria-label={showPw ? "Hide password" : "Show password"}
                                data-testid="reset-toggle-visibility"
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-brand"
                            >
                                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>

                    <div>
                        <label htmlFor="reset-confirm" className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">
                            Confirm new password
                        </label>
                        <input
                            id="reset-confirm"
                            type={showPw ? "text" : "password"}
                            value={confirm}
                            onChange={(e) => setConfirm(e.target.value)}
                            required
                            autoComplete="new-password"
                            data-testid="reset-confirm-input"
                            className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                        />
                    </div>

                    <ul className="text-xs space-y-1 pl-1" data-testid="reset-rules">
                        <RuleRow ok={rules.length}>At least 8 characters</RuleRow>
                        <RuleRow ok={rules.upper}>One uppercase letter</RuleRow>
                        <RuleRow ok={rules.digit}>One number</RuleRow>
                        <RuleRow ok={rules.match}>Passwords match</RuleRow>
                    </ul>

                    {err && (
                        <div data-testid="reset-error" className="flex items-start gap-2 text-sm text-brand bg-brand/5 border border-brand/20 rounded-sm px-4 py-2.5">
                            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                            <span>{err}</span>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading || !allValid || !token}
                        data-testid="reset-submit"
                        className="btn-primary w-full disabled:opacity-40"
                    >
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Set new password"}
                    </button>
                </form>

                <div className="mt-8 text-sm text-muted-foreground">
                    Remember it after all?{" "}
                    <Link to="/login" data-testid="reset-to-login-inline" className="text-brand hover:underline">
                        Back to sign in
                    </Link>
                </div>
            </div>
        </div>
    );
}

function RuleRow({ ok, children }) {
    return (
        <li className={`flex items-center gap-2 ${ok ? "text-success" : "text-muted-foreground"}`}>
            <span className={`inline-flex w-3.5 h-3.5 rounded-full items-center justify-center ${ok ? "bg-success/15" : "bg-muted"}`}>
                {ok ? <CheckCircle2 className="w-3.5 h-3.5" /> : <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40" />}
            </span>
            {children}
        </li>
    );
}
