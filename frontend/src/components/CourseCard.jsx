import { Link } from "react-router-dom";
import { BookOpen, Clock, Star, Users } from "lucide-react";

export default function CourseCard({ course, testIdPrefix = "course" }) {
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
                {course.has_full_content && (
                    <span className="absolute top-3 right-3 badge-crimson bg-background/95 backdrop-blur">Full curriculum</span>
                )}
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
            </div>
        </Link>
    );
}
