import React from "react";
import { CheckCircle, Clock, AlertTriangle } from "lucide-react";

/**
 * StatusBadge — shared portal status pill.
 *
 * WS3 (GARUDA Day Edition, 2026-07-24): state colors read the semantic
 * --state-* tokens (WS2 operative-light AA overrides: success 4.80:1,
 * warning 4.78:1, danger 5.74:1, info 5.94:1 on paper) instead of
 * hardcoded neon hexes (#34d399 / #fbbf24 / #f87171 / #60a5fa). Badge
 * backgrounds are color-mix tints OF the state token, so each theme gets a
 * tint of its own AA step. No hardcoded colors.
 *
 * R19 (concept F): the pill is outlined — a hairline of the same state token
 * at 35%, a 6px leading dot in currentColor and an uppercase 10px label. The
 * meaning still lives in the token, not here: the four R19 meanings (forest
 * done / slate moving / copper needs-you / muted waiting) are what the theme
 * layer aliases --state-success / --state-info / --state-warning +
 * --state-danger / --tx-secondary to.
 */

type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_STYLES: Record<
  StatusTone,
  { bg: string; color: string; border: string }
> = {
  success: {
    bg: "color-mix(in srgb, var(--state-success) 7%, transparent)",
    color: "var(--state-success)",
    border: "color-mix(in srgb, var(--state-success) 35%, transparent)",
  },
  warning: {
    bg: "color-mix(in srgb, var(--state-warning) 7%, transparent)",
    color: "var(--state-warning)",
    border: "color-mix(in srgb, var(--state-warning) 35%, transparent)",
  },
  danger: {
    bg: "color-mix(in srgb, var(--state-danger) 7%, transparent)",
    color: "var(--state-danger)",
    border: "color-mix(in srgb, var(--state-danger) 35%, transparent)",
  },
  info: {
    bg: "color-mix(in srgb, var(--state-info) 7%, transparent)",
    color: "var(--state-info)",
    border: "color-mix(in srgb, var(--state-info) 35%, transparent)",
  },
  neutral: {
    bg: "color-mix(in srgb, var(--tx-secondary) 5%, transparent)",
    color: "var(--tx-secondary)",
    border: "var(--bz-border)",
  },
};

const STATUS_MAP: Record<
  string,
  { icon: React.ElementType; label: string; tone: StatusTone }
> = {
  // Green group
  ok: { icon: CheckCircle, label: "OK", tone: "success" },
  active: { icon: CheckCircle, label: "Active", tone: "success" },
  compliant: { icon: CheckCircle, label: "Compliant", tone: "success" },
  verified: { icon: CheckCircle, label: "Verified", tone: "success" },
  completed: { icon: CheckCircle, label: "Completed", tone: "success" },
  approved: { icon: CheckCircle, label: "Approved", tone: "success" },
  submitted: { icon: CheckCircle, label: "Submitted", tone: "success" },
  filed: { icon: CheckCircle, label: "Filed", tone: "success" },
  paid: { icon: CheckCircle, label: "Paid", tone: "success" },
  unpaid: { icon: Clock, label: "Unpaid", tone: "warning" },
  partial: { icon: Clock, label: "Partially paid", tone: "warning" },
  // Amber group
  applied: { icon: Clock, label: "Applied", tone: "warning" },
  pending: { icon: Clock, label: "Pending", tone: "warning" },
  // R19: work that is ours and moving reads slate (info), not needs-you.
  processing: { icon: Clock, label: "Processing", tone: "info" },
  attention: { icon: AlertTriangle, label: "Attention", tone: "warning" },
  warning: { icon: AlertTriangle, label: "Expiring", tone: "warning" },
  expiring: { icon: AlertTriangle, label: "Expiring", tone: "warning" },
  expiring_soon: {
    icon: AlertTriangle,
    label: "Expiring Soon",
    tone: "warning",
  },
  received: { icon: Clock, label: "Received", tone: "warning" },
  upcoming: { icon: Clock, label: "Upcoming", tone: "warning" },
  uploaded: { icon: Clock, label: "Uploaded", tone: "info" },
  draft: { icon: Clock, label: "Draft", tone: "warning" },
  // Red group
  expired: { icon: AlertTriangle, label: "Expired", tone: "danger" },
  critical: { icon: AlertTriangle, label: "Critical", tone: "danger" },
  overdue: { icon: AlertTriangle, label: "Overdue", tone: "danger" },
  rejected: { icon: AlertTriangle, label: "Rejected", tone: "danger" },
  cancelled: { icon: AlertTriangle, label: "Cancelled", tone: "danger" },
  // Partner program vocabulary (WS3 final slice, 2026-07-26): commission +
  // partner onboarding statuses from lib/api/partners/partners.ts. Additive —
  // existing keys unchanged, so other consumers render identically.
  accrued: { icon: Clock, label: "Accrued", tone: "warning" },
  pending_approval: {
    icon: Clock,
    label: "Pending Approval",
    tone: "warning",
  },
  ready_to_pay: { icon: Clock, label: "Ready to Pay", tone: "info" },
  clawback_pending: {
    icon: AlertTriangle,
    label: "Clawback Pending",
    tone: "warning",
  },
  clawed_back: { icon: AlertTriangle, label: "Clawed Back", tone: "danger" },
  inactive: { icon: AlertTriangle, label: "Inactive", tone: "danger" },
  offset_applied: { icon: CheckCircle, label: "Offset Applied", tone: "info" },
  waived: { icon: CheckCircle, label: "Waived", tone: "neutral" },
  repaid: { icon: CheckCircle, label: "Repaid", tone: "neutral" },
  // Default
  none: { icon: Clock, label: "None", tone: "neutral" },
};

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const config = STATUS_MAP[status.toLowerCase()] ?? STATUS_MAP.none;
  const tone = TONE_STYLES[config.tone];

  return (
    <div
      className={`inline-flex items-center gap-[7px] h-6 pl-[9px] pr-2.5 rounded-full border text-[10px] font-[650] uppercase tracking-[.12em] whitespace-nowrap ${className ?? ""}`}
      style={{
        background: tone.bg,
        color: tone.color,
        borderColor: tone.border,
      }}
    >
      <span
        aria-hidden="true"
        className="w-1.5 h-1.5 rounded-full bg-current shrink-0"
      />
      {config.label}
    </div>
  );
}
