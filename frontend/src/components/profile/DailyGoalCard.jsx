import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Target, Flame, Loader2, PencilLine, Check, X, Sparkles } from "lucide-react";

/**
 * DailyGoalCard — the habit engine card on the profile portal.
 *
 * Reads / writes GET+PATCH /api/me/daily-goal. Big ring shows today's
 * minutes vs target, 7-day heatmap dots strip below, and an inline
 * preset picker to change the target (5/15/30/60 min).
 */
export default function DailyGoalCard() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);

    const load = useCallback(async () => {
        try {
            const r = await api.get("/me/daily-goal");
            setData(r.data);
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Couldn't load daily goal");
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    const setTarget = async (minutes) => {
        setSaving(true);
        try {
            const r = await api.patch("/me/daily-goal", { target_minutes: minutes });
            setData(r.data);
            toast.success(`Daily goal set to ${minutes} min`);
            setEditing(false);
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Save failed");
        } finally { setSaving(false); }
    };

    if (loading) {
        return (
            <div className="ss-card tint-mint flex items-center justify-center py-10" data-testid="ss-daily-goal-card">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
        );
    }
    if (!data) return null;

    const { target_minutes, today, streak_days, week, preset_targets } = data;
    const message = motivatingCopy(today, streak_days);
    const ringColor = today.hit_goal ? "#0F7A55" : "#00A78B";

    return (
        <div className="ss-card tint-mint" data-testid="ss-daily-goal-card">
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                    <Target className="w-4 h-4" style={{ color: "#00A78B" }} />
                    <h2 className="font-serif text-xl leading-none">Daily learning goal</h2>
                </div>
                {!editing && (
                    <button
                        onClick={() => setEditing(true)}
                        data-testid="ss-goal-edit"
                        className="text-[10px] font-mono uppercase tracking-widest text-brand hover:text-brand-hover flex items-center gap-1"
                    >
                        <PencilLine className="w-3 h-3" /> Change target
                    </button>
                )}
            </div>

            {/* Target picker (inline edit) */}
            {editing && (
                <div className="mb-5 p-4 rounded-xl bg-white/70 backdrop-blur border border-border" data-testid="ss-goal-picker">
                    <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-2">
                        How many minutes per day?
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {preset_targets.map((m) => (
                            <button
                                key={m}
                                onClick={() => setTarget(m)}
                                disabled={saving}
                                data-testid={`ss-goal-preset-${m}`}
                                className={`px-4 py-2 rounded-full text-sm font-semibold transition-all border ${
                                    m === target_minutes
                                        ? "bg-brand text-white border-brand"
                                        : "bg-white text-foreground border-border hover:border-brand"
                                }`}
                            >
                                {m} min
                            </button>
                        ))}
                        <button
                            onClick={() => setEditing(false)}
                            className="ml-auto sa-icon-btn"
                            title="Cancel"
                            data-testid="ss-goal-cancel"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            )}

            {/* Ring + numbers */}
            <div className="flex flex-col sm:flex-row items-center gap-6">
                <div className="ss-ring shrink-0"
                     style={{ "--ss-ring-value": today.pct, "--ss-ring-color": ringColor, width: 140, height: 140 }}
                     data-testid="ss-goal-ring">
                    <div className="ss-ring-inner">
                        <div className="val" style={{ fontSize: 30 }}>
                            {today.minutes}<span className="text-base" style={{ color: "#94a3b8" }}>/{target_minutes}</span>
                        </div>
                        <div className="lab">MIN TODAY</div>
                    </div>
                </div>

                <div className="flex-1 min-w-0 text-center sm:text-left">
                    <p className="text-sm leading-relaxed" data-testid="ss-goal-message">
                        {message}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2 items-center justify-center sm:justify-start">
                        {streak_days > 0 && (
                            <span className="ss-flame" data-testid="ss-goal-streak">
                                <Flame className="fl-icon w-3.5 h-3.5" /> {streak_days}-day streak
                            </span>
                        )}
                        {today.hit_goal && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                                  style={{ background: "linear-gradient(135deg, #10B981 0%, #34D399 100%)", color: "#fff" }}>
                                <Check className="w-3 h-3" /> Goal hit
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Weekly heatmap */}
            <div className="mt-6" data-testid="ss-goal-heatmap">
                <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-2">
                    Last 7 days
                </div>
                <div className="grid grid-cols-7 gap-2">
                    {week.map((d, i) => (
                        <HeatmapDay key={d.date} day={d} isToday={i === week.length - 1} />
                    ))}
                </div>
            </div>
        </div>
    );
}

function HeatmapDay({ day, isToday }) {
    // Intensity: 0-4 buckets → shading
    const intensity = day.hit_goal
        ? 4
        : day.minutes >= 12 ? 3
        : day.minutes >= 6 ? 2
        : day.minutes > 0 ? 1
        : 0;
    const shades = [
        "rgba(203,213,225,0.35)",   // 0 · slate-300 ghost
        "rgba(74,222,128,0.35)",    // 1 · light green
        "rgba(52,211,153,0.65)",    // 2
        "rgba(20,184,166,0.85)",    // 3
        "#00A78B",                  // 4 · brand teal
    ];
    return (
        <div
            className={`flex flex-col items-center gap-1 py-2 rounded-lg ${isToday ? "ring-2 ring-brand/40" : ""}`}
            title={`${day.date} · ${day.minutes} min${day.hit_goal ? " · goal hit" : ""}`}
            data-testid={`ss-goal-day-${day.date}`}
        >
            <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-mono font-bold text-white"
                style={{ background: shades[intensity] }}
            >
                {day.minutes > 0 ? day.minutes : ""}
            </div>
            <div className="text-[10px] uppercase font-mono tracking-widest text-muted-foreground">
                {day.day_of_week}
            </div>
        </div>
    );
}

function motivatingCopy(today, streak) {
    if (today.hit_goal && streak >= 7) {
        return `A full week hitting your goal — you're on a legendary run. Keep the momentum.`;
    }
    if (today.hit_goal && streak > 1) {
        return `Nailed today's goal and rolling on a ${streak}-day streak. Tomorrow adds to it.`;
    }
    if (today.hit_goal) {
        return `Today's goal is in the bag. Consistency beats intensity — see you tomorrow.`;
    }
    if (today.remaining_minutes <= 5 && today.remaining_minutes > 0) {
        return `Just ${today.remaining_minutes} minutes to your daily target. One lesson away.`;
    }
    if (today.pct >= 50) {
        return `Halfway there. Finish a module now and lock in the day.`;
    }
    if (today.pct > 0) {
        return `You've made a start today. Keep going for ${today.remaining_minutes} more min.`;
    }
    if (streak > 0) {
        return `Your ${streak}-day streak is alive — 15 min of learning keeps it going.`;
    }
    return `The best time to build a learning habit is now. Even one lesson counts.`;
}
