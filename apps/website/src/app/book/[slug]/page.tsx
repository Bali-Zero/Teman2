import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { BookReader } from "../../../features/supporting/BookReader";
import {
  bookChapters,
  bookLocale,
} from "../../../features/supporting/book-model";
import source from "../../../features/supporting/book-content.json";
type Props = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};
export async function generateMetadata({
  params,
  searchParams,
}: Props): Promise<Metadata> {
  const { slug } = await params;
  const chapter = bookChapters.find((chapter) => chapter.id === slug);
  if (!chapter) return {};
  const locale = bookLocale((await searchParams).lang);
  return {
    title: `${source.translations[locale].chapters[chapter.index]} — The Bali Zero Book`,
  };
}
export default async function Page({ params, searchParams }: Props) {
  const { slug } = await params;
  if (!bookChapters.some((chapter) => chapter.id === slug)) notFound();
  return (
    <BookReader chapter={slug} locale={bookLocale((await searchParams).lang)} />
  );
}
