import { Montserrat } from "next/font/google";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";

const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
  display: "swap",
  weight: ["400", "500", "600", "700", "800", "900"],
});

export default function VisaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className={`${montserrat.variable} relative z-1`}
      style={{
        fontFamily: "var(--font-montserrat), system-ui, sans-serif",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" />}
        items={getFunnelNavItems("visa")}
        actions={<HeaderWhatsAppCTA funnel="visa" />}
      />
      <SessionInit funnel="visa" />
      <div className="mx-auto max-w-6xl px-4 pt-14 pb-8 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  );
}
