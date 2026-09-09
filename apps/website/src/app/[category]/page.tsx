import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  isJournalCategory,
  journalCategories,
} from "../../content/journal-categories";
import NewsPage from "../news/page";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  const definition = journalCategories.find((item) => item.slug === category);
  if (!definition) notFound();
  return {
    title: `${definition.label} | Bali Zero`,
    description: `${definition.label} news and practical analysis from the Bali Zero Journal.`,
    alternates: { canonical: `/${definition.slug}` },
  };
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ category: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { category } = await params;
  if (!isJournalCategory(category)) notFound();
  return NewsPage({
    searchParams: Promise.resolve({ ...(await searchParams), category }),
  });
}
