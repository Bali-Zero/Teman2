export default function BlueprintsLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-40 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] p-5 space-y-3">
            <div className="h-5 w-36 rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-4 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
