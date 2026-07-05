/**
 * ITHR brand assets & compound marks.
 *
 * IMPORTANT: brand guidelines mandate NO recolouring, rotation, effects, or
 * rearrangement of the logo. We render the master SVG at whatever size is
 * needed and rely on natural clear-space around it.
 */
import { ITHR_LOGO_URL, ITHR_MARK_URL, ITHR_LOGO_WHITE_URL } from "@/components/layout/Header";

/**
 * ITHR Mark — the triangle mark only. Use for tight spaces (avatars, favicons).
 */
export function ITHRMark({ size = 40, className = "", variant = "color" }) {
    const dim = typeof size === "number" ? `${size}px` : size;
    return (
        <img
            src={ITHR_MARK_URL}
            alt="ITHR Technologies"
            className={`object-contain ${className}`}
            style={{ width: dim, height: dim }}
        />
    );
}

/**
 * ITHR Lockup — the official ITHR wordmark SVG (mark + "ITHR" letters together).
 * Comes with an "· ACADEMY" sub-mark to identify the Academy sub-brand.
 *
 * variants:
 *   - `stacked` (default) — logo above ACADEMY tag line
 *   - `compact` — inline, for very tight headers
 *   - `white` — for use on navy/dark backgrounds
 */
export function ITHRLockup({ variant = "stacked", size = 44, className = "", onDark = false }) {
    const logoSrc = onDark ? ITHR_LOGO_WHITE_URL : ITHR_LOGO_URL;
    // The master logo aspect ratio is ≈ 2.7:1 (1378x510 viewBox), so width ≈ 2.7 × height.
    const logoH = typeof size === "number" ? size : parseInt(size, 10);
    const logoW = Math.round(logoH * 2.7);

    if (variant === "compact") {
        return (
            <div className={`inline-flex items-center gap-2 ${className}`}>
                <img
                    src={logoSrc}
                    alt="ITHR Technologies"
                    style={{ height: `${logoH}px`, width: `${logoW}px` }}
                    className="object-contain"
                />
            </div>
        );
    }
    return (
        <div className={`inline-flex items-center gap-3 ${className}`}>
            <img
                src={logoSrc}
                alt="ITHR Technologies"
                style={{ height: `${logoH}px`, width: `${logoW}px` }}
                className="object-contain"
            />
            <div
                className={`pl-3 border-l leading-tight ${onDark ? "border-white/25 text-white" : "border-border text-foreground"}`}
                style={{ height: `${Math.round(logoH * 0.7)}px` }}
            >
                <div className="font-sans font-semibold text-sm tracking-tight">Academy</div>
                <div className={`text-[9px] font-mono uppercase tracking-[0.2em] mt-0.5 ${onDark ? "text-white/70" : "text-muted-foreground"}`}>
                    Independent Issuer
                </div>
            </div>
        </div>
    );
}

/**
 * ITHRSeal — the ceremonial certification seal.
 * Kept for the on-certificate ceremonial use; uses brand-navy + brand-teal only.
 */
export function ITHRSeal({ size = 96, label = "Independent Issuer" }) {
    const dim = typeof size === "number" ? `${size}px` : size;
    return (
        <div className="ithr-seal" style={{ width: dim, height: dim }} data-testid="ithr-seal">
            <svg viewBox="0 0 100 100" className="ithr-seal-text absolute inset-0 w-full h-full">
                <defs>
                    <path id="circle-top" d="M 50,50 m -37,0 a 37,37 0 1,1 74,0 a 37,37 0 1,1 -74,0" />
                </defs>
                <text style={{ fontSize: 8, letterSpacing: 4, fontFamily: "Tahoma, sans-serif" }} fill="hsl(var(--brand-teal))">
                    <textPath href="#circle-top" startOffset="0">
                        {`ITHR TECHNOLOGIES · ${label.toUpperCase()} · `}
                    </textPath>
                </text>
            </svg>
            <div className="relative z-10 flex flex-col items-center justify-center leading-none">
                <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-brand-teal">Est. 2026</div>
                <ITHRMark size={Math.round(dim.replace("px", "") * 0.42)} className="mt-1.5" />
                <div className="w-6 h-px bg-brand-teal my-1.5" />
                <div className="text-[8px] font-mono uppercase tracking-[0.2em] text-brand-navy opacity-80">Academy</div>
            </div>
        </div>
    );
}
