import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem("eaia_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (res) => res,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem("eaia_token");
            localStorage.removeItem("eaia_user");
        }
        return Promise.reject(error);
    }
);

// SSE streaming helper for AI Tutor
export async function streamTutor({ message, sessionId, courseContext, onDelta, onDone, onError }) {
    const token = localStorage.getItem("eaia_token");
    try {
        const res = await fetch(`${API_BASE}/ai/tutor`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                message,
                session_id: sessionId || null,
                course_context: courseContext || null,
            }),
        });

        if (!res.ok || !res.body) {
            const errText = await res.text().catch(() => "");
            onError?.(new Error(errText || `HTTP ${res.status}`));
            return;
        }

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
                    const payload = JSON.parse(evt.slice(6));
                    if (payload.delta) onDelta?.(payload.delta);
                    if (payload.error) onError?.(new Error(payload.error));
                    if (payload.done) onDone?.(payload);
                } catch {
                    /* ignore parse errors */
                }
            }
        }
    } catch (err) {
        onError?.(err);
    }
}
