import { useEffect, useRef, useState } from "react";
import { Headphones, Loader2, Pause } from "lucide-react";
import { API_BASE } from "@/lib/api";

/**
 * "Listen 30s" course preview — pulls a cached TTS pitch from
 *   GET /api/catalog/{slug}/preview-audio  (base64 MP3, hydrated on first
 *   click, then instant on subsequent plays). Placed in the CourseCard
 *   footer + CourseDetail hero.
 */
export default function CoursePreviewButton({ course, variant = "compact" }) {
    const [state, setState] = useState("idle"); // idle | loading | playing | error
    const audioRef = useRef(null);

    // Cleanup on unmount
    useEffect(() => () => { try { audioRef.current?.pause(); } catch { /* noop */ } }, []);

    const stop = () => {
        try {
            audioRef.current?.pause();
            audioRef.current = null;
        } catch { /* noop */ }
        setState("idle");
    };

    const play = async (e) => {
        e?.preventDefault?.();
        e?.stopPropagation?.();
        if (state === "playing") { stop(); return; }
        if (state === "loading") return;

        setState("loading");
        try {
            const res = await fetch(`${API_BASE}/courses/${course.slug}/preview-audio`);
            if (!res.ok) throw new Error(`preview ${res.status}`);
            const data = await res.json();
            const audio = new Audio(`data:${data.mime || "audio/mpeg"};base64,${data.audio_b64}`);
            audioRef.current = audio;
            audio.onended = () => setState("idle");
            audio.onerror = () => setState("error");
            await audio.play();
            setState("playing");
        } catch (err) {
            console.error("preview audio", err);
            setState("error");
            setTimeout(() => setState("idle"), 1800);
        }
    };

    const isCompact = variant === "compact";
    const base = "inline-flex items-center gap-1.5 font-mono uppercase transition-colors";
    const style = isCompact
        ? `${base} text-[10px] tracking-[0.15em] text-muted-foreground hover:text-brand`
        : `${base} text-xs tracking-[0.15em] px-3 py-1.5 rounded-full border border-border bg-surface-alt hover:border-brand hover:text-brand`;

    const icon = state === "loading"
        ? <Loader2 className="w-3 h-3 animate-spin" />
        : state === "playing"
            ? <Pause className="w-3 h-3" />
            : <Headphones className="w-3 h-3" />;

    const label = state === "playing" ? "Stop" : state === "error" ? "Try again" : "Listen 30s";

    return (
        <button
            type="button"
            onClick={play}
            data-testid={`course-preview-audio-${course.slug}`}
            aria-label={`Play 30-second audio preview of ${course.title}`}
            className={style}
        >
            {icon}
            <span>{label}</span>
        </button>
    );
}
