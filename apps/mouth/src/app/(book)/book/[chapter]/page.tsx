import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CHAPTERS } from "@/components/book/book-data";
import { chapterTitleMetadata } from "@/components/book/book-title";
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
    // The (book) layout appends ` — Bali Zero` to every chapter title, and the
    // cover chapter is literally titled "Bali Zero" — the append produced
    // `Bali Zero — Bali Zero`, measured live 2026-07-29. The rule lives in
    // book-title.ts so book-title.test.ts can compose it against the REAL
    // chapter data instead of asserting about this line.
    title: chapterTitleMetadata(chapter.title),
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
