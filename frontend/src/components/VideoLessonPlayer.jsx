import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { CheckCircle2, XCircle, Loader2, PlayCircle } from "lucide-react";
import { toast } from "sonner";

/**
 * Video player with interactive checkpoint quizzes.
 * Pauses at DB-defined timestamps, shows an MCQ overlay; the learner must
 * answer correctly to resume. 3 wrong attempts -> lesson progress resets and
 * the video restarts from the beginning.
 */
export default function VideoLessonPlayer({ lessonId, onProgressReset }) {
    const videoRef = useRef(null);
    const [videoUrl, setVideoUrl] = useState(null);
    const [checkpoints, setCheckpoints] = useState([]);
    const [active, setActive] = useState(null);
    const [selected, setSelected] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [feedback, setFeedback] = useState(null);

    const load = useCallback(() => {
        api.get(`/lessons/${lessonId}/video-quiz`).then((r) => {
            setVideoUrl(r.data.video_url || null);
            setCheckpoints(r.data.checkpoints || []);
        }).catch(() => {});
    }, [lessonId]);

    useEffect(() => { load(); setActive(null); setFeedback(null); setSelected(null); }, [load]);

    const nextUnpassed = useCallback((time) =>
        checkpoints.find((c) => !c.passed && time >= c.timestamp_sec) || null,
    [checkpoints]);

    const onTimeUpdate = () => {
        const v = videoRef.current;
        if (!v || active) return;
        const cp = nextUnpassed(v.currentTime);
        if (cp) {
            v.pause();
            setActive(cp);
            setSelected(null);
            setFeedback(null);
        }
    };

    const onSeeking = () => {
        // Prevent skipping past an unanswered checkpoint.
        const v = videoRef.current;
        if (!v || active) return;
        const blocker = checkpoints.find((c) => !c.passed && v.currentTime > c.timestamp_sec + 0.5);
        if (blocker) v.currentTime = blocker.timestamp_sec;
    };

    const submit = async () => {
        if (selected === null || !active) return;
        setSubmitting(true);
        try {
            const res = await api.post(`/video-quiz/${active.id}/answer`, { selected_index: selected });
            const d = res.data;
            if (d.correct) {
                setCheckpoints((prev) => prev.map((c) => (c.id === active.id ? { ...c, passed: true } : c)));
                setFeedback({ type: "correct" });
                setTimeout(() => {
                    setActive(null);
                    setFeedback(null);
                    videoRef.current?.play();
                }, 900);
            } else if (d.reset) {
                setFeedback({ type: "reset" });
                toast.error("3 incorrect attempts — lesson progress reset. The video restarts from the beginning.");
                setTimeout(() => {
                    setCheckpoints((prev) => prev.map((c) => ({ ...c, passed: false, attempts_used: 0 })));
                    setActive(null);
                    setFeedback(null);
                    setSelected(null);
                    if (videoRef.current) {
                        videoRef.current.currentTime = 0;
                        videoRef.current.pause();
                    }
                    onProgressReset?.();
                }, 1600);
            } else {
                setFeedback({ type: "wrong", left: d.attempts_left });
                setSelected(null);
            }
        } finally {
            setSubmitting(false);
        }
    };

    if (!videoUrl) return null;

    return (
        <div className="relative mb-10 border border-border bg-foreground" data-testid="video-lesson-player">
            <video
                ref={videoRef}
                src={videoUrl}
                controls={!active}
                onTimeUpdate={onTimeUpdate}
                onSeeking={onSeeking}
                className="w-full block max-h-[480px]"
                data-testid="lesson-video"
            />

            <div className="bg-surface-alt px-4 py-2 border-t border-border flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                <PlayCircle className="w-3.5 h-3.5 text-brand" />
                Interactive lesson · {checkpoints.filter((c) => c.passed).length}/{checkpoints.length} checkpoints passed
            </div>

            {active && (
                <div className="absolute inset-0 z-10 bg-foreground/90 backdrop-blur-sm flex items-center justify-center p-6" data-testid="video-quiz-overlay">
                    <div className="w-full max-w-lg bg-surface border border-brand/40 p-6">
                        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand mb-3">
                            Checkpoint · answer to continue
                        </div>
                        <div className="font-serif text-xl leading-snug mb-5" data-testid="video-quiz-question">{active.question}</div>
                        <div className="space-y-2 mb-4">
                            {active.options.map((opt, i) => (
                                <button
                                    key={opt}
                                    onClick={() => setSelected(i)}
                                    data-testid={`video-quiz-option-${i}`}
                                    className={`w-full text-left px-4 py-2.5 text-sm border transition-colors ${selected === i ? "border-brand bg-brand/10" : "border-border hover:border-foreground/40"}`}
                                >
                                    <span className="font-mono text-xs text-brand mr-2">{String.fromCharCode(65 + i)}</span>
                                    {opt}
                                </button>
                            ))}
                        </div>

                        {feedback?.type === "wrong" && (
                            <div className="flex items-center gap-2 text-sm text-brand mb-3" data-testid="video-quiz-feedback">
                                <XCircle className="w-4 h-4" /> Incorrect — {feedback.left} attempt{feedback.left === 1 ? "" : "s"} left.
                            </div>
                        )}
                        {feedback?.type === "correct" && (
                            <div className="flex items-center gap-2 text-sm text-success mb-3" data-testid="video-quiz-feedback">
                                <CheckCircle2 className="w-4 h-4" /> Correct — resuming…
                            </div>
                        )}
                        {feedback?.type === "reset" && (
                            <div className="flex items-center gap-2 text-sm text-brand mb-3" data-testid="video-quiz-feedback">
                                <XCircle className="w-4 h-4" /> 3 attempts used — restarting the lesson.
                            </div>
                        )}

                        <button
                            onClick={submit}
                            disabled={selected === null || submitting || feedback?.type === "correct" || feedback?.type === "reset"}
                            data-testid="video-quiz-submit"
                            className="btn-primary w-full disabled:opacity-50"
                        >
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Submit answer"}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
