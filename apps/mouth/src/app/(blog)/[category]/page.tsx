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
  // `[category]` sits at the ROOT of the route tree, so it matches every
  // unknown single-segment URL on the domain. `generateMetadata` runs before
  // the component's `notFound()` guard, so without this check the title was
  // minted from whatever the caller put in the path: measured live on
  // 2026-08-27, `/nope-single-segment` answered 200 with
  // `<title>Nope-single-segment Insights | Bali Zero</title>` over a body that
  // renders "Article not found". Guard the metadata with the SAME list the
  // component guards with, so an unknown segment can never place
  // attacker-chosen text in a Bali Zero title.
  //
  // The string is deliberately bare: the root layout sets the title template
  // `%s | Bali Zero`, so it renders as "Page not found | Bali Zero". Writing
  // the suffix here would produce it twice. It matches `layout.tsx` verbatim.
  if (!VALID_CATEGORIES.includes(category as ArticleCategory)) {
    return {
      title: "Page not found",
      robots: { index: false, follow: false },
    };
  }
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
