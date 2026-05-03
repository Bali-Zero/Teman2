"use client";

import React, { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/workspace/AppSidebar";
import { PortalHeader } from "@/components/portal/PortalHeader";
import { PortalErrorBoundary } from "@/components/portal/PortalErrorBoundary";
import { ToastProvider } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { portalNavigation } from "@/types/navigation";
import { AdminImpersonationProvider } from "@/contexts/AdminImpersonationContext";

// Lazy: bottom nav is mobile-only and below-fold on desktop.
// Reduces parallel chunks on /portal/* — ERR_INSUFFICIENT_RESOURCES mitigation.
const PortalBottomNav = dynamic(
  () =>
    import("@/components/portal/PortalBottomNav").then((m) => ({
      default: m.PortalBottomNav,
    })),
  { ssr: false },
);

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState({
    name: "",
    email: "",
    avatar: undefined as string | undefined,
  });

  // Load user profile
  // Uses portal-scoped endpoint (/api/portal/profile) because /api/auth/profile
  // 500s for role=client — see commit history. Falls back to storedProfile name
  // when available, since portal profile uses fullName (not name).
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
          avatar: storedProfile.avatar,
        });
        return;
      }

      const portalProfile = await api.portal.getProfile();
      const userName =
        portalProfile.fullName ||
        (portalProfile.email ? portalProfile.email.split("@")[0] : "User");
      setUser({
        name: userName,
        email: portalProfile.email || "",
        avatar: undefined,
      });
    } catch (error) {
      logger.error(
        "Failed to load profile",
        { component: "PortalLayout", action: "loadUserProfile" },
        error as Error,
      );
    }
  }, []);

  // Check authentication and load data
  // Uses cookie-based auth check (not localStorage) for cross-domain SSO support.
  // When user logs in on kita.balizero.com, the httpOnly cookie on .balizero.com
  // is shared with my.balizero.com, but localStorage is NOT shared across subdomains.
  useEffect(() => {
    const checkAuth = async () => {
      setIsLoading(true);

      // First check localStorage (fast path for same-domain)
      const token = api.getToken();
      if (token) {
        try {
          await loadUserProfile();
        } catch (error) {
          if (error instanceof Error && error.message.includes("401")) {
            router.push("/portal/login");
            return;
          }
        } finally {
          setIsLoading(false);
        }
        return;
      }

      // No localStorage token — try cookie-based auth (cross-domain SSO).
      // The httpOnly cookie is sent automatically via credentials: "include".
      try {
        const portalProfile = await api.portal.getProfile();
        if (portalProfile?.email) {
          const userName =
            portalProfile.fullName ||
            (portalProfile.email ? portalProfile.email.split("@")[0] : "User");
          setUser({
            name: userName,
            email: portalProfile.email || "",
            avatar: undefined,
          });
          setIsLoading(false);
          return;
        }
      } catch {
        // Cookie auth also failed — redirect to login
      }

      setIsLoading(false);
      router.push("/portal/login");
    };

    const timeoutId = setTimeout(checkAuth, 100);
    return () => clearTimeout(timeoutId);
  }, [loadUserProfile, router]);

  // Handle logout
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (error) {
      logger.error(
        "Logout error",
        { component: "PortalLayout", action: "logout" },
        error as Error,
      );
    } finally {
      router.push("/portal/login");
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

  // Close mobile menu on Escape
  useEffect(() => {
    if (!isMobileMenuOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsMobileMenuOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isMobileMenuOpen]);

  // Show loading state
  if (isLoading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--bz-base)" }}
      >
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin"
            style={{
              borderColor: "var(--bz-accent-warm)",
              borderTopColor: "transparent",
            }}
          />
          <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
            Loading...
          </p>
        </div>
      </div>
    );
  }

  return (
    <AdminImpersonationProvider>
      <ToastProvider>
        <div className="min-h-screen" style={{ background: "var(--bz-base)" }}>
          {/* Desktop Sidebar */}
          <div className="hidden md:block">
            <AppSidebar
              user={{
                ...user,
                role: "client",
                team: "Client Portal",
                isOnline: true,
              }}
              navigationConfig={portalNavigation}
              isPortal={true}
              onLogout={handleLogout}
            />
          </div>

          {/* Mobile Sidebar Overlay */}
          {isMobileMenuOpen && (
            <>
              <div
                className="fixed inset-0 bg-black/50 z-40 md:hidden"
                onClick={() => setIsMobileMenuOpen(false)}
              />
              <div className="fixed inset-y-0 left-0 z-50 md:hidden">
                <AppSidebar
                  user={{
                    ...user,
                    role: "client",
                    team: "Client Portal",
                    isOnline: true,
                  }}
                  navigationConfig={portalNavigation}
                  isPortal={true}
                  onLogout={handleLogout}
                />
              </div>
            </>
          )}

          {/* Main Content */}
          <div className="md:ml-60 min-h-screen flex flex-col">
            {/* Header */}
            <PortalHeader
              userName={user.name}
              onMobileMenuToggle={handleMobileMenuToggle}
              isMobileMenuOpen={isMobileMenuOpen}
            />

            {/* Page Content */}
            <main className="flex-1 p-4 md:p-6 lg:p-8">
              <PortalErrorBoundary section="Portal">
                {children}
              </PortalErrorBoundary>
            </main>
          </div>

          {/* Mobile Bottom Nav */}
          <PortalBottomNav />
        </div>
      </ToastProvider>
    </AdminImpersonationProvider>
  );
}
