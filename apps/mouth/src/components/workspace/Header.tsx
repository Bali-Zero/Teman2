"use client";

import React, { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Menu, X, MessageCircle, CheckCheck } from "lucide-react";
import { routeTitles } from "@/types/navigation";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

import { useCrmNotifications } from "@/hooks/useCrmNotifications";

interface HeaderProps {
  userName: string;
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  whatsappUnread?: number;
  mobileMenuToggleRef?: React.RefObject<HTMLButtonElement | null>;
}

const SEVERITY_DOT: Record<string, string> = {
  critical: "var(--bz-red, #e45c5c)",
  high: "var(--bz-accent, #d4845a)",
  medium: "#e8b84a",
  low: "var(--bz-blue, #4a8ec4)",
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
      className="sticky top-0 z-30 w-full border-b transition-all duration-300"
      style={{
        height: "var(--bz-header-height, 48px)",
        background: "rgba(19, 19, 21, 0.65)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderColor: "var(--bz-border)",
      }}
    >
      <div className="flex items-center h-full px-5 gap-3">
        {/* Mobile menu */}
        <button
          ref={mobileMenuToggleRef}
          onClick={onMobileMenuToggle}
          className="md:hidden p-1.5 rounded-lg transition-colors"
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
          <span
            className="hidden lg:inline text-[11px] truncate"
            style={{ color: "var(--bz-text-1)" }}
          >
            We are writing the history!
          </span>
        </div>

        <div className="flex-1" />

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
            className="relative p-1.5 rounded-lg transition-colors hidden md:flex"
            style={{ color: "var(--bz-text-2)" }}
            aria-label={`${whatsappUnread} unread WhatsApp`}
          >
            <MessageCircle size={15} />
            <span
              className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] text-[8px] font-bold rounded-full flex items-center justify-center text-white"
              style={{ background: "var(--bz-accent)" }}
            >
              {whatsappUnread > 99 ? "99+" : whatsappUnread}
            </span>
          </button>
        )}

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-1.5 rounded-lg transition-colors"
            style={{ color: "var(--bz-text-2)" }}
            aria-label="Notifications"
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
          {showNotifications && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowNotifications(false)}
              />
              <div
                className="absolute right-0 top-full mt-3 w-80 z-50 rounded-xl shadow-2xl border max-h-[420px] flex flex-col overflow-hidden transition-all duration-300"
                style={{
                  background: "rgba(32, 32, 36, 0.75)",
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
                          onClick={() =>
                            handleNotificationClick(n.actionUrl, n.id)
                          }
                          className="w-full text-left p-2.5 rounded-lg transition-colors flex gap-2.5 items-start hover:bg-white/[0.04]"
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

        {/* Clock chip removed — PANOPTICON auto-clock-in from login (2026-04-14) */}
      </div>
    </header>
  );
}
