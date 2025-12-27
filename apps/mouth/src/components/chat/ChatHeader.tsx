'use client';

import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import {
  Clock,
  User,
  Menu,
  Shield,
  Bell,
  ChevronDown,
  LogOut,
  Settings,
  Camera,
  Loader2,
} from 'lucide-react';

export interface ChatHeaderProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  isClockIn: boolean;
  isClockLoading: boolean;
  onToggleClock: () => void;
  messagesCount: number;
  isWsConnected: boolean;
  userName: string;
  userAvatar: string | null;
  showUserMenu: boolean;
  onToggleUserMenu: () => void;
  userMenuRef: React.RefObject<HTMLDivElement | null>;
  avatarInputRef: React.RefObject<HTMLInputElement | null>;
  onAvatarUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onShowToast: (message: string, type: 'success' | 'error') => void;
}

export function ChatHeader({
  isSidebarOpen,
  onToggleSidebar,
  isClockIn,
  isClockLoading,
  onToggleClock,
  messagesCount,
  isWsConnected,
  userName,
  userAvatar,
  showUserMenu,
  onToggleUserMenu,
  userMenuRef,
  avatarInputRef,
  onAvatarUpload,
  onShowToast,
}: ChatHeaderProps) {
  const router = useRouter();

  const handleLogout = async () => {
    if (!window.confirm('Are you sure you want to logout?')) return;
    try {
      await api.logout();
    } finally {
      router.push('/login');
    }
  };

  return (
    <header className="h-14 border-b border-[var(--border)] bg-[var(--background)] flex-shrink-0">
      <div className="h-full max-w-5xl mx-auto px-4 md:px-6 flex items-center justify-between">
        {/* Left: Menu + Clock In */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSidebar}
            aria-label={isSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
            className="flex-shrink-0"
          >
            <Menu className="w-5 h-5" />
          </Button>
          <Button
            onClick={onToggleClock}
            variant={isClockIn ? 'default' : 'outline'}
            size="sm"
            disabled={isClockLoading}
            className={`gap-2 ${isClockIn ? 'bg-[var(--success)] hover:bg-[var(--success)]/90' : ''}`}
          >
            {isClockLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Clock className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">{isClockIn ? 'Clock Out' : 'Clock In'}</span>
            {isClockIn && <span className="w-2 h-2 rounded-full bg-white animate-pulse" />}
          </Button>
        </div>

        {/* Center: Logo */}
        <div
          className={`absolute left-1/2 -translate-x-1/2 transition-all duration-500 ease-in-out ${
            messagesCount > 0
              ? 'opacity-100 translate-y-0'
              : 'opacity-0 -translate-y-4 pointer-events-none'
          }`}
        >
          <Image
            src="/images/logo_zan.png"
            alt="Zantara"
            width={64}
            height={64}
            className="drop-shadow-[0_0_15px_rgba(255,255,255,0.4)] hover:scale-110 transition-transform duration-300"
          />
        </div>

        {/* Right: Notifications + Avatar */}
        <div className="flex items-center gap-2">
          {/* WS Connection indicator */}
          {isWsConnected && (
            <span
              className="w-2 h-2 rounded-full bg-green-500 hidden sm:block"
              title="Real-time connected"
            />
          )}

          {/* Notifications */}
          <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
            <Bell className="w-5 h-5" />
          </Button>

          {/* User Avatar with Dropdown Menu */}
          <input
            type="file"
            ref={avatarInputRef}
            onChange={onAvatarUpload}
            accept="image/*"
            className="hidden"
            aria-label="Upload avatar image"
          />
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={onToggleUserMenu}
              className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-[var(--background-elevated)] transition-colors"
              aria-label="User menu"
            >
              <div className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-white font-medium overflow-hidden relative">
                {userAvatar ? (
                  <Image
                    src={userAvatar}
                    alt="User avatar"
                    fill
                    className="object-cover"
                    sizes="32px"
                  />
                ) : userName ? (
                  userName.charAt(0).toUpperCase()
                ) : (
                  <User className="w-4 h-4" />
                )}
              </div>
              <ChevronDown
                className={`w-4 h-4 text-[var(--foreground-muted)] hidden sm:block transition-transform ${showUserMenu ? 'rotate-180' : ''}`}
              />
            </button>

            {/* User Dropdown Menu */}
            {showUserMenu && (
              <div className="absolute right-0 top-full mt-2 w-56 bg-[var(--background-secondary)] rounded-xl border border-[var(--border)] shadow-lg overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200 z-50">
                {/* User Info */}
                <div className="px-4 py-3 border-b border-[var(--border)]">
                  <p className="text-sm font-medium text-[var(--foreground)]">
                    {userName || 'User'}
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">Online</p>
                </div>

                {/* Menu Items */}
                <div className="py-1">
                  <button
                    onClick={() => {
                      avatarInputRef.current?.click();
                      onToggleUserMenu();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--background-elevated)] transition-colors text-sm text-[var(--foreground)]"
                  >
                    <Camera className="w-4 h-4" />
                    Change Avatar
                  </button>
                  <button
                    onClick={() => {
                      onShowToast('Settings coming soon!', 'success');
                      onToggleUserMenu();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--background-elevated)] transition-colors text-sm text-[var(--foreground)]"
                  >
                    <Settings className="w-4 h-4" />
                    Settings
                  </button>
                  {api.isAdmin() && (
                    <button
                      onClick={() => {
                        router.push('/admin');
                        onToggleUserMenu();
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--background-elevated)] transition-colors text-sm text-[var(--foreground)]"
                    >
                      <Shield className="w-4 h-4" />
                      Admin Dashboard
                    </button>
                  )}
                </div>

                {/* Logout */}
                <div className="border-t border-[var(--border)] py-1">
                  <button
                    onClick={() => {
                      onToggleUserMenu();
                      handleLogout();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--error)]/10 transition-colors text-sm text-[var(--error)]"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
