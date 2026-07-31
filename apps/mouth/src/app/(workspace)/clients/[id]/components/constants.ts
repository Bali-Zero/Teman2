"use client";

export const STANDARD_FOLDERS: Record<string, { label: string; icon: string }> =
  {
    "00_Profile": { label: "Profile", icon: "\u{1F464}" },
    "01_Immigration": { label: "Immigration", icon: "\u{1F6C2}" },
    "02_Company": { label: "Company", icon: "\u{1F3E2}" },
    "03_Tax": { label: "Tax", icon: "\u{1F4B0}" },
    "04_Family": {
      label: "Family",
      icon: "\u{1F468}\u200D\u{1F469}\u200D\u{1F467}\u200D\u{1F466}",
    },
    "99_Misc": { label: "Misc", icon: "\u{1F4C1}" },
  };

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

// Document category colors
export const CATEGORY_COLORS: Record<string, string> = {
  visas: "bg-[var(--state-info)]/10 text-[var(--state-info)]",
  pma: "bg-[var(--bz-copper-text)]/10 text-[var(--bz-copper-text)]",
  tax: "bg-[var(--state-success)]/10 text-[var(--state-success)]",
  personal: "bg-[var(--state-warning)]/10 text-[var(--state-warning)]",
  other: "bg-[var(--bz-surface)] text-[var(--bz-text-2)]",
};

// NOTE: Visa prices MUST come from PricingTool/backend API, never hardcoded (Golden Rule).
// This map is only used as a display-name fallback -- price values are intentionally omitted.
export const VISA_DISPLAY_NAMES: Record<string, string> = {
  c1: "C1 Tourist Visa",
  c1_visa: "C1 Tourist Visa",
  d1: "D1 Tourism (Multiple Entry)",
  d12: "D12 Business Visa",
  b1: "B1 Visa on Arrival (VOA)",
  voa: "B1 Visa on Arrival (VOA)",
  voa_extension: "B1 Visa on Arrival Extension",
  e33e: "Retirement KITAS",
  e33g: "Digital Nomad KITAS",
  e28a: "Investor KITAS",
  kitas: "KITAS",
  kitap: "KITAP",
};

// Team members loaded from API — see useTeamMembers hook
