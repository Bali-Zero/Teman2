"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Home,
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
} from "lucide-react";
import {
  navigation,
  portalNavigation,
  NavSection,
  NavItem,
} from "@/types/navigation";
import { cn } from "@/lib/utils";

// Icon mapping
const iconMap: Record<string, React.ElementType> = {
  Home,
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
  navigationConfig?: NavSection[]; // Allow custom navigation
  isPortal?: boolean; // Portal mode flag
}

export function AppSidebar({
  user,
  unreadWhatsApp = 0,
  onLogout,
  navigationConfig,
  isPortal = false,
}: AppSidebarProps) {
  const pathname = usePathname();
  const nav = navigationConfig || navigation;

  const isActive = (href: string) => {
    if (!pathname) return false;
    if (href === "/dashboard" || href === "/portal") {
      return pathname === href;
    }
    return pathname.startsWith(href);
  };

  const renderNavItem = (item: NavItem) => {
    const Icon = iconMap[item.icon] || Home;
    const active = isActive(item.href);
    const badge = item.href === "/whatsapp" ? unreadWhatsApp : item.badge;

    const sharedClassName = cn(
      "flex items-center gap-2 px-2 py-[6px] rounded-[7px] mb-[1px] text-[12.5px] transition-colors group",
      active
        ? "font-medium"
        : "hover:bg-[var(--bz-surface)] hover:text-[var(--bz-text-1)]",
    );
    const sharedStyle = active
      ? { background: "rgba(212,132,90,0.10)", color: "var(--bz-accent)" }
      : { color: "var(--bz-text-2)" };

    const sharedContent = (
      <>
        <Icon
          size={15}
          className="flex-shrink-0"
          style={{ opacity: active ? 1 : 0.65 }}
        />
        <span className="flex-1">{item.title}</span>
        {item.external && (
          <ExternalLink
            size={10}
            style={{ color: "var(--bz-text-3)", opacity: 0.6 }}
          />
        )}
        {badge && badge > 0 && (
          <span
            className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
            style={{
              background: "rgba(212,132,90,0.18)",
              color: "var(--bz-accent)",
            }}
          >
            {badge > 99 ? "99+" : badge}
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
      <Link
        key={item.href}
        href={item.href}
        className={sharedClassName}
        style={sharedStyle}
      >
        {sharedContent}
      </Link>
    );
  };

  const renderNavSection = (section: NavSection, index: number) => (
    <div key={index} className="space-y-0">
      {section.title && (
        <div
          className="text-[9px] font-semibold uppercase tracking-[0.7px] px-2 pt-3 pb-1"
          style={{ color: "var(--bz-text-3)" }}
        >
          {section.title}
        </div>
      )}
      {section.items.map(renderNavItem)}
    </div>
  );

  return (
    <aside
      className="fixed left-0 top-0 z-40 h-screen flex flex-col border-r"
      style={{
        width: "var(--bz-sidebar-width, 216px)",
        background: "var(--bz-elevated)",
        borderColor: "var(--bz-border)",
      }}
    >
      {/* Workspace Picker */}
      <div
        className="p-2.5 border-b"
        style={{ borderColor: "var(--bz-border)" }}
      >
        <button className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg transition-colors hover:bg-[var(--bz-surface)]">
          <Image
            src="/static/balizero-logo-clean.png"
            alt="Bali Zero"
            width={36}
            height={36}
            className="rounded-full flex-shrink-0"
            priority
          />
          <span className="text-[10px]" style={{ color: "var(--bz-text-3)" }}>
            ⌃
          </span>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0">
        {nav.map(renderNavSection)}
      </nav>

      {/* User Profile Footer */}
      <div
        className="border-t p-2.5"
        style={{ borderColor: "var(--bz-border)" }}
      >
        <div className="flex items-center gap-2 px-1.5 py-1.5 rounded-lg hover:bg-[var(--bz-surface)] cursor-pointer transition-colors">
          <div className="relative flex-shrink-0">
            {user.avatar ? (
              <Image
                src={user.avatar}
                alt={user.name}
                width={26}
                height={26}
                className="rounded-[7px]"
              />
            ) : (
              <div
                className="w-[26px] h-[26px] rounded-[7px] flex items-center justify-center text-[10px] font-bold text-white"
                style={{
                  background:
                    "linear-gradient(135deg, #c9a96e 0%, #d4845a 100%)",
                }}
              >
                {user.name?.[0]?.toUpperCase() || "U"}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className="text-[12px] font-medium truncate"
              style={{ color: "var(--bz-text-1)" }}
            >
              {user.name}
            </div>
            <div className="text-[10px]" style={{ color: "var(--bz-text-3)" }}>
              {isPortal ? "Client Portal" : user.role || user.team || "Team"}
            </div>
          </div>
          <div
            className="w-[7px] h-[7px] rounded-full flex-shrink-0"
            style={{
              background: user.isOnline
                ? "var(--bz-green)"
                : "var(--bz-text-3)",
              boxShadow: user.isOnline
                ? "0 0 5px rgba(77,184,122,0.45)"
                : "none",
            }}
          />
        </div>
        <button
          onClick={onLogout}
          className="flex items-center gap-2 w-full mt-1 px-2 py-1.5 text-[11px] rounded-lg transition-colors"
          style={{ color: "var(--bz-text-3)" }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.color = "var(--bz-text-1)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--bz-text-3)")
          }
        >
          <LogOut size={13} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
