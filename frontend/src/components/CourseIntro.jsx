import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Play, X, Volume2, VolumeX } from "lucide-react";

/**
 * Course intro system — Ken-Burns cinemagraph today, Sora 2 tomorrow.
 *
 * Three exports:
 *  - <CourseIntroHero />      Full-bleed autoplay on CourseDetail hero.
 *  - <CourseIntroButton />    Small compact play button (for CourseCard overlay).
 *                             Opens the lightbox on click without bubbling.
 *  - <CourseIntroLightbox />  The 10-sec looping reel modal itself; useful if
 *                             a caller wants to trigger it from anywhere.
 */

/* Full-bleed hero — autoplay, no click. Used on CourseDetail. */
export function CourseIntroHero({ course, className = "" }) {
    const hasVideo = !!course?.intro_video_url;
    return (
        <div className={`relative w-full h-full overflow-hidden ${className}`} data-testid="course-intro-hero">
            {hasVideo ? (
                <video
                    src={course.intro_video_url}
                    autoPlay
                    muted
                    loop
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover"
                    data-testid="course-intro-video"
                />
            ) : (
                <img
                    src={course?.hero_url || course?.thumbnail_url}
                    alt=""
                    className="absolute inset-0 w-full h-full object-cover course-intro-cinemagraph"
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                    data-testid="course-intro-cinemagraph"
                />
            )}
        </div>
    );
}

/* Compact play chip. Renders as a small pill, opens the lightbox. */
export function CourseIntroButton({ course, className = "" }) {
    const [open, setOpen] = useState(false);
    return (
        <>
            <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true); }}
                className={`inline-flex items-center gap-1.5 rounded-full bg-white/95 text-brand-navy px-3 py-1.5 shadow-lg hover:scale-105 transition-transform ${className}`}
                data-testid={`course-intro-play-${course?.slug || course?.id}`}
                aria-label={`Play intro for ${course?.title}`}
            >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span className="text-[10px] font-mono uppercase tracking-[0.15em]">10-sec intro</span>
            </button>
            {open && <CourseIntroLightbox course={course} onClose={() => setOpen(false)} />}
        </>
    );
}

export function CourseIntroLightbox({ course, onClose }) {
    const [muted, setMuted] = useState(true);
    const videoRef = useRef(null);
    const hasVideo = !!course?.intro_video_url;

    // Auto-close after 12s (10s clip + a small buffer) so the lightbox never
    // squats on the page if the user forgets it — matches the "10 second"
    // product framing.
    useEffect(() => {
        const t = setTimeout(onClose, 12000);
        return () => clearTimeout(t);
    }, [onClose]);

    // ESC to close
    useEffect(() => {
        const handler = (e) => e.key === "Escape" && onClose();
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [onClose]);

    // Portal to document.body so nothing ancestor (Link.overflow-hidden,
    // group.transform, card.contain) can clip the fixed-positioned modal.
    const modal = (
        <div
            className="fixed inset-0 z-50 bg-brand-navy/85 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={onClose}
            data-testid="course-intro-lightbox"
        >
            <div className="relative w-full max-w-3xl aspect-video bg-brand-navy rounded-sm overflow-hidden shadow-2xl" onClick={(e) => e.stopPropagation()}>
                {hasVideo ? (
                    <video
                        ref={videoRef}
                        src={course.intro_video_url}
                        autoPlay
                        loop
                        muted={muted}
                        playsInline
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full relative overflow-hidden">
                        <img
                            src={course.hero_url || course.thumbnail_url}
                            alt=""
                            className="absolute inset-0 w-full h-full object-cover course-intro-cinemagraph"
                        />
                        <div className="absolute inset-0 bg-brand-navy/30" />
                    </div>
                )}

                {/* Course label overlay */}
                <div className="absolute inset-x-0 bottom-0 p-6 bg-gradient-to-t from-brand-navy/95 to-transparent text-white">
                    <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-brand-sky mb-2">
                        {course.category}
                    </div>
                    <div className="font-serif text-2xl md:text-3xl leading-tight max-w-lg">
                        {course.title}
                    </div>
                </div>

                {/* Controls */}
                <div className="absolute top-3 right-3 flex gap-2">
                    {hasVideo && (
                        <button
                            onClick={() => setMuted((m) => !m)}
                            data-testid="course-intro-mute"
                            className="p-2 rounded-full bg-white/15 hover:bg-white/25 text-white transition-colors"
                            aria-label={muted ? "Unmute" : "Mute"}
                        >
                            {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                        </button>
                    )}
                    <button
                        onClick={onClose}
                        data-testid="course-intro-close"
                        className="p-2 rounded-full bg-white/15 hover:bg-white/25 text-white transition-colors"
                        aria-label="Close"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );

    return createPortal(modal, document.body);
}
