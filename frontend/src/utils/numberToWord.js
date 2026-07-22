/**
 * Number → English word helper.
 *
 * Used to keep marketing copy ("six tiers", "twenty industries") in sync
 * with the actual data model. If someone adds a new certification tier
 * tomorrow, the homepage copy updates automatically — no more "eight tiers"
 * showing on a "six" page.
 */
const WORDS_TO_20 = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
];

const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

export function numberToWord(n) {
    if (n == null || Number.isNaN(n)) return "";
    n = Math.abs(Math.trunc(n));
    if (n <= 20) return WORDS_TO_20[n];
    if (n < 100) {
        const t = Math.floor(n / 10);
        const o = n % 10;
        return o === 0 ? TENS[t] : `${TENS[t]}-${WORDS_TO_20[o]}`;
    }
    // Beyond 99 we just return the number itself — enterprise-safe fallback.
    return String(n);
}

/** Capitalised variant for start-of-sentence usage ("Six tiers."). */
export function numberToWordCap(n) {
    const w = numberToWord(n);
    return w ? w[0].toUpperCase() + w.slice(1) : "";
}
