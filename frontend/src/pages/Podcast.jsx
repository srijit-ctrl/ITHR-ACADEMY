import { useEffect, useState } from "react";
import { Headphones, Rss, Loader2, Calendar, Signal, GraduationCap } from "lucide-react";
import { api, API_BASE } from "@/lib/api";
import HeroBlobs from "@/components/HeroBlobs";

/**
 * /podcast — public episode list + inline HTML5 audio player.
 * Every Monday, a new 5-minute Executive Briefing lands here (and in the
 * RSS feed at /api/podcast/rss.xml).
 */
export default function Podcast() {
    const [episodes, setEpisodes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const rssUrl = `${API_BASE}/podcast/rss.xml`;

    useEffect(() => {
        api.get("/podcast/episodes")
            .then((r) => setEpisodes(r.data.episodes || []))
            .catch((e) => setError(e?.response?.data?.detail || "Couldn't load episodes."))
            .finally(() => setLoading(false));
    }, []);

    const fmtDate = (iso) => {
        if (!iso) return "";
        try {
            return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
        } catch { return iso.slice(0, 10); }
    };
    const fmtDuration = (secs) => {
        const m = Math.max(1, Math.round((secs || 300) / 60));
        return `${m} min`;
    };

    return (
        <div>
            <section className="relative overflow-hidden bg-white">
                <HeroBlobs variant="cool" />
                <div className="relative container-narrow pt-16 pb-10 text-center z-10">
                    <span className="section-kicker">Weekly Executive Briefing</span>
                    <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-4">
                        Five minutes. <span className="italic text-brand">Every Monday.</span>
                    </h1>
                    <p className="text-muted-foreground text-lg max-w-2xl mx-auto mb-6">
                        The three signals every enterprise leader should track this week, and one featured Academy program &mdash; narrated by Aletheia. Subscribe to your favourite podcast app.
                    </p>
                    <div className="flex items-center justify-center gap-3 flex-wrap">
                        <a
                            href={rssUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            data-testid="podcast-rss-link"
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-border bg-surface-alt text-sm hover:border-brand hover:text-brand transition-colors"
                        >
                            <Rss className="w-4 h-4" /> Subscribe via RSS
                        </a>
                        <span className="text-xs text-muted-foreground font-mono uppercase tracking-[0.15em]">Or add the RSS URL to Apple Podcasts &middot; Spotify &middot; Overcast</span>
                    </div>
                </div>
            </section>

            <div className="container-narrow pb-20">
                {loading && (
                    <div className="py-24 flex items-center justify-center text-muted-foreground" data-testid="podcast-loading">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading episodes…
                    </div>
                )}

                {!loading && error && (
                    <div className="card-flat p-8 text-center" data-testid="podcast-error">
                        <p className="text-sm text-muted-foreground">{error}</p>
                    </div>
                )}

                {!loading && !error && episodes.length === 0 && (
                    <div className="card-flat p-12 text-center" data-testid="podcast-empty">
                        <Headphones className="w-10 h-10 text-brand mx-auto mb-4" />
                        <p className="font-serif text-xl mb-1">No episodes yet.</p>
                        <p className="text-sm text-muted-foreground">The first Weekly Executive Briefing will publish soon. Subscribe to be notified.</p>
                    </div>
                )}

                {!loading && !error && episodes.length > 0 && (
                    <div className="space-y-6" data-testid="podcast-list">
                        {episodes.map((ep) => (
                            <EpisodeCard key={ep.id} ep={ep} fmtDate={fmtDate} fmtDuration={fmtDuration} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function EpisodeCard({ ep, fmtDate, fmtDuration }) {
    return (
        <article
            className="card-flat p-8"
            data-testid={`podcast-episode-${ep.id}`}
        >
            <div className="flex flex-wrap items-center gap-3 mb-3 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                <span className="badge-mono">{ep.week_key}</span>
                <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{fmtDate(ep.published_at)}</span>
                <span className="flex items-center gap-1"><Headphones className="w-3 h-3" />{fmtDuration(ep.duration_seconds_est)}</span>
            </div>
            <h2 className="font-serif text-2xl md:text-3xl leading-tight mb-3">{ep.title}</h2>
            {ep.summary && <p className="text-sm text-muted-foreground leading-relaxed mb-5 max-w-3xl">{ep.summary}</p>}

            <audio
                controls
                preload="none"
                src={ep.audio_url}
                data-testid={`podcast-audio-${ep.id}`}
                className="w-full mb-5"
            >
                Your browser does not support audio playback.
            </audio>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-5 border-t border-border">
                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2 flex items-center gap-1.5">
                        <Signal className="w-3 h-3" /> In this episode
                    </div>
                    <ul className="text-sm space-y-1.5">
                        {(ep.signals || []).map((s) => (
                            <li key={s.id || s.title} className="leading-snug">&middot; {s.title}</li>
                        ))}
                    </ul>
                </div>
                {ep.featured_course && (
                    <div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2 flex items-center gap-1.5">
                            <GraduationCap className="w-3 h-3" /> Featured program
                        </div>
                        <a
                            href={`/courses/${ep.featured_course.slug}`}
                            className="text-sm font-serif hover:text-brand transition-colors"
                            data-testid={`podcast-featured-${ep.id}`}
                        >
                            {ep.featured_course.title} &rarr;
                        </a>
                    </div>
                )}
            </div>
        </article>
    );
}
