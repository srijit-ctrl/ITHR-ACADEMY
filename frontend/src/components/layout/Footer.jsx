import { Link } from "react-router-dom";
import { ITHRLockup } from "@/components/brand/ITHRBrand";

export default function Footer() {
    return (
        <footer className="mt-24 bg-surface-alt/60 border-t border-border">
            {/* Signature brand row */}
            <div className="border-b border-border">
                <div className="container-page py-8 flex items-center justify-between flex-wrap gap-6">
                    <ITHRLockup size={52} />
                    <div className="flex items-center gap-6 text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">
                        <span className="hidden md:inline">An Independent Issuer for the Agentic Enterprise</span>
                        <span className="badge-gold">Est. 2026</span>
                    </div>
                </div>
            </div>

            <div className="container-page py-14 grid grid-cols-2 md:grid-cols-6 gap-10">
                <div className="col-span-2">
                    <p className="text-sm text-muted-foreground leading-relaxed max-w-md">
                        The Enterprise Agentic AI Academy is designed, curated, and operated by <span className="text-foreground font-medium">ITHR Technologies Consulting LLC</span> — a UAE consulting firm publishing structured learning and verifiable credentials for agentic-AI competence.
                    </p>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-teal mb-4">Learn</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/courses" className="hover:text-brand" data-testid="footer-catalog">Course catalog</Link></li>
                        <li><Link to="/certifications" className="hover:text-brand" data-testid="footer-certifications">Certifications</Link></li>
                        <li><Link to="/paths" className="hover:text-brand" data-testid="footer-paths">Learning paths</Link></li>
                        <li><Link to="/intelligence" className="hover:text-brand" data-testid="footer-intelligence">AI Intelligence</Link></li>
                        <li><Link to="/podcast" className="hover:text-brand" data-testid="footer-podcast">Weekly Briefing Podcast</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-teal mb-4">Enterprise</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/pricing" className="hover:text-brand" data-testid="footer-pricing">Pricing</Link></li>
                        <li><Link to="/enterprise" className="hover:text-brand" data-testid="footer-teams">For teams</Link></li>
                        <li><Link to="/hr-suite" className="hover:text-brand" data-testid="footer-hr-suite">HR Transformation Suite</Link></li>
                        <li><Link to="/verify" className="hover:text-brand" data-testid="footer-verify">Verify a credential</Link></li>
                        <li><Link to="/trust" className="hover:text-brand" data-testid="footer-trust">Trust &amp; security</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-teal mb-4">ITHR</div>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li>About ITHR</li>
                        <li>Consulting</li>
                        <li>Contact</li>
                    </ul>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-teal mb-4">Legal</div>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li><Link to="/legal/disclaimer" className="hover:text-brand" data-testid="footer-disclaimer">Disclaimer</Link></li>
                        <li><Link to="/legal/terms" className="hover:text-brand" data-testid="footer-terms">Terms of Service</Link></li>
                        <li><Link to="/legal/security" className="hover:text-brand" data-testid="footer-security">Cyber Security</Link></li>
                        <li><Link to="/legal/compliance" className="hover:text-brand" data-testid="footer-compliance">Compliance</Link></li>
                    </ul>
                </div>
            </div>

            <div className="border-t border-border">
                <div className="container-page py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 text-xs text-muted-foreground">
                    <div className="font-mono uppercase tracking-[0.15em]">© 2026 ITHR Technologies Consulting LLC · All Rights Reserved</div>
                    <Link to="/trust" data-testid="footer-madeinuae" className="inline-flex items-center gap-2.5 hover:text-brand" title="Made in the UAE — for the world">
                        <svg viewBox="0 0 12 6" aria-hidden="true" className="w-6 h-3.5 rounded-[2px] shadow-sm">
                            <rect x="0" y="0" width="12" height="6" fill="#000" />
                            <rect x="0" y="0" width="12" height="4" fill="#FFF" />
                            <rect x="0" y="0" width="12" height="2" fill="#00732F" />
                            <rect x="0" y="0" width="3" height="6" fill="#FF0000" />
                        </svg>
                        <span className="font-mono uppercase tracking-[0.15em]">Made in the UAE — for the world</span>
                    </Link>
                </div>
            </div>
        </footer>
    );
}
