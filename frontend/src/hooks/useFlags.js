import { useEffect, useState } from "react";
import { api } from "@/lib/api";

let _cache = null;

// Feature flags — defaults to all-enabled until fetched (backend enforces anyway).
export default function useFlags() {
    const [flags, setFlags] = useState(_cache || {});

    useEffect(() => {
        if (_cache) return;
        api.get("/flags").then((r) => {
            _cache = r.data;
            setFlags(r.data);
        }).catch(() => {});
    }, []);

    return { flags, isEnabled: (name) => flags[name] !== false };
}
