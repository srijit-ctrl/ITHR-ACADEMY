import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import TutorLauncher from "@/components/tutor/TutorLauncher";
import TutorDrawer from "@/components/tutor/TutorDrawer";

/**
 * AITutorPanel — floating tutor available anywhere in the app for
 * authenticated users. Delegates the open/closed states to two focused
 * components so this shell stays under 25 lines.
 */
export default function AITutorPanel({ courseSlug = null }) {
    const { user } = useAuth();
    const [open, setOpen] = useState(false);

    if (!user) return null;

    return (
        <>
            {!open && <TutorLauncher onOpen={() => setOpen(true)} />}
            {open && <TutorDrawer courseSlug={courseSlug} onClose={() => setOpen(false)} />}
        </>
    );
}
