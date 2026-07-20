import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Loader2, MessageSquare, TrendingUp, Phone, Sparkles, ChevronRight, RefreshCcw } from "lucide-react";
import { toast } from "sonner";

/**
 * Super-Admin PulseDesk console.
 *
 * Two stacked panels:
 *   1. "What visitors ask" — rule-based intent aggregation over the last N
 *      days of widget conversations. Shows top intents, counts, and up to
 *      3 verbatim samples per intent. Adjustable window (7 / 30 / 90 days).
 *   2. Recent conversations — newest-first list of every widget visitor,
 *      with a drill-in view showing the full message log. Callback
 *      requests appear as system messages inline.
 */
export default function PulseDeskAdminPanel() {
    const [tab, setTab] = useState("intents");
    return (
        <div data-testid="pulsedesk-admin-panel">
            <div className="mb-6 flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-brand" />
                <h2 className="font-serif text-2xl">PulseDesk widget</h2>
            </div>
            <p className="text-sm text-muted-foreground mb-6 max-w-2xl">
                Live visitor conversations from the floating chat bubble embedded on every ITHR page.
                Powered by the Aletheia AI (Emergent LLM key). Callback requests captured here.
            </p>

            <div className="mb-6 flex gap-1 border-b border-border">
                <TabBtn active={tab === "intents"} onClick={() => setTab("intents")} testId="pd-tab-intents">
                    <TrendingUp className="w-3.5 h-3.5" /> Popular questions
                </TabBtn>
                <TabBtn active={tab === "conversations"} onClick={() => setTab("conversations")} testId="pd-tab-conversations">
                    <MessageSquare className="w-3.5 h-3.5" /> Conversations
                </TabBtn>
                <TabBtn active={tab === "callbacks"} onClick={() => setTab("callbacks")} testId="pd-tab-callbacks">
                    <Phone className="w-3.5 h-3.5" /> Callback requests
                </TabBtn>
            </div>

            {tab === "intents" && <PopularQuestions />}
            {tab === "conversations" && <ConversationsList />}
            {tab === "callbacks" && <CallbacksList />}
        </div>
    );
}


