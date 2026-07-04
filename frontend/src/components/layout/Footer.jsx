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
                        <span className="hidden md:inline">A Certification Authority for the Agentic Enterprise</span>
                        <span className="badge-gold">Est. 2026</span>
                    </div>
                </div>
            </div>

            <div className="container-page py-14 grid grid-cols-2 md:grid-cols-5 gap-10">
                <div className="col-span-2">
                    <p className="text-sm text-muted-foreground leading-relaxed max-w-md">
                        The Enterprise Agentic AI Academy is designed, curated, and continuously refreshed by <span className="text-foreground font-medium">ITHR Technologies Consulting LLC</span>. Trusted by Fortune 500 workforces to master autonomous AI systems.
                    </p>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-gold-deep mb-4">Learn</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/courses" className="hover:text-brand" data-testid="footer-catalog">Course catalog</Link></li>
                        <li><Link to="/certifications" className="hover:text-brand" data-testid="footer-certifications">Certifications</Link></li>
                        <li><Link to="/paths" className="hover:text-brand" data-testid="footer-paths">Learning paths</Link></li>
                        <li><Link to="/intelligence" className="hover:text-brand" data-testid="footer-intelligence">AI Intelligence</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-gold-deep mb-4">Enterprise</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/pricing" className="hover:text-brand" data-testid="footer-pricing">Pricing</Link></li>
                        <li><Link to="/enterprise" className="hover:text-brand" data-testid="footer-teams">For teams</Link></li>
                        <li><Link to="/verify" className="hover:text-brand" data-testid="footer-verify">Verify a credential</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand-gold-deep mb-4">ITHR</div>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li>About ITHR</li>
                        <li>Consulting</li>
                        <li>Contact</li>
                    </ul>
                </div>
            </div>

            <div className="border-t border-border">
                <div className="container-page py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 text-xs text-muted-foreground">
                    <div className="font-mono uppercase tracking-[0.15em]">© 2026 ITHR Technologies Consulting LLC · All Rights Reserved</div>
                    <div className="flex gap-6 font-mono uppercase tracking-[0.15em]">
                        <span>SOC 2 Type II</span>
                        <span>ISO 27001</span>
                        <span>GDPR</span>
                    </div>
                </div>
            </div>
        </footer>
    );
}
