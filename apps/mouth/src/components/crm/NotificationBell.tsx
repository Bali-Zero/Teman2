"use client";

/**
 * NotificationBell — CRM header notification bell component.
 *
 * Shows unread count badge. On click opens a dropdown with portal_document_upload
 * alerts and expiry alerts from useCrmNotifications.
 *
 * Used in: apps/mouth/src/components/workspace/Header.tsx
 */

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Bell, CheckCheck, Upload, Calendar } from "lucide-react";
import { useCrmNotifications } from "@/hooks/useCrmNotifications";

interface NotificationBellProps {
  /** Polling interval in ms (default 3 min) */
  refreshInterval?: number;
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  portal_upload: <Upload size={11} />,
  expiry: <Calendar size={11} />,
};

export function NotificationBell({
  refreshInterval = 3 * 60 * 1000,
}: NotificationBellProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const { notifications, unreadCount, isLoading, markAsRead, markAllAsRead } =
    useCrmNotifications({ autoRefresh: true, refreshInterval });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const handleClick = (id: string, actionUrl?: string) => {
    markAsRead(id);
    if (actionUrl) {
      setOpen(false);
      router.push(actionUrl);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-1.5 rounded-lg transition-colors"
        style={{ color: "var(--bz-text-2)" }}
        aria-label={`${unreadCount} unread notifications`}
      >
        <Bell size={15} />
        {unreadCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] text-[8px] font-bold rounded-full flex items-center justify-center text-white"
            style={{ background: "var(--bz-accent)" }}
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} role="presentation" />
          <div
            className="absolute right-0 top-full mt-3 w-80 z-50 rounded-xl shadow-2xl border max-h-[420px] flex flex-col overflow-hidden"
            style={{
              background: "rgba(32, 32, 36, 0.90)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              borderColor: "var(--bz-border)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between p-3 border-b"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <span
                className="text-[12px] font-semibold"
                style={{ color: "var(--bz-text-1)" }}
              >
                Notifications{unreadCount > 0 && ` (${unreadCount})`}
              </span>
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md transition-colors hover:opacity-80"
                  style={{ color: "var(--bz-accent)" }}
                >
                  <CheckCheck size={12} />
                  Mark all read
                </button>
              )}
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto">
              {isLoading ? (
                <div className="p-4 space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-12 rounded-lg animate-pulse"
                      style={{ background: "rgba(255,255,255,0.04)" }}
                    />
                  ))}
                </div>
              ) : notifications.length === 0 ? (
                <div
                  className="p-6 text-[11px] text-center"
                  style={{ color: "var(--bz-text-3)" }}
                >
                  No notifications
                </div>
              ) : (
                <div className="p-1.5">
                  {notifications.slice(0, 12).map((n) => (
                    <button
                      key={n.id}
                      onClick={() => handleClick(n.id, n.actionUrl)}
                      className="w-full text-left p-2.5 rounded-lg transition-colors flex gap-2.5 items-start hover:bg-white/[0.04]"
                    >
                      <span
                        className="flex-shrink-0 mt-0.5 opacity-60"
                        style={{ color: "var(--bz-accent)" }}
                      >
                        {TYPE_ICON[n.type] ?? <Bell size={11} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div
                          className="text-[11px] font-medium truncate"
                          style={{ color: "var(--bz-text-1)" }}
                        >
                          {n.title}
                        </div>
                        <div
                          className="text-[10px] mt-0.5 truncate"
                          style={{ color: "var(--bz-text-3)" }}
                        >
                          {n.message}
                        </div>
                      </div>
                      {!n.read && (
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5"
                          style={{ background: "var(--bz-accent)" }}
                        />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
              <div
                className="border-t p-2"
                style={{ borderColor: "var(--bz-border)" }}
              >
                <button
                  onClick={() => {
                    setOpen(false);
                    router.push("/notifications");
                  }}
                  className="w-full text-center text-[10px] py-1.5 rounded-md transition-colors hover:bg-white/[0.04]"
                  style={{ color: "var(--bz-accent)" }}
                >
                  View all notifications
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
