import { Sparkles } from "lucide-react";

/**
 * Bottom-left floating launcher button for the AITutorPanel. Split out so
 * the parent component just toggles `open`.
 */
export default function TutorLauncher({ onOpen }) {
    return (
        <button
            onClick={onOpen}
            data-testid="open-ai-tutor"
            className="fixed bottom-6 left-6 z-50 group flex items-center gap-2 bg-foreground text-background rounded-sm pl-4 pr-5 py-3 shadow-[0_10px_40px_-10px_rgba(0,168,151,0.4)] hover:bg-brand transition-all duration-300"
        >
            <div className="relative">
                <Sparkles className="w-5 h-5" />
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-brand rounded-full animate-pulse" />
            </div>
            <span className="font-medium text-sm">Ask Aletheia</span>
        </button>
    );
}
