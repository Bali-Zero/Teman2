export default function TaxLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-36 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-8 w-28 rounded-full bg-[var(--background-secondary)] animate-pulse" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] p-5 space-y-3">
            <div className="h-5 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-4 w-3/4 rounded bg-[var(--background-secondary)] animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
