import { useEffect, useState, useRef } from "react";
import DOMPurify from "dompurify";
import { api, API_BASE } from "@/lib/api";
import { Send, Loader2, Sparkles, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Anonymous "Try a lesson" widget — streams Aletheia's answer with a curated
 * demo lesson. No auth required. Rate-limited server-side to 5 questions per IP.
 */
export default function TryALesson() {
    const [lesson, setLesson] = useState(null);
    const [messages, setMessages] = useState([]); // {role, content}
    const [input, setInput] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [limitReached, setLimitReached] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        api.get("/demo/lesson")
            .then((r) => setLesson(r.data))
            .catch((err) => console.error("demo lesson fetch failed:", err));
    }, []);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    const ask = async (text) => {
        const msg = (text || input).trim();
        if (!msg || streaming || limitReached) return;
        setInput("");
        setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
        setStreaming(true);

        try {
            const res = await fetch(`${API_BASE}/demo/ask`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: msg }),
            });
            if (res.status === 429) {
                setLimitReached(true);
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { role: "assistant", content: "You've reached the demo limit. Register free to keep chatting with Aletheia without limits." };
                    return copy;
                });
                setStreaming(false);
                return;
            }
            if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const events = buffer.split("\n\n");
                buffer = events.pop() || "";
                for (const evt of events) {
                    if (!evt.startsWith("data: ")) continue;
                    try {
                        const p = JSON.parse(evt.slice(6));
                        if (p.delta) {
                            setMessages((m) => {
                                const copy = [...m];
                                copy[copy.length - 1] = {
                                    role: "assistant",
                                    content: copy[copy.length - 1].content + p.delta,
                                };
                                return copy;
                            });
                        }
                        if (p.error) throw new Error(p.error);
                    } catch (parseErr) { /* SSE partial JSON — wait for next chunk */ }
                }
            }
        } catch (e) {
            setMessages((m) => {
                const copy = [...m];
                copy[copy.length - 1] = { role: "assistant", content: `Sorry — ${e.message}` };
                return copy;
            });
        } finally { setStreaming(false); }
    };

    if (!lesson) return null;

    return (
        <section className="section-warm-cream border-y border-border py-24" data-testid="try-a-lesson">
            <div className="container-page">
                <div className="text-center max-w-2xl mx-auto mb-14">
                    <span className="section-kicker">Try before you enroll</span>
                    <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight mb-4">
                        Take a lesson with <span className="italic text-brand">Aletheia</span>.
                    </h2>
                    <p className="text-muted-foreground text-lg">
                        No sign-up. Read a 4-minute mini-lesson, then ask Aletheia any question &mdash; she&apos;ll stream a live answer right below.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 max-w-6xl mx-auto">
                    {/* Lesson body */}
                    <article className="lg:col-span-3 step-card">
                        <div className="flex items-center justify-between mb-5">
                            <span className="badge-gold">Unit 01 · {lesson.duration_min} min</span>
                            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand-gold-deep">ITHR Academy</span>
                        </div>
                        <h3 className="font-serif text-3xl tracking-tight mb-6">{lesson.title}</h3>
                        <div className="space-y-6">
                            {lesson.sections.map((s) => (
                                <div key={s.heading}>
                                    <h4 className="font-serif text-lg text-brand mb-2">{s.heading}</h4>
                                    <p
                                        className="text-sm leading-relaxed text-foreground"
                                        dangerouslySetInnerHTML={{
                                            __html: DOMPurify.sanitize(
                                                s.body
                                                    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                                                    .replace(/\*(.+?)\*/g, '<em class="text-brand">$1</em>')
                                            ),
                                        }}
                                    />
                                </div>
                            ))}
                        </div>
                    </article>

                    {/* Chat */}
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
                                    <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
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
                </div>
            </div>
        </section>
    );
}
