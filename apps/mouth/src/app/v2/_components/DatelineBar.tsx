"use client";

/**
 * DatelineBar — sticky editorial dateline strip.
 *
 * "The Dispatch" direction (Wave 3): the dateline that used to live as a
 * static line inside HeroBlueprint's copy overlay now persists as a thin
 * bar under the fixed NavShell (h-14 = 56px) as the visitor scrolls —
 * a quiet editorial signature, not a second nav.
 *
 * Month is computed client-side (`toLocaleString`) so the dateline never
 * goes stale — no hardcoded "April 2026" to forget about next month.
 *
 * Client Component: needs `Date` at render time. Tiny — no state, no
 * effect, just a formatted string, so the JS cost is a handful of bytes.
 */
export function DatelineBar() {
  const monthYear = new Date().toLocaleString("en-US", {
    month: "long",
    year: "numeric",
  });

  return (
    <div
      className="sticky hidden sm:block"
      style={{
        top: 56, // below the fixed h-14 NavShell
        zIndex: 200, // under NavShell's z-300, above page content
        background: "var(--nav-bg, #1e3863)",
        borderBottom: "1px solid rgba(255,255,255,0.12)",
      }}
    >
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 lg:px-16 py-1.5">
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.28em]"
          style={{ color: "rgba(255,255,255,0.55)" }}
        >
          Bali Zero · Dispatch · {monthYear} · Kerobokan
        </span>
      </div>
    </div>
  );
}
