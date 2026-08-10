import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getArticlesByCategory } from "@/lib/blog/articles";
import { generateCategoryMetadata } from "@/lib/blog/metadata";
import type { ArticleCategory } from "@/lib/blog/types";
import CategoryContent from "./CategoryContent";

// All valid blog categories — kept in sync with ArticleCategory union type
const VALID_CATEGORIES: ArticleCategory[] = [
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "trends",
];

interface PageProps {
  params: Promise<{ category: string }>;
}

export function generateStaticParams(): { category: string }[] {
  return VALID_CATEGORIES.map((category) => ({ category }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { category } = await params;
  return generateCategoryMetadata(category);
}

export default async function CategoryPage({
  params,
}: PageProps): Promise<React.JSX.Element> {
  const { category } = await params;

  // Guard: only serve known categories — everything else is a 404
  if (!VALID_CATEGORIES.includes(category as ArticleCategory)) {
    notFound();
  }

  const articleCategory = category as ArticleCategory;

  // Fetch all articles server-side (no limit cap — expose full corpus to Googlebot)
  const { articles } = await getArticlesByCategory(articleCategory, 500, 0);

  return <CategoryContent articles={articles} category={articleCategory} />;
}
