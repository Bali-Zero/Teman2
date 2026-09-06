import type { Metadata } from "next";
import { JournalIndex } from "../../components/journal/JournalIndex";
import { getPublicJournalArticles } from "../../content/journal";

export const metadata: Metadata = {
  title: "The Bali Zero Journal",
  description:
    "A verified index of Bali Zero news and practical analysis from Indonesia.",
};

export default function JournalPage() {
  return <JournalIndex articles={getPublicJournalArticles()} />;
}
