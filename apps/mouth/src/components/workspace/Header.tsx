'use client';

import React, { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Bell, Clock, Menu, X, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { routeTitles } from '@/types/navigation';
import { cn } from '@/lib/utils';

interface HeaderProps {
  userName: string;
  isClockIn: boolean;
  isClockLoading: boolean;
  onToggleClock: () => void;
  onMobileMenuToggle: () => void;
  isMobileMenuOpen: boolean;
  notificationCount?: number;
  whatsappUnread?: number;
}

export function Header({
  userName,
  isClockIn,
  isClockLoading,
  onToggleClock,
  onMobileMenuToggle,
  isMobileMenuOpen,
  notificationCount = 0,
  whatsappUnread = 0,
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
      if (pathname.startsWith(route) && route !== '/') {
        return title;
      }
    }
    return 'Dashboard';
  };

  // Get greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Buongiorno';
    if (hour < 18) return 'Buon pomeriggio';
    return 'Buonasera';
  };

  // Format current date
  const formatDate = () => {
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    };
    return new Date().toLocaleDateString('it-IT', options);
  };

  return (
    <header className="sticky top-0 z-30 w-full bg-[var(--background)]/80 backdrop-blur-md border-b border-[var(--border)]">
      <div className="flex items-center justify-between h-16 px-4 md:px-6">
        {/* Left Section - Mobile Menu + Greeting */}
        <div className="flex items-center gap-4">
          {/* Mobile Menu Button */}
          <button
            onClick={onMobileMenuToggle}
            className="md:hidden p-2 rounded-lg hover:bg-[var(--background-elevated)] transition-colors"
            aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {isMobileMenuOpen ? (
              <X className="w-5 h-5 text-[var(--foreground)]" />
            ) : (
              <Menu className="w-5 h-5 text-[var(--foreground)]" />
            )}
          </button>

          {/* Greeting */}
          <div className="hidden sm:block">
            <h1 className="text-lg font-semibold text-[var(--foreground)]">
              {getGreeting()}, {userName.split(' ')[0]}
            </h1>
            <p className="text-sm text-[var(--foreground-muted)] capitalize">
              {formatDate()}
            </p>
          </div>

          {/* Mobile Page Title */}
          <h1 className="sm:hidden text-lg font-semibold text-[var(--foreground)]">
            {getPageTitle()}
          </h1>
        </div>

        {/* Right Section - Actions */}
        <div className="flex items-center gap-2">
          {/* WhatsApp Unread Badge */}
          {whatsappUnread > 0 && (
            <Button
              variant="ghost"
              size="icon"
              className="relative hidden md:flex hover:bg-[var(--background-elevated)]"
              aria-label={`${whatsappUnread} unread WhatsApp messages`}
            >
              <MessageCircle className="w-5 h-5 text-[var(--foreground-secondary)]" />
              <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] text-xs font-semibold rounded-full bg-[var(--accent)] text-white">
                {whatsappUnread > 99 ? '99+' : whatsappUnread}
              </span>
            </Button>
          )}

          {/* Notifications */}
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative hover:bg-[var(--background-elevated)]"
              aria-label={`${notificationCount} notifications`}
            >
              <Bell className="w-5 h-5 text-[var(--foreground-secondary)]" />
              {notificationCount > 0 && (
                <span className="absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] text-xs font-semibold rounded-full bg-[var(--accent)] text-white">
                  {notificationCount > 99 ? '99+' : notificationCount}
                </span>
              )}
            </Button>

            {/* Notifications Dropdown */}
            {showNotifications && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowNotifications(false)}
                />
                <div className="absolute right-0 top-full mt-2 w-80 max-h-96 overflow-y-auto z-50 bg-[var(--background-secondary)] border border-[var(--border)] rounded-xl shadow-xl">
                  <div className="p-4 border-b border-[var(--border)]">
                    <h3 className="font-semibold text-[var(--foreground)]">
                      Notifiche
                    </h3>
                  </div>
                  <div className="p-4">
                    <p className="text-sm text-[var(--foreground-muted)] text-center py-4">
                      Nessuna nuova notifica
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Clock In/Out Button */}
          <Button
            onClick={onToggleClock}
            disabled={isClockLoading}
            variant="outline"
            size="sm"
            className={cn(
              'hidden sm:flex items-center gap-2 transition-all',
              isClockIn
                ? 'border-[var(--success)] text-[var(--success)] hover:bg-[var(--success)]/10'
                : 'border-[var(--border)] text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)]'
            )}
          >
            <Clock className="w-4 h-4" />
            <span className="hidden md:inline">
              {isClockLoading ? 'Loading...' : isClockIn ? 'Clock Out' : 'Clock In'}
            </span>
          </Button>

          {/* Mobile Clock Button */}
          <Button
            onClick={onToggleClock}
            disabled={isClockLoading}
            variant="ghost"
            size="icon"
            className={cn(
              'sm:hidden',
              isClockIn
                ? 'text-[var(--success)]'
                : 'text-[var(--foreground-secondary)]'
            )}
            aria-label={isClockIn ? 'Clock out' : 'Clock in'}
          >
            <Clock className="w-5 h-5" />
          </Button>
        </div>
      </div>
    </header>
  );
}
