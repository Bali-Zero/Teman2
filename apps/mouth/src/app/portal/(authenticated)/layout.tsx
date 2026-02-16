"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/workspace/AppSidebar";
import {
  PortalBottomNav,
  PortalHeader,
  PortalErrorBoundary,
} from "@/components/portal";
import { ToastProvider } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { portalNavigation } from "@/types/navigation";

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

      const profile = await api.getProfile();
      const userName =
        profile.name || (profile.email ? profile.email.split("@")[0] : "User");
      setUser({
        name: userName,
        email: profile.email || "",
        avatar: profile.avatar,
      });
    } catch (error) {
      console.error("Failed to load profile", error);
    }
  }, []);

  // Check authentication and load data
  useEffect(() => {
    const checkAuth = () => {
      const token = api.getToken();

      if (!token) {
        router.push("/portal/login");
        return;
      }

      const loadData = async () => {
        setIsLoading(true);
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
      };

      loadData();
    };

    const timeoutId = setTimeout(checkAuth, 100);
    return () => clearTimeout(timeoutId);
  }, [loadUserProfile, router]);

  // Handle logout
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (error) {
      console.error("Logout error", error);
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

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#2a2a2a]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--foreground-muted)]">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <ToastProvider>
      <div className="min-h-screen bg-[#2a2a2a]">
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
  );
}
