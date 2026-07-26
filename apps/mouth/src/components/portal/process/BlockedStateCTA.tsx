import Link from "next/link";
import { AlertTriangle } from "lucide-react";

interface Props {
  practiceId: string | number;
  /** Optional reason text (e.g., from assigned_to or a future blocked_reason field). */
  reason?: string | null;
}

// WS3 slice 4 (GARUDA Day Edition, 2026-07-24): blocked state reads
// --state-danger (WS2 operative-light AA override #b91c1c = 5.74:1 on
// paper — was raw #c94a4a); the contact link reads --bz-copper-text with
// the slice-1 fallback (was raw #d4845a = 2.57:1 on paper, below AA).
export function BlockedStateCTA({ practiceId, reason }: Props) {
  const topic = encodeURIComponent(`practice-${practiceId}`);
  const href = `/portal/messages?topic=${topic}`;
  return (
    <div
      role="alert"
      className="rounded-lg p-4 border flex items-start gap-3"
      style={{
        borderColor: "color-mix(in srgb, var(--state-danger) 40%, transparent)",
        background: "color-mix(in srgb, var(--state-danger) 8%, transparent)",
      }}
    >
      <AlertTriangle
        className="w-5 h-5 shrink-0 mt-0.5"
        style={{ color: "var(--state-danger)" }}
        aria-hidden
      />
      <div className="flex-1">
        <p className="text-sm mb-2" style={{ color: "var(--state-danger)" }}>
          Practice blocked{reason ? `: ${reason}` : ""}.
        </p>
        <Link
          href={href}
          className="inline-block text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] hover:underline"
        >
          Contact the team →
        </Link>
      </div>
    </div>
  );
}
