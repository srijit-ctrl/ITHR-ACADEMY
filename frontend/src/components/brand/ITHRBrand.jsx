/**
 * ITHR brand assets & compound marks.
 *
 * Renders the ITHR logotype with configurable size and variant. This is the
 * canonical branding lockup used across Header, Footer, hero, and certificates.
 */
import { ITHR_LOGO_URL } from "@/components/layout/Header";

/**
 * ITHR Mark — the raw logo square. Use for tight spaces.
 */
export function ITHRMark({ size = 40, className = "" }) {
    const dim = typeof size === "number" ? `${size}px` : size;
    return (
        <div
            className={`brand-mark flex items-center justify-center overflow-hidden rounded-sm ${className}`}
            style={{ width: dim, height: dim }}
        >
            <img
                src={ITHR_LOGO_URL}
                alt="ITHR Technologies"
                className="w-[75%] h-[75%] object-contain"
                style={{ filter: "drop-shadow(0 0 6px rgba(0,168,151,0.35))" }}
            />
        </div>
    );
}

/**
 * ITHR Lockup — the ITHR logotype + wordmark + academy sub-mark.
 * Two variants:
 *   - `stacked` (default): logo left, ITHR name + academy sub-mark stacked
 *   - `compact`: single-line, for very tight headers
 */
export function ITHRLockup({ variant = "stacked", size = 44, className = "" }) {
    if (variant === "compact") {
        return (
            <div className={`brand-lockup ${className}`}>
                <ITHRMark size={size} />
                <span className="brand-wordmark text-xl">ITHR</span>
            </div>
        );
    }
    return (
        <div className={`brand-lockup ${className}`}>
            <ITHRMark size={size} />
            <div className="flex flex-col leading-none">
                <span className="brand-wordmark text-lg md:text-xl">
                    ITHR <span className="text-brand">Academy</span>
                </span>
                <span className="brand-tag mt-1">Enterprise Agentic AI · Certification Authority</span>
            </div>
        </div>
    );
}

/**
 * ITHRSeal — the ceremonial certification seal.
 * Used prominently on hero / certificates / cornerstones.
 */
export function ITHRSeal({ size = 96, label = "Certification Authority" }) {
    const dim = typeof size === "number" ? `${size}px` : size;
    return (
        <div className="ithr-seal" style={{ width: dim, height: dim }} data-testid="ithr-seal">
            <svg viewBox="0 0 100 100" className="ithr-seal-text absolute inset-0 w-full h-full">
                <defs>
                    <path id="circle-top" d="M 50,50 m -37,0 a 37,37 0 1,1 74,0 a 37,37 0 1,1 -74,0" />
                </defs>
                <text style={{ fontSize: 8, letterSpacing: 4, fontFamily: "IBM Plex Mono, monospace" }} fill="hsl(var(--brand-gold))">
                    <textPath href="#circle-top" startOffset="0">
                        {`ITHR TECHNOLOGIES · ${label.toUpperCase()} · `}
                    </textPath>
                </text>
            </svg>
            <div className="relative z-10 flex flex-col items-center justify-center leading-none">
                <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-brand-gold">Est. 2026</div>
                <div className="font-serif text-2xl mt-1 tracking-tight">ITHR</div>
                <div className="w-6 h-px bg-brand-gold my-1.5" />
                <div className="text-[8px] font-mono uppercase tracking-[0.2em] opacity-80">Academy</div>
            </div>
        </div>
    );
}
