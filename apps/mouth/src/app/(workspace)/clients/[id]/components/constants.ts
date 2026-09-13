"use client";

// Status badge colors — canonical 6-state vocabulary
// (mirrors backend practice_state_machine.VALID_TRANSITIONS keys).
export const STATUS_COLORS: Record<string, string> = {
  inquiry: "bg-[var(--state-info)]/10 text-[var(--state-info)]",
  waiting_documents: "bg-[var(--state-warning)]/10 text-[var(--state-warning)]",
  sending_invoice: "bg-[var(--bz-copper-text)]/10 text-[var(--bz-copper-text)]",
  on_process: "bg-[var(--state-info)]/10 text-[var(--state-info)]",
  completed: "bg-[var(--state-success)]/10 text-[var(--state-success)]",
  cancelled: "bg-[var(--state-danger)]/10 text-[var(--state-danger)]",
};

// Alert color styles
export const ALERT_COLORS: Record<string, string> = {
  green:
    "bg-[var(--state-success)]/10 text-[var(--state-success)] border-[var(--state-success)]/30",
  yellow:
    "bg-[var(--state-warning)]/10 text-[var(--state-warning)] border-[var(--state-warning)]/30",
  red: "bg-[var(--state-danger)]/10 text-[var(--state-danger)] border-[var(--state-danger)]/30",
  expired:
    "bg-[var(--state-danger)]/15 text-[var(--state-danger)] border-[var(--state-danger)]/50",
};

// Team members loaded from API — see useTeamMembers hook
