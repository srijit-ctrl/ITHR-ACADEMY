import { useState, useRef, useEffect } from "react";
import { streamTutor } from "@/lib/api";
import { Sparkles, Send, Loader2, HelpCircle, Lightbulb, Layers, X } from "lucide-react";

/**
 * InlineTutor — embedded in the lesson pane. Compact widget that seeds context-aware
 * quick prompts (explain, example, quiz-me) and streams answers inline. Reuses the
 * existing /api/ai/tutor endpoint by passing `courseContext` and the lesson metadata
 * concatenated into the user message.
 */
export default function InlineTutor({ courseSlug, lesson, moduleTitle }) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    // Reset transient state when the user moves to a different lesson
    useEffect(() => {
        setMessages([]);
        setSessionId(null);
    }, [lesson?.id]);

    const QUICK_PROMPTS = [
        { icon: HelpCircle, label: "Explain simply", text: `Explain the key idea of "${lesson?.title}" in plain language for a busy executive.` },
        { icon: Lightbulb, label: "Real-world example", text: `Give me a concrete real-world example that demonstrates the concepts in "${lesson?.title}".` },
        { icon: Layers, label: "Quiz me", text: `Ask me 3 tough questions to check my understanding of "${lesson?.title}", one at a time. Wait for my answer before revealing the next.` },
    ];

    const send = async (text) => {
        const raw = (text || input).trim();
        if (!raw || streaming) return;
        setInput("");

        // Prepend lesson context so Aletheia knows what's on screen.
        const contextMsg = [
            `Current lesson: "${lesson?.title}"`,
            moduleTitle ? `Module: ${moduleTitle}` : null,
            "Learner question:",
            raw,
        ].filter(Boolean).join("\n");

        setMessages((m) => [
            ...m,
            { id: `u-${Date.now()}-${m.length}`, role: "user", content: raw },
            { id: `a-${Date.now()}-${m.length + 1}`, role: "assistant", content: "" },
        ]);
        setStreaming(true);

        await streamTutor({
            message: contextMsg,
            sessionId,
            courseContext: courseSlug,
            onDelta: (delta) => {
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + delta };
                    return copy;
                });
            },
            onDone: (p) => {
                setStreaming(false);
                if (p.session_id) setSessionId(p.session_id);
            },
            onError: (err) => {
                setStreaming(false);
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { role: "assistant", content: `Sorry — ${err.message}` };
                    return copy;
                });
            },
        });
    };

    return (
        <div className="mt-12 border-t border-border pt-10" data-testid="inline-tutor">
            <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-foreground text-background flex items-center justify-center rounded-sm">
                        <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="font-serif text-lg leading-none">Ask Aletheia about this lesson</div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                            Contextual AI Tutor · streaming
                        </div>
                    </div>
                </div>
                {messages.length > 0 && (
                    <button
                        data-testid="inline-tutor-reset"
                        onClick={() => { setMessages([]); setSessionId(null); }}
                        className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-brand flex items-center gap-1"
                    >
                        <X className="w-3 h-3" /> Clear
                    </button>
                )}
            </div>

            {/* Quick prompts */}
            {messages.length === 0 && !open && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
                    {QUICK_PROMPTS.map((qp, i) => (
                        <button
                            key={qp.label}
                            data-testid={`inline-tutor-quick-${i}`}
                            onClick={() => { setOpen(true); send(qp.text); }}
                            className="card-sharp p-3 text-left group"
                        >
                            <qp.icon className="w-3.5 h-3.5 text-brand mb-1.5" />
                            <div className="text-xs font-mono uppercase tracking-[0.15em] text-foreground">{qp.label}</div>
                        </button>
                    ))}
                </div>
            )}

            {/* Messages */}
            {(open || messages.length > 0) && (
                <div
                    ref={scrollRef}
                    className="border border-border bg-surface-alt/30 max-h-[420px] overflow-y-auto p-5 space-y-4"
                    data-testid="inline-tutor-conversation"
                >
                    {messages.length === 0 && (
                        <p className="text-sm text-muted-foreground italic">Ask a question below — I have the full lesson context.</p>
                    )}
                    {messages.map((m, i) => (
                        <div key={m.id || `msg-${i}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div
                                className={`max-w-[85%] px-4 py-2.5 text-[14px] leading-relaxed rounded-sm whitespace-pre-wrap ${
                                    m.role === "user"
                                        ? "bg-foreground text-background"
                                        : "bg-surface border border-border"
                                }`}
                            >
                                {m.content || (streaming && i === messages.length - 1 ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" /> : "")}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Input */}
            <div className="mt-4 flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (setOpen(true), send())}
                    onFocus={() => setOpen(true)}
                    placeholder={`Ask about "${lesson?.title || "this lesson"}"…`}
                    disabled={streaming}
                    data-testid="inline-tutor-input"
                    className="flex-1 bg-surface-alt border border-border rounded-sm px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
                />
                <button
                    onClick={() => { setOpen(true); send(); }}
                    disabled={streaming || !input.trim()}
                    data-testid="inline-tutor-send"
                    className="btn-primary"
                >
                    {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Ask</>}
                </button>
            </div>
        </div>
    );
}
