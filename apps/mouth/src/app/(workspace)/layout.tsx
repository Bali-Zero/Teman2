'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { AppSidebar } from '@/components/workspace/AppSidebar';
import { Header } from '@/components/workspace/Header';
import { api } from '@/lib/api';
import { useTeamStatus } from '@/hooks/useTeamStatus';

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
  const {
    isClockIn,
    isLoading: isClockLoading,
    loadClockStatus,
    toggleClock,
  } = useTeamStatus();

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile) {
        setUser({
          name: storedProfile.name || storedProfile.email.split('@')[0],
          email: storedProfile.email,
          role: storedProfile.role || 'Member',
          team: storedProfile.team || 'Team',
          avatar: undefined,
          isOnline: true,
          hoursToday: undefined,
        });
        return;
      }

      const profile = await api.getProfile();
      setUser({
        name: profile.name || profile.email.split('@')[0],
        email: profile.email,
        role: profile.role || 'Member',
        team: profile.team || 'Team',
        avatar: undefined,
        isOnline: true,
        hoursToday: undefined,
      });
    } catch (error) {
      console.error('Failed to load profile:', error);
    }
  }, []);

  // Check authentication and load data
  useEffect(() => {
    // Add a small delay to ensure token is available after login redirect
    // This prevents redirect loops when coming from login page
    const checkAuth = () => {
      // Force re-read from localStorage to ensure we have the latest token
      const token = api.getToken();
      
      if (!token) {
        router.push('/login');
        return;
      }

      const loadData = async () => {
        setIsLoading(true);
        try {
          await Promise.all([loadUserProfile(), loadClockStatus()]);
        } catch (error) {
          // If profile load fails, might be auth issue - redirect to login
          if (error instanceof Error && error.message.includes('401')) {
            router.push('/login');
            return;
          }
        } finally {
          setIsLoading(false);
        }
      };

      loadData();
    };

    // Small delay to ensure localStorage is fully available after page reload
    const timeoutId = setTimeout(checkAuth, 100);
    return () => clearTimeout(timeoutId);
  }, [router, loadUserProfile, loadClockStatus]);

  // Update isOnline based on clock status
  useEffect(() => {
    setUser((prev) => ({ ...prev, isOnline: isClockIn }));
  }, [isClockIn]);

  // Handle logout
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (error) {
      console.error('Logout error:', error);
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

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--foreground-muted)]">Caricamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Desktop Sidebar */}
      <div className="hidden md:block">
        <AppSidebar
          user={user}
          unreadWhatsApp={0}
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
              user={user}
              unreadWhatsApp={0}
              onLogout={handleLogout}
            />
          </div>
        </>
      )}

      {/* Main Content */}
      <div className="md:ml-60 min-h-screen flex flex-col">
        {/* Header */}
        <Header
          userName={user.name}
          isClockIn={isClockIn}
          isClockLoading={isClockLoading}
          onToggleClock={toggleClock}
          onMobileMenuToggle={handleMobileMenuToggle}
          isMobileMenuOpen={isMobileMenuOpen}
          notificationCount={0}
          whatsappUnread={0}
        />

        {/* Page Content */}
        <main className="flex-1 p-4 md:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
