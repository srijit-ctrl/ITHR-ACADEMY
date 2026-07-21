import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import {
    Award, BookOpen, Flame, Sparkles, TrendingUp, Lock, ShieldCheck, Loader2,
    Save, ChevronRight, Eye, EyeOff, MapPin, Briefcase, Clock, PenSquare
} from "lucide-react";

import QuoteHero from "./QuoteHero";
import AvatarUploader from "./AvatarUploader";
import "@/styles/self-service.css";

/* ==========================================================================
 * Confetti burst — pure CSS, fired on avatar save / password change.
 * ========================================================================== */
function fireConfetti(container = document.body) {
    const wrap = document.createElement("div");
    wrap.className = "ss-confetti";
    const colors = ["#00A78B", "#2E7FC1", "#D4A836", "#F472B6", "#8B5CF6"];
    for (let i = 0; i < 60; i++) {
        const s = document.createElement("span");
        const angle = (Math.random() - 0.5) * 300;
        s.style.left = `${50 + (Math.random() - 0.5) * 60}%`;
        s.style.background = colors[i % colors.length];
        s.style.setProperty("--dx", `${angle}px`);
        s.style.animationDelay = `${Math.random() * 0.35}s`;
        s.style.transform = `rotate(${Math.random() * 360}deg)`;
        wrap.appendChild(s);
    }
    container.appendChild(wrap);
    setTimeout(() => wrap.remove(), 2200);
}

const firstNameOf = (u) => (u?.full_name || u?.email || "there").split(/[\s@]+/)[0];

/* ==========================================================================
 * SelfServicePortal — the "Profile" tab body on /dashboard.
 * ========================================================================== */
export default function SelfServicePortal() {
    const { refreshUser } = useAuth();
    const [profile, setProfile] = useState(null);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        try {
            const [p, s] = await Promise.all([
                api.get("/me"),
                api.get("/me/summary"),
            ]);
            setProfile(p.data.user);
            setSummary(s.data);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load profile");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    if (loading) {
        return (
            <div className="flex justify-center py-24">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
        );
    }
    if (!profile || !summary) return null;

    const first = firstNameOf(profile);
    const xpLevel = Math.min(100, Math.round((summary.user.xp || 0) % 500 / 5));
    const progressPct = Math.min(100, Math.round(summary.kpis.avg_progress_pct || 0));
    const certPct = summary.kpis.enrollments_total > 0
        ? Math.round((summary.kpis.certificates / summary.kpis.enrollments_total) * 100)
        : 0;

    const onAvatarUpdated = (updatedUser) => {
        setProfile((prev) => ({ ...prev, ...updatedUser }));
        setSummary((prev) => prev ? { ...prev, user: { ...prev.user, avatar_url: updatedUser.avatar_url } } : prev);
        refreshUser?.();
        fireConfetti();
    };

    return (
        <div className="ss-portal" data-testid="self-service-portal">
            {/* --- Motivational hero ------------------------------------- */}
            <QuoteHero firstName={first} />

            {/* --- Identity strip ---------------------------------------- */}
            <section className="mt-8 flex flex-col sm:flex-row items-start sm:items-center gap-6" data-testid="ss-identity-strip">
                <AvatarUploader user={profile} onUpdated={onAvatarUpdated} />
                <div className="flex-1 min-w-0">
                    <h1 className="font-serif text-3xl md:text-4xl leading-tight tracking-tight">
                        <span className="ss-underline">{profile.full_name || first}</span>
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1.5">{profile.email}</p>
                    <div className="flex flex-wrap gap-2 mt-3 items-center">
                        {(summary.user.streak_days || 0) > 0 && (
                            <span className="ss-flame" data-testid="ss-streak-flame">
                                <Flame className="fl-icon w-3.5 h-3.5" /> {summary.user.streak_days}-day streak
                            </span>
                        )}
                        {profile.founding_member_seq && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
                                  style={{ background: "linear-gradient(135deg, #D4A836 0%, #F5CB65 100%)", color: "#5A3F0A" }}>
                                <Sparkles className="w-3 h-3" /> Founding #{profile.founding_member_seq}
                            </span>
                        )}
                        {profile.title && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs bg-slate-100 text-slate-700">
                                <Briefcase className="w-3 h-3" /> {profile.title}
                            </span>
                        )}
                        {profile.location && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs bg-slate-100 text-slate-700">
                                <MapPin className="w-3 h-3" /> {profile.location}
                            </span>
                        )}
                    </div>
                </div>
            </section>

            {/* --- Stats grid -------------------------------------------- */}
            <section className="mt-10 grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="ss-stats-grid">
                <StatRing
                    testId="stat-progress"
                    tint="mint"
                    value={progressPct}
                    label="Avg progress"
                    icon={TrendingUp}
                    caption={`${summary.kpis.enrollments_in_progress} in progress`}
                />
                <StatRing
                    testId="stat-xp"
                    tint="sky"
                    value={xpLevel}
                    label={`${summary.user.xp || 0} XP`}
                    icon={Sparkles}
                    caption="Level XP progress"
                    ringColor="#2E7FC1"
                />
                <StatRing
                    testId="stat-cert-coverage"
                    tint="cream"
                    value={certPct}
                    label="Cert coverage"
                    icon={Award}
                    caption={`${summary.kpis.certificates} earned`}
                    ringColor="#D4A836"
                />
                <StatRing
                    testId="stat-courses"
                    tint="rose"
                    value={summary.kpis.enrollments_total > 0
                        ? Math.round((summary.kpis.enrollments_completed / summary.kpis.enrollments_total) * 100)
                        : 0}
                    label="Courses done"
                    icon={BookOpen}
                    caption={`${summary.kpis.enrollments_completed}/${summary.kpis.enrollments_total} completed`}
                    ringColor="#F472B6"
                />
            </section>

            {/* --- Next up -------------------------------------------------*/}
            {summary.next_up && (
                <section className="mt-8" data-testid="ss-next-up">
                    <h2 className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-3">Pick up where you left off</h2>
                    <Link
                        to={`/courses/${summary.next_up.slug}`}
                        className="ss-card ss-hover-lift flex items-center gap-4 no-underline"
                        data-testid="ss-next-up-link"
                    >
                        {summary.next_up.thumbnail_url && (
                            <div className="w-16 h-16 rounded-xl overflow-hidden shrink-0">
                                <img src={summary.next_up.thumbnail_url} alt="" className="w-full h-full object-cover" />
                            </div>
                        )}
                        <div className="flex-1 min-w-0">
                            <div className="font-serif text-lg text-foreground leading-tight truncate">{summary.next_up.title}</div>
                            <div className="ss-bar-track mt-3">
                                <div className="ss-bar-fill" style={{ width: `${summary.next_up.progress_pct}%` }} />
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">{summary.next_up.progress_pct}% complete</div>
                        </div>
                        <ChevronRight className="w-5 h-5 text-brand shrink-0" />
                    </Link>
                </section>
            )}

            {/* --- Two-column: profile form + password ----------------- */}
            <section className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <PersonalDetailsCard profile={profile} onSaved={(u) => { setProfile((prev) => ({ ...prev, ...u })); refreshUser?.(); }} />
                </div>
                <div>
                    <PasswordChangeCard canChangePassword={profile.can_change_password} />
                </div>
            </section>
        </div>
    );
}

