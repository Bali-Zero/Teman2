import type { Metadata } from "next";
import { BookReader } from "../../features/supporting/BookReader";
import { bookLocale } from "../../features/supporting/book-model";
export const metadata: Metadata = {
  title: "The Bali Zero Book",
  description:
    "Our story, people, services and tools. An eight-chapter introduction to Bali Zero.",
};
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  return <BookReader locale={bookLocale((await searchParams).lang)} />;
}
