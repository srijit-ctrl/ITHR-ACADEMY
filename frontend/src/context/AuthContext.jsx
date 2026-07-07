import { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import { api, setAccessToken } from "@/lib/api";

const AuthContext = createContext(null);
const IMPERSONATION_STASH_KEY = "ithr_imp_stash_v1";

/**
 * Auth state is held in memory only.
 * - Access token: kept via api.js's module-level holder; never persisted.
 * - Refresh token: lives in an httpOnly Secure cookie set by the backend.
 * On mount we call /auth/refresh to see if a valid session already exists (cookie
 * survives page reloads, JWT survives navigations because of React context).
 *
 * Impersonation flow (super-admin only):
 *   - beginImpersonation({token, user}): stash the CURRENT admin session in
 *     sessionStorage (survives tab refresh, cleared on close), swap the
 *     in-memory token+user to the impersonation target, and remember the
 *     "acting as" state so the ImpersonationBanner can render.
 *   - endImpersonation(): pop the stash, restore the admin session, and
 *     hydrate a fresh access token via /auth/refresh (cookie is still the
 *     admin's).
 */
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [impersonation, setImpersonation] = useState(null); // { actorEmail, target: {email, id} }

    const hydrate = useCallback(async () => {
        try {
            const res = await api.post("/auth/refresh");
            setAccessToken(res.data.token);
            setUser(res.data.user);
        } catch {
            setAccessToken(null);
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        hydrate();
        // Restore an in-progress impersonation banner state (only banner, not
        // the token — impersonation tokens are one-shot and expire in 15 min).
        try {
            const stash = sessionStorage.getItem(IMPERSONATION_STASH_KEY);
            if (stash) {
                const parsed = JSON.parse(stash);
                if (parsed?.actorEmail) setImpersonation(parsed);
            }
        } catch (e) {
            // sessionStorage may be blocked (privacy mode / Safari ITP); banner
            // just won't reappear across reloads. Non-fatal — do not throw.
            console.debug("[Auth] impersonation stash read failed:", e?.message);
        }
    }, [hydrate]);

    const login = useCallback(async (email, password) => {
        const res = await api.post("/auth/login", { email, password });
        setAccessToken(res.data.token);
        setUser(res.data.user);
        return res.data.user;
    }, []);

    const register = useCallback(async (payload) => {
        const res = await api.post("/auth/register", payload);
        setAccessToken(res.data.token);
        setUser(res.data.user);
        return res.data.user;
    }, []);

    const logout = useCallback(async () => {
        try {
            await api.post("/auth/logout");
        } catch (e) {
            // Server-side logout is best-effort; local state is cleared below.
            console.debug("[Auth] logout POST failed (non-fatal):", e?.message);
        }
        setAccessToken(null);
        setUser(null);
        setImpersonation(null);
        try {
            sessionStorage.removeItem(IMPERSONATION_STASH_KEY);
        } catch (e) {
            // sessionStorage may be blocked; ignore — key just won't clear.
            console.debug("[Auth] impersonation stash clear failed:", e?.message);
        }
    }, []);

    const refreshUser = useCallback(async () => {
        try {
            const res = await api.get("/auth/me");
            setUser(res.data);
        } catch {
            setAccessToken(null);
            setUser(null);
        }
    }, []);

    const beginImpersonation = useCallback(({ token, user: targetUser, actorEmail }) => {
        // Stash the admin's identity so the banner can render "return".
        // We DO NOT stash the admin's access token — it's short-lived in memory
        // and would be exposed to XSS if persisted. Instead, we rely on the
        // admin's refresh cookie (still valid) via /auth/refresh on return.
        const stash = { actorEmail, target: { id: targetUser.id, email: targetUser.email, full_name: targetUser.full_name } };
        try {
            sessionStorage.setItem(IMPERSONATION_STASH_KEY, JSON.stringify(stash));
        } catch (e) {
            console.debug("[Auth] impersonation stash write failed:", e?.message);
        }
        setImpersonation(stash);
        setAccessToken(token);
        setUser(targetUser);
    }, []);

    const endImpersonation = useCallback(async () => {
        try {
            sessionStorage.removeItem(IMPERSONATION_STASH_KEY);
        } catch (e) {
            console.debug("[Auth] impersonation stash clear failed:", e?.message);
        }
        setImpersonation(null);
        // Fresh access token via the admin's still-valid refresh cookie.
        try {
            const res = await api.post("/auth/refresh");
            setAccessToken(res.data.token);
            setUser(res.data.user);
        } catch {
            setAccessToken(null);
            setUser(null);
        }
    }, []);

    const value = useMemo(
        () => ({ user, loading, login, register, logout, refreshUser, impersonation, beginImpersonation, endImpersonation }),
        [user, loading, login, register, logout, refreshUser, impersonation, beginImpersonation, endImpersonation]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
    return ctx;
}
