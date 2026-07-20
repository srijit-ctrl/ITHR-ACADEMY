import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Mail, Send, Loader2, Eye, Users, ScrollText, RefreshCcw, TestTube } from "lucide-react";
import { toast } from "sonner";

/**
 * Super-Admin Email Campaigns composer + history log.
 *
 * Basic v1 (segmentation: all-learners / role / by-course / founding-only).
 * Preview counts recipient before send. Test-send fires to a single QA email
 * without logging a campaign. Send-to-all requires a typed confirmation.
 */
export default function EmailCampaignsPanel() {
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [ctaLabel, setCtaLabel] = useState("");
    const [ctaUrl, setCtaUrl] = useState("");
    const [segment, setSegment] = useState("all_learners");
    const [role, setRole] = useState("learner");
    const [courseSlug, setCourseSlug] = useState("");
    const [courses, setCourses] = useState([]);

    const [preview, setPreview] = useState(null);
    const [previewing, setPreviewing] = useState(false);
    const [testEmail, setTestEmail] = useState("");
    const [testSending, setTestSending] = useState(false);
    const [sending, setSending] = useState(false);
    const [confirm, setConfirm] = useState(false);
    const [typedConfirm, setTypedConfirm] = useState("");
    const [history, setHistory] = useState([]);
    const [reengBusy, setReengBusy] = useState(false);

    const filterSpec = useMemo(() => {
        const f = { segment };
        if (segment === "role") f.role = role;
        if (segment === "by_course") f.course_slug = courseSlug;
        return f;
    }, [segment, role, courseSlug]);

    const loadCourses = useCallback(async () => {
        try {
            const res = await api.get("/courses");
            const list = res.data || [];
            setCourses(list);
            if (!courseSlug && list.length > 0) setCourseSlug(list[0].slug);
        } catch (e) {
            console.debug("[campaigns] course fetch failed", e?.message);
        }
    }, [courseSlug]);

    const loadHistory = useCallback(async () => {
        try {
            const res = await api.get("/admin/campaigns/history");
            setHistory(res.data.campaigns || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load campaign history");
        }
    }, []);

    useEffect(() => {
        loadCourses();
        loadHistory();
    }, [loadCourses, loadHistory]);

    // Auto-preview on filter change (debounced).
    useEffect(() => {
        const t = setTimeout(async () => {
            setPreviewing(true);
            try {
                const res = await api.post("/admin/campaigns/preview", { filter: filterSpec });
                setPreview(res.data);
            } catch (e) {
                setPreview(null);
            } finally {
                setPreviewing(false);
            }
        }, 300);
        return () => clearTimeout(t);
    }, [filterSpec]);

    const canSend = subject.trim().length > 3 && body.trim().length > 10 && (preview?.count || 0) > 0;
    const canTest = subject.trim().length > 3 && body.trim().length > 10 && testEmail.includes("@");

    const doTestSend = async () => {
        setTestSending(true);
        try {
            const res = await api.post("/admin/campaigns/test-send", {
                subject, body_markdown: body, test_recipient: testEmail,
                cta_label: ctaLabel || null, cta_url: ctaUrl || null,
            });
            toast.success(`Test email sent to ${res.data.recipient} (delivered=${res.data.delivered})`);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Test send failed");
        } finally { setTestSending(false); }
    };

    const doSend = async () => {
        if (typedConfirm !== "SEND") {
            toast.error("Type SEND in the confirmation box to dispatch");
            return;
        }
        setSending(true);
        try {
            const res = await api.post("/admin/campaigns/send", {
                subject, body_markdown: body, filter: filterSpec,
                cta_label: ctaLabel || null, cta_url: ctaUrl || null,
            });
            toast.success(`Campaign dispatched · ${res.data.delivered_count}/${res.data.total_recipients} delivered`);
            setConfirm(false);
            setTypedConfirm("");
            setSubject("");
            setBody("");
            setCtaLabel("");
            setCtaUrl("");
            loadHistory();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Campaign send failed");
        } finally { setSending(false); }
    };

    const runReengagement = async (dry) => {
        setReengBusy(true);
        try {
            const res = await api.post(`/admin/campaigns/reengagement/run?dry_run=${dry}`);
            const d = res.data;
            toast.success(
                dry
                    ? `Re-engagement dry-run · ${d.eligible} eligible learners`
                    : `Re-engagement sweep sent · ${d.sent} emails (${d.errors} errors)`
            );
        } catch (e) {
            toast.error(e.response?.data?.detail || "Sweep failed");
        } finally { setReengBusy(false); }
    };

    return (
        <div data-testid="campaigns-panel">
            <div className="mb-6 flex items-center gap-3">
                <Mail className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl">Email campaigns</h2>
            </div>
            <p className="text-sm text-muted-foreground mb-6 max-w-2xl">
                Compose bulk campaigns, target a segment, preview the recipient count, and dispatch.
                Automated lifecycle triggers (module completion, module-5 offer, 7-day re-engagement)
                also live here — see the panel at the bottom.
            </p>

            {/* ---- Composer ---- */}
            <div className="grid lg:grid-cols-3 gap-6 mb-8">
                <div className="lg:col-span-2 space-y-4">
                    <FieldLabel>Subject line</FieldLabel>
                    <input
                        type="text"
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                        placeholder="ITHR Academy · New enterprise course live"
                        data-testid="campaign-subject"
                        className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand"
                    />

                    <FieldLabel>Body (paragraphs separated by blank line)</FieldLabel>
                    <textarea
                        value={body}
                        onChange={(e) => setBody(e.target.value)}
                        rows={10}
                        placeholder={"Hello,\n\nWe just added a new enterprise course covering RAG evaluation for regulated industries.\n\nHave a look and tell us what's missing.\n\nWarmly,\nThe ITHR team"}
                        data-testid="campaign-body"
                        className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm leading-relaxed focus:outline-none focus:border-brand"
                    />

                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <FieldLabel>CTA button label (optional)</FieldLabel>
                            <input
                                type="text"
                                value={ctaLabel}
                                onChange={(e) => setCtaLabel(e.target.value)}
                                placeholder="See the New Course"
                                data-testid="campaign-cta-label"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand"
                            />
                        </div>
                        <div>
                            <FieldLabel>CTA button URL (optional)</FieldLabel>
                            <input
                                type="url"
                                value={ctaUrl}
                                onChange={(e) => setCtaUrl(e.target.value)}
                                placeholder="https://ithr.online/courses/rag-fundamentals"
                                data-testid="campaign-cta-url"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand"
                            />
                        </div>
                    </div>
                </div>

                <div className="space-y-4">
                    <div className="card-flat p-4">
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">Audience</div>
                        <label className="block mb-3">
                            <div className="text-xs text-muted-foreground mb-1">Segment</div>
                            <select
                                value={segment}
                                onChange={(e) => setSegment(e.target.value)}
                                data-testid="campaign-segment"
                                className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm"
                            >
                                <option value="all_learners">All learners</option>
                                <option value="role">By role</option>
                                <option value="by_course">By course enrollment</option>
                                <option value="founding_only">Founding cohort only (first 500)</option>
                            </select>
                        </label>

                        {segment === "role" && (
                            <label className="block mb-3">
                                <div className="text-xs text-muted-foreground mb-1">Role</div>
                                <select
                                    value={role}
                                    onChange={(e) => setRole(e.target.value)}
                                    data-testid="campaign-role"
                                    className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm"
                                >
                                    <option value="learner">Learner</option>
                                    <option value="instructor">Instructor</option>
                                    <option value="corporate_admin">Corporate admin</option>
                                </select>
                            </label>
                        )}

                        {segment === "by_course" && (
                            <label className="block mb-3">
                                <div className="text-xs text-muted-foreground mb-1">Course</div>
                                <select
                                    value={courseSlug}
                                    onChange={(e) => setCourseSlug(e.target.value)}
                                    data-testid="campaign-course"
                                    className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm"
                                >
                                    {courses.map(c => (
                                        <option key={c.slug} value={c.slug}>{c.title}</option>
                                    ))}
                                </select>
                            </label>
                        )}

                        <div className="border-t border-border pt-3">
                            <div className="flex items-center gap-2 mb-2">
                                <Users className="w-4 h-4 text-brand" />
                                <span className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">Recipients</span>
                            </div>
                            {previewing ? (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> counting…
                                </div>
                            ) : (
                                <div>
                                    <div className="font-serif text-2xl text-brand" data-testid="campaign-recipient-count">
                                        {preview?.count ?? "—"}
                                    </div>
                                    {preview?.truncated && (
                                        <div className="text-[10px] text-destructive mt-1">
                                            Capped at {preview.max_recipients}. Narrow the segment to reach more.
                                        </div>
                                    )}
                                    {preview?.sample_emails?.length > 0 && (
                                        <div className="text-[10px] text-muted-foreground mt-2 leading-snug break-all">
                                            <span className="font-mono">Sample:</span><br />
                                            {preview.sample_emails.slice(0, 3).join(", ")}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="card-flat p-4">
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">QA test send</div>
                        <input
                            type="email"
                            value={testEmail}
                            onChange={(e) => setTestEmail(e.target.value)}
                            placeholder="you@ithr.online"
                            data-testid="campaign-test-email"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm mb-2 focus:outline-none focus:border-brand"
                        />
                        <button
                            onClick={doTestSend}
                            disabled={!canTest || testSending}
                            data-testid="campaign-test-send-btn"
                            className="btn-outline w-full text-sm"
                        >
                            {testSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <><TestTube className="w-4 h-4" /> Send test only</>}
                        </button>
                    </div>
                </div>
            </div>

            {/* ---- Send button + confirmation ---- */}
            <div className="border-t border-border pt-6 mb-8 flex justify-end">
                {!confirm ? (
                    <button
                        onClick={() => setConfirm(true)}
                        disabled={!canSend}
                        data-testid="campaign-open-send-modal"
                        className="btn-primary"
                    >
                        <Send className="w-4 h-4" /> Send to {preview?.count || 0} recipients
                    </button>
                ) : (
                    <div className="card-flat p-4 border-brand max-w-md w-full space-y-3" data-testid="campaign-confirm-box">
                        <div className="text-sm">
                            <b>Confirm dispatch.</b> You are about to email{" "}
                            <b className="text-brand">{preview?.count || 0}</b> recipients. This action cannot be undone.
                        </div>
                        <input
                            type="text"
                            value={typedConfirm}
                            onChange={(e) => setTypedConfirm(e.target.value.toUpperCase())}
                            placeholder="Type SEND to confirm"
                            data-testid="campaign-typed-confirm"
                            className="w-full bg-surface border border-border rounded-sm px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand"
                        />
                        <div className="flex gap-2 justify-end">
                            <button onClick={() => { setConfirm(false); setTypedConfirm(""); }} className="btn-outline text-sm">Cancel</button>
                            <button
                                onClick={doSend}
                                disabled={typedConfirm !== "SEND" || sending}
                                data-testid="campaign-dispatch-btn"
                                className="btn-primary text-sm"
                            >
                                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Dispatch</>}
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* ---- Re-engagement sweep ---- */}
            <div className="card-flat p-5 mb-8">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <RefreshCcw className="w-4 h-4 text-brand" />
                            <h3 className="font-serif text-lg">Automated · 7-day re-engagement sweep</h3>
                        </div>
                        <p className="text-sm text-muted-foreground max-w-xl">
                            Finds learners registered ≥ 7 days ago who have not touched any enrolment
                            or completed any lesson in the last 7 days, and sends a warm re-entry email.
                            30-day cooldown per user — safe to run daily.
                        </p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                        <button
                            onClick={() => runReengagement(true)}
                            disabled={reengBusy}
                            data-testid="reeng-dry-run"
                            className="btn-outline text-sm"
                        >
                            {reengBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Eye className="w-4 h-4" /> Dry run</>}
                        </button>
                        <button
                            onClick={() => runReengagement(false)}
                            disabled={reengBusy}
                            data-testid="reeng-run"
                            className="btn-primary text-sm"
                        >
                            {reengBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Run now</>}
                        </button>
                    </div>
                </div>
            </div>

            {/* ---- History ---- */}
            <div>
                <div className="flex items-center gap-2 mb-4">
                    <ScrollText className="w-4 h-4 text-brand" />
                    <h3 className="font-serif text-lg">Campaign history</h3>
                    <button
                        onClick={loadHistory}
                        data-testid="campaign-history-refresh"
                        className="ml-auto text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-brand"
                    >
                        Refresh
                    </button>
                </div>

                {history.length === 0 ? (
                    <div className="card-flat p-8 text-center text-sm text-muted-foreground">
                        No campaigns sent yet.
                    </div>
                ) : (
                    <div className="card-flat divide-y divide-border" data-testid="campaign-history-table">
                        <div className="grid grid-cols-12 gap-3 p-4 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                            <div className="col-span-4">Subject</div>
                            <div className="col-span-2">Filter</div>
                            <div className="col-span-2">Sent by</div>
                            <div className="col-span-2">Sent at</div>
                            <div className="col-span-2 text-right">Delivered</div>
                        </div>
                        {history.map((c) => (
                            <div key={c.id} className="grid grid-cols-12 gap-3 p-4 items-center text-sm" data-testid={`campaign-row-${c.id}`}>
                                <div className="col-span-4 truncate">
                                    <div className="font-serif text-base leading-tight truncate">{c.subject}</div>
                                    <div className="text-[10px] text-muted-foreground">
                                        {c.status} · {c.cta_url ? <span className="font-mono">CTA active</span> : "no CTA"}
                                    </div>
                                </div>
                                <div className="col-span-2 text-xs">
                                    <div className="font-mono">{c.filter?.segment || "all_learners"}</div>
                                    {c.filter?.role && <div className="text-[10px] text-muted-foreground">role: {c.filter.role}</div>}
                                    {c.filter?.course_slug && <div className="text-[10px] text-muted-foreground">course: {c.filter.course_slug}</div>}
                                </div>
                                <div className="col-span-2 text-xs font-mono truncate">{c.sent_by_email || "—"}</div>
                                <div className="col-span-2 text-xs text-muted-foreground">
                                    {c.sent_at ? new Date(c.sent_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—"}
                                </div>
                                <div className="col-span-2 text-right">
                                    <div className="font-serif text-lg text-brand">
                                        {c.delivered_count} <span className="text-xs text-muted-foreground">/ {c.total_recipients}</span>
                                    </div>
                                    {c.failed_count > 0 && (
                                        <div className="text-[10px] text-destructive">{c.failed_count} failed</div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function FieldLabel({ children }) {
    return (
        <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground block mb-1.5">
            {children}
        </label>
    );
}
