import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { X, Gift, ArrowRight, Sparkles } from "lucide-react";

const DISMISS_KEY = "ithr_inaugural_flasher_dismissed_v2";

export default function InauguralFlasher() {
    const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISS_KEY) === "1");
    const [visible, setVisible] = useState(false);
    const [seats, setSeats] = useState(null);

    useEffect(() => {
        if (dismissed) return;
        const t = setTimeout(() => setVisible(true), 900);
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/trust/founding-seats`)
            .then((r) => setSeats(r.data))
            .catch(() => {});
        return () => clearTimeout(t);
    }, [dismissed]);

    if (dismissed) return null;

    const dismiss = () => {
        localStorage.setItem(DISMISS_KEY, "1");
        setDismissed(true);
    };

    return (
        <div
            data-testid="inaugural-flasher"
            className="fixed z-[70] bottom-4 right-4 left-4 sm:left-auto sm:bottom-24 sm:right-6 sm:w-[380px]"
            style={{
                transition: "opacity 0.6s ease, transform 0.6s cubic-bezier(0.16,1,0.3,1)",
                opacity: visible ? 1 : 0,
                transform: visible ? "translateY(0)" : "translateY(60px)",
                pointerEvents: visible ? "auto" : "none",
            }}
        >
            <style>{`
                @keyframes flasher-float { 0%, 100% { transform: translateY(0) rotate(-6deg); } 50% { transform: translateY(-10px) rotate(-2deg); } }
                @keyframes flasher-glow { 0%, 100% { box-shadow: 0 12px 40px rgba(16,31,58,0.55), 0 0 0 1px rgba(198,161,90,0.55), 0 0 26px rgba(198,161,90,0.35); } 50% { box-shadow: 0 12px 40px rgba(16,31,58,0.55), 0 0 0 1px rgba(228,206,154,0.9), 0 0 44px rgba(198,161,90,0.6); } }
                @keyframes flasher-shine { 0% { transform: translateX(-140%) skewX(-18deg); } 55%, 100% { transform: translateX(320%) skewX(-18deg); } }
                .flasher-card { animation: flasher-glow 2.6s ease-in-out infinite; }
                .flasher-medallion { animation: flasher-float 3.5s ease-in-out infinite; filter: drop-shadow(0 10px 18px rgba(0,0,0,0.45)); }
                .flasher-cta-shine { position: absolute; top: 0; bottom: 0; width: 40%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent); animation: flasher-shine 2.8s ease-in-out infinite; }
            `}</style>

            <div
                className="flasher-card relative rounded-2xl overflow-visible"
                style={{ background: "linear-gradient(150deg, #101F3A 0%, #16335E 60%, #0D1A31 100%)" }}
            >
                {/* Floating medallion overlapping the card */}
                <img
                    src="/assets/offer-medallion.png"
                    alt="Free certification medallion"
                    className="flasher-medallion absolute -top-10 -left-5 w-24 h-24 sm:w-28 sm:h-28 select-none pointer-events-none z-10"
                    draggable={false}
                />

                <button
                    onClick={dismiss}
                    data-testid="flasher-dismiss"
                    aria-label="Dismiss offer"
                    className="absolute right-2.5 top-2.5 p-1.5 rounded-full text-white/50 hover:text-white hover:bg-white/10 transition-colors z-20"
                >
                    <X className="w-4 h-4" />
                </button>

                <div className="relative rounded-2xl overflow-hidden px-5 pt-5 pb-5">
                    <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: "linear-gradient(90deg, transparent, #C6A15A, #E4CE9A, #C6A15A, transparent)" }} />

                    <div className="pl-20 sm:pl-24 min-h-[60px]">
                        <span
                            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[9px] font-mono font-semibold uppercase tracking-[0.18em]"
                            style={{ background: "rgba(198,161,90,0.16)", color: "#E4CE9A", border: "1px solid rgba(198,161,90,0.45)" }}
                            data-testid="flasher-badge"
                        >
                            <Sparkles className="w-3 h-3" />
                            Inaugural Launch Offer
                        </span>
                        <h3 className="mt-2 text-white font-bold text-lg leading-tight" data-testid="flasher-headline">
                            Full Course + Certification{" "}
                            <span style={{ color: "#E4CE9A" }}>FREE</span>
                        </h3>
                    </div>

                    <p className="mt-3 text-[13px] leading-snug text-white/80" data-testid="flasher-message">
                        Exclusively for the first <b style={{ color: "#E4CE9A" }}>500 joiners</b>.
                        <span className="mx-1.5 text-white/40">·</span>
                        <Gift className="inline w-3.5 h-3.5 -mt-0.5 mr-1" style={{ color: "#E4CE9A" }} />
                        Earn up to <b style={{ color: "#E4CE9A" }}>5 bonus courses</b> through referrals.
                    </p>

                    {seats && (
                        <div className="mt-3.5" data-testid="flasher-seat-counter">
                            <div className="flex items-baseline justify-between text-[11px] font-mono uppercase tracking-[0.14em]">
                                <span className="text-white/60">Seats claimed</span>
                                <span style={{ color: "#E4CE9A" }} data-testid="flasher-seat-count">
                                    <b className="text-sm">{seats.claimed}</b> / {seats.total}
                                </span>
                            </div>
                            <div className="mt-1.5 h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.12)" }}>
                                <div
                                    className="h-full rounded-full"
                                    style={{
                                        width: `${Math.max(2, (seats.claimed / seats.total) * 100)}%`,
                                        background: "linear-gradient(90deg, #C6A15A, #E4CE9A)",
                                        transition: "width 1s ease-out",
                                    }}
                                />
                            </div>
                            <p className="mt-1 text-[10px] text-white/50 font-mono">
                                Only <b style={{ color: "#E4CE9A" }}>{seats.remaining}</b> free seats left
                            </p>
                        </div>
                    )}

                    <Link
                        to="/register"
                        data-testid="flasher-cta"
                        className="relative overflow-hidden mt-4 w-full inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-bold transition-transform hover:scale-[1.03]"
                        style={{ background: "linear-gradient(135deg, #E4CE9A, #C6A15A)", color: "#101F3A" }}
                    >
                        <span className="flasher-cta-shine" />
                        Claim my free seat
                        <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>
            </div>
        </div>
    );
}
