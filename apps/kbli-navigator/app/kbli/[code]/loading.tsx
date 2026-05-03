export default function KBLICodeLoading() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* Breadcrumb skeleton */}
      <div className="h-4 w-64 rounded bg-white/10" />

      {/* Code header */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="h-12 w-24 rounded-xl bg-white/10" />
          <div className="h-8 w-56 rounded bg-white/10" />
        </div>
        <div className="flex gap-2">
          <div className="h-7 w-24 rounded-full bg-white/10" />
          <div className="h-7 w-24 rounded-full bg-white/10" />
          <div className="h-7 w-28 rounded-full bg-white/10" />
        </div>
      </div>

      {/* Description skeleton */}
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-white/10" />
        <div className="h-4 w-full rounded bg-white/10" />
        <div className="h-4 w-4/5 rounded bg-white/10" />
      </div>

      {/* Sections skeleton */}
      <div className="grid gap-4 md:grid-cols-2">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-40 rounded-2xl bg-white/10" />
        ))}
      </div>

      {/* Chat skeleton */}
      <div className="h-64 rounded-2xl bg-white/10" />
    </div>
  );
}
