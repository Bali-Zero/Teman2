export default function Loading() {
  return (
    <div className="flex h-full bg-[#0c0c0e]">
      {/* Sidebar skeleton */}
      <div className="hidden w-56 flex-shrink-0 border-r border-white/[0.055] bg-[#131315] p-4 lg:block">
        <div className="mb-6 h-9 w-full animate-pulse rounded-lg bg-white/[0.06]" />
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 animate-pulse rounded-md bg-white/[0.04]" />
          ))}
        </div>
      </div>
      {/* Main content skeleton */}
      <div className="flex-1 p-6">
        {/* Toolbar skeleton */}
        <div className="mb-6 flex items-center gap-3">
          <div className="h-9 w-64 animate-pulse rounded-lg bg-white/[0.06]" />
          <div className="flex-1" />
          <div className="h-9 w-9 animate-pulse rounded-lg bg-white/[0.06]" />
          <div className="h-9 w-9 animate-pulse rounded-lg bg-white/[0.06]" />
        </div>
        {/* File grid skeleton */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-xl bg-white/[0.04]" />
          ))}
        </div>
      </div>
    </div>
  );
}
