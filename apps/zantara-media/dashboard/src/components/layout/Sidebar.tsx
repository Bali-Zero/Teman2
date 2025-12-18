"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  Calendar,
  Send,
  BarChart3,
  Radio,
  Settings,
  Bell,
  Zap,
  Users,
  FolderOpen,
  X,
} from "lucide-react";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navigation = [
  {
    name: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    name: "Content",
    href: "/content",
    icon: FileText,
  },
  {
    name: "Calendar",
    href: "/calendar",
    icon: Calendar,
  },
  {
    name: "Distribution",
    href: "/distribution",
    icon: Send,
  },
  {
    name: "Intel Signals",
    href: "/intel",
    icon: Zap,
  },
  {
    name: "Analytics",
    href: "/analytics",
    icon: BarChart3,
  },
  {
    name: "Podcasts",
    href: "/podcasts",
    icon: Radio,
  },
  {
    name: "Assets",
    href: "/assets",
    icon: FolderOpen,
  },
];

const secondaryNavigation = [
  {
    name: "Team",
    href: "/team",
    icon: Users,
  },
  {
    name: "Notifications",
    href: "/notifications",
    icon: Bell,
  },
  {
    name: "Settings",
    href: "/settings",
    icon: Settings,
  },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 z-50 h-screen w-64 bg-[var(--background-secondary)] border-r border-[var(--border)] transition-transform duration-300 ease-in-out flex flex-col",
          isOpen ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0"
        )}
      >
        {/* Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-[var(--border)]">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/images/logo_zan.png"
              alt="ZANTARA"
              width={32}
              height={32}
              className="rounded"
            />
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-[var(--foreground)]">
                ZANTARA
              </span>
              <span className="text-[10px] text-[var(--accent)] font-medium tracking-wider">
                MEDIA
              </span>
            </div>
          </Link>
          <button
            onClick={onClose}
            className="md:hidden p-1 rounded hover:bg-[var(--background-elevated)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Main navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <div className="space-y-1">
            {navigation.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--accent)]/10 text-[var(--accent)]"
                      : "text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)] hover:text-[var(--foreground)]"
                  )}
                  onClick={onClose}
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                  {item.name === "Intel Signals" && (
                    <span className="ml-auto bg-[var(--accent)] text-white text-xs px-1.5 py-0.5 rounded-full">
                      12
                    </span>
                  )}
                </Link>
              );
            })}
          </div>

          {/* Divider */}
          <div className="my-4 border-t border-[var(--border)]" />

          {/* Secondary navigation */}
          <div className="space-y-1">
            {secondaryNavigation.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--accent)]/10 text-[var(--accent)]"
                      : "text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)] hover:text-[var(--foreground)]"
                  )}
                  onClick={onClose}
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--border)]">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
            <div className="w-8 h-8 rounded-full bg-[var(--accent)]/10 flex items-center justify-center">
              <span className="text-sm font-semibold text-[var(--accent)]">
                Z
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--foreground)] truncate">
                Zero
              </p>
              <p className="text-xs text-[var(--foreground-muted)] truncate">
                Editor-in-Chief
              </p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
