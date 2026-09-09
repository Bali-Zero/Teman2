import { notFound } from "next/navigation";
import { isJournalCategory } from "../../content/journal-categories";
import JournalPage from "../journal/page";

export default async function CategoryPage({ params, searchParams }: { params: Promise<{ category: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { category } = await params;
  if (!isJournalCategory(category)) notFound();
  return JournalPage({ searchParams: Promise.resolve({ ...await searchParams, category }) });
}
