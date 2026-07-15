export const TUTOR_META_MARKER = "@@META@@";

// Splits a streamed tutor response into visible text + structured meta.
export function splitTutorMeta(content) {
    const raw = content || "";
    const idx = raw.indexOf(TUTOR_META_MARKER);
    if (idx === -1) return { text: raw, meta: null };
    let meta = null;
    try {
        meta = JSON.parse(raw.slice(idx + TUTOR_META_MARKER.length).trim());
    } catch {
        meta = null;
    }
    return { text: raw.slice(0, idx).trimEnd(), meta };
}
