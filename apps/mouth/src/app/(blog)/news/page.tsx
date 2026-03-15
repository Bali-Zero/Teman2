import type { Metadata } from "next";
import { getAllArticles } from "@/lib/blog/articles";
import NewsPageClient from "../NewsPageClient";

// ISR: Rigenera la pagina ogni 60 secondi per contenuti freschi
export const revalidate = 60;

export const dynamicParams = true;

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Indonesia News & Regulatory Intelligence",
  description:
    "Latest Indonesia news on visas, immigration policy, business regulations, tax updates, and KBLI changes. AI-curated intelligence from Bali Zero.",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${baseUrl}/news`,
    title: "Indonesia News & Regulatory Intelligence | Bali Zero",
    description:
      "Latest Indonesia news on visas, immigration policy, business regulations, tax updates, and KBLI changes. AI-curated intelligence from Bali Zero.",
    siteName: "Bali Zero",
    images: [
      {
        url: `${baseUrl}/static/og-image.jpg`,
        width: 1200,
        height: 630,
        alt: "Indonesia News & Regulatory Intelligence",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Indonesia News & Regulatory Intelligence | Bali Zero",
    description:
      "Latest Indonesia news on visas, immigration, business regulations, and tax updates.",
    creator: "@balizero",
  },
  alternates: {
    canonical: `${baseUrl}/news`,
  },
};

/**
 * /news route - Same editorial layout as homepage
 * Uses real MDX articles from filesystem via ISR
 */
export default async function NewsRoute() {
  const { articles } = await getAllArticles({});

  return <NewsPageClient articles={articles} />;
}
