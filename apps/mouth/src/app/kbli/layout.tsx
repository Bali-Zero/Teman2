import { Montserrat } from "next/font/google";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";

const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
  display: "swap",
  weight: ["400", "500", "600", "700", "800", "900"],
});

export default function KBLILayout({
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
        items={[
          { label: "Home", href: "https://balizero.com/" },
          { label: "Visa", href: "https://visa.balizero.com/" },
          { label: "Tax", href: "https://tax.balizero.com/" },
        ]}
        actions={
          <a
            href="https://wa.me/628213107363"
            className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold"
            style={{ background: "var(--kbli-accent)", color: "#fff" }}
          >
            WhatsApp
          </a>
        }
      />
      <SessionInit funnel="kbli" />
      <div className="mx-auto max-w-6xl px-4 pt-14 pb-8 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  );
}
