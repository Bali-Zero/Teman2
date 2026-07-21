import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import { parseEditionPacket } from "../lib/contracts/publication.ts";
import { createPublicationRepository } from "../lib/server/publication-repository.ts";

const RAW_STORY_ID = "story_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_QUARANTINED_ID = "story_01JZX7Z8P9Q2M4N6R8T0V2W4Z7";
const RAW_CLAIM_ID = "claim_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_EVIDENCE_ID = "evidence_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_RUN_ID = "run_01JZX7Z8P9Q2M4N6R8T0V2W4Y6";
const RAW_NOTEBOOK_ID = "nb-933509f9-internal";
const RAW_DIGEST = "a".repeat(64);

const storyRows = [
  {
    story_id: RAW_STORY_ID,
    version: 2,
    slug: "bali-visa-evidence-standard",
    language: "en",
    domain: "immigration",
    section: "immigration",
    editorial_order: 1,
    lead: true,
    severity: "high",
    lifecycle_state: "amended",
    title: "Bali visa files move to a stricter evidence standard",
    deck: "A verified document trail now matters earlier in the application cycle.",
    summary:
      "The operational change shifts document checks forward and narrows the margin for incomplete submissions.",
    why_it_matters:
      "Teams must identify missing evidence before a client reaches the submission window.",
    curiosity_text:
      "The overlooked detail: translation dates can change the useful life of a supporting document.",
    coverage_state: "full",
    confidence: "high",
    first_seen_at: "2026-07-18T00:15:00.000Z",
    event_occurred_at: null,
    updated_at: "2026-07-18T01:20:00.000Z",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: JSON.stringify([
      "intel-lake-private-id",
      RAW_NOTEBOOK_ID,
    ]),
    desired_quarantined: 0,
    media_alt_text:
      "A reviewed immigration dossier arranged beside a verification checklist",
    media_source: "Bali Zero editorial desk",
    media_created_at: "2026-07-18T00:45:00.000Z",
    verified_at: "2026-07-18T01:25:00.000Z",
  },
  {
    story_id: "story_company_internal",
    version: 1,
    slug: "investment-licensing-sequence",
    domain: "company",
    section: "company",
    editorial_order: 1,
    lead: false,
    severity: "medium",
    lifecycle_state: "verified",
    title: "Investment licensing now rewards the correct filing sequence",
    deck: "Corporate documents and operational permits must tell the same story.",
    summary: "A sequencing mismatch can delay downstream approvals.",
    why_it_matters: "Company setup teams need one shared readiness view.",
    curiosity_text: null,
    coverage_state: "full",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "Company licensing documents reviewed in sequence",
  },
  {
    story_id: "story_tax_internal",
    version: 1,
    slug: "tax-calendar-cross-check",
    domain: "tax",
    section: "tax",
    editorial_order: 1,
    lead: false,
    severity: "medium",
    lifecycle_state: "verified",
    title: "The tax calendar needs a second operational cross-check",
    deck: "Filing dates and client evidence windows do not always align.",
    summary: "A cross-check protects the filing window.",
    why_it_matters: "Tax teams can surface missing records before deadlines.",
    curiosity_text:
      "A one-day document lag can turn an apparently complete file into a partial filing record.",
    coverage_state: "partial",
    confidence: "medium",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "A tax calendar annotated with document checkpoints",
  },
  {
    story_id: "story_property_internal",
    version: 1,
    slug: "property-rights-review",
    domain: "property",
    section: "property",
    editorial_order: 1,
    lead: false,
    severity: "medium",
    lifecycle_state: "verified",
    title: "Property reviews put usage rights before the sales narrative",
    deck: "The operational file begins with title, zoning, and permitted use.",
    summary: "Rights verification precedes commercial interpretation.",
    why_it_matters: "Advisers need a grounded file before discussing options.",
    curiosity_text: null,
    coverage_state: "full",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "A land title and zoning map under review",
  },
  {
    story_id: "story_regulation_internal",
    version: 1,
    slug: "regulatory-source-refresh",
    domain: "compliance",
    section: "compliance",
    editorial_order: 1,
    lead: false,
    severity: "critical",
    lifecycle_state: "verified",
    title: "Primary-source refresh changes the compliance watchlist",
    deck: "A newly verified source changes which files require attention first.",
    summary: "The watchlist now follows the verified primary source.",
    why_it_matters: "Compliance owners can prioritize affected client files.",
    curiosity_text: null,
    coverage_state: "full",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 0,
    media_alt_text: "A primary regulation source marked for review",
  },
  {
    story_id: RAW_QUARANTINED_ID,
    version: 1,
    slug: "quarantined-draft",
    domain: "tax",
    section: "tax",
    editorial_order: 2,
    lead: false,
    severity: "high",
    lifecycle_state: "verified",
    title: "This quarantined title must never render",
    deck: "Hidden by the latest visibility overlay.",
    summary: "Hidden.",
    why_it_matters: "Hidden.",
    curiosity_text: null,
    coverage_state: "full",
    confidence: "high",
    published_at: "2026-07-18T01:30:00.000Z",
    contributing_system_ids_json: "[]",
    desired_quarantined: 1,
    media_alt_text: "A quarantined editorial asset",
  },
];

