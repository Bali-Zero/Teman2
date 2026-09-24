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
  const count = data?.total_unread;

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
            ? `${count} unread client messages`
            : "Client messages unavailable"
        }
        aria-expanded={open}
        aria-controls={open ? "team-portal-messages" : undefined}
        onClick={() => setOpen(!open)}
        className="flex min-h-10 items-center gap-2 rounded-lg border border-[var(--bz-copper-text)] bg-[var(--bz-accent-warm)] px-3 text-sm font-semibold text-[var(--bz-on-warm)] focus-ring"
      >
        <MessageCircle size={18} aria-hidden="true" />
        <span role="status" aria-live="polite">
          {count ? `${count} new` : "!"}
        </span>
        <span className="hidden lg:inline">client messages</span>
      </button>
      {open && (
        <div
          id="team-portal-messages"
          className="fixed inset-x-3 top-14 z-50 mt-2 sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:w-80 max-h-[70vh] overflow-y-auto rounded-xl border border-[var(--bz-border)] bg-[var(--surface-overlay)] p-3 shadow-xl text-[var(--tx-primary)]"
        >
          <h2 className="font-semibold">Client messages</h2>
          <p className="mb-2 text-xs text-[var(--tx-secondary)]">
            Open a conversation to read and reply.
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
          {data?.by_client.map((client) => (
            <Link
              key={client.client_id}
              href={`/clients/${client.client_id}?tab=overview#portal-messages`}
              prefetch={false}
              onClick={() => setOpen(false)}
              className="flex min-h-12 items-center justify-between gap-3 border-t border-[var(--bz-border)] py-3 text-sm focus-ring"
            >
              <span className="min-w-0 break-words">{client.client_name}</span>
              <span className="shrink-0 font-semibold">
                {client.unread_count} unread →
              </span>
            </Link>
          ))}
          {data &&
            data.total_unread >
              data.by_client.reduce(
                (sum, client) => sum + client.unread_count,
                0,
              ) && (
              <p className="text-xs text-[var(--tx-secondary)]">
                Showing the 10 conversations with most unread messages. More
                appear as these are read.
              </p>
            )}
        </div>
      )}
    </div>
  );
}
