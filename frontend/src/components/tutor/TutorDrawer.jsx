import { useEffect, useRef, useState } from "react";
import { streamTutor } from "@/lib/api";
import { Loader2, MessageCircle, Send, X } from "lucide-react";

const WELCOME = {
    id: "welcome",
    role: "assistant",
    content: "I'm Aletheia — your AI tutor. Ask me anything about agentic AI, course material, or your certification path.",
};

/**
 * The open floating panel for the AITutorPanel. Handles its own streaming
 * chat state so the launcher stays trivially cheap. Kept lightweight
 * (no dependency on useTutorStream hook — it uses a bare AITutorPanel copy
 * because the panel does not carry per-lesson context prepending).
 */
export default function TutorDrawer({ courseSlug, onClose }) {
    const [messages, setMessages] = useState([WELCOME]);
    const [input, setInput] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    const send = async () => {
        if (!input.trim() || streaming) return;
        const msg = input.trim();
        setInput("");
        setMessages((m) => [
            ...m,
            { id: `u-${Date.now()}-${m.length}`, role: "user", content: msg },
            { id: `a-${Date.now()}-${m.length + 1}`, role: "assistant", content: "" },
        ]);
        setStreaming(true);

        await streamTutor({
            message: msg,
            sessionId,
            courseContext: courseSlug,
            onDelta: (delta) => {
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { ...copy[copy.length - 1], content: (copy[copy.length - 1]?.content || "") + delta };
                    return copy;
                });
            },
            onDone: (payload) => {
                setStreaming(false);
                if (payload.session_id) setSessionId(payload.session_id);
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

    return (
        <div
            className="fixed bottom-6 left-6 z-50 w-[calc(100vw-3rem)] sm:w-[440px] h-[600px] max-h-[calc(100vh-3rem)] card-flat shadow-[0_30px_80px_-20px_rgba(13,19,33,0.35)] flex flex-col overflow-hidden"
            data-testid="ai-tutor-panel"
        >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-surface-alt/60 backdrop-blur-xl">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-foreground text-background flex items-center justify-center rounded-sm">
                        <span className="font-serif text-lg">A</span>
                    </div>
                    <div>
                        <div className="font-serif text-base leading-none">Aletheia</div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">AI Tutor · Sonnet 4.5</div>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    data-testid="close-ai-tutor"
                    className="p-1.5 hover:bg-surface-alt rounded-sm transition-colors"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {messages.map((m, i) => (
                    <div key={m.id || `msg-${i}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div
                            className={`max-w-[85%] px-4 py-2.5 text-[14px] leading-relaxed rounded-sm ${
                                m.role === "user"
                                    ? "bg-foreground text-background"
                                    : "bg-surface-alt border border-border text-foreground"
                            }`}
                        >
                            {m.content || (streaming && i === messages.length - 1 ? (
                                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                            ) : "")}
                        </div>
                    </div>
                ))}
            </div>

            <div className="border-t border-border p-3 bg-surface">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && send()}
                        placeholder="Ask about agents, RAG, governance…"
                        disabled={streaming}
                        data-testid="ai-tutor-input"
                        className="flex-1 bg-surface-alt border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
                    />
                    <button
                        onClick={send}
                        disabled={streaming || !input.trim()}
                        data-testid="ai-tutor-send"
                        className="btn-primary px-4 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                    <MessageCircle className="w-3 h-3" /> Streaming responses · Powered by Claude Sonnet 4.5
                </div>
            </div>
        </div>
    );
}
