export default function KitasLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-40 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-8 w-24 rounded-full bg-[var(--background-secondary)] animate-pulse" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] p-5 space-y-3">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-[var(--background-secondary)] animate-pulse" />
              <div className="h-5 w-32 rounded bg-[var(--background-secondary)] animate-pulse" />
            </div>
            <div className="h-4 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-4 w-2/3 rounded bg-[var(--background-secondary)] animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
