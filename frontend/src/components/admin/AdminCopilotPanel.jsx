import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, X, Loader2, Send, RefreshCw, Bot } from "lucide-react";
import { toast } from "sonner";
import { getAccessToken, API_BASE } from "@/lib/api";

const STARTER_PROMPTS = [
    "Give me a 3-sentence platform health summary right now.",
    "Which orgs have low seat utilization I should follow up with?",
    "How many new enterprise leads are unresponded to?",
    "Are there any high-severity alerts open right now?",
    "Draft a Slack blurb for tomorrow's ops standup based on today's metrics.",
];

/* ==========================================================================
 * AdminCopilotPanel — right-slide-in AI operations assistant.
 * Streams delta events from POST /api/admin/copilot/chat (SSE).
 * ========================================================================== */
export default function AdminCopilotPanel({ open, onClose, currentTab }) {
    const [sessionId, setSessionId] = useState(() => `copilot-${Math.random().toString(36).slice(2, 12)}`);
    const [messages, setMessages] = useState([]); // {role: 'user'|'assistant'|'system', text, ts}
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const scrollRef = useRef(null);
    const abortRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // ESC to close
    useEffect(() => {
        const onKey = (e) => { if (e.key === "Escape" && open) onClose?.(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    const send = useCallback(async (text) => {
        const query = (text ?? input).trim();
        if (!query || busy) return;
        setInput("");
        setBusy(true);
        setMessages((prev) => [...prev, { role: "user", text: query, ts: Date.now() }]);
        // Add pending assistant bubble that we stream into
        const asstIdx = (m) => m.length; // index will be updated after user msg push
        let currentAssistant = "";
        setMessages((prev) => [...prev, { role: "assistant", text: "", ts: Date.now(), streaming: true }]);

        try {
            const controller = new AbortController();
            abortRef.current = controller;
            const token = getAccessToken() || "";
            const resp = await fetch(`${API_BASE}/admin/copilot/chat`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "text/event-stream",
                    Authorization: token ? `Bearer ${token}` : "",
                },
                credentials: "include",
                body: JSON.stringify({ message: query, session_id: sessionId, page_context: currentTab }),
                signal: controller.signal,
            });
            if (!resp.ok || !resp.body) {
                let detail = "Copilot request failed";
                try { const j = await resp.json(); detail = j.detail || detail; } catch { /* ignore */ }
                throw new Error(detail);
            }
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            // Read SSE stream — parse events split by blank lines.
            // Each event: "event: name\ndata: payload"
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                let sep;
                while ((sep = buffer.indexOf("\n\n")) !== -1) {
                    const raw = buffer.slice(0, sep);
                    buffer = buffer.slice(sep + 2);
                    let eventName = "message", dataStr = "";
                    for (const line of raw.split("\n")) {
                        if (line.startsWith("event:")) eventName = line.slice(6).trim();
                        else if (line.startsWith("data:")) dataStr += line.slice(5).trimStart();
                    }
                    if (eventName === "delta") {
                        currentAssistant += dataStr;
                        setMessages((prev) => {
                            const next = [...prev];
                            const last = next[next.length - 1];
                            if (last && last.role === "assistant") {
                                next[next.length - 1] = { ...last, text: currentAssistant };
                            }
                            return next;
                        });
                    } else if (eventName === "open") {
                        try {
                            const parsed = JSON.parse(dataStr);
                            if (parsed.session_id) setSessionId(parsed.session_id);
                        } catch { /* ignore */ }
                    } else if (eventName === "error") {
                        toast.error("Copilot error: " + dataStr.slice(0, 200));
                        break;
                    } else if (eventName === "done") {
                        // mark the assistant bubble complete
                        setMessages((prev) => {
                            const next = [...prev];
                            const last = next[next.length - 1];
                            if (last && last.role === "assistant") next[next.length - 1] = { ...last, streaming: false };
                            return next;
                        });
                    }
                }
            }
        } catch (e) {
            if (e?.name !== "AbortError") {
                toast.error(e?.message || "Copilot request failed");
                setMessages((prev) => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last && last.role === "assistant" && !last.text) {
                        next[next.length - 1] = { ...last, text: "(No response — check backend logs.)", streaming: false, failed: true };
                    }
                    return next;
                });
            }
        } finally {
            setBusy(false);
            abortRef.current = null;
        }
        return asstIdx;
    }, [busy, input, sessionId, currentTab]);

    const resetSession = async () => {
        if (abortRef.current) abortRef.current.abort();
        setMessages([]);
        setInput("");
        setSessionId(`copilot-${Math.random().toString(36).slice(2, 12)}`);
    };

    return (
        <>
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-slate-900/30 backdrop-blur-[1px] z-[60] transition-opacity ${open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}
                onClick={onClose}
                data-testid="copilot-backdrop"
            />
            {/* Drawer */}
            <aside
                className={`fixed top-0 right-0 bottom-0 z-[61] w-full sm:w-[480px] transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}
                data-testid="copilot-panel"
                aria-hidden={!open}
            >
                <div className="h-full sa-glass-hero flex flex-col rounded-none sm:rounded-l-2xl border-l border-border overflow-hidden">
                    {/* Header */}
                    <div className="px-5 py-4 border-b border-border flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white"
                                 style={{ background: "linear-gradient(135deg, #00A78B 0%, #2E7FC1 100%)" }}>
                                <Sparkles className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="font-serif text-lg leading-none">Command Assist</div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground mt-1">
                                    Claude Sonnet 4.5 · grounded in live metrics
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-1">
                            <button onClick={resetSession} className="sa-icon-btn" title="New conversation" data-testid="copilot-reset">
                                <RefreshCw className="w-4 h-4" />
                            </button>
                            <button onClick={onClose} className="sa-icon-btn" title="Close" data-testid="copilot-close">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>

                    {/* Messages */}
                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4" data-testid="copilot-messages">
                        {messages.length === 0 && (
                            <div className="space-y-4">
                                <div className="text-sm text-muted-foreground">
                                    Ask me about platform metrics, users, orgs, credentials, revenue, alerts, or Agent OS runs. I read live data at each turn.
                                </div>
                                <div className="space-y-2">
                                    <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Try one</div>
                                    {STARTER_PROMPTS.map((p, i) => (
                                        <button
                                            key={i}
                                            onClick={() => send(p)}
                                            disabled={busy}
                                            data-testid={`copilot-starter-${i}`}
                                            className="w-full text-left px-3 py-2 text-sm rounded-lg border border-border hover:border-brand bg-white/60 hover:bg-white transition-colors"
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                        {messages.map((m, i) => (
                            <MessageBubble key={i} m={m} />
                        ))}
                    </div>

                    {/* Composer */}
                    <div className="p-4 border-t border-border shrink-0 bg-white/70 backdrop-blur">
                        <form
                            onSubmit={(e) => { e.preventDefault(); send(); }}
                            className="flex gap-2 items-end"
                            data-testid="copilot-form"
                        >
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                                placeholder="Ask about metrics, users, alerts…"
                                rows={2}
                                disabled={busy}
                                data-testid="copilot-input"
                                className="flex-1 resize-none bg-white/80 border border-border rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-brand"
                            />
                            <button
                                type="submit"
                                disabled={busy || !input.trim()}
                                data-testid="copilot-send"
                                className="w-11 h-11 rounded-xl flex items-center justify-center text-white disabled:opacity-40"
                                style={{ background: "linear-gradient(135deg, #00A78B 0%, #2E7FC1 100%)" }}
                            >
                                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            </button>
                        </form>
                    </div>
                </div>
            </aside>
        </>
    );
}

function MessageBubble({ m }) {
    if (m.role === "user") {
        return (
            <div className="flex justify-end" data-testid="copilot-msg-user">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-white"
                     style={{ background: "linear-gradient(135deg, #16335E 0%, #2C4B84 100%)" }}>
                    {m.text}
                </div>
            </div>
        );
    }
    return (
        <div className="flex items-start gap-2" data-testid="copilot-msg-assistant">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-white"
                 style={{ background: "linear-gradient(135deg, #00A78B 0%, #2E7FC1 100%)" }}>
                <Bot className="w-3.5 h-3.5" />
            </div>
            <div className={`max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm bg-white/85 border border-border ${m.failed ? "text-destructive" : "text-foreground"}`}>
                <div className="whitespace-pre-wrap leading-relaxed">{m.text || (m.streaming ? "…" : "")}</div>
                {m.streaming && (
                    <div className="mt-1.5 flex items-center gap-1 text-[10px] font-mono text-muted-foreground">
                        <span className="w-1 h-1 rounded-full bg-current animate-pulse" />
                        <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ animationDelay: "150ms" }} />
                        <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ animationDelay: "300ms" }} />
                    </div>
                )}
            </div>
        </div>
    );
}
