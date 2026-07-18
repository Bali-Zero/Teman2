import { sql } from "drizzle-orm";
import {
  check,
  integer,
  primaryKey,
  sqliteTable,
  text,
  unique,
} from "drizzle-orm/sqlite-core";

const createdAt = () =>
  text("created_at")
    .notNull()
    .default(sql`CURRENT_TIMESTAMP`);

const sha256Check = (columnName: string) =>
  sql`length(${sql.identifier(columnName)}) = 64 and ${sql.identifier(columnName)} not glob '*[^0-9a-f]*'`;

export const sourceSystems = sqliteTable(
  "source_systems",
  {
    systemId: text("system_id").primaryKey(),
    displayName: text("display_name").notNull(),
    expectedCadenceSeconds: integer("expected_cadence_seconds").notNull(),
    readiness: text("readiness").notNull(),
    health: text("health").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    check(
      "source_systems_readiness_check",
      sql`${table.readiness} in ('required', 'optional')`,
    ),
    check(
      "source_systems_health_check",
      sql`${table.health} in ('healthy', 'delayed', 'degraded', 'unavailable', 'unknown')`,
    ),
    check(
      "source_systems_cadence_check",
      sql`${table.expectedCadenceSeconds} > 0`,
    ),
  ],
);

export const collectorRuns = sqliteTable(
  "collector_runs",
  {
    runId: text("run_id").primaryKey(),
    systemId: text("system_id")
      .notNull()
      .references(() => sourceSystems.systemId),
    collectorId: text("collector_id").notNull(),
    startedAt: text("started_at").notNull(),
    completedAt: text("completed_at").notNull(),
    status: text("status").notNull(),
    freshness: text("freshness").notNull(),
    itemsSeen: integer("items_seen").notNull(),
    itemsEligible: integer("items_eligible").notNull(),
    sourceCount: integer("source_count").notNull(),
    unreachableSourceCount: integer("unreachable_source_count").notNull(),
    watermark: text("watermark").notNull(),
    verifiedAt: text("verified_at").notNull(),
  },
  (table) => [
    check(
      "collector_runs_status_check",
      sql`${table.status} in ('healthy', 'delayed', 'degraded', 'unavailable', 'unknown')`,
    ),
    check(
      "collector_runs_freshness_check",
      sql`${table.freshness} in ('fresh', 'delayed', 'archived')`,
    ),
    check(
      "collector_runs_counts_check",
      sql`${table.itemsSeen} >= 0 and ${table.itemsEligible} >= 0 and ${table.sourceCount} >= 0 and ${table.unreachableSourceCount} >= 0`,
    ),
  ],
);

export const publicationPackets = sqliteTable(
  "publication_packets",
  {
    packetId: text("packet_id").primaryKey(),
    manifestHash: text("manifest_hash").notNull(),
    packetKind: text("packet_kind").notNull(),
    publicationState: text("publication_state").notNull().default("building"),
    stagedAt: createdAt(),
    publishedAt: text("published_at"),
  },
  (table) => [
    check("publication_packets_hash_check", sha256Check("manifest_hash")),
    check(
      "publication_packets_kind_check",
      sql`${table.packetKind} in ('edition', 'breaking')`,
    ),
    check(
      "publication_packets_state_check",
      sql`${table.publicationState} in ('building', 'published', 'failed')`,
    ),
  ],
);

export const stories = sqliteTable(
  "stories",
  {
    storyId: text("story_id").primaryKey(),
    slug: text("slug").notNull().unique(),
    currentVersion: integer("current_version").notNull().default(0),
    createdAt: createdAt(),
  },
  (table) => [
    check("stories_current_version_check", sql`${table.currentVersion} >= 0`),
  ],
);

export const storyVersions = sqliteTable(
  "story_versions",
  {
    storyId: text("story_id")
      .notNull()
      .references(() => stories.storyId),
    version: integer("version").notNull(),
    packetId: text("packet_id")
      .notNull()
      .references(() => publicationPackets.packetId),
    expectedCurrentVersion: integer("expected_current_version").notNull(),
    language: text("language").notNull(),
    domain: text("domain").notNull(),
    severity: text("severity").notNull(),
    lifecycleState: text("lifecycle_state").notNull(),
    firstSeenAt: text("first_seen_at").notNull(),
    updatedAt: text("updated_at").notNull(),
    title: text("title").notNull(),
    deck: text("deck").notNull(),
    summary: text("summary").notNull(),
    whyItMatters: text("why_it_matters").notNull(),
    curiosityText: text("curiosity_text"),
    scoreComponentsJson: text("score_components_json").notNull(),
    contributingSystemIdsJson: text("contributing_system_ids_json").notNull(),
    coverageState: text("coverage_state").notNull(),
    confidence: text("confidence").notNull(),
    assetDigestsJson: text("asset_digests_json").notNull(),
    adapterVersion: text("adapter_version").notNull(),
    rulesetVersion: text("ruleset_version").notNull(),
    publicationState: text("publication_state").notNull().default("building"),
    publishedAt: text("published_at"),
  },
  (table) => [
    primaryKey({ columns: [table.storyId, table.version] }),
    unique("story_versions_story_version_unique").on(
      table.storyId,
      table.version,
    ),
    check("story_versions_version_check", sql`${table.version} > 0`),
    check(
      "story_versions_expected_version_check",
      sql`${table.expectedCurrentVersion} >= 0 and ${table.version} > ${table.expectedCurrentVersion}`,
    ),
    check(
      "story_versions_state_check",
      sql`${table.publicationState} in ('building', 'published', 'superseded', 'failed')`,
    ),
  ],
);

