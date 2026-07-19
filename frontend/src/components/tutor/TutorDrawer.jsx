import { useEffect, useRef, useState } from "react";
import { api, streamTutor } from "@/lib/api";
import { splitTutorMeta, TUTOR_META_MARKER } from "@/components/tutor/tutorMeta";
import { TutorMetaExtras, TutorRateBar } from "@/components/tutor/TutorConversation";
import { GraduationCap, Loader2, MessageCircle, Send, X } from "lucide-react";

/**
 * The open floating panel for the AITutorPanel. Per-course tutor persona,
 * streaming chat with structured meta (suggested-action chips, knowledge
 * checks) and an in-chat quiz mode.
 */
export default function TutorDrawer({ courseSlug, onClose }) {
    const [tutor, setTutor] = useState({ name: "Aletheia", style: "" });
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [quizMode, setQuizMode] = useState(false);
    const [ratings, setRatings] = useState({});
    const scrollRef = useRef(null);

    useEffect(() => {
        api.get("/ai/tutor-profile", { params: { course_slug: courseSlug || undefined } })
            .then((r) => setTutor(r.data))
            .catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [courseSlug]);

    useEffect(() => {
        if (!sessionId) return;
        let cancelled = false;
        api.get(`/ai/tutor/ratings/${sessionId}`)
            .then((r) => { if (!cancelled) setRatings(r.data?.ratings || {}); })
            .catch(() => {});
        return () => { cancelled = true; };
    }, [sessionId]);

    const rateTurn = async (turnIndex, rating, reason) => {
        if (!sessionId) return;
        const prev = ratings[turnIndex];
        setRatings((r) => ({ ...r, [turnIndex]: rating }));
        try {
            await api.post("/ai/tutor/rate", { session_id: sessionId, turn_index: turnIndex, rating, reason: reason || null });
        } catch {
            setRatings((r) => {
                const copy = { ...r };
                if (prev) copy[turnIndex] = prev; else delete copy[turnIndex];
                return copy;
            });
        }
    };

    useEffect(() => {
        setMessages([{
            id: "welcome",
            role: "assistant",
            content: `I'm ${tutor.name} — your AI tutor. Ask me anything about agentic AI, course material, or your certification path. You can also say "quiz me" any time.`,
        }]);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tutor.name]);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    const send = async (raw, { mode } = {}) => {
        const msg = (raw || input).trim();
        if (!msg || streaming) return;
        setInput("");
        setMessages((m) => [
            ...m,
            { id: `u-${Date.now()}-${m.length}`, role: "user", content: msg },
            { id: `a-${Date.now()}-${m.length + 1}`, role: "assistant", content: "", raw: "" },
        ]);
        setStreaming(true);

        await streamTutor({
            message: msg,
            sessionId,
            courseContext: courseSlug,
            mode: mode || (quizMode ? "quiz" : null),
            onDelta: (delta) => {
                setMessages((m) => {
                    const copy = [...m];
                    const last = copy[copy.length - 1];
                    const raw2 = (last?.raw || "") + delta;
                    copy[copy.length - 1] = { ...last, raw: raw2, content: raw2.split(TUTOR_META_MARKER)[0] };
                    return copy;
                });
            },
            onDone: (payload) => {
                setStreaming(false);
                if (payload.session_id) setSessionId(payload.session_id);
                setMessages((m) => {
                    const copy = [...m];
                    const last = copy[copy.length - 1];
                    const { text, meta } = splitTutorMeta(last?.raw || last?.content || "");
                    copy[copy.length - 1] = { ...last, content: text, meta };
                    return copy;
                });
            },
            onError: (err) => {
                setStreaming(false);
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { ...copy[copy.length - 1], content: `Sorry, I hit an error: ${err.message}. Please try again.` };
                    return copy;
                });
            },
        });
    };

    const startQuiz = () => {
        setQuizMode(true);
        send("Quiz me — start a 5-question quiz now.", { mode: "quiz" });
    };

    const endQuiz = () => {
        setQuizMode(false);
        send("Let's end the quiz here — give me my summary.", { mode: "quiz" });
    };

    const lastIdx = messages.length - 1;

    return (
        <div
            className="fixed bottom-6 left-6 z-50 w-[calc(100vw-3rem)] sm:w-[440px] h-[600px] max-h-[calc(100vh-3rem)] card-flat shadow-[0_30px_80px_-20px_rgba(13,19,33,0.35)] flex flex-col overflow-hidden"
            data-testid="ai-tutor-panel"
        >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-surface-alt/60 backdrop-blur-xl">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-foreground text-background flex items-center justify-center rounded-sm">
                        <span className="font-serif text-lg">{tutor.name.charAt(0)}</span>
                    </div>
                    <div>
                        <div className="font-serif text-base leading-none" data-testid="tutor-name">{tutor.name}</div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                            {quizMode ? "Quiz mode active" : "AI Tutor · ITHR Academy"}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    {quizMode ? (
                        <button onClick={endQuiz} disabled={streaming} data-testid="tutor-end-quiz" className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand border border-brand/40 rounded-full px-3 py-1.5 hover:bg-brand hover:text-white transition-colors">
                            End quiz
                        </button>
                    ) : (
                        <button onClick={startQuiz} disabled={streaming} data-testid="tutor-start-quiz" className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-brand border border-brand/40 rounded-full px-3 py-1.5 hover:bg-brand hover:text-white transition-colors">
                            <GraduationCap className="w-3 h-3" /> Quiz me
                        </button>
                    )}
                    <button onClick={onClose} data-testid="close-ai-tutor" className="p-1.5 hover:bg-surface-alt rounded-sm transition-colors">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {(() => {
                    let assistantSeen = -1;
                    return messages.map((m, i) => {
                        let turnIndex = null;
                        if (m.role === "assistant" && m.id !== "welcome") {
                            assistantSeen += 1;
                            turnIndex = assistantSeen;
                        }
                        return (
                            <div key={m.id || `msg-${i}`}>
                                <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                                    <div
                                        className={`max-w-[85%] px-4 py-2.5 text-[14px] leading-relaxed rounded-sm whitespace-pre-wrap ${
                                            m.role === "user"
                                                ? "bg-foreground text-background"
                                                : "bg-surface-alt border border-border text-foreground"
                                        }`}
                                    >
                                        {m.content || (streaming && i === lastIdx ? (
                                            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                                        ) : "")}
                                    </div>
                                </div>
                                {m.role === "assistant" && i === lastIdx && !streaming && m.meta && (
                                    <TutorMetaExtras meta={m.meta} onAction={(a) => send(a)} />
                                )}
                                {m.role === "assistant" && turnIndex !== null && m.content && !(streaming && i === lastIdx) && (
                                    <TutorRateBar
                                        turnIndex={turnIndex}
                                        current={ratings[turnIndex]}
                                        onRate={rateTurn}
                                    />
                                )}
                            </div>
                        );
                    });
                })()}
            </div>

            <div className="border-t border-border p-3 bg-surface">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && send()}
                        placeholder={quizMode ? "Type your answer…" : "Ask about agents, RAG, governance…"}
                        disabled={streaming}
                        data-testid="ai-tutor-input"
                        className="flex-1 bg-surface-alt border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
                    />
                    <button
                        onClick={() => send()}
                        disabled={streaming || !input.trim()}
                        data-testid="ai-tutor-send"
                        className="btn-primary px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                    <MessageCircle className="w-3 h-3" /> Streaming · Adaptive teaching · ITHR Academy
                </div>
            </div>
        </div>
    );
}
