export default function Loading() {
  return (
    <div className="flex h-full bg-[#0c0c0e]">
      {/* Folder sidebar skeleton */}
      <div className="hidden w-56 flex-shrink-0 border-r border-white/[0.055] bg-[#131315] p-4 md:block">
        <div className="mb-6 h-10 w-full animate-pulse rounded-lg bg-white/[0.06]" />
        <div className="space-y-1">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-9 animate-pulse rounded-md bg-white/[0.04]" />
          ))}
        </div>
      </div>
      {/* Email list skeleton */}
      <div className="w-80 flex-shrink-0 border-r border-white/[0.055] p-3 lg:w-96">
        <div className="mb-4 h-9 animate-pulse rounded-lg bg-white/[0.06]" />
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-white/[0.04]" />
          ))}
        </div>
      </div>
      {/* Email viewer skeleton */}
      <div className="hidden flex-1 p-6 lg:block">
        <div className="mb-4 h-8 w-2/3 animate-pulse rounded-lg bg-white/[0.06]" />
        <div className="mb-2 h-4 w-1/3 animate-pulse rounded bg-white/[0.04]" />
        <div className="mt-8 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-4 animate-pulse rounded bg-white/[0.03]" style={{ width: `${85 - i * 10}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}
