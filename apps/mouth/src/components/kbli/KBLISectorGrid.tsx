import Link from "next/link";
import type { KBLISection } from "@/lib/kbli-types";

export function KBLISectorGrid({ sections }: { sections: KBLISection[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {sections.map((s) => (
        <Link
          key={s.id}
          href={`/kbli/sectors/${s.id}`}
          className="group relative flex flex-col p-5 rounded-2xl border border-[var(--border)] bg-[var(--kbli-bg-card)]
                     transition-all duration-300 hover:border-[var(--kbli-accent)]/40 hover:bg-[var(--kbli-bg-card-hover)]
                     hover:shadow-xl hover:shadow-[var(--kbli-accent)]/5"
        >
          {/* Icon */}
          <div className="text-3xl mb-4 transform transition-transform group-hover:scale-110 duration-300">
            {s.icon}
          </div>

          {/* Letter Label */}
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--kbli-accent)] mb-1 opacity-80">
            Section {s.id}
          </div>

          {/* Name */}
          <h3 className="text-sm font-semibold text-[var(--foreground)] group-hover:text-[var(--kbli-accent)] transition-colors leading-tight mb-2">
            {s.nameEn}
          </h3>

          {/* Count */}
          <div className="mt-auto pt-2 text-[11px] text-[var(--foreground-muted)] flex items-center gap-2">
            <span className="font-mono">{s.codeCount}</span>
            <span>codes</span>
          </div>

          {/* Hover Arrow */}
          <div className="absolute bottom-5 right-5 text-[var(--foreground-muted)] opacity-0 transform translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all">
            →
          </div>
        </Link>
      ))}
    </div>
  );
}
