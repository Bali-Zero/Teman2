'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { AppSidebar } from '@/components/workspace/AppSidebar';
import { Header } from '@/components/workspace/Header';
import { ToastProvider } from '@/components/ui/toast';
import { api } from '@/lib/api';
import { useTeamStatus } from '@/hooks/useTeamStatus';
import { logger } from '@/lib/logger';
import { ErrorBoundary } from '@/components/optimization';
import { CellWidget } from '@/components/cell/CellWidget';

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState({
    name: '',
    email: '',
    role: '',
    team: '',
    avatar: undefined as string | undefined,
    isOnline: false,
    hoursToday: undefined as string | undefined,
  });

  // Clock status from existing hook
  const { isClockIn, isLoading: isClockLoading, loadClockStatus, toggleClock } = useTeamStatus();

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile) {
        const userName =
          storedProfile.name || (storedProfile.email ? storedProfile.email.split('@')[0] : 'User');
        setUser({
          name: userName,
          email: storedProfile.email || '',
          role: storedProfile.role || 'Member',
          team: storedProfile.team || 'Team',
          avatar: storedProfile.avatar,
          isOnline: true,
          hoursToday: undefined,
        });
        return;
      }

      const profile = await api.getProfile();
      const userName = profile.name || (profile.email ? profile.email.split('@')[0] : 'User');
      setUser({
        name: userName,
        email: profile.email || '',
        role: profile.role || 'Member',
        team: profile.team || 'Team',
        avatar: profile.avatar,
        isOnline: true,
        hoursToday: undefined,
      });
    } catch (error) {
      logger.error(
        'Failed to load profile',
        { component: 'WorkspaceLayout', action: 'loadProfile' },
        error instanceof Error ? error : new Error(String(error))
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
          if (profile?.role === 'client') {
            // Clients should use the portal, not the team workspace
            router.push('/portal');
            return;
          }

          // Load clock status with timeout - don't block if it fails
          await Promise.race([
            loadClockStatus(),
            new Promise((resolve) => setTimeout(resolve, 5000)), // 5s timeout
          ]).catch(() => {
            // Clock status failed, but continue anyway
            logger.warn('Clock status load failed or timed out, continuing anyway', {
              component: 'WorkspaceLayout',
              action: 'loadClockStatus',
            });
          });
        } catch (error) {
          // Profile load failed = not authenticated → redirect to login
          // Always use kita.balizero.com for login (auth hub), preserving return URL
          const currentUrl = typeof window !== 'undefined' ? window.location.href : '';
          const loginBase = 'https://kita.balizero.com/login';
          const loginUrl = currentUrl
            ? `${loginBase}?redirect=${encodeURIComponent(currentUrl)}`
            : loginBase;

          // --- UI DEV BYPASS ---
          if (process.env.NODE_ENV === 'development') {
            logger.warn('[DEV MODE] Bypassing login redirect for local UI inspection', {
              component: 'WorkspaceLayout',
              action: 'authCheck',
            });
            setUser({
              name: 'Zero (Local Dev)',
              email: 'zero@balizero.com',
              role: 'admin',
              team: 'Management',
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

  // Update isOnline based on clock status
  useEffect(() => {
    setUser((prev) => ({ ...prev, isOnline: isClockIn }));
  }, [isClockIn]);

  // Handle logout
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (error) {
      logger.error(
        'Logout error',
        { component: 'WorkspaceLayout', action: 'logout' },
        error instanceof Error ? error : new Error(String(error))
      );
    } finally {
      router.push('/login');
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
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsMobileMenuOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isMobileMenuOpen]);

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-transparent">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--bz-accent)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--bz-text-2)]">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <ToastProvider>
      <div className="min-h-screen bg-transparent">
        {/* Desktop Sidebar */}
        <div className="hidden md:block">
          <AppSidebar user={user} unreadWhatsApp={0} onLogout={handleLogout} />
        </div>

        {/* Mobile Sidebar Overlay */}
        {isMobileMenuOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 md:hidden transition-all duration-300"
              onClick={() => setIsMobileMenuOpen(false)}
            />
            <div className="fixed inset-y-0 left-0 z-50 md:hidden">
              <AppSidebar user={user} unreadWhatsApp={0} onLogout={handleLogout} />
            </div>
          </>
        )}

        {/* Main Content */}
        <div className="md:ml-[216px] min-h-screen flex flex-col transition-all duration-300">
          {/* Header */}
          <Header
            userName={user.name}
            isClockIn={isClockIn}
            isClockLoading={isClockLoading}
            onToggleClock={toggleClock}
            onMobileMenuToggle={handleMobileMenuToggle}
            isMobileMenuOpen={isMobileMenuOpen}
            whatsappUnread={0}
          />

          {/* Page Content */}
          <main className="flex-1 p-4 md:p-6 lg:p-8">
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
      <CellWidget />
    </ToastProvider>
  );
}
