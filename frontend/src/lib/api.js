import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

// -----------------------------------------------------------------------------
// In-memory access token holder.
// The access token is short-lived (~15 min) and is deliberately kept only in
// module memory — never localStorage/sessionStorage — to remove the XSS-exfil
// path. The long-lived refresh session lives in an httpOnly Secure cookie set
// by the backend on /api/auth/login|register|google-callback|refresh.
// -----------------------------------------------------------------------------
let _accessToken = null;

export function setAccessToken(token) {
    _accessToken = token || null;
}

export function getAccessToken() {
    return _accessToken;
}

export const api = axios.create({
    baseURL: API_BASE,
    withCredentials: true, // include the httpOnly refresh cookie on same-origin calls
});

api.interceptors.request.use((config) => {
    if (_accessToken) {
        config.headers.Authorization = `Bearer ${_accessToken}`;
    }
    return config;
});

// Track a single in-flight refresh so we don't storm the endpoint on parallel 401s.
let _refreshInFlight = null;

async function _tryRefresh() {
    if (!_refreshInFlight) {
        _refreshInFlight = axios
            .post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true })
            .then((res) => {
                setAccessToken(res.data.token);
                return res.data;
            })
            .catch((err) => {
                setAccessToken(null);
                throw err;
            })
            .finally(() => {
                _refreshInFlight = null;
            });
    }
    return _refreshInFlight;
}

api.interceptors.response.use(
    (res) => res,
    async (error) => {
        const original = error.config;
        const isAuthEndpoint = original?.url?.startsWith("/auth/");
        if (
            error.response?.status === 401 &&
            !isAuthEndpoint &&
            !original.__retried
        ) {
            original.__retried = true;
            try {
                await _tryRefresh();
                return api(original);
            } catch {
                setAccessToken(null);
            }
        }
        return Promise.reject(error);
    }
);

// SSE streaming helper for AI Tutor
export async function streamTutor({ message, sessionId, courseContext, onDelta, onDone, onError }) {
    return _streamSSE("/ai/tutor", { message, session_id: sessionId || null, course_context: courseContext || null }, { onDelta, onDone, onError });
}

// SSE streaming helper for AI Mentor (career coach)
export async function streamMentor({ message, sessionId, context, onDelta, onDone, onError }) {
    return _streamSSE("/mentor/chat", { message, session_id: sessionId || null, context: context || null }, { onDelta, onDone, onError });
}

async function _streamSSE(path, body, { onDelta, onDone, onError }) {
    // Reads token from in-memory state; if missing we still send (server will 401).
    // We do not attempt to refresh here because SSE streams should be started only
    // after normal API calls have hydrated the token.
    const token = getAccessToken();
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            credentials: "include",
            body: JSON.stringify(body),
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
                } catch (parseErr) {
                    console.debug("SSE partial chunk, waiting for next:", parseErr?.message);
                }
            }
        }
    } catch (err) {
        onError?.(err);
    }
}
