// WS3 slice 4 (GARUDA Day Edition, 2026-07-24): skeleton pulses read the
// glass tokens (dark: white highlights; operative-light: dark-on-paper
// highlights) — was bg-white/10 + bg-white/5, invisible on paper.
export function TimelineSkeleton({ count = 3 }: { count?: number }) {
  return (
    <ul aria-label="Loading timeline" className="list-none p-0 m-0">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="flex gap-4 pb-6">
          <div className="flex flex-col items-center">
            <span
              className="w-3 h-3 rounded-full animate-pulse"
              style={{ background: "var(--glass-highlight)" }}
            />
            {i < count - 1 && (
              <span
                className="flex-1 w-px my-1"
                style={{ background: "var(--glass-rim)" }}
              />
            )}
          </div>
          <div className="flex-1 space-y-2">
            <div
              className="h-4 w-1/2 animate-pulse rounded"
              style={{ background: "var(--glass-highlight)" }}
            />
            <div
              className="h-3 w-1/3 animate-pulse rounded"
              style={{ background: "var(--glass-rim)" }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
