import assert from "node:assert/strict";
import test from "node:test";

import {
  parseEditionPacket,
  parseStoryPacket,
} from "../lib/contracts/publication.ts";
import {
  parseAssetUploadMetadata,
  parseCollectorRunProjection,
} from "../lib/contracts/collector.ts";

const HASH = "a".repeat(64);

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
    event_occurred_at: null,
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
    asset_digests: [HASH],
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
    stories: [story({ severity: "medium" })],
    placements: [
      {
        story_id: "story-1",
        version: 2,
        section: "compliance",
        order: 1,
        lead: true,
      },
    ],
    breaking_story_ids: [],
    referenced_claim_ids: ["claim-1"],
    referenced_evidence_ids: ["evidence-1"],
    asset_digests: [HASH],
    coverage_gaps: [],
    reader_notices: [],
    ...overrides,
  };
}

test("edition contract keeps kind and coverage as orthogonal dimensions", () => {
  assert.equal(parseEditionPacket(edition()).edition_kind, "standard");
  const quietPartial = parseEditionPacket(
    edition({
      edition_kind: "quiet",
      coverage_state: "partial",
      placements: [{ ...edition().placements[0], lead: false }],
    }),
  );
  assert.equal(quietPartial.edition_kind, "quiet");
  assert.equal(quietPartial.coverage_state, "partial");

  assert.throws(
    () => parseEditionPacket(edition({ edition_kind: "morning" })),
    /edition_kind/,
  );
  assert.throws(
    () => parseEditionPacket(edition({ coverage_state: "full" })),
    /coverage_state/,
  );
  assert.throws(
    () => parseEditionPacket(edition({ coverage_state: "quiet" })),
    /coverage_state/,
  );
});

test("story contract carries an explicit nullable event occurrence timestamp", () => {
  const occurredAt = "2026-07-17T19:30:00Z";
  const parsed = parseStoryPacket(
    breaking({ story: story({ event_occurred_at: occurredAt }) }),
  );
  assert.equal(parsed.story.event_occurred_at, occurredAt);
  assert.equal(
    parseStoryPacket(breaking({ story: story({ event_occurred_at: null }) }))
      .story.event_occurred_at,
    null,
  );
  assert.throws(
    () =>
      parseStoryPacket(
        breaking({ story: story({ event_occurred_at: "yesterday" }) }),
      ),
    /event_occurred_at.*UTC RFC 3339/i,
  );
});

test("edition contract requires one explicit lead only for standard editions", () => {
  const placement = edition().placements[0];
  const standard = parseEditionPacket(
    edition({ placements: [{ ...placement, lead: true }] }),
  );
  assert.equal(standard.placements[0].lead, true);

  assert.throws(
    () =>
      parseEditionPacket(
        edition({ placements: [{ ...placement, lead: false }] }),
      ),
    /standard edition must declare exactly one lead/i,
  );
  assert.throws(
    () =>
      parseEditionPacket(
        edition({
          stories: [story(), story({ story_id: "story-2", slug: "story-2" })],
          placements: [
            { ...placement, lead: true },
            {
              story_id: "story-2",
              version: 2,
              section: "tax",
              order: 1,
              lead: true,
            },
          ],
        }),
      ),
    /standard edition must declare exactly one lead/i,
  );
  assert.doesNotThrow(() =>
    parseEditionPacket(
      edition({
        edition_kind: "quiet",
        placements: [{ ...placement, lead: false }],
      }),
    ),
  );
  assert.throws(
    () =>
      parseEditionPacket(
        edition({
          edition_kind: "quiet",
          placements: [{ ...placement, lead: true }],
        }),
      ),
    /quiet edition must not declare a lead/i,
  );
});

test("contract rejects a packet containing raw OSINT", () => {
  assert.throws(
    () => parseEditionPacket({ ...edition(), raw_payload: "secret" }),
    /unknown field raw_payload/,
  );
});

