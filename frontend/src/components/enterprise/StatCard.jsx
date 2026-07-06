/**
 * Small stat card used across enterprise + super-admin portals.
 * Extracted from EnterprisePortal.jsx so it can be reused independently.
 */
export default function StatCard({ label, value, unit, icon: Icon, accent, testId }) {
    return (
        <div className={`card-flat p-5 ${accent ? "border-brand border-2" : ""}`} data-testid={testId}>
            <Icon className={`w-4 h-4 mb-2 ${accent ? "text-brand" : "text-muted-foreground"}`} />
            <div className="font-serif text-3xl leading-none">
                {value}<span className="text-sm text-muted-foreground">{unit}</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-2">{label}</div>
        </div>
    );
}
