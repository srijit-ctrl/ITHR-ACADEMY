import { Trash2 } from "lucide-react";

/**
 * Presentational table of org members. All actions bubble up to the parent.
 */
export default function MembersTable({ members, isAdmin, onRemove }) {
    return (
        <div className="card-flat divide-y divide-border">
            {members.map((m) => (
                <div
                    key={m.id}
                    className="grid grid-cols-12 gap-4 p-4 items-center"
                    data-testid={`member-row-${m.user_id}`}
                >
                    <div className="col-span-5">
                        <div className="font-serif text-base leading-tight">{m.full_name}</div>
                        <div className="text-xs text-muted-foreground">{m.email}</div>
                        {m.department && (
                            <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
                                {m.department}
                            </div>
                        )}
                    </div>
                    <div className="col-span-2 text-xs">
                        <span className={`badge-mono ${m.role === "owner" ? "border-brand text-brand" : ""}`}>
                            {m.role}
                        </span>
                    </div>
                    <div className="col-span-4 text-xs text-muted-foreground grid grid-cols-3 gap-2">
                        <div><b className="text-foreground">{m.stats.enrollments}</b><br />courses</div>
                        <div><b className="text-foreground">{m.stats.certificates}</b><br />certs</div>
                        <div><b className="text-foreground">{m.stats.avg_progress}%</b><br />avg</div>
                    </div>
                    <div className="col-span-1 text-right">
                        {isAdmin && m.role !== "owner" && (
                            <button
                                onClick={() => onRemove(m.id)}
                                data-testid={`remove-member-${m.user_id}`}
                                className="p-1.5 text-muted-foreground hover:text-destructive"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                            </button>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
