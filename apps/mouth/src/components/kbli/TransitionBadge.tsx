import type { KBLIMappingStatus, KBLITransition } from "@/lib/kbli-types";

const LABELS: Record<KBLIMappingStatus, string> = {
  MATCH_LANGSUNG: "Direct Match",
  CODICE_RINUMERATO: "Renumbered",
  MATCH_CON_AGGREGAZIONE: "Aggregated",
  BPS_ONLY: "New in 2025",
  "": "",
};

// Dark-theme tokens (src/styles/kbli-theme.css), NOT hardcoded light-mode
// Tailwind classes (bg-green-50 …) — those rendered as pale chips on the dark
// hero, out of step with every sibling KBLI badge (Risk/PMA/Bali/Provenance).
// bg + border are alpha-composited from the same token via color-mix, mirroring
// KBLIProvenancePanel. Four distinct hues, one per mapping status.
const COLORS: Record<KBLIMappingStatus, string> = {
  MATCH_LANGSUNG: "var(--kbli-pma-open)", // #5ec490 green — clean 1:1 match
  CODICE_RINUMERATO: "var(--kbli-accent2)", // #8b9cf7 blue — renumbered
  MATCH_CON_AGGREGAZIONE: "var(--kbli-amber)", // #e8a849 amber — merged
  BPS_ONLY: "var(--kbli-accent)", // #d4845a terracotta — brand-new code
  "": "",
};

interface TransitionBadgeProps {
  transition: Pick<KBLITransition, "mappingStatus" | "bpsCrosswalk">;
}

export function TransitionBadge({ transition }: TransitionBadgeProps) {
  const status = transition.mappingStatus;
  // mappingStatus was derived from the legacy PP28 matching layer on every
  // PP28-only code. Without an authoritative BPS ancestor it would place a
  // "Direct Match"/"Renumbered" claim beside the BPS-gap disclosure.
  if ((transition.bpsCrosswalk?.codes.length ?? 0) === 0) return null;
  if (!status) return null;
  const label = LABELS[status];
  // `BPS_ONLY` is legacy mapping metadata, not proof that the activity is new.
  // When official BPS ancestors exist (03300 has sixteen), rendering "New in
  // 2025" would contradict the adjacent authoritative crosswalk card.
  if (label === "New in 2025") return null;
  const color = COLORS[status];
  return (
    <span
      className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium"
      style={{
        color,
        borderColor: `color-mix(in srgb, ${color} 30%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
      }}
    >
      {label}
    </span>
  );
}
