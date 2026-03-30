import React from "react";
import { CheckCircle, Clock, AlertTriangle } from "lucide-react";

const STATUS_MAP: Record<string, { icon: React.ElementType; label: string; bg: string; color: string }> = {
  // Green group
  active:    { icon: CheckCircle,   label: 'Active',    bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  compliant: { icon: CheckCircle,   label: 'Compliant', bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  verified:  { icon: CheckCircle,   label: 'Verified',  bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  completed: { icon: CheckCircle,   label: 'Completed', bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  approved:  { icon: CheckCircle,   label: 'Approved',  bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  submitted: { icon: CheckCircle,   label: 'Submitted', bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  filed:     { icon: CheckCircle,   label: 'Filed',     bg: 'rgba(16,185,129,0.12)', color: '#34d399' },
  // Amber group
  pending:    { icon: Clock,          label: 'Pending',    bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  processing: { icon: Clock,          label: 'Processing', bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  attention:  { icon: AlertTriangle,  label: 'Attention',  bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  warning:    { icon: AlertTriangle,  label: 'Expiring',   bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  expiring:   { icon: AlertTriangle,  label: 'Expiring',   bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  received:   { icon: Clock,          label: 'Received',   bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  uploaded:   { icon: Clock,          label: 'Uploaded',   bg: 'rgba(59,130,246,0.12)', color: '#60a5fa' },
  draft:      { icon: Clock,          label: 'Draft',      bg: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
  // Red group
  expired:   { icon: AlertTriangle, label: 'Expired',   bg: 'rgba(239,68,68,0.12)', color: '#f87171' },
  overdue:   { icon: AlertTriangle, label: 'Overdue',   bg: 'rgba(239,68,68,0.12)', color: '#f87171' },
  rejected:  { icon: AlertTriangle, label: 'Rejected',  bg: 'rgba(239,68,68,0.12)', color: '#f87171' },
  cancelled: { icon: AlertTriangle, label: 'Cancelled', bg: 'rgba(239,68,68,0.12)', color: '#f87171' },
  // Default
  none: { icon: Clock, label: 'None', bg: 'rgba(255,255,255,0.05)', color: 'var(--bz-text-2)' },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const config = STATUS_MAP[status.toLowerCase()] ?? STATUS_MAP.none;
  const Icon = config.icon;

  return (
    <div
      className={`px-2.5 py-1 rounded-full flex items-center gap-1.5 text-xs font-medium ${className ?? ''}`}
      style={{ background: config.bg, color: config.color }}
    >
      <Icon className="w-3.5 h-3.5" />
      {config.label}
    </div>
  );
}
