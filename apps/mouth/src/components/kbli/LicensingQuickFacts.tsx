// =============================================================================
// Licensing quick facts — the 4-cell grid the NON-gold KBLI page shows above
// the fold. Extracted from `app/kbli/[code]/page.tsx` so it can be RENDERED in
// a test: it was a twin of `KeyFacts` (LicensingSection.tsx) down to the
// comment, and the last three cures to that idiom reached one copy and not the
// other (cicatrix #3 / W132).
//
// HONESTY RULE: a cell states a licensing value only when the record's own
// provenance says the rows are OSS-RBA KBLI-2025 native. Otherwise the cell
// carries the declared gap — the same treatment Foreign Ownership has always
// had one cell to the left, rather than a full-weight value under a footnote.
// =============================================================================

import {
  UNVERIFIED_LICENSING_FACT,
  isLicensingVerifiedForBareClaim,
  isPmaVerdictVerified,
} from "@/lib/kbli-provenance";
import { formatPmaOwnership } from "@/lib/kbli-pma-disclosure";
import { formatTimeframe, riskLabelEn } from "@/lib/kbli-derive";
import type { KBLICode } from "@/lib/kbli-types";

export function LicensingQuickFacts({ kbli }: { kbli: KBLICode }) {
  const primary = kbli.licensing[0];
  if (!primary) return null;

  const rowsVerified = isLicensingVerifiedForBareClaim(kbli);
  const pmaVerified = isPmaVerdictVerified(kbli);
  const detached = kbli.provenance?.licensing.status === "detached";

  const cells: { label: string; value: string; muted: boolean }[] = [
    {
      label: "Risk Level",
      value: rowsVerified
        ? (riskLabelEn(primary.riskCategory) ?? primary.riskCategory)
        : UNVERIFIED_LICENSING_FACT,
      muted: !rowsVerified,
    },
    {
      label: "License Type",
      value: rowsVerified
        ? primary.licenseType || "NIB"
        : UNVERIFIED_LICENSING_FACT,
      muted: !rowsVerified,
    },
    {
      label: "Foreign Ownership",
      value: pmaVerified
        ? formatPmaOwnership(kbli.pma)
        : UNVERIFIED_LICENSING_FACT,
      muted: !pmaVerified,
    },
    {
      label: "Processing",
      value: rowsVerified
        ? (formatTimeframe(primary.timeframe) ?? "Through OSS")
        : UNVERIFIED_LICENSING_FACT,
      muted: !rowsVerified,
    },
  ];

  return (
    <section className="py-10">
      <div
        className="overflow-hidden rounded-xl border border-[var(--border)]"
        style={{ background: "var(--kbli-bg-elevated)" }}
      >
        <div
          className="grid grid-cols-2 gap-px sm:grid-cols-4"
          style={{ background: "var(--kbli-border)" }}
        >
          {cells.map((cell) => (
            <div
              key={cell.label}
              className="flex flex-col gap-1 p-4"
              style={{ background: "var(--kbli-bg-elevated)" }}
            >
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--foreground-muted)]">
                {cell.label}
              </span>
              <span
                className="text-sm font-semibold"
                style={{
                  color: cell.muted
                    ? "var(--foreground-muted)"
                    : "var(--foreground)",
                }}
              >
                {cell.value}
              </span>
            </div>
          ))}
        </div>
      </div>
      {/* The values are WITHHELD above, not footnoted — so this line says where
          they went, and WHY, in the two shapes the dataset distinguishes. */}
      {!rowsVerified && (
        <p className="mt-2 text-[11px] text-[var(--foreground-muted)]">
          {detached
            ? "⚠ This code's licensing rows were detached after a code-number collision: their source could not be verified as applying to this activity. See Regulatory Divergence below."
            : "⏳ We hold PP 28/2025 licensing rows for this code, but their KBLI-2025 crosswalk is not verified — they are listed, unverified, under Licensing Data below."}
        </p>
      )}
    </section>
  );
}
