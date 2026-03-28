export default function OurJourneyLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="h-8 w-44 rounded bg-[var(--background-secondary)] animate-pulse" />
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-4 items-start">
            <div className="h-12 w-12 rounded-full bg-[var(--background-secondary)] animate-pulse flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-5 w-48 rounded bg-[var(--background-secondary)] animate-pulse" />
              <div className="h-4 w-full rounded bg-[var(--background-secondary)] animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
