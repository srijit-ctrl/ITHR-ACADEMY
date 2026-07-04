import { Link } from "react-router-dom";
import { BookOpen, Star, Users, Radio } from "lucide-react";

function freshnessColor(score) {
    if (score >= 90) return "text-brand border-brand bg-brand/5";
    if (score >= 75) return "text-brand-blue border-brand-blue bg-brand-blue/5";
    if (score >= 65) return "text-warning border-warning bg-warning/5";
    return "text-muted-foreground border-border bg-surface-alt";
}

function freshnessLabel(days) {
    if (days == null || days > 500) return "New";
    if (days === 0) return "Refreshed today";
    if (days === 1) return "Refreshed 1d ago";
    if (days < 7) return `Refreshed ${days}d ago`;
    if (days < 30) return `Refreshed ${Math.floor(days / 7)}w ago`;
    if (days < 90) return `Refreshed ${Math.floor(days / 30)}mo ago`;
    return "Review scheduled";
}

export default function CourseCard({ course, testIdPrefix = "course" }) {
    const score = course.freshness_score ?? 100;
    return (
        <Link
            to={`/courses/${course.slug}`}
            data-testid={`${testIdPrefix}-card-${course.slug}`}
            className="card-sharp group flex flex-col overflow-hidden"
        >
            <div className="aspect-[16/10] relative overflow-hidden bg-surface-alt">
                <img
                    src={course.thumbnail_url}
                    alt={course.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                    loading="lazy"
                />
                <div className="absolute top-3 left-3 flex gap-1.5">
                    <span className="badge-mono bg-background/95 backdrop-blur">{course.category}</span>
                </div>
                <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5">
                    {course.has_full_content && (
                        <span className="badge-mono bg-background/95 backdrop-blur border-brand text-brand">Full curriculum</span>
                    )}
                    <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-none text-[10px] font-mono uppercase tracking-[0.15em] border ${freshnessColor(score)} bg-background shadow-sm`}
                        data-testid={`freshness-badge-${course.slug}`}
                        title={freshnessLabel(course.days_since_review)}
                    >
                        <Radio className="w-2.5 h-2.5" />
                        {score}
                    </span>
                </div>
            </div>

            <div className="p-6 flex flex-col flex-1">
                <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-3">
                    <span>{course.difficulty}</span>
                    <span className="opacity-30">·</span>
                    <span>{course.duration_hours} hours</span>
                </div>
                <h3 className="font-serif text-xl leading-tight tracking-tight mb-2 group-hover:text-brand transition-colors">
                    {course.title}
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed flex-1 line-clamp-2">
                    {course.subtitle}
                </p>

                <div className="mt-5 pt-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                    <div className="flex items-center gap-3">
                        <span className="flex items-center gap-1"><Star className="w-3 h-3 fill-brand text-brand" />{course.rating.toFixed(1)}</span>
                        <span className="flex items-center gap-1"><Users className="w-3 h-3" />{course.enrolled_count.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center gap-1"><BookOpen className="w-3 h-3" />{course.module_count || 15} modules</div>
                </div>
                <div className="mt-2 text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                    {freshnessLabel(course.days_since_review)}
                </div>
            </div>
        </Link>
    );
}
