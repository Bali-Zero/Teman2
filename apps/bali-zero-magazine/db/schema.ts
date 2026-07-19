import { sql } from "drizzle-orm";
import {
  check,
  foreignKey,
  index,
  integer,
  primaryKey,
  sqliteTable,
  text,
  unique,
  uniqueIndex,
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
    manifestHash: text("manifest_hash").notNull(),
  },
  (table) => [
    check("collector_runs_manifest_hash_check", sha256Check("manifest_hash")),
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
    expectedStoryVersionCount: integer(
      "expected_story_version_count",
    ).notNull(),
    expectedClaimCount: integer("expected_claim_count").notNull(),
    expectedEvidenceLinkCount: integer(
      "expected_evidence_link_count",
    ).notNull(),
    expectedEditionEntryCount: integer(
      "expected_edition_entry_count",
    ).notNull(),
    expectedBreakingEntryCount: integer(
      "expected_breaking_entry_count",
    ).notNull(),
    expectedAssetReferenceCount: integer(
      "expected_asset_reference_count",
    ).notNull(),
    referencedClaimIdsJson: text("referenced_claim_ids_json").notNull(),
    referencedEvidenceIdsJson: text("referenced_evidence_ids_json").notNull(),
    referencedAssetDigestsJson: text("referenced_asset_digests_json").notNull(),
    breakingEntriesJson: text("breaking_entries_json").notNull(),
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
    check(
      "publication_packets_expected_counts_check",
      sql`${table.expectedStoryVersionCount} >= 0 and ${table.expectedClaimCount} >= 0 and ${table.expectedEvidenceLinkCount} >= 0 and ${table.expectedEditionEntryCount} >= 0 and ${table.expectedBreakingEntryCount} >= 0 and ${table.expectedAssetReferenceCount} >= 0`,
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
    eventOccurredAt: text("event_occurred_at"),
    updatedAt: text("updated_at").notNull(),
    title: text("title").notNull(),
    deck: text("deck").notNull(),
    summary: text("summary").notNull(),
    whyItMatters: text("why_it_matters").notNull(),
    curiosityText: text("curiosity_text"),
    scoreComponentsJson: text("score_components_json").notNull(),
    claimIdsJson: text("claim_ids_json").notNull(),
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
    unique("story_versions_packet_story_version_unique").on(
      table.packetId,
      table.storyId,
      table.version,
    ),
    check("story_versions_version_check", sql`${table.version} > 0`),
    check(
      "story_versions_expected_version_check",
      sql`${table.expectedCurrentVersion} >= 0 and ${table.version} = ${table.expectedCurrentVersion} + 1`,
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
    claimId: text("claim_id").notNull(),
    packetId: text("packet_id")
      .notNull()
      .references(() => publicationPackets.packetId),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    claimKind: text("claim_kind").notNull(),
    normalizedText: text("normalized_text").notNull(),
    numericValue: text("numeric_value"),
    numericUnit: text("numeric_unit"),
    asOf: text("as_of"),
    breakingGate: text("breaking_gate"),
    evidenceIdsJson: text("evidence_ids_json").notNull(),
    publicationState: text("publication_state").notNull().default("building"),
  },
  (table) => [
    primaryKey({
      columns: [table.packetId, table.storyId, table.version, table.claimId],
    }),
    unique("story_claims_story_version_claim_unique").on(
      table.storyId,
      table.version,
      table.claimId,
    ),
    unique("story_claims_packet_claim_unique").on(
      table.packetId,
      table.claimId,
    ),
    foreignKey({
      columns: [table.packetId, table.storyId, table.version],
      foreignColumns: [
        storyVersions.packetId,
        storyVersions.storyId,
        storyVersions.version,
      ],
      name: "story_claims_story_version_fk",
    }),
    check(
      "story_claims_kind_check",
      sql`${table.claimKind} in ('fact', 'numeric', 'analysis')`,
    ),
    check(
      "story_claims_state_check",
      sql`${table.publicationState} in ('building', 'published', 'failed')`,
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
    packetId: text("packet_id")
      .notNull()
      .references(() => publicationPackets.packetId),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    claimId: text("claim_id").notNull(),
    evidenceId: text("evidence_id")
      .notNull()
      .references(() => evidenceRefs.evidenceId),
    publicationState: text("publication_state").notNull().default("building"),
  },
  (table) => [
    primaryKey({
      columns: [
        table.packetId,
        table.storyId,
        table.version,
        table.claimId,
        table.evidenceId,
      ],
    }),
    foreignKey({
      columns: [table.packetId, table.storyId, table.version, table.claimId],
      foreignColumns: [
        storyClaims.packetId,
        storyClaims.storyId,
        storyClaims.version,
        storyClaims.claimId,
      ],
      name: "story_evidence_claim_fk",
    }),
    check(
      "story_evidence_state_check",
      sql`${table.publicationState} in ('building', 'published', 'failed')`,
    ),
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

export const publicationAuditBindings = sqliteTable(
  "publication_audit_bindings",
  {
    operation: text("operation").notNull(),
    packetId: text("packet_id").notNull(),
    eventId: text("event_id")
      .notNull()
      .unique()
      .references(() => auditEvents.eventId),
    streamId: text("stream_id").notNull(),
    streamSeq: integer("stream_seq").notNull(),
    eventHash: text("event_hash").notNull(),
    createdAt: createdAt(),
  },
  (table) => [
    primaryKey({ columns: [table.operation, table.packetId] }),
    unique("publication_audit_stream_seq_unique").on(
      table.streamId,
      table.streamSeq,
    ),
    check(
      "publication_audit_operation_check",
      sql`${table.operation} in ('edition.publish', 'breaking.publish')`,
    ),
    check("publication_audit_seq_check", sql`${table.streamSeq} > 0`),
    check("publication_audit_hash_check", sha256Check("event_hash")),
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
    placementsJson: text("placements_json").notNull(),
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
    unique("editions_id_packet_unique").on(table.editionId, table.packetId),
    check("editions_revision_check", sql`${table.editionRevision} > 0`),
    check(
      "editions_state_check",
      sql`${table.publicationState} in ('building', 'published', 'superseded', 'failed')`,
    ),
    check(
      "editions_kind_check",
      sql`${table.editionKind} in ('standard', 'quiet')`,
    ),
    check(
      "editions_coverage_check",
      sql`${table.coverageState} in ('complete', 'partial')`,
    ),
  ],
);

export const editionEntries = sqliteTable(
  "edition_entries",
  {
    editionId: text("edition_id")
      .notNull()
      .references(() => editions.editionId),
    packetId: text("packet_id")
      .notNull()
      .references(() => publicationPackets.packetId),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    section: text("section").notNull(),
    editorialOrder: integer("editorial_order").notNull(),
    isLead: integer("is_lead", { mode: "boolean" }).notNull(),
    publicationState: text("publication_state").notNull().default("building"),
  },
  (table) => [
    primaryKey({ columns: [table.editionId, table.packetId, table.storyId] }),
    unique("edition_entries_order_unique").on(
      table.editionId,
      table.section,
      table.editorialOrder,
    ),
    uniqueIndex("edition_entries_single_lead_unique")
      .on(table.editionId)
      .where(sql`${table.isLead} = 1`),
    foreignKey({
      columns: [table.editionId, table.packetId],
      foreignColumns: [editions.editionId, editions.packetId],
      name: "edition_entries_edition_packet_fk",
    }),
    foreignKey({
      columns: [table.packetId, table.storyId, table.version],
      foreignColumns: [
        storyVersions.packetId,
        storyVersions.storyId,
        storyVersions.version,
      ],
      name: "edition_entries_story_version_fk",
    }),
    check(
      "edition_entries_state_check",
      sql`${table.publicationState} in ('building', 'published', 'failed')`,
    ),
    check("edition_entries_lead_check", sql`${table.isLead} in (0, 1)`),
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
    publicationState: text("publication_state").notNull().default("building"),
  },
  (table) => [
    primaryKey({ columns: [table.breakingRevision, table.storyId] }),
    foreignKey({
      columns: [table.storyId, table.version],
      foreignColumns: [storyVersions.storyId, storyVersions.version],
      name: "breaking_entries_story_version_fk",
    }),
    check(
      "breaking_entries_state_check",
      sql`${table.publicationState} in ('building', 'published', 'failed')`,
    ),
  ],
);

export const assets = sqliteTable(
  "assets",
  {
    sha256: text("sha256").primaryKey(),
    r2Key: text("r2_key").notNull().unique(),
    mimeType: text("mime_type").notNull(),
    byteCount: integer("byte_count").notNull(),
    width: integer("width").notNull(),
    height: integer("height").notNull(),
    createdAt: createdAt(),
  },
  (table) => [
    check("assets_hash_check", sha256Check("sha256")),
    check("assets_mime_check", sql`${table.mimeType} = 'image/png'`),
    check(
      "assets_dimensions_check",
      sql`${table.byteCount} > 0 and ${table.width} > 0 and ${table.height} > 0`,
    ),
  ],
);

export const assetSources = sqliteTable(
  "asset_sources",
  {
    assetId: text("asset_id").primaryKey(),
    packetId: text("packet_id").notNull(),
    canonicalSha256: text("canonical_sha256")
      .notNull()
      .references(() => assets.sha256),
    sourceSha256: text("source_sha256").notNull(),
    sourceByteCount: integer("source_byte_count").notNull(),
    sourceMimeType: text("source_mime_type").notNull(),
    sourceWidth: integer("source_width").notNull(),
    sourceHeight: integer("source_height").notNull(),
    altText: text("alt_text").notNull(),
    source: text("source").notNull(),
    sourceUrl: text("source_url"),
    rightsBasis: text("rights_basis").notNull().default("unknown"),
    rightsStatus: text("rights_status").notNull(),
    usageStatus: text("usage_status").notNull().default("unknown"),
    dlpStatus: text("dlp_status").notNull().default("pending"),
    sanitizationStatus: text("sanitization_status")
      .notNull()
      .default("pending"),
    perceptualDedupStatus: text("perceptual_dedup_status")
      .notNull()
      .default("unreviewed"),
    status: text("status").notNull(),
    capturedAt: text("captured_at")
      .notNull()
      .default(sql`CURRENT_TIMESTAMP`),
    createdAt: createdAt(),
  },
  (table) => [
    unique("asset_sources_source_sha256_unique").on(table.sourceSha256),
    index("asset_sources_canonical_sha256_idx").on(table.canonicalSha256),
    check("asset_sources_source_hash_check", sha256Check("source_sha256")),
    check(
      "asset_sources_source_mime_check",
      sql`${table.sourceMimeType} in ('image/jpeg', 'image/png', 'image/webp')`,
    ),
    check(
      "asset_sources_status_check",
      sql`${table.status} in ('pending', 'verified', 'quarantined', 'revoked')`,
    ),
    check(
      "asset_sources_rights_status_check",
      sql`${table.rightsStatus} in ('approved', 'denied', 'unknown')`,
    ),
    check(
      "asset_sources_rights_basis_check",
      sql`${table.rightsBasis} in ('internal-owned', 'licensed', 'public-domain', 'official-use', 'generated', 'unknown')`,
    ),
    check(
      "asset_sources_usage_status_check",
      sql`${table.usageStatus} in ('approved', 'denied', 'unknown')`,
    ),
    check(
      "asset_sources_dlp_status_check",
      sql`${table.dlpStatus} in ('pending', 'passed', 'failed')`,
    ),
    check(
      "asset_sources_sanitization_status_check",
      sql`${table.sanitizationStatus} in ('pending', 'passed', 'failed')`,
    ),
    check(
      "asset_sources_perceptual_dedup_status_check",
      sql`${table.perceptualDedupStatus} in ('unreviewed', 'unique', 'intentional-reuse')`,
    ),
    check(
      "asset_sources_source_dimensions_check",
      sql`${table.sourceByteCount} > 0 and ${table.sourceWidth} > 0 and ${table.sourceHeight} > 0`,
    ),
  ],
);

export const storyAssetReferences = sqliteTable(
  "story_asset_references",
  {
    packetId: text("packet_id")
      .notNull()
      .references(() => publicationPackets.packetId),
    storyId: text("story_id").notNull(),
    version: integer("version").notNull(),
    assetSha256: text("asset_sha256")
      .notNull()
      .references(() => assets.sha256),
    publicationState: text("publication_state").notNull().default("building"),
  },
  (table) => [
    primaryKey({
      columns: [
        table.packetId,
        table.storyId,
        table.version,
        table.assetSha256,
      ],
    }),
    foreignKey({
      columns: [table.packetId, table.storyId, table.version],
      foreignColumns: [
        storyVersions.packetId,
        storyVersions.storyId,
        storyVersions.version,
      ],
      name: "story_asset_references_story_version_fk",
    }),
    check("story_asset_references_hash_check", sha256Check("asset_sha256")),
    check(
      "story_asset_references_state_check",
      sql`${table.publicationState} in ('building', 'published', 'failed')`,
    ),
  ],
);

export const assetStatusEvents = sqliteTable(
  "asset_status_events",
  {
    assetId: text("asset_id")
      .notNull()
      .references(() => assetSources.assetId),
    statusSeq: integer("status_seq").notNull(),
    status: text("status").notNull(),
    rightsStatus: text("rights_status").notNull(),
    reasonCode: text("reason_code").notNull(),
    replacementAssetId: text("replacement_asset_id"),
    createdAt: createdAt(),
  },
  (table) => [
    primaryKey({ columns: [table.assetId, table.statusSeq] }),
    check(
      "asset_status_events_status_check",
      sql`${table.status} in ('pending', 'verified', 'quarantined', 'revoked')`,
    ),
    check(
      "asset_status_events_rights_status_check",
      sql`${table.rightsStatus} in ('approved', 'denied', 'unknown')`,
    ),
  ],
);

export const researchJobs = sqliteTable(
  "research_jobs",
  {
    jobId: text("job_id").primaryKey(),
    actorKey: text("actor_key").notNull(),
    mode: text("mode").notNull(),
    queryJson: text("query_json").notNull(),
    requestHash: text("request_hash").notNull(),
    idempotencyKey: text("idempotency_key").notNull().unique(),
    status: text("status").notNull(),
    attemptLimit: integer("attempt_limit").notNull().default(3),
    attemptCount: integer("attempt_count").notNull().default(0),
    workerId: text("worker_id"),
    claimToken: text("claim_token"),
    fencingToken: integer("fencing_token").notNull().default(0),
    targetKey: text("target_key").notNull(),
    targetFencingToken: integer("target_fencing_token").notNull().default(0),
    heartbeatAt: text("heartbeat_at"),
    leaseDeadline: text("lease_deadline"),
    createdAt: createdAt(),
    expiresAt: text("expires_at").notNull(),
    completedAt: text("completed_at"),
    cancelledAt: text("cancelled_at"),
  },
  (table) => [
    index("research_jobs_claim_queue_idx").on(
      table.status,
      table.expiresAt,
      table.createdAt,
    ),
    check("research_jobs_actor_key_check", sha256Check("actor_key")),
    check("research_jobs_request_hash_check", sha256Check("request_hash")),
    check(
      "research_jobs_mode_check",
      sql`${table.mode} in ('search', 'compare', 'timeline', 'notebook_insight')`,
    ),
    check(
      "research_jobs_status_check",
      sql`${table.status} in ('queued', 'claimed', 'completed', 'failed', 'cancelled')`,
    ),
    check(
      "research_jobs_attempts_check",
      sql`${table.attemptLimit} between 1 and 5 and ${table.attemptCount} between 0 and ${table.attemptLimit}`,
    ),
    check("research_jobs_fencing_check", sql`${table.fencingToken} >= 0`),
  ],
);

export const researchResults = sqliteTable(
  "research_results",
  {
    resultId: text("result_id").primaryKey(),
    jobId: text("job_id")
      .notNull()
      .references(() => researchJobs.jobId)
      .unique(),
    status: text("status").notNull(),
    resultJson: text("result_json").notNull(),
    resultHash: text("result_hash").notNull(),
    requestHash: text("request_hash").notNull(),
    fencingToken: integer("fencing_token").notNull(),
    receiptKeyId: text("receipt_key_id").notNull(),
    receiptBodyHash: text("receipt_body_hash").notNull(),
    createdAt: createdAt(),
  },
  (table) => [
    check("research_results_hash_check", sha256Check("result_hash")),
    check("research_results_request_hash_check", sha256Check("request_hash")),
    check(
      "research_results_receipt_hash_check",
      sha256Check("receipt_body_hash"),
    ),
    check(
      "research_results_status_check",
      sql`${table.status} in ('completed', 'failed')`,
    ),
    check("research_results_fencing_check", sql`${table.fencingToken} > 0`),
  ],
);

export const researchAuditEvents = sqliteTable(
  "research_audit_events",
  {
    eventId: text("event_id").primaryKey(),
    jobId: text("job_id")
      .notNull()
      .references(() => researchJobs.jobId),
    eventType: text("event_type").notNull(),
    actorKey: text("actor_key"),
    workerId: text("worker_id"),
    status: text("status").notNull(),
    failureCode: text("failure_code"),
    fencingToken: integer("fencing_token"),
    createdAt: createdAt(),
  },
  (table) => [
    index("research_audit_job_idx").on(table.jobId, table.createdAt),
    check(
      "research_audit_event_type_check",
      sql`${table.eventType} in ('created', 'cancelled', 'claimed', 'completed', 'failed')`,
    ),
    check(
      "research_audit_status_check",
      sql`${table.status} in ('queued', 'claimed', 'completed', 'failed', 'cancelled')`,
    ),
    check(
      "research_audit_failure_code_check",
      sql`${table.failureCode} is null or ${table.failureCode} in ('source_unavailable', 'dlp_rejected', 'evidence_missing', 'invalid_result', 'internal_error')`,
    ),
  ],
);

export const opsIntents = sqliteTable(
  "ops_intents",
  {
    intentId: text("intent_id").primaryKey(),
    actorKey: text("actor_key").notNull(),
    effectiveRole: text("effective_role").notNull(),
    policyVersion: text("policy_version").notNull(),
    idempotencyKey: text("idempotency_key").notNull(),
    intentKind: text("intent_kind").notNull(),
    paramsJson: text("params_json").notNull(),
    requestHash: text("request_hash").notNull(),
    reasonCode: text("reason_code").notNull(),
    status: text("status").notNull(),
    attemptLimit: integer("attempt_limit").notNull().default(3),
    attemptCount: integer("attempt_count").notNull().default(0),
    workerId: text("worker_id"),
    claimToken: text("claim_token"),
    fencingToken: integer("fencing_token").notNull().default(0),
    heartbeatAt: text("heartbeat_at"),
    leaseDeadline: text("lease_deadline"),
    effectToken: text("effect_token"),
    preEffectAttestedAt: text("pre_effect_attested_at"),
    attestedPolicyVersion: text("attested_policy_version"),
    attestationExpiresAt: text("attestation_expires_at"),
    effectConsumedAt: text("effect_consumed_at"),
    expiresAt: text("expires_at").notNull(),
    startedAt: text("started_at"),
    completedAt: text("completed_at"),
    failureCode: text("failure_code"),
    createdAt: createdAt(),
  },
  (table) => [
    unique("ops_intents_actor_idempotency_unique").on(
      table.actorKey,
      table.idempotencyKey,
    ),
    index("ops_intents_claim_idx").on(
      table.status,
      table.expiresAt,
      table.leaseDeadline,
      table.createdAt,
    ),
    check("ops_intents_role_check", sql`${table.effectiveRole} = 'operator'`),
    check(
      "ops_intents_kind_check",
      sql`${table.intentKind} in ('rerun_collector', 'rebuild_edition', 'quarantine_story', 'release_story', 'refresh_research_job')`,
    ),
    check(
      "ops_intents_status_check",
      sql`${table.status} in ('queued', 'claimed', 'running', 'succeeded', 'failed', 'cancelled_revoked', 'outcome_unknown')`,
    ),
    check("ops_intents_request_hash_check", sha256Check("request_hash")),
  ],
);

export const opsTargetFences = sqliteTable("ops_target_fences", {
  targetKey: text("target_key").primaryKey(),
  nextFencingToken: integer("next_fencing_token").notNull().default(0),
  effectFencingToken: integer("effect_fencing_token").notNull().default(0),
  updatedAt: text("updated_at").notNull(),
});

export const opsReceipts = sqliteTable(
  "ops_receipts",
  {
    receiptId: text("receipt_id").primaryKey(),
    intentId: text("intent_id")
      .notNull()
      .unique()
      .references(() => opsIntents.intentId),
    status: text("status").notNull(),
    receiptJson: text("receipt_json").notNull(),
    receiptHash: text("receipt_hash").notNull(),
    requestHash: text("request_hash").notNull(),
    keyId: text("key_id").notNull(),
    bodyHash: text("body_hash").notNull(),
    fencingToken: integer("fencing_token").notNull(),
    attestedPolicyVersion: text("attested_policy_version"),
    createdAt: createdAt(),
  },
  () => [
    check("ops_receipts_hash_check", sha256Check("receipt_hash")),
    check("ops_receipts_request_hash_check", sha256Check("request_hash")),
    check("ops_receipts_body_hash_check", sha256Check("body_hash")),
  ],
);

export const opsAuditEvents = sqliteTable(
  "ops_audit_events",
  {
    eventId: text("event_id").primaryKey(),
    intentId: text("intent_id")
      .notNull()
      .references(() => opsIntents.intentId),
    eventType: text("event_type").notNull(),
    actorKey: text("actor_key"),
    workerId: text("worker_id"),
    status: text("status").notNull(),
    failureCode: text("failure_code"),
    fencingToken: integer("fencing_token"),
    createdAt: createdAt(),
  },
  (table) => [
    index("ops_audit_intent_idx").on(table.intentId, table.createdAt),
  ],
);

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
    unique("audit_anchor_previous_hash_unique").on(
      table.streamId,
      table.previousAnchorHash,
    ),
    check("audit_anchor_seq_check", sql`${table.streamSeq} > 0`),
    check("audit_anchor_event_hash_check", sha256Check("event_hash")),
    check(
      "audit_anchor_previous_hash_check",
      sha256Check("previous_anchor_hash"),
    ),
    check("audit_anchor_hash_check", sha256Check("anchor_hash")),
  ],
);

export const auditAnchorHeads = sqliteTable(
  "audit_anchor_heads",
  {
    streamId: text("stream_id").primaryKey(),
    streamSeq: integer("stream_seq").notNull(),
    eventHash: text("event_hash").notNull(),
    anchorHash: text("anchor_hash").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    check("audit_anchor_heads_seq_check", sql`${table.streamSeq} > 0`),
    check("audit_anchor_heads_event_hash_check", sha256Check("event_hash")),
    check("audit_anchor_heads_anchor_hash_check", sha256Check("anchor_hash")),
  ],
);

export const auditPromotionBlock = sqliteTable(
  "audit_promotion_block",
  {
    singletonId: integer("singleton_id").primaryKey(),
    blocked: integer("blocked", { mode: "boolean" }).notNull(),
    reason: text("reason").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    check(
      "audit_promotion_block_singleton_check",
      sql`${table.singletonId} = 1`,
    ),
    check("audit_promotion_block_value_check", sql`${table.blocked} in (0, 1)`),
  ],
);

export const auditPromotionPermits = sqliteTable(
  "audit_promotion_permits",
  {
    operation: text("operation").notNull(),
    packetId: text("packet_id").notNull(),
    streamId: text("stream_id").notNull(),
    streamSeq: integer("stream_seq").notNull(),
    eventHash: text("event_hash").notNull(),
    anchorHash: text("anchor_hash").notNull(),
    status: text("status").notNull(),
    createdAt: createdAt(),
    consumedAt: text("consumed_at"),
  },
  (table) => [
    primaryKey({ columns: [table.operation, table.packetId] }),
    check(
      "audit_promotion_permit_operation_check",
      sql`${table.operation} in ('edition.publish', 'breaking.publish')`,
    ),
    check("audit_promotion_permit_seq_check", sql`${table.streamSeq} > 0`),
    check("audit_promotion_permit_event_hash_check", sha256Check("event_hash")),
    check(
      "audit_promotion_permit_anchor_hash_check",
      sha256Check("anchor_hash"),
    ),
    check(
      "audit_promotion_permit_status_check",
      sql`${table.status} in ('permitted', 'consumed')`,
    ),
  ],
);
