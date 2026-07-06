import { useEffect } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

/**
 * State + side-effects for the SeatEditor modal. Preview polling is debounced
 * to 200ms; apply handles the three server outcomes (checkout redirect,
 * credit success, no-op) and reports back via callbacks.
 */
export function useSeatEditor({
    open, seatTarget, setSeatPreview, setSeatBusy, onClose, onSuccess,
}) {
    useEffect(() => {
        if (!open) return;
        const t = setTimeout(() => {
            api.post("/enterprise/organizations/seats/preview", { seat_count: seatTarget })
                .then((r) => setSeatPreview(r.data))
                .catch(() => setSeatPreview(null));
        }, 200);
        return () => clearTimeout(t);
    }, [seatTarget, open, setSeatPreview]);

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
        } finally {
            setSeatBusy(false);
        }
    };

    return { applySeatChange };
}
