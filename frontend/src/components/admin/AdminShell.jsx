import { useEffect, useRef, useState } from "react";
import {
    Activity, AlertTriangle, Award, BarChart3, Bell, Boxes, Bot, Building2,
    ChevronLeft, ChevronRight, ClipboardCheck, Cog, FileWarning, Filter, Flag,
    Gauge, Globe2, KeyRound, Layers, LifeBuoy, ListChecks, Lock, LogOut, Mail,
    MailPlus, MessageCircle, MessagesSquare, Radar, Send, ShieldCheck, Sparkles,
    Users, Video, Workflow, Zap
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import GlobalSearchBar from "./GlobalSearchBar";

/* ============================================================================
 * Navigation config — icons + human labels for every super-admin tab.
 * Adding a tab? Add its key here and it inherits the new nav treatment.
 * ========================================================================== */
export const NAV_ITEMS = {
    command:     { icon: Gauge,         label: "Command Centre", group: "Overview" },
    alertcenter: { icon: AlertTriangle, label: "Alerts",         group: "Overview" },
    analytics:   { icon: BarChart3,     label: "Analytics",      group: "Overview" },
    traffic:     { icon: Globe2,        label: "Traffic",        group: "Overview" },
    orgs:        { icon: Building2,     label: "Organizations",  group: "Customers" },
    users:       { icon: Users,         label: "Users",          group: "Customers" },
    leads:       { icon: MessageCircle, label: "Enterprise leads", group: "Customers" },
    pulsedesk:   { icon: MessagesSquare,label: "Widget conversations", group: "Customers" },
    funnel:      { icon: Layers,        label: "Learning funnel", group: "Learning & AI" },
    assessments: { icon: ClipboardCheck,label: "Assessments",    group: "Learning & AI" },
    credentials: { icon: Award,         label: "Credentials",    group: "Learning & AI" },
    aiops:       { icon: Bot,           label: "AI operations",  group: "Learning & AI" },
    videoquiz:   { icon: Video,         label: "Video quizzes",  group: "Learning & AI" },
    sessions:    { icon: Radar,         label: "AI sessions",    group: "Learning & AI" },
    campaigns:   { icon: MailPlus,      label: "Email campaigns", group: "Operations" },
    emails:      { icon: Mail,          label: "Send email",     group: "Operations" },
    agentos:     { icon: Workflow,      label: "Agent OS",       group: "Operations" },
    automations: { icon: Sparkles,      label: "Automations",    group: "Operations" },
    audit:       { icon: FileWarning,   label: "Audit log",      group: "Operations" },
    security:    { icon: Lock,          label: "Security",       group: "Governance" },
    flags:       { icon: Flag,          label: "Feature flags",  group: "Governance" },
    whatsapp:    { icon: Zap,           label: "WhatsApp",       group: "Operations" },
};

const GROUP_ORDER = ["Overview", "Customers", "Learning & AI", "Operations", "Governance"];

/* ==========================================================================
 * Sidebar — collapsible, icon-first when collapsed. Persists preference in
 * localStorage so operators come back to their chosen density.
 * ========================================================================== */
export function AdminSidebar({ tab, setTab, orgsCount = 0, usersCount = 0 }) {
    const [collapsed, setCollapsed] = useState(() => {
        try { return localStorage.getItem("sa-sidebar-collapsed") === "1"; } catch { return false; }
    });
    useEffect(() => {
        try { localStorage.setItem("sa-sidebar-collapsed", collapsed ? "1" : "0"); } catch { /* ignore */ }
    }, [collapsed]);

    const groups = GROUP_ORDER.map((g) => ({
        group: g,
        items: Object.entries(NAV_ITEMS).filter(([, meta]) => meta.group === g),
    }));

    return (
        <aside
            className={`sa-sidebar ${collapsed ? "collapsed" : "expanded"} shrink-0 min-h-[calc(100vh-64px)] hidden lg:block sticky top-[64px] self-start flex flex-col`}
            data-testid="sa-sidebar"
            data-collapsed={collapsed ? "true" : "false"}
        >
            <div className="flex-1 overflow-y-auto pb-2">
                {groups.map((g) => (
                    <div key={g.group}>
                        <div className="sa-sidebar-group">
                            <span className="sa-sidebar-group-label">{g.group}</span>
                            {!collapsed && <span className="sa-sidebar-group-line" />}
                        </div>
                        {g.items.map(([key, meta]) => {
                            const Icon = meta.icon;
                            const active = tab === key;
                            return (
                                <button
                                    key={key}
                                    onClick={() => setTab(key)}
                                    data-testid={`tab-${key}`}
                                    data-label={meta.label}
                                    className={`sa-sidebar-link ${active ? "active" : ""}`}
                                    title={collapsed ? meta.label : undefined}
                                >
                                    <Icon className="icon" strokeWidth={2} />
                                    <span className="label">{meta.label}</span>
                                    {key === "orgs" && <span className="count">{orgsCount}</span>}
                                    {key === "users" && <span className="count">{usersCount}</span>}
                                </button>
                            );
                        })}
                    </div>
                ))}
            </div>
            <div className="sa-sidebar-collapse">
                <button
                    onClick={() => setCollapsed((v) => !v)}
                    data-testid="sa-sidebar-toggle"
                    className="sa-sidebar-collapse-btn"
                    title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : (
                        <>
                            <ChevronLeft className="w-3.5 h-3.5" />
                            <span>Collapse</span>
                        </>
                    )}
                </button>
            </div>
        </aside>
    );
}

