import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Activity, Award, Building2, GraduationCap, UserPlus, Loader2 } from "lucide-react";

const POLL_INTERVAL_MS = 3000;
const FEED_LIMIT = 25;

// Icon per event kind. Falls back to <Activity> for unknown kinds.
const KIND_META = {
    signup:       { icon: UserPlus,      color: "text-brand-teal",   label: "Signup" },
    enrollment:   { icon: GraduationCap, color: "text-brand",        label: "Enrollment" },
    certificate:  { icon: Award,         color: "text-brand-gold",   label: "Certificate" },
    org_created:  { icon: Building2,     color: "text-foreground",   label: "New Org" },
    other:        { icon: Activity,      color: "text-muted-foreground", label: "Event" },
};

/**
 * Live activity feed for the super-admin dashboard.
 *
 * Polls /api/admin/activity/recent every 3s. On the first fetch pulls the
 * last 25 events; subsequent polls use `since=<latest_ts>` for delta only.
 * The feed keeps the running window at 25 items — older events roll off the
 * top of the DOM as new ones stream in.
 */
export default function ActivityFeedPanel() {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [live, setLive] = useState(true);
    const latestTsRef = useRef(null);

    const fetchOnce = useCallback(async (isInitial) => {
        try {
            const params = isInitial ? { limit: FEED_LIMIT } : { since: latestTsRef.current };
            const { data } = await api.get("/admin/activity/recent", { params });
            const incoming = data.events || [];
            if (incoming.length > 0) {
                latestTsRef.current = incoming[0].created_at;
                setEvents((prev) => {
                    const merged = [...incoming, ...prev];
                    // De-dupe by id + keep newest FEED_LIMIT
                    const seen = new Set();
                    const dedup = [];
                    for (const e of merged) {
                        if (!seen.has(e.id)) { seen.add(e.id); dedup.push(e); }
                    }
                    return dedup.slice(0, FEED_LIMIT);
                });
            }
        } catch (e) {
            // Silent — polling recovers on next tick. Log to devtools only
            // so operators can spot sustained failures without console spam.
            console.debug("[ActivityFeed] poll failed:", e?.message);
        } finally {
            if (isInitial) setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchOnce(true);
    }, [fetchOnce]);

    useEffect(() => {
        if (!live) return;
        const id = setInterval(() => fetchOnce(false), POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, [live, fetchOnce]);

    return (
        <section className="card-flat p-6" data-testid="activity-feed-panel">
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Activity className="w-4 h-4 text-brand" />
                        {live && <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-brand rounded-full animate-pulse" />}
                    </div>
                    <div className="overline">Live activity</div>
                </div>
                <button
                    onClick={() => setLive((v) => !v)}
                    data-testid="activity-feed-toggle"
                    className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground"
                >
                    {live ? "Pause" : "Resume"}
                </button>
            </div>

            {loading && (
                <div className="flex items-center justify-center py-10">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
            )}

            {!loading && events.length === 0 && (
                <div className="text-sm text-muted-foreground text-center py-8" data-testid="activity-feed-empty">
                    No platform activity in the last 7 days yet. New signups, enrollments, and certificate awards will stream in here as they happen.
                </div>
            )}

            {!loading && events.length > 0 && (
                <ul className="space-y-3 max-h-[440px] overflow-y-auto pr-1" data-testid="activity-feed-list">
                    {events.map((e) => (
                        <FeedRow key={e.id} event={e} />
                    ))}
                </ul>
            )}
        </section>
    );
}

function FeedRow({ event }) {
    const meta = KIND_META[event.kind] || KIND_META.other;
    const Icon = meta.icon;
    return (
        <li className="flex items-start gap-3 pb-3 border-b border-border last:border-b-0" data-testid={`activity-row-${event.id}`}>
            <div className={`w-8 h-8 shrink-0 rounded-sm bg-surface-alt flex items-center justify-center ${meta.color}`}>
                <Icon className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="text-sm leading-snug text-foreground">{event.message}</div>
                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-0.5">
                    {meta.label} · {formatRelative(event.created_at)}
                </div>
            </div>
        </li>
    );
}

function formatRelative(iso) {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const s = Math.max(0, Math.floor((now - then) / 1000));
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
}
