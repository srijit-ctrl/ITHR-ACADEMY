import { HelpCircle, Layers, Lightbulb } from "lucide-react";

/**
 * 3-button prompt grid shown before the tutor conversation starts.
 * Prompts are contextual to the lesson (title-substituted via props.lessonTitle).
 */
export default function QuickPrompts({ lessonTitle, onPick }) {
    const prompts = [
        {
            icon: HelpCircle,
            label: "Explain simply",
            text: `Explain the key idea of "${lessonTitle}" in plain language for a busy executive.`,
        },
        {
            icon: Lightbulb,
            label: "Real-world example",
            text: `Give me a concrete real-world example that demonstrates the concepts in "${lessonTitle}".`,
        },
        {
            icon: Layers,
            label: "Quiz me",
            text: `Ask me 3 tough questions to check my understanding of "${lessonTitle}", one at a time. Wait for my answer before revealing the next.`,
        },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
            {prompts.map((qp, i) => (
                <button
                    key={qp.label}
                    data-testid={`inline-tutor-quick-${i}`}
                    onClick={() => onPick(qp.text)}
                    className="card-sharp p-3 text-left group"
                >
                    <qp.icon className="w-3.5 h-3.5 text-brand mb-1.5" />
                    <div className="text-xs font-mono uppercase tracking-[0.15em] text-foreground">{qp.label}</div>
                </button>
            ))}
        </div>
    );
}
