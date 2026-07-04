import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Sparkles, Check, X, Clock, Loader2, ArrowRight, Filter } from "lucide-react";
import { toast } from "sonner";

const STATUSES = [
    { key: "proposed", label: "Pending review" },
    { key: "approved", label: "Approved" },
    { key: "rejected", label: "Rejected" },
];

export default function PatchReview() {
    const [status, setStatus] = useState("proposed");
    const [patches, setPatches] = useState([]);
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState(null);
    const [expandedId, setExpandedId] = useState(null);

    const load = async (s = status) => {
        setLoading(true);
        try {
            const res = await api.get(`/intelligence/patches?status=${s}`);
            setPatches(res.data.patches || []);
        } finally { setLoading(false); }
    };

    useEffect(() => {
        setLoading(true);
        api.get(`/intelligence/patches?status=${status}`)
            .then((r) => setPatches(r.data.patches || []))
            .finally(() => setLoading(false));
    }, [status]);

    const decide = async (patchId, decision) => {
        setBusyId(patchId);
        try {
            await api.post(`/intelligence/patches/${patchId}/decide`, { decision });
            toast.success(`Patch ${decision}.`);
            load();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Decision failed");
        } finally { setBusyId(null); }
    };

    return (
        <div className="container-page py-14">
            <div className="max-w-3xl mb-10">
                <div className="overline mb-4 fine-rule pl-4">Curriculum Ops</div>
                <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-4">
                    Patch review queue.
                </h1>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    Every AI-drafted curriculum patch pushed from the Intelligence Desk lands here for human review.
                    Approve to publish into the course, reject to discard.
                </p>
            </div>

            <div className="flex items-center gap-2 mb-8 flex-wrap">
                <Filter className="w-4 h-4 text-muted-foreground" />
                {STATUSES.map((s) => (
                    <button
                        key={s.key}
                        onClick={() => setStatus(s.key)}
                        data-testid={`patch-filter-${s.key}`}
                        className={`px-3 py-1.5 text-xs font-mono uppercase tracking-[0.15em] border ${
                            status === s.key
                                ? "border-brand bg-brand text-white"
                                : "border-border text-muted-foreground hover:border-foreground"
                        }`}
                    >
                        {s.label}
                    </button>
                ))}
                <Link to="/intelligence" className="ml-auto text-xs text-brand font-mono uppercase tracking-[0.15em] hover:underline">
                    Go to Intelligence Desk <ArrowRight className="w-3 h-3 inline" />
                </Link>
            </div>

            {loading ? (
                <div className="py-24 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>
            ) : patches.length === 0 ? (
                <div className="card-flat p-16 text-center">
                    <Sparkles className="w-8 h-8 text-brand mx-auto mb-4" />
                    <h3 className="font-serif text-2xl mb-2">Queue clear.</h3>
                    <p className="text-muted-foreground text-sm">
                        {status === "proposed"
                            ? "No pending patches. Head to the Intelligence Desk to push a signal into curriculum."
                            : `No ${status} patches yet.`}
                    </p>
                </div>
            ) : (
                <div className="space-y-4" data-testid="patch-list">
                    {patches.map((p) => {
                        const isOpen = expandedId === p.id;
                        return (
                            <div key={p.id} className="card-flat" data-testid={`patch-row-${p.id}`}>
                                <div className="p-5 flex items-start gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                                            <span className="badge-mono">{p.patch_type}</span>
                                            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                                                {new Date(p.created_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}
                                            </span>
                                            {p.module_number && (
                                                <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand">
                                                    Module {String(p.module_number).padStart(2, "0")}
                                                </span>
                                            )}
                                        </div>
                                        <div className="font-serif text-lg leading-tight mb-1">{p.proposed_title}</div>
                                        <div className="text-xs text-muted-foreground">
                                            <span className="text-foreground font-mono">{p.course_slug}</span>
                                            {p.module_title && <> · {p.module_title}</>}
                                        </div>
                                        <div className="text-xs text-muted-foreground mt-2 line-clamp-2 italic">
                                            Signal: {p.signal_title}
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-2 shrink-0">
                                        {p.status === "proposed" ? (
                                            <>
                                                <button
                                                    onClick={() => decide(p.id, "approved")}
                                                    disabled={busyId === p.id}
                                                    data-testid={`patch-approve-${p.id}`}
                                                    className="btn-primary py-1.5 text-xs"
                                                >
                                                    {busyId === p.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <><Check className="w-3 h-3" /> Approve</>}
                                                </button>
                                                <button
                                                    onClick={() => decide(p.id, "rejected")}
                                                    disabled={busyId === p.id}
                                                    data-testid={`patch-reject-${p.id}`}
                                                    className="btn-outline py-1.5 text-xs"
                                                >
                                                    <X className="w-3 h-3" /> Reject
                                                </button>
                                            </>
                                        ) : (
                                            <span className={`badge-mono ${p.status === "approved" ? "!bg-success !text-white" : ""}`}>
                                                {p.status}
                                            </span>
                                        )}
                                        <button
                                            onClick={() => setExpandedId(isOpen ? null : p.id)}
                                            data-testid={`patch-toggle-${p.id}`}
                                            className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand hover:underline"
                                        >
                                            {isOpen ? "Hide" : "Preview"}
                                        </button>
                                    </div>
                                </div>

                                {isOpen && (
                                    <div className="border-t border-border bg-surface-alt/40 p-6 space-y-4" data-testid={`patch-preview-${p.id}`}>
                                        {p.rationale && (
                                            <div>
                                                <div className="overline mb-2">Rationale</div>
                                                <p className="text-sm text-muted-foreground">{p.rationale}</p>
                                            </div>
                                        )}
                                        <div>
                                            <div className="overline mb-2">Proposed content</div>
                                            <div className="prose-lesson text-sm whitespace-pre-wrap">{p.proposed_content}</div>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs text-muted-foreground border-t border-border pt-3">
                                            <Clock className="w-3 h-3" />
                                            Reviewed by learners: {p.reviewed_at ? new Date(p.reviewed_at).toLocaleString() : "pending"}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
