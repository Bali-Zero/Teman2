import { connection } from "next/server";
import type { Metadata } from "next";
import { JournalIndex } from "../../components/journal/JournalIndex";
import { loadJournalFeed } from "../../lib/server/journal-feed";
import { isJournalCategory } from "../../content/journal-categories";

export const metadata: Metadata = {
  title: "The Bali Zero Journal",
  description:
    "News and practical analysis from the Bali Zero Journal: visas, business, taxes, property, living and technology in Indonesia.",
};

export default async function JournalPage({ searchParams }: { searchParams?: Promise<Record<string, string | string[] | undefined>> }) {
  await connection();
  const params = await searchParams ?? {};
  const q = typeof params.q === "string" ? params.q.trim().slice(0, 120) : undefined;
  const category = typeof params.category === "string" && isJournalCategory(params.category) ? params.category : undefined;
  const page = typeof params.page === "string" && /^\d{1,4}$/.test(params.page) ? Math.max(1, Math.min(1000, Number(params.page))) : 1;
  const feed = await loadJournalFeed({ q, category, page, limit: 12 });
  return <JournalIndex articles={feed.articles} status={feed.status} fixture={feed.provenance === "fixture"} query={{ q, category, page }} hasMore={feed.hasMore} catalogSize={feed.catalogSize} total={feed.total} />;
}
