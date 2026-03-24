"use client";

/**
 * PortalHeader Component
 *
 * Header dedicato per il client portal con notifiche integrate
 */

import React from "react";
import { usePathname } from "next/navigation";
import { Menu, X, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { routeTitles } from "@/types/navigation";
import { cn } from "@/lib/utils";
import { PortalNotificationsPopover } from "./PortalNotifications";

interface PortalHeaderProps {
  userName: string;
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  showBackButton?: boolean;
  onBack?: () => void;
  customTitle?: string;
}

export function PortalHeader({
  userName,
  onMobileMenuToggle,
  isMobileMenuOpen,
  showBackButton = false,
  onBack,
  customTitle,
}: PortalHeaderProps) {
  const pathname = usePathname();

  // Get page title from pathname
  const getPageTitle = () => {
    if (customTitle) return customTitle;

    if (!pathname) return "Dashboard";
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
    };
    return new Date().toLocaleDateString("en-US", options);
  };

  return (
    <header className="sticky top-0 z-30 w-full bg-[rgba(29,39,59,0.7)] backdrop-blur-[24px] border-b border-[var(--glass-rim)] shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
      <div className="flex items-center justify-between h-16 px-4 md:px-6">
        {/* Left Section */}
        <div className="flex items-center gap-3">
          {/* Back Button */}
          {showBackButton && onBack && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onBack}
              className="hover:bg-[var(--background-elevated)]"
            >
              <ChevronLeft className="w-5 h-5 text-[var(--foreground)]" />
            </Button>
          )}

          {/* Mobile Menu Button */}
          <button
            onClick={onMobileMenuToggle}
            className={cn(
              "p-2 rounded-lg hover:bg-[var(--background-elevated)] transition-colors",
              showBackButton && "md:hidden",
            )}
            aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
          >
            {isMobileMenuOpen ? (
              <X className="w-5 h-5 text-[var(--foreground)]" />
            ) : (
              <Menu className="w-5 h-5 text-[var(--foreground)]" />
            )}
          </button>

          {/* Page Title */}
          <div className="hidden sm:block">
            <h1 className="text-lg font-bold text-[var(--tx-pure)] tracking-wide">
              {getPageTitle()}
            </h1>
            <p className="text-[11px] text-[var(--tx-secondary)] uppercase tracking-widest font-bold mt-0.5">
              {formatDate()} <span className="text-[var(--bz-copper)] opacity-70 px-1">•</span> {getGreeting()}, {userName.split(" ")[0]}
            </p>
          </div>

          {/* Mobile Page Title */}
          <h1 className="sm:hidden text-lg font-bold text-[var(--tx-pure)] tracking-wide">
            {getPageTitle()}
          </h1>
        </div>

        {/* Right Section */}
        <div className="flex items-center gap-2">
          {/* Notifications */}
          <PortalNotificationsPopover />
        </div>
      </div>
    </header>
  );
}
