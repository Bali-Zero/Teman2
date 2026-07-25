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
 * tint of its own AA step — on dark the mix reproduces the previous
 * rgba(16,185,129,0.12)-style tints exactly (state primitives ARE those
 * hexes). No hardcoded colors.
 */

type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_STYLES: Record<StatusTone, { bg: string; color: string }> = {
  success: {
    bg: "color-mix(in srgb, var(--state-success) 12%, transparent)",
    color: "var(--state-success)",
  },
  warning: {
    bg: "color-mix(in srgb, var(--state-warning) 12%, transparent)",
    color: "var(--state-warning)",
  },
  danger: {
    bg: "color-mix(in srgb, var(--state-danger) 12%, transparent)",
    color: "var(--state-danger)",
  },
  info: {
    bg: "color-mix(in srgb, var(--state-info) 12%, transparent)",
    color: "var(--state-info)",
  },
  neutral: {
    bg: "var(--bz-border)",
    color: "var(--bz-text-2)",
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
  // Amber group
  applied: { icon: Clock, label: "Applied", tone: "warning" },
  pending: { icon: Clock, label: "Pending", tone: "warning" },
  processing: { icon: Clock, label: "Processing", tone: "warning" },
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
  const Icon = config.icon;

  return (
    <div
      className={`px-2.5 py-1 rounded-full flex items-center gap-1.5 text-xs font-medium ${className ?? ""}`}
      style={{ background: tone.bg, color: tone.color }}
    >
      <Icon className="w-3.5 h-3.5" />
      {config.label}
    </div>
  );
}
