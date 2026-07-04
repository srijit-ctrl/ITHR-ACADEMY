import { Link } from "react-router-dom";
import { ITHR_LOGO_URL } from "@/components/layout/Header";

export default function Footer() {
    return (
        <footer className="border-t border-border mt-24 bg-surface-alt/50">
            <div className="container-page py-16 grid grid-cols-2 md:grid-cols-5 gap-10">
                <div className="col-span-2 md:col-span-2">
                    <div className="flex items-center gap-3 mb-5">
                        <div className="w-10 h-10 bg-foreground p-1 flex items-center justify-center rounded-sm">
                            <img src={ITHR_LOGO_URL} alt="ITHR" className="w-full h-full object-contain" />
                        </div>
                        <div className="flex flex-col leading-none">
                            <span className="font-serif text-lg">Agentic AI Academy</span>
                            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mt-1">An ITHR Technologies Value Proposition</span>
                        </div>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed max-w-md">
                        A certification authority for the agentic enterprise — designed, curated, and continuously refreshed by ITHR Technologies Consulting LLC. Trusted by Fortune 500 workforces to master autonomous AI systems.
                    </p>
                </div>

                <div>
                    <div className="overline mb-4">Learn</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/courses" className="hover:text-brand" data-testid="footer-catalog">Course catalog</Link></li>
                        <li><Link to="/certifications" className="hover:text-brand" data-testid="footer-certifications">Certifications</Link></li>
                        <li><Link to="/industries" className="hover:text-brand" data-testid="footer-industries">Industry tracks</Link></li>
                        <li><Link to="/intelligence" className="hover:text-brand" data-testid="footer-intelligence">AI Intelligence</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="overline mb-4">Enterprise</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/pricing" className="hover:text-brand" data-testid="footer-pricing">Pricing</Link></li>
                        <li><Link to="/enterprise" className="hover:text-brand" data-testid="footer-teams">For teams</Link></li>
                        <li><Link to="/verify" className="hover:text-brand" data-testid="footer-verify">Verify a credential</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="overline mb-4">ITHR</div>
                    <ul className="space-y-2 text-sm">
                        <li><span className="text-muted-foreground">About ITHR</span></li>
                        <li><span className="text-muted-foreground">Consulting</span></li>
                        <li><span className="text-muted-foreground">Contact</span></li>
                    </ul>
                </div>
            </div>

            <div className="border-t border-border">
                <div className="container-page py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 text-xs text-muted-foreground">
                    <div className="font-mono uppercase tracking-[0.15em]">© 2026 ITHR Technologies Consulting LLC · A Certification Authority</div>
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
