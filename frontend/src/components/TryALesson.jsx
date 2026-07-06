import useDemoLesson from "@/components/demo/useDemoLesson";
import DemoLessonBody from "@/components/demo/DemoLessonBody";
import DemoChat from "@/components/demo/DemoChat";

/**
 * Anonymous "Try a lesson" widget shown on the landing page.
 * Composes the lesson body + streaming Q&A chat. All streaming state lives
 * in the useDemoLesson hook.
 */
export default function TryALesson() {
    const { lesson, messages, input, setInput, streaming, limitReached, ask } = useDemoLesson();
    if (!lesson) return null;

    return (
        <section className="section-warm-cream border-y border-border py-24" data-testid="try-a-lesson">
            <div className="container-page">
                <div className="text-center max-w-2xl mx-auto mb-14">
                    <span className="section-kicker">Try before you enroll</span>
                    <h2 className="font-serif text-4xl md:text-5xl tracking-tighter leading-tight mb-4">
                        Take a lesson with <span className="italic text-brand">Aletheia</span>.
                    </h2>
                    <p className="text-muted-foreground text-lg">
                        No sign-up. Read a 4-minute mini-lesson, then ask Aletheia any question &mdash; she&apos;ll stream a live answer right below.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 max-w-6xl mx-auto">
                    <DemoLessonBody lesson={lesson} />
                    <DemoChat
                        lesson={lesson}
                        messages={messages}
                        input={input}
                        setInput={setInput}
                        streaming={streaming}
                        limitReached={limitReached}
                        ask={ask}
                    />
                </div>
            </div>
        </section>
    );
}
