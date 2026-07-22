import { Link } from "react-router-dom";
import { Compass, ArrowLeft } from "lucide-react";

export default function NotFound() {
    return (
        <div className="container-page py-24 md:py-32" data-testid="not-found-page">
            <div className="max-w-2xl">
                <div className="overline mb-4 text-brand">Error 404</div>
                <div className="font-serif text-[6rem] md:text-[9rem] leading-none tracking-tighter text-brand/20 select-none">
                    404
                </div>
                <h1 className="font-serif text-4xl md:text-5xl tracking-tighter leading-none -mt-4 mb-5">
                    This page took a wrong turn.
                </h1>
                <p className="text-lg text-muted-foreground leading-relaxed mb-8 max-w-xl">
                    The page you&apos;re looking for doesn&apos;t exist, moved, or never did. Let&apos;s get you
                    back to something useful.
                </p>
                <div className="flex flex-wrap gap-3">
                    <Link to="/" className="btn-primary" data-testid="not-found-home">
                        <ArrowLeft className="w-4 h-4" /> Back to home
                    </Link>
                    <Link to="/courses" className="btn-outline" data-testid="not-found-catalog">
                        <Compass className="w-4 h-4" /> Browse the course catalog
                    </Link>
                </div>
            </div>
        </div>
    );
}
