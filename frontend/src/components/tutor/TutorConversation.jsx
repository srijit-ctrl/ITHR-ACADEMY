import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";

/**
 * Scrollable message list used by the inline tutor (Aletheia embedded in a
 * lesson pane). Auto-scrolls to the bottom whenever new deltas stream in.
 */
export default function TutorConversation({ messages, streaming }) {
    const scrollRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages, streaming]);

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
                <div key={m.id || `msg-${i}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                        className={`max-w-[85%] px-4 py-2.5 text-[14px] leading-relaxed rounded-sm whitespace-pre-wrap ${
                            m.role === "user"
                                ? "bg-foreground text-background"
                                : "bg-surface border border-border"
                        }`}
                    >
                        {m.content || (streaming && i === messages.length - 1 ? (
                            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                        ) : "")}
                    </div>
                </div>
            ))}
        </div>
    );
}
