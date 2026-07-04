import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, API_BASE } from "@/lib/api";
import { Award, ShieldCheck, Share2, Download, Loader2, Linkedin, Copy, Check } from "lucide-react";

export default function Certificate() {
    const { certId } = useParams();
    const [cert, setCert] = useState(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        api.get(`/certificates/verify/${certId}`)
            .then((r) => setCert(r.data.certificate))
            .catch(() => setNotFound(true))
            .finally(() => setLoading(false));
    }, [certId]);

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;
    if (notFound) return <div className="container-page py-24 text-center">Certificate not found.</div>;

    const issued = new Date(cert.issued_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
    const shareUrl = `${window.location.origin}/verify/${cert.certificate_id}`;
    const qrUrl = `${API_BASE}/certificates/${cert.certificate_id}/qr.svg`;
    const linkedInUrl = `https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME&name=${encodeURIComponent(cert.course_title)}&organizationName=${encodeURIComponent("ITHR Technologies")}&issueYear=${new Date(cert.issued_at).getFullYear()}&issueMonth=${new Date(cert.issued_at).getMonth() + 1}&certUrl=${encodeURIComponent(shareUrl)}&certId=${encodeURIComponent(cert.certificate_id)}`;

    const copyLink = async () => {
        await navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="container-page py-16">
            <div className="max-w-4xl mx-auto">
                <div className="overline mb-4 text-center">Digital Credential</div>

                <div className="cert-beam mb-8">
                    <div className="bg-surface p-12 md:p-16">
                        <div className="flex items-start justify-between mb-10 gap-4">
                            <div className="flex items-center gap-3">
                                <div className="w-12 h-12 bg-foreground text-background flex items-center justify-center">
                                    <span className="font-serif text-xl">A</span>
                                </div>
                                <div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Enterprise Agentic AI Academy</div>
                                    <div className="font-serif text-sm">Issued by ITHR Technologies</div>
                                </div>
                            </div>
                            <Award className="w-12 h-12 text-brand" />
                        </div>

                        <div className="text-center py-6">
                            <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-6">This is to certify that</p>
                            <h1 className="font-serif text-5xl md:text-6xl tracking-tighter mb-8" data-testid="cert-holder-name">{cert.user_name}</h1>
                            <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-4">has successfully completed the program</p>
                            <p className="font-serif italic text-2xl md:text-3xl leading-tight mb-6 text-brand" data-testid="cert-course-title">
                                {cert.course_title}
                            </p>
                            <p className="text-sm text-muted-foreground">
                                with a score of <b className="text-foreground">{cert.score}%</b>
                            </p>
                        </div>

                        <div className="mt-10 pt-8 border-t border-border grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
                            <div className="text-center md:text-left">
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Credential ID</div>
                                <div className="font-mono text-sm" data-testid="cert-id">{cert.certificate_id}</div>
                            </div>
                            <div className="text-center md:text-left">
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Issued</div>
                                <div className="font-serif text-lg">{issued}</div>
                            </div>
                            <div className="text-center md:text-left">
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1">Verification</div>
                                <div className="flex items-center md:justify-start justify-center gap-1 text-sm text-success">
                                    <ShieldCheck className="w-4 h-4" /> Verified
                                </div>
                            </div>
                            <div className="flex md:justify-end justify-center">
                                <div className="bg-white p-2 border border-border" data-testid="cert-qr">
                                    <img src={qrUrl} alt="QR verify" className="w-24 h-24 block" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex flex-wrap gap-3 justify-center">
                    <a
                        href={linkedInUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid="share-linkedin"
                        className="btn-primary"
                    >
                        <Linkedin className="w-4 h-4" /> Add to LinkedIn
                    </a>
                    <button
                        onClick={() => window.print()}
                        data-testid="download-certificate"
                        className="btn-outline"
                    >
                        <Download className="w-4 h-4" /> Print / Save PDF
                    </button>
                    <button
                        onClick={copyLink}
                        data-testid="share-certificate"
                        className="btn-outline"
                    >
                        {copied ? <><Check className="w-4 h-4" /> Copied</> : <><Copy className="w-4 h-4" /> Copy verify link</>}
                    </button>
                    <a
                        href={qrUrl}
                        download={`${cert.certificate_id}-qr.svg`}
                        data-testid="download-qr"
                        className="btn-outline"
                    >
                        <Share2 className="w-4 h-4" /> Download QR
                    </a>
                    <Link to="/dashboard" data-testid="cert-back-dashboard" className="btn-outline">Back to dashboard</Link>
                </div>

                <div className="mt-10 text-center text-xs text-muted-foreground max-w-2xl mx-auto">
                    This credential is verifiable at <span className="font-mono">{shareUrl}</span> — anyone can scan the QR to confirm authenticity. ITHR Technologies maintains a public registry of all issued credentials.
                </div>
            </div>
        </div>
    );
}

