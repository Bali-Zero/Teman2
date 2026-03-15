import type { Metadata } from "next";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Contact Bali Zero | Free Visa & Business Consultation",
  description:
    "Contact Bali Zero for a free consultation on Indonesia visas, company setup, tax compliance, and property investment. WhatsApp, email, or visit our Bali office.",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${baseUrl}/contact`,
    title: "Contact Bali Zero | Free Visa & Business Consultation",
    description:
      "Contact Bali Zero for a free consultation on Indonesia visas, company setup, tax compliance, and property investment in Bali.",
    siteName: "Bali Zero",
    images: [
      {
        url: `${baseUrl}/static/og-image.jpg`,
        width: 1200,
        height: 630,
        alt: "Contact Bali Zero",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Contact Bali Zero | Free Visa Consultation",
    description:
      "Get a free consultation on Indonesia visas, company setup, and tax compliance from Bali Zero.",
    creator: "@balizero",
  },
  alternates: {
    canonical: `${baseUrl}/contact`,
  },
};

export default function ContactLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
