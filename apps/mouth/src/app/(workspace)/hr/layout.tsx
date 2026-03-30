"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Banknote,
  Gift,
  Calendar,
  Settings,
  LayoutDashboard,
  Users,
} from "lucide-react";

const navItems = [
  { href: "/hr", label: "Dashboard", icon: LayoutDashboard },
  { href: "/hr/employees", label: "Employees", icon: Users },
  { href: "/hr/bonuses", label: "Bonuses", icon: Gift },
  { href: "/hr/payroll", label: "Payroll", icon: Banknote },
  { href: "/hr/leave", label: "Leave", icon: Calendar },
  { href: "/hr/settings", label: "Settings", icon: Settings },
];

export default function HRLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col md:flex-row h-full">
      {/* Desktop sidebar */}
      <nav className="w-56 border-r border-zinc-800 bg-zinc-950/50 p-4 space-y-1 hidden md:block flex-shrink-0">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4 px-3">
          HR / Payroll
        </h2>
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/hr" && pathname?.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              }`}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Mobile navigation */}
      <nav className="md:hidden flex gap-1 overflow-x-auto px-4 py-2 border-b border-zinc-800 bg-zinc-950/50 flex-shrink-0 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/hr" && pathname?.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? "bg-[var(--bz-accent)]/15 text-[var(--bz-accent)] border border-[var(--bz-accent)]/30"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 border border-transparent"
              }`}
            >
              <Icon size={14} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-6">{children}</div>
    </div>
  );
}