const editionRow = {
  edition_id: "edition_2026-07-18_internal_revision_2",
  edition_date: "2026-07-18",
  edition_revision: 2,
  edition_kind: "standard",
  coverage_state: "partial",
  verified_at: "2026-07-18T01:25:00.000Z",
  published_at: "2026-07-18T01:30:00.000Z",
  coverage_gaps_json: JSON.stringify(["One optional tax source is delayed"]),
  reader_notices_json: JSON.stringify(["Partial input coverage"]),
};

const sourceRows = [
  {
    system_id: "intel-lake-private-id",
    display_name: "Intel Lake",
    health: "healthy",
    verified_at: "2026-07-18T01:20:00.000Z",
    run_id: RAW_RUN_ID,
  },
  {
    system_id: RAW_NOTEBOOK_ID,
    display_name: "Notebook Insight",
    health: "delayed",
    verified_at: "2026-07-18T00:50:00.000Z",
    run_id: "run_notebook_internal",
  },
];

const claimRows = [
  {
    claim_id: RAW_CLAIM_ID,
    claim_kind: "fact",
    legal_effect: "changes-legal-effect",
    normalized_text:
      "The reviewed workflow requires supporting evidence before submission readiness is confirmed.",
    numeric_value: null,
    numeric_unit: null,
    as_of: "2026-07-18",
  },
];

const evidenceRows = [
  {
    claim_id: RAW_CLAIM_ID,
    evidence_id: RAW_EVIDENCE_ID,
    root_source_id: "root_source_private",
    canonical_url: "https://example.go.id/verified-guidance",
    publisher: "Directorate General of Immigration",
    document_citation: "Operational guidance, section 4",
    published_at: "2026-07-17T08:00:00.000Z",
    retrieved_at: "2026-07-18T00:10:00.000Z",
    source_type: "official",
    primary_document_status: "primary",
    root_resolution_status: "resolved",
    evidence_note: "Primary guidance verified against the issuing authority.",
  },
];

class FixtureStatement {
  constructor(sql, fixture) {
    this.sql = sql;
    this.fixture = fixture;
    this.values = [];
  }

  bind(...values) {
    this.values = values;
    return this;
  }

  async first() {
    return this.fixture.answer(this.sql, this.values, "first");
  }

  async all() {
    return {
      success: true,
      results: this.fixture.answer(this.sql, this.values, "all") ?? [],
    };
  }

  async run() {
    return { success: true, meta: { changes: 0 } };
  }
}

