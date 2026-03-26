import type { Metadata } from "next";
import { League_Spartan, Montserrat } from "next/font/google";
import "@/app/globals.css";

const leagueSpartan = League_Spartan({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-spartan",
  weight: ["400", "600", "700", "800", "900"],
});

const montserrat = Montserrat({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-montserrat",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: {
    template: "%s — Bali Zero",
    default: "Bali Zero — The story",
  },
  description:
    "From CV Bayu Santero (2006) to Bali Zero (2020). 5,000+ clients. Indonesia's only AI-first agency.",
  openGraph: {
    type: "website",
    siteName: "Bali Zero",
  },
};

export default function BookLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className={`${leagueSpartan.variable} ${montserrat.variable} min-h-screen text-[#edeae4]`}
      style={{ background: "var(--book-bg, #0d0d14)" }}
    >
      {/*
        Nebula stellar background — CSS only, no images.
        Three radial gradients layered on a near-black base with a subtle
        blue-violet tint (#0d0d14), plus two soft glows in brand gold/coral.
        This creates the "brilliant starfield" depth without pure black.
      */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          background: `
            radial-gradient(ellipse 80% 60% at 15% 20%, rgba(62, 40, 96, 0.35) 0%, transparent 65%),
            radial-gradient(ellipse 60% 50% at 85% 80%, rgba(40, 32, 80, 0.40) 0%, transparent 60%),
            radial-gradient(ellipse 40% 40% at 50% 50%, rgba(212, 132, 90, 0.04) 0%, transparent 70%),
            radial-gradient(ellipse 100% 100% at 50% 50%, #0d0d14 0%, #08080f 100%)
          `,
        }}
      />
      {/* Subtle star-dust texture layer */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          backgroundImage: `
            radial-gradient(circle, rgba(255,255,255,0.35) 1px, transparent 1px),
            radial-gradient(circle, rgba(255,255,255,0.20) 1px, transparent 1px),
            radial-gradient(circle, rgba(212,132,90,0.25) 1px, transparent 1px)
          `,
          backgroundSize: "340px 340px, 220px 220px, 480px 480px",
          backgroundPosition: "0 0, 110px 80px, 200px 160px",
          maskImage:
            "radial-gradient(ellipse 100% 100% at 50% 50%, black 0%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 100% 100% at 50% 50%, black 0%, transparent 100%)",
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}
