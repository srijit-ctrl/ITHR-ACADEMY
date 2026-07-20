import { useEffect, useRef, useState } from "react";
import { Loader2, Send, Sparkles, X } from "lucide-react";
import QuickPrompts from "@/components/tutor/QuickPrompts";
import TutorConversation from "@/components/tutor/TutorConversation";
import useTutorStream from "@/components/tutor/useTutorStream";
import useVoiceIO from "@/components/tutor/useVoiceIO";
import VoiceControls from "@/components/tutor/VoiceControls";

/**
 * InlineTutor — embedded in the lesson pane. Composes quick-prompt grid +
 * streaming conversation via the useTutorStream hook. Voice-enabled: mic
 * transcribes into the input, speaker plays back the last reply, and
 * mic-asked questions auto-play the answer.
 */
export default function InlineTutor({ courseSlug, lesson, moduleTitle }) {
    const [open, setOpen] = useState(false);
    const [input, setInput] = useState("");
    const [autoplayNext, setAutoplayNext] = useState(false);
    const spokenIdRef = useRef(null);
    const voice = useVoiceIO();
    const { messages, streaming, send, reset, ratings, rateTurn, modelKey, setModelKey, availableModels } = useTutorStream({ courseSlug, lesson, moduleTitle });

    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

    useEffect(() => {
        if (!autoplayNext || streaming || !lastAssistant?.content) return;
        if (spokenIdRef.current === lastAssistant.id) return;
        spokenIdRef.current = lastAssistant.id;
        voice.speak(lastAssistant.content);
        setAutoplayNext(false);
    }, [streaming, lastAssistant, autoplayNext, voice]);

    const handleSend = async (text) => {
        const clean = (text || input).trim();
        if (!clean) return;
        setInput("");
        setOpen(true);
        await send(clean);
    };

    const handleMicTranscript = async (text) => {
        setInput("");
        setOpen(true);
        setAutoplayNext(true);
        await send(text);
    };

    return (
        <div className="mt-12 border-t border-border pt-10" data-testid="inline-tutor">
            <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-foreground text-background flex items-center justify-center rounded-sm">
                        <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="font-serif text-lg leading-none">Ask Aletheia about this lesson</div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                            Contextual AI Tutor · streaming · voice-enabled
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <VoiceControls
                        voice={voice}
                        onTranscript={handleMicTranscript}
                        lastAssistantText={lastAssistant?.content || ""}
                        testidPrefix="inline-tutor-voice"
                    />
                    {messages.length > 0 && (
                        <button
                            data-testid="inline-tutor-reset"
                            onClick={reset}
                            className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-brand flex items-center gap-1"
                        >
                            <X className="w-3 h-3" /> Clear
                        </button>
                    )}
                </div>
            </div>

            {messages.length === 0 && !open && (
                <QuickPrompts lessonTitle={lesson?.title || "this lesson"} onPick={handleSend} />
            )}

            {(open || messages.length > 0) && (
                <TutorConversation messages={messages} streaming={streaming} onAction={handleSend} ratings={ratings} onRate={rateTurn} />
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSend()}
                    onFocus={() => setOpen(true)}
                    placeholder={`Ask about "${lesson?.title || "this lesson"}"… or tap the mic`}
                    disabled={streaming}
                    data-testid="inline-tutor-input"
                    className="flex-1 min-w-[200px] bg-surface-alt border border-border rounded-sm px-4 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
                />
                {availableModels?.models?.length > 1 && (
                    <select
                        value={modelKey || availableModels.default}
                        onChange={(e) => setModelKey(e.target.value)}
                        disabled={streaming}
                        data-testid="tutor-model-picker"
                        aria-label="Tutor model"
                        className="bg-surface-alt border border-border rounded-sm px-2.5 py-2.5 text-xs font-mono focus:outline-none focus:border-brand"
                    >
                        {availableModels.models.map((m) => (
                            <option key={m.key} value={m.key}>{m.label}</option>
                        ))}
                    </select>
                )}
                <button
                    onClick={() => handleSend()}
                    disabled={streaming || !input.trim()}
                    data-testid="inline-tutor-send"
                    className="btn-primary"
                >
                    {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4" /> Ask</>}
                </button>
            </div>
        </div>
    );
}
