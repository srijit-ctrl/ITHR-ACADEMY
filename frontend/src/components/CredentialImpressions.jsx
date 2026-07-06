import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Eye, TrendingUp } from "lucide-react";

/**
 * Credential impressions widget — surfaces verify-page visits so credential
 * holders can see when recruiters / hiring managers / partners are checking
 * their work. Empty state is deliberately warm rather than empty-looking.
 */
export default function CredentialImpressions() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.get("/certificates/impressions")
            .then((r) => setData(r.data))
            .catch(() => setData(null))
            .finally(() => setLoading(false));
    }, []);

    if (loading || !data) return null;

    // Only render if the user has AT LEAST one certificate (per-cert list has entries)
    // OR has any all-time impression. Otherwise the widget adds no signal.
    const hasAny = data.total_all_time > 0 || (data.by_certificate?.length || 0) > 0;
    if (!hasAny) return null;

    return (
        <section className="card-flat p-6" data-testid="credential-impressions">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Eye className="w-4 h-4 text-brand" />
                    <div className="overline">Credential Impressions</div>
                </div>
                {data.total_last_30d >= 3 && (
                    <div className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-[0.15em] text-brand">
                        <TrendingUp className="w-3 h-3" /> Being verified
                    </div>
                )}
            </div>

            <div className="grid grid-cols-3 gap-4 mb-5">
                <StatMini value={data.total_this_month} label="This month" testId="impressions-month" accent />
                <StatMini value={data.total_last_30d} label="Last 30 days" testId="impressions-30d" />
                <StatMini value={data.total_all_time} label="All time" testId="impressions-all" />
            </div>

            {(data.by_certificate || []).length > 0 && (
                <div className="border-t border-border pt-4">
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2">
                        Most-verified credentials
                    </div>
                    <ul className="space-y-1.5">
                        {data.by_certificate.slice(0, 3).map((c) => (
                            <li key={c.certificate_id} className="flex items-baseline justify-between text-sm" data-testid={`impr-cert-${c.certificate_id}`}>
                                <span className="truncate mr-3 text-foreground">{c.course_title}</span>
                                <span className="font-mono text-xs text-brand shrink-0">
                                    {c.impressions}× {c.impressions === 1 ? "verify" : "verifies"}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <p className="text-[11px] leading-relaxed text-muted-foreground mt-4">
                An impression is a unique verifier per day. Someone likely checked your credential during a
                recruiting or partnership process — good time to make sure your <a href="/passport" className="text-brand hover:underline">AI Skills Passport</a> is up to date.
            </p>
        </section>
    );
}

function StatMini({ value, label, testId, accent }) {
    return (
        <div className={accent ? "border-l-2 border-brand pl-3" : "border-l border-border pl-3"} data-testid={testId}>
            <div className={`font-serif text-3xl leading-none ${accent ? "text-brand" : "text-foreground"}`}>{value}</div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1.5">{label}</div>
        </div>
    );
}