function createFixtureDb({ quiet = false, empty = false } = {}) {
  const currentEdition = empty
    ? null
    : {
        ...editionRow,
        edition_kind: quiet ? "quiet" : editionRow.edition_kind,
      };
  const fixture = {
    answer(sql, values, mode) {
      if (sql.includes("SELECT ep.current_edition_id")) {
        return currentEdition === null
          ? null
          : { current_edition_id: currentEdition.edition_id };
      }
      if (
        sql.includes("FROM editions") &&
        sql.includes("WHERE edition_id = ?")
      ) {
        return values[0] === currentEdition?.edition_id ? currentEdition : null;
      }
      if (sql.includes("FROM edition_entries ee")) {
        return quiet
          ? []
          : storyRows
              .filter(
                (story) =>
                  story.desired_quarantined !== 1 &&
                  story.slug !== "regulatory-source-refresh",
              )
              .map((story) => ({
                ...story,
                order: story.editorial_order,
              }));
      }
      if (sql.includes("FROM breaking_pointer bp")) {
        return quiet
          ? []
          : storyRows.filter(
              (story) => story.slug === "regulatory-source-refresh",
            );
      }
      if (sql.includes("FROM stories s")) {
        return values[0] === "bali-visa-evidence-standard"
          ? storyRows[0]
          : null;
      }
      if (sql.includes("magazine:edition-id-by-key")) {
        return values[0] === "2026-07-18" && values[1] === 2
          ? { edition_id: currentEdition?.edition_id }
          : null;
      }
      if (sql.includes("magazine:story-publication-metadata")) {
        return {
          section: "immigration",
          verified_at: editionRow.verified_at,
        };
      }
      if (sql.includes("magazine:current-edition")) return currentEdition;
      if (sql.includes("magazine:edition-by-id")) {
        return values[0] === "2026-07-18" && values[1] === 2
          ? currentEdition
          : null;
      }
      if (sql.includes("magazine:edition-stories")) {
        return quiet ? [] : storyRows;
      }
      if (sql.includes("magazine:active-breaking")) {
        return quiet
          ? []
          : storyRows.filter(
              (story) => story.slug === "regulatory-source-refresh",
            );
      }
      if (sql.includes("magazine:source-status")) return sourceRows;
      if (sql.includes("magazine:story-by-slug")) {
        return values[0] === "bali-visa-evidence-standard"
          ? storyRows[0]
          : null;
      }
      if (sql.includes("magazine:story-contributors")) return sourceRows;
      if (sql.includes("magazine:story-claims")) return claimRows;
      if (sql.includes("magazine:story-evidence")) return evidenceRows;
      if (sql.includes("magazine:story-history")) {
        return [
          {
            version: 2,
            lifecycle_state: "amended",
            publication_state: "published",
            published_at: "2026-07-18T01:30:00.000Z",
          },
          {
            version: 1,
            lifecycle_state: "superseded",
            publication_state: "superseded",
            published_at: "2026-07-17T01:30:00.000Z",
          },
        ];
      }
      if (sql.includes("magazine:story-visibility-history")) {
        return [
          {
            story_version: 1,
            desired_quarantined: 1,
            created_at: "2026-07-17T02:00:00.000Z",
          },
          {
            story_version: 2,
            desired_quarantined: 0,
            created_at: "2026-07-18T01:28:00.000Z",
          },
        ];
      }
      if (sql.includes("magazine:story-assets")) {
        return [
          {
            asset_sha256: RAW_DIGEST,
            alt_text:
              "A reviewed immigration dossier arranged beside a verification checklist",
            source: "Bali Zero editorial desk",
            source_url: null,
            rights_basis: "internal-owned",
            created_at: "2026-07-18T00:45:00.000Z",
            status: "verified",
            rights_status: "approved",
            usage_status: "approved",
            dlp_status: "passed",
            sanitization_status: "passed",
            perceptual_dedup_status: "unique",
          },
        ];
      }
      throw new Error(`Unexpected fixture query (${mode}): ${sql}`);
    },
  };
  return {
    prepare(sql) {
      return new FixtureStatement(sql, fixture);
    },
    async batch() {
      throw new Error("read-only fixture must not batch");
    },
  };
}

class SqliteD1Statement {
  constructor(owner, sql, values = []) {
    this.owner = owner;
    this.sql = sql;
    this.values = values;
  }

  bind(...values) {
    return new SqliteD1Statement(this.owner, this.sql, values);
  }

  runSync() {
    const result = this.owner.sqlite.prepare(this.sql).run(...this.values);
    return {
      success: true,
      results: [],
      meta: { changes: Number(result.changes) },
    };
  }

  async run() {
    return this.runSync();
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
    const migrationDirectory = new URL("../drizzle/", import.meta.url);
    for (const filename of readdirSync(migrationDirectory)
      .filter((name) => /^\d+.*\.sql$/.test(name))
      .sort()) {
      const migration = readFileSync(
        new URL(filename, migrationDirectory),
        "utf8",
      ).replaceAll("--> statement-breakpoint", "");
      this.sqlite.exec(migration);
    }
  }

  prepare(sql) {
    return new SqliteD1Statement(this, sql);
  }

