import Link from "next/link";
import { AlertTriangle } from "lucide-react";

interface Props {
  practiceId: string | number;
  /** Optional reason text (e.g., from assigned_to or a future blocked_reason field). */
  reason?: string | null;
}

export function BlockedStateCTA({ practiceId, reason }: Props) {
  const topic = encodeURIComponent(`practice-${practiceId}`);
  const href = `/portal/messages?topic=${topic}`;
  return (
    <div
      role="alert"
      className="rounded-lg p-4 border border-[#c94a4a]/40 bg-[#c94a4a]/10 flex items-start gap-3"
    >
      <AlertTriangle
        className="w-5 h-5 text-[#c94a4a] shrink-0 mt-0.5"
        aria-hidden
      />
      <div className="flex-1">
        <p className="text-sm text-[#c94a4a] mb-2">
          Practice blocked{reason ? `: ${reason}` : ""}.
        </p>
        <Link
          href={href}
          className="inline-block text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
        >
          Contact the team →
        </Link>
      </div>
    </div>
  );
}
