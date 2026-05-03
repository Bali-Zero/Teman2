"use client";
import { useEffect } from "react";
import {
  usePrimeNexus,
  type ZoneSelection,
} from "@/contexts/PrimeNexusContext";

function ZoneCard({
  zone,
  onClear,
  slot,
}: {
  zone: ZoneSelection;
  onClear: () => void;
  slot: "A" | "B";
}) {
  const info = zone.info ?? {};
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/90">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-white/50">
          Slot {slot}
        </span>
        <button
          type="button"
          onClick={onClear}
          className="text-white/50 hover:text-white text-xs"
          aria-label={`Clear slot ${slot}`}
        >
          ✕
        </button>
      </div>
      <div className="font-semibold">{zone.name}</div>
      {zone.zoneCode && (
        <div className="text-xs text-white/60">Code: {zone.zoneCode}</div>
      )}
      <dl className="mt-2 space-y-1 text-xs">
        {Object.entries(info).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4">
            <dt className="text-white/50">{k}</dt>
            <dd className="text-white/80 truncate">{String(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Delta({ a, b }: { a: ZoneSelection; b: ZoneSelection }) {
  const infoA = a.info ?? {};
  const infoB = b.info ?? {};
  const keys = Array.from(
    new Set([...Object.keys(infoA), ...Object.keys(infoB)]),
  );
  const diffs = keys.filter(
    (k) => JSON.stringify(infoA[k]) !== JSON.stringify(infoB[k]),
  );
  return (
    <div className="rounded-xl border border-[#d4845a]/40 bg-[#d4845a]/5 p-3 text-xs">
      <div className="text-[10px] uppercase tracking-wider text-[#d4845a] mb-2">
        Delta
      </div>
      {diffs.length === 0 ? (
        <div className="text-white/60">No differences detected</div>
      ) : (
        <ul className="space-y-1">
          {diffs.map((k) => (
            <li key={k} className="flex justify-between gap-2">
              <span className="text-white/50">{k}</span>
              <span className="text-white/80">
                {String(infoA[k] ?? "—")} → {String(infoB[k] ?? "—")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PrimeCompareDrawer() {
  const ctx = usePrimeNexus();
  const { compareA, compareB, clearCompareSlot, clearCompareAll } = ctx;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && (compareA || compareB)) {
        clearCompareAll();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [compareA, compareB, clearCompareAll]);

  if (!compareA && !compareB) return null;

  return (
    <div
      role="dialog"
      aria-label="Zone comparison"
      className="absolute top-4 right-20 bottom-4 w-80 z-40 overflow-y-auto rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl p-3 space-y-3"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm uppercase tracking-wider text-white/70">
          Compare
        </h2>
        <button
          type="button"
          onClick={clearCompareAll}
          className="text-xs text-white/50 hover:text-white"
        >
          Clear all
        </button>
      </div>
      {compareA && (
        <ZoneCard
          zone={compareA}
          slot="A"
          onClear={() => clearCompareSlot("A")}
        />
      )}
      {compareB && (
        <ZoneCard
          zone={compareB}
          slot="B"
          onClear={() => clearCompareSlot("B")}
        />
      )}
      {compareA && compareB && <Delta a={compareA} b={compareB} />}
    </div>
  );
}
