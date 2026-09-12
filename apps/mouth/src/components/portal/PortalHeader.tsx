"use client";

/**
 * PortalHeader Component
 *
 * Header dedicato per il client portal con notifiche integrate
 */

import React from "react";
import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { Menu, X, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { routeTitles } from "@/types/navigation";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { usePortalDateFormat } from "@/lib/format/usePortalDateFormat";

// Lazy: notifications + impersonation are not first-paint critical.
// Reduces parallel chunks on /portal/* — ERR_INSUFFICIENT_RESOURCES mitigation.
const PortalNotificationsPopover = dynamic(
  () =>
    import("./PortalNotifications").then((m) => ({
      default: m.PortalNotificationsPopover,
    })),
  { ssr: false },
);
const SuperuserImpersonationBar = dynamic(
  () =>
    import("./SuperuserImpersonationBar").then((m) => ({
      default: m.SuperuserImpersonationBar,
    })),
  { ssr: false },
);

interface PortalHeaderProps {
  userName: string;
  variant?: "client" | "partner";
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  showBackButton?: boolean;
  onBack?: () => void;
  customTitle?: string;
  mobileMenuToggleRef?: React.RefObject<HTMLButtonElement | null>;
}

export function PortalHeader({
  userName,
  variant = "client",
  onMobileMenuToggle,
  isMobileMenuOpen,
  showBackButton = false,
  onBack,
  customTitle,
  mobileMenuToggleRef,
}: PortalHeaderProps) {
  const pathname = usePathname();
  const { formatDate: formatDateLocale } = usePortalDateFormat();

  // Get page title from pathname
  const getPageTitle = () => {
    if (customTitle) return customTitle;

    if (!pathname) return "Dashboard";
    // Check exact match first
    if (routeTitles[pathname]) {
      return routeTitles[pathname];
    }
    // Check dynamic routes by specificity so /portal does not shadow /portal/*
    const match = Object.entries(routeTitles)
      .filter(([route]) => route !== "/" && pathname.startsWith(route))
      .sort(([a], [b]) => b.length - a.length)[0];
    return match?.[1] ?? "Dashboard";
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
    return formatDateLocale(new Date(), options);
  };

  return (
    <header className="sticky top-0 z-30 w-full bg-[var(--portal-header-bg)] backdrop-blur-[24px] border-b border-[var(--bz-border)]">
      <div className="flex items-center justify-between h-[var(--bz-header-height,64px)] px-4 md:px-6">
        {/* Left Section */}
        <div className="flex items-center gap-3">
          {/* Back Button */}
          {showBackButton && onBack && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onBack}
              aria-label="Go back"
              className="h-10 w-10 rounded-[0.25rem] hover:bg-[var(--background-elevated)]"
            >
              <ChevronLeft className="w-5 h-5 text-[var(--foreground)]" />
            </Button>
          )}

          {/* Mobile Menu Button */}
          <button
            ref={mobileMenuToggleRef}
            type="button"
            onClick={onMobileMenuToggle}
            className={cn(
              "h-10 w-10 grid place-items-center rounded-[0.25rem] text-[var(--tx-secondary)] hover:bg-[var(--background-elevated)] hover:text-[var(--tx-pure)] transition-colors md:hidden",
            )}
            aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
            aria-controls="workspace-mobile-nav"
            aria-expanded={isMobileMenuOpen}
          >
            {isMobileMenuOpen ? (
              <X className="w-5 h-5 text-[var(--foreground)]" />
            ) : (
              <Menu className="w-5 h-5 text-[var(--foreground)]" />
            )}
          </button>

          {/* Page Title */}
          <div className="hidden sm:block">
            <h1 className="text-[20px] font-medium leading-[1.1] text-[var(--tx-pure)] tracking-[-0.01em] [font-family:var(--font-serif)]">
              {getPageTitle()}
            </h1>
            <p className="text-[12px] text-[var(--tx-secondary)] mt-[3px]">
              {formatDate()}
              <span
                aria-hidden="true"
                className="text-[var(--bz-copper)] px-[5px]"
              >
                ·
              </span>
              {getGreeting()}, {userName.split(" ")[0] || "there"}
            </p>
          </div>

          {/* Mobile Page Title */}
          <h1 className="sm:hidden text-[18px] font-medium text-[var(--tx-pure)] tracking-[-0.01em] [font-family:var(--font-serif)]">
            {getPageTitle()}
          </h1>
        </div>

        {/* Right Section */}
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {variant === "client" && (
            <>
              {/* Superuser impersonation (renders null for non-superusers) */}
              <SuperuserImpersonationBar />
              {/* Notifications */}
              <PortalNotificationsPopover />
            </>
          )}
        </div>
      </div>
    </header>
  );
}
