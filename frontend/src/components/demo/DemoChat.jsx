import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Loader2, Send, Sparkles } from "lucide-react";

/**
 * Right-side streaming chat for the anonymous demo. Composes the suggestion
 * grid → active conversation → input row → limit-reached CTA states.
 */
export default function DemoChat({ lesson, messages, input, setInput, streaming, limitReached, ask }) {
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    return (
        <div className="lg:col-span-2 step-card flex flex-col min-h-[500px]" data-testid="demo-chat">
            <div className="flex items-center gap-3 mb-4 pb-4 border-b border-border">
                <div className="w-9 h-9 bg-foreground text-background flex items-center justify-center rounded-sm">
                    <span className="font-serif text-lg">A</span>
                </div>
                <div>
                    <div className="font-serif text-base leading-none">Aletheia</div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">AI Tutor · streaming</div>
                </div>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 mb-4 max-h-[420px] pr-1">
                {messages.length === 0 ? (
                    <div>
                        <p className="text-sm text-muted-foreground mb-4">Not sure where to start? Try one of these:</p>
                        <div className="space-y-2">
                            {lesson.suggested_questions.map((q) => (
                                <button
                                    key={q}
                                    onClick={() => ask(q)}
                                    data-testid={`demo-suggested-${q.slice(0, 32)}`}
                                    className="w-full text-left text-xs card-sharp p-3 hover:border-brand"
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    messages.map((m, i) => (
                        <div key={m.id || `msg-${i}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div className={`max-w-[90%] px-3 py-2 text-[13.5px] leading-relaxed rounded-sm whitespace-pre-wrap ${m.role === "user" ? "bg-foreground text-background" : "bg-surface-alt border border-border"}`}>
                                {m.content || (streaming && i === messages.length - 1 ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" /> : "")}
                            </div>
                        </div>
                    ))
                )}
            </div>

            {limitReached ? (
                <Link to="/register" className="btn-primary w-full" data-testid="demo-register">
                    <Sparkles className="w-4 h-4" /> Register free to continue
                    <ArrowRight className="w-4 h-4" />
                </Link>
            ) : (
                <div className="flex gap-2">
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && ask()}
                        placeholder="Ask Aletheia anything…"
                        disabled={streaming}
                        data-testid="demo-input"
                        className="flex-1 bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand"
                        maxLength={500}
                    />
                    <button
                        onClick={() => ask()}
                        disabled={streaming || !input.trim()}
                        data-testid="demo-send"
                        className="btn-primary px-4 py-2 disabled:opacity-40"
                    >
                        {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                </div>
            )}
        </div>
    );
}
