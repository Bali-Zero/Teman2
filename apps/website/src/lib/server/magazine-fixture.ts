import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { DatabaseSync, type SQLInputValue } from "node:sqlite";
import {
  createPublicationRepository,
  type D1DatabaseLike,
  type D1PreparedStatementLike,
  type D1ResultLike,
} from "../../../../bali-zero-magazine/lib/server/publication-repository";
import type { EditionPacketV1, StoryVersionV1 } from "../../../../bali-zero-magazine/lib/contracts/publication";
import { readMagazinePublication, type MagazinePublicationEnvelope } from "./magazine-publication";

export const FIXTURE_DATES = {
  publication: "2026-09-01T08:00:00.000Z",
  amendment: "2026-09-02T08:00:00.000Z",
} as const;
const ARTWORK_HASH = "a".repeat(64);

// Local proof only. SQLite executes the publisher's actual migrations and SQL;
// it does not emulate Cloudflare's latency, authorization, or deployment binding.
class FixtureStatement implements D1PreparedStatementLike {
  constructor(readonly owner: MagazineFixtureDatabase, readonly sql: string, readonly values: readonly unknown[] = []) {}
  bind(...values: readonly unknown[]): FixtureStatement { return new FixtureStatement(this.owner, this.sql, values); }
  runSync<T>(): D1ResultLike<T> {
    const result = this.owner.sqlite.prepare(this.sql).run(...this.values as SQLInputValue[]);
    return { success: true, results: [], meta: { changes: Number(result.changes) } };
  }
  async run<T>(): Promise<D1ResultLike<T>> { return this.runSync<T>(); }
  async first<T>(): Promise<T | null> {
    return (this.owner.sqlite.prepare(this.sql).get(...this.values as SQLInputValue[]) as T | undefined) ?? null;
  }
  async all<T>(): Promise<D1ResultLike<T>> {
    return { success: true, results: this.owner.sqlite.prepare(this.sql).all(...this.values as SQLInputValue[]) as T[] };
  }
}

export class MagazineFixtureDatabase implements D1DatabaseLike {
  readonly sqlite = new DatabaseSync(":memory:");
  constructor() {
    // The candidate supports execution from either its worktree root or app root.
    const fromApp = resolve(process.cwd(), "../bali-zero-magazine/drizzle");
    const fromWorktree = resolve(process.cwd(), "apps/bali-zero-magazine/drizzle");
    const directory = existsSync(fromApp) ? fromApp : fromWorktree;
    try {
      this.sqlite.exec("PRAGMA foreign_keys = ON");
      for (const file of readdirSync(directory).filter((name) => /^\d+.*\.sql$/.test(name)).sort()) {
        this.sqlite.exec(readFileSync(resolve(directory, file), "utf8").replaceAll("--> statement-breakpoint", ""));
      }
    } catch (error) {
      this.sqlite.close();
      throw error;
    }
  }
  prepare(sql: string): FixtureStatement { return new FixtureStatement(this, sql); }
  async batch<T>(statements: readonly D1PreparedStatementLike[]): Promise<readonly D1ResultLike<T>[]> {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const results = statements.map((statement) => {
        if (!(statement instanceof FixtureStatement)) throw new Error("Foreign fixture statement");
        return statement.runSync<T>();
      });
      this.sqlite.exec("COMMIT");
      return results;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }
  close(): void { this.sqlite.close(); }
}

