'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { api } from '@/lib/api';
import {
  LayoutDashboard,
  Plane,
  Building2,
  Receipt,
  FileText,
  MessageSquare,
  Settings,
  LogOut,
  Menu,
  X,
  UserCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface PortalLayoutProps {
  children: React.ReactNode;
}

interface NavItem {
  href: string;
  label: string;
  icon: string;
  cssClass: string;
  activeColor: string;
}

const navItems: NavItem[] = [
  { href: '/portal', label: 'Dashboard', icon: 'LayoutDashboard', cssClass: 'nav-icon-teal', activeColor: '#2DD4BF' },
  { href: '/portal/visa', label: 'Visa & Immigration', icon: 'Plane', cssClass: 'nav-icon-emerald', activeColor: '#34D399' },
  { href: '/portal/company', label: 'Company', icon: 'Building2', cssClass: 'nav-icon-blue', activeColor: '#60A5FA' },
  { href: '/portal/taxes', label: 'Taxes', icon: 'Receipt', cssClass: 'nav-icon-amber', activeColor: '#FBBF24' },
  { href: '/portal/documents', label: 'Documents', icon: 'FileText', cssClass: 'nav-icon-violet', activeColor: '#C084FC' },
  { href: '/portal/messages', label: 'Messages', icon: 'MessageSquare', cssClass: 'nav-icon-sky', activeColor: '#38BDF8' },
  { href: '/portal/settings', label: 'Settings', icon: 'Settings', cssClass: 'nav-icon-gray', activeColor: '#9CA3AF' },
];

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard,
  Plane,
  Building2,
  Receipt,
  FileText,
  MessageSquare,
  Settings,
};

export default function PortalLayout({ children }: PortalLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState({
    name: '',
    email: '',
    role: '',
  });

  // Check client authentication
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = api.getToken();
        if (!token) {
          router.push('/login');
          return;
        }

        const storedProfile = api.getUserProfile();
        if (storedProfile) {
          // Verify user is a client
          if (storedProfile.role !== 'client') {
            router.push('/dashboard');
            return;
          }
          setUser({
            name: storedProfile.name || storedProfile.email.split('@')[0],
            email: storedProfile.email,
            role: storedProfile.role,
          });
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        router.push('/login');
      } finally {
        setIsLoading(false);
      }
    };

    const timeoutId = setTimeout(checkAuth, 100);
    return () => clearTimeout(timeoutId);
  }, [router]);

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      router.push('/login');
    }
  };

  const isActive = (href: string) => {
    if (href === '/portal') {
      return pathname === '/portal';
    }
    return pathname?.startsWith(href);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#2a2a2a]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[#4FD1C5] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[#9AA0AE]">Loading portal...</p>
        </div>
      </div>
    );
  }

  const renderNavItem = (item: NavItem) => {
    const Icon = iconMap[item.icon] || LayoutDashboard;
    const active = isActive(item.href);

    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
          'text-sm font-medium group',
          active
            ? 'bg-white/5 border border-white/10'
            : 'text-[#9AA0AE] hover:bg-white/5'
        )}
        style={{
          color: active ? item.activeColor : undefined,
          borderColor: active ? `${item.activeColor}20` : undefined,
        }}
      >
        <Icon
          className={cn('w-5 h-5', !active && item.cssClass)}
          style={active ? { color: item.activeColor } : undefined}
        />
        <span
          className={cn(
            'flex-1 transition-colors',
            !active && 'group-hover:text-[#E6E7EB]'
          )}
          style={{ color: active ? item.activeColor : undefined }}
        >
          {item.label}
        </span>
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-[#2a2a2a]">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-60 md:flex-col md:fixed md:inset-y-0 bg-[#242424] border-r border-white/5">
        {/* Logo Section */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-[rgba(255,255,255,0.04)]">
          <div className="relative w-10 h-10">
            <Image
              src="/assets/logo/logo_zan.png"
              alt="Zantara"
              fill
              className="object-contain"
            />
          </div>
          <div>
            <h1 className="text-lg font-bold text-[#E6E7EB] tracking-wide">ZANTARA</h1>
            <span className="text-xs text-[#4FD1C5]">Client Portal</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {navItems.map(renderNavItem)}
        </nav>

        {/* User Profile Footer */}
        <div className="p-3 border-t border-[rgba(255,255,255,0.04)] bg-transparent">
          <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-[#4FD1C5]/5 transition-colors cursor-pointer group">
            {/* Avatar */}
            <div className="relative">
              <div className="w-10 h-10 rounded-full bg-[#1A1D24] flex items-center justify-center overflow-hidden border border-[rgba(255,255,255,0.04)]">
                <UserCircle className="w-6 h-6 text-[#9AA0AE]" />
              </div>
              {/* Online indicator */}
              <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-[#242424] bg-[#4FD1C5]" />
            </div>

            {/* User Info */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[#E6E7EB] truncate">
                {user.name}
              </p>
              <p className="text-xs text-[#9AA0AE] truncate">
                {user.email}
              </p>
            </div>
          </div>

          {/* Logout Button */}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full mt-2 px-3 py-2 text-sm text-[#9AA0AE] hover:text-[#E6E7EB] hover:bg-[#4FD1C5]/10 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 h-16 bg-[#242424] border-b border-white/5 flex items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="relative w-8 h-8">
            <Image
              src="/assets/logo/logo_zan.png"
              alt="Zantara"
              fill
              className="object-contain"
            />
          </div>
          <div>
            <span className="text-lg font-bold text-[#E6E7EB]">ZANTARA</span>
            <span className="ml-2 text-xs text-[#4FD1C5]">Portal</span>
          </div>
        </div>
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="p-2 text-[#9AA0AE] hover:bg-white/5 rounded-lg"
        >
          {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40 md:hidden"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 w-60 bg-[#242424] z-50 md:hidden flex flex-col">
            <div className="flex items-center gap-3 h-16 px-4 border-b border-white/5">
              <div className="relative w-8 h-8">
                <Image
                  src="/assets/logo/logo_zan.png"
                  alt="Zantara"
                  fill
                  className="object-contain"
                />
              </div>
              <span className="text-lg font-bold text-[#E6E7EB]">ZANTARA</span>
            </div>
            <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
              {navItems.map((item) => {
                const Icon = iconMap[item.icon] || LayoutDashboard;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                      'text-sm font-medium',
                      active
                        ? 'bg-white/5 border border-white/10'
                        : 'text-[#9AA0AE] hover:bg-white/5 hover:text-[#E6E7EB]'
                    )}
                    style={{
                      color: active ? item.activeColor : undefined,
                      borderColor: active ? `${item.activeColor}20` : undefined,
                    }}
                  >
                    <Icon
                      className="w-5 h-5"
                      style={active ? { color: item.activeColor } : undefined}
                    />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
            <div className="p-3 border-t border-white/5">
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[#9AA0AE] hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </>
      )}

      {/* Main Content */}
      <main className="md:ml-60 pt-16 md:pt-0 min-h-screen">
        <div className="p-4 md:p-6 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
