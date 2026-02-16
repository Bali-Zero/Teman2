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
  // Fetch articoli dal filesystem (server-side)
  const articles = await getAllArticles({ 
    published: true,
    sortBy: 'publishedAt',
    order: 'desc'
  });

  return <NewsPageClient articles={articles} />;
}
