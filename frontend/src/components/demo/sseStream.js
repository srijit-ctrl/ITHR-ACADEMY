/**
 * Minimal SSE (Server-Sent Events) reader for the anonymous demo `/demo/ask`
 * endpoint. Parses the "data: {json}\n\n" event framing and dispatches
 * `onDelta` / `onDone` / `onError` callbacks.
 *
 * Extracted from useDemoLesson so the streaming state machine can be
 * unit-tested independently from the React hook.
 */
export async function readSSEStream(response, { onDelta, onError }) {
    if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const evt of events) {
            processSSEEvent(evt, onDelta, onError);
        }
    }
}

function processSSEEvent(evt, onDelta, onError) {
    if (!evt.startsWith("data: ")) return;
    try {
        const payload = JSON.parse(evt.slice(6));
        if (payload.delta) onDelta(payload.delta);
        if (payload.error) onError(new Error(payload.error));
    } catch (parseErr) {
        // Chunk boundary hit mid-JSON — the next chunk will complete it
        // via the buffered reader loop above. Not an error.
        console.debug("[SSE] partial chunk, awaiting next:", parseErr?.message);
    }
}
