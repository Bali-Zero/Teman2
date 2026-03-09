"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { Bell, Clock, Menu, X, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { routeTitles } from "@/types/navigation";
import { cn } from "@/lib/utils";

interface HeaderProps {
  userName: string;
  isClockIn?: boolean;
  isClockLoading?: boolean;
  onToggleClock?: () => void;
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  notificationCount?: number;
  whatsappUnread?: number;
  showClock?: boolean; // Show clock in/out button
}

export function Header({
  userName,
  isClockIn = false,
  isClockLoading = false,
  onToggleClock,
  onMobileMenuToggle,
  isMobileMenuOpen,
  notificationCount = 0,
  whatsappUnread = 0,
  showClock = true,
}: HeaderProps) {
  const pathname = usePathname();
  const [showNotifications, setShowNotifications] = useState(false);

  // Get page title from pathname
  const getPageTitle = () => {
    // Check exact match first
    if (routeTitles[pathname]) {
      return routeTitles[pathname];
    }
    // Check for dynamic routes
    for (const [route, title] of Object.entries(routeTitles)) {
      if (pathname.startsWith(route) && route !== "/") {
        return title;
      }
    }
    return "Dashboard";
  };

  // Get greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
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

  return (
    <header
      className="sticky top-0 z-30 w-full border-b"
      style={{ height: "var(--bz-header-height, 48px)", background: "var(--bz-elevated)", borderColor: "var(--bz-border)" }}
    >
      <div className="flex items-center h-full px-5 gap-3">
        {/* Mobile menu */}
        <button
          onClick={onMobileMenuToggle}
          className="md:hidden p-1.5 rounded-lg transition-colors"
          style={{ color: "var(--bz-text-2)" }}
          aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
        >
          {isMobileMenuOpen ? <X size={16} /> : <Menu size={16} />}
        </button>

        {/* Page title */}
        <h1 className="text-[13px] font-medium" style={{ color: "var(--bz-text-1)" }}>
          {getPageTitle()}
        </h1>

        <div className="flex-1" />

        {/* Date chip */}
        <span className="hidden sm:block text-[11px]" style={{ color: "var(--bz-text-3)" }}>
          {formatDate()}
        </span>

        {/* WhatsApp badge */}
        {whatsappUnread > 0 && (
          <button className="relative p-1.5 rounded-lg transition-colors hidden md:flex"
                  style={{ color: "var(--bz-text-2)" }}
                  aria-label={`${whatsappUnread} unread WhatsApp`}>
            <MessageCircle size={15} />
            <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] text-[8px] font-bold rounded-full flex items-center justify-center text-white"
                  style={{ background: "var(--bz-accent)" }}>
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
            {notificationCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] text-[8px] font-bold rounded-full flex items-center justify-center text-white"
                    style={{ background: "var(--bz-accent)" }}>
                {notificationCount > 99 ? "99+" : notificationCount}
              </span>
            )}
          </button>
          {showNotifications && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowNotifications(false)} />
              <div className="absolute right-0 top-full mt-2 w-72 z-50 rounded-xl shadow-xl border"
                   style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}>
                <div className="p-3 border-b text-[12px] font-semibold"
                     style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-1)" }}>
                  Notifications
                </div>
                <div className="p-4 text-[11px] text-center" style={{ color: "var(--bz-text-3)" }}>
                  No new notifications
                </div>
              </div>
            </>
          )}
        </div>

        {/* Clock chip */}
        {showClock && onToggleClock && (
          <button
            onClick={onToggleClock}
            disabled={isClockLoading}
            className={cn("hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium transition-all border")}
            style={isClockIn
              ? { borderColor: "rgba(77,184,122,0.25)", background: "rgba(77,184,122,0.07)", color: "var(--bz-green)" }
              : { borderColor: "var(--bz-border)", background: "var(--bz-surface)", color: "var(--bz-text-2)" }
            }
          >
            <span className={cn("w-[5px] h-[5px] rounded-full", isClockIn && "animate-pulse")}
                  style={{ background: isClockIn ? "var(--bz-green)" : "var(--bz-text-3)" }} />
            {isClockLoading ? "..." : isClockIn ? "Clocked In" : "Clock In"}
          </button>
        )}
      </div>
    </header>
  );
}
