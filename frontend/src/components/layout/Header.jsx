import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Sparkles, LogOut, User as UserIcon } from "lucide-react";
import { ITHRLockup } from "@/components/brand/ITHRBrand";

// Official ITHR brand kit assets (do NOT modify these files — brand-guideline compliant)
export const ITHR_LOGO_URL = "/brand/ITHR_Logo_FullColor.svg";
export const ITHR_LOGO_WHITE_URL = "/brand/ITHR_Logo_Mono_White.svg";
export const ITHR_LOGO_NAVY_URL = "/brand/ITHR_Logo_Mono_Navy.svg";
export const ITHR_MARK_URL = "/brand/ITHR_Mark.svg";

const navItems = [
    { to: "/paths", label: "Learning paths" },
    { to: "/courses", label: "Catalog" },
    { to: "/intelligence", label: "Intelligence" },
    { to: "/mentor", label: "Mentor" },
    { to: "/certifications", label: "Certifications" },
    { to: "/pricing", label: "Pricing" },
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
        <header className="glass-header sticky top-0 z-40 border-b border-b-border" data-testid="site-header">
            <div className="container-page flex items-center justify-between h-20 gap-6">
                <Link to="/" className="shrink-0" data-testid="brand-home-link">
                    <ITHRLockup size={47} className="hidden md:inline-flex" />
                    <ITHRLockup size={39} variant="compact" className="md:hidden" />
                </Link>

                <nav className="hidden lg:flex items-center gap-5 flex-1 justify-center min-w-0">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                            className={({ isActive }) =>
                                `text-[13px] font-medium whitespace-nowrap transition-colors ${
                                    isActive ? "text-brand" : "text-foreground hover:text-brand"
                                }`
                            }
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                <div className="flex items-center gap-3 shrink-0 lg:pl-6 lg:border-l lg:border-border">
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
