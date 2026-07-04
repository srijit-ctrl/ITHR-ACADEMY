import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(() => {
        const cached = localStorage.getItem("eaia_user");
        return cached ? JSON.parse(cached) : null;
    });
    const [loading, setLoading] = useState(true);

    const refreshUser = useCallback(async () => {
        const token = localStorage.getItem("eaia_token");
        if (!token) {
            setUser(null);
            setLoading(false);
            return;
        }
        try {
            const res = await api.get("/auth/me");
            setUser(res.data);
            localStorage.setItem("eaia_user", JSON.stringify(res.data));
        } catch {
            localStorage.removeItem("eaia_token");
            localStorage.removeItem("eaia_user");
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refreshUser();
    }, [refreshUser]);

    const login = async (email, password) => {
        const res = await api.post("/auth/login", { email, password });
        localStorage.setItem("eaia_token", res.data.token);
        localStorage.setItem("eaia_user", JSON.stringify(res.data.user));
        setUser(res.data.user);
        return res.data.user;
    };

    const register = async (payload) => {
        const res = await api.post("/auth/register", payload);
        localStorage.setItem("eaia_token", res.data.token);
        localStorage.setItem("eaia_user", JSON.stringify(res.data.user));
        setUser(res.data.user);
        return res.data.user;
    };

    const logout = () => {
        localStorage.removeItem("eaia_token");
        localStorage.removeItem("eaia_user");
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
    return ctx;
}
