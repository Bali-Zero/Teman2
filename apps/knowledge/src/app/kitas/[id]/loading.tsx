export default function KitasDetailLoading() {
  return (
    <div className="space-y-6 p-6 max-w-4xl mx-auto">
      <div className="h-6 w-24 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="h-10 w-2/3 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="flex gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-7 w-20 rounded-full bg-[var(--background-secondary)] animate-pulse" />
        ))}
      </div>
      <div className="rounded-xl border border-[var(--border)] p-6 space-y-4">
        <div className="h-5 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
        <div className="h-5 w-5/6 rounded bg-[var(--background-secondary)] animate-pulse" />
        <div className="h-5 w-4/6 rounded bg-[var(--background-secondary)] animate-pulse" />
      </div>
    </div>
  );
}