export const storyClaims = sqliteTable(
  "story_claims",
  {
    claimId: text("claim_id").primaryKey(),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    claimKind: text("claim_kind").notNull(),
    normalizedText: text("normalized_text").notNull(),
    numericValue: text("numeric_value"),
    numericUnit: text("numeric_unit"),
    asOf: text("as_of"),
    breakingGate: text("breaking_gate"),
  },
  (table) => [
    unique("story_claims_story_version_claim_unique").on(
      table.storyId,
      table.version,
      table.claimId,
    ),
    check(
      "story_claims_kind_check",
      sql`${table.claimKind} in ('fact', 'numeric', 'analysis')`,
    ),
  ],
);

export const evidenceRefs = sqliteTable(
  "evidence_refs",
  {
    evidenceId: text("evidence_id").primaryKey(),
    rootSourceId: text("root_source_id").notNull(),
    canonicalUrl: text("canonical_url"),
    publisher: text("publisher").notNull(),
    documentCitation: text("document_citation"),
    publishedAt: text("published_at"),
    retrievedAt: text("retrieved_at").notNull(),
    sourceType: text("source_type").notNull(),
    primaryDocumentStatus: text("primary_document_status").notNull(),
    rootResolutionStatus: text("root_resolution_status").notNull(),
    independenceVerdict: text("independence_verdict").notNull(),
    evidenceNote: text("evidence_note"),
    upstreamRootSourceIdsJson: text("upstream_root_source_ids_json").notNull(),
    syndicationGroupFingerprint: text(
      "syndication_group_fingerprint",
    ).notNull(),
    independenceRulesetVersion: text("independence_ruleset_version").notNull(),
    independenceReason: text("independence_reason").notNull(),
    countsTowardBreaking: integer("counts_toward_breaking", {
      mode: "boolean",
    }).notNull(),
  },
  (table) => [
    check(
      "evidence_refs_source_type_check",
      sql`${table.sourceType} in ('official', 'journalism', 'research', 'dataset')`,
    ),
  ],
);

export const storyEvidence = sqliteTable(
  "story_evidence",
  {
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    claimId: text("claim_id").notNull(),
    evidenceId: text("evidence_id")
      .notNull()
      .references(() => evidenceRefs.evidenceId),
  },
  (table) => [
    primaryKey({
      columns: [table.storyId, table.version, table.claimId, table.evidenceId],
    }),
  ],
);

export const auditEvents = sqliteTable(
  "audit_events",
  {
    eventId: text("event_id").primaryKey(),
    streamId: text("stream_id").notNull(),
    streamSeq: integer("stream_seq").notNull(),
    payloadJson: text("payload_json").notNull(),
    previousEventHash: text("previous_event_hash").notNull(),
    eventHash: text("event_hash").notNull(),
    createdAt: createdAt(),
  },
  (table) => [
    unique("audit_events_stream_seq_unique").on(
      table.streamId,
      table.streamSeq,
    ),
    check("audit_events_seq_check", sql`${table.streamSeq} > 0`),
    check(
      "audit_events_previous_hash_check",
      sha256Check("previous_event_hash"),
    ),
    check("audit_events_hash_check", sha256Check("event_hash")),
  ],
);

export const auditStreamHeads = sqliteTable(
  "audit_stream_heads",
  {
    streamId: text("stream_id").primaryKey(),
    streamSeq: integer("stream_seq").notNull(),
    eventHash: text("event_hash").notNull(),
  },
  (table) => [
    check("audit_stream_heads_seq_check", sql`${table.streamSeq} > 0`),
    check("audit_stream_heads_hash_check", sha256Check("event_hash")),
  ],
);

