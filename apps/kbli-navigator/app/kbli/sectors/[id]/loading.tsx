export default function SectorDetailLoading() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* Breadcrumb skeleton */}
      <div className="h-4 w-64 rounded bg-white/10" />

      {/* Sector header skeleton */}
      <div className="space-y-3">
        <div className="h-10 w-3/4 rounded bg-white/10" />
        <div className="h-4 w-full max-w-2xl rounded bg-white/10" />
        <div className="h-4 w-2/3 max-w-xl rounded bg-white/10" />
      </div>

      {/* KBLI cards skeleton */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(12)].map((_, i) => (
          <div key={i} className="h-32 rounded-2xl bg-white/10" />
        ))}
      </div>
    </div>
  );
}
