"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { usePortalUnreadMessages } from "@/hooks/usePortalUnreadMessages";

export function PortalMessageNotice({
  compact = false,
}: {
  compact?: boolean;
}) {
  const pathname = usePathname();
  const {
    data: count,
    isError,
    isFetching,
    refetch,
  } = usePortalUnreadMessages();
  if (!compact && ["/portal/chat", "/portal/messages"].includes(pathname))
    return null;
  if (!isError && !count) return null;

  return (
    <div
      className={compact ? "p-3 border-b border-[var(--bz-border)]" : "mb-5"}
    >
      <div
        role={compact ? undefined : "status"}
        aria-live={compact ? undefined : "polite"}
        aria-atomic="true"
      >
        {count ? (
          <Link
            href="/portal/messages"
            prefetch={false}
            className="flex min-h-14 items-center gap-3 rounded-lg border-2 border-[var(--bz-accent-warm)] bg-[var(--bz-accent-warm)] p-4 font-semibold text-[var(--bz-on-warm)] focus-ring"
          >
            <MessageCircle className="h-6 w-6 shrink-0" aria-hidden="true" />
            <span className="min-w-0">
              {count} unread message{count === 1 ? "" : "s"} from your team
              <span className="block text-sm font-medium">Open messages →</span>
            </span>
          </Link>
        ) : null}
        {isError && (
          <p className="mt-2 text-sm text-[var(--tx-secondary)]">
            {count
              ? "Message count may be out of date. "
              : "Cannot check messages. "}
            <button
              type="button"
              className="underline focus-ring"
              disabled={isFetching}
              onClick={() => void refetch()}
            >
              {isFetching ? "Checking…" : "Retry"}
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