export const storyVisibilityEvents = sqliteTable(
  "story_visibility_events",
  {
    storyId: text("story_id").notNull(),
    visibilitySeq: integer("visibility_seq").notNull(),
    storyVersion: integer("story_version").notNull(),
    intentId: text("intent_id").notNull().unique(),
    desiredQuarantined: integer("desired_quarantined", {
      mode: "boolean",
    }).notNull(),
    auditEventId: text("audit_event_id")
      .notNull()
      .references(() => auditEvents.eventId),
    createdAt: createdAt(),
  },
  (table) => [
    primaryKey({ columns: [table.storyId, table.visibilitySeq] }),
    unique("story_visibility_story_seq_unique").on(
      table.storyId,
      table.visibilitySeq,
    ),
  ],
);

export const editions = sqliteTable(
  "editions",
  {
    editionId: text("edition_id").primaryKey(),
    packetId: text("packet_id")
      .notNull()
      .unique()
      .references(() => publicationPackets.packetId),
    editorVersion: text("editor_version").notNull(),
    rulesetVersion: text("ruleset_version").notNull(),
    editionDate: text("edition_date").notNull(),
    editionRevision: integer("edition_revision").notNull(),
    expectedCurrentRevision: integer("expected_current_revision").notNull(),
    expectedBreakingRevision: integer("expected_breaking_revision").notNull(),
    editionKind: text("edition_kind").notNull(),
    publicationState: text("publication_state").notNull().default("building"),
    coverageState: text("coverage_state").notNull(),
    readinessCutoff: text("readiness_cutoff").notNull(),
    verifiedAt: text("verified_at").notNull(),
    collectorRunIdsJson: text("collector_run_ids_json").notNull(),
    breakingStoryIdsJson: text("breaking_story_ids_json").notNull(),
    assetDigestsJson: text("asset_digests_json").notNull(),
    coverageGapsJson: text("coverage_gaps_json").notNull(),
    readerNoticesJson: text("reader_notices_json").notNull(),
    publishedAt: text("published_at"),
  },
  (table) => [
    unique("editions_date_revision_unique").on(
      table.editionDate,
      table.editionRevision,
    ),
    check("editions_revision_check", sql`${table.editionRevision} > 0`),
    check(
      "editions_state_check",
      sql`${table.publicationState} in ('building', 'published', 'superseded', 'failed')`,
    ),
    check(
      "editions_kind_check",
      sql`${table.editionKind} in ('morning', 'quiet')`,
    ),
    check(
      "editions_coverage_check",
      sql`${table.coverageState} in ('full', 'partial', 'quiet')`,
    ),
  ],
);

export const editionEntries = sqliteTable(
  "edition_entries",
  {
    editionId: text("edition_id")
      .notNull()
      .references(() => editions.editionId),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    section: text("section").notNull(),
    editorialOrder: integer("editorial_order").notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.editionId, table.storyId] }),
    unique("edition_entries_order_unique").on(
      table.editionId,
      table.section,
      table.editorialOrder,
    ),
  ],
);

export const editionPointer = sqliteTable(
  "edition_pointer",
  {
    singletonId: integer("singleton_id").primaryKey().default(1),
    currentEditionId: text("current_edition_id"),
    currentRevision: integer("current_revision").notNull().default(0),
  },
  (table) => [
    check("edition_pointer_singleton_check", sql`${table.singletonId} = 1`),
    check("edition_pointer_revision_check", sql`${table.currentRevision} >= 0`),
  ],
);

export const breakingPointer = sqliteTable(
  "breaking_pointer",
  {
    singletonId: integer("singleton_id").primaryKey().default(1),
    activeRevision: integer("active_revision").notNull().default(0),
    updatedAt: text("updated_at"),
  },
  (table) => [
    check("breaking_pointer_singleton_check", sql`${table.singletonId} = 1`),
    check("breaking_pointer_revision_check", sql`${table.activeRevision} >= 0`),
  ],
);

export const breakingEntries = sqliteTable(
  "breaking_entries",
  {
    breakingRevision: integer("breaking_revision").notNull(),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    packetId: text("packet_id")
      .notNull()
      .references(() => publicationPackets.packetId),
  },
  (table) => [primaryKey({ columns: [table.breakingRevision, table.storyId] })],
);

export const assets = sqliteTable(
  "assets",
  {
    assetId: text("asset_id").primaryKey(),
    packetId: text("packet_id").notNull(),
    sha256: text("sha256").notNull().unique(),
    r2Key: text("r2_key").notNull().unique(),
    mimeType: text("mime_type").notNull(),
    byteCount: integer("byte_count").notNull(),
    width: integer("width").notNull(),
    height: integer("height").notNull(),
    altText: text("alt_text").notNull(),
    source: text("source").notNull(),
    rightsStatus: text("rights_status").notNull(),
    status: text("status").notNull(),
    createdAt: createdAt(),
  },
  (table) => [
    check("assets_hash_check", sha256Check("sha256")),
    check(
      "assets_status_check",
      sql`${table.status} in ('pending', 'verified', 'quarantined', 'revoked')`,
    ),
    check(
      "assets_dimensions_check",
      sql`${table.width} > 0 and ${table.height} > 0`,
    ),
  ],
);

