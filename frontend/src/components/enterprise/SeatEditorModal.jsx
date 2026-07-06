import { useEffect } from "react";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

/**
 * Owner-only seat-adjustment modal.
 * Owns none of the state — everything is passed in from EnterprisePortal so
 * the parent can freely re-run its `load()` after a successful change.
 */
export default function SeatEditorModal({
    open, org, summary,
    seatTarget, setSeatTarget,
    seatPreview, setSeatPreview,
    seatBusy, setSeatBusy,
    onClose, onSuccess,
}) {
    // Live preview of seat change (debounced 200ms)
    useEffect(() => {
        if (!open) return;
        const t = setTimeout(() => {
            api.post("/enterprise/organizations/seats/preview", { seat_count: seatTarget })
                .then((r) => setSeatPreview(r.data))
                .catch(() => setSeatPreview(null));
        }, 200);
        return () => clearTimeout(t);
    }, [seatTarget, open, setSeatPreview]);

    if (!open) return null;

    const applySeatChange = async () => {
        setSeatBusy(true);
        try {
            const res = await api.post("/enterprise/organizations/seats", {
                seat_count: seatTarget,
                origin_url: window.location.origin,
            });
            if (res.data.action === "checkout" && res.data.checkout_url) {
                window.location.href = res.data.checkout_url;
                return;
            }
            if (res.data.action === "credit") toast.success(res.data.message);
            else toast.info("No change applied.");
            onClose();
            onSuccess();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Seat update failed");
        } finally { setSeatBusy(false); }
    };

    return (
        <div className="fixed inset-0 z-50 bg-foreground/40 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="seat-editor">
                <div className="p-6 border-b border-border">
                    <div className="overline mb-2">Manage seats</div>
                    <h3 className="font-serif text-2xl">Adjust your team plan</h3>
                </div>
                <div className="p-6 space-y-5">
                    <div>
                        <label htmlFor="seat-target-input" className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Seat count (min 10)</label>
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
                        <p className="text-xs text-muted-foreground mt-1">Currently: {org.seat_count} · In use: {summary.seats_used}</p>
                    </div>

                    {seatPreview && seatPreview.action !== "noop" && (
                        <div className={`border p-4 ${seatPreview.action === "checkout" ? "border-brand bg-brand/5" : "border-border bg-surface-alt"}`} data-testid="seat-preview">
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
                            {seatBusy ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                seatPreview?.action === "checkout" ? "Proceed to checkout" :
                                seatPreview?.action === "credit" ? "Apply reduction" : "Apply"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
