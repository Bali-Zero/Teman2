'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { AppSidebar } from '@/components/workspace/AppSidebar';
import { Header } from '@/components/workspace/Header';
import { ToastProvider } from '@/components/ui/toast';
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
    // #region agent log
    fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:38',message:'loadUserProfile entry',data:{hasStoredProfile:!!api.getUserProfile()},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    try {
      const storedProfile = api.getUserProfile();
      // #region agent log
      fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:42',message:'storedProfile check',data:{hasStoredProfile:!!storedProfile,hasEmail:!!storedProfile?.email},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      if (storedProfile) {
        const userName = storedProfile.name || (storedProfile.email ? storedProfile.email.split('@')[0] : 'User');
        // #region agent log
        fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:45',message:'setUser from stored',data:{userName,email:storedProfile.email,role:storedProfile.role},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
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
      // #region agent log
      fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:58',message:'api.getProfile success',data:{hasProfile:!!profile,hasEmail:!!profile?.email},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      const userName = profile.name || (profile.email ? profile.email.split('@')[0] : 'User');
      // #region agent log
      fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:60',message:'setUser from api',data:{userName,email:profile.email,role:profile.role},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
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
      // #region agent log
      fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:72',message:'loadUserProfile error',data:{errorMessage:error instanceof Error?error.message:String(error),errorName:error instanceof Error?error.name:'Unknown'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      console.error('Failed to load profile:', error);
    }
  }, []);

  // Check authentication and load data
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:70',message:'auth check useEffect entry',data:{pathname:typeof window!=='undefined'?window.location.pathname:'unknown'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    // Add a small delay to ensure token is available after login redirect
    // This prevents redirect loops when coming from login page
    const checkAuth = () => {
      // Force re-read from localStorage to ensure we have the latest token
      const token = api.getToken();
      // #region agent log
      fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:76',message:'token check',data:{hasToken:!!token},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion

      if (!token) {
        // #region agent log
        fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:79',message:'no token redirect',data:{redirectTo:'/login'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        router.push('/login');
        return;
      }

      const loadData = async () => {
        setIsLoading(true);
        // #region agent log
        fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:85',message:'loadData start',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        try {
          // Load profile first (critical), clock status can fail gracefully
          await loadUserProfile();
          // #region agent log
          fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:88',message:'loadUserProfile complete',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
          // #endregion

          // Check if user is a client - redirect to portal
          const profile = api.getUserProfile();
          // #region agent log
          fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:91',message:'profile role check',data:{role:profile?.role,isClient:profile?.role==='client'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
          // #endregion
          if (profile?.role === 'client') {
            // Clients should use the portal, not the team workspace
            // #region agent log
            fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:94',message:'client redirect',data:{redirectTo:'/portal'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
            // #endregion
            router.push('/portal');
            return;
          }

          // Load clock status with timeout - don't block if it fails
          await Promise.race([
            loadClockStatus(),
            new Promise((resolve) => setTimeout(resolve, 5000)), // 5s timeout
          ]).catch(() => {
            // Clock status failed, but continue anyway
            // #region agent log
            fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:102',message:'clock status timeout',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
            // #endregion
            if (process.env.NODE_ENV !== 'production') {
              console.warn('Clock status load failed or timed out, continuing anyway');
            }
          });
          // #region agent log
          fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:107',message:'loadData success',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
          // #endregion
        } catch (error) {
          // #region agent log
          fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:110',message:'loadData error',data:{errorMessage:error instanceof Error?error.message:String(error),is401:error instanceof Error&&error.message.includes('401')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
          // #endregion
          // If profile load fails, might be auth issue - redirect to login
          if (error instanceof Error && error.message.includes('401')) {
            // #region agent log
            fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:113',message:'401 redirect',data:{redirectTo:'/login'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
            // #endregion
            router.push('/login');
            return;
          }
        } finally {
          setIsLoading(false);
          // #region agent log
          fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:118',message:'loadData finally',data:{isLoading:false},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
          // #endregion
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
            {/* #region agent log */}
            {typeof window !== 'undefined' && fetch('http://127.0.0.1:7244/ingest/c653ea36-ca67-44be-acf7-89137013d04b',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'layout.tsx:208',message:'render children',data:{pathname:window.location.pathname},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{})}
            {/* #endregion */}
            {children}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
