import { useEffect, useState } from "react";
import { api, API_BASE } from "@/lib/api";
import { readSSEStream } from "@/components/demo/sseStream";

/**
 * Fetches the demo lesson once on mount and manages the streaming Q&A
 * chat state (messages, input, streaming flag, IP-rate-limit).
 *
 * SSE plumbing lives in components/demo/sseStream.js so this hook stays
 * focused on React state.
 */
export default function useDemoLesson() {
    const [lesson, setLesson] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [limitReached, setLimitReached] = useState(false);

    useEffect(() => {
        api.get("/demo/lesson")
            .then((r) => setLesson(r.data))
            .catch((err) => console.error("demo lesson fetch failed:", err));
    }, []);

    const appendUserAndPlaceholder = (msg) => {
        setMessages((m) => [
            ...m,
            { id: `u-${Date.now()}-${m.length}`, role: "user", content: msg },
            { id: `a-${Date.now()}-${m.length + 1}`, role: "assistant", content: "" },
        ]);
    };

    const replaceLastAssistant = (updater) => {
        setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = typeof updater === "function" ? updater(last) : updater;
            return copy;
        });
    };

    const handleRateLimited = () => {
        setLimitReached(true);
        replaceLastAssistant({
            role: "assistant",
            content: "You've reached the demo limit. Register free to keep chatting with Aletheia without limits.",
        });
        setStreaming(false);
    };

    const ask = async (text) => {
        const msg = (text || input).trim();
        if (!msg || streaming || limitReached) return;
        setInput("");
        appendUserAndPlaceholder(msg);
        setStreaming(true);

        try {
            const res = await fetch(`${API_BASE}/demo/ask`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: msg }),
            });
            if (res.status === 429) return handleRateLimited();

            await readSSEStream(res, {
                onDelta: (delta) => replaceLastAssistant((last) => ({
                    role: "assistant",
                    content: (last?.content || "") + delta,
                })),
                onError: (err) => { throw err; },
            });
        } catch (e) {
            replaceLastAssistant({ role: "assistant", content: `Sorry — ${e.message}` });
        } finally { setStreaming(false); }
    };

    return { lesson, messages, input, setInput, streaming, limitReached, ask };
}
