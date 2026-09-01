"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpDown } from "lucide-react";
import type { KBLISection } from "@/lib/kbli-types";

type SortKey = "id" | "nameEn" | "codeCount";
type SortDir = "asc" | "desc";

/**
 * Spreadsheet-style view of the KBLI sections.
 * Same data as KBLISectorGrid, denser and sortable — for people who
 * want to scan/compare rather than browse cards.
 */
export function KBLISectorTable({ sections }: { sections: KBLISection[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("codeCount");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const maxCount = Math.max(...sections.map((s) => s.codeCount), 1);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      // Counts read best highest-first; text reads best A→Z.
      setSortDir(key === "codeCount" ? "desc" : "asc");
    }
  }

  const rows = [...sections].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortKey === "codeCount") return (a.codeCount - b.codeCount) * dir;
    return String(a[sortKey]).localeCompare(String(b[sortKey])) * dir;
  });

  const headCell =
    "px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400";
  const sortBtn =
    "inline-flex items-center gap-1 transition-colors hover:text-accent-warm";

  return (
    <div className="overflow-x-auto rounded-2xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
      <table className="w-full min-w-[560px] border-collapse text-left">
        <caption className="sr-only">
          KBLI 2025 sectors, sortable by section, name, or number of codes
        </caption>
        <thead>
          <tr className="border-b border-white/[0.08]">
            <th scope="col" className={headCell}>
              <button
                type="button"
                onClick={() => toggleSort("id")}
                className={sortBtn}
                aria-label="Sort by section letter"
              >
                Section <ArrowUpDown size={12} />
              </button>
            </th>
            <th scope="col" className={headCell}>
              <button
                type="button"
                onClick={() => toggleSort("nameEn")}
                className={sortBtn}
                aria-label="Sort by sector name"
              >
                Sector <ArrowUpDown size={12} />
              </button>
            </th>
            <th scope="col" className={`${headCell} text-right`}>
              <button
                type="button"
                onClick={() => toggleSort("codeCount")}
                className={sortBtn}
                aria-label="Sort by number of codes"
              >
                Codes <ArrowUpDown size={12} />
              </button>
            </th>
            <th scope="col" className={`${headCell} hidden sm:table-cell`}>
              Share
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const barPct = Math.max(
              2,
              Math.round((s.codeCount / maxCount) * 100),
            );
            return (
              <tr
                key={s.id}
                className="border-b border-white/[0.05] last:border-0 transition-colors hover:bg-white/[0.05]"
              >
                <td className="px-3 py-2.5">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-accent-warm">
                    {s.id}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <Link
                    href={`/kbli/sectors/${s.id}`}
                    className="text-sm font-medium text-white transition-colors hover:text-accent-warm hover:underline underline-offset-2"
                  >
                    {s.nameEn}
                  </Link>
                </td>
                <td className="px-3 py-2.5 text-right text-sm tabular-nums text-zinc-300">
                  {s.codeCount}
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  <div className="h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-[#d4845a] via-[#a855f7] to-[#3b82f6] opacity-70"
                      style={{ width: `${barPct}%` }}
                    />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