  async batch(statements) {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const results = statements.map((statement) => statement.runSync());
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
}

function integrationStory({
  suffix,
  domain,
  version,
  expectedCurrentVersion,
  title,
}) {
  return {
    story_id: `story-render-integration-${suffix}`,
    version,
    expected_current_version: expectedCurrentVersion,
    slug: `reader-current-version-invariant-${suffix}`,
    language: "en",
    domain,
    severity: "high",
    lifecycle_state: version === 1 ? "verified" : "amended",
    first_seen_at: "2026-07-17T23:45:00Z",
    event_occurred_at: null,
    updated_at: version === 1 ? "2026-07-18T00:15:00Z" : "2026-07-18T01:15:00Z",
    title,
    deck: "The canonical publication reader must preserve version equality.",
    summary: "A sanitized reader-integration fixture.",
    why_it_matters: "Stale Breaking rows cannot override the story head.",
    curiosity_text: null,
    score_components: {
      editorial: 0.9,
      impact: 0.8,
      freshness: 0.9,
      evidence: 1,
      diversity: 0.6,
    },
    claims: [
      {
        claim_id: `claim-render-integration-${suffix}`,
        claim_kind: "fact",
        legal_effect: "changes-legal-effect",
        normalized_text: "The current story version is the only visible one.",
        numeric_value: null,
        numeric_unit: null,
        as_of: "2026-07-18",
        evidence_ids: [`evidence-render-integration-${suffix}`],
        breaking_gate: "official-primary",
      },
    ],
    evidence_refs: [
      {
        evidence_id: `evidence-render-integration-${suffix}`,
        root_source_id: `root-render-integration-${suffix}`,
        canonical_url: "https://example.go.id/current-version",
        publisher: "Example Authority",
        document_citation: "Current version notice",
        published_at: "2026-07-17T23:30:00Z",
        retrieved_at: "2026-07-17T23:40:00Z",
        source_type: "official",
        primary_document_status: "verified",
        root_resolution_status: "resolved",
        independence_verdict: "independent",
        evidence_note: "Verified issuing-authority publication.",
        upstream_root_source_ids: [],
        syndication_group_fingerprint: `render-integration-${suffix}`,
        independence_ruleset_version: "independence.v1",
        independence_reason: "issuing-authority-primary-document",
        counts_toward_breaking: true,
      },
    ],
    contributing_system_ids: [],
    coverage_state: "full",
    confidence: "high",
    asset_digests: [RAW_DIGEST],
    adapter_version: "adapter.v1",
    ruleset_version: "rules.v1",
  };
}

function integrationEdition({
  revision,
  stories,
  leadStoryId,
  breakingStoryIds,
}) {
  return {
    schema_version: "edition.v1",
    packet_id: `packet-render-integration-${revision}`,
    editor_version: "editor.v1",
    ruleset_version: "rules.v1",
    edition_date: "2026-07-18",
    edition_revision: revision,
    expected_current_revision: revision - 1,
    expected_breaking_revision: revision - 1,
    edition_kind: "standard",
    publication_state: "building",
    coverage_state: "complete",
    readiness_cutoff: "2026-07-18T01:20:00Z",
    verified_at:
      revision === 1 ? "2026-07-18T00:20:00Z" : "2026-07-18T01:20:00Z",
    collector_run_ids: [],
    stories,
    placements: stories.map((story) => ({
      story_id: story.story_id,
      version: story.version,
      section: story.domain,
      order: 1,
      lead: story.story_id === leadStoryId,
    })),
    breaking_story_ids: breakingStoryIds,
    referenced_claim_ids: stories.flatMap((story) =>
      story.claims.map((claim) => claim.claim_id),
    ),
    referenced_evidence_ids: stories.flatMap((story) =>
      story.evidence_refs.map((evidence) => evidence.evidence_id),
    ),
    asset_digests: [RAW_DIGEST],
    coverage_gaps: [],
    reader_notices: [],
  };
}

async function createIntegrationDb() {
  const db = new SqliteD1Database();
  db.execute(
    `INSERT INTO assets(sha256, r2_key, mime_type, byte_count, width, height)
     VALUES (?, ?, ?, ?, ?, ?)`,
    RAW_DIGEST,
    `assets/sha256/${RAW_DIGEST}.png`,
    "image/png",
    1024,
    1200,
    800,
  );
  db.execute(
    `INSERT INTO asset_sources(
       asset_id, packet_id, canonical_sha256, source_sha256,
       source_byte_count, source_mime_type, source_width, source_height,
       alt_text, source, rights_basis, rights_status, usage_status,
       dlp_status, sanitization_status, perceptual_dedup_status, status
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    "asset-render-integration",
    "asset-packet-render-integration",
    RAW_DIGEST,
    RAW_DIGEST,
    1024,
    "image/webp",
    1200,
    800,
    "A compliance publication under editorial review",
    "Bali Zero editorial desk",
    "internal-owned",
    "approved",
    "approved",
    "passed",
    "passed",
    "unique",
    "verified",
  );
  const repository = createPublicationRepository(db, {
    now: () => "2026-07-18T01:30:00.000Z",
  });
  const firstCompliance = integrationStory({
    suffix: "compliance",
    domain: "compliance",
    version: 1,
    expectedCurrentVersion: 0,
    title: "Stale breaking revision must not render",
  });
  const firstTax = integrationStory({
    suffix: "tax",
    domain: "tax",
    version: 1,
    expectedCurrentVersion: 0,
    title: "Earlier tax dispatch",
  });
  const firstEdition = parseEditionPacket(
    integrationEdition({
      revision: 1,
      stories: [firstCompliance, firstTax],
      leadStoryId: firstCompliance.story_id,
      breakingStoryIds: [firstCompliance.story_id],
    }),
  );
  const currentCompliance = integrationStory({
    suffix: "compliance",
    domain: "compliance",
    version: 2,
    expectedCurrentVersion: 1,
    title: "Current amended compliance revision",
  });
  const currentTax = integrationStory({
    suffix: "tax",
    domain: "tax",
    version: 2,
    expectedCurrentVersion: 1,
    title: "Explicit tax lead wins equal section order",
  });
  const currentEdition = parseEditionPacket(
    integrationEdition({
      revision: 2,
      stories: [currentCompliance, currentTax],
      leadStoryId: currentTax.story_id,
      breakingStoryIds: [],
    }),
  );

  await repository.stageEdition(firstEdition, "b".repeat(64));
  assert.equal(
    await repository.finalizeEdition(firstEdition.packet_id),
    "published",
  );
  await repository.stageEdition(currentEdition, "c".repeat(64));
  assert.equal(
    await repository.finalizeEdition(currentEdition.packet_id),
    "published",
  );

  // Simulate an out-of-date active Breaking revision. The canonical reader must
  // still enforce breaking_entries.version = stories.current_version.
  db.execute(
    "UPDATE breaking_pointer SET active_revision = 1 WHERE singleton_id = 1",
  );
  return db;
}

function appEnv(db) {
  return {
    ACTOR_KEY_SECRET: "test-actor-key-secret-with-enough-entropy",
    ROLE_ALLOWLIST_JSON: JSON.stringify({
      version: "roles.test.v1",
      analysts: [],
      operators: [],
    }),
    DB: db,
    ASSETS: {
      fetch: async () => new Response("Not found", { status: 404 }),
    },
  };
}

const magazineWorkerPromise = import(
  new URL("../dist/server/index.js", import.meta.url).href
);

async function render(
  pathname,
  { authenticated = true, db = createFixtureDb() } = {},
) {
  const { default: worker } = await magazineWorkerPromise;
  const headers = new Headers({ accept: "text/html" });
  if (authenticated) {
    headers.set("oai-authenticated-user-email", "reader@example.com");
  }
  return worker.fetch(
    new Request(`http://localhost${pathname}`, { headers }),
    appEnv(db),
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

function assertProtectedHtml(response) {
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.match(
    response.headers.get("content-security-policy") ?? "",
    /default-src 'self'/,
  );
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
}

function assertNoInternalIdentifiers(html) {
  for (const identifier of [
    RAW_STORY_ID,
    RAW_QUARANTINED_ID,
    RAW_CLAIM_ID,
    RAW_EVIDENCE_ID,
    RAW_RUN_ID,
    RAW_NOTEBOOK_ID,
    RAW_DIGEST,
    "intel-lake-private-id",
    "root_source_private",
  ]) {
    assert.doesNotMatch(html, new RegExp(identifier, "i"));
  }
}

test("magazine front page renders editorial priority, five domains, coverage, and sanitized source status", async () => {
  const response = await render("/");
  assertProtectedHtml(response);
  const html = await response.text();

  assert.match(html, /Bali Zero Magazine/);
  assert.match(html, /18 July 2026/i);
  assert.match(html, /The Morning File/);
  assert.match(html, /Bali visa files move to a stricter evidence standard/);
  assert.match(html, /Breaking/);
  assert.match(html, /Primary-source refresh changes the compliance watchlist/);
  for (const section of [
    "Immigration",
    "Company & Investment",
    "Tax",
    "Property",
    "Regulation & Compliance",
  ]) {
    const encodedSection = section.replaceAll("&", "(?:&|&amp;)");
    assert.match(html, new RegExp(`>${encodedSection}<`, "i"));
  }
  assert.match(html, /The Detail Everyone Missed/);
  assert.match(html, /Source systems/);
  assert.match(html, /Intel Lake/);
  assert.match(html, /Notebook Insight/);
  assert.match(html, /Partial coverage/);
  assert.match(html, /Delayed/);
  assert.match(html, /Last verified/i);
  assert.match(html, /09:25 WITA/i);
  assert.match(
    html,
    /<meta[^>]+name="robots"[^>]+content="noindex, nofollow"/i,
  );
  assert.ok(
    html.indexOf("The Morning File") < html.indexOf("Source systems"),
    "editorial issue must precede system controls",
  );
  assert.doesNotMatch(html, /This quarantined title must never render/);
  assertNoInternalIdentifiers(html);
});

test("magazine front page omits Breaking and explains quiet and empty publication modes", async () => {
  const quietResponse = await render("/", {
    db: createFixtureDb({ quiet: true }),
  });
  assertProtectedHtml(quietResponse);
  const quietHtml = await quietResponse.text();
  assert.match(quietHtml, /Quiet edition/);
  assert.match(
    quietHtml,
    /No verified developments cleared the publication threshold/i,
  );
  assert.doesNotMatch(quietHtml, /class="breaking-strip"/);

  const emptyResponse = await render("/", {
    db: createFixtureDb({ empty: true }),
  });
  assertProtectedHtml(emptyResponse);
  const emptyHtml = await emptyResponse.text();
  assert.match(emptyHtml, /No published edition yet/i);
  assert.match(emptyHtml, /Source systems/);
  assertNoInternalIdentifiers(emptyHtml);
});

test("story page separates analysis from claim evidence and exposes current revision state without IDs", async () => {
  const response = await render("/stories/bali-visa-evidence-standard");
  assertProtectedHtml(response);
  const html = await response.text();

  assert.match(html, /Bali visa files move to a stricter evidence standard/);
  assert.match(html, /Why it matters/);
  assert.match(html, /Contributing systems/);
  assert.match(html, /Intel Lake/);
  assert.match(html, /Notebook Insight/);
  assert.match(html, /Claims and evidence/);
  assert.match(html, /The reviewed workflow requires supporting evidence/);
  assert.match(html, /Directorate General of Immigration/);
  assert.match(html, /Operational guidance, section 4/);
  for (const label of [
    "Section",
    "Immigration",
    "Severity",
    "High",
    "Lifecycle",
    "Amended",
    "Coverage",
    "Full",
    "Event time",
    "First seen",
    "Verified",
    "Published",
    "Visual provenance",
    "Bali Zero editorial desk",
    "Revision published — lifecycle amended",
    "Revision published — lifecycle superseded — currently superseded",
    "Quarantined",
    "Restored",
  ]) {
    assert.match(html, new RegExp(label, "i"));
  }
  assert.match(
    html,
    /Unavailable — source packet did not declare an occurrence time/i,
  );
  assert.doesNotMatch(html, /correction recorded/i);
  assert.match(html, /Visible now/);
  assert.match(html, /rel="noopener noreferrer"/i);
  assertNoInternalIdentifiers(html);
});

test("edition archive identifies its immutable revision and applies current visibility overlays", async () => {
  const response = await render("/editions/2026-07-18-r2");
  assertProtectedHtml(response);
  const html = await response.text();

  assert.match(html, /Edition archive/);
  assert.match(html, /Immutable revision 2/i);
  assert.match(html, /Current visibility and rights overlays apply/i);
  assert.match(html, /Bali visa files move to a stricter evidence standard/);
  assert.doesNotMatch(html, /class="breaking-strip"/);
  assert.doesNotMatch(
    html,
    /Primary-source refresh changes the compliance watchlist/,
  );
  assert.doesNotMatch(html, /This quarantined title must never render/);
  assertNoInternalIdentifiers(html);
});

test("contract-valid packets render the explicit cross-section lead without stale Breaking rows", async () => {
  const db = await createIntegrationDb();
  const currentResponse = await render("/", { db });
  assertProtectedHtml(currentResponse);
  const currentHtml = await currentResponse.text();

  assert.match(currentHtml, /Current amended compliance revision/);
  assert.match(
    currentHtml,
    /<article class="story-card story-card--hero">[\s\S]*?Explicit tax lead wins equal section order[\s\S]*?<\/article>/,
  );
  assert.doesNotMatch(currentHtml, /Stale breaking revision must not render/);
  assert.doesNotMatch(currentHtml, /class="breaking-strip"/);

  const archivedResponse = await render("/editions/2026-07-18-r1", { db });
  assertProtectedHtml(archivedResponse);
  const archivedHtml = await archivedResponse.text();
  assert.match(
    archivedHtml,
    /<article class="story-card story-card--hero">[\s\S]*?Stale breaking revision must not render[\s\S]*?<\/article>/,
  );
  assert.match(archivedHtml, /Earlier tax dispatch/);
  assert.doesNotMatch(archivedHtml, /Current amended compliance revision/);
  assert.doesNotMatch(
    archivedHtml,
    /Explicit tax lead wins equal section order/,
  );
  assert.doesNotMatch(archivedHtml, /class="breaking-strip"/);
});

test("editorial CSS uses the locked Bali Zero palette and Montserrat stack", () => {
  const css = readFileSync(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  for (const token of ["#2C2F38", "#000000", "#FFFFFF", "#F4C430", "#C8102E"]) {
    assert.match(css, new RegExp(token, "i"));
  }
  for (const rejected of [
    "#141414",
    "#FFD400",
    "#D52B1E",
    "#333333",
    "#C6C6C6",
    "Inter",
    "Arial",
  ]) {
    assert.doesNotMatch(css, new RegExp(rejected, "i"));
  }
  assert.match(css, /--paper:\s*var\(--anthracite\)/i);
  assert.match(css, /--secondary-surface:\s*var\(--black\)/i);
  assert.match(css, /--ink:\s*var\(--white\)/i);
  assert.match(
    css,
    /html\s*\{[^}]*background:\s*var\(--paper\)[^}]*color:\s*var\(--ink\)/is,
  );
  assert.match(
    css,
    /body\s*\{[^}]*background:\s*var\(--paper\)[^}]*color:\s*var\(--ink\)/is,
  );
  assert.match(css, /font-family:\s*Montserrat,\s*sans-serif/i);
});

test("anonymous readers receive a protected shell without editorial data", async () => {
  const response = await render("/", { authenticated: false });
  assertProtectedHtml(response);
  const html = await response.text();
  assert.match(html, /Workspace access required/i);
  assert.doesNotMatch(html, /The Morning File/);
  assert.doesNotMatch(
    html,
    /Bali visa files move to a stricter evidence standard/,
  );
});

test("worker security wrapper mutates protected HTML only", async () => {
  const workerSourceUrl = new URL(
    "../worker/response-security.ts",
    import.meta.url,
  );
  workerSourceUrl.searchParams.set(
    "security-test",
    `${process.pid}-${Date.now()}`,
  );
  const { secureProtectedHtmlResponse } = await import(workerSourceUrl.href);
  const request = new Request("https://magazine.example/", {
    headers: { accept: "text/html" },
  });
  const htmlResponse = secureProtectedHtmlResponse(
    request,
    new Response("<main>Magazine</main>", {
      headers: { "content-type": "text/html; charset=utf-8", etag: "issue-2" },
    }),
  );
  assert.equal(htmlResponse.headers.get("cache-control"), "private, no-store");
  assert.match(
    htmlResponse.headers.get("content-security-policy") ?? "",
    /frame-ancestors 'none'/,
  );
  assert.equal(htmlResponse.headers.get("etag"), "issue-2");

  const jsonResponse = new Response('{"ok":true}', {
    headers: {
      "content-type": "application/json",
      "cache-control": "max-age=60",
    },
  });
  assert.equal(
    secureProtectedHtmlResponse(
      new Request("https://magazine.example/api/machine/collector-runs"),
      jsonResponse,
    ),
    jsonResponse,
  );
  const mediaResponse = new Response("image", {
    headers: {
      "content-type": "image/webp",
      "cross-origin-resource-policy": "same-origin",
    },
  });
  assert.equal(
    secureProtectedHtmlResponse(
      new Request("https://magazine.example/api/media/public-slug"),
      mediaResponse,
    ),
    mediaResponse,
  );
});
