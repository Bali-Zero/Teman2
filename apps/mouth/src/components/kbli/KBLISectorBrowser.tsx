"use client";

import { useEffect, useState } from "react";
import { LayoutGrid, Table2 } from "lucide-react";
import type { KBLISection } from "@/lib/kbli-types";
import { KBLISectorGrid } from "@/components/kbli/KBLISectorGrid";
import { KBLISectorTable } from "@/components/kbli/KBLISectorTable";

type View = "cards" | "table";

const STORAGE_KEY = "kbli:sector-view";

/**
 * Two ways to read the same sector list: the existing cards, or a dense
 * spreadsheet-style table. The choice is remembered per browser.
 *
 * Cards stay the default so the first paint is unchanged for everyone who
 * never touches the toggle.
 */
export function KBLISectorBrowser({ sections }: { sections: KBLISection[] }) {
  const [view, setView] = useState<View>("cards");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "table" || saved === "cards") setView(saved);
    } catch {
      // Private mode / blocked storage — cards default is fine.
    }
  }, []);

  function pick(next: View) {
    setView(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Non-fatal: the view still switches for this visit.
    }
  }

  const tab = (active: boolean) =>
    `inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-300 ${
      active
        ? "bg-white/[0.10] text-white border border-white/[0.14]"
        : "text-zinc-400 border border-transparent hover:text-white hover:bg-white/[0.06]"
    }`;

  return (
    <div>
      <div
        role="tablist"
        aria-label="Sector view"
        className="mb-4 inline-flex gap-1 rounded-full border border-white/[0.08] bg-white/[0.03] p-1 backdrop-blur-md"
      >
        <button
          type="button"
          role="tab"
          aria-selected={view === "cards"}
          onClick={() => pick("cards")}
          className={tab(view === "cards")}
        >
          <LayoutGrid size={13} /> Cards
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === "table"}
          onClick={() => pick("table")}
          className={tab(view === "table")}
        >
          <Table2 size={13} /> Table
        </button>
      </div>

      {view === "cards" ? (
        <KBLISectorGrid sections={sections} />
      ) : (
        <KBLISectorTable sections={sections} />
      )}
    </div>
  );
}
