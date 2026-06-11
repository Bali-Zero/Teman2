import type { ComponentType, CSSProperties, ElementType } from "react";

export interface SubNavItem {
  label: string;
  href: string;
  icon?: ComponentType<{ size?: number; className?: string }>;
}

export type SubNavVariant = "tabs" | "sidebar" | "chips";

interface VariantSpec {
  link: string;
  active: string;
  inactive: string;
  activeStyle?: CSSProperties;
  inactiveStyle?: CSSProperties;
  iconSize: number;
  iconClassName?: string;
}

const VARIANTS: Record<SubNavVariant, VariantSpec> = {
  tabs: {
    link: "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11.5px] font-medium transition-all duration-150",
    active: "shadow-sm",
    inactive: "hover:bg-white/[0.04]",
    activeStyle: {
      background: "rgba(212,132,90,0.12)",
      color: "var(--bz-accent)",
      border: "1px solid rgba(212,132,90,0.2)",
    },
    inactiveStyle: { color: "var(--bz-text-2)" },
    iconSize: 13,
    iconClassName: "flex-shrink-0",
  },
  sidebar: {
    link: "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
    active: "bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]",
    inactive: "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50",
    iconSize: 18,
  },
  chips: {
    link: "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors",
    active:
      "bg-[var(--bz-accent)]/15 text-[var(--bz-accent)] border border-[var(--bz-accent)]/30",
    inactive:
      "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 border border-transparent",
    iconSize: 14,
  },
};

export interface SubNavProps {
  items: SubNavItem[];
  /** Current route, e.g. from next/navigation's `usePathname()`. */
  pathname: string | null;
  variant: SubNavVariant;
  /** Section root href (e.g. "/hr") — active on exact match only. */
  rootHref?: string;
  /** Link element — pass next/link's `Link` for client-side routing. */
  linkAs?: ElementType;
}

/**
 * Section sub-navigation (workspace P1.1): the single active-route link
 * list previously hand-rolled per section. Renders only the links — the
 * positioning container (sidebar, pill group, chip strip) stays at the
 * call site.
 */
export function SubNav({
  items,
  pathname,
  variant,
  rootHref,
  linkAs: LinkAs = "a",
}: SubNavProps) {
  const spec = VARIANTS[variant];
  return (
    <>
      {items.map((item) => {
        const active =
          pathname === item.href ||
          (item.href !== rootHref && Boolean(pathname?.startsWith(item.href)));
        const Icon = item.icon;
        return (
          <LinkAs
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`${spec.link} ${active ? spec.active : spec.inactive}`}
            style={active ? spec.activeStyle : spec.inactiveStyle}
          >
            {Icon ? (
              <Icon size={spec.iconSize} className={spec.iconClassName} />
            ) : null}
            {item.label}
          </LinkAs>
        );
      })}
    </>
  );
}
