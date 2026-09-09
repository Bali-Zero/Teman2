import { connection } from "next/server";
import { Journal } from "./Journal";
import { loadJournalFeed } from "../lib/server/journal-feed";

/** Only the editorial island waits for request-time publication verification. */
export async function HomeJournal() {
  await connection();
  const feed = await loadJournalFeed({ home: true });
  return <Journal featuredCount={feed.featuredCount} articles={feed.articles} status={feed.status} fixture={feed.provenance === "fixture"} />;
}

export function JournalPending() {
  return <div className="wrap"><section className="journal" id="journal" aria-labelledby="journal-pending-title" aria-busy="true">
    <div className="masthead"><span className="eyebrow">News · Analysis · Guides</span><h2 id="journal-pending-title">The Bali Zero Journal</h2></div>
    <div className="journal-sub"><p role="status">Checking the latest published stories…</p><a className="textlink" href="/journal">Explore the Journal <span aria-hidden="true">↗</span></a></div>
  </section></div>;
}
