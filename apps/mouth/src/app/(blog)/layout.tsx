import type { ReactNode } from "react";
import Link from "next/link";
import { NavShell, BZLogo } from "@balizero/core";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { ZantaraFAB } from "@/app/v2/_components/ZantaraFAB";
import { Footer } from "@/app/v2/_components/Footer";
import { I18nProvider } from "@/i18n";

const BLOG_NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Visa", href: "/services/visa" },
  { label: "Business", href: "/services/company" },
  { label: "Tax", href: "/services/tax" },
  { label: "Property", href: "/services/property" },
  { label: "News", href: "/news" },
  { label: "Team", href: "/team" },
];

export default function BlogLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <div
        className="min-h-screen flex flex-col"
        style={{
          background: "var(--surface-base)",
          color: "var(--text-primary)",
        }}
      >
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
          items={BLOG_NAV_ITEMS}
          slotAfter={<MobileNav items={BLOG_NAV_ITEMS} />}
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
        <main className="flex-1 pt-14">{children}</main>
        <Footer />
        <ZantaraFAB />
      </div>
    </I18nProvider>
  );
}
