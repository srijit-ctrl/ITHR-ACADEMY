import { useRef, useState } from "react";
import { Camera, Loader2, User } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/**
 * Avatar uploader — client-side crop-to-square + downscale + JPEG compress.
 *
 * Reads the file → draws it to an off-screen <canvas> at 256×256 → exports
 * as JPEG data-URI at quality 0.85. Result is typically 40-90 KB even for
 * DSLR-shot inputs, well under the backend's 400 KB cap.
 */
const AVATAR_SIZE = 256;
const AVATAR_QUALITY = 0.85;

function initialsFrom(name, email) {
    const src = (name || email || "?").trim();
    const parts = src.split(/[\s@]+/).filter(Boolean).slice(0, 2);
    return parts.map((p) => p[0].toUpperCase()).join("") || "?";
}

async function readAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(r.result);
        r.onerror = reject;
        r.readAsDataURL(file);
    });
}

async function cropToSquare(dataUrl) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
            const size = Math.min(img.width, img.height);
            const sx = (img.width - size) / 2;
            const sy = (img.height - size) / 2;
            const canvas = document.createElement("canvas");
            canvas.width = AVATAR_SIZE;
            canvas.height = AVATAR_SIZE;
            const ctx = canvas.getContext("2d");
            ctx.imageSmoothingQuality = "high";
            ctx.drawImage(img, sx, sy, size, size, 0, 0, AVATAR_SIZE, AVATAR_SIZE);
            resolve(canvas.toDataURL("image/jpeg", AVATAR_QUALITY));
        };
        img.onerror = reject;
        img.src = dataUrl;
    });
}

export default function AvatarUploader({ user, onUpdated }) {
    const [busy, setBusy] = useState(false);
    const fileRef = useRef(null);

    const initials = initialsFrom(user?.full_name, user?.email);

    const pick = () => fileRef.current?.click();

    const onFileChange = async (e) => {
        const file = e.target.files?.[0];
        e.target.value = ""; // allow re-picking the same file
        if (!file) return;
        if (!file.type.startsWith("image/")) {
            toast.error("Please pick an image file.");
            return;
        }
        if (file.size > 8 * 1024 * 1024) {
            toast.error("File too large — please pick an image under 8 MB.");
            return;
        }
        setBusy(true);
        try {
            const raw = await readAsDataUrl(file);
            const compressed = await cropToSquare(raw);
            const res = await api.patch("/me/profile", { avatar_url: compressed });
            onUpdated?.(res.data.user);
            toast.success("Avatar updated");
        } catch (err) {
            toast.error(err?.response?.data?.detail || "Avatar upload failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <button
            type="button"
            onClick={pick}
            disabled={busy}
            data-testid="ss-avatar-btn"
            className="ss-avatar-frame ss-hover-lift disabled:opacity-60"
            aria-label="Change avatar"
        >
            <div className="inner">
                {user?.avatar_url ? (
                    <img src={user.avatar_url} alt="Your avatar" className="w-full h-full object-cover" />
                ) : (
                    <span>{initials}</span>
                )}
            </div>
            <div className="edit">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
            </div>
            <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={onFileChange}
                data-testid="ss-avatar-input"
            />
        </button>
    );
}

/** Small variant used elsewhere in the app (header nav etc). */
export function AvatarBadge({ user, size = 40 }) {
    const initials = initialsFrom(user?.full_name, user?.email);
    return (
        <div
            className="rounded-full bg-gradient-to-br from-teal-500 to-blue-500 flex items-center justify-center text-white font-semibold overflow-hidden"
            style={{ width: size, height: size }}
        >
            {user?.avatar_url ? (
                <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
                <span style={{ fontSize: size * 0.4 }}>{initials || <User className="w-4 h-4" />}</span>
            )}
        </div>
    );
}
