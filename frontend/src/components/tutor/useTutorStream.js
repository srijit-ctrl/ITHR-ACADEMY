import { useEffect, useState } from "react";
import { streamTutor } from "@/lib/api";
import { splitTutorMeta, TUTOR_META_MARKER } from "@/components/tutor/tutorMeta";

/**
 * Custom hook that manages the streaming conversation state for the Inline
 * (and Panel) tutor. Keeps message list, session-id, streaming flag, and
 * exposes a single `send()` function. Strips the tutor's @@META@@ structured
 * footer from visible content and attaches it as `message.meta` on completion.
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

    const send = async (raw, { mode } = {}) => {
        const clean = (raw || "").trim();
        if (!clean || streaming) return;

        // Prepend lesson context so the tutor knows what's on screen.
        const contextMsg = [
            lesson?.title ? `Current lesson: "${lesson.title}"` : null,
            moduleTitle ? `Module: ${moduleTitle}` : null,
            "Learner question:",
            clean,
        ].filter(Boolean).join("\n");

        setMessages((m) => [
            ...m,
            { id: `u-${Date.now()}-${m.length}`, role: "user", content: clean },
            { id: `a-${Date.now()}-${m.length + 1}`, role: "assistant", content: "", raw: "" },
        ]);
        setStreaming(true);

        await streamTutor({
            message: contextMsg,
            sessionId,
            courseContext: courseSlug,
            mode,
            onDelta: (delta) => {
                setMessages((m) => {
                    const copy = [...m];
                    const last = copy[copy.length - 1];
                    const raw2 = (last?.raw || "") + delta;
                    copy[copy.length - 1] = { ...last, raw: raw2, content: raw2.split(TUTOR_META_MARKER)[0] };
                    return copy;
                });
            },
            onDone: (p) => {
                setStreaming(false);
                if (p.session_id) setSessionId(p.session_id);
                setMessages((m) => {
                    const copy = [...m];
                    const last = copy[copy.length - 1];
                    const { text, meta } = splitTutorMeta(last?.raw || last?.content || "");
                    copy[copy.length - 1] = { ...last, content: text, meta };
                    return copy;
                });
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
