export function TimelineSkeleton({ count = 3 }: { count?: number }) {
  return (
    <ul aria-label="Loading timeline" className="list-none p-0 m-0">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="flex gap-4 pb-6">
          <div className="flex flex-col items-center">
            <span className="w-3 h-3 rounded-full bg-white/10 animate-pulse" />
            {i < count - 1 && <span className="flex-1 w-px bg-white/5 my-1" />}
          </div>
          <div className="flex-1 space-y-2">
            <div className="h-4 w-1/2 bg-white/10 animate-pulse rounded" />
            <div className="h-3 w-1/3 bg-white/5 animate-pulse rounded" />
          </div>
        </li>
      ))}
    </ul>
  );
}
