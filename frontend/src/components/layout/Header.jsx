import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Sparkles, LogOut, User as UserIcon } from "lucide-react";

const navItems = [
    { to: "/courses", label: "Catalog" },
    { to: "/industries", label: "Industries" },
    { to: "/certifications", label: "Certifications" },
    { to: "/enterprise", label: "For Enterprise" },
];

export default function Header() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate("/");
    };

    return (
        <header className="glass-header sticky top-0 z-40">
            <div className="container-page flex items-center justify-between h-16">
                <Link to="/" className="flex items-center gap-2.5" data-testid="brand-home-link">
                    <div className="w-8 h-8 bg-foreground text-background flex items-center justify-center">
                        <span className="font-serif text-lg font-medium">A</span>
                    </div>
                    <div className="flex flex-col leading-none">
                        <span className="font-serif text-lg tracking-tight">Agentic AI Academy</span>
                        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Enterprise · Est. 2026</span>
                    </div>
                </Link>

                <nav className="hidden md:flex items-center gap-8">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                            className={({ isActive }) =>
                                `text-sm font-medium transition-colors ${
                                    isActive ? "text-brand" : "text-foreground hover:text-brand"
                                }`
                            }
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                <div className="flex items-center gap-3">
                    {user ? (
                        <>
                            <Link
                                to="/dashboard"
                                data-testid="nav-dashboard"
                                className="hidden sm:inline-flex items-center gap-2 text-sm font-medium hover:text-brand transition-colors"
                            >
                                <UserIcon className="w-4 h-4" />
                                {user.full_name.split(" ")[0]}
                            </Link>
                            <button
                                onClick={handleLogout}
                                data-testid="logout-button"
                                className="p-2 hover:bg-surface-alt rounded-sm transition-colors"
                                title="Sign out"
                            >
                                <LogOut className="w-4 h-4" />
                            </button>
                        </>
                    ) : (
                        <>
                            <Link to="/login" data-testid="nav-login" className="text-sm font-medium hover:text-brand transition-colors">
                                Sign in
                            </Link>
                            <Link to="/register" data-testid="nav-register" className="btn-primary text-sm">
                                <Sparkles className="w-4 h-4" />
                                Enroll now
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </header>
    );
}
