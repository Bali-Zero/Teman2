import { loadPublicHomeFeed } from "./home-editorial";
import { readMagazineFeed } from "../editorial-feed";
import { readFixturePublication } from "./magazine-fixture";
import { loadPublicJournalFeed, type JournalQuery, type JournalFeed } from "./public-editorial";

/** Read current public content. Synthetic Magazine stories are test input only. */
export async function loadJournalFeed(query: JournalQuery & { home?: boolean } = {}): Promise<JournalFeed> {
  if (process.env.NODE_ENV !== "test" || process.env.WEBSITE_EDITORIAL_FIXTURE !== "1") {
    return query.home ? loadPublicHomeFeed() : loadPublicJournalFeed(query);
  }
  return readMagazineFeed(readFixturePublication, {
    allowFixture: true,
    approvedEvidenceOrigins: ["https://example.org"],
  });
}
