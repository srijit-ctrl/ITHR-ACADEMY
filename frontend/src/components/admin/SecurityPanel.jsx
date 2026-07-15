import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { KeyRound, Loader2, Plus, RefreshCw, ShieldCheck, Trash2, Copy } from "lucide-react";
import { toast } from "sonner";

export default function SecurityPanel() {
    return (
        <div className="space-y-10" data-testid="security-panel">
            <MfaSection />
            <PasswordPolicySection />
            <PlatformApiKeysSection />
            <VendorKeysSection />
        </div>
    );
}

/* ---------- MFA enforcement + self enrollment ---------- */

function MfaSection() {
    const [enforcement, setEnforcement] = useState("off");
    const [myMfa, setMyMfa] = useState(null);
    const [enroll, setEnroll] = useState(null); // {qr_image, secret}
    const [code, setCode] = useState("");
    const [backupCodes, setBackupCodes] = useState([]);
    const [busy, setBusy] = useState(false);

    const load = () => {
        api.get("/admin/security/settings").then((r) => setEnforcement(r.data.mfa_enforcement)).catch(() => {});
        api.get("/security/mfa/status").then((r) => setMyMfa(r.data)).catch(() => {});
    };
    useEffect(load, []);

    const saveEnforcement = async (val) => {
        setEnforcement(val);
        try {
            await api.put("/admin/security/settings", { mfa_enforcement: val });
            toast.success("MFA enforcement updated");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Update failed");
        }
    };

    const startEnroll = async () => {
        setBusy(true);
        try {
            const r = await api.post("/security/mfa/setup");
            setEnroll(r.data);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Setup failed");
        } finally {
            setBusy(false);
        }
    };

    const verifyEnroll = async () => {
        setBusy(true);
        try {
            const r = await api.post("/security/mfa/verify", { code });
            setBackupCodes(r.data.backup_codes);
            setEnroll(null);
            setCode("");
            load();
            toast.success("MFA enabled");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Invalid code");
        } finally {
            setBusy(false);
        }
    };

    const disableMfa = async () => {
        const c = window.prompt("Enter a current code from your authenticator to disable MFA:");
        if (!c) return;
        try {
            await api.post("/security/mfa/disable", { code: c });
            toast.success("MFA disabled");
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Disable failed");
        }
    };

    return (
        <section className="card-flat p-6">
            <div className="flex items-center gap-2 mb-5">
                <ShieldCheck className="w-4 h-4 text-brand" />
                <h3 className="font-serif text-xl tracking-tight">Multi-factor authentication</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                    <div className="overline mb-3">Enforcement policy</div>
                    <select value={enforcement} onChange={(e) => saveEnforcement(e.target.value)} data-testid="mfa-enforcement-select" className="w-full bg-surface border border-border rounded-sm px-3 py-2.5 text-sm focus:outline-none focus:border-brand">
                        <option value="off">Off — MFA optional for everyone</option>
                        <option value="super_admins">Require for super admins</option>
                        <option value="admins">Require for all admins</option>
                        <option value="all">Require for all users</option>
                    </select>
                    <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
                        Users covered by the policy who haven't enrolled see a setup prompt at login. Users with MFA enabled always get the TOTP challenge.
                    </p>
                </div>
                <div>
                    <div className="overline mb-3">Your account</div>
                    {!myMfa ? <Loader2 className="w-4 h-4 animate-spin" /> : myMfa.enabled ? (
                        <div>
                            <div className="text-sm text-success mb-3">✓ MFA is enabled on your account</div>
                            <button onClick={disableMfa} data-testid="mfa-disable-btn" className="btn-outline text-sm">Disable MFA</button>
                        </div>
                    ) : enroll ? (
                        <div className="space-y-3" data-testid="mfa-enroll-flow">
                            <img src={enroll.qr_image} alt="MFA QR" className="w-40 h-40 border border-border" />
                            <div className="text-xs text-muted-foreground">Scan with Google Authenticator / Authy, or enter manually:</div>
                            <code className="text-xs font-mono break-all block bg-surface-alt px-2 py-1">{enroll.secret}</code>
                            <div className="flex gap-2">
                                <input value={code} onChange={(e) => setCode(e.target.value)} data-testid="mfa-enroll-code" placeholder="6-digit code" className="flex-1 bg-surface border border-border rounded-sm px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand" />
                                <button onClick={verifyEnroll} disabled={busy || !code.trim()} data-testid="mfa-enroll-verify" className="btn-primary text-sm">
                                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify"}
                                </button>
                            </div>
                        </div>
                    ) : (
                        <button onClick={startEnroll} disabled={busy} data-testid="mfa-setup-btn" className="btn-primary text-sm">
                            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Set up MFA on my account"}
                        </button>
                    )}
                    {backupCodes.length > 0 && (
                        <div className="mt-4 border border-brand/30 bg-brand/5 p-4" data-testid="mfa-backup-codes">
                            <div className="overline mb-2 text-brand">Backup codes — save these now</div>
                            <pre className="text-xs font-mono leading-relaxed">{backupCodes.join("\n")}</pre>
                            <p className="text-[10px] text-muted-foreground mt-2">Each code works once. They will not be shown again.</p>
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}

/* ---------- Password policy ---------- */

function PasswordPolicySection() {
    const [policy, setPolicy] = useState(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        api.get("/admin/security/settings").then((r) => setPolicy(r.data.password_policy)).catch(() => {});
    }, []);

    const save = async () => {
        setSaving(true);
        try {
            await api.put("/admin/security/settings", { password_policy: policy });
            toast.success("Password policy saved");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Save failed");
        } finally {
            setSaving(false);
        }
    };

    if (!policy) return null;
    const Toggle = ({ k, label }) => (
        <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={!!policy[k]} onChange={(e) => setPolicy({ ...policy, [k]: e.target.checked })} data-testid={`policy-${k}`} className="accent-[var(--brand,#00A78B)]" />
            {label}
        </label>
    );

    return (
        <section className="card-flat p-6" data-testid="password-policy-section">
            <div className="flex items-center gap-2 mb-5">
                <KeyRound className="w-4 h-4 text-brand" />
                <h3 className="font-serif text-xl tracking-tight">Password policy</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                <div>
                    <div className="overline mb-2">Minimum length</div>
                    <input type="number" min={6} max={64} value={policy.min_length} onChange={(e) => setPolicy({ ...policy, min_length: parseInt(e.target.value || 8, 10) })} data-testid="policy-min-length" className="w-24 bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                </div>
                <div className="space-y-2">
                    <Toggle k="require_upper" label="Require uppercase letter" />
                    <Toggle k="require_lower" label="Require lowercase letter" />
                    <Toggle k="require_digit" label="Require digit" />
                    <Toggle k="require_symbol" label="Require symbol" />
                    <Toggle k="block_common" label="Block common passwords" />
                </div>
                <div>
                    <button onClick={save} disabled={saving} data-testid="policy-save" className="btn-primary text-sm">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save policy"}
                    </button>
                    <p className="text-xs text-muted-foreground mt-3">Applies to new registrations and password changes.</p>
                </div>
            </div>
        </section>
    );
}

/* ---------- Platform-issued API keys ---------- */

function PlatformApiKeysSection() {
    const [keys, setKeys] = useState([]);
    const [name, setName] = useState("");
    const [newKey, setNewKey] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = () => api.get("/admin/api-keys").then((r) => setKeys(r.data.keys || [])).catch(() => {});
    useEffect(() => { load(); }, []);

    const create = async () => {
        setBusy(true);
        try {
            const r = await api.post("/admin/api-keys", { name });
            setNewKey(r.data.key);
            setName("");
            load();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Create failed");
        } finally {
            setBusy(false);
        }
    };

    const rotate = async (id) => {
        try {
            const r = await api.post(`/admin/api-keys/${id}/rotate`);
            setNewKey(r.data.key);
            load();
            toast.success("Key rotated — old key revoked");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Rotate failed");
        }
    };

    const revoke = async (id, kname) => {
        if (!window.confirm(`Revoke "${kname}"? Consumers using it will lose access immediately.`)) return;
        try {
            await api.delete(`/admin/api-keys/${id}`);
            load();
            toast.success("Key revoked");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Revoke failed");
        }
    };

    return (
        <section className="card-flat p-6" data-testid="api-keys-section">
            <div className="flex items-center justify-between mb-5">
                <h3 className="font-serif text-xl tracking-tight">Platform API keys</h3>
                <div className="flex gap-2">
                    <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Key name (e.g. Partner X)" data-testid="apikey-name-input" className="bg-surface border border-border rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-brand" />
                    <button onClick={create} disabled={busy || !name.trim()} data-testid="apikey-create-btn" className="btn-primary text-sm flex items-center gap-1">
                        <Plus className="w-3.5 h-3.5" /> Issue key
                    </button>
                </div>
            </div>
            {newKey && (
                <div className="border border-brand/30 bg-brand/5 p-4 mb-5" data-testid="apikey-new-key">
                    <div className="overline mb-2 text-brand">Copy this key now — it will not be shown again</div>
                    <div className="flex items-center gap-2">
                        <code className="text-xs font-mono break-all flex-1">{newKey}</code>
                        <button onClick={() => { navigator.clipboard.writeText(newKey); toast.success("Key copied"); }} data-testid="apikey-copy" className="p-2 border border-border hover:border-brand"><Copy className="w-3.5 h-3.5" /></button>
                    </div>
                </div>
            )}
            {keys.length === 0 ? (
                <p className="text-sm text-muted-foreground">No platform API keys issued yet. Keys grant partners access to ITHR APIs (validate via GET /api/partner/ping with X-API-Key).</p>
            ) : (
                <table className="w-full text-sm">
                    <thead><tr className="text-left text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-b border-border">
                        <th className="py-2">Name</th><th>Prefix</th><th>Created</th><th>Last used</th><th>Status</th><th></th>
                    </tr></thead>
                    <tbody>
                        {keys.map((k) => (
                            <tr key={k.id} className="border-b border-border/50" data-testid={`apikey-row-${k.id}`}>
                                <td className="py-2.5">{k.name}</td>
                                <td className="font-mono text-xs">{k.prefix}…</td>
                                <td className="text-xs text-muted-foreground">{(k.created_at || "").slice(0, 10)}</td>
                                <td className="text-xs text-muted-foreground">{k.last_used_at ? k.last_used_at.slice(0, 10) : "never"}</td>
                                <td>{k.revoked ? <span className="text-xs text-muted-foreground">revoked</span> : <span className="text-xs text-success">active</span>}</td>
                                <td className="text-right">
                                    {!k.revoked && (
                                        <div className="flex gap-1 justify-end">
                                            <button onClick={() => rotate(k.id)} title="Rotate" data-testid={`apikey-rotate-${k.id}`} className="p-1.5 border border-border hover:border-brand"><RefreshCw className="w-3.5 h-3.5" /></button>
                                            <button onClick={() => revoke(k.id, k.name)} title="Revoke" data-testid={`apikey-revoke-${k.id}`} className="p-1.5 border border-border hover:border-red-500 hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                                        </div>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </section>
    );
}

/* ---------- Vendor (3rd-party) key rotation tracking ---------- */

function VendorKeysSection() {
    const [keys, setKeys] = useState([]);

    const load = () => api.get("/admin/vendor-keys").then((r) => setKeys(r.data.keys || [])).catch(() => {});
    useEffect(() => { load(); }, []);

    const markRotated = async (name) => {
        try {
            await api.post(`/admin/vendor-keys/${name}/mark-rotated`);
            load();
            toast.success(`${name} marked as rotated`);
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    const rotationDue = (k) => {
        if (!k.last_rotated_at) return true;
        const days = (Date.now() - new Date(k.last_rotated_at).getTime()) / 86400000;
        return days > (k.reminder_days || 90);
    };

    return (
        <section className="card-flat p-6" data-testid="vendor-keys-section">
            <h3 className="font-serif text-xl tracking-tight mb-2">3rd-party vendor keys</h3>
            <p className="text-xs text-muted-foreground mb-5">Rotate these at the vendor's dashboard, update the environment variable, then mark rotated here. Reminder window: 90 days.</p>
            <table className="w-full text-sm">
                <thead><tr className="text-left text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-b border-border">
                    <th className="py-2">Key</th><th>Value</th><th>Last rotated</th><th>Status</th><th></th>
                </tr></thead>
                <tbody>
                    {keys.map((k) => (
                        <tr key={k.key_name} className="border-b border-border/50" data-testid={`vendor-key-${k.key_name}`}>
                            <td className="py-2.5 font-mono text-xs">{k.key_name}</td>
                            <td className="font-mono text-xs text-muted-foreground">{k.configured ? k.masked : <span className="text-red-500">not set</span>}</td>
                            <td className="text-xs text-muted-foreground">{k.last_rotated_at ? k.last_rotated_at.slice(0, 10) : "unknown"}</td>
                            <td>{rotationDue(k) ? <span className="text-xs text-brand">rotation due</span> : <span className="text-xs text-success">fresh</span>}</td>
                            <td className="text-right">
                                <button onClick={() => markRotated(k.key_name)} data-testid={`vendor-rotated-${k.key_name}`} className="text-xs border border-border hover:border-brand px-2 py-1">Mark rotated</button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </section>
    );
}
