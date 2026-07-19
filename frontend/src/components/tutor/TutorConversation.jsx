import { useEffect, useRef, useState } from "react";
import { Loader2, HelpCircle, ThumbsUp, ThumbsDown } from "lucide-react";

/**
 * Scrollable message list used by the inline tutor. Auto-scrolls on new
 * deltas. Renders the tutor's structured meta (suggested-action chips +
 * knowledge-check highlight) on the last assistant message.
 *
 * If `onRate` is passed, every completed (non-streaming) assistant message
 * — except the synthetic "welcome" bubble — gets thumbs-up / thumbs-down
 * buttons wired to the AI Ops learner-satisfaction signal.
 */
export default function TutorConversation({ messages, streaming, onAction, ratings, onRate }) {
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

    const lastIdx = messages.length - 1;

    return (
        <div
            ref={scrollRef}
            className="border border-border bg-surface-alt/30 max-h-[420px] overflow-y-auto p-5 space-y-4"
            data-testid="inline-tutor-conversation"
        >
            {messages.length === 0 && (
                <p className="text-sm text-muted-foreground italic">
                    Ask a question below — I have the full lesson context.
                </p>
            )}
            {(() => {
                let assistantSeen = -1;
                return messages.map((m, i) => {
                    let turnIndex = null;
                    if (m.role === "assistant") {
                        assistantSeen += 1;
                        // Skip the synthetic welcome bubble for rating purposes.
                        if (m.id !== "welcome") turnIndex = assistantSeen;
                    }
                    return (
                        <div key={m.id || `msg-${i}`}>
                            <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div
                                    className={`max-w-[85%] px-4 py-2.5 text-[14px] leading-relaxed rounded-sm whitespace-pre-wrap ${
                                        m.role === "user"
                                            ? "bg-foreground text-background"
                                            : "bg-surface border border-border"
                                    }`}
                                >
                                    {m.content || (streaming && i === lastIdx ? (
                                        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                                    ) : "")}
                                </div>
                            </div>
                            {m.role === "assistant" && i === lastIdx && !streaming && m.meta && (
                                <TutorMetaExtras meta={m.meta} onAction={onAction} />
                            )}
                            {onRate && m.role === "assistant" && turnIndex !== null && m.content && !(streaming && i === lastIdx) && (
                                <TutorRateBar
                                    turnIndex={turnIndex}
                                    current={ratings?.[turnIndex]}
                                    onRate={onRate}
                                />
                            )}
                        </div>
                    );
                });
            })()}
        </div>
    );
}

export function TutorRateBar({ turnIndex, current, onRate }) {
    const [showReason, setShowReason] = useState(false);
    const [reason, setReason] = useState("");
    const active = current || null;

    const submit = (rating) => {
        if (rating === "down" && !active) {
            setShowReason(true);
            onRate(turnIndex, rating);
            return;
        }
        onRate(turnIndex, rating);
        setShowReason(false);
    };

    const sendReason = () => {
        if (!reason.trim()) { setShowReason(false); return; }
        onRate(turnIndex, "down", reason.trim());
        setReason("");
        setShowReason(false);
    };

    return (
        <div className="mt-1.5 flex items-center gap-1.5" data-testid={`tutor-rate-bar-${turnIndex}`}>
            <button
                type="button"
                aria-label="Helpful"
                onClick={() => submit("up")}
                data-testid={`tutor-rate-up-${turnIndex}`}
                className={`p-1 rounded-full transition-colors ${
                    active === "up"
                        ? "text-brand bg-brand/10"
                        : "text-muted-foreground/60 hover:text-brand hover:bg-brand/5"
                }`}
            >
                <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button
                type="button"
                aria-label="Not helpful"
                onClick={() => submit("down")}
                data-testid={`tutor-rate-down-${turnIndex}`}
                className={`p-1 rounded-full transition-colors ${
                    active === "down"
                        ? "text-destructive bg-destructive/10"
                        : "text-muted-foreground/60 hover:text-destructive hover:bg-destructive/5"
                }`}
            >
                <ThumbsDown className="w-3.5 h-3.5" />
            </button>
            {active && (
                <span className="text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground">
                    {active === "up" ? "Thanks for the feedback" : "Noted — we'll improve"}
                </span>
            )}
            {showReason && (
                <div className="flex items-center gap-1.5 ml-1" data-testid={`tutor-rate-reason-${turnIndex}`}>
                    <input
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && sendReason()}
                        placeholder="What was off? (optional)"
                        className="text-xs bg-surface border border-border rounded-sm px-2 py-1 w-56 focus:outline-none focus:border-brand"
                        maxLength={500}
                        autoFocus
                    />
                    <button
                        type="button"
                        onClick={sendReason}
                        data-testid={`tutor-rate-reason-submit-${turnIndex}`}
                        className="text-[10px] font-mono uppercase tracking-[0.14em] text-brand hover:underline"
                    >
                        Send
                    </button>
                </div>
            )}
        </div>
    );
}

export function TutorMetaExtras({ meta, onAction }) {
    const actions = (meta?.suggested_actions || []).filter((a) => a?.label && a?.action).slice(0, 4);
    const kc = meta?.knowledge_check;
    if (!actions.length && !kc?.included) return null;
    return (
        <div className="mt-2 space-y-2" data-testid="tutor-meta-extras">
            {kc?.included && kc.question && (
                <div className="flex items-start gap-2 text-xs text-brand bg-brand/5 border border-brand/20 rounded-sm px-3 py-2" data-testid="tutor-knowledge-check">
                    <HelpCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    <span>Knowledge check — answer above to continue.</span>
                </div>
            )}
            {actions.length > 0 && onAction && (
                <div className="flex flex-wrap gap-2">
                    {actions.map((a, i) => (
                        <button
                            key={i}
                            onClick={() => onAction(a.action)}
                            data-testid={`tutor-action-chip-${i}`}
                            className="text-xs border border-brand/40 text-brand hover:bg-brand hover:text-white rounded-full px-3 py-1.5 transition-colors"
                        >
                            {a.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
