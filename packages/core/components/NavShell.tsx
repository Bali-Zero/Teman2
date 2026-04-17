import type { ReactNode } from "react";

export interface NavItem {
  label: string;
  href: string;
}

interface NavShellProps {
  logo: ReactNode;
  items: NavItem[];
  actions: ReactNode;
  slotBefore?: ReactNode;
  slotAfter?: ReactNode;
  children?: ReactNode;
}

/**
 * NavShell — the glassmorphism bar used on every page.
 * Reads only semantic tokens. Funnel-agnostic (never reads --accent-funnel).
 *
 * Route groups customize via:
 *   - `items` prop for the link list
 *   - `slotBefore` / `slotAfter` for search, language switcher, funnel picker
 *   - `children` as an escape hatch (replaces center region entirely)
 *
 * If you need to fork NavShell, extend it with a new slot instead — a fork
 * signals the primitive is wrong.
 */
export function NavShell({
  logo,
  items,
  actions,
  slotBefore,
  slotAfter,
  children,
}: NavShellProps) {
  return (
    <nav
      className="flex items-center px-5 md:px-10 h-14 backdrop-blur-xl"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        width: "100%",
        zIndex: 300,
        background: "var(--nav-bg)",
        borderBottom: "1px solid var(--nav-border)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
      }}
    >
      <div className="mr-auto opacity-75 transition-opacity hover:opacity-100">
        {logo}
      </div>

      {slotBefore ? (
        <div className="mr-4 hidden md:flex">{slotBefore}</div>
      ) : null}

      {children ? (
        <div className="hidden md:flex flex-1 items-center justify-center">
          {children}
        </div>
      ) : (
        <ul className="hidden md:flex gap-0.5 list-none">
          {items.map((item) => (
            <li key={item.href}>
              <a
                href={item.href}
                className="px-3.5 py-1.5 rounded-lg text-[11.5px] font-medium uppercase tracking-wide transition-colors"
                style={{ color: "var(--text-tertiary)" }}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      )}

      {slotAfter ? <div className="ml-auto md:ml-4">{slotAfter}</div> : null}

      <div className="ml-4 hidden md:flex gap-2">{actions}</div>
    </nav>
  );
}
