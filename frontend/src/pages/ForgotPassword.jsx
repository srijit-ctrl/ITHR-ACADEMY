import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ArrowLeft, Loader2, MailCheck } from "lucide-react";

/**
 * Forgot Password entry page.
 *
 * Deliberately shows the SAME success screen whether the email exists or not
 * (backend already returns a generic 200 to prevent user enumeration). This
 * makes the frontend match the backend semantics — a spammer can't glean
 * whether a given email is registered.
 */
export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState(false);
    const [err, setErr] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        setErr("");
        setLoading(true);
        try {
            await api.post("/auth/forgot-password", { email: email.trim().toLowerCase() });
            setSubmitted(true);
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

    if (submitted) {
        return (
            <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16">
                <div className="w-full max-w-md text-center" data-testid="forgot-success">
                    <div className="w-14 h-14 mx-auto mb-6 bg-brand/10 text-brand rounded-full flex items-center justify-center">
                        <MailCheck className="w-7 h-7" />
                    </div>
                    <div className="overline mb-4">Check your inbox</div>
                    <h1 className="font-serif text-4xl tracking-tighter leading-none mb-4">
                        Reset link on the way.
                    </h1>
                    <p className="text-muted-foreground mb-2 leading-relaxed">
                        If an account exists for <b className="text-foreground">{email}</b>, we&apos;ve sent a reset link.
                    </p>
                    <p className="text-sm text-muted-foreground mb-8">
                        The link expires in 60 minutes. Don&apos;t see it? Check your spam folder, or try again in a few minutes.
                    </p>
                    <Link
                        to="/login"
                        data-testid="forgot-back-to-login"
                        className="btn-outline inline-flex items-center gap-2"
                    >
                        <ArrowLeft className="w-4 h-4" /> Back to sign in
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center container-page py-16">
            <div className="w-full max-w-md">
                <div className="overline mb-4">Forgot your password?</div>
                <h1 className="font-serif text-4xl tracking-tighter leading-none mb-3">
                    Reset in one email.
                </h1>
                <p className="text-muted-foreground mb-8">
                    Enter your account email and we&apos;ll send you a secure link to set a new password.
                </p>

                <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
                    <div>
                        <label htmlFor="forgot-email" className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground block mb-2">
                            Email
                        </label>
                        <input
                            id="forgot-email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            autoComplete="email"
                            data-testid="forgot-email-input"
                            placeholder="you@company.com"
                            className="w-full bg-surface border border-border rounded-sm px-4 py-3 focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                        />
                    </div>

                    {err && (
                        <div data-testid="forgot-error" className="text-sm text-brand bg-brand/5 border border-brand/20 rounded-sm px-4 py-2">
                            {err}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading || !email.trim()}
                        data-testid="forgot-submit"
                        className="btn-primary w-full disabled:opacity-40"
                    >
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Send reset link"}
                    </button>
                </form>

                <div className="mt-8 text-sm text-muted-foreground flex items-center gap-1">
                    <ArrowLeft className="w-3 h-3" />
                    <Link to="/login" data-testid="forgot-to-login" className="text-brand hover:underline">
                        Back to sign in
                    </Link>
                </div>
            </div>
        </div>
    );
}
