import { useEffect, useState, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { CheckCircle2, XCircle, Loader2, ArrowRight, Clock } from "lucide-react";

export default function CheckoutSuccess() {
    const [params] = useSearchParams();
    const sessionId = params.get("session_id");
    const [state, setState] = useState({ phase: "polling", data: null, error: null });
    const pollCount = useRef(0);
    const timerRef = useRef(null);

    useEffect(() => {
        if (!sessionId) {
            setState({ phase: "error", error: "Missing session_id in URL", data: null });
            return;
        }

        const poll = async () => {
            if (pollCount.current >= 12) { // 12 * 2s = 24s max
                setState((s) => ({ ...s, phase: "timeout" }));
                return;
            }
            pollCount.current += 1;
            try {
                const res = await api.get(`/checkout/status/${sessionId}`);
                if (res.data.payment_status === "paid") {
                    setState({ phase: "paid", data: res.data, error: null });
                    return;
                }
                if (res.data.status === "expired") {
                    setState({ phase: "expired", data: res.data, error: null });
                    return;
                }
                setState({ phase: "polling", data: res.data, error: null });
                timerRef.current = setTimeout(poll, 2000);
            } catch (e) {
                setState({ phase: "error", data: null, error: e.response?.data?.detail || e.message });
            }
        };
        poll();
        return () => timerRef.current && clearTimeout(timerRef.current);
    }, [sessionId]);

    return (
        <div className="container-narrow py-20">
            {state.phase === "polling" && (
                <div className="text-center py-16" data-testid="checkout-polling">
                    <Loader2 className="w-10 h-10 animate-spin text-brand mx-auto mb-6" />
                    <div className="overline mb-3">Payment processing</div>
                    <h1 className="font-serif text-4xl tracking-tighter leading-none mb-4">
                        Confirming your enrollment…
                    </h1>
                    <p className="text-muted-foreground">
                        Verifying with Stripe. This usually takes just a few seconds.
                    </p>
                </div>
            )}

            {state.phase === "paid" && (
                <div className="text-center py-12" data-testid="checkout-success">
                    <div className="w-16 h-16 mx-auto mb-6 bg-success text-white flex items-center justify-center">
                        <CheckCircle2 className="w-8 h-8" />
                    </div>
                    <div className="overline mb-3">Payment confirmed</div>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-5">
                        Welcome to the <span className="italic text-brand">{state.data.tier}</span> tier.
                    </h1>
                    <p className="text-muted-foreground text-lg mb-8 max-w-xl mx-auto">
                        Your subscription is active. You now have full access to the catalog, unlimited AI tutor sessions, and all certification tracks in your tier.
                    </p>

                    <div className="cert-beam max-w-xl mx-auto mb-10">
                        <div className="bg-surface p-8 text-left">
                            <div className="overline mb-3">Receipt</div>
                            <div className="grid grid-cols-2 gap-6 text-sm">
                                <div>
                                    <div className="text-muted-foreground text-xs">Package</div>
                                    <div className="font-serif text-lg mt-1">{state.data.package_id.replace(/_/g, " ")}</div>
                                </div>
                                <div>
                                    <div className="text-muted-foreground text-xs">Amount charged</div>
                                    <div className="font-serif text-lg mt-1">${(state.data.amount).toFixed(2)} {state.data.currency.toUpperCase()}</div>
                                </div>
                                <div>
                                    <div className="text-muted-foreground text-xs">Tier</div>
                                    <div className="font-mono uppercase tracking-[0.15em] mt-1 text-brand">{state.data.tier}</div>
                                </div>
                                <div>
                                    <div className="text-muted-foreground text-xs">Session</div>
                                    <div className="font-mono text-xs mt-1 truncate">{sessionId}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-3 justify-center flex-wrap">
                        <Link to="/dashboard" data-testid="checkout-goto-dashboard" className="btn-primary">
                            Go to dashboard <ArrowRight className="w-4 h-4" />
                        </Link>
                        <Link to="/courses" data-testid="checkout-explore-catalog" className="btn-outline">
                            Explore catalog
                        </Link>
                    </div>
                </div>
            )}

            {state.phase === "expired" && (
                <div className="text-center py-16" data-testid="checkout-expired">
                    <XCircle className="w-12 h-12 text-brand mx-auto mb-6" />
                    <h1 className="font-serif text-4xl tracking-tighter leading-none mb-4">Session expired.</h1>
                    <p className="text-muted-foreground mb-8">Your Stripe checkout session expired before payment completed.</p>
                    <Link to="/pricing" className="btn-primary">Try again</Link>
                </div>
            )}

            {state.phase === "timeout" && (
                <div className="text-center py-16" data-testid="checkout-timeout">
                    <Clock className="w-12 h-12 text-warning mx-auto mb-6" />
                    <h1 className="font-serif text-3xl tracking-tight mb-4">Still processing…</h1>
                    <p className="text-muted-foreground mb-6">This is taking longer than usual. Your card may still be charged — please check your email for confirmation.</p>
                    <div className="flex gap-3 justify-center">
                        <button onClick={() => window.location.reload()} className="btn-outline">Refresh status</button>
                        <Link to="/dashboard" className="btn-primary">Go to dashboard</Link>
                    </div>
                </div>
            )}

            {state.phase === "error" && (
                <div className="text-center py-16" data-testid="checkout-error">
                    <XCircle className="w-12 h-12 text-destructive mx-auto mb-6" />
                    <h1 className="font-serif text-3xl tracking-tight mb-4">Something went wrong.</h1>
                    <p className="text-muted-foreground mb-6 text-sm">{state.error}</p>
                    <Link to="/pricing" className="btn-primary">Back to pricing</Link>
                </div>
            )}
        </div>
    );
}
