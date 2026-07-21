/**
 * Curated inspirational quote pool.
 *
 * The self-service portal picks one at random on every login/mount for an
 * instant peppy hit. The "Get a personalised one" button then calls the AI
 * endpoint (Claude Sonnet 4.5 via Emergent LLM key) for a bespoke sentence.
 *
 * Themes: AI mastery, learning, curiosity, engineering craft, agency.
 */
export const CURATED_QUOTES = [
    { text: "The best time to learn agentic AI was five years ago. The second best time is right now.", author: "ITHR Academy" },
    { text: "Every model you train quietly rewires how you think about problems.", author: "Anon · Practitioner" },
    { text: "Curiosity, then rigor, then output. In that order. Every single day.", author: "ITHR Academy" },
    { text: "Small daily reps of learning beat rare heroic sprints. Compound the streak.", author: "James Clear · adapted" },
    { text: "You're not learning tools — you're learning to think in systems that think back.", author: "ITHR Academy" },
    { text: "The most powerful prompt is the one that makes you a better engineer for having written it.", author: "ITHR Academy" },
    { text: "Ship a lesson. Ship a prompt. Ship a demo. Movement over motivation.", author: "ITHR Academy" },
    { text: "Deep work is the new deep learning.", author: "Cal Newport · adapted" },
    { text: "In a world of infinite AI outputs, taste is the ultimate moat.", author: "ITHR Academy" },
    { text: "Great agents aren't smarter — they're better instructed by better thinkers.", author: "ITHR Academy" },
    { text: "The frontier doesn't wait. Neither should you.", author: "ITHR Academy" },
    { text: "Every module you finish is a rung. Certificates are the ladder. Impact is the roof.", author: "ITHR Academy" },
    { text: "The people who move the field aren't those who read the papers — they're those who reimplement them.", author: "Andrej Karpathy · adapted" },
    { text: "You don't master agentic AI by chasing every new model. You master it by staying with one hard problem long enough.", author: "ITHR Academy" },
    { text: "Progress is a byproduct of showing up. Today's small lesson is tomorrow's shipped agent.", author: "ITHR Academy" },
    { text: "The gap between knowing and doing is closed with a single lesson, then repeated 100 times.", author: "ITHR Academy" },
    { text: "Fluency in AI is not vocabulary — it's judgment under uncertainty.", author: "ITHR Academy" },
    { text: "Talent is what people call it when they can't see the practice.", author: "Anon · Practitioner" },
    { text: "You will spend more time thinking about the problem than the model. That's the whole game.", author: "ITHR Academy" },
    { text: "One lesson a day. That's the entire strategy.", author: "ITHR Academy" },
    { text: "Every hour on curated learning saves you a week of trial-and-error later.", author: "ITHR Academy" },
    { text: "The engineers who thrive next are the ones who befriend the machines that think.", author: "ITHR Academy" },
    { text: "Show up before the streak asks you to. That's how careers get built.", author: "ITHR Academy" },
    { text: "Read the paper. Read the code. Then write your own version. That's how mastery is minted.", author: "ITHR Academy" },
    { text: "The certificate is the receipt. The transformation is the reward.", author: "ITHR Academy" },
    { text: "Great agent designers are boring in the best way — they finish what they start.", author: "ITHR Academy" },
    { text: "Optimism is a skill. Practice it while you practice prompting.", author: "ITHR Academy" },
    { text: "Learn the fundamentals before the frontier — the frontier keeps moving.", author: "ITHR Academy" },
    { text: "Explain it to a rubber duck. If it can't understand, neither can your agent.", author: "Programmer folklore" },
    { text: "The best time to reset is now. The best time to keep going is also now.", author: "ITHR Academy" },
];

export function pickRandomQuote() {
    return CURATED_QUOTES[Math.floor(Math.random() * CURATED_QUOTES.length)];
}
