export default function LicensesLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-48 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="h-10 w-80 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] p-5 space-y-3">
            <div className="h-6 w-16 rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-5 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-4 w-5/6 rounded bg-[var(--background-secondary)] animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
