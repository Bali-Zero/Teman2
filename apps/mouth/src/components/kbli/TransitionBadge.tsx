import type { KBLIMappingStatus } from "@/lib/kbli-types";

const LABELS: Record<KBLIMappingStatus, string> = {
  MATCH_LANGSUNG: "Direct Match",
  CODICE_RINUMERATO: "Renumbered",
  MATCH_CON_AGGREGAZIONE: "Aggregated",
  BPS_ONLY: "New in 2025",
  "": "",
};

const COLORS: Record<KBLIMappingStatus, string> = {
  MATCH_LANGSUNG: "bg-green-50 text-green-700 border-green-200",
  CODICE_RINUMERATO: "bg-blue-50 text-blue-700 border-blue-200",
  MATCH_CON_AGGREGAZIONE: "bg-amber-50 text-amber-700 border-amber-200",
  BPS_ONLY: "bg-purple-50 text-purple-700 border-purple-200",
  "": "",
};

interface TransitionBadgeProps {
  status: KBLIMappingStatus;
}

export function TransitionBadge({ status }: TransitionBadgeProps) {
  if (!status) return null;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${COLORS[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
