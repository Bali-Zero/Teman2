"use client";

interface Props {
  opener?: string;
  suggestions?: string[];
}

export function ZantaraChat({ opener, suggestions }: Props) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-4">
      {opener && <p className="text-sm text-[var(--foreground-muted)] mb-3">{opener}</p>}
      {suggestions && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((s, i) => (
            <span key={i} className="text-xs px-2 py-1 rounded-full bg-[var(--accent)]/10">
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
