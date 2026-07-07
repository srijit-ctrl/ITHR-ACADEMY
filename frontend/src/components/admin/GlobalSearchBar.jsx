import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Search, Loader2, X } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Top-of-portal global search — autocomplete across users, orgs, courses.
 * Debounced 250ms; opens a floating results panel; closes on outside-click.
 */
export default function GlobalSearchBar({ onNavigateUser }) {
    const [q, setQ] = useState("");
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [open, setOpen] = useState(false);
    const boxRef = useRef(null);

    useEffect(() => {
        if (q.trim().length < 2) { setResults(null); return; }
        const t = setTimeout(async () => {
            setLoading(true);
            try {
                const r = await api.get(`/admin/search?q=${encodeURIComponent(q.trim())}`);
                setResults(r.data);
                setOpen(true);
            } finally { setLoading(false); }
        }, 250);
        return () => clearTimeout(t);
    }, [q]);

    useEffect(() => {
        const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
        document.addEventListener("click", onDoc);
        return () => document.removeEventListener("click", onDoc);
    }, []);

    const total = results ? (results.users.length + results.orgs.length + results.courses.length) : 0;

    return (
        <div ref={boxRef} className="relative" data-testid="admin-global-search">
            <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                    type="text"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    onFocus={() => q.trim().length >= 2 && setOpen(true)}
                    placeholder="Search users, orgs, courses…"
                    data-testid="admin-search-input"
                    className="w-full md:w-96 bg-surface-alt border border-border rounded-full pl-9 pr-9 py-2 text-sm focus:outline-none focus:border-brand"
                />
                {q && (
                    <button
                        onClick={() => { setQ(""); setResults(null); setOpen(false); }}
                        data-testid="admin-search-clear"
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-brand"
                    >
                        <X className="w-4 h-4" />
                    </button>
                )}
            </div>

            {open && (
                <div className="absolute top-full mt-2 left-0 right-0 md:w-[28rem] bg-surface border border-border rounded-lg shadow-lg z-50 max-h-[520px] overflow-y-auto" data-testid="admin-search-results">
                    {loading ? (
                        <div className="p-4 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Searching…</div>
                    ) : !results || total === 0 ? (
                        <div className="p-4 text-sm text-muted-foreground">No matches for &ldquo;{q}&rdquo;.</div>
                    ) : (
                        <div className="divide-y divide-border">
                            {results.users.length > 0 && (
                                <SearchSection title={`Users (${results.users.length})`}>
                                    {results.users.map((u) => (
                                        <button
                                            key={u.id}
                                            onClick={() => { onNavigateUser?.(u); setOpen(false); }}
                                            data-testid={`search-user-${u.id}`}
                                            className="block w-full text-left px-4 py-2 hover:bg-surface-alt"
                                        >
                                            <div className="text-sm font-medium truncate">{u.full_name || u.email}</div>
                                            <div className="text-xs text-muted-foreground truncate">
                                                {u.email} · <span className="text-brand">{u.role}</span>
                                                {u.is_suspended && <span className="text-destructive ml-1">· suspended</span>}
                                            </div>
                                        </button>
                                    ))}
                                </SearchSection>
                            )}
                            {results.orgs.length > 0 && (
                                <SearchSection title={`Organizations (${results.orgs.length})`}>
                                    {results.orgs.map((o) => (
                                        <div key={o.id} data-testid={`search-org-${o.id}`} className="px-4 py-2">
                                            <div className="text-sm font-medium truncate">{o.name}</div>
                                            <div className="text-xs text-muted-foreground truncate">{o.domain || "—"} · {o.seats || 0} seats</div>
                                        </div>
                                    ))}
                                </SearchSection>
                            )}
                            {results.courses.length > 0 && (
                                <SearchSection title={`Courses (${results.courses.length})`}>
                                    {results.courses.map((c) => (
                                        <Link
                                            key={c.id}
                                            to={`/courses/${c.slug}`}
                                            onClick={() => setOpen(false)}
                                            data-testid={`search-course-${c.slug}`}
                                            className="block px-4 py-2 hover:bg-surface-alt"
                                        >
                                            <div className="text-sm font-medium truncate">{c.title}</div>
                                            <div className="text-xs text-muted-foreground truncate">/courses/{c.slug} · {c.category}</div>
                                        </Link>
                                    ))}
                                </SearchSection>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function SearchSection({ title, children }) {
    return (
        <div>
            <div className="px-4 py-2 bg-surface-alt text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{title}</div>
            {children}
        </div>
    );
}
