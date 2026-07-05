import { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import { api, setAccessToken } from "@/lib/api";

const AuthContext = createContext(null);

/**
 * Auth state is held in memory only.
 * - Access token: kept via api.js's module-level holder; never persisted.
 * - Refresh token: lives in an httpOnly Secure cookie set by the backend.
 * On mount we call /auth/refresh to see if a valid session already exists (cookie
 * survives page reloads, JWT survives navigations because of React context).
 */
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

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

    const value = useMemo(
        () => ({ user, loading, login, register, logout, refreshUser }),
        [user, loading, login, register, logout, refreshUser]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
    return ctx;
}
