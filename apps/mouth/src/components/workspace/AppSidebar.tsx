"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Archive,
  Building2,
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
  BotMessageSquare,
  Receipt,
} from "lucide-react";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { navigation, NavSection, NavItem } from "@/types/navigation";
import { cn } from "@/lib/utils";
import { isOwner } from "@/lib/auth/owner";

// Icon mapping
const iconMap: Record<string, React.ElementType> = {
  Archive,
  Building2,
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
  BotMessageSquare,
  Receipt,
};

interface AppSidebarProps {
  id?: string;
  user: {
    name: string;
    email: string;
    role?: string;
    team?: string;
    avatar?: string;
  };
  reviewCount?: number;
  onLogout: () => void;
  navigationConfig?: NavSection[];
  isPortal?: boolean;
  ariaLabel?: string;
  onZantaraToggle?: () => void;
  isZantaraOpen?: boolean;
}

export function AppSidebar({
  id,
  user,
  reviewCount = 0,
  onLogout,
  navigationConfig,
  isPortal = false,
  ariaLabel = "Primary",
  onZantaraToggle,
  isZantaraOpen = false,
}: AppSidebarProps) {
  const pathname = usePathname();
  const nav = (navigationConfig || navigation).filter(
    (section) => !section.ownerOnly || isOwner(user.email),
  );

  const isActive = (href: string) => {
    if (!pathname) return false;
    if (href === "/dashboard" || href === "/portal") {
      return pathname === href;
    }
    return pathname.startsWith(href);
  };

  // Shared border/hairline colour for the workspace rail (K1c-bis): the
  // portal keeps its warm-paper --bz-border unchanged.
  const railEdgeColor = isPortal ? "var(--bz-border)" : "var(--nav-edge)";

  const renderNavItem = (item: NavItem, ordinal?: string) => {
    const Icon = iconMap[item.icon] || Home;
    const active = isActive(item.href);
    const badge = item.href === "/review" ? reviewCount : item.badge;

    // R19 kita rail v2 (K1c-bis): the workspace rail is now permanently ink
    // (globals.css --nav-rail-bg, invariant across light/dark — "the rail
    // is ink in BOTH themes"). A copper LEFT RULE still marks the active
    // item, now 3px per the frozen render, and a running Fraunces ordinal
    // (see workspaceContent below) replaces the lucide icon entirely. The
    // portal branch immediately below is untouched: paper, an icon, 40px
    // rows.
    const workspaceClassName = cn(
      "flex items-center gap-[9px] h-[31px] [@media(hover:none)]:h-11 pl-[11px] pr-[9px] mb-[2px] border-l-[3px] text-[11px] font-semibold transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nav-rule)]",
      active
        ? "font-bold border-[var(--nav-rule)] bg-[var(--nav-active-wash)]"
        : "border-transparent hover:bg-[var(--nav-active-wash)] hover:text-[var(--nav-fg)]",
    );
    // R19 portal rail: hairline paper, 40px rows, copper left rule on active.
    const portalClassName = cn(
      "flex items-center gap-2.5 h-10 px-2.5 rounded-[0.25rem] mb-[2px] text-[14px] font-medium border-l-2 transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bz-base)]",
      active
        ? "text-[var(--tx-pure)] bg-[var(--bz-card)] border-[var(--bz-copper)]"
        : "text-[var(--tx-secondary)] border-transparent hover:bg-[var(--bz-card)] hover:text-[var(--tx-pure)]",
    );
    const sharedClassName = isPortal ? portalClassName : workspaceClassName;
    const workspaceStyle = active
      ? { color: "var(--nav-fg)" }
      : { color: "var(--nav-fg-muted)" };
    const sharedStyle = isPortal ? undefined : workspaceStyle;

    const portalContent = (
      <>
        <Icon
          size={15}
          className="flex-shrink-0"
          style={{ opacity: active ? 1 : 0.65 }}
        />
        <span className="flex-1 leading-relaxed">{item.title}</span>
        {item.external && (
          <ExternalLink
            size={9}
            style={{ color: "var(--bz-text-3)", opacity: 0.5 }}
          />
        )}
        {badge && badge > 0 && (
          <span className="ml-auto text-[10px] font-[650] text-[var(--bz-copper)] tabular-nums">
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </>
    );

    // The workspace row has no icon slot: the ordinal glyph takes its place
    // ("the ordinal replaces the lucide icon in the workspace rail").
    // `ordinal` is undefined for an item inside an ownerOnly section — see
    // renderNavSection — so that row renders with no glyph rather than a
    // shifted number. `aria-hidden` keeps the glyph out of the link's
    // accessible name, which stays just the title (e.g. "Dashboard", not
    // "01 Dashboard").
    const workspaceContent = (
      <>
        {ordinal !== undefined && (
          <span
            aria-hidden="true"
            className="w-6 flex-shrink-0 text-center tabular-nums"
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 450,
              fontVariationSettings: '"opsz" 144',
              fontSize: "18px",
              letterSpacing: "-0.02em",
              color: "inherit",
            }}
          >
            {ordinal}
          </span>
        )}
        <span className="flex-1 leading-relaxed">
          {item.title}
          {item.external && (
            <>
              <span
                aria-hidden="true"
                className="ml-[5px] text-[11px] opacity-90"
              >
                ↗
              </span>
              <span className="sr-only"> (opens in a new tab)</span>
            </>
          )}
        </span>
        {badge && badge > 0 && (
          // The rail copper reads 4.89:1 on the bare ink, but only 4.12:1
          // once the row takes its 6% paper hover wash — and 17px/450 is not
          // large text. So the badge lifts to paper on hover, the same place
          // the row's own label goes, rather than staying copper on a ground
          // that has moved under it.
          <span
            className={cn(
              "tabular-nums",
              active
                ? "text-[var(--nav-fg)]"
                : "text-[var(--nav-rule)] group-hover:text-[var(--nav-fg)]",
            )}
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 450,
              fontSize: "17px",
            }}
          >
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </>
    );

    const sharedContent = isPortal ? portalContent : workspaceContent;

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
        // Protected RSC prefetches can race portal auth hydration in WebKit.
        // Explicit clicks keep normal client-side navigation semantics.
        prefetch={isPortal ? false : undefined}
        className={sharedClassName}
        style={sharedStyle}
      >
        {sharedContent}
      </Link>
    );
  };

  // The rail numbers visible items 01..13 with a single counter that runs
  // across ALL non-ownerOnly sections without resetting per group (K1c-bis:
  // "the ordinal is a running index ... it does NOT restart per group").
  // ownerOnly sections (only ever visible to the owner) are skipped for
  // numbering so one person's extra "Da fare" section cannot shift anyone
  // else's numbers. Portal rows never carry an ordinal at all.
  let ordinalCounter = 0;

  const renderNavSection = (section: NavSection, index: number) => (
    <div key={index}>
      {section.title && (
        // More muted section headers — "structure felt not seen"
        <div
          className={
            isPortal
              ? "text-[9px] font-[650] uppercase tracking-[.16em] text-[var(--tx-secondary)] px-3 pt-[18px] pb-2"
              : "text-[9px] font-bold uppercase tracking-[.16em] pt-[9px] px-[11px] pb-1"
          }
          style={isPortal ? undefined : { color: "var(--nav-rule)" }}
        >
          {section.title}
        </div>
      )}
      {section.note && (
        <div
          className="text-[8px] px-2.5 pb-1.5 leading-snug"
          style={{
            color: isPortal ? "var(--bz-text-3)" : "var(--nav-fg-muted)",
          }}
        >
          {section.note}
        </div>
      )}
      {section.items.map((item) => {
        if (isPortal || section.ownerOnly) {
          return renderNavItem(item, undefined);
        }
        ordinalCounter += 1;
        return renderNavItem(item, String(ordinalCounter).padStart(2, "0"));
      })}
    </div>
  );

  return (
    <aside
      id={id}
      aria-label={ariaLabel}
      className={cn(
        "fixed left-0 top-0 z-40 h-screen flex flex-col border-r transition-all duration-300",
        isPortal ? "bg-[var(--bz-base)]" : "bg-[var(--nav-rail-bg)]",
      )}
      style={{
        width: "var(--bz-sidebar-width, 216px)",
        borderColor: railEdgeColor,
      }}
    >
      {/* Logo Header */}
      <div
        className={cn(
          "border-b flex items-center",
          isPortal ? "px-[18px]" : "justify-center px-3",
        )}
        style={{
          height: isPortal
            ? "var(--bz-header-height, 64px)"
            : "var(--bz-header-height, 48px)",
          borderColor: railEdgeColor,
        }}
      >
        <Link
          href={isPortal ? "/portal" : "/dashboard"}
          // Apply the same protected-route rule to the workspace home link.
          prefetch={isPortal ? false : undefined}
          aria-label="Bali Zero — workspace home"
          className={cn(
            "flex items-center transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
            // Both the ring AND its offset have to answer to the ground the
            // ring sits on. --border-focus is the paper-ground copper #a44b36,
            // which reads 2.46:1 against the ink rail and fails SC 1.4.11's
            // 3:1 for a focus indicator; --nav-rule is the rail's own copper
            // and reads 4.89:1 there.
            isPortal
              ? "gap-2.5 rounded-[0.25rem] focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-[var(--bz-base)]"
              : "justify-center rounded-full focus-visible:ring-[var(--nav-rule)] focus-visible:ring-offset-[var(--nav-rail-bg)]",
          )}
        >
          <BZLogo
            variant="full"
            size={isPortal ? 28 : 36}
            className={isPortal ? undefined : "rounded-full"}
            priority
          />
          {isPortal && (
            <span className="flex flex-col leading-none">
              <span className="text-[17px] font-medium tracking-[-0.01em] text-[var(--tx-pure)] [font-family:var(--font-serif)]">
                Bali Zero
              </span>
              <span className="mt-[5px] text-[9px] font-[650] uppercase tracking-[.16em] text-[var(--tx-secondary)]">
                Client portal
              </span>
            </span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav aria-label={ariaLabel} className="flex-1 overflow-y-auto px-2 py-3">
        {nav.map(renderNavSection)}
      </nav>

      {/* User Profile Footer */}
      <div className="border-t p-2.5" style={{ borderColor: railEdgeColor }}>
        {/* Zantara toggle button */}
        {onZantaraToggle && (
          <button
            onClick={onZantaraToggle}
            className={cn(
              "flex items-center gap-2.5 w-full px-2.5 py-[7px] mb-1.5 border-l-2 text-[11.5px] font-medium uppercase tracking-[0.5px] transition-colors focus-visible:outline-none focus-visible:ring-2",
              isPortal
                ? "focus-visible:ring-[var(--bz-copper)]"
                : "focus-visible:ring-[var(--nav-rule)]",
              isZantaraOpen
                ? isPortal
                  ? "bg-[var(--bz-card)] border-[var(--bz-copper)]"
                  : "bg-[var(--nav-active-wash)] border-[var(--nav-rule)]"
                : isPortal
                  ? "border-transparent hover:bg-[var(--bz-card)]"
                  : "border-transparent hover:bg-[var(--nav-active-wash)]",
            )}
            style={{
              color: isZantaraOpen
                ? isPortal
                  ? "var(--tx-pure)"
                  : "var(--nav-fg)"
                : isPortal
                  ? "var(--tx-secondary)"
                  : "var(--nav-fg-muted)",
            }}
            aria-label="Toggle Zantara AI"
          >
            <BotMessageSquare
              size={15}
              className="flex-shrink-0"
              style={{ opacity: isZantaraOpen ? 1 : 0.65 }}
            />
            <span className="flex-1 leading-relaxed text-left">Zantara</span>
            <span
              className="text-[8px] font-medium"
              style={{
                color: isPortal ? "var(--tx-secondary)" : "var(--nav-fg-muted)",
              }}
            >
              ⌘J
            </span>
          </button>
        )}

        <div
          className={cn(
            "flex items-center gap-2.5 px-1.5 py-1.5 rounded-lg cursor-pointer transition-colors",
            // --surface-raised is the warm CARD (#fffcf7 light): on the ink
            // rail that hover would flash a paper block. The rail hovers
            // with its own 6% paper wash, the portal keeps the card.
            isPortal
              ? "hover:bg-[var(--surface-raised)]"
              : "hover:bg-[var(--nav-active-wash)]",
          )}
        >
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
                className={
                  isPortal
                    ? "w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-[650] text-[var(--tx-pure)]"
                    : "w-[28px] h-[28px] rounded-[8px] flex items-center justify-center text-[10px] font-bold"
                }
                // The render's rail avatar is a 14% paper wash carrying paper
                // text; --bz-wash is the warm #eae3d8, which would sit on the
                // ink rail as a bright cream chip. The portal keeps it.
                style={
                  isPortal
                    ? { background: "var(--bz-wash, var(--bz-elevated))" }
                    : {
                        background:
                          "color-mix(in srgb, var(--nav-fg) 14%, transparent)",
                        color: "var(--nav-fg)",
                      }
                }
              >
                {user.name?.[0]?.toUpperCase() || "U"}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className={
                isPortal
                  ? "text-[13px] font-semibold leading-[1.2] text-[var(--tx-pure)] truncate"
                  : "text-[11.5px] font-semibold uppercase tracking-[0.3px] truncate"
              }
              style={isPortal ? undefined : { color: "var(--nav-fg)" }}
            >
              {user.name}
            </div>
            <div
              className={
                isPortal
                  ? "text-[11px] text-[var(--tx-secondary)]"
                  : "text-[9.5px] uppercase tracking-[0.5px]"
              }
              style={isPortal ? undefined : { color: "var(--nav-fg-muted)" }}
            >
              {isPortal ? "Client Portal" : user.role || user.team || "Team"}
            </div>
          </div>
        </div>
        <button
          onClick={onLogout}
          className={cn(
            "flex items-center gap-2 w-full mt-1 px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-[0.5px] rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
            // See the brand link above: --border-focus is a paper-ground
            // copper and fails 3:1 on the ink rail.
            isPortal
              ? "focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-[var(--bz-base)]"
              : "focus-visible:ring-[var(--nav-rule)] focus-visible:ring-offset-[var(--nav-rail-bg)]",
          )}
          style={{
            color: isPortal ? "var(--bz-text-2)" : "var(--nav-fg-muted)",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.color = isPortal
              ? "var(--bz-text-1)"
              : "var(--nav-fg)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = isPortal
              ? "var(--bz-text-2)"
              : "var(--nav-fg-muted)")
          }
        >
          <LogOut size={13} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}
