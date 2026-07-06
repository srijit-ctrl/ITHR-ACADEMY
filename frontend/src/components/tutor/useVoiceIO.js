import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

/**
 * Voice IO for the Aletheia tutor surfaces.
 *  - startRecording() → opens the mic, buffers a webm/opus blob
 *  - stopRecording()  → uploads to /api/voice/stt, returns the transcript
 *  - speak(text)      → fetches /api/voice/tts, plays the MP3 inline
 *  - stopSpeaking()   → mutes any playing TTS
 *
 * Nothing is persisted; the audio blob lives in memory only.
 */
export default function useVoiceIO() {
    const [recording, setRecording] = useState(false);
    const [transcribing, setTranscribing] = useState(false);
    const [speaking, setSpeaking] = useState(false);
    const [micSupported] = useState(
        typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined",
    );

    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const streamRef = useRef(null);
    const audioRef = useRef(null);

    // Ensure any in-flight audio is stopped on unmount
    useEffect(() => {
        return () => {
            try { audioRef.current?.pause(); } catch { /* noop */ }
            try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch { /* noop */ }
        };
    }, []);

    const startRecording = useCallback(async () => {
        if (!micSupported || recording) return;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;
            const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                ? "audio/webm;codecs=opus"
                : (MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "");
            const mr = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
            chunksRef.current = [];
            mr.ondataavailable = (e) => e.data && e.data.size > 0 && chunksRef.current.push(e.data);
            mr.start();
            mediaRecorderRef.current = mr;
            setRecording(true);
        } catch (err) {
            console.error("mic error", err);
            setRecording(false);
        }
    }, [micSupported, recording]);

    const stopRecording = useCallback(async () => {
        const mr = mediaRecorderRef.current;
        if (!mr || mr.state === "inactive") return null;

        const blob = await new Promise((resolve) => {
            mr.onstop = () => {
                const b = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
                resolve(b);
            };
            mr.stop();
        });

        // Release the mic
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        setRecording(false);

        if (!blob || blob.size < 500) return null; // ignore silent taps

        setTranscribing(true);
        try {
            const fd = new FormData();
            fd.append("file", blob, `mic.${(blob.type.split("/")[1] || "webm").split(";")[0]}`);
            fd.append("language", "en");
            const res = await fetch(`${API_BASE}/voice/stt`, { method: "POST", body: fd });
            if (!res.ok) throw new Error(`STT ${res.status}`);
            const data = await res.json();
            return (data.text || "").trim();
        } catch (err) {
            console.error("stt error", err);
            return null;
        } finally {
            setTranscribing(false);
        }
    }, []);

    const stopSpeaking = useCallback(() => {
        try {
            audioRef.current?.pause();
            audioRef.current = null;
        } catch { /* noop */ }
        setSpeaking(false);
    }, []);

    const speak = useCallback(async (text) => {
        const clean = (text || "").trim();
        if (!clean) return;
        stopSpeaking();
        try {
            const res = await fetch(`${API_BASE}/voice/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: clean, voice: "shimmer" }),
            });
            if (!res.ok) throw new Error(`TTS ${res.status}`);
            const data = await res.json();
            const src = `data:${data.mime || "audio/mpeg"};base64,${data.audio_b64}`;
            const audio = new Audio(src);
            audioRef.current = audio;
            setSpeaking(true);
            audio.onended = () => setSpeaking(false);
            audio.onerror = () => setSpeaking(false);
            await audio.play();
        } catch (err) {
            console.error("tts error", err);
            setSpeaking(false);
        }
    }, [stopSpeaking]);

    return {
        micSupported,
        recording,
        transcribing,
        speaking,
        startRecording,
        stopRecording,
        speak,
        stopSpeaking,
    };
}
