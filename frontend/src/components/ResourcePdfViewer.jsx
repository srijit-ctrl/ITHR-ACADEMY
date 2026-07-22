/**
 * ResourcePdfViewer — modal PDF viewer for course companion resources.
 *
 * Rendering approach: `react-pdf` (pdf.js) — renders every PDF page to a canvas,
 * so it works in every browser including headless Chromium (which lacks the
 * native PDF plugin). We fetch the PDF as a blob (auth headers carried by axios)
 * and hand the ArrayBuffer to `<Document file={...}>`.
 *
 * Fallback UX: on 502 (LibreOffice unavailable), 415 (unpreviewable format),
 * or a pdf.js load failure, we show a friendly card with a "Download the source"
 * CTA so the learner is never stuck.
 *
 * Access rule mirrors the backend: enrolled learners only for non-public
 * resources; the modal is unreachable for other users because the parent
 * card only renders the "Open" button when they're enrolled.
 */
import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { X, Loader2, Download, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

// pdf.js worker — served from the CDN that matches the pdfjs-dist version
// bundled by react-pdf so the API surface can't drift.
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export default function ResourcePdfViewer({ resource, courseSlug, onClose }) {
    const [status, setStatus] = useState("loading"); // loading | ready | error
    const [pdfData, setPdfData] = useState(null);
    const [numPages, setNumPages] = useState(0);
    const [pageNumber, setPageNumber] = useState(1);
    const [errorMsg, setErrorMsg] = useState("");
    const containerRef = useRef(null);
    const [containerWidth, setContainerWidth] = useState(1000);

    // Fetch the PDF once on mount.
    useEffect(() => {
        let cancelled = false;
        const ctrl = new AbortController();

        (async () => {
            try {
                const res = await api.get(
                    `/courses/${courseSlug}/resources/${encodeURIComponent(resource.filename)}/preview.pdf`,
                    { responseType: "arraybuffer", signal: ctrl.signal },
                );
                if (cancelled) return;
                setPdfData(res.data);
                setStatus("ready");
            } catch (err) {
                if (cancelled || err?.name === "CanceledError") return;
                const s = err?.response?.status;
                if (s === 502) {
                    setErrorMsg("In-portal preview isn't available right now — please download the deck instead.");
                } else if (s === 403) {
                    setErrorMsg("Enrol in this course to preview the deck inside the portal.");
                } else if (s === 415) {
                    setErrorMsg("This file type can't be previewed. Please download it instead.");
                } else {
                    setErrorMsg("Couldn't load the preview. Please try again in a moment.");
                }
                setStatus("error");
            }
        })();

        return () => {
            cancelled = true;
            ctrl.abort();
        };
    }, [resource.filename, courseSlug]);

    // Resize page rendering when container width changes.
    useEffect(() => {
        if (!containerRef.current) return;
        const ro = new ResizeObserver((entries) => {
            for (const e of entries) setContainerWidth(Math.max(400, e.contentRect.width - 48));
        });
        ro.observe(containerRef.current);
        return () => ro.disconnect();
    }, [status]);

    // Keyboard: ESC closes, arrows page through.
    useEffect(() => {
        const onKey = (e) => {
            if (e.key === "Escape") onClose?.();
            if (e.key === "ArrowLeft") setPageNumber((n) => Math.max(1, n - 1));
            if (e.key === "ArrowRight") setPageNumber((n) => Math.min(numPages || 1, n + 1));
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [onClose, numPages]);

    const downloadOriginal = async () => {
        try {
            const res = await api.get(
                `/courses/${courseSlug}/resources/${encodeURIComponent(resource.filename)}`,
                { responseType: "blob" },
            );
            const url = URL.createObjectURL(res.data);
            const a = document.createElement("a");
            a.href = url;
            a.download = resource.download_name || resource.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast.success("Downloaded — check your Downloads folder");
        } catch (e) {
            toast.error("Download failed. Please contact support.");
        }
    };

    // Memoise the file prop so react-pdf doesn't reload on every render.
    const [fileProp, setFileProp] = useState(null);
    useEffect(() => {
        if (pdfData) setFileProp({ data: pdfData });
    }, [pdfData]);

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
            data-testid="resource-pdf-viewer"
            role="dialog"
            aria-modal="true"
            onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
        >
            <div className="w-full h-[92vh] max-w-6xl bg-background rounded-lg border border-border shadow-2xl flex flex-col overflow-hidden">
                {/* Header */}
                <div className="flex items-center gap-3 px-5 py-3 border-b border-border shrink-0">
                    <div className="w-9 h-9 rounded-md flex items-center justify-center shrink-0"
                         style={{ background: "linear-gradient(135deg, #00A78B 0%, #2E7FC1 100%)", color: "#fff" }}>
                        <span className="text-xs font-mono font-bold">PDF</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="font-serif text-base leading-tight truncate">{resource.title}</div>
                        <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-0.5">
                            In-portal preview · Rendered from PowerPoint deck
                        </div>
                    </div>
                    {status === "ready" && numPages > 0 && (
                        <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-muted-foreground">
                            <button
                                onClick={() => setPageNumber((n) => Math.max(1, n - 1))}
                                disabled={pageNumber <= 1}
                                className="p-1.5 rounded hover:bg-surface-alt disabled:opacity-30"
                                data-testid="viewer-prev-page"
                                title="Previous page"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <span data-testid="viewer-page-indicator">{pageNumber} / {numPages}</span>
                            <button
                                onClick={() => setPageNumber((n) => Math.min(numPages, n + 1))}
                                disabled={pageNumber >= numPages}
                                className="p-1.5 rounded hover:bg-surface-alt disabled:opacity-30"
                                data-testid="viewer-next-page"
                                title="Next page"
                            >
                                <ChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    )}
                    <button
                        onClick={downloadOriginal}
                        data-testid="viewer-download-source"
                        className="btn-outline text-xs inline-flex items-center gap-1.5"
                        title="Download the original PPTX"
                    >
                        <Download className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Download PPTX</span>
                    </button>
                    <button
                        onClick={onClose}
                        data-testid="viewer-close"
                        className="p-2 rounded-md hover:bg-surface-alt text-muted-foreground"
                        title="Close preview"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Body */}
                <div
                    ref={containerRef}
                    className="flex-1 relative bg-surface-alt/40 overflow-auto"
                >
                    {status === "loading" && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                            <Loader2 className="w-6 h-6 animate-spin text-brand" />
                            <div className="text-sm">Preparing your preview…</div>
                            <div className="text-xs opacity-70">First open converts the deck — takes ~5-10 seconds.</div>
                        </div>
                    )}

                    {status === "ready" && fileProp && (
                        <div className="flex flex-col items-center gap-4 py-6 px-4" data-testid="viewer-pdf-canvas-wrap">
                            <Document
                                file={fileProp}
                                onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                                onLoadError={(err) => {
                                    setErrorMsg("Couldn't render this document — please download it instead.");
                                    setStatus("error");
                                    console.error("react-pdf load error:", err);
                                }}
                                loading={
                                    <div className="flex items-center gap-3 text-muted-foreground">
                                        <Loader2 className="w-5 h-5 animate-spin text-brand" />
                                        <span className="text-sm">Rendering deck…</span>
                                    </div>
                                }
                            >
                                <Page
                                    pageNumber={pageNumber}
                                    width={containerWidth}
                                    renderTextLayer={false}
                                    renderAnnotationLayer={false}
                                    className="shadow-md"
                                />
                            </Document>
                        </div>
                    )}

                    {status === "error" && (
                        <div className="absolute inset-0 flex items-center justify-center p-8">
                            <div className="card-flat p-8 max-w-md text-center" data-testid="viewer-error-card">
                                <div className="w-12 h-12 rounded-full bg-warning/10 flex items-center justify-center mx-auto mb-4">
                                    <AlertCircle className="w-6 h-6 text-warning" />
                                </div>
                                <div className="font-serif text-xl mb-2">Preview unavailable</div>
                                <p className="text-sm text-muted-foreground mb-6">{errorMsg}</p>
                                <div className="flex gap-2 justify-center">
                                    <button onClick={downloadOriginal} className="btn-primary text-xs" data-testid="viewer-fallback-download">
                                        <Download className="w-3.5 h-3.5" /> Download PPTX
                                    </button>
                                    <button onClick={onClose} className="btn-outline text-xs">
                                        Close
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
