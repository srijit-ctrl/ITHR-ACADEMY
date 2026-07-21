import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Search, Loader2, Users, Building2, BookOpen, Mail, Workflow, ScrollText,
    MessageCircle, Command, ArrowRight, LayoutGrid
} from "lucide-react";
import { api } from "@/lib/api";
import { NAV_ITEMS } from "./AdminShell";

/* ==========================================================================
 * CommandPalette — Cmd/Ctrl+K launcher over the whole super-admin console.
 * Searches users, orgs, courses, campaigns, agent runs, audit, leads plus
 * every admin tab so operators can jump anywhere in <2s.
 * ========================================================================== */
export default function CommandPalette({ open, onClose, onTabJump }) {
    const [q, setQ] = useState("");
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [cursor, setCursor] = useState(0);
    const inputRef = useRef(null);
    const navigate = useNavigate();

    // Focus input on open + reset state
    useEffect(() => {
        if (open) {
            setQ("");
            setResults(null);
            setCursor(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [open]);

    // ESC to close
    useEffect(() => {
        const onKey = (e) => { if (e.key === "Escape" && open) onClose?.(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    // Debounced search
    useEffect(() => {
        if (!open) return;
        if (q.trim().length < 2) { setResults(null); return; }
        const t = setTimeout(async () => {
            setLoading(true);
            try {
                const r = await api.get(`/admin/search?q=${encodeURIComponent(q.trim())}`);
                setResults(r.data);
                setCursor(0);
            } catch { /* silent */ } finally { setLoading(false); }
        }, 200);
        return () => clearTimeout(t);
    }, [q, open]);

    // Tab suggestions — always visible when no query typed
    const tabMatches = useMemo(() => {
        const query = q.trim().toLowerCase();
        return Object.entries(NAV_ITEMS)
            .filter(([, meta]) => !query || meta.label.toLowerCase().includes(query) || meta.group.toLowerCase().includes(query))
            .slice(0, 8);
    }, [q]);

    /* Flatten every result section into a single navigable list.
     * Each item: { section, label, sublabel, icon, onSelect } */
    const items = useMemo(() => {
        const arr = [];
        tabMatches.forEach(([key, meta]) => {
            arr.push({
                section: "Jump to tab",
                icon: meta.icon,
                label: meta.label,
                sublabel: meta.group,
                onSelect: () => { onTabJump?.(key); onClose?.(); },
            });
        });
        if (results) {
            results.users?.forEach((u) => arr.push({
                section: "Users",
                icon: Users,
                label: u.full_name || u.email,
                sublabel: `${u.email} · ${u.role}${u.is_suspended ? " · suspended" : ""}`,
                onSelect: () => { onTabJump?.("users"); onClose?.(); },
            }));
            results.orgs?.forEach((o) => arr.push({
                section: "Organizations",
                icon: Building2,
                label: o.name,
                sublabel: `@${o.domain || "—"} · ${o.seats || 0} seats`,
                onSelect: () => { onTabJump?.("orgs"); onClose?.(); },
            }));
            results.leads?.forEach((l) => arr.push({
                section: "Enterprise leads",
                icon: MessageCircle,
                label: `${l.name || l.email} · ${l.company || ""}`,
                sublabel: `${l.bundle || "—"} · ${l.status || "new"}`,
                onSelect: () => { onTabJump?.("leads"); onClose?.(); },
            }));
            results.courses?.forEach((c) => arr.push({
                section: "Courses",
                icon: BookOpen,
                label: c.title,
                sublabel: `/courses/${c.slug} · ${c.category || ""}`,
                onSelect: () => { navigate(`/courses/${c.slug}`); onClose?.(); },
            }));
            results.campaigns?.forEach((c) => arr.push({
                section: "Email campaigns",
                icon: Mail,
                label: c.subject,
                sublabel: `${c.filter || "—"} · ${c.total_recipients || 0} recipients`,
                onSelect: () => { onTabJump?.("campaigns"); onClose?.(); },
            }));
            results.agent_runs?.forEach((r) => arr.push({
                section: "Agent OS runs",
                icon: Workflow,
                label: `${r.pod_id} · ${r.status}`,
                sublabel: `Triggered by ${r.triggered_by || "system"} · ${(r.created_at || "").slice(0, 19)}`,
                onSelect: () => { onTabJump?.("agentos"); onClose?.(); },
            }));
            results.audit?.forEach((a) => arr.push({
                section: "Audit log",
                icon: ScrollText,
                label: a.action,
                sublabel: `${a.target_type || ""}${a.target_id ? " · " + a.target_id : ""} · ${(a.created_at || "").slice(0, 19)}`,
                onSelect: () => { onTabJump?.("audit"); onClose?.(); },
            }));
        }
        return arr;
    }, [results, tabMatches, navigate, onTabJump, onClose]);

    // Keyboard: arrow up/down + enter
    const onKeyDown = useCallback((e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
        else if (e.key === "Enter") {
            e.preventDefault();
            items[cursor]?.onSelect?.();
        }
    }, [items, cursor]);

    // Group by section for rendering
    const groups = useMemo(() => {
        const map = new Map();
        items.forEach((it, i) => {
            if (!map.has(it.section)) map.set(it.section, []);
            map.get(it.section).push({ ...it, i });
        });
        return Array.from(map.entries());
    }, [items]);

    if (!open) return null;
    return (
        <div className="fixed inset-0 z-[70] flex items-start justify-center pt-[10vh] px-4" data-testid="cmdk-root">
            <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
            <div
                className="relative w-full max-w-[640px] sa-glass-hero rounded-2xl overflow-hidden shadow-2xl"
                data-testid="cmdk-panel"
            >
                <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
                    <Search className="w-4 h-4 text-muted-foreground shrink-0" />
                    <input
                        ref={inputRef}
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        onKeyDown={onKeyDown}
                        placeholder="Jump to a tab, or search users, orgs, courses, campaigns, agent runs…"
                        data-testid="cmdk-input"
                        className="flex-1 bg-transparent focus:outline-none text-[15px]"
                    />
                    {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
                    <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-border bg-white text-[10px] font-mono text-muted-foreground">
                        <span>esc</span>
                    </kbd>
                </div>

                <div className="max-h-[60vh] overflow-y-auto py-2" data-testid="cmdk-results">
                    {items.length === 0 && (
                        <div className="p-6 text-center text-sm text-muted-foreground" data-testid="cmdk-empty">
                            {q.trim().length < 2 ? "Start typing to search users, orgs, courses…" : "No matches."}
                        </div>
                    )}
                    {groups.map(([section, secItems]) => (
                        <div key={section} className="py-1">
                            <div className="px-4 py-1 text-[10px] font-mono uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                                {section === "Jump to tab" ? <LayoutGrid className="w-3 h-3" /> : null}
                                {section}
                            </div>
                            {secItems.map((it) => (
                                <button
                                    key={it.i}
                                    onClick={it.onSelect}
                                    onMouseEnter={() => setCursor(it.i)}
                                    data-testid={`cmdk-item-${it.i}`}
                                    className={`w-full text-left px-4 py-2 flex items-center gap-3 ${cursor === it.i ? "bg-white" : "hover:bg-white/60"}`}
                                >
                                    <it.icon className="w-4 h-4 text-brand shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm truncate">{it.label}</div>
                                        {it.sublabel && <div className="text-[11px] text-muted-foreground truncate">{it.sublabel}</div>}
                                    </div>
                                    <ArrowRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                                </button>
                            ))}
                        </div>
                    ))}
                </div>

                <div className="px-4 py-2 border-t border-border text-[10px] font-mono uppercase tracking-widest text-muted-foreground flex items-center gap-4">
                    <span className="flex items-center gap-1"><Command className="w-3 h-3" /> K to open</span>
                    <span>↑ ↓ to navigate</span>
                    <span>Enter to select</span>
                </div>
            </div>
        </div>
    );
}
