import type { Practice } from "@/lib/api/crm/crm.types";
import { COLUMN_COLORS, getStatusColumn } from "./kanban-colors";

interface GhostCardProps {
  practice: Practice;
  onClick: () => void;
}

export function GhostCard({ practice, onClick }: GhostCardProps) {
  const currentColumn = getStatusColumn(practice.status);
  const colors = COLUMN_COLORS[currentColumn];
  const isCompleted = currentColumn === "completed";

  return (
    <div
      onClick={onClick}
      className="rounded-lg p-2.5 cursor-pointer transition-all hover:opacity-50"
      style={{
        opacity: 0.35,
        background: "rgba(255,255,255, 0.02)",
        border: "1px solid rgba(255,255,255, 0.04)",
      }}
    >
      <p className="text-xs font-medium text-[var(--bz-text-2)]">
        {practice.practice_type_code?.toUpperCase().replace(/_/g, " ") ||
          "Process"}
      </p>
      <p className="text-[10px] text-[var(--bz-text-2)]/60 mt-0.5">
        {practice.client_name || "Unknown Client"}
      </p>
      <div className="flex items-center gap-1 mt-1.5">
        <span
          className="w-[5px] h-[5px] rounded-full"
          style={{ background: colors.textColor }}
        />
        <span className="text-[8px] text-[var(--bz-text-2)]/50">
          {isCompleted ? "completata" : `ora: ${colors.label}`}
        </span>
      </div>
    </div>
  );
}