function story(id: string, title: string, summary: string, withImage = false): StoryVersionV1 {
  return {
    story_id: id, slug: id, version: 1, expected_current_version: 0,
    language: "en", domain: "general", severity: "low", lifecycle_state: "verified",
    first_seen_at: FIXTURE_DATES.publication, event_occurred_at: null,
    updated_at: FIXTURE_DATES.publication, title,
    deck: "A synthetic editorial record for this local website preview.", summary,
    why_it_matters: "This preview demonstrates the reading experience. It is not news or regulatory advice.",
    curiosity_text: null,
    score_components: { editorial: 1, impact: 0, freshness: 1, evidence: 1, diversity: 1 },
    claims: [{
      claim_id: `${id}-claim`, claim_kind: "analysis", legal_effect: "none",
      normalized_text: "This is an explicitly approved synthetic website fixture.",
      numeric_value: null, numeric_unit: null, as_of: null,
      evidence_ids: [`${id}-evidence`], breaking_gate: null,
    }],
    evidence_refs: [{
      evidence_id: `${id}-evidence`, root_source_id: `${id}-private-root`,
      canonical_url: `https://example.org/${id}`,
      publisher: "Synthetic editorial fixture", document_citation: "Local design proof; not a news source",
      published_at: FIXTURE_DATES.publication, retrieved_at: FIXTURE_DATES.publication,
      source_type: "research", primary_document_status: "not-primary", root_resolution_status: "resolved",
      independence_verdict: "independent", evidence_note: "PRIVATE_FIXTURE_NOTE_MUST_NOT_LEAK",
      upstream_root_source_ids: [], syndication_group_fingerprint: `${id}-private-fingerprint`,
      independence_ruleset_version: "fixture.v1", independence_reason: "synthetic-design-proof", counts_toward_breaking: false,
    }],
    contributing_system_ids: [], coverage_state: "full", confidence: "high",
    asset_digests: withImage ? [ARTWORK_HASH] : [], adapter_version: "fixture.v1", ruleset_version: "fixture.v1",
  };
}

function edition(stories: readonly StoryVersionV1[], packetId = "fixture-approved-edition"): EditionPacketV1 {
  return {
    schema_version: "edition.v1", packet_id: packetId, editor_version: "fixture.v1", ruleset_version: "fixture.v1",
    edition_date: "2026-09-01", edition_revision: 1, expected_current_revision: 0, expected_breaking_revision: 0,
    edition_kind: stories.length ? "standard" : "quiet", publication_state: "building", coverage_state: "complete",
    readiness_cutoff: FIXTURE_DATES.publication, verified_at: FIXTURE_DATES.publication,
    collector_run_ids: [], stories,
    placements: stories.map((item, index) => ({ story_id: item.story_id, version: item.version, section: "general", order: index, lead: index === 0 })),
    breaking_story_ids: [], referenced_claim_ids: stories.flatMap((item) => item.claims.map((claim) => claim.claim_id)),
    referenced_evidence_ids: stories.flatMap((item) => item.evidence_refs.map((ref) => ref.evidence_id)),
    asset_digests: [...new Set(stories.flatMap((item) => item.asset_digests))], coverage_gaps: [], reader_notices: [],
  };
}

export function quarantineFixtureStory(db: MagazineFixtureDatabase, storyId: string, seq = 1, quarantined = true): void {
  const current = db.sqlite.prepare("SELECT current_version FROM stories WHERE story_id = ?").get(storyId)!;
  const eventId = `fixture-visibility-${storyId}-${seq}`;
  db.sqlite.prepare(`INSERT INTO audit_events(event_id, stream_id, stream_seq, payload_json, previous_event_hash, event_hash)
    VALUES (?, ?, ?, '{}', ?, ?)`).run(eventId, `fixture-visibility:${storyId}`, seq, "0".repeat(64), `${seq.toString(16)}`.padStart(64, "0"));
  db.sqlite.prepare(`INSERT INTO story_visibility_events(story_id, visibility_seq, story_version, intent_id, desired_quarantined, audit_event_id)
    VALUES (?, ?, ?, ?, ?, ?)`).run(storyId, seq, current.current_version, eventId, quarantined ? 1 : 0, eventId);
}

