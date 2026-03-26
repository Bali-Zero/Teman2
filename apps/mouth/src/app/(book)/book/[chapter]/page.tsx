import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CHAPTERS } from "@/components/book/book-data";
import { BookPage } from "../BookPage";

interface Props {
  params: Promise<{ chapter: string }>;
}

export async function generateStaticParams() {
  return CHAPTERS.map((c) => ({ chapter: c.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { chapter: chapterId } = await params;
  const chapter = CHAPTERS.find((c) => c.id === chapterId);
  if (!chapter) return {};

  return {
    title: chapter.title,
    description: chapter.subtitle,
    openGraph: {
      title: `${chapter.title} — Bali Zero`,
      description: chapter.subtitle,
      images: [
        {
          url: `/api/og/book?chapter=${chapterId}&title=${encodeURIComponent(chapter.title)}`,
          width: 1200,
          height: 630,
        },
      ],
    },
  };
}

export default async function BookChapterPage({ params }: Props) {
  const { chapter: chapterId } = await params;
  const chapter = CHAPTERS.find((c) => c.id === chapterId);
  if (!chapter) notFound();

  return <BookPage initialChapter={chapterId} />;
}
