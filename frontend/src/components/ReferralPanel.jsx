import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Copy, Gift, Users, Loader2, Check, Linkedin, MessageCircle, Trophy, Crown } from "lucide-react";
import useFlags from "@/hooks/useFlags";
import { toast } from "sonner";

export const ReferralPanel = () => {
    const { isEnabled } = useFlags();
    const [data, setData] = useState(null);
    const [courses, setCourses] = useState([]);
    const [pick, setPick] = useState("");
    const [redeeming, setRedeeming] = useState(false);
    const [leaderboard, setLeaderboard] = useState(null);

    const load = () => api.get("/referrals/me").then((r) => setData(r.data)).catch(() => {});

    useEffect(() => { load(); }, []);

    useEffect(() => {
        if (!isEnabled("referrals")) return;
        api.get("/referrals/leaderboard?limit=10")
            .then((r) => setLeaderboard(r.data))
            .catch(() => {});
    }, [isEnabled]);

    useEffect(() => {
        if (data?.rewards_available > 0 && courses.length === 0) {
            api.get("/courses").then((r) => setCourses(r.data || [])).catch(() => {});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    if (!isEnabled("referrals") || !data?.code) return null;

    const copy = (text, label) => {
        navigator.clipboard.writeText(text);
        toast.success(`${label} copied`);
    };

    const redeem = async () => {
        if (!pick) return;
        setRedeeming(true);
        try {
            const r = await api.post("/referrals/redeem", { course_slug: pick });
            toast.success(`Enrolled free in "${r.data.enrolled_course}"`);
            setPick("");
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Redemption failed");
        } finally {
            setRedeeming(false);
        }
    };

    const signups = data.signups || [];

    return (
        <section className="mb-14" data-testid="referral-panel">
            <div className="flex items-baseline justify-between mb-5">
                <h2 className="font-serif text-2xl tracking-tight">Refer &amp; earn</h2>
                <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Up to 5 free courses</span>
            </div>
            <div className="card-flat p-6 md:p-8 grid grid-cols-1 md:grid-cols-12 gap-8">
                <div className="md:col-span-5">
                    <div className="overline mb-3 flex items-center gap-2"><Gift className="w-3.5 h-3.5 text-brand" /> Your referral code</div>
                    <div className="flex items-center gap-2 mb-3">
                        <code data-testid="referral-code" className="font-mono text-lg tracking-[0.2em] bg-surface border border-dashed border-brand text-brand px-4 py-2.5 flex-1 text-center">{data.code}</code>
                        <button onClick={() => copy(data.code, "Code")} data-testid="referral-copy-code" className="border border-border hover:border-brand p-3 transition-colors" title="Copy code">
                            <Copy className="w-4 h-4" />
                        </button>
                    </div>
                    <button onClick={() => copy(data.share_url, "Share link")} data-testid="referral-copy-link" className="text-xs text-brand hover:underline font-mono break-all text-left">
                        {data.share_url}
                    </button>
                    <div className="flex gap-2 mt-3">
                        <a
                            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(data.share_url)}`}
                            target="_blank" rel="noopener noreferrer"
                            data-testid="referral-share-linkedin"
                            className="flex-1 flex items-center justify-center gap-2 border border-border hover:border-[#0A66C2] hover:text-[#0A66C2] rounded-sm px-3 py-2 text-xs font-medium transition-colors"
                        >
                            <Linkedin className="w-3.5 h-3.5" /> Share on LinkedIn
                        </a>
                        <a
                            href={`https://wa.me/?text=${encodeURIComponent(`Your first AI course at ITHR Academy is free with my referral code ${data.code} — enroll here: ${data.share_url}`)}`}
                            target="_blank" rel="noopener noreferrer"
                            data-testid="referral-share-whatsapp"
                            className="flex-1 flex items-center justify-center gap-2 border border-border hover:border-[#25D366] hover:text-[#128C4A] rounded-sm px-3 py-2 text-xs font-medium transition-colors"
                        >
                            <MessageCircle className="w-3.5 h-3.5" /> WhatsApp
                        </a>
                    </div>
                    <p className="text-sm text-muted-foreground mt-4 leading-relaxed">
                        Share with up to {data.max_uses} people. They get their first course free — and each one who enrolls unlocks a free course of your choice for you.
                    </p>
                </div>
                <div className="md:col-span-3">
                    <div className="overline mb-3 flex items-center gap-2"><Users className="w-3.5 h-3.5 text-brand" /> Signups {signups.length}/{data.max_uses}</div>
                    <div className="flex gap-1.5 mb-4">
                        {Array.from({ length: data.max_uses }).map((_, i) => (
                            <div key={i} className={`h-2 flex-1 ${i < signups.length ? (signups[i]?.converted ? "bg-brand" : "bg-brand/40") : "bg-border"}`} />
                        ))}
                    </div>
                    {signups.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No referrals yet — share your code to start earning.</p>
                    ) : (
                        <ul className="space-y-1.5">
                            {signups.map((s, i) => (
                                <li key={i} className="text-xs flex items-center gap-2 text-muted-foreground">
                                    {s.converted ? <Check className="w-3 h-3 text-brand shrink-0" /> : <span className="w-3 h-3 rounded-full border border-border shrink-0" />}
                                    <span className="truncate">{s.referred_email}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
                <div className="md:col-span-4 md:border-l md:border-border md:pl-8">
                    <div className="overline mb-3">Rewards</div>
                    <div className="font-serif text-4xl tracking-tighter mb-1" data-testid="referral-rewards-count">{data.rewards_available}</div>
                    <div className="text-xs text-muted-foreground mb-4">free course{data.rewards_available === 1 ? "" : "s"} available to redeem</div>
                    {data.rewards_available > 0 && (
                        <div className="space-y-2">
                            <select value={pick} onChange={(e) => setPick(e.target.value)} data-testid="referral-redeem-select" className="w-full bg-surface border border-border rounded-sm px-3 py-2.5 text-sm focus:outline-none focus:border-brand">
                                <option value="">Choose a course…</option>
                                {courses.map((c) => <option key={c.slug} value={c.slug}>{c.title}</option>)}
                            </select>
                            <button onClick={redeem} disabled={!pick || redeeming} data-testid="referral-redeem-btn" className="btn-primary w-full text-sm">
                                {redeeming ? <Loader2 className="w-4 h-4 animate-spin" /> : "Redeem free course"}
                            </button>
                        </div>
                    )}
                    {data.rewards_redeemed?.length > 0 && (
                        <ul className="mt-4 space-y-1">
                            {data.rewards_redeemed.map((r, i) => (
                                <li key={i} className="text-xs text-muted-foreground flex items-center gap-2">
                                    <Check className="w-3 h-3 text-brand" /> {r.course_title}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>

            {leaderboard && leaderboard.rows.length > 0 && (
                <div className="card-flat p-6 md:p-7 mt-5" data-testid="referral-leaderboard">
                    <div className="flex items-baseline justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <Trophy className="w-4 h-4 text-brand" />
                            <h3 className="font-serif text-xl tracking-tight">Founding referrers · Leaderboard</h3>
                        </div>
                        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                            {leaderboard.totals.referrers} referrers · {leaderboard.totals.converted} conversions
                        </span>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm" data-testid="referral-leaderboard-table">
                            <thead>
                                <tr className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-b border-border">
                                    <th className="text-left py-2 pr-4 w-14">Rank</th>
                                    <th className="text-left py-2 pr-4">Referrer</th>
                                    <th className="text-left py-2 pr-4 hidden md:table-cell">Organization</th>
                                    <th className="text-right py-2 pr-4">Signups</th>
                                    <th className="text-right py-2">Converted</th>
                                </tr>
                            </thead>
                            <tbody>
                                {leaderboard.rows.map((row) => {
                                    const isMe = leaderboard.viewer_rank === row.rank && (leaderboard.viewer_stats?.name || "") === row.name;
                                    return (
                                        <tr
                                            key={row.rank}
                                            data-testid={`leaderboard-row-${row.rank}`}
                                            className={`border-b border-border/40 ${isMe ? "bg-brand/5" : ""}`}
                                        >
                                            <td className="py-2.5 pr-4 font-mono text-xs">
                                                {row.rank === 1 ? (
                                                    <span className="inline-flex items-center gap-1 text-brand">
                                                        <Crown className="w-3.5 h-3.5" /> 1
                                                    </span>
                                                ) : `#${row.rank}`}
                                            </td>
                                            <td className="py-2.5 pr-4">{row.name}{isMe && <span className="ml-2 text-[10px] font-mono uppercase tracking-[0.15em] text-brand">You</span>}</td>
                                            <td className="py-2.5 pr-4 hidden md:table-cell text-muted-foreground truncate max-w-[220px]">{row.organization || "—"}</td>
                                            <td className="py-2.5 pr-4 text-right font-mono">{row.signups}</td>
                                            <td className="py-2.5 text-right font-mono text-brand">{row.converted}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <div className="mt-4 flex items-center justify-between text-xs" data-testid="referral-leaderboard-you">
                        {leaderboard.viewer_stats ? (
                            leaderboard.viewer_rank ? (
                                <p className="text-muted-foreground">
                                    You are <b className="text-brand font-mono">#{leaderboard.viewer_rank}</b> with{" "}
                                    <b className="text-foreground">{leaderboard.viewer_stats.signups}</b> signup{leaderboard.viewer_stats.signups === 1 ? "" : "s"} ·{" "}
                                    <b className="text-brand">{leaderboard.viewer_stats.converted}</b> converted.
                                </p>
                            ) : (
                                <p className="text-muted-foreground italic">
                                    Refer your first professional to appear on this leaderboard.
                                </p>
                            )
                        ) : <span />}
                        <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground/70">
                            Names masked · public view
                        </span>
                    </div>
                </div>
            )}
        </section>
    );
};
