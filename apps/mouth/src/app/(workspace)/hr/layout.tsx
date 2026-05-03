"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Banknote,
  Gift,
  Calendar,
  Lock,
  Settings,
  LayoutDashboard,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { isHRAdmin } from "@/lib/hr/admin";
import { isOwner } from "@/lib/auth/owner";

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  adminOnly: boolean;
  ownerOnly?: boolean;
};

const allNavItems: NavItem[] = [
  { href: "/hr", label: "Dashboard", icon: LayoutDashboard, adminOnly: false },
  { href: "/hr/employees", label: "Employees", icon: Users, adminOnly: true },
  { href: "/hr/bonuses", label: "Bonuses", icon: Gift, adminOnly: false },
  { href: "/hr/payroll", label: "Payroll", icon: Banknote, adminOnly: false },
  { href: "/hr/leave", label: "Leave", icon: Calendar, adminOnly: false },
  { href: "/hr/settings", label: "Settings", icon: Settings, adminOnly: true },
  { href: "/hr/owner-cashout", label: "Owner Cashout", icon: Lock, adminOnly: false, ownerOnly: true },
];

export default function HRLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isAdmin, setIsAdmin] = useState(false);
  const [isOwnerUser, setIsOwnerUser] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((user) => {
        setIsAdmin(isHRAdmin(user));
        setIsOwnerUser(isOwner(user?.email));
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const navItems = loaded
    ? allNavItems.filter((item) => {
        if (item.adminOnly && !isAdmin) return false;
        if (item.ownerOnly && !isOwnerUser) return false;
        return true;
      })
    : allNavItems.filter((item) => !item.adminOnly && !item.ownerOnly);

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
