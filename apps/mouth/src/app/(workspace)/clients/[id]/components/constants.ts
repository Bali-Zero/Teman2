"use client";

// Status badge colors — canonical 6-state vocabulary
// (mirrors backend practice_state_machine.VALID_TRANSITIONS keys).
export const STATUS_COLORS: Record<string, string> = {
  inquiry: "bg-[var(--state-info)]/10 text-[var(--state-info)]",
  waiting_documents: "bg-[var(--state-warning)]/10 text-[var(--state-warning)]",
  sending_invoice: "bg-[var(--bz-copper-text)]/10 text-[var(--bz-copper-text)]",
  on_process: "bg-[var(--state-info)]/10 text-[var(--state-info)]",
  completed: "bg-[var(--state-success)]/10 text-[var(--state-success)]",
  // Terminal, like a client's "lost"/"inactive" — muted plus the word, never danger.
  cancelled: "bg-[var(--tx-secondary)]/10 text-[var(--tx-secondary)]",
};

// Alert color styles. `red`/`expired` are DATES — urgency, never ownership,
// never danger (a date is warning throughout this desk).
export const ALERT_COLORS: Record<string, string> = {
  green:
    "bg-[var(--state-success)]/10 text-[var(--state-success)] border-[var(--state-success)]/30",
  yellow:
    "bg-[var(--state-warning)]/10 text-[var(--state-warning)] border-[var(--state-warning)]/30",
  red: "bg-[var(--state-warning)]/10 text-[var(--state-warning)] border-[var(--state-warning)]/30",
  expired:
    "bg-[var(--state-warning)]/15 text-[var(--state-warning)] border-[var(--state-warning)]/50",
};

// Team members loaded from API — see useTeamMembers hook
