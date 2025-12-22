'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import {
  Home,
  MessageSquare,
  MessageCircle,
  Users,
  FolderKanban,
  BookOpen,
  UserCircle,
  BarChart3,
  Settings,
  LogOut,
  ChevronDown,
} from 'lucide-react';
import { navigation, NavSection, NavItem } from '@/types/navigation';
import { cn } from '@/lib/utils';

// Icon mapping
const iconMap: Record<string, React.ElementType> = {
  Home,
  MessageSquare,
  MessageCircle,
  Users,
  FolderKanban,
  BookOpen,
  UserCircle,
  BarChart3,
  Settings,
};

interface AppSidebarProps {
  user: {
    name: string;
    email: string;
    role: string;
    team: string;
    avatar?: string;
    isOnline: boolean;
    hoursToday?: string;
  };
  unreadWhatsApp?: number;
  onLogout: () => void;
}

export function AppSidebar({ user, unreadWhatsApp = 0, onLogout }: AppSidebarProps) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/dashboard') {
      return pathname === '/dashboard';
    }
    return pathname.startsWith(href);
  };

  const renderNavItem = (item: NavItem) => {
    const Icon = iconMap[item.icon] || Home;
    const active = isActive(item.href);
    const badge = item.href === '/whatsapp' ? unreadWhatsApp : item.badge;

    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
          'text-sm font-medium group',
          active
            ? 'bg-[#63E6E2]/10 text-[#63E6E2] border border-[#63E6E2]/20 shadow-[0_0_10px_rgba(99,230,226,0.1)]'
            : 'text-[#9AA0AE] hover:text-[#4FD1C5] hover:bg-[#4FD1C5]/5'
        )}
      >
        <Icon className={cn('w-5 h-5 transition-colors', active ? 'text-[#63E6E2]' : 'text-[#9AA0AE] group-hover:text-[#4FD1C5]')} />
        <span className="flex-1">{item.title}</span>
        {badge && badge > 0 && (
          <span className="flex items-center justify-center min-w-[20px] h-5 px-1.5 text-xs font-semibold rounded-full bg-[#63E6E2] text-[#0B0E13]">
            {badge > 99 ? '99+' : badge}
          </span>
        )}
      </Link>
    );
  };

  const renderNavSection = (section: NavSection, index: number) => (
    <div key={index} className="space-y-1">
      {section.title && (
        <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[#9AA0AE] opacity-80">
          {section.title}
        </p>
      )}
      {section.items.map(renderNavItem)}
    </div>
  );

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-60 flex flex-col bg-[#0E1116] bg-gradient-to-b from-[#10131A] to-[#0B0E13] border-r border-[rgba(255,255,255,0.04)]">
      {/* Logo Section */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-[rgba(255,255,255,0.04)]">
        <div className="relative w-10 h-10">
          <Image
            src="/images/logo_zan.png"
            alt="Zerosphere"
            fill
            className="object-contain"
          />
        </div>
        <div>
          <h1 className="text-lg font-bold text-[#E6E7EB] tracking-wide">ZANTARA</h1>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {navigation.map(renderNavSection)}
      </nav>

      {/* User Profile Footer */}
      <div className="p-3 border-t border-[rgba(255,255,255,0.04)] bg-transparent">
        <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-[#4FD1C5]/5 transition-colors cursor-pointer group">
          {/* Avatar */}
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-[#1A1D24] flex items-center justify-center overflow-hidden border border-[rgba(255,255,255,0.04)]">
              {user.avatar ? (
                <Image
                  src={user.avatar}
                  alt={user.name}
                  fill
                  className="object-cover"
                />
              ) : (
                <UserCircle className="w-6 h-6 text-[#9AA0AE]" />
              )}
            </div>
            {/* Online indicator */}
            <span
              className={cn(
                'absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-[#0B0E13]',
                user.isOnline ? 'bg-[#4FD1C5]' : 'bg-[#9AA0AE]'
              )}
            />
          </div>

          {/* User Info */}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[#E6E7EB] truncate">
              {user.name}
            </p>
            <p className="text-xs text-[#9AA0AE] truncate">
              {user.team}
            </p>
          </div>

          {/* Status */}
          <div className="flex flex-col items-end text-right">
            <span
              className={cn(
                'text-xs font-medium',
                user.isOnline ? 'text-[#4FD1C5]' : 'text-[#9AA0AE]'
              )}
            >
              {user.isOnline ? 'Online' : 'Offline'}
            </span>
            {user.hoursToday && (
              <span className="text-xs text-[#9AA0AE]">
                {user.hoursToday}
              </span>
            )}
          </div>
        </div>

        {/* Logout Button */}
        <button
          onClick={onLogout}
          className="flex items-center gap-2 w-full mt-2 px-3 py-2 text-sm text-[#9AA0AE] hover:text-[#E6E7EB] hover:bg-[#4FD1C5]/10 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
