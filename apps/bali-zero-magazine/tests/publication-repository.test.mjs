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
  "storyAssetReferences",
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
  assert.match(
    sql,
    /story_versions_expected_version_check[^;]+version[^;]+expected_current_version[^;]+\+ 1/i,
  );
  assert.match(sql, /editions_kind_check[^;]+\('standard', 'quiet'\)/i);
  assert.match(sql, /editions_coverage_check[^;]+\('complete', 'partial'\)/i);
  assert.match(
    sql,
    /CREATE UNIQUE INDEX `edition_entries_single_lead_unique`[^;]+\(`edition_id`\)[^;]+is_lead[^;]+1/i,
  );
  assert.match(sql, /edition_entries_lead_check[^;]+is_lead[^;]+\(0, 1\)/i);
  assert.match(
    sql,
    /CREATE TABLE `story_versions`[^;]+`event_occurred_at` text/is,
  );
  assert.match(
    sql,
    /CREATE TABLE `asset_status_events`[^;]+`rights_status` text NOT NULL/is,
  );
  assert.match(
    sql,
    /INSERT INTO edition_pointer[^;]+VALUES\s*\(1,\s*NULL,\s*0\)/i,
  );
  assert.match(
    sql,
    /INSERT INTO breaking_pointer[^;]+VALUES\s*\(1,\s*0,\s*NULL\)/i,
  );
  for (const table of [
    "story_claims",
    "story_evidence",
    "edition_entries",
    "breaking_entries",
    "story_asset_references",
  ]) {
    assert.match(
      sql,
      new RegExp(
        `CREATE TABLE .${table}.[^;]+.packet_id.[^;]+.publication_state.`,
        "is",
      ),
    );
  }
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
    if (this.owner.beforeFirst) await this.owner.beforeFirst(this.sql);
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
    this.beforeFirst = null;
    this.failBatchAfterIndex = null;
  }

  prepare(sql) {
    return new SqliteD1Statement(this, sql);
  }

  async batch(statements) {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const results = [];
      for (const [index, statement] of statements.entries()) {
        results.push(statement._runSync());
        if (index === this.failBatchAfterIndex) {
          throw new Error(`injected batch failure after statement ${index}`);
        }
      }
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
    event_occurred_at: "2026-07-17T19:30:00Z",
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
    edition_kind: "standard",
    publication_state: "building",
    coverage_state: "complete",
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
        lead: true,
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

function seedAsset(db, { assetId = "asset-1", digest = HASH_A } = {}) {
  db.execute(
    `INSERT INTO assets(
       asset_id, packet_id, sha256, r2_key, mime_type, byte_count, width,
       height, alt_text, source, rights_status, status
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    assetId,
    "asset-packet-1",
    digest,
    `assets/sha256/${digest}.webp`,
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

function seedHeadsAndAsset(
  db,
  { editionRevision = 0, breakingRevision = 0 } = {},
) {
  db.execute(
    "UPDATE edition_pointer SET current_edition_id = NULL, current_revision = ? WHERE singleton_id = 1",
    editionRevision,
  );
  db.execute(
    "UPDATE breaking_pointer SET active_revision = ?, updated_at = NULL WHERE singleton_id = 1",
    breakingRevision,
  );
  seedAsset(db);
}

function seedStoryHead(db, version = 1) {
  db.execute(
    "INSERT INTO stories(story_id, slug, current_version) VALUES (?, ?, ?)",
    "story-1",
    "important-regulation",
    version,
  );
}

function appendVisibilityEvent(db, { seq, quarantined, storyVersion = 2 }) {
  const eventId = `audit-visibility-${seq}`;
  db.execute(
    `INSERT INTO audit_events(
       event_id, stream_id, stream_seq, payload_json,
       previous_event_hash, event_hash
     ) VALUES (?, ?, ?, ?, ?, ?)`,
    eventId,
    "story-visibility:story-1",
    seq,
    "{}",
    "0".repeat(64),
    (seq % 2 === 0 ? "b" : "a").repeat(64),
  );
  db.execute(
    `INSERT INTO story_visibility_events(
       story_id, visibility_seq, story_version, intent_id,
       desired_quarantined, audit_event_id
     ) VALUES (?, ?, ?, ?, ?, ?)`,
    "story-1",
    seq,
    storyVersion,
    `intent-visibility-${seq}`,
    quarantined ? 1 : 0,
    eventId,
  );
}

function appendAssetStatusEvent(
  db,
  { seq, status = "verified", rightsStatus = "approved" },
) {
  db.execute(
    `INSERT INTO asset_status_events(
       asset_id, status_seq, status, rights_status, reason_code
     ) VALUES (?, ?, ?, ?, ?)`,
    "asset-1",
    seq,
    status,
    rightsStatus,
    `asset-status-${seq}`,
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

function firstEdition(overrides = {}) {
  const firstStory = story({ version: 1, expected_current_version: 0 });
  return edition({
    edition_revision: 1,
    expected_current_revision: 0,
    expected_breaking_revision: 0,
    stories: [firstStory],
    placements: [
      {
        story_id: firstStory.story_id,
        version: firstStory.version,
        section: "compliance",
        order: 1,
        lead: true,
      },
    ],
    ...overrides,
  });
}

function independentStory(suffix, evidenceRecord = evidence()) {
  return story({
    story_id: `story-${suffix}`,
    version: 1,
    expected_current_version: 0,
    slug: `important-regulation-${suffix}`,
    claims: [
      {
        ...story().claims[0],
        claim_id: `claim-${suffix}`,
        evidence_ids: [evidenceRecord.evidence_id],
      },
    ],
    evidence_refs: [evidenceRecord],
  });
}

function twoPartyBarrier() {
  let arrivals = 0;
  let release;
  const released = new Promise((resolve) => {
    release = resolve;
  });
  return async () => {
    arrivals += 1;
    if (arrivals === 2) release();
    await released;
  };
}

function installPacketReadBarrier(db) {
  const wait = twoPartyBarrier();
  db.beforeFirst = async (sql) => {
    if (/FROM publication_packets WHERE packet_id = \?/i.test(sql)) {
      await wait();
    }
  };
}

function assertPacketAndHeadsRemainStaged(
  db,
  packetId,
  { editionRevision, breakingRevision, storyVersion },
) {
  assert.equal(
    db.get(
      "SELECT publication_state FROM publication_packets WHERE packet_id = ?",
      packetId,
    ).publication_state,
    "building",
  );
  assert.equal(
    db.get(
      "SELECT publication_state FROM story_versions WHERE packet_id = ?",
      packetId,
    ).publication_state,
    "building",
  );
  assert.equal(
    db.get(
      "SELECT current_revision FROM edition_pointer WHERE singleton_id = 1",
    ).current_revision,
    editionRevision,
  );
  assert.equal(
    db.get(
      "SELECT active_revision FROM breaking_pointer WHERE singleton_id = 1",
    ).active_revision,
    breakingRevision,
  );
  assert.equal(
    db.get("SELECT current_version FROM stories WHERE story_id = 'story-1'")
      .current_version,
    storyVersion,
  );
}

function assertPacketGraphRemainsBuilding(db, packetId, tables) {
  for (const table of tables) {
    const row = db.get(
      `SELECT count(*) AS count,
              sum(publication_state = 'building') AS building
       FROM ${table} WHERE packet_id = ?`,
      packetId,
    );
    assert.ok(row.count > 0, `${table} must contain packet rows`);
    assert.equal(
      row.building,
      row.count,
      `${table} rows must remain building after rollback`,
    );
  }
}

test("fresh migration seeds singleton heads and publishes the first edition", async () => {
  const db = new SqliteD1Database();
  seedAsset(db);
  const repository = await loadRepository(db);
  const packet = firstEdition();

  assert.deepEqual(
    {
      ...db.get(
        "SELECT current_edition_id, current_revision FROM edition_pointer WHERE singleton_id = 1",
      ),
    },
    { current_edition_id: null, current_revision: 0 },
  );
  assert.deepEqual(
    {
      ...db.get(
        "SELECT active_revision, updated_at FROM breaking_pointer WHERE singleton_id = 1",
      ),
    },
    { active_revision: 0, updated_at: null },
  );

  await repository.stageEdition(packet, HASH_A);
  assert.equal(await repository.finalizeEdition(packet.packet_id), "published");
  assert.equal((await repository.getCurrentEdition())?.edition_revision, 1);
  assert.equal(
    (await repository.getCurrentStory(packet.stories[0].slug))?.version,
    1,
  );
});

test("D1 rejects story versions that skip the exact next version", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  await repository.stageEdition(edition(), HASH_A);

  assert.throws(
    () =>
      db.execute(
        `INSERT INTO story_versions
        SELECT story_id, version + 1, packet_id, expected_current_version,
               language, domain, severity, lifecycle_state, first_seen_at,
               event_occurred_at, updated_at, title, deck, summary,
               why_it_matters, curiosity_text,
               score_components_json, claim_ids_json, contributing_system_ids_json,
               coverage_state, confidence, asset_digests_json, adapter_version,
               ruleset_version, publication_state, published_at
        FROM story_versions WHERE packet_id = ?`,
        "packet-edition-1",
      ),
    /story_versions_expected_version_check|CHECK constraint failed/i,
  );
});

test("concurrent identical packet staging returns staged plus replay", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  installPacketReadBarrier(db);
  const repository = await loadRepository(db);
  const packet = edition();

  const results = await Promise.all([
    repository.stageEdition(packet, HASH_A),
    repository.stageEdition(packet, HASH_A),
  ]);

  assert.deepEqual([...results].sort(), ["replay", "staged"]);
  assert.equal(
    db.get("SELECT count(*) AS count FROM publication_packets").count,
    1,
  );
});

test("concurrent packet hash mismatch remains fail closed", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  installPacketReadBarrier(db);
  const repository = await loadRepository(db);
  const packet = edition();

  const results = await Promise.allSettled([
    repository.stageEdition(packet, HASH_A),
    repository.stageEdition(packet, HASH_B),
  ]);
  const fulfilled = results.filter((result) => result.status === "fulfilled");
  const rejected = results.filter((result) => result.status === "rejected");

  assert.equal(fulfilled.length, 1);
  assert.equal(fulfilled[0].value, "staged");
  assert.equal(rejected.length, 1);
  assert.match(String(rejected[0].reason), /replay hash mismatch/i);
});

test("evidence IDs accept exact immutable reuse and reject changed content", async () => {
  const db = new SqliteD1Database();
  seedAsset(db);
  const repository = await loadRepository(db);
  const sharedEvidence = evidence();
  const first = breaking({
    packet_id: "packet-evidence-1",
    expected_breaking_revision: 0,
    story: independentStory("evidence-1", sharedEvidence),
  });
  const exactReuse = breaking({
    packet_id: "packet-evidence-2",
    expected_breaking_revision: 0,
    story: independentStory("evidence-2", sharedEvidence),
  });
  const changedReuse = breaking({
    packet_id: "packet-evidence-3",
    expected_breaking_revision: 0,
    story: independentStory(
      "evidence-3",
      evidence({ publisher: "A different authority" }),
    ),
  });

  assert.equal(await repository.stageBreaking(first, HASH_A), "staged");
  assert.equal(await repository.stageBreaking(exactReuse, HASH_B), "staged");
  await assert.rejects(
    repository.stageBreaking(changedReuse, "c".repeat(64)),
    /immutable evidence conflict/i,
  );
  assert.equal(
    db.get(
      "SELECT publisher FROM evidence_refs WHERE evidence_id = 'evidence-1'",
    ).publisher,
    "Example Authority",
  );
  assert.equal(
    db.get(
      "SELECT count(*) AS count FROM publication_packets WHERE packet_id = 'packet-evidence-3'",
    ).count,
    0,
  );
});

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
  assert.deepEqual(
    (await repository.getActiveBreaking()).map((story) => story.story_id),
    [packet.story.story_id],
  );
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

test("edition finalization promotes the complete packet-scoped graph", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();

  await repository.stageEdition(packet, HASH_A);
  assert.equal(await repository.finalizeEdition(packet.packet_id), "published");

  for (const table of [
    "story_versions",
    "story_claims",
    "story_evidence",
    "edition_entries",
    "story_asset_references",
  ]) {
    assert.deepEqual(
      {
        ...db.get(
          `SELECT count(*) AS count,
                sum(publication_state = 'published') AS published
         FROM ${table} WHERE packet_id = ?`,
          packet.packet_id,
        ),
      },
      { count: 1, published: 1 },
      `${table} must be promoted exactly once`,
    );
  }
  const publishedEntries = (await repository.getCurrentEdition())?.entries;
  assert.deepEqual(
    publishedEntries?.map((entry) => ({
      story_id: entry.story_id,
      version: entry.version,
      section: entry.section,
      order: entry.order,
      lead: entry.lead,
    })),
    [
      {
        story_id: "story-1",
        version: 2,
        section: "compliance",
        order: 1,
        lead: true,
      },
    ],
  );
  assert.deepEqual(
    publishedEntries?.map((entry) => ({
      slug: entry.story.slug,
      domain: entry.story.domain,
      firstSeenAt: entry.story.first_seen_at,
      eventOccurredAt: entry.story.event_occurred_at,
      updatedAt: entry.story.updated_at,
    })),
    [
      {
        slug: packet.stories[0].slug,
        domain: packet.stories[0].domain,
        firstSeenAt: packet.stories[0].first_seen_at,
        eventOccurredAt: packet.stories[0].event_occurred_at,
        updatedAt: packet.stories[0].updated_at,
      },
    ],
  );
});

test("concurrent duplicate edition finalization returns published plus replay", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();
  await repository.stageEdition(packet, HASH_A);
  installPacketReadBarrier(db);

  const results = await Promise.all([
    repository.finalizeEdition(packet.packet_id),
    repository.finalizeEdition(packet.packet_id),
  ]);

  assert.deepEqual([...results].sort(), ["published", "replay"]);
});

test("concurrent duplicate Breaking finalization returns published plus replay", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = breaking();
  await repository.stageBreaking(packet, HASH_A);
  installPacketReadBarrier(db);

  const results = await Promise.all([
    repository.finalizeBreaking(packet.packet_id),
    repository.finalizeBreaking(packet.packet_id),
  ]);

  assert.deepEqual([...results].sort(), ["published", "replay"]);
});

test("edition finalization rejects a latest quarantine overlay atomically", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();
  await repository.stageEdition(packet, HASH_A);
  appendVisibilityEvent(db, { seq: 1, quarantined: true });

  await assert.rejects(
    repository.finalizeEdition(packet.packet_id),
    /CAS conflict/,
  );
  assertPacketAndHeadsRemainStaged(db, packet.packet_id, {
    editionRevision: 4,
    breakingRevision: 4,
    storyVersion: 1,
  });
  assertPacketGraphRemainsBuilding(db, packet.packet_id, [
    "publication_packets",
    "editions",
    "story_versions",
    "story_claims",
    "story_evidence",
    "edition_entries",
    "story_asset_references",
  ]);
});

for (const overlay of [
  {
    name: "quarantined asset status",
    status: "quarantined",
    rightsStatus: "approved",
  },
  {
    name: "denied asset rights",
    status: "verified",
    rightsStatus: "denied",
  },
]) {
  test(`Breaking finalization rejects the latest ${overlay.name} atomically`, async () => {
    const db = new SqliteD1Database();
    seedHeadsAndAsset(db, { breakingRevision: 4 });
    seedStoryHead(db);
    const repository = await loadRepository(db);
    const packet = breaking();
    await repository.stageBreaking(packet, HASH_A);
    appendAssetStatusEvent(db, { seq: 1, ...overlay });

    await assert.rejects(
      repository.finalizeBreaking(packet.packet_id),
      /CAS conflict/,
    );
    assertPacketAndHeadsRemainStaged(db, packet.packet_id, {
      editionRevision: 0,
      breakingRevision: 4,
      storyVersion: 1,
    });
    assertPacketGraphRemainsBuilding(db, packet.packet_id, [
      "publication_packets",
      "story_versions",
      "story_claims",
      "story_evidence",
      "breaking_entries",
      "story_asset_references",
    ]);
  });
}

test("edition finalization evaluates only the latest visibility and asset overlays", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();
  await repository.stageEdition(packet, HASH_A);
  appendVisibilityEvent(db, { seq: 1, quarantined: true });
  appendVisibilityEvent(db, { seq: 2, quarantined: false });
  appendAssetStatusEvent(db, {
    seq: 1,
    status: "quarantined",
    rightsStatus: "denied",
  });
  appendAssetStatusEvent(db, {
    seq: 2,
    status: "verified",
    rightsStatus: "approved",
  });

  assert.equal(await repository.finalizeEdition(packet.packet_id), "published");
});

test("late edition batch failure rolls back promoted graph rows and heads", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();
  await repository.stageEdition(packet, HASH_A);
  db.failBatchAfterIndex = 7;

  await assert.rejects(
    repository.finalizeEdition(packet.packet_id),
    /CAS conflict/,
  );
  assertPacketAndHeadsRemainStaged(db, packet.packet_id, {
    editionRevision: 4,
    breakingRevision: 4,
    storyVersion: 1,
  });
  assertPacketGraphRemainsBuilding(db, packet.packet_id, [
    "publication_packets",
    "editions",
    "story_versions",
    "story_claims",
    "story_evidence",
    "edition_entries",
    "story_asset_references",
  ]);
});

for (const fault of [
  {
    name: "claim",
    sql: "UPDATE story_claims SET publication_state = 'failed' WHERE packet_id = ?",
  },
  {
    name: "claim evidence link",
    sql: "DELETE FROM story_evidence WHERE packet_id = ?",
  },
  {
    name: "edition placement",
    sql: "UPDATE edition_entries SET publication_state = 'failed' WHERE packet_id = ?",
  },
  {
    name: "edition lead designation",
    sql: "UPDATE edition_entries SET is_lead = 0 WHERE packet_id = ?",
  },
  {
    name: "asset reference",
    sql: "DELETE FROM story_asset_references WHERE packet_id = ?",
  },
]) {
  test(`edition finalization fails closed on a corrupted ${fault.name}`, async () => {
    const db = new SqliteD1Database();
    seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
    seedStoryHead(db);
    const repository = await loadRepository(db);
    const packet = edition();
    await repository.stageEdition(packet, HASH_A);
    db.execute(fault.sql, packet.packet_id);

    await assert.rejects(
      repository.finalizeEdition(packet.packet_id),
      /CAS conflict/,
    );
    assertPacketAndHeadsRemainStaged(db, packet.packet_id, {
      editionRevision: 4,
      breakingRevision: 4,
      storyVersion: 1,
    });
    assert.equal(
      db.get(
        "SELECT publication_state FROM editions WHERE packet_id = ?",
        packet.packet_id,
      ).publication_state,
      "building",
    );
  });
}

test("Breaking finalization promotes claims, links, placement, and asset references", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = breaking();

  await repository.stageBreaking(packet, HASH_A);
  assert.equal(
    await repository.finalizeBreaking(packet.packet_id),
    "published",
  );

  for (const table of [
    "story_versions",
    "story_claims",
    "story_evidence",
    "breaking_entries",
    "story_asset_references",
  ]) {
    assert.deepEqual(
      {
        ...db.get(
          `SELECT count(*) AS count,
                sum(publication_state = 'published') AS published
         FROM ${table} WHERE packet_id = ?`,
          packet.packet_id,
        ),
      },
      { count: 1, published: 1 },
      `${table} must be promoted exactly once`,
    );
  }
});

for (const fault of [
  {
    name: "claim",
    sql: "UPDATE story_claims SET publication_state = 'failed' WHERE packet_id = ?",
  },
  {
    name: "claim evidence link",
    sql: "DELETE FROM story_evidence WHERE packet_id = ?",
  },
  {
    name: "Breaking placement",
    sql: "UPDATE breaking_entries SET publication_state = 'failed' WHERE packet_id = ?",
  },
  {
    name: "asset reference",
    sql: "DELETE FROM story_asset_references WHERE packet_id = ?",
  },
]) {
  test(`Breaking finalization fails closed on a corrupted ${fault.name}`, async () => {
    const db = new SqliteD1Database();
    seedHeadsAndAsset(db, { breakingRevision: 4 });
    seedStoryHead(db);
    const repository = await loadRepository(db);
    const packet = breaking();
    await repository.stageBreaking(packet, HASH_A);
    db.execute(fault.sql, packet.packet_id);

    await assert.rejects(
      repository.finalizeBreaking(packet.packet_id),
      /CAS conflict/,
    );
    assertPacketAndHeadsRemainStaged(db, packet.packet_id, {
      editionRevision: 0,
      breakingRevision: 4,
      storyVersion: 1,
    });
  });
}

test("current and historical edition reads apply the latest quarantine overlay", async () => {
  const db = new SqliteD1Database();
  seedHeadsAndAsset(db, { editionRevision: 4, breakingRevision: 4 });
  seedStoryHead(db);
  const repository = await loadRepository(db);
  const packet = edition();
  await repository.stageEdition(packet, HASH_A);
  await repository.finalizeEdition(packet.packet_id);

  assert.equal((await repository.getCurrentEdition())?.entries.length, 1);
  assert.equal(
    (await repository.getPublishedEdition(packet.packet_id))?.entries.length,
    1,
  );

  db.execute(
    `INSERT INTO audit_events(
       event_id, stream_id, stream_seq, payload_json,
       previous_event_hash, event_hash
     ) VALUES (?, ?, ?, ?, ?, ?)`,
    "audit-quarantine-1",
    "story-visibility:story-1",
    1,
    "{}",
    "0".repeat(64),
    HASH_B,
  );
  db.execute(
    `INSERT INTO story_visibility_events(
       story_id, visibility_seq, story_version, intent_id,
       desired_quarantined, audit_event_id
     ) VALUES (?, ?, ?, ?, ?, ?)`,
    "story-1",
    1,
    2,
    "intent-quarantine-1",
    1,
    "audit-quarantine-1",
  );

  assert.deepEqual((await repository.getCurrentEdition())?.entries, []);
  assert.deepEqual(
    (await repository.getPublishedEdition(packet.packet_id))?.entries,
    [],
  );
});
