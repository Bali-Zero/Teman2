import { R19_CLASS, R19_DIRECTION_A_VARS } from "@/lib/theme/r19Vars";
import "@/styles/r19-fonts.css";
import "@/styles/r19-direction-a.css";
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
    // R19 Direction A (BRIEF-v2 R-1) on this route group's own wrapper, never
    // the root layout: the var set and its class hook sit on ONE element
    // (r19Vars.ts scoping contract); the Fraunces/Manrope faces are the SAME
    // ones main's editorial R19 registers (styles/r19-fonts.css, unified
    // 2026-09-27 — no per-route font class anymore). `kbli-paper` re-points
    // every --kbli-* token at paper (styles/kbli-theme.css), so the 1,559
    // code pages change skin without changing structure.
    <div
      className={`${R19_CLASS} kbli-paper relative min-h-screen`}
      style={R19_DIRECTION_A_VARS}
    >
      <NavShell
        logo={<BZLogo variant="full" />}
        items={navItems}
        slotAfter={<MobileNav items={navItems} funnel="kbli" />}
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
