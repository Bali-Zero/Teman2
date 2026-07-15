"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NavShell, BZLogo } from "@balizero/core";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import type { NavItem } from "@balizero/core";

const ALL_NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/" },
  { label: "Visa", href: "/services/visa" },
  { label: "Business", href: "/services/company" },
  { label: "Tax", href: "/services/tax" },
  { label: "Property", href: "/services/property" },
  { label: "News", href: "/news" },
  { label: "Team", href: "/team" },
];

export function BlogNav() {
  const pathname = usePathname();
  const items =
    pathname === "/"
      ? ALL_NAV_ITEMS.filter((item) => item.href !== "/")
      : ALL_NAV_ITEMS;

  return (
    <NavShell
      logo={
        <Link
          href="/"
          aria-label="Bali Zero"
          className="inline-flex items-center"
        >
          <BZLogo variant="full" />
        </Link>
      }
      items={items}
      slotAfter={<MobileNav items={items} />}
      actions={
        <Link
          href="/contact"
          className="inline-flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.18em] px-4 py-2 rounded-full transition-all"
          style={{
            background: "var(--accent-funnel, #3a6dff)",
            color: "#fff",
          }}
        >
          Talk to us
        </Link>
      }
    />
  );
}
