import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Bali Visa Agency 2026 | KITAS, PT PMA, Golden Visa Services",
  description:
    "Complete visa and business services in Bali. KITAS from IDR 11M, PT PMA setup IDR 20M, Golden Visa, tax compliance. Transparent pricing, 5000+ clients served.",
  alternates: {
    canonical: "https://balizero.com/services",
  },
  openGraph: {
    title: "Bali Zero Services | Visa, PT PMA, Tax & Property",
    description:
      "Complete visa and business services in Bali. KITAS, PT PMA, Golden Visa, tax compliance. Transparent pricing.",
    url: "https://balizero.com/services",
  },
};

export default function ServicesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
