import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import * as schema from "../db/schema.ts";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);

const REQUIRED_TABLE_EXPORTS = [
  "sourceSystems",
  "collectorRuns",
  "publicationPackets",
  "stories",
  "storyVersions",
  "storyClaims",
  "evidenceRefs",
  "storyEvidence",
  "storyVisibilityEvents",
  "editions",
  "editionEntries",
  "editionPointer",
  "breakingPointer",
  "breakingEntries",
  "assets",
  "assetStatusEvents",
  "researchJobs",
  "researchResults",
  "opsIntents",
  "opsReceipts",
  "ingestNonces",
  "auditEvents",
  "auditStreamHeads",
  "releaseAttestations",
  "auditAnchorReceipts",
];

test("publication schema exposes every approved durable entity", () => {
  for (const name of REQUIRED_TABLE_EXPORTS) {
    assert.ok(schema[name], `missing schema export ${name}`);
  }
});

test("publication migration encodes replay, singleton-head, uniqueness, and state invariants", () => {
  const migrationPath = new URL(
    "../drizzle/0000_magazine_core.sql",
    import.meta.url,
  );
  assert.ok(existsSync(migrationPath), "core migration must exist");
  const sql = readFileSync(migrationPath, "utf8");

  assert.match(
    sql,
    /CREATE UNIQUE INDEX `story_versions_story_version_unique`[^;]+\(`story_id`,`version`\)/i,
  );
  assert.match(
    sql,
    /CREATE UNIQUE INDEX `audit_events_stream_seq_unique`[^;]+\(`stream_id`,`stream_seq`\)/i,
  );
  assert.match(
    sql,
    /CREATE TABLE `publication_packets`[^;]+`packet_id` text PRIMARY KEY[^;]+`manifest_hash`[^;]+CHECK\s*\([^;]*manifest_hash/is,
  );
  assert.match(
    sql,
    /singleton_check[^;]+CHECK\([^;]+["`]singleton_id["`] = 1\)/i,
  );
  assert.match(
    sql,
    /CHECK\([^;]+["`]publication_state["`] in \('building', 'published', 'superseded', 'failed'\)\)/i,
  );
});

class SqliteD1Statement {
  constructor(owner, sql, values = []) {
    this.owner = owner;
    this.sql = sql;
    this.values = values;
  }

  bind(...values) {
    return new SqliteD1Statement(this.owner, this.sql, values);
  }

  _runSync() {
    const result = this.owner.sqlite.prepare(this.sql).run(...this.values);
    return {
      success: true,
      results: [],
      meta: { changes: Number(result.changes) },
    };
  }

  async run() {
    return this._runSync();
  }

  async first() {
    return this.owner.sqlite.prepare(this.sql).get(...this.values) ?? null;
  }

  async all() {
    return {
      success: true,
      results: this.owner.sqlite.prepare(this.sql).all(...this.values),
      meta: { changes: 0 },
    };
  }
}

class SqliteD1Database {
  constructor() {
    this.sqlite = new DatabaseSync(":memory:");
    this.sqlite.exec("PRAGMA foreign_keys = ON");
    const migration = readFileSync(
      new URL("../drizzle/0000_magazine_core.sql", import.meta.url),
      "utf8",
    ).replaceAll("--> statement-breakpoint", "");
    this.sqlite.exec(migration);
  }

  prepare(sql) {
    return new SqliteD1Statement(this, sql);
  }

  async batch(statements) {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const results = statements.map((statement) => statement._runSync());
      this.sqlite.exec("COMMIT");
      return results;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }

  execute(sql, ...values) {
    return this.sqlite.prepare(sql).run(...values);
  }

  get(sql, ...values) {
    return this.sqlite.prepare(sql).get(...values) ?? null;
  }
}

function evidence(overrides = {}) {
  return {
    evidence_id: "evidence-1",
    root_source_id: "root-1",
    canonical_url: "https://example.com/regulation",
    publisher: "Example Authority",
    document_citation: "Regulation 1/2026",
    published_at: "2026-07-17T20:00:00Z",
    retrieved_at: "2026-07-17T21:00:00Z",
    source_type: "official",
    primary_document_status: "verified",
    root_resolution_status: "resolved",
    independence_verdict: "independent",
    evidence_note: "The authority published the effective date.",
    upstream_root_source_ids: [],
    syndication_group_fingerprint: "sg-1",
    independence_ruleset_version: "independence.v1",
    independence_reason: "issuing-authority-primary-document",
    counts_toward_breaking: true,
    ...overrides,
  };
}

function story(overrides = {}) {
  return {
    story_id: "story-1",
    version: 2,
    expected_current_version: 1,
    slug: "important-regulation",
    language: "en",
    domain: "compliance",
    severity: "high",
    lifecycle_state: "verified",
    first_seen_at: "2026-07-17T20:00:00Z",
    updated_at: "2026-07-17T21:00:00Z",
    title: "An important regulation changed",
    deck: "The official source confirms the effective date.",
    summary: "A concise sanitized summary.",
    why_it_matters: "Operators should review affected deadlines.",
    curiosity_text: null,
    score_components: {
      editorial: 0.9,
      impact: 0.9,
      freshness: 0.8,
      evidence: 1,
      diversity: 0.5,
    },
    claims: [
      {
        claim_id: "claim-1",
        claim_kind: "fact",
        normalized_text: "The regulation has an effective date.",
        numeric_value: null,
        numeric_unit: null,
        as_of: "2026-07-18",
        evidence_ids: ["evidence-1"],
        breaking_gate: "official-primary",
      },
    ],
    evidence_refs: [evidence()],
    contributing_system_ids: ["regulatory-watcher"],
    coverage_state: "full",
    confidence: "high",
    asset_digests: [HASH_A],
    adapter_version: "adapter.v1",
    ruleset_version: "rules.v1",
    ...overrides,
  };
}

function breaking(overrides = {}) {
  return {
    schema_version: "story.v1",
    packet_id: "packet-breaking-1",
    publication_target: "breaking",
    expected_breaking_revision: 4,
    publication_state: "building",
    verified_at: "2026-07-17T21:01:00Z",
    story: story(),
    ...overrides,
  };
}

function edition(overrides = {}) {
  const editionStory = story({ severity: "medium" });
  return {
    schema_version: "edition.v1",
    packet_id: "packet-edition-1",
    editor_version: "editor.v1",
    ruleset_version: "rules.v1",
    edition_date: "2026-07-18",
    edition_revision: 5,
    expected_current_revision: 4,
    expected_breaking_revision: 4,
    edition_kind: "morning",
    publication_state: "building",
    coverage_state: "full",
    readiness_cutoff: "2026-07-17T22:15:00Z",
    verified_at: "2026-07-17T22:16:00Z",
    collector_run_ids: ["run-1"],
    stories: [editionStory],
    placements: [
      {
        story_id: editionStory.story_id,
        version: editionStory.version,
        section: "compliance",
        order: 1,
      },
    ],
    breaking_story_ids: [],
    referenced_claim_ids: ["claim-1"],
    referenced_evidence_ids: ["evidence-1"],
    asset_digests: [HASH_A],
    coverage_gaps: [],
    reader_notices: [],
    ...overrides,
  };
}

function seedHeadsAndAsset(
  db,
  { editionRevision = 0, breakingRevision = 0 } = {},
) {
  db.execute(
    "INSERT INTO edition_pointer(singleton_id, current_revision) VALUES (1, ?)",
    editionRevision,
  );
  db.execute(
    "INSERT INTO breaking_pointer(singleton_id, active_revision) VALUES (1, ?)",
    breakingRevision,
  );
  db.execute(
    `INSERT INTO assets(
       asset_id, packet_id, sha256, r2_key, mime_type, byte_count, width,
       height, alt_text, source, rights_status, status
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    "asset-1",
    "asset-packet-1",
    HASH_A,
    `assets/sha256/${HASH_A}.webp`,
    "image/webp",
    1024,
    1200,
    800,
    "Editorial image",
    "editorial",
    "approved",
    "verified",
  );
}

function seedStoryHead(db, version = 1) {
  db.execute(
    "INSERT INTO stories(story_id, slug, current_version) VALUES (?, ?, ?)",
    "story-1",
    "important-regulation",
    version,
  );
}

async function loadRepository(db) {
  const modulePath = new URL(
    "../lib/server/publication-repository.ts",
    import.meta.url,
  );
  assert.ok(existsSync(modulePath), "publication repository must exist");
  const { createPublicationRepository } = await import(modulePath);
  return createPublicationRepository(db, {
    now: () => "2026-07-17T22:17:00.000Z",
  });
}

test("publication replay accepts the same manifest and rejects a hash mismatch", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();

  assert.equal(await repository.stageEdition(packet, HASH_A), "staged");
  assert.equal(await repository.stageEdition(packet, HASH_A), "replay");
  await assert.rejects(
    repository.stageEdition(packet, HASH_B),
    /replay hash mismatch/i,
  );
});

test("a failed edition CAS exposes no staged row", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 9, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();

  await repository.stageEdition(packet, HASH_A);
  await assert.rejects(
    repository.finalizeEdition(packet.packet_id),
    /CAS conflict/,
  );

  assert.equal(await repository.getCurrentEdition(), null);
  assert.equal(await repository.getCurrentStory(packet.stories[0].slug), null);
  assert.equal(
    db.get(
      "SELECT publication_state FROM editions WHERE edition_id = ?",
      packet.packet_id,
    ).publication_state,
    "building",
  );
});

test("standalone Breaking commits both heads or neither", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = breaking();

  await repository.stageBreaking(packet, HASH_A);
  await repository.finalizeBreaking(packet.packet_id);

  assert.equal(
    (await repository.getCurrentStory(packet.story.slug))?.version,
    2,
  );
  assert.deepEqual(await repository.getActiveBreaking(), [
    packet.story.story_id,
  ]);
});

test("a Breaking CAS conflict leaves both story and Breaking heads unchanged", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { breakingRevision: 7 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = breaking();

  await repository.stageBreaking(packet, HASH_A);
  await assert.rejects(
    repository.finalizeBreaking(packet.packet_id),
    /CAS conflict/,
  );

  assert.equal(
    db.get("SELECT current_version FROM stories WHERE story_id = 'story-1'")
      .current_version,
    1,
  );
  assert.equal(
    db.get(
      "SELECT active_revision FROM breaking_pointer WHERE singleton_id = 1",
    ).active_revision,
    7,
  );
  assert.equal(
    db.get(
      "SELECT publication_state FROM story_versions WHERE story_id = 'story-1' AND version = 2",
    ).publication_state,
    "building",
  );
});
