'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import {
  Home,
  Inbox,
  MessageSquare,
  MessageCircle,
  Mail,
  Users,
  FolderKanban,
  FolderOpen,
  BookOpen,
  UserCircle,
  BarChart3,
  Settings,
  LogOut,
  Activity,
  Briefcase,
  FileText,
  Cloud,
  Calendar,
  ExternalLink,
  ClipboardCheck,
  Banknote,
  Terminal,
  Handshake,
} from 'lucide-react';
import { navigation, portalNavigation, NavSection, NavItem } from '@/types/navigation';
import { cn } from '@/lib/utils';

// Icon mapping
const iconMap: Record<string, React.ElementType> = {
  Home,
  Inbox,
  MessageSquare,
  MessageCircle,
  Mail,
  Users,
  FolderKanban,
  FolderOpen,
  BookOpen,
  UserCircle,
  BarChart3,
  Settings,
  Activity,
  Briefcase,
  FileText,
  Cloud,
  Calendar,
  ClipboardCheck,
  Banknote,
  Terminal,
  Handshake,
};

interface AppSidebarProps {
  user: {
    name: string;
    email: string;
    role?: string;
    team?: string;
    avatar?: string;
    isOnline?: boolean;
    hoursToday?: string;
  };
  unreadWhatsApp?: number;
  onLogout: () => void;
  navigationConfig?: NavSection[];
  isPortal?: boolean;
  ariaLabel?: string;
}

export function AppSidebar({
  user,
  unreadWhatsApp = 0,
  onLogout,
  navigationConfig,
  isPortal = false,
  ariaLabel = 'Primary',
}: AppSidebarProps) {
  const pathname = usePathname();
  const nav = navigationConfig || navigation;

  const isActive = (href: string) => {
    if (!pathname) return false;
    if (href === '/dashboard' || href === '/portal') {
      return pathname === href;
    }
    return pathname.startsWith(href);
  };

  const renderNavItem = (item: NavItem) => {
    const Icon = iconMap[item.icon] || Home;
    const active = isActive(item.href);
    const badge = item.href === '/whatsapp' ? unreadWhatsApp : item.badge;

    const sharedClassName = cn(
      'flex items-center gap-2.5 px-2.5 py-[7px] rounded-[8px] mb-[2px] text-[11.5px] font-medium uppercase tracking-[0.5px] transition-all group',
      active ? 'font-semibold' : 'hover:bg-[rgba(255,255,255,0.05)] hover:text-[var(--bz-text-1)]'
    );
    const sharedStyle = active
      ? { background: 'rgba(212,132,90,0.12)', color: 'var(--bz-accent)' }
      : { color: 'var(--bz-text-2)' };

    const sharedContent = (
      <>
        <Icon size={15} className="flex-shrink-0" style={{ opacity: active ? 1 : 0.7 }} />
        <span className="flex-1 leading-relaxed">{item.title}</span>
        {item.external && (
          <ExternalLink size={9} style={{ color: 'var(--bz-text-3)', opacity: 0.5 }} />
        )}
        {badge && badge > 0 && (
          <span
            className="text-[8px] font-bold px-1.5 py-0.5 rounded-full"
            style={{
              background: 'rgba(212,132,90,0.18)',
              color: 'var(--bz-accent)',
            }}
          >
            {badge > 99 ? '99+' : badge}
          </span>
        )}
      </>
    );

    if (item.external) {
      return (
        <a
          key={item.href}
          href={item.href}
          target="_blank"
          rel="noopener noreferrer"
          className={sharedClassName}
          style={sharedStyle}
        >
          {sharedContent}
        </a>
      );
    }

    return (
      <Link key={item.href} href={item.href} className={sharedClassName} style={sharedStyle}>
        {sharedContent}
      </Link>
    );
  };

  const renderNavSection = (section: NavSection, index: number) => (
    <div key={index}>
      {section.title && (
        // bz-text-2 (#8c8884 → ~5.0:1 on glass-panel-deep) without opacity
        // multiplier — keeps the muted look while satisfying WCAG AA 4.5:1.
        <div
          className="text-[8.5px] font-bold uppercase tracking-[1.2px] px-2.5 pt-4 pb-1.5"
          style={{ color: 'var(--bz-text-2)' }}
        >
          {section.title}
        </div>
      )}
      {section.items.map(renderNavItem)}
    </div>
  );

  return (
    <aside
      id="workspace-mobile-nav"
      aria-label={ariaLabel}
      className="fixed left-0 top-0 z-40 h-screen flex flex-col border-r transition-all duration-300 glass-panel-deep"
      style={{
        width: 'var(--bz-sidebar-width, 216px)',
        borderColor: 'var(--bz-border)',
      }}
    >
      {/* Logo Header — Centered, 2x scale */}
      <div
        className="border-b flex items-center justify-center py-4 px-3"
        style={{ borderColor: 'var(--bz-border)' }}
      >
        <Link
          href={isPortal ? '/portal' : '/dashboard'}
          aria-label="Bali Zero — workspace home"
          className="flex items-center justify-center transition-opacity hover:opacity-80"
        >
          <Image
            src="/static/balizero-logo-clean.png"
            alt=""
            width={144}
            height={144}
            className="rounded-full"
            priority
          />
        </Link>
      </div>

      {/* Navigation */}
      <nav aria-label={ariaLabel} className="flex-1 overflow-y-auto px-2 py-3">
        {nav.map(renderNavSection)}
      </nav>

      {/* User Profile Footer */}
      <div className="border-t p-2.5" style={{ borderColor: 'var(--bz-border)' }}>
        <div className="flex items-center gap-2.5 px-1.5 py-1.5 rounded-lg hover:bg-[rgba(255,255,255,0.05)] cursor-pointer transition-colors">
          <div className="relative flex-shrink-0">
            {user.avatar ? (
              <Image
                src={user.avatar}
                alt={user.name}
                width={28}
                height={28}
                className="rounded-[8px]"
              />
            ) : (
              <div
                className="w-[28px] h-[28px] rounded-[8px] flex items-center justify-center text-[10px] font-bold text-white"
                style={{
                  background: 'linear-gradient(135deg, #c9a96e 0%, #d4845a 100%)',
                }}
              >
                {user.name?.[0]?.toUpperCase() || 'U'}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className="text-[11.5px] font-semibold uppercase tracking-[0.3px] truncate"
              style={{ color: 'var(--bz-text-1)' }}
            >
              {user.name}
            </div>
            <div
              className="text-[9.5px] uppercase tracking-[0.5px]"
              style={{ color: 'var(--bz-text-2)' }}
            >
              {isPortal ? 'Client Portal' : user.role || user.team || 'Team'}
            </div>
          </div>
          <div
            className="w-[7px] h-[7px] rounded-full flex-shrink-0"
            style={{
              background: user.isOnline ? 'var(--bz-green)' : 'var(--bz-text-3)',
              boxShadow: user.isOnline ? '0 0 6px rgba(77,184,122,0.45)' : 'none',
            }}
          />
        </div>
        <button
          onClick={onLogout}
          className="flex items-center gap-2 w-full mt-1 px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-[0.5px] rounded-lg transition-colors"
          style={{ color: 'var(--bz-text-2)' }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--bz-text-1)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--bz-text-2)')}
        >
          <LogOut size={13} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
