import type { Metadata } from "next";
import { getAllArticles } from "@/lib/blog/articles";
import NewsPageClient from "./NewsPageClient";

export const metadata: Metadata = {
  title: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia",
  description:
    "Indonesia's AI-powered visa agency. KITAS, KITAP, Golden Visa, PT PMA company setup, tax compliance. 24/7 AI assistant. Trusted by 5000+ clients since 2020.",
  alternates: {
    canonical: "https://balizero.com",
  },
  openGraph: {
    title: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia",
    description:
      "Indonesia's AI-powered visa agency. KITAS, KITAP, Golden Visa, PT PMA company setup, tax compliance. 24/7 AI assistant. Trusted by 5000+ clients.",
    url: "https://balizero.com",
  },
};

// ISR: Rigenera la pagina ogni 60 secondi per contenuti freschi
// ma con cache per performance ottimali
export const dynamic = "force-dynamic";
export const revalidate = 60;

// Cache tags per invalidazione manuale quando necessario
export const dynamicParams = true;

/**
 * Homepage Server Component con ISR
 *
 * - Pre-renderizzata a build time
 * - Rigenerata ogni 60 secondi (ISR)
 * - Cache tags per invalidazione programmatica
 */
export default async function NewsPage() {
  // Fetch all articles from filesystem (server-side) with ISR caching
  // No limit: homepage needs specific slugs for the 5-article hero collage
  const { articles } = await getAllArticles({});

  return <NewsPageClient articles={articles} />;
}
