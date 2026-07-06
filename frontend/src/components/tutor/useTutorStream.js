import { useEffect, useState } from "react";
import { streamTutor } from "@/lib/api";

/**
 * Custom hook that manages the streaming conversation state for the Inline
 * (and Panel) tutor. Keeps message list, session-id, streaming flag, and
 * exposes a single `send()` function.
 */
export default function useTutorStream({ courseSlug, lesson, moduleTitle } = {}) {
    const [messages, setMessages] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [streaming, setStreaming] = useState(false);

    // Reset transient state when the user moves to a different lesson
    useEffect(() => {
        setMessages([]);
        setSessionId(null);
    }, [lesson?.id]);

    const reset = () => {
        setMessages([]);
        setSessionId(null);
    };

    const send = async (raw) => {
        const clean = (raw || "").trim();
        if (!clean || streaming) return;

        // Prepend lesson context so Aletheia knows what's on screen.
        const contextMsg = [
            lesson?.title ? `Current lesson: "${lesson.title}"` : null,
            moduleTitle ? `Module: ${moduleTitle}` : null,
            "Learner question:",
            clean,
        ].filter(Boolean).join("\n");

        setMessages((m) => [
            ...m,
            { id: `u-${Date.now()}-${m.length}`, role: "user", content: clean },
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
                    copy[copy.length - 1] = {
                        ...copy[copy.length - 1],
                        content: (copy[copy.length - 1]?.content || "") + delta,
                    };
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
                    copy[copy.length - 1] = {
                        ...copy[copy.length - 1],
                        content: `Sorry — ${err.message}`,
                    };
                    return copy;
                });
            },
        });
    };

    return { messages, streaming, send, reset, sessionId };
}
