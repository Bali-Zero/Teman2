'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Banknote,
  Gift,
  Calendar,
  Settings,
  LayoutDashboard,
} from 'lucide-react';

const navItems = [
  { href: '/hr', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/hr/bonuses', label: 'Bonuses', icon: Gift },
  { href: '/hr/payroll', label: 'Payroll', icon: Banknote },
  { href: '/hr/leave', label: 'Leave', icon: Calendar },
  { href: '/hr/settings', label: 'Settings', icon: Settings },
];

export default function HRLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full">
      {/* HR Sub-Navigation */}
      <nav className="w-56 border-r border-zinc-800 bg-zinc-950/50 p-4 space-y-1 hidden md:block">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4 px-3">
          HR / Payroll
        </h2>
        {navItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/hr' && pathname?.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
              }`}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-6">
        {children}
      </div>
    </div>
  );
}
