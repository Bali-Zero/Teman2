import { getAllArticles } from "@/lib/blog/articles";
import NewsPageClient from "./NewsPageClient";

// ISR: Rigenera la pagina ogni 60 secondi per contenuti freschi
// ma con cache per performance ottimali
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
