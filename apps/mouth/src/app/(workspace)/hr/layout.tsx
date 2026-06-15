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
import { SubNav, type SubNavItem } from "@balizero/core";

type NavItem = SubNavItem & {
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
  {
    href: "/hr/owner-cashout",
    label: "Owner Cashout",
    icon: Lock,
    adminOnly: false,
    ownerOnly: true,
  },
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

  const subNav = { items: navItems, pathname, rootHref: "/hr", linkAs: Link };

  return (
    <div className="flex flex-col md:flex-row h-full">
      {/* Desktop sidebar */}
      <nav className="w-56 border-r border-zinc-800 bg-zinc-950/50 p-4 space-y-1 hidden md:block flex-shrink-0">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4 px-3">
          HR / Payroll
        </h2>
        <SubNav {...subNav} variant="sidebar" />
      </nav>

      {/* Mobile navigation */}
      <nav className="md:hidden flex gap-1 overflow-x-auto px-4 py-2 border-b border-zinc-800 bg-zinc-950/50 flex-shrink-0 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        <SubNav {...subNav} variant="chips" />
      </nav>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-6">{children}</div>
    </div>
  );
}
