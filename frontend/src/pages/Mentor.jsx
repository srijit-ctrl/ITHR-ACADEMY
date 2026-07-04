import { useEffect, useRef, useState } from "react";
import { api, streamMentor, API_BASE } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Compass, Send, Loader2, Trash2, MessageSquare, Sparkles, Briefcase, GraduationCap, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

const STARTERS = [
    { icon: Briefcase, text: "I'm a product manager in banking. What agentic AI skills matter most for me in 2026?" },
    { icon: GraduationCap, text: "I just passed the Foundation exam. What's my best next credential + course?" },
    { icon: Compass, text: "I want to transition from data engineering to AI architecture. Design a 6-month plan." },
    { icon: Sparkles, text: "Which industry track has the strongest ROI for someone with a healthcare operations background?" },
];

export default function Mentor() {
    const { user } = useAuth();
    const [sessions, setSessions] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [role, setRole] = useState("");
    const [industry, setIndustry] = useState("");
    const [years, setYears] = useState("");
    const scrollRef = useRef(null);

    useEffect(() => {
        if (!user) return;
        api.get("/mentor/sessions").then((r) => setSessions(r.data)).catch(() => {});
    }, [user]);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    const openSession = async (id) => {
        try {
            const r = await api.get(`/mentor/sessions/${id}`);
            setSessionId(id);
            setMessages(r.data.messages || []);
        } catch (e) { void e; }
    };

    const newSession = () => {
        setSessionId(null);
        setMessages([]);
    };

    const removeSession = async (id, e) => {
        e.stopPropagation();
        try {
            await api.delete(`/mentor/sessions/${id}`);
            setSessions((s) => s.filter((x) => x.id !== id));
            if (sessionId === id) newSession();
        } catch (err) { void err; }
    };

    const send = async (text) => {
        const msg = (text || input).trim();
        if (!msg || streaming) return;
        setInput("");
        setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
        setStreaming(true);
        const ctx = {};
        if (role) ctx.role = role;
        if (industry) ctx.industry = industry;
        if (years) ctx.years_experience = years;

        await streamMentor({
            message: msg,
            sessionId,
            context: Object.keys(ctx).length ? ctx : null,
            onDelta: (delta) => {
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + delta };
                    return copy;
                });
            },
            onDone: (p) => {
                setStreaming(false);
                if (p.session_id && !sessionId) {
                    setSessionId(p.session_id);
                    api.get("/mentor/sessions").then((r) => setSessions(r.data)).catch(() => {});
                }
            },
            onError: (err) => {
                setStreaming(false);
                setMessages((m) => {
                    const copy = [...m];
                    copy[copy.length - 1] = { role: "assistant", content: `Error: ${err.message}` };
                    return copy;
                });
            },
        });
    };

    if (!user) {
        return (
            <div className="container-narrow py-24 text-center">
                <div className="overline mb-4">AI Career Mentor</div>
                <h1 className="font-serif text-5xl tracking-tighter mb-4">Sign in to meet Solon.</h1>
                <p className="text-muted-foreground mb-8">Personalized AI career coaching, credential roadmaps, and 90-day plans — anchored in the ITHR credential ladder.</p>
                <Link to="/login" className="btn-primary">Sign in</Link>
            </div>
        );
    }

    return (
        <div className="container-page py-10">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                {/* Sidebar */}
                <aside className="lg:col-span-3 space-y-6">
                    <div>
                        <div className="overline mb-3 fine-rule pl-4">AI Career Mentor</div>
                        <h1 className="font-serif text-4xl tracking-tighter leading-none">Solon</h1>
                        <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                            Your personal mentor for role-based upskilling and credential strategy. Anchored to the ITHR credential ladder.
                        </p>
                    </div>

                    <div className="card-flat p-5 space-y-3">
                        <div className="overline">Your profile</div>
                        <label className="block">
                            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Current role</span>
                            <input
                                data-testid="mentor-role-input"
                                value={role} onChange={(e) => setRole(e.target.value)}
                                placeholder="e.g. Product Manager"
                                className="mt-1 w-full text-sm bg-surface-alt border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                            />
                        </label>
                        <label className="block">
                            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Industry</span>
                            <input
                                data-testid="mentor-industry-input"
                                value={industry} onChange={(e) => setIndustry(e.target.value)}
                                placeholder="e.g. Banking"
                                className="mt-1 w-full text-sm bg-surface-alt border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                            />
                        </label>
                        <label className="block">
                            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Years of experience</span>
                            <input
                                data-testid="mentor-years-input"
                                value={years} onChange={(e) => setYears(e.target.value)}
                                placeholder="e.g. 5"
                                className="mt-1 w-full text-sm bg-surface-alt border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-brand"
                            />
                        </label>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <div className="overline">Past conversations</div>
                            <button data-testid="mentor-new-session" onClick={newSession} className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand hover:underline">+ new</button>
                        </div>
                        <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
                            {sessions.length === 0 && (
                                <p className="text-xs text-muted-foreground italic">No conversations yet.</p>
                            )}
                            {sessions.map((s) => (
                                <div
                                    key={s.id}
                                    onClick={() => openSession(s.id)}
                                    data-testid={`mentor-session-${s.id}`}
                                    className={`group flex items-start gap-2 p-2.5 border cursor-pointer transition-colors ${sessionId === s.id ? "border-brand bg-brand/5" : "border-border hover:border-foreground"}`}
                                >
                                    <MessageSquare className="w-3 h-3 text-muted-foreground shrink-0 mt-1" />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-xs leading-tight line-clamp-2">{s.title}</div>
                                    </div>
                                    <button
                                        onClick={(e) => removeSession(s.id, e)}
                                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-brand transition-opacity"
                                        aria-label="delete"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                </aside>

                {/* Chat */}
                <section className="lg:col-span-9 card-flat flex flex-col min-h-[600px]" data-testid="mentor-chat">
                    <div className="border-b border-border p-5 flex items-center gap-3">
                        <div className="w-10 h-10 bg-foreground text-background flex items-center justify-center rounded-sm">
                            <Compass className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="font-serif text-lg leading-none">Solon</div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">Career Mentor · Streaming · Sonnet 4.5</div>
                        </div>
                    </div>

                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-5 max-h-[70vh]">
                        {messages.length === 0 ? (
                            <div className="max-w-2xl">
                                <p className="font-serif text-2xl leading-tight mb-3">Where would you like to go next in your career?</p>
                                <p className="text-sm text-muted-foreground mb-6">Fill in your profile on the left for sharper advice, or start with a question below.</p>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {STARTERS.map((s, i) => (
                                        <button
                                            key={i}
                                            data-testid={`mentor-starter-${i}`}
                                            onClick={() => send(s.text)}
                                            className="text-left card-sharp p-4 group"
                                        >
                                            <s.icon className="w-4 h-4 text-brand mb-2" />
                                            <p className="text-sm leading-snug">{s.text}</p>
                                            <span className="mt-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-[0.15em] text-brand opacity-0 group-hover:opacity-100 transition-opacity">Ask <ArrowRight className="w-3 h-3" /></span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            messages.map((m, i) => (
                                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                                    <div className={`max-w-[85%] px-4 py-3 text-[14.5px] leading-relaxed rounded-sm whitespace-pre-wrap ${m.role === "user" ? "bg-foreground text-background" : "bg-surface-alt border border-border"}`}>
                                        {m.content || (streaming && i === messages.length - 1 ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" /> : "")}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>

                    <div className="border-t border-border p-4 bg-surface">
                        <div className="flex gap-3">
                            <input
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && send()}
                                placeholder="Ask about your next credential, a career pivot, or a 90-day plan…"
                                disabled={streaming}
                                data-testid="mentor-input"
                                className="flex-1 bg-surface-alt border border-border rounded-sm px-4 py-3 text-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
                            />
                            <button
                                data-testid="mentor-send"
                                onClick={() => send()}
                                disabled={streaming || !input.trim()}
                                className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                                {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Send</>}
                            </button>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
}
