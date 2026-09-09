import { afterEach, describe, expect, it } from "vitest";
import type { D1DatabaseLike, D1PreparedStatementLike } from "../../../bali-zero-magazine/lib/server/publication-repository";
import {
  createMagazineFixture, FIXTURE_DATES, MagazineFixtureDatabase, quarantineFixtureStory, readFixturePublication,
} from "../../src/lib/server/magazine-fixture";
import { FIXTURE_ARTWORK, MAGAZINE_ORIGIN, readMagazinePublication } from "../../src/lib/server/magazine-publication";

const databases: MagazineFixtureDatabase[] = [];
const options = { provenance: "fixture", approvedEvidenceOrigins: ["https://example.org"] } as const;
async function fixture(): Promise<MagazineFixtureDatabase> {
  const db = await createMagazineFixture();
  databases.push(db);
  return db;
}
afterEach(() => { databases.splice(0).forEach((db) => db.close()); });

describe("actual Magazine repository to website producer", () => {
  it("reads three approved synthetic records, never building or withdrawn content", async () => {
    const db = await fixture();
    const result = await readMagazinePublication(db, options);
    expect(result.status).toBe("ready");
    expect(result.articles).toHaveLength(3);
    expect(result.articles.every((article) => article.publicationState === "published" && article.visibility === "visible")).toBe(true);
    expect(JSON.stringify(result)).not.toMatch(/MUST_NOT_LEAK|private-root|private-fingerprint|claim_id|evidence_note|packet_id|collector|NotebookLM/);
    expect(result.articles[0].canonicalUrl).toBe(`${MAGAZINE_ORIGIN}/stories/fixture-paper-and-type`);
    expect(result.articles[0].image).toEqual({ src: FIXTURE_ARTWORK, alt: expect.any(String) });
    expect(result.articles[1].image).toBeNull();
    expect(result.articles[0].evidence).toEqual([{
      publisher: "Synthetic editorial fixture", citation: "Local design proof; not a news source",
      url: "https://example.org/fixture-paper-and-type",
    }]);
    expect(db.sqlite.prepare("PRAGMA foreign_key_check").all()).toEqual([]);
  });

  it("returns the amendment although the edition pins its historic version", async () => {
    const db = await fixture();
    const result = await readMagazinePublication(db, options);
    const article = result.articles.find((item) => item.slug === "fixture-notes-in-the-margin")!;
    expect(article).toMatchObject({ revision: 2, lifecycleState: "amended", publishedAt: FIXTURE_DATES.amendment });
    expect(article.summary).toContain("revised");
    expect(article.revisions).toEqual([
      { version: 1, publishedAt: FIXTURE_DATES.publication },
      { version: 2, publishedAt: FIXTURE_DATES.amendment },
    ]);
    db.sqlite.prepare("UPDATE story_versions SET publication_state = 'superseded' WHERE story_id = 'fixture-notes-in-the-margin' AND version = 1").run();
    const superseded = await readMagazinePublication(db, options);
    expect(superseded.articles.find((item) => item.slug === article.slug)).toEqual(article);
  });

  it("distinguishes no edition from unpublished preparation", async () => {
    const empty = new MagazineFixtureDatabase();
    databases.push(empty);
    expect((await readMagazinePublication(empty, options)).status).toBe("empty");
    const db = await fixture();
    db.sqlite.exec("UPDATE editions SET publication_state = 'building'; UPDATE edition_pointer SET current_edition_id = NULL");
    const result = await readMagazinePublication(db, options);
    expect(result.status).toBe("unpublished");
    expect(result.articles).toEqual([]);
  });

  it("returns a withdrawn tombstone without withdrawn titles when every candidate is quarantined", async () => {
    const db = await fixture();
    for (const slug of ["fixture-paper-and-type", "fixture-room-to-read", "fixture-notes-in-the-margin"]) quarantineFixtureStory(db, slug);
    const result = await readMagazinePublication(db, options);
    expect(result).toEqual({ version: 2, publisher: "bali-zero-magazine", status: "withdrawn", articles: [], provenance: "fixture" });
  });

  it("uses latest visibility events and prevents a historical edition from reviving unpublished current content", async () => {
    const db = await fixture();
    quarantineFixtureStory(db, "fixture-paper-and-type");
    expect((await readMagazinePublication(db, options)).articles).toHaveLength(2);
    quarantineFixtureStory(db, "fixture-paper-and-type", 2, false);
    expect((await readMagazinePublication(db, options)).articles).toHaveLength(3);
    db.sqlite.prepare("UPDATE story_versions SET publication_state = 'building' WHERE story_id = 'fixture-notes-in-the-margin' AND version = 2").run();
    const result = await readMagazinePublication(db, options);
    expect(result.articles.map((item) => item.slug)).not.toContain("fixture-notes-in-the-margin");
  });

  it("does not invent missing dates or an empty edition on malformed published state", async () => {
    const db = await fixture();
    db.sqlite.prepare("UPDATE story_versions SET published_at = NULL WHERE story_id = 'fixture-paper-and-type'").run();
    expect(await readMagazinePublication(db, options)).toMatchObject({ status: "malformed", articles: [] });
  });

  it("rejects a superseded current story and timestamp formats outside the shared contract", async () => {
    const db = await fixture();
    db.sqlite.prepare("UPDATE story_versions SET lifecycle_state = 'superseded' WHERE story_id = 'fixture-paper-and-type'").run();
    expect((await readMagazinePublication(db, options)).status).toBe("malformed");
    db.sqlite.prepare("UPDATE story_versions SET lifecycle_state = 'verified', updated_at = '2026-09-01T08:00:00.1Z' WHERE story_id = 'fixture-paper-and-type'").run();
    expect((await readMagazinePublication(db, options)).status).toBe("malformed");
  });

  it("rejects malformed edition dates and history instead of silently dropping them", async () => {
    const db = await fixture();
    db.sqlite.exec("UPDATE editions SET published_at = '2026-02-30T08:00:00.000Z'");
    expect((await readMagazinePublication(db, options)).status).toBe("malformed");
    db.sqlite.prepare("UPDATE editions SET published_at = ?").run(FIXTURE_DATES.publication);
    db.sqlite.prepare("UPDATE story_versions SET published_at = NULL WHERE story_id = 'fixture-notes-in-the-margin' AND version = 1").run();
    expect((await readMagazinePublication(db, options)).status).toBe("malformed");
  });

  it("requires evidence from currently published claims and links", async () => {
    const db = await fixture();
    db.sqlite.exec("UPDATE story_claims SET publication_state = 'building' WHERE story_id = 'fixture-paper-and-type'");
    expect((await readMagazinePublication(db, options)).status).toBe("malformed");
    db.sqlite.exec("UPDATE story_claims SET publication_state = 'published' WHERE story_id = 'fixture-paper-and-type'; UPDATE story_evidence SET publication_state = 'building' WHERE story_id = 'fixture-paper-and-type'");
    expect((await readMagazinePublication(db, options)).status).toBe("malformed");
  });

  it.each(["https://not-approved.example/source", "https://example.org/source?private=value", "https://user:pass@example.org/source", "http://example.org/source", "https://example.org/source#private"]) (
    "refuses an unapproved or unsafe evidence destination: %s", async (url) => {
      const db = await fixture();
      db.sqlite.prepare("UPDATE evidence_refs SET canonical_url = ? WHERE evidence_id = 'fixture-paper-and-type-evidence'").run(url);
      expect(await readMagazinePublication(db, options)).toMatchObject({ status: "malformed", articles: [] });
    },
  );

  it("has no implicit evidence origin authorization", async () => {
    const db = await fixture();
    expect((await readMagazinePublication(db, { provenance: "publisher" })).status).toBe("malformed");
  });

  it("revokes images using latest status/rights even when original metadata remains approved", async () => {
    const db = await fixture();
    db.sqlite.exec("INSERT INTO asset_status_events(asset_id, status_seq, status, rights_status, reason_code) VALUES ('fixture-artwork', 1, 'revoked', 'denied', 'fixture-rights-withdrawn')");
    const result = await readMagazinePublication(db, options);
    expect(result.status).toBe("ready");
    expect(result.articles[0].image).toBeNull();
    db.sqlite.exec("INSERT INTO asset_status_events(asset_id, status_seq, status, rights_status, reason_code) VALUES ('fixture-artwork', 2, 'verified', 'approved', 'fixture-rights-restored')");
    expect((await readMagazinePublication(db, options)).articles[0].image?.src).toBe(FIXTURE_ARTWORK);
  });

  it("never projects private digest media or unverified cross-origin publisher media", async () => {
    const db = await fixture();
    const result = await readMagazinePublication(db, { ...options, provenance: "publisher" });
    expect(result.status).toBe("ready");
    expect(result.articles.every((article) => article.image === null)).toBe(true);
    expect(JSON.stringify(result)).not.toContain("a".repeat(64));
    expect(JSON.stringify(result)).not.toContain("/api/media/");
  });

  it("treats unsuccessful D1 reads and thrown reads as unavailable without exception disclosure", async () => {
    const db = await fixture();
    const failed: D1DatabaseLike = {
      prepare: (sql) => {
        const original = db.prepare(sql);
        const wrap = (statement: D1PreparedStatementLike): D1PreparedStatementLike => ({
          bind: (...values) => wrap(statement.bind(...values)), run: () => { throw new Error("No writes"); },
          first: () => statement.first(), all: async () => ({ success: false, results: [] }),
        });
        return wrap(original);
      },
      batch: () => { throw new Error("No writes"); },
    };
    expect(await readMagazinePublication(failed, options)).toMatchObject({ status: "unavailable", articles: [] });
    const thrown: D1DatabaseLike = { prepare: () => { throw new Error("PRIVATE_DB_ERROR_MUST_NOT_LEAK"); }, batch: db.batch.bind(db) };
    const result = await readMagazinePublication(thrown, options);
    expect(result).toMatchObject({ status: "unavailable", articles: [] });
    expect(JSON.stringify(result)).not.toContain("PRIVATE_DB_ERROR");
  });

  it("executes SELECT-only reads in the producer", async () => {
    const db = await fixture();
    const sql: string[] = [];
    const readOnly: D1DatabaseLike = {
      prepare: (query) => { sql.push(query); return db.prepare(query); },
      batch: () => { throw new Error("Batch must not execute"); },
    };
    expect((await readMagazinePublication(readOnly, options)).status).toBe("ready");
    expect(sql.every((query) => /^\s*(?:\/\*[\s\S]*?\*\/\s*)?SELECT\b/i.test(query))).toBe(true);
  });

  it("deduplicates repeated edition candidates without duplicating public stories", async () => {
    const db = await fixture();
    const repeated: D1DatabaseLike = {
      prepare: (query) => {
        const wrap = (statement: D1PreparedStatementLike): D1PreparedStatementLike => ({
          bind: (...values) => wrap(statement.bind(...values)), run: () => { throw new Error("No writes"); },
          first: () => statement.first(),
          all: async <T,>() => {
            const result = await statement.all<T>();
            return query.includes("website:edition-current-candidates")
              ? { ...result, results: [...result.results!, ...result.results!] } : result;
          },
        });
        return wrap(db.prepare(query));
      }, batch: () => { throw new Error("No writes"); },
    };
    expect((await readMagazinePublication(repeated, options)).articles).toHaveLength(3);
  });

  it("fails unavailable on an observed withdrawal during read instead of returning stale content", async () => {
    const db = await fixture();
    let reads = 0;
    const changing: D1DatabaseLike = {
      prepare: (query) => {
        const wrap = (statement: D1PreparedStatementLike): D1PreparedStatementLike => ({
          bind: (...values) => wrap(statement.bind(...values)), run: () => { throw new Error("No writes"); },
          first: async <T,>() => {
            if (query.includes("WHERE s.slug = ?") && ++reads === 2) quarantineFixtureStory(db, "fixture-paper-and-type");
            return statement.first<T>();
          },
          all: () => statement.all(),
        });
        return wrap(db.prepare(query));
      }, batch: () => { throw new Error("No writes"); },
    };
    expect(await readMagazinePublication(changing, options)).toMatchObject({ status: "unavailable", articles: [] });
  });

  it("returns deterministic proof data through the real fixture entry point", async () => {
    const first = await readFixturePublication();
    expect(first.status).toBe("ready");
    expect(first).toEqual(await readFixturePublication());
  });

  it.each(["withdrawal", "image revocation"])("rechecks an earlier candidate after a later candidate observes %s", async (change) => {
    const db = await fixture();
    let evidenceReads = 0;
    const changing: D1DatabaseLike = {
      prepare: (query) => {
        const wrap = (statement: D1PreparedStatementLike): D1PreparedStatementLike => ({
          bind: (...values) => wrap(statement.bind(...values)), run: () => { throw new Error("No writes"); },
          first: () => statement.first(),
          all: async <T,>() => {
            if (query.includes("website:public-evidence") && ++evidenceReads === 3) {
              if (change === "withdrawal") quarantineFixtureStory(db, "fixture-paper-and-type");
              else db.sqlite.exec("INSERT INTO asset_status_events(asset_id, status_seq, status, rights_status, reason_code) VALUES ('fixture-artwork', 1, 'revoked', 'denied', 'fixture-late-revocation')");
            }
            return statement.all<T>();
          },
        });
        return wrap(db.prepare(query));
      }, batch: () => { throw new Error("No writes"); },
    };
    const result = await readMagazinePublication(changing, options);
    expect(evidenceReads).toBe(3);
    if (change === "withdrawal") expect(result).toMatchObject({ status: "unavailable", articles: [] });
    else {
      expect(result.status).toBe("ready");
      expect(result.articles[0].image).toBeNull();
    }
  });
});