function TabBtn({ active, onClick, children, testId }) {
    return (
        <button
            onClick={onClick}
            data-testid={testId}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-mono uppercase tracking-[0.12em] border-b-2 -mb-px transition-colors ${active ? "border-brand text-brand" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
            {children}
        </button>
    );
}


// ---- Popular questions ----------------------------------------------------


function PopularQuestions() {
    const [days, setDays] = useState(7);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get(`/admin/pulsedesk/popular-questions?days=${days}&top_n=10`);
            setData(res.data);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load intents");
        } finally { setLoading(false); }
    }, [days]);

    useEffect(() => { load(); }, [load]);

    const maxCount = data && data.top_intents.length > 0
        ? Math.max(...data.top_intents.map(i => i.count))
        : 1;

    return (
        <div data-testid="pd-popular-questions">
            <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">
                        Voice of the visitor
                    </div>
                    <h3 className="font-serif text-xl">
                        {loading ? "…" : `${data?.total_visitor_messages ?? 0}`} visitor messages · last{" "}
                        <select
                            value={days}
                            onChange={(e) => setDays(parseInt(e.target.value, 10))}
                            data-testid="pd-window-select"
                            className="bg-transparent border border-border rounded-sm px-2 py-0.5 text-base font-serif"
                        >
                            <option value={7}>7</option>
                            <option value={30}>30</option>
                            <option value={90}>90</option>
                        </select>{" "}
                        days
                    </h3>
                </div>
                <button onClick={load} disabled={loading} data-testid="pd-refresh-intents" className="btn-outline text-xs">
                    {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><RefreshCcw className="w-3.5 h-3.5" /> Refresh</>}
                </button>
            </div>

            {loading ? (
                <div className="card-flat p-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
            ) : !data?.top_intents?.length ? (
                <div className="card-flat p-10 text-center text-sm text-muted-foreground" data-testid="pd-empty-intents">
                    <Sparkles className="w-6 h-6 mx-auto mb-3 text-muted-foreground/50" />
                    No visitor messages yet in the last {days} days.
                </div>
            ) : (
                <div className="space-y-3" data-testid="pd-intents-list">
                    {data.top_intents.map((i) => (
                        <div key={i.intent} className="card-flat p-4" data-testid={`pd-intent-${i.intent.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}>
                            <div className="flex items-baseline justify-between gap-3 mb-2">
                                <div className="font-serif text-lg leading-tight">{i.intent}</div>
                                <div className="font-mono text-xs text-muted-foreground shrink-0">
                                    <span className="text-brand font-bold">{i.count}</span> msgs · {i.unique_visitors} visitor{i.unique_visitors === 1 ? "" : "s"}
                                </div>
                            </div>
                            <div className="h-1.5 bg-border rounded-full mb-3 overflow-hidden">
                                <div
                                    className="h-full bg-brand transition-all"
                                    style={{ width: `${(i.count / maxCount) * 100}%` }}
                                />
                            </div>
                            {i.samples.length > 0 && (
                                <ul className="space-y-1.5">
                                    {i.samples.map((s, idx) => (
                                        <li key={idx} className="text-xs text-muted-foreground pl-3 border-l-2 border-border italic leading-relaxed">
                                            &ldquo;{s}&rdquo;
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}


// ---- Conversations list ---------------------------------------------------


function ConversationsList() {
    const [convs, setConvs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [messages, setMessages] = useState([]);

    useEffect(() => {
        (async () => {
            try {
                const res = await api.get("/admin/pulsedesk/conversations?limit=200");
                setConvs(res.data.conversations || []);
            } catch (e) {
                toast.error(e.response?.data?.detail || "Failed to load conversations");
            } finally { setLoading(false); }
        })();
    }, []);

    const openConv = async (c) => {
        setSelected(c);
        setMessages([]);
        try {
            const res = await api.get(`/admin/pulsedesk/conversations/${c.id}/messages`);
            setMessages(res.data.messages || []);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed to load messages");
        }
    };

    if (loading) return <div className="card-flat p-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>;
    if (convs.length === 0) return <div className="card-flat p-10 text-center text-sm text-muted-foreground">No widget conversations yet.</div>;

    return (
        <div className="grid md:grid-cols-5 gap-4" data-testid="pd-conversations">
            <div className="md:col-span-2 card-flat divide-y divide-border max-h-[550px] overflow-y-auto">
                {convs.map((c) => (
                    <button
                        key={c.id}
                        onClick={() => openConv(c)}
                        data-testid={`pd-conv-${c.id}`}
                        className={`w-full text-left p-3 hover:bg-surface-alt transition-colors ${selected?.id === c.id ? "bg-surface-alt" : ""}`}
                    >
                        <div className="text-xs font-mono truncate">{c.visitor_id}</div>
                        <div className="text-[10px] text-muted-foreground mt-1 flex justify-between">
                            <span>{c.message_count || 0} msgs · {c.status}</span>
                            <span>{c.last_message_at ? new Date(c.last_message_at).toLocaleDateString() : "—"}</span>
                        </div>
                        {c.visitor_meta?.url && (
                            <div className="text-[10px] text-brand mt-1 truncate">{c.visitor_meta.url}</div>
                        )}
                    </button>
                ))}
            </div>

            <div className="md:col-span-3 card-flat p-4 max-h-[550px] overflow-y-auto">
                {!selected ? (
                    <div className="text-center text-sm text-muted-foreground py-16">
                        <ChevronRight className="w-5 h-5 mx-auto mb-2 opacity-50" />
                        Pick a conversation from the left to view messages.
                    </div>
                ) : (
                    <>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">
                            {selected.visitor_id} · {selected.status}
                        </div>
                        {messages.map((m) => (
                            <div key={m.id} className={`mb-3 ${m.sender_type === "visitor" ? "text-right" : ""}`}>
                                <div className="text-[10px] uppercase text-muted-foreground mb-1">{m.sender_type}</div>
                                <div className={`inline-block px-3 py-2 rounded-lg text-sm max-w-[85%] whitespace-pre-wrap ${
                                    m.sender_type === "visitor" ? "bg-brand text-white" :
                                    m.sender_type === "ai" ? "bg-surface-alt" :
                                    m.sender_type === "system" ? "bg-muted/50 text-muted-foreground italic text-xs" :
                                    "bg-surface-alt border border-border"
                                }`}>
                                    {m.text}
                                </div>
                            </div>
                        ))}
                    </>
                )}
            </div>
        </div>
    );
}


// ---- Callback requests ----------------------------------------------------


function CallbacksList() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        (async () => {
            try {
                const res = await api.get("/admin/pulsedesk/callbacks?limit=200");
                setRows(res.data.callbacks || []);
            } catch (e) {
                toast.error(e.response?.data?.detail || "Failed to load callbacks");
            } finally { setLoading(false); }
        })();
    }, []);
    if (loading) return <div className="card-flat p-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>;
    if (rows.length === 0) return <div className="card-flat p-10 text-center text-sm text-muted-foreground">No callback requests yet.</div>;
    return (
        <div className="card-flat divide-y divide-border" data-testid="pd-callbacks">
            {rows.map((r) => (
                <div key={r.id} className="grid grid-cols-12 gap-3 p-4 items-center text-sm" data-testid={`pd-callback-${r.id}`}>
                    <div className="col-span-3 font-mono text-brand">{r.phone_number}</div>
                    <div className="col-span-3 text-xs font-mono truncate">{r.visitor_id}</div>
                    <div className="col-span-3 text-xs text-muted-foreground">{r.created_at ? new Date(r.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—"}</div>
                    <div className="col-span-3 text-right">
                        <span className={`text-xs px-2 py-1 rounded-sm border ${r.status === "new" ? "bg-brand/10 text-brand border-brand/30" : "bg-muted text-muted-foreground border-border"}`}>
                            {r.status}
                        </span>
                    </div>
                </div>
            ))}
        </div>
    );
}
