"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CircleDollarSign,
  FolderOpen,
  Home,
  MessageCircle,
  User,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const POLL_INTERVAL = 30000; // 30 seconds

interface PortalBottomNavProps {
  readonly variant?: "client" | "partner";
}

export function PortalBottomNav({ variant = "client" }: PortalBottomNavProps) {
  const pathname = usePathname();
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchUnreadCount = useCallback(async () => {
    if (variant === "partner") return;
    try {
      const data = await api.portal.getMessages(1, 0);
      setUnreadCount(data.unreadCount);
    } catch (err) {
      // Silently fail - not critical for nav
    }
  }, [variant]);

  // Initial fetch
  useEffect(() => {
    fetchUnreadCount();
  }, [fetchUnreadCount]);

  // Polling for unread messages
  useEffect(() => {
    const interval = setInterval(fetchUnreadCount, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Refetch when navigating away from messages
  useEffect(() => {
    if (pathname !== "/portal/messages" && pathname !== "/portal/chat") {
      fetchUnreadCount();
    }
  }, [pathname, fetchUnreadCount]);

  const tabs =
    variant === "partner"
      ? [
          {
            name: "Home",
            href: "/portal/partner/dashboard",
            icon: Home,
          },
          {
            name: "Referrals",
            href: "/portal/partner/referrals",
            icon: Users,
          },
          {
            name: "Commissions",
            href: "/portal/partner/commissions",
            icon: CircleDollarSign,
          },
          {
            name: "Profile",
            href: "/portal/partner/profile",
            icon: User,
          },
        ]
      : [
          { name: "Home", href: "/portal", icon: Home },
          { name: "Vault", href: "/portal/vault", icon: FolderOpen },
          {
            name: "Messages",
            href: "/portal/messages",
            icon: MessageCircle,
            badge: unreadCount,
          },
          { name: "Profile", href: "/portal/profile", icon: User },
        ];

  // Only show on mobile
  return (
    <nav
      aria-label="Main navigation"
      className="fixed bottom-0 left-0 right-0 border-t border-[var(--bz-border)] bg-[var(--bz-bottom-nav-bg)] backdrop-blur-[20px] md:hidden z-50 safe-area-bottom"
    >
      <div className="flex items-center justify-around h-16">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive =
            pathname === tab.href ||
            (tab.href !== "/portal" && pathname?.startsWith(tab.href));
          const showBadge = tab.badge && tab.badge > 0;
          return (
            <Link
              key={tab.name}
              href={tab.href}
              // Mobile links are still mounted when CSS hides this nav on
              // desktop, so prevent protected RSC prefetches in every profile.
              prefetch={false}
              aria-current={isActive ? "page" : undefined}
              aria-label={tab.name}
              className={cn(
                "flex flex-col items-center justify-center gap-[5px] w-full h-full min-h-11 transition-colors relative",
                isActive
                  ? "text-[var(--tx-pure)]"
                  : "text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]",
              )}
            >
              <div className="relative">
                <Icon
                  className={cn(
                    "w-5 h-5",
                    isActive && "text-[var(--bz-copper)]",
                  )}
                />
                {showBadge && (
                  <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 flex items-center justify-center rounded-full bg-[var(--bz-copper)] text-white text-[9px] font-[650] tabular-nums">
                    {tab.badge > 99 ? "99+" : tab.badge}
                  </span>
                )}
              </div>
              <span className="text-[9px] font-[650] uppercase tracking-[.1em]">
                {tab.name}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
