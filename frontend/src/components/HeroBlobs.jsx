/**
 * Reusable aiilm-style blob hero background.
 * Renders 3-4 soft floating orbs behind the hero + a faint diamond pattern.
 * Absolutely positioned, non-interactive — place inside a `relative overflow-hidden` section.
 */
export default function HeroBlobs({ variant = "warm" }) {
    const configs = {
        warm: [
            { cls: "blob-yellow", w: 340, h: 340, top: 40,  right: -60 },
            { cls: "blob-pink",   w: 260, h: 260, top: 320, left: 200 },
            { cls: "blob-blue",   w: 240, h: 240, bottom: -40, left: -40 },
            { cls: "blob-purple", w: 280, h: 280, top: 180, right: 200, delay: "6s" },
        ],
        cool: [
            { cls: "blob-blue",   w: 380, h: 380, top: 0, left: -80 },
            { cls: "blob-purple", w: 300, h: 300, top: 200, right: -60, delay: "3s" },
            { cls: "blob-pink",   w: 220, h: 220, bottom: 20, right: 240, delay: "6s" },
        ],
        gold: [
            { cls: "blob-yellow", w: 380, h: 380, top: -40, right: -80 },
            { cls: "blob-pink",   w: 240, h: 240, top: 260, left: 120, delay: "3s" },
            { cls: "blob-purple", w: 260, h: 260, bottom: -20, left: -20, delay: "6s" },
        ],
    };
    const blobs = configs[variant] || configs.warm;
    return (
        <>
            {blobs.map((b, i) => (
                <div
                    key={i}
                    className={`blob ${b.cls}`}
                    style={{
                        width: b.w, height: b.h,
                        top: b.top, right: b.right, bottom: b.bottom, left: b.left,
                        animationDelay: b.delay || `${i}s`,
                    }}
                />
            ))}
            <div
                className="absolute inset-0 opacity-[0.04] pointer-events-none"
                style={{
                    backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 60 60'><g stroke='%231f2430' fill='none' stroke-width='1'><path d='M30 4l26 26-26 26L4 30z'/></g></svg>\")",
                }}
            />
        </>
    );
}
