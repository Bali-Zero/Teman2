export default function SectorsLoading() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* Breadcrumb skeleton */}
      <div className="h-4 w-48 rounded bg-white/10" />

      {/* Title skeleton */}
      <div className="h-8 w-64 rounded bg-white/10" />

      {/* Sector grid skeleton */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(12)].map((_, i) => (
          <div key={i} className="h-28 rounded-2xl bg-white/10" />
        ))}
      </div>
    </div>
  );
}
