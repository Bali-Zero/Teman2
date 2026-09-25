"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MessageCircle } from "lucide-react";
import { useTeamPortalUnreadMessages } from "@/hooks/usePortalUnreadMessages";

export function TeamPortalMessageAlerts() {
  const { data, isError, isFetching, refetch } = useTeamPortalUnreadMessages();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const isPending = data?.total_pending !== undefined;
  const count = isPending ? data?.total_pending : data?.total_unread;
  const clients = isPending ? data?.pending_by_client : data?.by_client;

  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  if (!count && !isError) return null;

  return (
    <div ref={root} className="relative shrink-0">
      <button
        ref={trigger}
        type="button"
        aria-label={
          count
            ? isPending
              ? `${count} client${count === 1 ? "" : "s"} awaiting a reply`
              : `${count} unread client messages`
            : "Client messages unavailable"
        }
        aria-expanded={open}
        aria-controls={open ? "team-portal-messages" : undefined}
        onClick={() => setOpen(!open)}
        className="flex min-h-10 items-center gap-2 rounded-lg border border-[var(--bz-copper-text)] bg-[var(--bz-accent-warm)] px-3 text-sm font-semibold text-[var(--bz-on-warm)] focus-ring"
      >
        <MessageCircle
          size={18}
          aria-hidden="true"
          className={
            isPending && count
              ? "motion-safe:animate-pulse motion-reduce:animate-none"
              : undefined
          }
        />
        <span role="status" aria-live="polite">
          {count ? `${count} ${isPending ? "to reply" : "new"}` : "!"}
        </span>
        <span className="hidden lg:inline">
          {isPending ? "client conversations" : "client messages"}
        </span>
      </button>
      {open && (
        <div
          id="team-portal-messages"
          className="fixed inset-x-3 top-14 z-50 mt-2 sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:w-80 max-h-[70vh] overflow-y-auto rounded-xl border border-[var(--bz-border)] bg-[var(--surface-overlay)] p-3 shadow-xl text-[var(--tx-primary)]"
        >
          <h2 className="font-semibold">
            {isPending ? "Awaiting your reply" : "Client messages"}
          </h2>
          <p className="mb-2 text-xs text-[var(--tx-secondary)]">
            {isPending
              ? "The reminder stays until you reply."
              : "Open a conversation to read and reply."}
          </p>
          {isError && (
            <p role="alert" className="my-2 text-sm">
              {data
                ? "Message count may be out of date. "
                : "Cannot check messages. "}
              <button
                type="button"
                className="underline focus-ring"
                disabled={isFetching}
                onClick={() => void refetch()}
              >
                Retry
              </button>
            </p>
          )}
          {clients?.map((client) => (
            <Link
              key={client.client_id}
              href={`/clients/${client.client_id}?tab=overview#portal-messages`}
              prefetch={false}
              onClick={() => setOpen(false)}
              className="flex min-h-12 items-center justify-between gap-3 border-t border-[var(--bz-border)] py-3 text-sm focus-ring"
            >
              <span className="min-w-0 break-words">{client.client_name}</span>
              <span className="shrink-0 font-semibold">
                {isPending
                  ? "Reply →"
                  : `${"unread_count" in client ? client.unread_count : 0} unread →`}
              </span>
            </Link>
          ))}
          {data &&
            (isPending
              ? (data.total_pending ?? 0) > (clients?.length ?? 0)
              : data.total_unread >
                data.by_client.reduce(
                  (sum, client) => sum + client.unread_count,
                  0,
                )) && (
              <p className="text-xs text-[var(--tx-secondary)]">
                {isPending
                  ? "Showing the 10 oldest conversations. More appear as you reply."
                  : "Showing the 10 conversations with most unread messages. More appear as these are read."}
              </p>
            )}
        </div>
      )}
    </div>
  );
}
