"use client";

import React, { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Menu, X, MessageCircle, CheckCheck, Search } from "lucide-react";
import { routeTitles } from "@/types/navigation";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

import { TeamPortalMessageAlerts } from "./TeamPortalMessageAlerts";
import { useCrmNotifications } from "@/hooks/useCrmNotifications";

interface HeaderProps {
  userName: string;
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  whatsappUnread?: number;
  mobileMenuToggleRef?: React.RefObject<HTMLButtonElement | null>;
}

/**
 * Severity as the four meanings, never as a red. `critical` used to read
 * `var(--bz-red, #e45c5c)`: on kita the token itself already re-aliases to
 * copper, but the literal FALLBACK would still paint #e45c5c on any surface
 * that had not declared the token — a red hiding behind a comma. Critical and
 * high both mean "you are the next actor", so both take copper and the rank
 * is carried by the word and the ordinal, not by a second hue.
 */
const SEVERITY_DOT: Record<string, string> = {
  critical: "var(--bz-copper-text)",
  high: "var(--bz-copper-text)",
  medium: "var(--state-warning)",
  low: "var(--tx-secondary)",
};

export function Header({
  userName,
  onMobileMenuToggle,
  isMobileMenuOpen,
  whatsappUnread = 0,
  mobileMenuToggleRef,
}: HeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [showNotifications, setShowNotifications] = useState(false);

  const {
    notifications,
    unreadCount,
    isLoading: notifLoading,
    markAsRead,
    markAllAsRead,
  } = useCrmNotifications({
    autoRefresh: true,
    refreshInterval: 3 * 60 * 1000,
  });

  // Get page title from pathname
  const getPageTitle = () => {
    if (!pathname) return "Dashboard";
    if (routeTitles[pathname]) return routeTitles[pathname];
    for (const [route, title] of Object.entries(routeTitles)) {
      if (pathname.startsWith(route) && route !== "/") return title;
    }
    return "Dashboard";
  };

  // Format current date
  const formatDate = () => {
    const options: Intl.DateTimeFormatOptions = {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    };
    return new Date().toLocaleDateString("en-US", options);
  };

  useEffect(() => {
    if (!showNotifications) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowNotifications(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [showNotifications]);

  const handleNotificationClick = (actionUrl?: string, id?: string) => {
    if (id) markAsRead(id);
    if (actionUrl) {
      setShowNotifications(false);
      router.push(actionUrl);
    }
  };

  return (
    <header
      className="sticky top-0 z-30 w-full border-b transition-colors"
      style={{
        height: "var(--bz-header-height, 48px)",
        background: "var(--nav-bg)",
        borderColor: "var(--bz-border)",
      }}
    >
      <div className="flex items-center h-full px-5 gap-3">
        {/* Mobile menu */}
        <button
          ref={mobileMenuToggleRef}
          onClick={onMobileMenuToggle}
          className="md:hidden p-1.5 rounded-lg transition-colors hover:bg-[var(--surface-raised)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bz-base)]"
          style={{ color: "var(--bz-text-1)" }}
          aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
          aria-expanded={isMobileMenuOpen}
          aria-controls="workspace-mobile-nav"
        >
          {isMobileMenuOpen ? <X size={16} /> : <Menu size={16} />}
        </button>

        {/* Greeting + Page context (presentational — real h1 lives in <main>) */}
        <div className="flex items-baseline gap-2 min-w-0">
          <span
            className="text-[13px] font-medium truncate"
            style={{ color: "var(--bz-text-1)" }}
          >
            {userName ? `${userName}, ayo!` : getPageTitle()}
          </span>
        </div>

        {/*
          The visible front door. KitaCommandPalette already binds Cmd/Ctrl+K
          on `window`; this is the same door made VISIBLE, so a staff member
          who does not know the shortcut can still find it. It dispatches that
          existing event rather than taking a new prop, so no handler, no
          signature and no wiring changes here.

          The copy is the render's, in English, because adding an i18n key is
          outside this window's perimeter. Recorded as a gap.
        */}
        <button
          type="button"
          onClick={() =>
            window.dispatchEvent(
              new KeyboardEvent("keydown", { key: "k", metaKey: true }),
            )
          }
          aria-label="Search clients, practices, pages"
          className="hidden md:flex flex-1 min-w-0 max-w-[420px] mx-2 h-9 items-center gap-2 rounded px-2.5 text-[12px] text-[var(--tx-secondary)] border border-[var(--line-control)] transition-colors hover:bg-[var(--bz-card)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
        >
          <Search size={14} className="flex-shrink-0" />
          <span className="truncate">Search clients, practices, pages…</span>
          <span className="ml-auto flex-none rounded-[3px] border border-[var(--bz-border)] px-1.5 py-0.5 text-[10px] font-[650] tracking-[0.06em]">
            ⌘K
          </span>
        </button>

        <div className="flex-1 md:hidden" />

        {/* Date chip */}
        <span
          className="hidden sm:block text-[11px]"
          style={{ color: "var(--bz-text-2)" }}
        >
          {formatDate()}
        </span>

        {/* Theme toggle */}
        <ThemeToggle />

        {/* WhatsApp badge */}
        {whatsappUnread > 0 && (
          <button
            className="relative p-1.5 rounded-lg transition-colors hidden md:flex hover:bg-[var(--surface-raised)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bz-base)]"
            style={{ color: "var(--bz-text-2)" }}
            aria-label={`${whatsappUnread} unread WhatsApp`}
          >
            <MessageCircle size={15} />
            <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] px-1 text-[9px] font-[650] tabular-nums rounded-full flex items-center justify-center border border-[var(--bz-copper-text)] bg-[var(--bz-base)] text-[var(--bz-copper-text)]">
              {whatsappUnread > 99 ? "99+" : whatsappUnread}
            </span>
          </button>
        )}

        <TeamPortalMessageAlerts />

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-1.5 rounded-lg transition-colors hover:bg-[var(--surface-raised)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bz-base)]"
            style={{ color: "var(--bz-text-2)" }}
            aria-label="Notifications"
          >
            <Bell size={15} />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-[16px] px-1 text-[9px] font-[650] tabular-nums rounded-full flex items-center justify-center border border-[var(--bz-copper-text)] bg-[var(--bz-base)] text-[var(--bz-copper-text)]">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>
          {showNotifications && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowNotifications(false)}
              />
              <div
                className="absolute right-0 top-full mt-3 w-80 z-50 rounded-xl shadow-2xl border max-h-[420px] flex flex-col overflow-hidden transition-all duration-300"
                style={{
                  background: "var(--surface-overlay)",
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
                    Notifications {unreadCount > 0 && `(${unreadCount})`}
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

                {/* Notification list */}
                <div className="flex-1 overflow-y-auto">
                  {notifLoading ? (
                    <div className="p-4 space-y-3">
                      {[1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className="h-12 rounded-lg animate-pulse"
                          style={{ background: "var(--surface-raised)" }}
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
                          onClick={() =>
                            handleNotificationClick(n.actionUrl, n.id)
                          }
                          className="w-full text-left p-2.5 rounded-lg transition-colors flex gap-2.5 items-start hover:bg-[var(--surface-raised)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]"
                        >
                          {/* Severity dot */}
                          <span
                            className="w-[6px] h-[6px] rounded-full flex-shrink-0 mt-1.5"
                            style={{
                              background:
                                SEVERITY_DOT[n.severity] || SEVERITY_DOT.low,
                            }}
                          />
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
                        setShowNotifications(false);
                        router.push("/notifications");
                      }}
                      className="w-full text-center text-[10px] py-1.5 rounded-md transition-colors hover:bg-[var(--surface-raised)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)]"
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

        {/* Clock chip removed — PANOPTICON auto-clock-in from login (2026-04-14) */}
      </div>
    </header>
  );
}
