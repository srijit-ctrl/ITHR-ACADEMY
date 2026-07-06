import { Link } from "react-router-dom";
import { Receipt } from "lucide-react";

/**
 * Right sidebar for EnterprisePortal: departments card, top-courses card,
 * and (owner-only) billing history.
 */
export default function EnterpriseSidebar({ departments, topCourses, isOwner, billing }) {
    return (
        <div className="space-y-8">
            <section>
                <h2 className="font-serif text-xl tracking-tight mb-4">Departments</h2>
                <div className="card-flat">
                    {departments.length === 0 ? (
                        <div className="p-6 text-sm text-muted-foreground">No departments yet — assign departments when inviting.</div>
                    ) : departments.map((d) => (
                        <div key={d.name} className="p-4 border-b border-border last:border-b-0" data-testid={`dept-${d.name}`}>
                            <div className="flex justify-between items-baseline mb-2">
                                <div className="font-serif text-base">{d.name}</div>
                                <div className="text-xs text-muted-foreground">{d.members} people</div>
                            </div>
                            <div className="h-1 bg-border">
                                <div className="h-full bg-brand" style={{ width: `${Math.min(100, d.avg_progress)}%` }} />
                            </div>
                            <div className="flex justify-between text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                                <span>{d.avg_progress}% avg progress</span>
                                <span>{d.certificates} certs</span>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            <section>
                <h2 className="font-serif text-xl tracking-tight mb-4">Top courses</h2>
                <div className="space-y-2">
                    {topCourses.length === 0 ? (
                        <div className="card-flat p-6 text-sm text-muted-foreground">No enrollments yet</div>
                    ) : topCourses.map((c) => (
                        <Link key={c.id} to={`/courses/${c.slug}`} className="card-flat p-4 flex gap-3 items-center hover:border-brand transition-colors" data-testid={`top-course-${c.slug}`}>
                            <div className="w-14 h-14 shrink-0 overflow-hidden border border-border">
                                <img src={c.thumbnail_url} alt="" className="w-full h-full object-cover" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">{c.category}</div>
                                <div className="font-serif text-sm leading-tight truncate">{c.title}</div>
                            </div>
                            <div className="text-xs font-mono text-brand">{c.enrolled_count}×</div>
                        </Link>
                    ))}
                </div>
            </section>

            {isOwner && billing.length > 0 && (
                <section>
                    <h2 className="font-serif text-xl tracking-tight mb-4 flex items-center gap-2">
                        <Receipt className="w-4 h-4 text-brand" /> Billing history
                    </h2>
                    <div className="card-flat divide-y divide-border" data-testid="billing-history">
                        {billing.slice(0, 5).map((b) => (
                            <div key={b.id} className="p-4 text-xs" data-testid={`billing-event-${b.id}`}>
                                <div className="flex items-baseline justify-between gap-2 mb-1">
                                    <span className="font-mono uppercase tracking-[0.15em] text-brand">
                                        {b.type === "prorated_credit" ? "Credit" : "Seats"}
                                    </span>
                                    <span className="text-muted-foreground">
                                        {new Date(b.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                                    </span>
                                </div>
                                <div className="font-serif text-sm">
                                    {b.type === "prorated_credit"
                                        ? `-${b.seats_removed} seats · $${b.amount.toFixed(2)} credit`
                                        : `+${b.seats_added} seats · $${b.amount.toFixed(2)}`}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}
