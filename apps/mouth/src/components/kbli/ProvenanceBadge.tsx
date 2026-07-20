import { cn } from "@/lib/utils";
import type { KBLIVerificationState } from "@/lib/kbli-types";

// TRACK-P provenance badge — the code-level verification state of the risk &
// licensing data. Scoped claim by design: "verified" speaks ONLY for the
// OSS-RBA risk-row axis (the PMA layer carries its own vintage disclosure in
// the Sources & Verification panel), so the badge never overstates.
interface ProvenanceBadgeProps {
  state: KBLIVerificationState;
  size?: "sm" | "md";
}

const config: Record<
  KBLIVerificationState,
  { label: string; icon: string; tone: "ok" | "warn" | "gap"; title: string }
> = {
  verified: {
    label: "OSS-verified · KBLI 2025",
    icon: "✓",
    tone: "ok",
    title:
      "Risk & licensing rows come from the OSS-RBA KBLI-2025 catalog (vintage-native, no cross-vintage fill).",
  },
  pending: {
    label: "Crosswalk audit pending",
    icon: "⏳",
    tone: "warn",
    title:
      "This code's risk & licensing rows are not verified against a KBLI-2025-native OSS source; per-code crosswalk adjudication is pending. See Sources & Verification below for the specifics.",
  },
  not_classifiable: {
    label: "Not classifiable — divergence documented",
    icon: "❓",
    tone: "gap",
    title:
      "The licensing previously shown was detached because its source could not be verified as applying to this activity (e.g. a KBLI 2020-vs-2025 code-number collision). See the Regulatory Divergence section for the documented sources.",
  },
};

const toneClass = {
  ok: "bg-[var(--kbli-pma-open-bg)] text-[var(--kbli-pma-open)] border-[var(--kbli-pma-open)]/20",
  warn: "bg-[var(--kbli-pma-restricted-bg)] text-[var(--kbli-pma-restricted)] border-[var(--kbli-pma-restricted)]/20",
  gap: "bg-[var(--kbli-bg-elevated)] text-[var(--foreground-secondary)] border-[var(--kbli-border)]",
};

export function ProvenanceBadge({ state, size = "md" }: ProvenanceBadgeProps) {
  const c = config[state];
  if (!c) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        toneClass[c.tone],
      )}
      title={c.title}
    >
      <span aria-hidden="true">{c.icon}</span>
      <span>{c.label}</span>
    </span>
  );
}
