"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AppSidebar } from "@/components/workspace/AppSidebar";
import { Header } from "@/components/workspace/Header";
import { ToastProvider } from "@/components/ui/toast";
import { api } from "@/lib/api";
// useTeamStatus removed — PANOPTICON auto-clock-in from login (2026-04-14)
import { logger } from "@/lib/logger";
import { ErrorBoundary } from "@/components/optimization";
import { CellWidget } from "@/components/cell/CellWidget";
import { WorkspaceAssistant } from "@/components/workspace/WorkspaceAssistant";
import { KitaCommandPalette } from "@/components/workspace/KitaCommandPalette";
import { routeTitles } from "@/types/navigation";

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

function getRouteTitle(pathname: string | null): string {
  if (!pathname) return "Workspace";
  if (routeTitles[pathname]) return routeTitles[pathname];
  for (const [route, title] of Object.entries(routeTitles)) {
    if (pathname.startsWith(route) && route !== "/") return title;
  }
  return "Workspace";
}

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const isTerminalPage = pathname === "/terminal";
  const pageTitle = getRouteTitle(pathname);
  const mobileSidebarRef = useRef<HTMLDivElement | null>(null);
  const mobileMenuToggleRef = useRef<HTMLButtonElement | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState({
    name: "",
    email: "",
    role: "",
    team: "",
    avatar: undefined as string | undefined,
    isOnline: false,
    hoursToday: undefined as string | undefined,
  });

  // Clock-in is now automatic on login (PANOPTICON Phase 0)

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile) {
        const userName =
          storedProfile.name ||
          (storedProfile.email ? storedProfile.email.split("@")[0] : "User");
        setUser({
          name: userName,
          email: storedProfile.email || "",
          role: storedProfile.role || "Member",
          team: storedProfile.team || "Team",
          avatar: storedProfile.avatar,
          isOnline: true,
          hoursToday: undefined,
        });
        return;
      }

      const profile = await api.getProfile();
      const userName =
        profile.name || (profile.email ? profile.email.split("@")[0] : "User");
      setUser({
        name: userName,
        email: profile.email || "",
        role: profile.role || "Member",
        team: profile.team || "Team",
        avatar: profile.avatar,
        isOnline: true,
        hoursToday: undefined,
      });
    } catch (error) {
      logger.error(
        "Failed to load profile",
        { component: "WorkspaceLayout", action: "loadProfile" },
        error instanceof Error ? error : new Error(String(error)),
      );
      throw error; // Re-throw so caller can redirect to login
    }
  }, []);

  // Check authentication and load data
  useEffect(() => {
    // Add a small delay to ensure token is available after login redirect
    // This prevents redirect loops when coming from login page
    const checkAuth = () => {
      const loadData = async () => {
        setIsLoading(true);
        try {
          // Load profile first (critical), clock status can fail gracefully
          // This call uses httpOnly cookies — works across all *.balizero.com subdomains
          // even when localStorage is empty (e.g. first visit on calendar.balizero.com)
          await loadUserProfile();

          // Check if user is a client - redirect to portal
          const profile = api.getUserProfile();
          if (profile?.role === "client") {
            // Clients should use the portal, not the team workspace
            router.push("/portal");
            return;
          }

          // Clock-in is now automatic on login (PANOPTICON Phase 0)
        } catch (error) {
          // Profile load failed = not authenticated → redirect to login
          // Always use kita.balizero.com for login (auth hub), preserving return URL
          const currentUrl =
            typeof window !== "undefined" ? window.location.href : "";
          const loginBase = "https://kita.balizero.com/login";
          const loginUrl = currentUrl
            ? `${loginBase}?redirect=${encodeURIComponent(currentUrl)}`
            : loginBase;

          // --- UI DEV BYPASS ---
          if (process.env.NODE_ENV === "development") {
            logger.warn(
              "[DEV MODE] Bypassing login redirect for local UI inspection",
              {
                component: "WorkspaceLayout",
                action: "authCheck",
              },
            );
            setUser({
              name: "Zero (Local Dev)",
              email: "zero@balizero.com",
              role: "admin",
              team: "Management",
              avatar: undefined,
              isOnline: true,
              hoursToday: undefined,
            });
            setIsLoading(false);
            return;
          }

          window.location.href = loginUrl;
          return;
        } finally {
          setIsLoading(false);
        }
      };

      loadData();
    };

    // Small delay to ensure localStorage is fully available after page reload
    const timeoutId = setTimeout(checkAuth, 100);
    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // ← Run only once on mount to avoid infinite loop

  // isOnline status is now managed server-side (PANOPTICON)

  // Handle logout
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (error) {
      logger.error(
        "Logout error",
        { component: "WorkspaceLayout", action: "logout" },
        error instanceof Error ? error : new Error(String(error)),
      );
    } finally {
      router.push("/login");
    }
  };

  // Handle mobile menu toggle
  const handleMobileMenuToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, []);

  // Mobile sidebar dialog: Esc to close + focus trap + return focus to toggle
  useEffect(() => {
    if (!isMobileMenuOpen) return;

    const root = mobileSidebarRef.current;
    const focusables = root
      ? Array.from(
          root.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled]), select:not([disabled])',
          ),
        )
      : [];
    focusables[0]?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsMobileMenuOpen(false);
        return;
      }
      if (e.key !== "Tab" || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      // Return focus to the toggle that opened the dialog (a11y best practice)
      mobileMenuToggleRef.current?.focus();
    };
  }, [isMobileMenuOpen]);

  // Show loading state
  if (isLoading) {
    return (
      <main
        id="main-content"
        aria-busy="true"
        aria-live="polite"
        className="min-h-screen flex items-center justify-center bg-transparent"
      >
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-10 h-10 border-2 border-[var(--bz-accent)] border-t-transparent rounded-full animate-spin"
            role="status"
            aria-label="Loading workspace"
          />
          {/* Use --bz-text-1 (#edeae4) — passes WCAG AA on workspace surfaces. */}
          <p className="text-sm text-[var(--bz-text-1)]">Loading…</p>
        </div>
      </main>
    );
  }

  return (
    <ToastProvider>
      <a href="#main-content" className="bz-skip-link">
        Skip to main content
      </a>
      <div className="min-h-screen bg-transparent">
        {/* Desktop Sidebar — labelled landmark so AT can list it */}
        <div className="hidden md:block">
          <AppSidebar
            user={user}
            unreadWhatsApp={0}
            onLogout={handleLogout}
            ariaLabel="Primary"
          />
        </div>

        {/* Mobile Sidebar Overlay (dialog) */}
        {isMobileMenuOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 md:hidden transition-all duration-300"
              onClick={() => setIsMobileMenuOpen(false)}
              aria-hidden="true"
            />
            <div
              ref={mobileSidebarRef}
              role="dialog"
              aria-modal="true"
              aria-label="Workspace navigation"
              className="fixed inset-y-0 left-0 z-50 md:hidden"
            >
              <AppSidebar
                user={user}
                unreadWhatsApp={0}
                onLogout={handleLogout}
                ariaLabel="Primary (mobile)"
              />
            </div>
          </>
        )}

        {/* Main Content */}
        <div className="md:ml-[216px] min-h-screen flex flex-col transition-all duration-300">
          {/* Header */}
          <Header
            userName={user.name}
            onMobileMenuToggle={handleMobileMenuToggle}
            isMobileMenuOpen={isMobileMenuOpen}
            whatsappUnread={0}
            mobileMenuToggleRef={mobileMenuToggleRef}
          />

          {/* Page Content — single labelled <main> landmark */}
          <main
            id="main-content"
            aria-labelledby="bz-page-title"
            tabIndex={-1}
            className="flex-1 p-4 md:p-6 lg:p-8"
          >
            {/* Visually-hidden h1 ensures every workspace route satisfies
                page-has-heading-one, even when the in-page header uses a
                small visual title or the page itself has no h1. */}
            <h1 id="bz-page-title" className="sr-only">
              {pageTitle}
            </h1>
            <ErrorBoundary
              fallback={
                <div className="p-8 text-center text-white">
                  Something went wrong. Please refresh the page.
                </div>
              }
            >
              {children}
            </ErrorBoundary>
          </main>
        </div>
      </div>
      {!isTerminalPage && <CellWidget />}
      {!isTerminalPage && <WorkspaceAssistant />}
      <KitaCommandPalette />
    </ToastProvider>
  );
}