test("contract rejects an unsupported schema version", () => {
  assert.throws(
    () => parseStoryPacket({ ...breaking(), schema_version: "story.v2" }),
    /unsupported schema_version/,
  );
});

test("contract rejects unknown nested fields", () => {
  const packet = breaking();
  packet.story.claims[0].verbatim_excerpt = "raw source body";
  assert.throws(
    () => parseStoryPacket(packet),
    /unknown field verbatim_excerpt/,
  );
});

test("contract rejects factual claims without evidence", () => {
  const packet = breaking();
  packet.story.claims[0].evidence_ids = [];
  assert.throws(() => parseStoryPacket(packet), /requires evidence/);
});

test("contract rejects evidence IDs absent from the packet", () => {
  const packet = breaking();
  packet.story.claims[0].evidence_ids = ["missing-evidence"];
  assert.throws(() => parseStoryPacket(packet), /unknown evidence_id/);
});

test("contract rejects malformed asset hashes", () => {
  assert.throws(
    () => parseEditionPacket(edition({ asset_digests: ["ABC123"] })),
    /SHA-256/,
  );
});

test("contract rejects non-monotonic story and edition versions", () => {
  assert.throws(
    () => parseStoryPacket(breaking({ story: story({ version: 1 }) })),
    /story version must equal expected_current_version \+ 1/,
  );
  assert.throws(
    () => parseEditionPacket(edition({ edition_revision: 4 })),
    /edition_revision must equal expected_current_revision \+ 1/,
  );
});

test("contract rejects Breaking claims without a valid per-claim gate", () => {
  const noGate = breaking();
  noGate.story.claims[0].breaking_gate = null;
  assert.throws(() => parseStoryPacket(noGate), /valid Breaking gate/);

  const fakeQuorum = breaking();
  fakeQuorum.story.claims[0].breaking_gate = "two-independent-root-sources";
  assert.throws(
    () => parseStoryPacket(fakeQuorum),
    /two independent resolved root sources/,
  );
});

test("contract rejects an unresolved official-primary source", () => {
  const unresolved = breaking();
  unresolved.story.evidence_refs[0] = evidence({
    canonical_url: null,
    document_citation: null,
    primary_document_status: "verified",
  });
  assert.throws(
    () => parseStoryPacket(unresolved),
    /resolvable official primary document/,
  );
});

test("contract collapses syndicated and dependency-linked Breaking roots", () => {
  const first = evidence({
    source_type: "journalism",
    primary_document_status: "not-primary",
    evidence_id: "evidence-1",
    root_source_id: "root-1",
    syndication_group_fingerprint: "shared-wire-copy",
  });
  const sameSyndicate = evidence({
    source_type: "journalism",
    primary_document_status: "not-primary",
    evidence_id: "evidence-2",
    root_source_id: "root-2",
    syndication_group_fingerprint: "shared-wire-copy",
  });
  const sharedUpstream = evidence({
    source_type: "journalism",
    primary_document_status: "not-primary",
    evidence_id: "evidence-2",
    root_source_id: "root-2",
    syndication_group_fingerprint: "distinct-publication",
    upstream_root_source_ids: ["root-1"],
  });
  const twoSourceClaim = {
    ...story().claims[0],
    evidence_ids: ["evidence-1", "evidence-2"],
    breaking_gate: "two-independent-root-sources",
  };

  assert.throws(
    () =>
      parseStoryPacket(
        breaking({
          story: story({
            claims: [twoSourceClaim],
            evidence_refs: [first, sameSyndicate],
          }),
        }),
      ),
    /two independent resolved root sources/,
  );
  assert.throws(
    () =>
      parseStoryPacket(
        breaking({
          story: story({
            claims: [twoSourceClaim],
            evidence_refs: [first, sharedUpstream],
          }),
        }),
      ),
    /two independent resolved root sources/,
  );
});

test("contract rejects lineage verdicts inconsistent with Breaking eligibility", () => {
  const packet = breaking();
  packet.story.evidence_refs[0] = evidence({
    root_resolution_status: "ambiguous",
    independence_verdict: "ambiguous",
    counts_toward_breaking: true,
  });
  assert.throws(
    () => parseStoryPacket(packet),
    /counts_toward_breaking contradicts lineage verdict/,
  );
});

