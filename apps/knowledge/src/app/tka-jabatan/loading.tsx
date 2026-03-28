export default function TkaJabatanLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-52 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="flex gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-10 w-32 rounded-lg bg-[var(--background-secondary)] animate-pulse" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] p-4 space-y-2">
            <div className="h-5 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-4 w-3/4 rounded bg-[var(--background-secondary)] animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
