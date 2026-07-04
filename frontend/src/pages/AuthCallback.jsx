import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
    const navigate = useNavigate();
    const processed = useRef(false);

    useEffect(() => {
        if (processed.current) return;
        processed.current = true;

        const hash = window.location.hash;
        const match = hash.match(/session_id=([^&]+)/);
        if (!match) {
            navigate("/login");
            return;
        }
        const sessionId = match[1];

        (async () => {
            try {
                const res = await api.post("/auth/google/callback", { session_id: sessionId });
                localStorage.setItem("eaia_token", res.data.token);
                localStorage.setItem("eaia_user", JSON.stringify(res.data.user));
                // clear the hash and go to dashboard
                window.history.replaceState(null, "", window.location.pathname);
                window.location.href = "/dashboard";
            } catch (e) {
                console.error("Google auth failed", e);
                navigate("/login?error=google");
            }
        })();
    }, [navigate]);

    return (
        <div className="min-h-screen flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand mb-4" />
            <p className="text-muted-foreground text-sm font-mono uppercase tracking-[0.2em]">Completing sign-in…</p>
        </div>
    );
}
