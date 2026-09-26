"use client";

import { ArrowRight, Compass, LayoutGrid, Layers } from "lucide-react";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

type KBLIDoor = "sectors" | "decoder" | "builder";

/** Every door used to point at `#search`, which is now the first thing on the
 *  page — so each door leads somewhere the search does not. The decoder and
 *  builder pages are written in Bahasa Indonesia; the door says so rather than
 *  switching language under the reader's feet. */
const DOORS = [
  {
    id: "sectors" as KBLIDoor,
    href: "#sectors",
    icon: LayoutGrid,
    label: "Browse by sector",
    subtext: "Start from an industry and narrow down to the code.",
    note: null,
  },
  {
    id: "decoder" as KBLIDoor,
    href: "/kbli/decoder",
    icon: Compass,
    label: "Not sure which code fits?",
    subtext:
      "Tell our team what your business does and we find the matching KBLI 2025 codes.",
    note: "Page in Bahasa Indonesia",
  },
  {
    id: "builder" as KBLIDoor,
    href: "/kbli/builder",
    icon: Layers,
    label: "Setting up a PT PMA?",
    subtext:
      "Our team assembles the set of KBLI 2025 codes your incorporation needs.",
    note: "Page in Bahasa Indonesia",
  },
] as const;

function handleDoorClick(door: KBLIDoor): void {
  void trackFunnelEvent("persona_door_click", {
    sessionId: getOrCreateSessionId(),
    payload: { door, source: "kbli_hero" },
  });
}

export function KBLIPersonaDoors() {
  return (
    <nav aria-label="Other ways in">
      <ul className="grid grid-cols-1 gap-1 sm:grid-cols-3 sm:gap-6">
        {DOORS.map(({ id, href, icon: Icon, label, subtext, note }) => (
          <li key={id}>
            <a
              href={href}
              onClick={() => handleDoorClick(id)}
              className="group flex h-full min-h-[44px] items-start gap-3 border-t border-[var(--kbli-text-primary)] bg-transparent px-1 pb-3 pt-3 no-underline transition-colors duration-200 hover:bg-[var(--kbli-bg-surface-hover)] focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-[var(--kbli-accent)] sm:px-2 sm:pt-4"
            >
              <Icon
                size={18}
                strokeWidth={1.8}
                aria-hidden="true"
                className="mt-0.5 shrink-0 text-[var(--kbli-text-secondary)]"
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5 text-[15px] font-semibold text-[var(--kbli-text-primary)] group-hover:text-[var(--kbli-accent)]">
                  {label}
                  <ArrowRight
                    size={14}
                    aria-hidden="true"
                    className="text-[var(--kbli-accent)] transition-transform duration-200 group-hover:translate-x-0.5"
                  />
                </span>
                <span className="mt-1 hidden text-[13px] leading-relaxed text-[var(--kbli-text-secondary)] sm:block">
                  {subtext}
                </span>
                {note ? (
                  <span className="mt-1 block text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--kbli-text-secondary)] sm:mt-2">
                    {note}
                  </span>
                ) : null}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
