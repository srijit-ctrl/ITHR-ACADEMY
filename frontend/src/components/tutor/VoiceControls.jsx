import { Loader2, Mic, MicOff, Volume2, VolumeX } from "lucide-react";

/**
 * Compact mic + speaker control cluster used across all Aletheia surfaces.
 * Props:
 *   - voice: return value of useVoiceIO()
 *   - onTranscript(text): fired when a mic recording finishes and STT resolves
 *   - lastAssistantText: last assistant reply — enables the speaker button
 *   - size: "sm" (default) | "md"
 *   - testidPrefix: e.g. "cert-tutor-voice"
 */
export default function VoiceControls({ voice, onTranscript, lastAssistantText, size = "sm", testidPrefix = "voice" }) {
    if (!voice) return null;
    const { micSupported, recording, transcribing, speaking, startRecording, stopRecording, speak, stopSpeaking } = voice;

    const dim = size === "md" ? "w-11 h-11" : "w-9 h-9";
    const icon = size === "md" ? "w-5 h-5" : "w-4 h-4";

    const handleMic = async () => {
        if (recording) {
            const text = await stopRecording();
            if (text) onTranscript?.(text);
        } else {
            await startRecording();
        }
    };

    const handleSpeaker = () => {
        if (speaking) {
            stopSpeaking();
        } else if (lastAssistantText) {
            speak(lastAssistantText);
        }
    };

    return (
        <div className="flex items-center gap-1.5" data-testid={testidPrefix}>
            {micSupported && (
                <button
                    type="button"
                    onClick={handleMic}
                    disabled={transcribing}
                    data-testid={`${testidPrefix}-mic`}
                    title={recording ? "Stop recording" : "Ask by voice"}
                    className={`${dim} rounded-sm border flex items-center justify-center transition-colors ${
                        recording
                            ? "bg-brand text-background border-brand animate-pulse"
                            : "bg-surface-alt border-border text-foreground hover:border-brand"
                    } disabled:opacity-50`}
                >
                    {transcribing ? <Loader2 className={`${icon} animate-spin`} /> : recording ? <MicOff className={icon} /> : <Mic className={icon} />}
                </button>
            )}
            <button
                type="button"
                onClick={handleSpeaker}
                disabled={!lastAssistantText}
                data-testid={`${testidPrefix}-speaker`}
                title={speaking ? "Stop speaking" : "Hear last answer"}
                className={`${dim} rounded-sm border flex items-center justify-center transition-colors ${
                    speaking
                        ? "bg-brand text-background border-brand"
                        : "bg-surface-alt border-border text-foreground hover:border-brand"
                } disabled:opacity-40`}
            >
                {speaking ? <VolumeX className={icon} /> : <Volume2 className={icon} />}
            </button>
        </div>
    );
}
