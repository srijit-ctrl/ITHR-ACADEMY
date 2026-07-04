import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import CourseCard from "@/components/CourseCard";
import { Search, X } from "lucide-react";

export default function CourseCatalog() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [courses, setCourses] = useState([]);
    const [categories, setCategories] = useState([]);
    const [industries, setIndustries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState(searchParams.get("q") || "");

    const currentCategory = searchParams.get("category") || "";
    const currentIndustry = searchParams.get("industry") || "";
    const currentDifficulty = searchParams.get("difficulty") || "";

    useEffect(() => {
        api.get("/catalog/categories").then((r) => setCategories(r.data.categories));
        api.get("/catalog/industries").then((r) => setIndustries(r.data.industries));
    }, []);

    useEffect(() => {
        setLoading(true);
        const params = {};
        if (currentCategory) params.category = currentCategory;
        if (currentIndustry) params.industry = currentIndustry;
        if (currentDifficulty) params.difficulty = currentDifficulty;
        if (query) params.q = query;
        api.get("/courses", { params }).then((r) => { setCourses(r.data); setLoading(false); });
    }, [currentCategory, currentIndustry, currentDifficulty, query]);

    const updateFilter = (key, value) => {
        const next = new URLSearchParams(searchParams);
        if (value) next.set(key, value); else next.delete(key);
        setSearchParams(next);
    };

    const clearFilters = () => setSearchParams({});

    const difficulties = ["Fundamental", "Beginner", "Intermediate", "Advanced", "Expert", "Architect", "Enterprise Leader", "CXO"];
    const activeCount = [currentCategory, currentIndustry, currentDifficulty].filter(Boolean).length;

    return (
        <div className="container-page py-12 md:py-16">
            <div className="mb-12">
                <div className="overline mb-4 fine-rule pl-4">The Full Catalog</div>
                <h1 className="font-serif text-5xl md:text-6xl tracking-tighter leading-none">Course Catalog</h1>
                <p className="mt-5 text-lg text-muted-foreground max-w-2xl">
                    {courses.length} courses across {categories.length}+ categories and {industries.length} industries. Filter by domain, industry, or level.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-10">
                {/* Filters */}
                <aside className="md:col-span-3 space-y-8">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search courses..."
                            data-testid="catalog-search"
                            className="w-full pl-9 pr-3 py-2.5 bg-surface border border-border rounded-sm text-sm focus:outline-none focus:border-brand focus:ring-1 focus:ring-brand"
                        />
                    </div>

                    {activeCount > 0 && (
                        <button onClick={clearFilters} data-testid="clear-filters" className="text-xs font-mono uppercase tracking-[0.15em] text-brand hover:text-brand-hover flex items-center gap-1">
                            <X className="w-3 h-3" /> Clear {activeCount} filter{activeCount > 1 ? "s" : ""}
                        </button>
                    )}

                    <FilterGroup title="Category" values={categories} current={currentCategory} onChange={(v) => updateFilter("category", v)} testId="filter-category" />
                    <FilterGroup title="Industry" values={industries} current={currentIndustry} onChange={(v) => updateFilter("industry", v)} testId="filter-industry" />
                    <FilterGroup title="Difficulty" values={difficulties} current={currentDifficulty} onChange={(v) => updateFilter("difficulty", v)} testId="filter-difficulty" />
                </aside>

                {/* Grid */}
                <div className="md:col-span-9">
                    {loading ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                            {Array.from({ length: 6 }).map((_, i) => (
                                <div key={i} className="card-flat h-96 animate-pulse bg-surface-alt" />
                            ))}
                        </div>
                    ) : courses.length === 0 ? (
                        <div className="card-flat p-12 text-center">
                            <p className="text-muted-foreground">No courses match your filters.</p>
                            <button onClick={clearFilters} className="btn-outline mt-4">Clear filters</button>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                            {courses.map((c) => <CourseCard key={c.id} course={c} testIdPrefix="catalog-course" />)}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function FilterGroup({ title, values, current, onChange, testId }) {
    return (
        <div>
            <div className="overline mb-3">{title}</div>
            <div className="flex flex-col gap-1.5 max-h-64 overflow-y-auto pr-2">
                {values.map((v) => (
                    <button
                        key={v}
                        onClick={() => onChange(current === v ? "" : v)}
                        data-testid={`${testId}-${v.toLowerCase().replace(/\s+/g, "-").replace(/&/g, "and")}`}
                        className={`text-left text-sm py-1 transition-colors ${current === v ? "text-brand font-medium" : "text-muted-foreground hover:text-foreground"}`}
                    >
                        {v}
                    </button>
                ))}
            </div>
        </div>
    );
}
