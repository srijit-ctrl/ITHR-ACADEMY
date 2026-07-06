import { Loader2 } from "lucide-react";
import { useSeatEditor } from "@/hooks/useSeatEditor";

const seatChangeLabel = (previewAction) => {
    if (previewAction === "checkout") return "Proceed to checkout";
    if (previewAction === "credit") return "Apply reduction";
    return "Apply";
};

/**
 * Owner-only seat-adjustment modal. Presentational shell — the debounced
 * preview + apply orchestration lives in `useSeatEditor`.
 */
export default function SeatEditorModal({
    open, org, summary,
    seatTarget, setSeatTarget,
    seatPreview, setSeatPreview,
    seatBusy, setSeatBusy,
    onClose, onSuccess,
}) {
    const { applySeatChange } = useSeatEditor({
        open, seatTarget, setSeatPreview, setSeatBusy, onClose, onSuccess,
    });

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 bg-foreground/40 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="seat-editor">
                <div className="p-6 border-b border-border">
                    <div className="overline mb-2">Manage seats</div>
                    <h3 className="font-serif text-2xl">Adjust your team plan</h3>
                </div>
                <div className="p-6 space-y-5">
                    <div>
                        <label htmlFor="seat-target-input" className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                            Seat count (min 10)
                        </label>
                        <input
                            id="seat-target-input"
                            type="number"
                            min={10}
                            max={5000}
                            value={seatTarget}
                            onChange={(e) => setSeatTarget(parseInt(e.target.value || 0))}
                            data-testid="seat-target"
                            className="mt-1 w-full bg-surface-alt border border-border rounded-sm px-4 py-2 text-lg focus:outline-none focus:border-brand"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                            Currently: {org.seat_count} · In use: {summary.seats_used}
                        </p>
                    </div>

                    {seatPreview && seatPreview.action !== "noop" && (
                        <div
                            className={`border p-4 ${seatPreview.action === "checkout" ? "border-brand bg-brand/5" : "border-border bg-surface-alt"}`}
                            data-testid="seat-preview"
                        >
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] mb-1">
                                {seatPreview.action === "checkout" ? "Charge summary" : "Credit note"}
                            </div>
                            <p className="text-sm">{seatPreview.message}</p>
                        </div>
                    )}

                    <div className="flex gap-3 justify-end pt-2">
                        <button onClick={onClose} className="btn-outline">Cancel</button>
                        <button
                            onClick={applySeatChange}
                            disabled={seatBusy || seatTarget === org.seat_count}
                            data-testid="apply-seat-change"
                            className="btn-primary"
                        >
                            {seatBusy
                                ? <Loader2 className="w-4 h-4 animate-spin" />
                                : seatChangeLabel(seatPreview?.action)}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
