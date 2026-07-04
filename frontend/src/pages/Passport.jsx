import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, API_BASE } from "@/lib/api";
import { Award, ShieldCheck, ExternalLink, Clock, Loader2, Compass, Linkedin, Copy, Check, Building2 } from "lucide-react";

export default function Passport() {
    const { slug: paramSlug } = useParams();
    const { user } = useAuth();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [copied, setCopied] = useState(false);
    const isMe = !paramSlug;

    useEffect(() => {
        const url = isMe ? "/passport/me" : `/passport/${paramSlug}`;
        api.get(url)
            .then((r) => setData(r.data))
            .catch(() => setData(null))
            .finally(() => setLoading(false));
    }, [paramSlug, isMe]);

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;

    if (!data) return (
        <div className="container-page py-24 text-center">
            <div className="overline mb-3">Passport</div>
            <h1 className="font-serif text-4xl mb-3">Passport not found</h1>
            <p className="text-muted-foreground mb-6">The requested AI Skills Passport doesn&apos;t exist or hasn&apos;t been published yet.</p>
            <Link to="/courses" className="btn-outline">Browse courses</Link>
        </div>
    );

    const shareUrl = `${window.location.origin}/passport/${data.passport_slug}`;
    const copyLink = async () => {
        await navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="container-page py-14">
            {/* Hero */}
            <div className="cert-beam mb-10" data-testid="passport-hero">
                <div className="bg-surface p-10 md:p-14">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
                        <div className="md:col-span-8">
                            <div className="overline mb-4">AI Skills Passport · ITHR Technologies</div>
                            <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-4" data-testid="passport-name">
                                {data.full_name}
                            </h1>
                            <div className="flex items-center gap-3 flex-wrap text-sm mb-6">
                                {data.title && <span className="text-muted-foreground">{data.title}</span>}
                                {data.organization && (
                                    <>
                                        <span className="text-muted-foreground">·</span>
                                        <span className="inline-flex items-center gap-1 text-muted-foreground">
                                            <Building2 className="w-3.5 h-3.5" />
                                            {data.organization}
                                        </span>
                                    </>
                                )}
                            </div>
                            <div className="inline-flex items-center gap-2 border border-border px-4 py-2 bg-surface-alt" data-testid="passport-level">
                                <Award className="w-4 h-4 text-brand" />
                                <span className="font-serif text-lg">Credential level: <b className="text-brand">{data.credential_level}</b></span>
                            </div>
                        </div>

                        <div className="md:col-span-4">
                            <div className="grid grid-cols-3 gap-3">
                                <Metric label="Certificates" value={data.certificates.length} />
                                <Metric label="Skills" value={data.skills.length} />
                                <Metric label="Hours" value={data.learning_hours} />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Actions */}
            {isMe && (
                <div className="flex gap-3 flex-wrap justify-center mb-10">
                    <a
                        href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`}
                        target="_blank" rel="noopener noreferrer"
                        data-testid="passport-share-linkedin"
                        className="btn-primary"
                    >
                        <Linkedin className="w-4 h-4" /> Share on LinkedIn
                    </a>
                    <button onClick={copyLink} data-testid="passport-copy-link" className="btn-outline">
                        {copied ? <><Check className="w-4 h-4" /> Copied</> : <><Copy className="w-4 h-4" /> Copy public URL</>}
                    </button>
                    <Link to="/mentor" className="btn-outline"><Compass className="w-4 h-4" /> Ask Solon what's next</Link>
                </div>
            )}

            {/* Certificates */}
            <section className="mb-12">
                <div className="flex items-end justify-between mb-6">
                    <div>
                        <div className="overline mb-1">Verified credentials</div>
                        <h2 className="font-serif text-3xl tracking-tight">Certifications</h2>
                    </div>
                    <span className="text-sm text-muted-foreground">{data.certificates.length}</span>
                </div>

                {data.certificates.length === 0 ? (
                    <div className="card-flat p-10 text-center">
                        <p className="text-muted-foreground mb-4">No certifications yet.</p>
                        {isMe && <Link to="/courses" className="btn-outline">Start a course</Link>}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="passport-certificates">
                        {data.certificates.map((cert) => (
                            <div key={cert.certificate_id} className="card-sharp p-5">
                                <div className="flex items-start justify-between mb-4">
                                    <Award className="w-6 h-6 text-brand" />
                                    <img
                                        src={`${API_BASE}/certificates/${cert.certificate_id}/qr.svg`}
                                        alt="QR"
                                        className="w-14 h-14 bg-white p-1 border border-border"
                                    />
                                </div>
                                <div className="font-serif text-lg leading-tight mb-2 line-clamp-2">{cert.course_title}</div>
                                <div className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">
                                    {cert.certificate_id}
                                </div>
                                <div className="text-sm mb-4 flex items-center gap-2">
                                    <ShieldCheck className="w-3 h-3 text-success" />
                                    Score: <b>{cert.score}%</b>
                                    <span className="text-muted-foreground text-xs ml-auto">
                                        <Clock className="w-3 h-3 inline mr-1" />
                                        {new Date(cert.issued_at).toLocaleDateString("en-US", { year: "numeric", month: "short" })}
                                    </span>
                                </div>
                                <Link
                                    to={`/verify/${cert.certificate_id}`}
                                    data-testid={`passport-cert-verify-${cert.certificate_id}`}
                                    className="text-xs text-brand font-mono uppercase tracking-[0.15em] inline-flex items-center gap-1 hover:underline"
                                >
                                    Verify <ExternalLink className="w-3 h-3" />
                                </Link>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            {/* Skills */}
            {data.skills.length > 0 && (
                <section className="mb-12">
                    <div className="overline mb-1">Competencies</div>
                    <h2 className="font-serif text-3xl tracking-tight mb-6">Skills</h2>
                    <div className="flex flex-wrap gap-2" data-testid="passport-skills">
                        {data.skills.map((s) => (
                            <span key={s} className="border border-border px-3 py-1.5 text-sm bg-surface-alt">{s}</span>
                        ))}
                    </div>
                </section>
            )}

            {/* Industries */}
            {data.industries.length > 0 && (
                <section className="mb-12">
                    <div className="overline mb-1">Domain fluency</div>
                    <h2 className="font-serif text-3xl tracking-tight mb-6">Industries</h2>
                    <div className="flex flex-wrap gap-2" data-testid="passport-industries">
                        {data.industries.map((s) => (
                            <span key={s} className="badge-mono">{s}</span>
                        ))}
                    </div>
                </section>
            )}

            <div className="mt-14 pt-8 border-t border-border text-center text-xs text-muted-foreground">
                Issued by <b className="text-foreground">ITHR Technologies</b>. Every credential here is independently verifiable at{" "}
                <span className="font-mono">{window.location.origin}/verify/{"{cert-id}"}</span>.
            </div>
        </div>
    );
}

function Metric({ label, value }) {
    return (
        <div className="border border-border p-3 bg-surface-alt text-center">
            <div className="font-serif text-3xl leading-none">{value}</div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">{label}</div>
        </div>
    );
}
