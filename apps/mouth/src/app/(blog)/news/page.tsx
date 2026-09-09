import type { Metadata } from "next";
import { getAllArticles } from "@/lib/blog/articles";
import NewsPageClient from "../NewsPageClient";

// Force dynamic rendering to avoid prerender failures when APIs are unreachable
export const dynamic = "force-dynamic";

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

interface NewsRouteProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

/**
 * /news route - Same editorial layout as homepage
 * Uses real MDX articles from filesystem via ISR
 *
 * The homepage topic pills link here with ?category= or ?q=; both are read
 * server-side. `category` filters the fetch, `q` is seeded into the client
 * search box so the text filter runs on first paint (no Suspense boundary,
 * no flash of the unfiltered list).
 */
export default async function NewsRoute({ searchParams }: NewsRouteProps) {
  const sp = await searchParams;

  const rawCategory = Array.isArray(sp.category) ? sp.category[0] : sp.category;
  const category = rawCategory?.trim() ? rawCategory : undefined;

  const rawQuery = Array.isArray(sp.q) ? sp.q[0] : sp.q;
  const initialQuery = rawQuery ?? "";

  const { articles } = await getAllArticles(category ? { category } : {});

  return <NewsPageClient articles={articles} initialQuery={initialQuery} />;
}
