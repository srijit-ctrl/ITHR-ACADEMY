import { Copy, X } from "lucide-react";
import { toast } from "sonner";

/**
 * One-time display of a newly-created user's temporary credentials.
 * Copy-to-clipboard is the primary CTA — the password is not shown again.
 */
export default function TempCredsModal({ creds, onClose }) {
    const copyBoth = () => {
        navigator.clipboard.writeText(`Email: ${creds.email}\nTemp password: ${creds.temp_password}`);
        toast.success("Credentials copied");
    };

    return (
        <div className="fixed inset-0 z-50 bg-foreground/60 flex items-center justify-center p-4" onClick={onClose}>
            <div className="card-flat max-w-lg w-full bg-surface" onClick={(e) => e.stopPropagation()} data-testid="temp-creds-modal">
                <div className="p-6 border-b border-border flex items-start justify-between">
                    <div>
                        <div className="overline mb-1 text-brand">User created</div>
                        <h3 className="font-serif text-2xl">{creds.name}</h3>
                        <p className="text-xs text-muted-foreground mt-1">Share this temp password over a secure channel — it will not be shown again.</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-surface-alt rounded-sm"><X className="w-4 h-4" /></button>
                </div>
                <div className="p-6 space-y-4">
                    <div className="bg-brand/5 border border-brand p-4 rounded-sm space-y-2">
                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Email</div>
                            <div className="font-mono text-sm break-all" data-testid="temp-creds-email">{creds.email}</div>
                        </div>
                        <div>
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">Temp password</div>
                            <div className="font-mono text-base break-all select-all" data-testid="temp-creds-password">{creds.temp_password}</div>
                        </div>
                    </div>
                    <div className="flex gap-3 justify-end">
                        <button onClick={copyBoth} data-testid="copy-temp-creds" className="btn-outline">
                            <Copy className="w-4 h-4" /> Copy both
                        </button>
                        <button onClick={onClose} data-testid="close-temp-creds" className="btn-primary">Done</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
