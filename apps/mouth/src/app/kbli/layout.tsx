import { montserrat } from "@balizero/core/fonts/montserrat";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { Footer } from "@/app/v2/_components/Footer";

export default function KBLILayout({
  children,
  panel,
}: {
  children: React.ReactNode;
  panel: React.ReactNode;
}) {
  const navItems = getFunnelNavItems("kbli");

  return (
    <div
      className={`${montserrat.variable} relative`}
      style={{
        fontFamily: "var(--font-montserrat), system-ui, sans-serif",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" />}
        items={navItems}
        slotAfter={<MobileNav items={navItems} />}
        actions={
          <WhatsAppLeadButton
            source="kbli_navigator"
            whatsappContext={[{ label: "Source", value: "KBLI Navigator" }]}
            utm={{ page: "/kbli" }}
            fallbackHref={buildWhatsAppLink("kbli")}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
            style={{
              background: "var(--accent-funnel)",
              color: "var(--text-on-accent)",
            }}
          >
            Get Started
          </WhatsAppLeadButton>
        }
      />
      <SessionInit funnel="kbli" />
      <div className="mx-auto max-w-6xl px-4 pt-14 pb-8 sm:px-6 lg:px-8">
        {children}
      </div>
      {panel}
      <Footer />
    </div>
  );
}
