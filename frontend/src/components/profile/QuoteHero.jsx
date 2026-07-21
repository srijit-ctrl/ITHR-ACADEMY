import { useCallback, useEffect, useState } from "react";
import { Sparkles, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { pickRandomQuote } from "@/data/curatedQuotes";

/**
 * QuoteHero — the "peppy" hero at the top of the self-service portal.
 *
 * Starts with a random curated quote (zero cost). Clicking "Personalise for me"
 * calls the AI endpoint (Claude Sonnet 4.5 via Emergent LLM key) for a bespoke
 * one-liner grounded in the learner's XP / streak / current course.
 */
export default function QuoteHero({ firstName }) {
    // Rotate the seed quote each mount so every login feels fresh.
    const [quote, setQuote] = useState(() => pickRandomQuote());
    const [aiBusy, setAiBusy] = useState(false);
    const [personalised, setPersonalised] = useState(false);
    const [popping, setPopping] = useState(true);

    // pop animation on mount + on refresh
    useEffect(() => {
        setPopping(true);
        const t = setTimeout(() => setPopping(false), 600);
        return () => clearTimeout(t);
    }, [quote]);

    const shuffleCurated = useCallback(() => {
        setQuote(pickRandomQuote());
        setPersonalised(false);
    }, []);

    const personalise = useCallback(async () => {
        setAiBusy(true);
        try {
            const res = await api.post("/me/inspire", {});
            setQuote({ text: res.data.quote, author: "Personalised by Aletheia" });
            setPersonalised(!!res.data.personalised);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Couldn't generate a personalised quote — try again in a moment.");
        } finally {
            setAiBusy(false);
        }
    }, []);

    return (
        <section className="ss-quote-hero" data-testid="ss-quote-hero">
            <span className="quote-mark" aria-hidden>&ldquo;</span>
            <div className="relative">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-mono uppercase tracking-[0.22em] font-bold" style={{ color: "#00A78B" }}>
                        {firstName ? `Welcome back, ${firstName}` : "Welcome back"}
                    </span>
                    {personalised && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-full bg-white/70 backdrop-blur"
                              style={{ color: "#2E7FC1" }}>
                            <Sparkles className="w-2.5 h-2.5" /> personalised
                        </span>
                    )}
                </div>
                <p className={`quote-body ${popping ? "ss-pop" : ""}`} data-testid="ss-quote-text">
                    {quote.text}
                </p>
                <div className="flex items-center gap-3 mt-6 flex-wrap">
                    <button
                        onClick={personalise}
                        disabled={aiBusy}
                        data-testid="ss-quote-personalise"
                        className="ss-btn-primary"
                    >
                        {aiBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                        {aiBusy ? "Generating…" : "Personalise for me"}
                    </button>
                    <button
                        onClick={shuffleCurated}
                        disabled={aiBusy}
                        data-testid="ss-quote-shuffle"
                        className="ss-btn-ghost"
                    >
                        <RefreshCw className="w-3.5 h-3.5" /> New quote
                    </button>
                    <span className="text-xs text-muted-foreground ml-auto italic hidden sm:inline">— {quote.author}</span>
                </div>
            </div>
        </section>
    );
}
