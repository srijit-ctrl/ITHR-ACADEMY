import DOMPurify from "dompurify";

/**
 * Renders the demo lesson body (title + section list). Content is markdown-lite
 * (bold + emphasis) so we sanitize before dangerouslySetInnerHTML.
 */
export default function DemoLessonBody({ lesson }) {
    return (
        <article className="lg:col-span-3 step-card">
            <div className="flex items-center justify-between mb-5">
                <span className="badge-gold">Unit 01 · {lesson.duration_min} min</span>
                <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-brand-teal">ITHR Academy</span>
            </div>
            <h3 className="font-serif text-3xl tracking-tight mb-6">{lesson.title}</h3>
            <div className="space-y-6">
                {lesson.sections.map((s) => (
                    <div key={s.heading}>
                        <h4 className="font-serif text-lg text-brand mb-2">{s.heading}</h4>
                        <p
                            className="text-sm leading-relaxed text-foreground"
                            dangerouslySetInnerHTML={{
                                __html: DOMPurify.sanitize(
                                    s.body
                                        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                                        .replace(/\*(.+?)\*/g, '<em class="text-brand">$1</em>')
                                ),
                            }}
                        />
                    </div>
                ))}
            </div>
        </article>
    );
}
