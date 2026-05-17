import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import "./cockpit-shell.css";

const montserrat = Montserrat({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-montserrat",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Zantara Cockpit — Bali Zero",
  description: "Localhost-only command center. Not deployed anywhere.",
  robots: {
    index: false,
    follow: false,
  },
};

/**
 * Cockpit layout — scoped Bali Zero brand surface.
 *
 * Sets `data-cockpit="true"` on <html> so cockpit-shell.css applies only
 * here and leaves the existing cost-dashboard slate theme alone.
 *
 * Loads Montserrat from next/font/google (self-hosted, no external CDN at
 * runtime). The font CSS variable is exposed as --font-montserrat and the
 * existing CSS falls back to Inter / -apple-system.
 */
export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-cockpit="true" className={montserrat.variable}>
      <body>{children}</body>
    </html>
  );
}