/* --- Stat ring ---------------------------------------------------------- */
function StatRing({ testId, tint, value, label, icon: Icon, caption, ringColor = "#00A78B" }) {
    return (
        <div className={`ss-card tint-${tint} flex flex-col items-center text-center gap-2`} data-testid={testId}>
            <div className="ss-ring" style={{ "--ss-ring-value": value, "--ss-ring-color": ringColor }}>
                <div className="ss-ring-inner">
                    <div className="val">{value}%</div>
                    <div className="lab">Progress</div>
                </div>
            </div>
            <div className="text-sm font-semibold flex items-center gap-1.5 text-foreground">
                <Icon className="w-3.5 h-3.5" style={{ color: ringColor }} /> {label}
            </div>
            <div className="text-[11px] text-muted-foreground">{caption}</div>
        </div>
    );
}

/* --- Personal details card --------------------------------------------- */
function PersonalDetailsCard({ profile, onSaved }) {
    const [form, setForm] = useState({
        full_name: profile.full_name || "",
        title: profile.title || "",
        department: profile.department || "",
        location: profile.location || "",
        timezone: profile.timezone || "",
        bio: profile.bio || "",
    });
    const [busy, setBusy] = useState(false);

    const dirty = useMemo(() => (
        form.full_name !== (profile.full_name || "") ||
        form.title !== (profile.title || "") ||
        form.department !== (profile.department || "") ||
        form.location !== (profile.location || "") ||
        form.timezone !== (profile.timezone || "") ||
        form.bio !== (profile.bio || "")
    ), [form, profile]);

    const update = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

    const save = async (e) => {
        e.preventDefault();
        if (!dirty || busy) return;
        setBusy(true);
        try {
            const res = await api.patch("/me/profile", form);
            onSaved?.(res.data.user);
            toast.success("Profile updated");
        } catch (err) {
            toast.error(err?.response?.data?.detail || "Save failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="ss-card" data-testid="ss-personal-details">
            <div className="flex items-center gap-2 mb-5">
                <PenSquare className="w-4 h-4 text-brand" />
                <h2 className="font-serif text-xl leading-none">Personal details</h2>
            </div>
            <form onSubmit={save} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label className="ss-label">Full name</label>
                    <input value={form.full_name} onChange={update("full_name")} data-testid="ss-input-full-name" className="ss-input" />
                </div>
                <div>
                    <label className="ss-label">Job title</label>
                    <input value={form.title} onChange={update("title")} placeholder="e.g. Senior AI Engineer" data-testid="ss-input-title" className="ss-input" />
                </div>
                <div>
                    <label className="ss-label">Department</label>
                    <input value={form.department} onChange={update("department")} placeholder="e.g. Data Science" data-testid="ss-input-department" className="ss-input" />
                </div>
                <div>
                    <label className="ss-label">Location</label>
                    <input value={form.location} onChange={update("location")} placeholder="City, Country" data-testid="ss-input-location" className="ss-input" />
                </div>
                <div>
                    <label className="ss-label"><Clock className="w-3 h-3 inline mr-1" /> Timezone</label>
                    <input value={form.timezone} onChange={update("timezone")} placeholder="e.g. Asia/Dubai" data-testid="ss-input-timezone" className="ss-input" />
                </div>
                <div>
                    <label className="ss-label">Email (read-only)</label>
                    <input value={profile.email} disabled className="ss-input opacity-70 cursor-not-allowed" />
                </div>
                <div className="md:col-span-2">
                    <label className="ss-label">Short bio</label>
                    <textarea value={form.bio} onChange={update("bio")} rows={3}
                              placeholder="One sentence about what you're working on…"
                              data-testid="ss-input-bio"
                              className="ss-input resize-none" />
                    <div className="text-[10px] text-muted-foreground mt-1 font-mono">{form.bio.length}/500</div>
                </div>
                <div className="md:col-span-2 flex justify-end">
                    <button
                        type="submit"
                        disabled={!dirty || busy}
                        data-testid="ss-save-profile"
                        className="ss-btn-primary"
                    >
                        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        {busy ? "Saving…" : dirty ? "Save changes" : "All saved"}
                    </button>
                </div>
            </form>
        </div>
    );
}

/* --- Password change card ---------------------------------------------- */
function PasswordChangeCard({ canChangePassword }) {
    const [current, setCurrent] = useState("");
    const [next, setNext] = useState("");
    const [showCurrent, setShowCurrent] = useState(false);
    const [showNext, setShowNext] = useState(false);
    const [busy, setBusy] = useState(false);

    const strength = useMemo(() => {
        let s = 0;
        if (next.length >= 8) s += 1;
        if (next.length >= 12) s += 1;
        if (/[A-Z]/.test(next) && /[a-z]/.test(next)) s += 1;
        if (/[0-9]/.test(next)) s += 1;
        if (/[^A-Za-z0-9]/.test(next)) s += 1;
        return s;
    }, [next]);

    const strengthLabel = ["Too short", "Weak", "OK", "Good", "Strong", "Very strong"][Math.min(strength, 5)];
    const strengthPct = (strength / 5) * 100;

    if (!canChangePassword) {
        return (
            <div className="ss-card tint-sky" data-testid="ss-password-card">
                <div className="flex items-center gap-2 mb-4">
                    <ShieldCheck className="w-4 h-4 text-brand" />
                    <h2 className="font-serif text-xl leading-none">Password</h2>
                </div>
                <p className="text-sm text-muted-foreground">
                    Your account signs in with Google — passwords are managed by Google. Nothing to change here.
                </p>
            </div>
        );
    }

    const submit = async (e) => {
        e.preventDefault();
        if (!current || !next || busy) return;
        if (next.length < 8) { toast.error("Password must be at least 8 characters."); return; }
        setBusy(true);
        try {
            await api.post("/me/change-password", { current_password: current, new_password: next });
            toast.success("Password updated");
            setCurrent(""); setNext("");
            fireConfetti();
        } catch (err) {
            toast.error(err?.response?.data?.detail || "Password change failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="ss-card tint-mint" data-testid="ss-password-card">
            <div className="flex items-center gap-2 mb-5">
                <Lock className="w-4 h-4 text-brand" />
                <h2 className="font-serif text-xl leading-none">Change password</h2>
            </div>
            <form onSubmit={submit} className="space-y-4">
                <div>
                    <label className="ss-label">Current password</label>
                    <div className="relative">
                        <input
                            type={showCurrent ? "text" : "password"}
                            value={current}
                            onChange={(e) => setCurrent(e.target.value)}
                            data-testid="ss-current-password"
                            className="ss-input pr-10"
                        />
                        <button type="button" onClick={() => setShowCurrent((v) => !v)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                            {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                    </div>
                </div>
                <div>
                    <label className="ss-label">New password</label>
                    <div className="relative">
                        <input
                            type={showNext ? "text" : "password"}
                            value={next}
                            onChange={(e) => setNext(e.target.value)}
                            data-testid="ss-new-password"
                            minLength={8}
                            className="ss-input pr-10"
                        />
                        <button type="button" onClick={() => setShowNext((v) => !v)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                            {showNext ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                    </div>
                    {next && (
                        <div className="mt-2">
                            <div className="ss-bar-track">
                                <div className="ss-bar-fill" style={{ width: `${strengthPct}%` }} />
                            </div>
                            <div className="text-[10px] font-mono uppercase tracking-widest mt-1 text-muted-foreground">
                                Strength: {strengthLabel}
                            </div>
                        </div>
                    )}
                </div>
                <button
                    type="submit"
                    disabled={!current || !next || busy || next.length < 8}
                    data-testid="ss-change-password-btn"
                    className="ss-btn-primary w-full justify-center"
                >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                    {busy ? "Updating…" : "Update password"}
                </button>
            </form>
        </div>
    );
}
