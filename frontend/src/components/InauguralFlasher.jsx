import { useState } from "react";
import { Link } from "react-router-dom";
import { X, GraduationCap, Gift, ArrowRight } from "lucide-react";

const DISMISS_KEY = "ithr_inaugural_flasher_dismissed_v1";

export default function InauguralFlasher() {
    const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISS_KEY) === "1");
    if (dismissed) return null;

    const dismiss = () => {
        localStorage.setItem(DISMISS_KEY, "1");
        setDismissed(true);
    };

    return (
        <div className="relative overflow-hidden" data-testid="inaugural-flasher" style={{ background: "linear-gradient(100deg, #101F3A 0%, #16335E 55%, #101F3A 100%)" }}>
            <style>{`
                @keyframes flasher-shine {
                    0% { transform: translateX(-120%) skewX(-18deg); }
                    60%, 100% { transform: translateX(340%) skewX(-18deg); }
                }
                @keyframes flasher-pulse {
                    0%, 100% { box-shadow: 0 0 0 0 rgba(198,161,90,0.65); }
                    50% { box-shadow: 0 0 0 6px rgba(198,161,90,0); }
                }
                .flasher-shine-bar {
                    position: absolute; top: 0; bottom: 0; width: 18%;
                    background: linear-gradient(90deg, transparent, rgba(228,206,154,0.22), transparent);
                    animation: flasher-shine 4.5s ease-in-out infinite;
                    pointer-events: none;
                }
                .flasher-dot { animation: flasher-pulse 1.8s ease-out infinite; }
            `}</style>
            <div className="flasher-shine-bar" />
            <div className="absolute inset-x-0 top-0 h-[2px]" style={{ background: "linear-gradient(90deg, transparent, #C6A15A, #E4CE9A, #C6A15A, transparent)" }} />
            <div className="absolute inset-x-0 bottom-0 h-[2px]" style={{ background: "linear-gradient(90deg, transparent, #C6A15A, #E4CE9A, #C6A15A, transparent)" }} />

            <div className="container-page relative z-10 py-3.5 md:py-3 flex flex-col md:flex-row items-center justify-center gap-2.5 md:gap-6 text-center md:text-left">
                <span className="inline-flex items-center gap-2 shrink-0 rounded-full px-3 py-1 text-[10px] font-mono font-semibold uppercase tracking-[0.18em]"
                    style={{ background: "rgba(198,161,90,0.14)", color: "#E4CE9A", border: "1px solid rgba(198,161,90,0.45)" }}
                    data-testid="flasher-badge">
                    <span className="flasher-dot w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#E4CE9A" }} />
                    Inaugural Launch Offer
                </span>

                <p className="text-[13px] md:text-sm leading-snug text-white/90 max-w-2xl" data-testid="flasher-message">
                    <GraduationCap className="inline w-4 h-4 -mt-0.5 mr-1" style={{ color: "#E4CE9A" }} />
                    <b className="text-white">First full course + official certification FREE</b> for the first{" "}
                    <b style={{ color: "#E4CE9A" }}>500 joiners</b>
                    <span className="mx-2 text-white/40">·</span>
                    <Gift className="inline w-4 h-4 -mt-0.5 mr-1" style={{ color: "#E4CE9A" }} />
                    earn up to <b style={{ color: "#E4CE9A" }}>5 bonus courses</b> through referrals
                </p>

                <Link
                    to="/register"
                    data-testid="flasher-cta"
                    className="inline-flex items-center gap-1.5 shrink-0 rounded-full px-4 py-1.5 text-[13px] font-semibold transition-transform hover:scale-[1.04]"
                    style={{ background: "linear-gradient(135deg, #E4CE9A, #C6A15A)", color: "#101F3A" }}
                >
                    Claim my seat
                    <ArrowRight className="w-3.5 h-3.5" />
                </Link>
            </div>

            <button
                onClick={dismiss}
                data-testid="flasher-dismiss"
                aria-label="Dismiss offer"
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors z-20"
            >
                <X className="w-4 h-4" />
            </button>
        </div>
    );
}
