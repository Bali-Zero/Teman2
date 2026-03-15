import type { Metadata } from "next";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Our Expert Team",
  description:
    "Meet the Bali Zero team: visa consultants, tax experts, company setup specialists, and AI-powered support. Trusted by 5000+ clients in Bali since 2020.",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${baseUrl}/team`,
    title: "Our Expert Team | Bali Zero",
    description:
      "Meet the Bali Zero team: visa consultants, tax experts, company setup specialists, and AI-powered support. Trusted by 5000+ clients since 2020.",
    siteName: "Bali Zero",
    images: [
      {
        url: `${baseUrl}/static/og-image.jpg`,
        width: 1200,
        height: 630,
        alt: "Bali Zero Expert Team",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Our Expert Team | Bali Zero",
    description:
      "Meet the Bali Zero team: visa consultants, tax experts, and company setup specialists in Bali.",
    creator: "@balizero",
  },
  alternates: {
    canonical: `${baseUrl}/team`,
  },
};

export default function TeamLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
