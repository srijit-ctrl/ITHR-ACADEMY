import { useEffect, useRef } from "react";
import { Loader2, HelpCircle } from "lucide-react";

/**
 * Scrollable message list used by the inline tutor. Auto-scrolls on new
 * deltas. Renders the tutor's structured meta (suggested-action chips +
 * knowledge-check highlight) on the last assistant message.
 */
export default function TutorConversation({ messages, streaming, onAction }) {
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
            {messages.map((m, i) => (
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
                </div>
            ))}
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