test("contract enforces per-claim gates for Breaking stories carried by an edition", () => {
  const carried = story();
  carried.claims[0].breaking_gate = null;
  assert.throws(
    () =>
      parseEditionPacket(
        edition({ stories: [carried], breaking_story_ids: [carried.story_id] }),
      ),
    /valid Breaking gate/,
  );
});

test("contract rejects incomplete edition reference manifests", () => {
  assert.throws(
    () => parseEditionPacket(edition({ referenced_claim_ids: [] })),
    /referenced_claim_ids must exactly match/,
  );
  assert.throws(
    () => parseEditionPacket(edition({ referenced_evidence_ids: ["missing"] })),
    /referenced_evidence_ids must exactly match/,
  );
  assert.throws(
    () => parseEditionPacket(edition({ asset_digests: [] })),
    /asset_digests must exactly match/,
  );
});

test("contract rejects ambiguous duplicate story versions in one edition", () => {
  const placedUngated = story();
  placedUngated.claims[0].breaking_gate = null;
  const gatedOtherVersion = story({
    version: 3,
    expected_current_version: 2,
    claims: [
      {
        ...story().claims[0],
        claim_id: "claim-2",
        evidence_ids: ["evidence-2"],
      },
    ],
    evidence_refs: [evidence({ evidence_id: "evidence-2" })],
  });
  assert.throws(
    () =>
      parseEditionPacket(
        edition({
          stories: [placedUngated, gatedOtherVersion],
          breaking_story_ids: ["story-1"],
          referenced_claim_ids: ["claim-1", "claim-2"],
          referenced_evidence_ids: ["evidence-1", "evidence-2"],
        }),
      ),
    /duplicate story_id/,
  );
});

test("contract accepts a closed valid edition and Breaking packet", () => {
  assert.deepEqual(parseEditionPacket(edition()), edition());
  assert.deepEqual(parseStoryPacket(breaking()), breaking());
});

test("contract collector and asset projections reject unknown fields", () => {
  const run = {
    schema_version: "collector-run.v1",
    run_id: "run-1",
    system_id: "intel-lake",
    collector_id: "routing",
    started_at: "2026-07-18T00:00:00Z",
    completed_at: "2026-07-18T00:05:00Z",
    status: "healthy",
    freshness: "fresh",
    items_seen: 42,
    items_eligible: 7,
    source_count: 18,
    unreachable_source_count: 2,
    watermark: "opaque-nonsecret-value",
    verified_at: "2026-07-18T00:05:02Z",
  };
  assert.deepEqual(parseCollectorRunProjection(run), run);
  assert.throws(
    () => parseCollectorRunProjection({ ...run, internal_path: "/secret" }),
    /unknown field internal_path/,
  );

  const asset = {
    schema_version: "asset-upload.v1",
    packet_id: "packet-1",
    asset_id: "asset-1",
    sha256: HASH,
    byte_count: 1024,
    mime_type: "image/png",
    width: 800,
    height: 600,
    captured_at: "2026-07-18T00:00:00Z",
    alt_text: "A verified editorial image",
    source: "Bali Zero editorial desk",
    source_url: "https://www.balizero.com/editorial",
    rights_basis: "internal-owned",
    rights_status: "approved",
    usage_status: "approved",
    dlp_status: "passed",
    sanitization_status: "passed",
    perceptual_dedup_status: "unique",
  };
  assert.deepEqual(parseAssetUploadMetadata(asset), asset);
  assert.throws(
    () => parseAssetUploadMetadata({ ...asset, filename: "secret.png" }),
    /unknown field filename/,
  );
  for (const field of ["alt_text", "source", "rights_basis"]) {
    assert.throws(
      () => parseAssetUploadMetadata({ ...asset, [field]: "" }),
      new RegExp(field),
    );
  }
});
