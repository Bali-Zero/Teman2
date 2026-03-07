import { getAllArticles } from "@/lib/blog/articles";
import NewsPageClient from "../NewsPageClient";

// ISR: Rigenera la pagina ogni 60 secondi per contenuti freschi
export const revalidate = 60;

export const dynamicParams = true;

/**
 * /news route - Same editorial layout as homepage
 * Uses real MDX articles from filesystem via ISR
 */
export default async function NewsRoute() {
  const { articles } = await getAllArticles({});

  return <NewsPageClient articles={articles} />;
}
