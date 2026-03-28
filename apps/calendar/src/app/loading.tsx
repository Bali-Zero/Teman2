export default function Loading() {
  return (
    <div className="flex h-full bg-[#0c0c0e]">
      {/* Sidebar skeleton */}
      <div className="hidden w-64 flex-shrink-0 border-r border-white/[0.055] bg-[#131315] p-4 lg:block">
        <div className="mb-6 h-10 w-full animate-pulse rounded-lg bg-white/[0.06]" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-8 animate-pulse rounded-md bg-white/[0.04]" />
          ))}
        </div>
      </div>
      {/* Calendar grid skeleton */}
      <div className="flex-1 p-6">
        {/* Month header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="h-8 w-48 animate-pulse rounded-lg bg-white/[0.06]" />
          <div className="flex gap-2">
            <div className="h-9 w-9 animate-pulse rounded-lg bg-white/[0.06]" />
            <div className="h-9 w-9 animate-pulse rounded-lg bg-white/[0.06]" />
          </div>
        </div>
        {/* Week header */}
        <div className="mb-2 grid grid-cols-7 gap-1">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-6 animate-pulse rounded bg-white/[0.04]" />
          ))}
        </div>
        {/* Calendar cells */}
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: 35 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-white/[0.03]" />
          ))}
        </div>
      </div>
    </div>
  );
}