export const assetStatusEvents = sqliteTable(
  "asset_status_events",
  {
    assetId: text("asset_id")
      .notNull()
      .references(() => assets.assetId),
    statusSeq: integer("status_seq").notNull(),
    status: text("status").notNull(),
    reasonCode: text("reason_code").notNull(),
    replacementAssetId: text("replacement_asset_id"),
    createdAt: createdAt(),
  },
  (table) => [primaryKey({ columns: [table.assetId, table.statusSeq] })],
);

export const researchJobs = sqliteTable("research_jobs", {
  jobId: text("job_id").primaryKey(),
  actorKey: text("actor_key").notNull(),
  mode: text("mode").notNull(),
  queryJson: text("query_json").notNull(),
  status: text("status").notNull(),
  createdAt: createdAt(),
  expiresAt: text("expires_at").notNull(),
});

export const researchResults = sqliteTable("research_results", {
  resultId: text("result_id").primaryKey(),
  jobId: text("job_id")
    .notNull()
    .references(() => researchJobs.jobId),
  resultJson: text("result_json").notNull(),
  resultHash: text("result_hash").notNull(),
  createdAt: createdAt(),
});

export const opsIntents = sqliteTable("ops_intents", {
  intentId: text("intent_id").primaryKey(),
  idempotencyKey: text("idempotency_key").notNull().unique(),
  intentType: text("intent_type").notNull(),
  payloadJson: text("payload_json").notNull(),
  payloadHash: text("payload_hash").notNull(),
  actorKey: text("actor_key").notNull(),
  policyVersion: text("policy_version").notNull(),
  status: text("status").notNull(),
  attemptLimit: integer("attempt_limit").notNull(),
  expiresAt: text("expires_at").notNull(),
  claimToken: text("claim_token"),
  fencingToken: integer("fencing_token").notNull().default(0),
  heartbeatAt: text("heartbeat_at"),
  leaseDeadline: text("lease_deadline"),
  createdAt: createdAt(),
});

export const opsReceipts = sqliteTable("ops_receipts", {
  receiptId: text("receipt_id").primaryKey(),
  intentId: text("intent_id")
    .notNull()
    .references(() => opsIntents.intentId),
  status: text("status").notNull(),
  payloadJson: text("payload_json").notNull(),
  payloadHash: text("payload_hash").notNull(),
  fencingToken: integer("fencing_token").notNull(),
  createdAt: createdAt(),
});

export const ingestNonces = sqliteTable(
  "ingest_nonces",
  {
    keyId: text("key_id").notNull(),
    nonce: text("nonce").notNull(),
    bodyHash: text("body_hash").notNull(),
    expiresAt: text("expires_at").notNull(),
    createdAt: createdAt(),
  },
  (table) => [primaryKey({ columns: [table.keyId, table.nonce] })],
);

export const releaseAttestations = sqliteTable("release_attestations", {
  attestationId: text("attestation_id").primaryKey(),
  storyId: text("story_id").notNull(),
  storyVersion: integer("story_version").notNull(),
  evidenceBundleHash: text("evidence_bundle_hash").notNull(),
  assetSetHash: text("asset_set_hash").notNull(),
  keyId: text("key_id").notNull(),
  signature: text("signature").notNull(),
  expiresAt: text("expires_at").notNull(),
  consumedAt: text("consumed_at"),
  createdAt: createdAt(),
});

export const auditAnchorReceipts = sqliteTable(
  "audit_anchor_receipts",
  {
    anchorId: text("anchor_id").primaryKey(),
    streamId: text("stream_id").notNull(),
    streamSeq: integer("stream_seq").notNull(),
    eventHash: text("event_hash").notNull(),
    previousAnchorHash: text("previous_anchor_hash").notNull(),
    observedAt: text("observed_at").notNull(),
    keyId: text("key_id").notNull(),
    signature: text("signature").notNull(),
    anchorHash: text("anchor_hash").notNull().unique(),
    createdAt: createdAt(),
  },
  (table) => [
    unique("audit_anchor_stream_seq_unique").on(
      table.streamId,
      table.streamSeq,
    ),
    check("audit_anchor_event_hash_check", sha256Check("event_hash")),
    check(
      "audit_anchor_previous_hash_check",
      sha256Check("previous_anchor_hash"),
    ),
    check("audit_anchor_hash_check", sha256Check("anchor_hash")),
  ],
);