/* ==========================================================================
 * Notification Bell — polls /admin/alerts-center and shows the top few open
 * alerts in a floating dropdown. Click one → jumps to its drill tab.
 * ========================================================================== */
export function NotificationBell({ onNavigate }) {
    const [alerts, setAlerts] = useState([]);
    const [open, setOpen] = useState(false);
    const boxRef = useRef(null);

    useEffect(() => {
        const load = async () => {
            try {
                const { data } = await api.get("/admin/alerts-center");
                setAlerts((data.alerts || []).filter((a) => a.status !== "resolved"));
            } catch { /* silent */ }
        };
        load();
        const id = setInterval(load, 60000);
        return () => clearInterval(id);
    }, []);

    useEffect(() => {
        const onDoc = (e) => {
            if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener("click", onDoc);
        return () => document.removeEventListener("click", onDoc);
    }, []);

    const highCount = alerts.filter((a) => a.severity === "high").length;

    return (
        <div ref={boxRef} className="relative" data-testid="sa-notif-wrap">
            <button
                onClick={() => setOpen((v) => !v)}
                className="sa-icon-btn"
                data-testid="sa-notif-btn"
                title="Alerts & notifications"
            >
                <Bell className="w-4 h-4" />
                {alerts.length > 0 && <span className="sa-badge">{alerts.length > 9 ? "9+" : alerts.length}</span>}
            </button>
            {open && (
                <div className="sa-notif-dropdown" data-testid="sa-notif-dropdown">
                    <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Alerts</div>
                        <span className="text-[10px] font-mono text-muted-foreground">
                            {alerts.length} open · {highCount} high
                        </span>
                    </div>
                    {alerts.length === 0 && (
                        <div className="p-6 text-center text-sm text-muted-foreground">
                            All quiet. No open alerts. 🎉
                        </div>
                    )}
                    {alerts.slice(0, 8).map((a) => (
                        <button
                            key={a.key}
                            onClick={() => { setOpen(false); if (a.drill) onNavigate?.(a.drill); else onNavigate?.("alertcenter"); }}
                            data-testid={`sa-notif-item-${a.key}`}
                            className="w-full text-left px-4 py-3 border-b border-border hover:bg-surface-alt transition-colors flex items-start gap-3"
                        >
                            <span className={`mt-1 inline-block w-2 h-2 rounded-full shrink-0 ${a.severity === "high" ? "bg-rose-500" : a.severity === "medium" ? "bg-amber-500" : "bg-slate-400"}`} />
                            <div className="min-w-0 flex-1">
                                <div className="text-sm font-medium truncate">{a.title}</div>
                                <div className="text-xs text-muted-foreground line-clamp-2">{a.detail}</div>
                            </div>
                        </button>
                    ))}
                    {alerts.length > 8 && (
                        <button
                            onClick={() => { setOpen(false); onNavigate?.("alertcenter"); }}
                            className="w-full py-3 text-xs font-mono uppercase tracking-widest text-brand hover:bg-surface-alt"
                            data-testid="sa-notif-view-all"
                        >
                            View all in Alert Centre →
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

/* ==========================================================================
 * Profile pill — avatar + email, dropdown with sign-out.
 * ========================================================================== */
export function ProfileMenu() {
    const { user, logout } = useAuth();
    const [open, setOpen] = useState(false);
    const boxRef = useRef(null);
    useEffect(() => {
        const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
        document.addEventListener("click", onDoc);
        return () => document.removeEventListener("click", onDoc);
    }, []);
    if (!user) return null;
    const initials = (user.full_name || user.email || "?").split(/[\s@]+/).map((s) => s[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();

    const handleLogout = async () => {
        try {
            await logout();
            toast.success("Signed out");
            window.location.assign("/login");
        } catch { /* logout is best-effort */ }
    };

    return (
        <div ref={boxRef} className="relative" data-testid="sa-profile-wrap">
            <button onClick={() => setOpen((v) => !v)} className="sa-profile" data-testid="sa-profile-btn">
                <span className="avatar">{initials}</span>
                <span className="hidden md:block text-xs font-medium leading-tight">
                    <div className="truncate max-w-[140px]">{user.full_name || "Super admin"}</div>
                    <div className="sa-teal text-[10px] font-mono uppercase tracking-widest">super_admin</div>
                </span>
            </button>
            {open && (
                <div className="sa-notif-dropdown" style={{ width: 240 }} data-testid="sa-profile-dropdown">
                    <div className="px-4 py-3 border-b border-border">
                        <div className="text-sm font-semibold truncate">{user.full_name || "Super admin"}</div>
                        <div className="text-xs text-muted-foreground truncate">{user.email}</div>
                    </div>
                    <button onClick={handleLogout} data-testid="sa-profile-signout" className="w-full text-left px-4 py-2.5 hover:bg-surface-alt flex items-center gap-2 text-sm">
                        <LogOut className="w-4 h-4 text-muted-foreground" /> Sign out
                    </button>
                </div>
            )}
        </div>
    );
}

/* ==========================================================================
 * Top bar — brand mark + breadcrumb + search + notifications + profile.
 * ========================================================================== */
export function AdminTopBar({ tab, setTab }) {
    const meta = NAV_ITEMS[tab] || { label: "Command Centre", group: "Overview", icon: Gauge };
    const Icon = meta.icon;
    return (
        <div className="sa-header px-5 py-3 flex items-center justify-between gap-4 sticky top-0 z-40">
            <div className="flex items-center gap-4 min-w-0">
                <div className="sa-brand-lockup">
                    <div className="sa-brand-mark">
                        <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div className="min-w-0 hidden sm:block">
                        <div className="font-serif text-[17px] leading-none">ITHR</div>
                        <div className="text-[9px] font-mono uppercase tracking-[0.22em] text-muted-foreground mt-0.5">Super Admin</div>
                    </div>
                </div>
                <div className="sa-breadcrumb hidden md:flex" data-testid="sa-breadcrumb">
                    <span>{meta.group}</span>
                    <span className="sep">/</span>
                    <span className="current flex items-center gap-1.5">
                        <Icon className="w-3.5 h-3.5" />
                        {meta.label}
                    </span>
                </div>
            </div>
            <div className="flex-1 max-w-lg hidden md:block">
                <GlobalSearchBar onNavigateUser={() => setTab("users")} />
            </div>
            <div className="flex items-center gap-2">
                <NotificationBell onNavigate={setTab} />
                <ProfileMenu />
            </div>
        </div>
    );
}

/* Icon helpers for quick actions row */
export const QuickIcons = { Send, Bot, KeyRound, LifeBuoy, ListChecks, Cog, Boxes, Filter };
