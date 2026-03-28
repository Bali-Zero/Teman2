export default function SearchLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Breadcrumb skeleton */}
      <div className="h-4 w-48 rounded bg-white/10" />

      {/* Search bar skeleton */}
      <div className="h-14 w-full rounded-2xl bg-white/10" />

      {/* Filter chips skeleton */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="h-7 w-20 rounded-full bg-white/10" />
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-7 w-16 rounded-full bg-white/10" />
          ))}
        </div>
        <div className="flex gap-2">
          <div className="h-7 w-20 rounded-full bg-white/10" />
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-7 w-16 rounded-full bg-white/10" />
          ))}
        </div>
      </div>

      {/* Results skeleton */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(9)].map((_, i) => (
          <div key={i} className="h-32 rounded-2xl bg-white/10" />
        ))}
      </div>
    </div>
  );
}
