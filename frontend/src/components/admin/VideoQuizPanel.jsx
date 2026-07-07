import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Clapperboard, Plus, Trash2, Loader2, Save } from "lucide-react";
import { toast } from "sonner";

const EMPTY_FORM = { timestamp_sec: "", question: "", options: ["", "", "", ""], correct_index: 0 };

export default function VideoQuizPanel() {
    const [courses, setCourses] = useState([]);
    const [courseSlug, setCourseSlug] = useState("");
    const [course, setCourse] = useState(null);
    const [lessonId, setLessonId] = useState("");
    const [videoUrl, setVideoUrl] = useState("");
    const [rows, setRows] = useState([]);
    const [form, setForm] = useState(EMPTY_FORM);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        api.get("/courses").then((r) => setCourses(r.data || []));
    }, []);

    useEffect(() => {
        if (!courseSlug) { setCourse(null); setLessonId(""); return; }
        api.get(`/courses/${courseSlug}`).then((r) => { setCourse(r.data); setLessonId(""); });
    }, [courseSlug]);

    const lessons = (course?.modules || []).flatMap((m) =>
        (m.lessons || []).map((l) => ({ ...l, moduleTitle: m.title }))
    );
    const lesson = lessons.find((l) => l.id === lessonId);

    useEffect(() => {
        if (!lessonId) { setRows([]); setVideoUrl(""); return; }
        setVideoUrl(lesson?.video_url || "");
        api.get(`/admin/video-checkpoints?lesson_id=${lessonId}`).then((r) => setRows(r.data.rows || []));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lessonId]);

    const saveVideo = async () => {
        setBusy(true);
        try {
            await api.put(`/admin/lessons/${lessonId}/video`, { video_url: videoUrl || null });
            toast.success("Lesson video updated");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to update video");
        } finally { setBusy(false); }
    };

    const addCheckpoint = async () => {
        setBusy(true);
        try {
            const res = await api.post("/admin/video-checkpoints", {
                course_id: course.id,
                lesson_id: lessonId,
                timestamp_sec: Number(form.timestamp_sec),
                question: form.question,
                options: form.options.filter((o) => o.trim()),
                correct_index: Number(form.correct_index),
            });
            setRows((prev) => [...prev, res.data].sort((a, b) => a.timestamp_sec - b.timestamp_sec));
            setForm(EMPTY_FORM);
            toast.success("Checkpoint added");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to add checkpoint");
        } finally { setBusy(false); }
    };

    const remove = async (id) => {
        await api.delete(`/admin/video-checkpoints/${id}`);
        setRows((prev) => prev.filter((r) => r.id !== id));
        toast.success("Checkpoint deleted");
    };

    const setOption = (i, val) => setForm((f) => ({ ...f, options: f.options.map((o, j) => (j === i ? val : o)) }));

    return (
        <div data-testid="video-quiz-panel">
            <div className="flex items-center gap-3 mb-6">
                <Clapperboard className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl leading-none">Video quizzes</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6 max-w-3xl">
                <select value={courseSlug} onChange={(e) => setCourseSlug(e.target.value)} data-testid="vq-course-select" className="bg-surface-alt border border-border rounded-sm text-sm px-3 py-2">
                    <option value="">Select course…</option>
                    {courses.map((c) => <option key={c.slug} value={c.slug}>{c.title}</option>)}
                </select>
                <select value={lessonId} onChange={(e) => setLessonId(e.target.value)} disabled={!course} data-testid="vq-lesson-select" className="bg-surface-alt border border-border rounded-sm text-sm px-3 py-2">
                    <option value="">Select lesson…</option>
                    {lessons.map((l) => <option key={l.id} value={l.id}>{`${l.moduleTitle} · ${l.title}`}</option>)}
                </select>
            </div>

            {lessonId && (
                <>
                    <div className="max-w-3xl mb-8">
                        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-2">Lesson video URL (mp4)</div>
                        <div className="flex gap-2">
                            <input value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} data-testid="vq-video-url" placeholder="https://…/lesson.mp4" className="flex-1 bg-surface border border-border rounded-sm px-3 py-2 text-sm" />
                            <button onClick={saveVideo} disabled={busy} data-testid="vq-save-video" className="btn-primary">
                                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4" /> Save</>}
                            </button>
                        </div>
                    </div>

                    <div className="max-w-3xl mb-8">
                        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">Checkpoints ({rows.length})</div>
                        {rows.length === 0 && <div className="text-sm text-muted-foreground mb-4">No checkpoints yet for this lesson.</div>}
                        <div className="space-y-2 mb-6">
                            {rows.map((r) => (
                                <div key={r.id} data-testid={`vq-row-${r.id}`} className="flex items-start gap-3 border border-border bg-surface px-4 py-3">
                                    <span className="font-mono text-xs text-brand shrink-0 mt-0.5">{r.timestamp_sec}s</span>
                                    <div className="flex-1 text-sm">
                                        <div className="font-medium">{r.question}</div>
                                        <div className="text-xs text-muted-foreground mt-1">
                                            {r.options.map((o, i) => (
                                                <span key={o} className={i === r.correct_index ? "text-success font-medium" : ""}>
                                                    {String.fromCharCode(65 + i)}. {o}{i < r.options.length - 1 ? "  ·  " : ""}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <button onClick={() => remove(r.id)} data-testid={`vq-delete-${r.id}`} className="text-muted-foreground hover:text-brand">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>

                        <div className="border border-border bg-surface-alt/40 p-4 space-y-3">
                            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Add checkpoint</div>
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                                <input type="number" min="0" value={form.timestamp_sec} onChange={(e) => setForm({ ...form, timestamp_sec: e.target.value })} data-testid="vq-form-timestamp" placeholder="Pause at (sec)" className="bg-surface border border-border rounded-sm px-3 py-2 text-sm" />
                                <input value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} data-testid="vq-form-question" placeholder="Question" className="md:col-span-3 bg-surface border border-border rounded-sm px-3 py-2 text-sm" />
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {form.options.map((o, i) => (
                                    <div key={`opt-${i}`} className="flex items-center gap-2">
                                        <input type="radio" name="vq-correct" checked={Number(form.correct_index) === i} onChange={() => setForm({ ...form, correct_index: i })} data-testid={`vq-form-correct-${i}`} />
                                        <input value={o} onChange={(e) => setOption(i, e.target.value)} data-testid={`vq-form-option-${i}`} placeholder={`Option ${String.fromCharCode(65 + i)}`} className="flex-1 bg-surface border border-border rounded-sm px-3 py-2 text-sm" />
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={addCheckpoint}
                                disabled={busy || !form.question || !form.timestamp_sec || form.options.filter((o) => o.trim()).length < 2}
                                data-testid="vq-form-submit"
                                className="btn-primary disabled:opacity-50"
                            >
                                <Plus className="w-4 h-4" /> Add checkpoint
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
