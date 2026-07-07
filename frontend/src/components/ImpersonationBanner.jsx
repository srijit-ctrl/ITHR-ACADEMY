import { Eye, Loader2, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";

/**
 * Sticky banner that appears whenever the current session is an impersonation
 * (i.e. the AuthContext has an `impersonation` object). Provides the one-click
 * "Return to admin" action.
 */
export default function ImpersonationBanner() {
    const { impersonation, endImpersonation } = useAuth();
    const navigate = useNavigate();

    if (!impersonation) return null;

    const handleReturn = async () => {
        await endImpersonation();
        navigate("/admin");
    };

    return (
        <div
            data-testid="impersonation-banner"
            className="sticky top-0 z-40 w-full bg-brand text-background px-4 py-2 flex items-center justify-center gap-4 shadow-md"
        >
            <Eye className="w-4 h-4 shrink-0" />
            <div className="text-sm text-center">
                Viewing as{" "}
                <span className="font-mono font-semibold" data-testid="impersonation-target-email">
                    {impersonation.target?.email}
                </span>{" "}
                <span className="opacity-80">· Impersonation session expires in 15 minutes.</span>
            </div>
            <button
                onClick={handleReturn}
                data-testid="impersonation-return-btn"
                className="ml-2 inline-flex items-center gap-1 px-3 py-1 text-xs font-mono uppercase tracking-[0.15em] border border-background/50 hover:bg-background/10 rounded-sm"
            >
                <X className="w-3 h-3" /> Return to admin
            </button>
        </div>
    );
}
