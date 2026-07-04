import { Link } from "react-router-dom";

export default function Footer() {
    return (
        <footer className="border-t border-border mt-24 bg-surface-alt/40">
            <div className="container-page py-16 grid grid-cols-2 md:grid-cols-4 gap-10">
                <div className="col-span-2 md:col-span-1">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="w-7 h-7 bg-foreground text-background flex items-center justify-center">
                            <span className="font-serif text-base">A</span>
                        </div>
                        <span className="font-serif text-lg">Agentic AI Academy</span>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                        The certification authority for the agentic enterprise. Trusted by Fortune 500 workforces to master autonomous AI systems.
                    </p>
                </div>

                <div>
                    <div className="overline mb-4">Learn</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/courses" className="hover:text-brand" data-testid="footer-catalog">Course catalog</Link></li>
                        <li><Link to="/certifications" className="hover:text-brand" data-testid="footer-certifications">Certifications</Link></li>
                        <li><Link to="/industries" className="hover:text-brand" data-testid="footer-industries">Industry tracks</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="overline mb-4">Enterprise</div>
                    <ul className="space-y-2 text-sm">
                        <li><Link to="/enterprise" className="hover:text-brand" data-testid="footer-teams">For teams</Link></li>
                        <li><Link to="/verify" className="hover:text-brand" data-testid="footer-verify">Verify a certificate</Link></li>
                    </ul>
                </div>

                <div>
                    <div className="overline mb-4">Company</div>
                    <ul className="space-y-2 text-sm">
                        <li><span className="text-muted-foreground">About</span></li>
                        <li><span className="text-muted-foreground">Press</span></li>
                        <li><span className="text-muted-foreground">Careers</span></li>
                    </ul>
                </div>
            </div>

            <div className="border-t border-border">
                <div className="container-page py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 text-xs text-muted-foreground">
                    <div className="font-mono uppercase tracking-[0.15em]">© 2026 Enterprise Agentic AI Academy · A Certification Authority</div>
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
