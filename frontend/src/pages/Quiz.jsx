import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Timer, Award, XCircle, Loader2, ArrowRight, Shuffle } from "lucide-react";

const DEFAULT_COUNT = 15;

export default function Quiz() {
    const { slug } = useParams();
    const navigate = useNavigate();
    const [session, setSession] = useState(null);   // {course_id, questions, passing_score, total, bank_size}
    const [courseTitle, setCourseTitle] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [answers, setAnswers] = useState({});
    const [submitted, setSubmitted] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [startedAt, setStartedAt] = useState(Date.now());
    const [remaining, setRemaining] = useState(30 * 60);

    const loadSession = async () => {
        setLoading(true);
        setError("");
        setAnswers({});
        setSubmitted(null);
        try {
            const [s, c] = await Promise.all([
                api.get(`/courses/${slug}/assessment/session?count=${DEFAULT_COUNT}`),
                api.get(`/courses/${slug}`),
            ]);
            setSession(s.data);
            setCourseTitle(c.data.title);
            setStartedAt(Date.now());
            setRemaining(30 * 60);
        } catch (e) {
            setError(e?.response?.data?.detail || "Unable to start assessment");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadSession(); }, [slug]);

    useEffect(() => {
        if (submitted) return;
        const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
        return () => clearInterval(t);
    }, [submitted]);

    const toggle = (qid, idx, isMulti) => {
        setAnswers((prev) => {
            const cur = prev[qid] || [];
            if (isMulti) {
                return { ...prev, [qid]: cur.includes(idx) ? cur.filter((i) => i !== idx) : [...cur, idx] };
            }
            return { ...prev, [qid]: [idx] };
        });
    };

    const submit = async () => {
        setSubmitting(true);
        try {
            const duration = Math.round((Date.now() - startedAt) / 1000);
            const perms = {};
            for (const q of session.questions) perms[q.id] = q.permutation;
            const res = await api.post(`/courses/${slug}/quiz/submit`, {
                course_id: session.course_id,
                answers: { ...answers, __perm__: perms },
                duration_seconds: duration,
            });
            setSubmitted(res.data);
        } finally { setSubmitting(false); }
    };

    if (loading) return <div className="container-page py-24"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>;

    if (error || !session || !session.questions?.length) return (
        <div className="container-page py-24 text-center">
            <p className="text-muted-foreground mb-6">{error || "No assessment available for this course yet."}</p>
            <Link to={`/courses/${slug}`} className="btn-outline">Back to course</Link>
        </div>
    );

    if (submitted) return <QuizResults result={submitted} slug={slug} navigate={navigate} onRetry={loadSession} />;

    const mins = String(Math.floor(remaining / 60)).padStart(2, "0");
    const secs = String(remaining % 60).padStart(2, "0");
    const answeredCount = Object.keys(answers).length;
    const questions = session.questions;

    return (
        <div className="container-narrow py-12">
            <div className="flex items-start justify-between mb-10 gap-6 flex-wrap">
                <div>
                    <div className="overline mb-3 fine-rule pl-4">Certification Exam · Randomized</div>
                    <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none">{courseTitle}</h1>
                    <p className="mt-3 text-muted-foreground flex items-center gap-2 flex-wrap">
                        <span>Passing score: <b className="text-foreground">{session.passing_score}%</b></span>
                        <span className="text-muted-foreground">·</span>
                        <span>{session.total} of {session.bank_size} questions</span>
                        <span className="badge-brand"><Shuffle className="w-3 h-3 mr-1" />Randomized</span>
                    </p>
                </div>
                <div className="card-flat p-4 flex items-center gap-3 shrink-0">
                    <Timer className="w-5 h-5 text-brand" />
                    <div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Time remaining</div>
                        <div className="font-mono text-xl" data-testid="quiz-timer">{mins}:{secs}</div>
                    </div>
                </div>
            </div>

            <div className="space-y-8">
                {questions.map((q, qi) => {
                    const isMulti = q.type === "multi";
                    return (
                        <div key={q.id} className="card-flat p-6" data-testid={`quiz-question-${qi + 1}`}>
                            <div className="flex items-baseline gap-3 mb-4">
                                <span className="font-mono text-xs text-brand">{String(qi + 1).padStart(2, "0")}</span>
                                <div>
                                    <div className="font-serif text-lg leading-tight mb-1">{q.question}</div>
                                    <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                                        {q.type === "multi" ? "Multiple select" : q.type === "true_false" ? "True/False" : q.type === "scenario" ? "Scenario" : "Single answer"}
                                    </div>
                                </div>
                            </div>
                            <div className="space-y-2 pl-8">
                                {q.options.map((opt, oi) => {
                                    const selected = (answers[q.id] || []).includes(oi);
                                    return (
                                        <button
                                            key={oi}
                                            onClick={() => toggle(q.id, oi, isMulti)}
                                            data-testid={`quiz-q${qi + 1}-opt-${oi}`}
                                            className={`w-full text-left px-4 py-3 border transition-all text-sm ${
                                                selected
                                                    ? "border-brand bg-brand/5 text-foreground"
                                                    : "border-border hover:border-foreground bg-surface"
                                            }`}
                                        >
                                            <span className="font-mono text-xs text-muted-foreground mr-3">{String.fromCharCode(65 + oi)}</span>
                                            {opt}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="mt-10 flex justify-between items-center flex-wrap gap-3">
                <div className="text-sm text-muted-foreground">
                    Answered: <b className="text-foreground">{answeredCount}</b> / {questions.length}
                </div>
                <button
                    onClick={submit}
                    disabled={submitting || answeredCount === 0}
                    data-testid="submit-quiz"
                    className="btn-primary"
                >
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Submit exam <ArrowRight className="w-4 h-4" /></>}
                </button>
            </div>
        </div>
    );
}

function QuizResults({ result, slug, navigate, onRetry }) {
    return (
        <div className="container-narrow py-20 text-center">
            <div className={`w-16 h-16 mx-auto mb-8 flex items-center justify-center ${result.passed ? "bg-success text-white" : "bg-surface-alt text-muted-foreground border border-border"}`}>
                {result.passed ? <Award className="w-8 h-8" /> : <XCircle className="w-8 h-8" />}
            </div>

            <div className="overline mb-4">{result.passed ? "Certification Awarded" : "Exam Result"}</div>
            <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none mb-6">
                {result.passed ? "Congratulations." : "Not this time."}
            </h1>
            <p className="text-lg text-muted-foreground mb-10">
                You scored <b className="text-foreground">{result.score}%</b> ({result.correct}/{result.total} correct). Passing score: {result.passing_score}%.
            </p>

            {result.certificate && (
                <div className="cert-beam mb-10">
                    <div className="bg-surface p-8 text-left">
                        <div className="overline mb-2">Digital Credential</div>
                        <div className="font-serif text-2xl mb-2">{result.certificate.course_title}</div>
                        <div className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mb-6">ID: {result.certificate.certificate_id}</div>
                        <Link to={`/certificate/${result.certificate.certificate_id}`} data-testid="view-certificate" className="btn-primary">
                            View credential <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                </div>
            )}

            <div className="flex gap-3 justify-center flex-wrap">
                {!result.passed && (
                    <button onClick={onRetry} data-testid="retry-quiz" className="btn-outline">Retake with new questions</button>
                )}
                <Link to="/dashboard" data-testid="quiz-back-dashboard" className="btn-outline">Back to dashboard</Link>
            </div>
        </div>
    );
}
