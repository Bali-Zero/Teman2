export default function KnowledgeLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-8 w-48 rounded bg-[var(--background-secondary)] animate-pulse" />
          <div className="h-4 w-72 rounded bg-[var(--background-secondary)] animate-pulse" />
        </div>
        <div className="h-10 w-36 rounded bg-[var(--background-secondary)] animate-pulse" />
      </div>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="h-10 w-80 rounded bg-[var(--background-secondary)] animate-pulse" />
        <div className="h-10 w-28 rounded bg-[var(--background-secondary)] animate-pulse" />
      </div>

      {/* Categories */}
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-8 w-24 rounded bg-[var(--background-secondary)] animate-pulse"
          />
        ))}
      </div>

      {/* Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border border-[var(--border)] p-5 space-y-3"
          >
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded bg-[var(--background-secondary)] animate-pulse" />
              <div className="h-6 w-16 rounded bg-[var(--background-secondary)] animate-pulse" />
            </div>
            <div className="h-4 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
            <div className="h-4 w-5/6 rounded bg-[var(--background-secondary)] animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
