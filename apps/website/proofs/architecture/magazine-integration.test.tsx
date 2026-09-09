import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readMagazineFeed } from "../../src/lib/editorial-feed";
import { readFixturePublication } from "../../src/lib/server/magazine-fixture";
import { loadJournalFeed } from "../../src/lib/server/journal-feed";
import { Journal } from "../../src/components/Journal";
import { JournalIndex } from "../../src/components/journal/JournalIndex";

const policy = { allowFixture: true, approvedEvidenceOrigins: ["https://example.org"] };
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("Magazine repository → decoder → website Journal", () => {
  it("renders approved current records, evidence and actual revision dates in both consumers", async () => {
    vi.stubEnv("WEBSITE_EDITORIAL_FIXTURE", "1");
    const feed = await loadJournalFeed();
    expect(feed.status).toBe("ready");
    expect(feed.articles).toHaveLength(3);
    const home = renderToStaticMarkup(<Journal articles={feed.articles} status={feed.status} fixture />);
    const index = renderToStaticMarkup(<JournalIndex articles={feed.articles} status={feed.status} fixture />);
    for (const html of [home, index]) {
      expect(html).toContain("Editorial preview — sample stories and illustration");
      expect(html).toContain("/assets/editorial-fixture.svg");
      expect(html).not.toContain('href="https://bali-zero-magazine');
      expect(html).not.toContain('href="https://example.org');
      expect(html).not.toMatch(/MUST_NOT_LEAK|private-root|evidence_note|packet_id|claim_id/);
    }
    expect(index).toContain("Amended · Revision 2");
    expect(index).toContain("Local design proof; not a news source");
    expect(index).toContain("Sources and revisions");
    const amended = feed.articles.find((article) => article.editorial?.amended)!;
    for (const revision of amended.editorial!.revisions) {
      expect(index).toContain(`dateTime="${revision.publishedAt.iso}"`);
    }
  });

  it("never enables fixtures by default or treats an outage as sample news", async () => {
    vi.stubEnv("WEBSITE_EDITORIAL_FIXTURE", "");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 503 })));
    expect(await loadJournalFeed()).toMatchObject({ status: "unavailable", articles: [] });
    expect((await readMagazineFeed(readFixturePublication)).status).toBe("malformed");
    expect(await readMagazineFeed(async () => { throw new Error("PRIVATE_BACKEND_FAILURE"); }, policy))
      .toMatchObject({ status: "unavailable", articles: [] });
  });

  it.each(["empty", "unavailable", "malformed", "withdrawn", "unpublished"] as const)(
    "preserves %s through decoding and suppresses stale cards in both consumers", async (status) => {
      const payload = await readFixturePublication();
      const ready = await readMagazineFeed(async () => payload, policy);
      const feed = await readMagazineFeed(async () => ({ ...payload, status, articles: [] }), policy);
      expect(feed.status).toBe(status);
      for (const Component of [Journal, JournalIndex]) {
        const html = renderToStaticMarkup(<Component articles={ready.articles} status={status} />);
        expect(html).toContain('role="status"');
        expect(html).not.toContain(ready.articles[0].title);
        expect(html).not.toContain("/assets/editorial-fixture.svg");
      }
    },
  );

  it.each([
    { publicationState: "building" }, { visibility: "withdrawn" },
    { publishedAt: null }, { publishedAt: "2026-02-30T08:00:00Z" },
    { canonicalUrl: "https://example.org/wrong-article" },
    { image: { src: "/api/media/private-digest", alt: "Not approved" } },
    { evidence: [{ publisher: "Source", citation: null, url: "https://example.org/path?token=private" }] },
    { evidence: [{ publisher: "Source", citation: null, url: "https://private.example/path" }] },
    { revisions: [] }, { lifecycleState: "superseded" },
  ])("rejects a corrupt publication atomically: %j", async (change) => {
    const payload = await readFixturePublication();
    const feed = await readMagazineFeed(async () => ({ ...payload, articles: [{ ...payload.articles[0], ...change }, ...payload.articles.slice(1)] }), policy);
    expect(feed).toMatchObject({ status: "malformed", articles: [] });
  });

  it("drops unknown internal fields and detects duplicates instead of exposing raw records", async () => {
    const payload = await readFixturePublication();
    const feed = await readMagazineFeed(async () => ({ ...payload, private: "MUST_NOT_LEAK", articles: payload.articles.map((article) => ({ ...article, evidence_note: "MUST_NOT_LEAK" })) }), policy);
    expect(feed.status).toBe("ready");
    expect(JSON.stringify(feed)).not.toContain("MUST_NOT_LEAK");
    expect((await readMagazineFeed(async () => ({ ...payload, articles: [...payload.articles, payload.articles[0]] }), policy)).status).toBe("malformed");
  });
});
