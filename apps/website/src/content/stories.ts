import { getPublicJournalArticles } from "./journal";

// Preserve the two featured R19 positions while sharing verified metadata.
export const stories = getPublicJournalArticles().slice(0, 2);
