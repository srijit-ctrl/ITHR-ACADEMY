import { useEffect, useRef, useState } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";
import useTutorStream from "@/components/tutor/useTutorStream";
import TutorConversation from "@/components/tutor/TutorConversation";
import useVoiceIO from "@/components/tutor/useVoiceIO";
import VoiceControls from "@/components/tutor/VoiceControls";

/**
 * Certificate-page engagement widget. Post-certification "Ask Aletheia"
 * so credential holders can quickly refresh their memory or prep for
 * exam retries. Reuses the useTutorStream hook, so all streaming +
 * session logic is shared with InlineTutor / AITutorPanel.
 * Voice-interactive: mic → STT into input, and speaker → TTS of the last
 * assistant reply. Auto-plays new replies when the mic was used to ask.
 */
export default function CertificateTutor({ certificate }) {
    const [input, setInput] = useState("");
    const [autoplayNext, setAutoplayNext] = useState(false);
    const spokenIdRef = useRef(null);
    const voice = useVoiceIO();
    const { messages, streaming, send, ratings, rateTurn } = useTutorStream({
        courseSlug: certificate.course_slug,
        lesson: { id: certificate.course_id, title: certificate.course_title },
        moduleTitle: `Certified in ${certificate.course_title}`,
    });

    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

    // Auto-speak the newest full assistant reply (only when voice mode is active)
    useEffect(() => {
        if (!autoplayNext || streaming || !lastAssistant?.content) return;
        if (spokenIdRef.current === lastAssistant.id) return;
        spokenIdRef.current = lastAssistant.id;
        voice.speak(lastAssistant.content);
        setAutoplayNext(false);
    }, [streaming, lastAssistant, autoplayNext, voice]);

    const quickAsks = [
        `Give me a 60-second refresher on the key ideas of "${certificate.course_title}".`,
        `What are the top 3 things I should remember when applying "${certificate.course_title}" in a real project?`,
        `Ask me 3 questions to test if I still remember the material from "${certificate.course_title}".`,
    ];

    const handleSend = async (text) => {
        const clean = (text || input).trim();
        if (!clean) return;
        setInput("");
        await send(clean);
    };

    const handleMicTranscript = async (text) => {
        setInput("");
        setAutoplayNext(true);
        await send(text);
    };

    return (
        <section className="mt-16 border-t border-border pt-12" data-testid="cert-tutor">
            <div className="max-w-3xl mx-auto">
                <div className="flex items-center gap-3 mb-5">
                    <div className="w-10 h-10 bg-foreground text-background flex items-center justify-center rounded-sm">
                        <Sparkles className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                        <div className="font-serif text-xl leading-none">Keep the knowledge fresh</div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                            Ask Aletheia · {certificate.course_title} · voice-enabled
                        </div>
                    </div>
                    <VoiceControls
                        voice={voice}
                        onTranscript={handleMicTranscript}
                        lastAssistantText={lastAssistant?.content || ""}
                        testidPrefix="cert-tutor-voice"
                    />
                </div>

                {messages.length === 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-5">
                        {quickAsks.map((q) => (
                            <button
                                key={q}
                                onClick={() => handleSend(q)}
                                data-testid={`cert-tutor-quick-${quickAsks.indexOf(q)}`}
                                className="card-sharp p-3 text-left text-xs hover:border-brand"
                            >
                                {q}
                            </button>
                        ))}
                    </div>
                ) : (
                    <TutorConversation messages={messages} streaming={streaming} ratings={ratings} onRate={rateTurn} />
                )}

                <div className="mt-4 flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSend()}
                        placeholder={`Ask about ${certificate.course_title}… or tap the mic`}
                        disabled={streaming}
                        data-testid="cert-tutor-input"
                        className="flex-1 bg-surface-alt border border-border rounded-sm px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
                    />
                    <button
                        onClick={() => handleSend()}
                        disabled={streaming || !input.trim()}
                        data-testid="cert-tutor-send"
                        className="btn-primary"
                    >
                        {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Ask</>}
                    </button>
                </div>
            </div>
        </section>
    );
}
