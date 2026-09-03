import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { KBLISection } from "@/lib/kbli-types";

/**
 * In-panel navigation across the 22 sections.
 *
 * Every entry is a real `<Link>` to `/kbli/sectors/<id>`, so it is intercepted
 * exactly like the card that opened the panel: the section swaps inside the
 * open panel, no close/reopen, one history entry per hop, and the same link
 * still works as a plain page navigation when JS is off.
 */
export function KBLISectorStrip({
  sections,
  activeId,
}: {
  sections: KBLISection[];
  activeId: string;
}) {
  const index = sections.findIndex((s) => s.id === activeId);
  const prev = index > 0 ? sections[index - 1] : null;
  const next =
    index >= 0 && index < sections.length - 1 ? sections[index + 1] : null;

  const arrow =
    "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/[0.08] " +
    "bg-white/[0.03] text-zinc-400 transition-all hover:bg-white/[0.08] hover:text-white " +
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)]";

  return (
    <div className="flex items-center gap-2 border-b border-white/[0.06] px-5 py-3">
      {prev ? (
        <Link
          href={`/kbli/sectors/${prev.id}`}
          className={arrow}
          aria-label={`Previous section: ${prev.id} — ${prev.nameEn}`}
          data-testid="kbli-panel-prev"
        >
          <ChevronLeft size={15} />
        </Link>
      ) : (
        <span className={`${arrow} pointer-events-none opacity-30`} aria-hidden>
          <ChevronLeft size={15} />
        </span>
      )}

      <nav
        aria-label="KBLI sections"
        className="flex min-w-0 flex-1 gap-1 overflow-x-auto scroll-smooth [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        data-testid="kbli-panel-strip"
      >
        {sections.map((s) => {
          const active = s.id === activeId;
          return (
            <Link
              key={s.id}
              href={`/kbli/sectors/${s.id}`}
              aria-current={active ? "page" : undefined}
              title={`${s.nameEn} — ${s.codeCount} codes`}
              className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold
                          transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)] ${
                            active
                              ? "border border-[var(--kbli-accent)]/50 bg-[var(--kbli-accent)]/15 text-[var(--kbli-accent)]"
                              : "border border-transparent text-zinc-500 hover:bg-white/[0.06] hover:text-white"
                          }`}
            >
              {s.id}
            </Link>
          );
        })}
      </nav>

      {next ? (
        <Link
          href={`/kbli/sectors/${next.id}`}
          className={arrow}
          aria-label={`Next section: ${next.id} — ${next.nameEn}`}
          data-testid="kbli-panel-next"
        >
          <ChevronRight size={15} />
        </Link>
      ) : (
        <span className={`${arrow} pointer-events-none opacity-30`} aria-hidden>
          <ChevronRight size={15} />
        </span>
      )}
    </div>
  );
}