/** All writes are limited to this newly created in-memory database. */
export async function createMagazineFixture(): Promise<MagazineFixtureDatabase> {
  const db = new MagazineFixtureDatabase();
  try {
    db.sqlite.prepare("INSERT INTO assets(sha256, r2_key, mime_type, byte_count, width, height) VALUES (?, ?, 'image/png', 1024, 1200, 800)")
      .run(ARTWORK_HASH, `fixture-artwork/${ARTWORK_HASH}.png`);
    db.sqlite.prepare(`INSERT INTO asset_sources(asset_id, packet_id, canonical_sha256, source_sha256,
      source_byte_count, source_mime_type, source_width, source_height, alt_text, source,
      rights_basis, rights_status, usage_status, dlp_status, sanitization_status, perceptual_dedup_status, status)
      VALUES ('fixture-artwork', 'fixture-artwork-packet', ?, ?, 1024, 'image/png', 1200, 800,
      'Abstract paper, forest and copper shapes — original local preview artwork', 'Original local fixture artwork',
      'internal-owned', 'approved', 'approved', 'passed', 'passed', 'unique', 'verified')`).run(ARTWORK_HASH, ARTWORK_HASH);

    const records = [
      story("fixture-paper-and-type", "A place for paper and type", "A synthetic design note exploring the Journal’s paper, forest and copper palette.", true),
      story("fixture-room-to-read", "Room to read", "A synthetic editorial note about clear summaries, quiet spacing and a useful reading order."),
      story("fixture-notes-in-the-margin", "Notes in the margin", "The first version of a synthetic design note."),
      story("fixture-withdrawn", "WITHDRAWN_FIXTURE_TITLE_MUST_NOT_LEAK", "WITHDRAWN_FIXTURE_SUMMARY_MUST_NOT_LEAK"),
    ];
    const repository = createPublicationRepository(db, { now: () => FIXTURE_DATES.publication });
    const packet = edition(records);
    await repository.stageEdition(packet, "b".repeat(64));
    await repository.finalizeEdition(packet.packet_id);

    const original = records[2];
    const amended: StoryVersionV1 = {
      ...original, version: 2, expected_current_version: 1, lifecycle_state: "amended", updated_at: FIXTURE_DATES.amendment,
      summary: "This synthetic note was revised to demonstrate a visible amendment and dated revision history.",
      claims: original.claims.map((claim) => ({ ...claim, claim_id: `${claim.claim_id}-v2` })),
    };
    const correction = createPublicationRepository(db, { now: () => FIXTURE_DATES.amendment });
    await correction.stageBreaking({
      schema_version: "story.v1", packet_id: "fixture-approved-amendment", publication_target: "breaking",
      expected_breaking_revision: 1, publication_state: "building", verified_at: FIXTURE_DATES.amendment, story: amended,
    }, "c".repeat(64));
    await correction.finalizeBreaking("fixture-approved-amendment");
    // Legacy finalization currently leaves the older version published. The
    // adapter must select the current version in either permitted history state.
    quarantineFixtureStory(db, "fixture-withdrawn");
    await correction.stageBreaking({
      schema_version: "story.v1", packet_id: "fixture-unapproved-draft", publication_target: "breaking",
      expected_breaking_revision: 2, publication_state: "building", verified_at: FIXTURE_DATES.amendment,
      story: story("fixture-building", "UNPUBLISHED_FIXTURE_TITLE_MUST_NOT_LEAK", "UNPUBLISHED_FIXTURE_SUMMARY_MUST_NOT_LEAK"),
    }, "d".repeat(64));
    return db;
  } catch (error) {
    db.close();
    throw error;
  }
}

export async function readFixturePublication(): Promise<MagazinePublicationEnvelope> {
  let db: MagazineFixtureDatabase | undefined;
  try {
    db = await createMagazineFixture();
    return await readMagazinePublication(db, { provenance: "fixture", approvedEvidenceOrigins: ["https://example.org"] });
  } catch {
    return { version: 2, publisher: "bali-zero-magazine", status: "unavailable", articles: [], provenance: "fixture" };
  } finally {
    db?.close();
  }
}
