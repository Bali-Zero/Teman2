import React from "react";
import { ArrowRight, Loader, CheckCircle, Hourglass } from "lucide-react";

/**
 * PracticeBaton — "Your Turn / Our Turn" (FASE 2, blueprint §3.4)
 *
 * The single most important UX pattern for a legal/immigration client portal:
 * every practice declares WHO HOLDS THE BATON right now. This is what turns the
 * portal from a passive archive (DeepSeek AP1 "dead portal") into a place the
 * client returns to — a tracked action with a consequence (Your Turn), or the
 * relief of "it's out of your hands" (Our Turn).
 *
 * It derives the baton from the EXISTING practice status taxonomy
 * (PROCESS_STATUS_CONFIG in process/page.tsx, mirrored from CRM workspace) —
 * no new data, no PII, pure presentation. Theme-aware via CSS vars so it reads
 * correctly on both the light client surface and the dark backoffice.
 */

export type Baton = "your_turn" | "our_turn" | "done";

/**
 * Maps each practice status to who holds the baton.
 * SSOT for the Your/Our-Turn derivation — keep in sync with the CRM status set.
 * Unknown statuses default to "our_turn" (never falsely tell the client to act).
 */
export const STATUS_TO_BATON: Record<string, Baton> = {
  // ── Your Turn: the client must do something, with a consequence ──
  payment_pending: "your_turn",
  waiting_payment: "your_turn",
  waiting_documents: "your_turn",
  quotation_sent: "your_turn", // client must review/accept the quote
  sending_invoice: "your_turn", // invoice is on the client to settle
  rejected: "your_turn", // a document was rejected → client must re-supply

  // ── Our Turn: Bali Zero is working, client can relax ──
  inquiry: "our_turn",
  in_progress: "our_turn",
  on_process: "our_turn",
  submitted_to_gov: "our_turn",
  uploaded: "our_turn", // we received it, now we verify
  pending: "our_turn",

  // ── Done: closed, no baton ──
  approved: "done",
  completed: "done",
  verified: "done",
  cancelled: "done",
};

export function statusToBaton(status: string | undefined | null): Baton {
  if (!status) return "our_turn";
  return STATUS_TO_BATON[status.toLowerCase().trim()] ?? "our_turn";
}

interface BatonStyle {
  icon: React.ElementType;
  label: string;
  sub: string;
  /** vibrant accent for your-turn, muted for our-turn, green for done */
  fg: string;
  bg: string;
  ring: string;
  /** subtle "pulse" hint that work is in progress (our_turn only) */
  pulse: boolean;
}

const BATON_STYLE: Record<Baton, BatonStyle> = {
  your_turn: {
    icon: ArrowRight,
    label: "Your turn",
    sub: "Action needed from you",
    fg: "var(--bz-accent)", // vibrant copper — demands attention
    // WS3 slice 4: tints derive from the token (was raw rgba(212,132,90,*),
    // frozen at the dark-grade copper), so the chip follows the daylight
    // copper step when slice-1 re-arms --bz-copper on operative-light.
    bg: "color-mix(in srgb, var(--bz-accent) 12%, transparent)",
    ring: "color-mix(in srgb, var(--bz-accent) 40%, transparent)",
    pulse: false,
  },
  our_turn: {
    icon: Loader,
    label: "Our turn",
    sub: "Bali Zero is working on it",
    fg: "var(--bz-text-2)", // calm, muted — client can relax
    bg: "color-mix(in srgb, var(--bz-text-2) 10%, transparent)",
    ring: "var(--bz-border)",
    pulse: true,
  },
  done: {
    icon: CheckCircle,
    label: "Done",
    sub: "Completed",
    fg: "var(--bz-green)",
    bg: "color-mix(in srgb, var(--bz-green) 12%, transparent)",
    ring: "color-mix(in srgb, var(--bz-green) 35%, transparent)",
    pulse: false,
  },
};

export interface PracticeBatonProps {
  /** raw practice status string (from PROCESS_STATUS_CONFIG / CRM) */
  status: string | undefined | null;
  /** optional override of the baton when caller already knows it */
  baton?: Baton;
  /** the concrete next action shown when it's the client's turn */
  nextActionLabel?: string;
  /** click handler / href for the CTA (your_turn only) */
  onAction?: () => void;
  /** "what's happening" line for our_turn (e.g. "Submitted to Immigration") */
  statusLabel?: string;
  /** last-activity timestamp for our_turn transparency (cures AP7 black-box) */
  lastUpdate?: string;
  className?: string;
  compact?: boolean;
}

/**
 * The baton chip + (when it's the client's turn) a clear CTA.
 * Renders nothing structural beyond a self-contained card so it can drop into
 * a dashboard hero, a practice row, or a process header.
 */
export function PracticeBaton({
  status,
  baton: batonOverride,
  nextActionLabel,
  onAction,
  statusLabel,
  lastUpdate,
  className,
  compact = false,
}: PracticeBatonProps) {
  const baton = batonOverride ?? statusToBaton(status);
  const s = BATON_STYLE[baton];
  const Icon = s.icon;

  return (
    <div
      className={`flex ${compact ? "items-center gap-2" : "flex-col gap-3"} ${className ?? ""}`}
      data-baton={baton}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wider"
          style={{
            background: s.bg,
            color: s.fg,
            boxShadow: `inset 0 0 0 1px ${s.ring}`,
          }}
        >
          <Icon
            className={`w-3.5 h-3.5 ${s.pulse ? "animate-spin [animation-duration:2.4s]" : ""}`}
            aria-hidden
          />
          {s.label}
        </span>
        {!compact && (
          <span className="text-sm" style={{ color: "var(--bz-text-2)" }}>
            {statusLabel ?? s.sub}
          </span>
        )}
      </div>

      {/* Your Turn → vibrant CTA with the concrete next action (the hard dependency) */}
      {baton === "your_turn" && nextActionLabel && (
        <button
          type="button"
          onClick={onAction}
          className="group inline-flex items-center justify-between gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-colors"
          style={{
            background: "var(--bz-accent)",
            color: "#fff",
          }}
        >
          <span>{nextActionLabel}</span>
          <ArrowRight
            className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
            aria-hidden
          />
        </button>
      )}

      {/* Our Turn → calm reassurance + last-activity timestamp (transparency, cures AP7) */}
      {baton === "our_turn" && !compact && lastUpdate && (
        <p
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--text-tertiary, var(--bz-text-3))" }}
        >
          <Hourglass className="w-3 h-3" aria-hidden />
          Last update: {lastUpdate}
        </p>
      )}
    </div>
  );
}

export default PracticeBaton;
