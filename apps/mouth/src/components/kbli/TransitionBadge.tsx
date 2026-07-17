import type { KBLIMappingStatus } from "@/lib/kbli-types";

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
  status: KBLIMappingStatus;
}

export function TransitionBadge({ status }: TransitionBadgeProps) {
  if (!status) return null;
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
      {LABELS[status]}
    </span>
  );
}
