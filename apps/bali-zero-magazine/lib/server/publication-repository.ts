import type {
  ClaimV1,
  EditionPacketV1,
  EditionPlacementV1,
  EvidenceRefV1,
  StoryPacketV1,
  StoryVersionV1,
} from "../contracts/publication.ts";

export type D1ResultLike<T = Record<string, unknown>> = Readonly<{
  success?: boolean;
  results?: readonly T[];
  meta?: Readonly<{ changes?: number }>;
}>;

export interface D1PreparedStatementLike {
  bind(...values: readonly unknown[]): D1PreparedStatementLike;
  run<T = Record<string, unknown>>(): Promise<D1ResultLike<T>>;
  first<T = Record<string, unknown>>(): Promise<T | null>;
  all<T = Record<string, unknown>>(): Promise<D1ResultLike<T>>;
}

export interface D1DatabaseLike {
  prepare(sql: string): D1PreparedStatementLike;
  batch<T = Record<string, unknown>>(
    statements: readonly D1PreparedStatementLike[],
  ): Promise<readonly D1ResultLike<T>[]>;
}

export type StageResult = "staged" | "replay";
export type FinalizeResult = "published" | "replay";

export type PublishedStory = Readonly<{
  story_id: string;
  version: number;
  slug: string;
  language: string;
  domain: StoryVersionV1["domain"];
  severity: StoryVersionV1["severity"];
  lifecycle_state: StoryVersionV1["lifecycle_state"];
  first_seen_at: string;
  event_occurred_at: string | null;
  updated_at: string;
  title: string;
  deck: string;
  summary: string;
  why_it_matters: string;
  curiosity_text: string | null;
  coverage_state: StoryVersionV1["coverage_state"];
  confidence: StoryVersionV1["confidence"];
  published_at: string;
}>;

export type PublishedEdition = Readonly<{
  edition_id: string;
  edition_date: string;
  edition_revision: number;
  edition_kind: EditionPacketV1["edition_kind"];
  coverage_state: EditionPacketV1["coverage_state"];
  verified_at: string;
  published_at: string;
  coverage_gaps: readonly string[];
  reader_notices: readonly string[];
  entries: readonly Readonly<{
    story_id: string;
    version: number;
    section: EditionPlacementV1["section"];
    order: number;
    lead: boolean;
    story: PublishedStory;
  }>[];
}>;

type RepositoryOptions = Readonly<{ now?: () => string }>;
type PacketRow = Readonly<{
  packet_id: string;
  manifest_hash: string;
  packet_kind: "edition" | "breaking";
  publication_state: "building" | "published" | "failed";
  expected_claim_count: number;
  expected_evidence_link_count: number;
  expected_edition_entry_count: number;
  expected_breaking_entry_count: number;
  expected_asset_reference_count: number;
}>;

type BreakingEntryRow = Readonly<{
  story_id: string;
  version: number;
}>;

type ChangeExpectation = Readonly<{ index: number; count: number }>;

type EditionFinalizeRow = Readonly<{
  edition_id: string;
  edition_revision: number;
  expected_current_revision: number;
  expected_breaking_revision: number;
}>;

type StoryFinalizeRow = Readonly<{
  story_id: string;
  version: number;
  expected_current_version: number;
}>;

const SHA256 = /^[a-f0-9]{64}$/;

function json(value: unknown): string {
  return JSON.stringify(value);
}

function stringArray(value: string): readonly string[] {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function requireManifestHash(value: string): void {
  if (!SHA256.test(value)) {
    throw new TypeError("manifest hash must be a lowercase SHA-256 digest");
  }
}

function changes(result: D1ResultLike): number {
  return result.meta?.changes ?? 0;
}

function assertChangedExactly(
  results: readonly D1ResultLike[],
  expectations: readonly ChangeExpectation[],
  operation: string,
): void {
  if (
    expectations.some(
      ({ index, count }) => changes(results[index] ?? {}) !== count,
    )
  ) {
    throw new Error(
      `CAS conflict: ${operation} affected an unexpected row count`,
    );
  }
}

function packetExpectedCount(
  packet: PacketRow,
  kind: "claims" | "links" | "editionEntries" | "breakingEntries" | "assets",
): number {
  return {
    claims: packet.expected_claim_count,
    links: packet.expected_evidence_link_count,
    editionEntries: packet.expected_edition_entry_count,
    breakingEntries: packet.expected_breaking_entry_count,
    assets: packet.expected_asset_reference_count,
  }[kind];
}

function graphGuardStatement(
  db: D1DatabaseLike,
  packetId: string,
  headCondition: string,
): D1PreparedStatementLike {
  return db
    .prepare(
      `UPDATE publication_packets
       SET publication_state = CASE WHEN publication_state = 'building'
         AND expected_story_version_count = (
           SELECT count(*) FROM story_versions
           WHERE packet_id = publication_packets.packet_id
             AND publication_state = 'building'
         )
         AND expected_claim_count = (
           SELECT count(*) FROM story_claims
           WHERE packet_id = publication_packets.packet_id
             AND publication_state = 'building'
         )
         AND expected_evidence_link_count = (
           SELECT count(*) FROM story_evidence
           WHERE packet_id = publication_packets.packet_id
             AND publication_state = 'building'
         )
         AND expected_edition_entry_count = (
           SELECT count(*) FROM edition_entries
           WHERE packet_id = publication_packets.packet_id
             AND publication_state = 'building'
         )
         AND expected_breaking_entry_count = (
           SELECT count(*) FROM breaking_entries
           WHERE packet_id = publication_packets.packet_id
             AND publication_state = 'building'
         )
         AND expected_asset_reference_count = (
           SELECT count(*) FROM story_asset_references
           WHERE packet_id = publication_packets.packet_id
             AND publication_state = 'building'
         )
         AND NOT EXISTS (
           SELECT 1 FROM story_versions sv
           JOIN stories s ON s.story_id = sv.story_id
           WHERE sv.packet_id = publication_packets.packet_id
             AND (
               s.current_version <> sv.expected_current_version
               OR json_array_length(sv.claim_ids_json) <> (
                 SELECT count(*) FROM story_claims sc
                 WHERE sc.packet_id = sv.packet_id
                   AND sc.story_id = sv.story_id AND sc.version = sv.version
               )
               OR EXISTS (
                 SELECT 1 FROM json_each(sv.claim_ids_json) expected
                 WHERE NOT EXISTS (
                   SELECT 1 FROM story_claims sc
                   WHERE sc.packet_id = sv.packet_id
                     AND sc.story_id = sv.story_id AND sc.version = sv.version
                     AND sc.claim_id = expected.value
                 )
               )
               OR json_array_length(sv.asset_digests_json) <> (
                 SELECT count(*) FROM story_asset_references sar
                 WHERE sar.packet_id = sv.packet_id
                   AND sar.story_id = sv.story_id AND sar.version = sv.version
               )
               OR EXISTS (
                 SELECT 1 FROM story_visibility_events visibility
                 WHERE visibility.story_id = sv.story_id
                   AND visibility.visibility_seq = (
                     SELECT max(latest.visibility_seq)
                     FROM story_visibility_events latest
                     WHERE latest.story_id = sv.story_id
                   )
                   AND visibility.desired_quarantined = 1
               )
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM story_claims sc
           WHERE sc.packet_id = publication_packets.packet_id
             AND (
               json_array_length(sc.evidence_ids_json) <> (
                 SELECT count(*) FROM story_evidence se
                 WHERE se.packet_id = sc.packet_id
                   AND se.story_id = sc.story_id AND se.version = sc.version
                   AND se.claim_id = sc.claim_id
               )
               OR EXISTS (
                 SELECT 1 FROM json_each(sc.evidence_ids_json) expected
                 WHERE NOT EXISTS (
                   SELECT 1 FROM story_evidence se
                   WHERE se.packet_id = sc.packet_id
                     AND se.story_id = sc.story_id AND se.version = sc.version
                     AND se.claim_id = sc.claim_id
                     AND se.evidence_id = expected.value
                 )
               )
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM story_asset_references sar
           LEFT JOIN assets asset
             ON asset.sha256 = sar.asset_sha256
           JOIN story_versions sv
             ON sv.packet_id = sar.packet_id AND sv.story_id = sar.story_id
            AND sv.version = sar.version
           WHERE sar.packet_id = publication_packets.packet_id
             AND (
               asset.sha256 IS NULL
               OR (
                 NOT EXISTS (
                   SELECT 1 FROM asset_status_events status_event
                   WHERE status_event.asset_id = asset.asset_id
                 )
                 AND (
                   asset.status <> 'verified'
                   OR asset.rights_status <> 'approved'
                 )
               )
               OR EXISTS (
                 SELECT 1 FROM asset_status_events status_event
                 WHERE status_event.asset_id = asset.asset_id
                   AND status_event.status_seq = (
                     SELECT max(latest.status_seq)
                     FROM asset_status_events latest
                     WHERE latest.asset_id = asset.asset_id
                   )
                   AND (
                     status_event.status <> 'verified'
                     OR status_event.rights_status <> 'approved'
                   )
               )
               OR NOT EXISTS (
                 SELECT 1 FROM json_each(sv.asset_digests_json) expected
                 WHERE expected.value = sar.asset_sha256
               )
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM edition_entries ee
           JOIN editions e
             ON e.edition_id = ee.edition_id AND e.packet_id = ee.packet_id
           WHERE ee.packet_id = publication_packets.packet_id
             AND NOT EXISTS (
               SELECT 1 FROM json_each(e.placements_json) expected
               WHERE json_extract(expected.value, '$.story_id') = ee.story_id
                 AND json_extract(expected.value, '$.version') = ee.version
                 AND json_extract(expected.value, '$.section') = ee.section
                 AND json_extract(expected.value, '$.order') = ee.editorial_order
                 AND json_extract(expected.value, '$.lead') = ee.is_lead
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM breaking_entries be
           WHERE be.packet_id = publication_packets.packet_id
             AND NOT EXISTS (
               SELECT 1 FROM json_each(publication_packets.breaking_entries_json) expected
               WHERE json_extract(expected.value, '$.story_id') = be.story_id
                 AND json_extract(expected.value, '$.version') = be.version
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM json_each(publication_packets.referenced_claim_ids_json) expected
           WHERE NOT EXISTS (
             SELECT 1 FROM story_claims sc
             WHERE sc.packet_id = publication_packets.packet_id
               AND sc.claim_id = expected.value
           )
         )
         AND NOT EXISTS (
           SELECT 1 FROM story_claims sc
           WHERE sc.packet_id = publication_packets.packet_id
             AND NOT EXISTS (
               SELECT 1 FROM json_each(publication_packets.referenced_claim_ids_json) expected
               WHERE expected.value = sc.claim_id
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM json_each(publication_packets.referenced_evidence_ids_json) expected
           WHERE NOT EXISTS (
             SELECT 1 FROM story_evidence se
             WHERE se.packet_id = publication_packets.packet_id
               AND se.evidence_id = expected.value
           )
         )
         AND NOT EXISTS (
           SELECT 1 FROM story_evidence se
           WHERE se.packet_id = publication_packets.packet_id
             AND NOT EXISTS (
               SELECT 1 FROM json_each(publication_packets.referenced_evidence_ids_json) expected
               WHERE expected.value = se.evidence_id
             )
         )
         AND NOT EXISTS (
           SELECT 1 FROM json_each(publication_packets.referenced_asset_digests_json) expected
           WHERE NOT EXISTS (
             SELECT 1 FROM story_asset_references sar
             WHERE sar.packet_id = publication_packets.packet_id
               AND sar.asset_sha256 = expected.value
           )
         )
         AND NOT EXISTS (
           SELECT 1 FROM story_asset_references sar
           WHERE sar.packet_id = publication_packets.packet_id
             AND NOT EXISTS (
               SELECT 1 FROM json_each(publication_packets.referenced_asset_digests_json) expected
               WHERE expected.value = sar.asset_sha256
             )
         )
         ${headCondition}
       THEN 'building' ELSE '__cas_conflict__' END
       WHERE packet_id = ?`,
    )
    .bind(packetId);
}

function storyStatements(
  db: D1DatabaseLike,
  packetId: string,
  story: StoryVersionV1,
): D1PreparedStatementLike[] {
  const statements: D1PreparedStatementLike[] = [
    db
      .prepare(
        `INSERT INTO stories(story_id, slug, current_version)
         VALUES (?, ?, 0)
         ON CONFLICT(story_id) DO NOTHING`,
      )
      .bind(story.story_id, story.slug),
    db
      .prepare(
        `INSERT INTO story_versions(
           story_id, version, packet_id, expected_current_version, language,
           domain, severity, lifecycle_state, first_seen_at,
           event_occurred_at, updated_at, title,
           deck, summary, why_it_matters, curiosity_text, score_components_json,
           claim_ids_json,
           contributing_system_ids_json, coverage_state, confidence,
           asset_digests_json, adapter_version, ruleset_version, publication_state
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'building')`,
      )
      .bind(
        story.story_id,
        story.version,
        packetId,
        story.expected_current_version,
        story.language,
        story.domain,
        story.severity,
        story.lifecycle_state,
        story.first_seen_at,
        story.event_occurred_at,
        story.updated_at,
        story.title,
        story.deck,
        story.summary,
        story.why_it_matters,
        story.curiosity_text,
        json(story.score_components),
        json(story.claims.map((claim) => claim.claim_id)),
        json(story.contributing_system_ids),
        story.coverage_state,
        story.confidence,
        json(story.asset_digests),
        story.adapter_version,
        story.ruleset_version,
      ),
  ];

  for (const evidence of story.evidence_refs) {
    statements.push(evidenceStatement(db, evidence));
  }
  for (const claim of story.claims) {
    statements.push(claimStatement(db, packetId, story, claim));
    for (const evidenceId of claim.evidence_ids) {
      statements.push(
        db
          .prepare(
            `INSERT INTO story_evidence(
               packet_id, story_id, version, claim_id, evidence_id,
               publication_state
             ) VALUES (?, ?, ?, ?, ?, 'building')`,
          )
          .bind(
            packetId,
            story.story_id,
            story.version,
            claim.claim_id,
            evidenceId,
          ),
      );
    }
  }
  for (const digest of story.asset_digests) {
    statements.push(
      db
        .prepare(
          `INSERT INTO story_asset_references(
             packet_id, story_id, version, asset_sha256, publication_state
           ) VALUES (?, ?, ?, ?, 'building')`,
        )
        .bind(packetId, story.story_id, story.version, digest),
    );
  }
  return statements;
}

function evidenceStatement(
  db: D1DatabaseLike,
  evidence: EvidenceRefV1,
): D1PreparedStatementLike {
  return db
    .prepare(
      `INSERT INTO evidence_refs(
         evidence_id, root_source_id, canonical_url, publisher,
         document_citation, published_at, retrieved_at, source_type,
         primary_document_status, root_resolution_status, independence_verdict,
         evidence_note, upstream_root_source_ids_json,
         syndication_group_fingerprint, independence_ruleset_version,
         independence_reason, counts_toward_breaking
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(evidence_id) DO UPDATE SET source_type = CASE
         WHEN evidence_refs.root_source_id IS excluded.root_source_id
          AND evidence_refs.canonical_url IS excluded.canonical_url
          AND evidence_refs.publisher IS excluded.publisher
          AND evidence_refs.document_citation IS excluded.document_citation
          AND evidence_refs.published_at IS excluded.published_at
          AND evidence_refs.retrieved_at IS excluded.retrieved_at
          AND evidence_refs.source_type IS excluded.source_type
          AND evidence_refs.primary_document_status IS excluded.primary_document_status
          AND evidence_refs.root_resolution_status IS excluded.root_resolution_status
          AND evidence_refs.independence_verdict IS excluded.independence_verdict
          AND evidence_refs.evidence_note IS excluded.evidence_note
          AND evidence_refs.upstream_root_source_ids_json IS excluded.upstream_root_source_ids_json
          AND evidence_refs.syndication_group_fingerprint IS excluded.syndication_group_fingerprint
          AND evidence_refs.independence_ruleset_version IS excluded.independence_ruleset_version
          AND evidence_refs.independence_reason IS excluded.independence_reason
          AND evidence_refs.counts_toward_breaking IS excluded.counts_toward_breaking
         THEN evidence_refs.source_type ELSE '__immutable_conflict__' END`,
    )
    .bind(
      evidence.evidence_id,
      evidence.root_source_id,
      evidence.canonical_url,
      evidence.publisher,
      evidence.document_citation,
      evidence.published_at,
      evidence.retrieved_at,
      evidence.source_type,
      evidence.primary_document_status,
      evidence.root_resolution_status,
      evidence.independence_verdict,
      evidence.evidence_note,
      json(evidence.upstream_root_source_ids),
      evidence.syndication_group_fingerprint,
      evidence.independence_ruleset_version,
      evidence.independence_reason,
      evidence.counts_toward_breaking ? 1 : 0,
    );
}

function claimStatement(
  db: D1DatabaseLike,
  packetId: string,
  story: StoryVersionV1,
  claim: ClaimV1,
): D1PreparedStatementLike {
  return db
    .prepare(
      `INSERT INTO story_claims(
         claim_id, packet_id, story_id, version, claim_kind, normalized_text,
         numeric_value, numeric_unit, as_of, breaking_gate, evidence_ids_json,
         publication_state
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'building')`,
    )
    .bind(
      claim.claim_id,
      packetId,
      story.story_id,
      story.version,
      claim.claim_kind,
      claim.normalized_text,
      claim.numeric_value,
      claim.numeric_unit,
      claim.as_of,
      claim.breaking_gate,
      json(claim.evidence_ids),
    );
}

export function createPublicationRepository(
  db: D1DatabaseLike,
  options: RepositoryOptions = {},
) {
  const now = options.now ?? (() => new Date().toISOString());

  async function getPacket(packetId: string): Promise<PacketRow | null> {
    return db
      .prepare(
        `SELECT packet_id, manifest_hash, packet_kind, publication_state,
                expected_claim_count, expected_evidence_link_count,
                expected_edition_entry_count, expected_breaking_entry_count,
                expected_asset_reference_count
         FROM publication_packets WHERE packet_id = ?`,
      )
      .bind(packetId)
      .first<PacketRow>();
  }

  async function checkReplay(
    packetId: string,
    manifestHash: string,
    kind: PacketRow["packet_kind"],
  ): Promise<boolean> {
    requireManifestHash(manifestHash);
    const existing = await getPacket(packetId);
    if (existing === null) return false;
    if (
      existing.manifest_hash !== manifestHash ||
      existing.packet_kind !== kind
    ) {
      throw new Error(`replay hash mismatch for packet ${packetId}`);
    }
    return true;
  }

  async function recoverFinalizeConflict(
    packetId: string,
    kind: PacketRow["packet_kind"],
    cause: unknown,
  ): Promise<FinalizeResult> {
    // A concurrent duplicate may observe "building" before the winner's batch.
    // Re-read after rollback so the loser has explicit idempotent replay semantics.
    const winner = await getPacket(packetId);
    if (
      winner?.packet_kind === kind &&
      winner.publication_state === "published"
    ) {
      return "replay";
    }
    if (cause instanceof Error && cause.message.startsWith("CAS conflict:")) {
      throw cause;
    }
    const label = kind === "edition" ? "edition" : "Breaking";
    throw new Error(`CAS conflict: ${label} finalization rolled back`, {
      cause,
    });
  }

  async function verifyStoryIdentities(
    stories: readonly StoryVersionV1[],
  ): Promise<void> {
    for (const story of stories) {
      const existing = await db
        .prepare("SELECT slug FROM stories WHERE story_id = ?")
        .bind(story.story_id)
        .first<{ slug: string }>();
      if (existing !== null && existing.slug !== story.slug) {
        throw new Error(`story identity conflict for ${story.story_id}`);
      }
    }
  }

  function graphCounts(stories: readonly StoryVersionV1[]) {
    return {
      stories: stories.length,
      claims: stories.reduce((total, story) => total + story.claims.length, 0),
      links: stories.reduce(
        (total, story) =>
          total +
          story.claims.reduce(
            (claimTotal, claim) => claimTotal + claim.evidence_ids.length,
            0,
          ),
        0,
      ),
      assets: stories.reduce(
        (total, story) => total + story.asset_digests.length,
        0,
      ),
    };
  }

  async function recoverStageConflict(
    packetId: string,
    manifestHash: string,
    kind: PacketRow["packet_kind"],
    cause: unknown,
  ): Promise<StageResult> {
    if (await checkReplay(packetId, manifestHash, kind)) return "replay";
    if (
      /evidence_refs_source_type_check|__immutable_conflict__/i.test(
        String(cause),
      )
    ) {
      throw new Error("immutable evidence conflict", { cause });
    }
    throw new Error("publication staging conflict", { cause });
  }

  async function resolveBreakingEntries(
    storyIds: readonly string[],
    stagedStories: readonly StoryVersionV1[],
  ): Promise<BreakingEntryRow[]> {
    const entries: BreakingEntryRow[] = [];
    for (const storyId of storyIds) {
      const staged = stagedStories.find((story) => story.story_id === storyId);
      if (staged !== undefined) {
        entries.push({ story_id: storyId, version: staged.version });
        continue;
      }
      const published = await db
        .prepare(
          `SELECT s.story_id, s.current_version AS version
           FROM stories s
           JOIN story_versions sv
             ON sv.story_id = s.story_id AND sv.version = s.current_version
           WHERE s.story_id = ? AND sv.publication_state = 'published'`,
        )
        .bind(storyId)
        .first<BreakingEntryRow>();
      if (published === null) {
        throw new Error(`unknown published Breaking story ${storyId}`);
      }
      entries.push(published);
    }
    return entries;
  }

  async function stageEdition(
    packet: EditionPacketV1,
    manifestHash: string,
  ): Promise<StageResult> {
    if (await checkReplay(packet.packet_id, manifestHash, "edition")) {
      return "replay";
    }
    await verifyStoryIdentities(packet.stories);
    const counts = graphCounts(packet.stories);
    const breakingEntries = await resolveBreakingEntries(
      packet.breaking_story_ids,
      packet.stories,
    );

    const statements: D1PreparedStatementLike[] = [
      db
        .prepare(
          `INSERT INTO publication_packets(
             packet_id, manifest_hash, packet_kind, publication_state,
             expected_story_version_count, expected_claim_count,
             expected_evidence_link_count, expected_edition_entry_count,
             expected_breaking_entry_count, expected_asset_reference_count,
             referenced_claim_ids_json, referenced_evidence_ids_json,
             referenced_asset_digests_json, breaking_entries_json
           ) VALUES (?, ?, 'edition', 'building', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .bind(
          packet.packet_id,
          manifestHash,
          counts.stories,
          counts.claims,
          counts.links,
          packet.placements.length,
          breakingEntries.length,
          counts.assets,
          json(packet.referenced_claim_ids),
          json(packet.referenced_evidence_ids),
          json(packet.asset_digests),
          json(breakingEntries),
        ),
    ];
    for (const story of packet.stories) {
      statements.push(...storyStatements(db, packet.packet_id, story));
    }
    statements.push(
      db
        .prepare(
          `INSERT INTO editions(
             edition_id, packet_id, editor_version, ruleset_version,
             edition_date, edition_revision, expected_current_revision,
             expected_breaking_revision, edition_kind, publication_state,
             coverage_state, readiness_cutoff, verified_at,
             collector_run_ids_json, placements_json, breaking_story_ids_json,
             asset_digests_json, coverage_gaps_json, reader_notices_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'building', ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .bind(
          packet.packet_id,
          packet.packet_id,
          packet.editor_version,
          packet.ruleset_version,
          packet.edition_date,
          packet.edition_revision,
          packet.expected_current_revision,
          packet.expected_breaking_revision,
          packet.edition_kind,
          packet.coverage_state,
          packet.readiness_cutoff,
          packet.verified_at,
          json(packet.collector_run_ids),
          json(packet.placements),
          json(packet.breaking_story_ids),
          json(packet.asset_digests),
          json(packet.coverage_gaps),
          json(packet.reader_notices),
        ),
    );
    for (const placement of packet.placements) {
      statements.push(
        db
          .prepare(
            `INSERT INTO edition_entries(
               edition_id, packet_id, story_id, version, section,
               editorial_order, is_lead, publication_state
             ) VALUES (?, ?, ?, ?, ?, ?, ?, 'building')`,
          )
          .bind(
            packet.packet_id,
            packet.packet_id,
            placement.story_id,
            placement.version,
            placement.section,
            placement.order,
            placement.lead ? 1 : 0,
          ),
      );
    }
    const nextBreakingRevision = packet.expected_breaking_revision + 1;
    for (const entry of breakingEntries) {
      statements.push(
        db
          .prepare(
            `INSERT INTO breaking_entries(
               breaking_revision, story_id, version, packet_id,
               publication_state
             ) VALUES (?, ?, ?, ?, 'building')`,
          )
          .bind(
            nextBreakingRevision,
            entry.story_id,
            entry.version,
            packet.packet_id,
          ),
      );
    }

    try {
      await db.batch(statements);
    } catch (cause) {
      return recoverStageConflict(
        packet.packet_id,
        manifestHash,
        "edition",
        cause,
      );
    }
    return "staged";
  }

  async function stageBreaking(
    packet: StoryPacketV1,
    manifestHash: string,
  ): Promise<StageResult> {
    if (await checkReplay(packet.packet_id, manifestHash, "breaking")) {
      return "replay";
    }
    await verifyStoryIdentities([packet.story]);
    const nextBreakingRevision = packet.expected_breaking_revision + 1;
    const existingResult = await db
      .prepare(
        `SELECT be.story_id, be.version
         FROM breaking_entries be
         JOIN story_versions sv
           ON sv.story_id = be.story_id AND sv.version = be.version
         WHERE be.breaking_revision = ?
           AND be.publication_state = 'published'
           AND sv.publication_state = 'published'
           AND be.story_id <> ?
         ORDER BY be.story_id`,
      )
      .bind(packet.expected_breaking_revision, packet.story.story_id)
      .all<BreakingEntryRow>();
    const breakingEntries = [
      ...(existingResult.results ?? []),
      { story_id: packet.story.story_id, version: packet.story.version },
    ];
    const counts = graphCounts([packet.story]);
    const statements: D1PreparedStatementLike[] = [
      db
        .prepare(
          `INSERT INTO publication_packets(
             packet_id, manifest_hash, packet_kind, publication_state,
             expected_story_version_count, expected_claim_count,
             expected_evidence_link_count, expected_edition_entry_count,
             expected_breaking_entry_count, expected_asset_reference_count,
             referenced_claim_ids_json, referenced_evidence_ids_json,
             referenced_asset_digests_json, breaking_entries_json
           ) VALUES (?, ?, 'breaking', 'building', ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)`,
        )
        .bind(
          packet.packet_id,
          manifestHash,
          counts.stories,
          counts.claims,
          counts.links,
          breakingEntries.length,
          counts.assets,
          json(packet.story.claims.map((claim) => claim.claim_id)),
          json(packet.story.evidence_refs.map((item) => item.evidence_id)),
          json(packet.story.asset_digests),
          json(breakingEntries),
        ),
      ...storyStatements(db, packet.packet_id, packet.story),
    ];
    for (const entry of breakingEntries) {
      statements.push(
        db
          .prepare(
            `INSERT INTO breaking_entries(
               breaking_revision, story_id, version, packet_id,
               publication_state
             ) VALUES (?, ?, ?, ?, 'building')`,
          )
          .bind(
            nextBreakingRevision,
            entry.story_id,
            entry.version,
            packet.packet_id,
          ),
      );
    }
    try {
      await db.batch(statements);
    } catch (cause) {
      return recoverStageConflict(
        packet.packet_id,
        manifestHash,
        "breaking",
        cause,
      );
    }
    return "staged";
  }

  async function finalizeEdition(packetId: string): Promise<FinalizeResult> {
    const packet = await getPacket(packetId);
    if (packet?.packet_kind !== "edition") {
      throw new Error(`unknown edition packet ${packetId}`);
    }
    if (packet.publication_state === "published") return "replay";
    if (packet.publication_state !== "building") {
      throw new Error(`edition packet ${packetId} is not staged`);
    }
    const edition = await db
      .prepare(
        `SELECT edition_id, edition_revision, expected_current_revision,
                expected_breaking_revision
         FROM editions WHERE packet_id = ? AND publication_state = 'building'`,
      )
      .bind(packetId)
      .first<EditionFinalizeRow>();
    if (edition === null) throw new Error(`unknown staged edition ${packetId}`);
    const storyResult = await db
      .prepare(
        `SELECT story_id, version, expected_current_version
         FROM story_versions WHERE packet_id = ? AND publication_state = 'building'
         ORDER BY story_id`,
      )
      .bind(packetId)
      .all<StoryFinalizeRow>();
    const stories = storyResult.results ?? [];
    const publishedAt = now();
    const nextBreakingRevision = edition.expected_breaking_revision + 1;

    const statements: D1PreparedStatementLike[] = [
      graphGuardStatement(
        db,
        packetId,
        `AND EXISTS (
           SELECT 1 FROM editions e, edition_pointer ep, breaking_pointer bp
           WHERE e.packet_id = publication_packets.packet_id
             AND e.publication_state = 'building'
             AND ep.singleton_id = 1
             AND bp.singleton_id = 1
             AND e.expected_current_revision = ep.current_revision
             AND e.expected_breaking_revision = bp.active_revision
         )`,
      ),
      db
        .prepare(
          `UPDATE editions SET publication_state = 'published', published_at = ?
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(publishedAt, packetId),
      db
        .prepare(
          `UPDATE story_versions SET publication_state = 'published', published_at = ?
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(publishedAt, packetId),
      db
        .prepare(
          `UPDATE story_claims SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE story_evidence SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE edition_entries SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE breaking_entries SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE story_asset_references SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
    ];
    const expectations: ChangeExpectation[] = [
      { index: 0, count: 1 },
      { index: 1, count: 1 },
      { index: 2, count: stories.length },
      { index: 3, count: packetExpectedCount(packet, "claims") },
      { index: 4, count: packetExpectedCount(packet, "links") },
      { index: 5, count: packetExpectedCount(packet, "editionEntries") },
      { index: 6, count: packetExpectedCount(packet, "breakingEntries") },
      { index: 7, count: packetExpectedCount(packet, "assets") },
    ];
    for (const story of stories) {
      statements.push(
        db
          .prepare(
            `UPDATE stories SET current_version = ?
             WHERE story_id = ? AND current_version = ?`,
          )
          .bind(story.version, story.story_id, story.expected_current_version),
      );
      expectations.push({ index: statements.length - 1, count: 1 });
    }
    statements.push(
      db
        .prepare(
          `UPDATE edition_pointer
           SET current_edition_id = ?, current_revision = ?
           WHERE singleton_id = 1 AND current_revision = ?`,
        )
        .bind(
          edition.edition_id,
          edition.edition_revision,
          edition.expected_current_revision,
        ),
    );
    expectations.push({ index: statements.length - 1, count: 1 });
    statements.push(
      db
        .prepare(
          `UPDATE breaking_pointer SET active_revision = ?, updated_at = ?
           WHERE singleton_id = 1 AND active_revision = ?`,
        )
        .bind(
          nextBreakingRevision,
          publishedAt,
          edition.expected_breaking_revision,
        ),
    );
    expectations.push({ index: statements.length - 1, count: 1 });
    statements.push(
      db
        .prepare(
          `UPDATE publication_packets
           SET publication_state = 'published', published_at = ?
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(publishedAt, packetId),
    );
    expectations.push({ index: statements.length - 1, count: 1 });

    try {
      const results = await db.batch(statements);
      assertChangedExactly(results, expectations, "edition finalization");
    } catch (cause) {
      return recoverFinalizeConflict(packetId, "edition", cause);
    }
    return "published";
  }

  async function finalizeBreaking(packetId: string): Promise<FinalizeResult> {
    const packet = await getPacket(packetId);
    if (packet?.packet_kind !== "breaking") {
      throw new Error(`unknown Breaking packet ${packetId}`);
    }
    if (packet.publication_state === "published") return "replay";
    if (packet.publication_state !== "building") {
      throw new Error(`Breaking packet ${packetId} is not staged`);
    }
    const story = await db
      .prepare(
        `SELECT story_id, version, expected_current_version
         FROM story_versions
         WHERE packet_id = ? AND publication_state = 'building'`,
      )
      .bind(packetId)
      .first<StoryFinalizeRow>();
    if (story === null) throw new Error(`unknown staged Breaking ${packetId}`);
    const entry = await db
      .prepare(
        `SELECT breaking_revision FROM breaking_entries
         WHERE packet_id = ? AND story_id = ?`,
      )
      .bind(packetId, story.story_id)
      .first<{ breaking_revision: number }>();
    if (entry === null)
      throw new Error(`missing staged Breaking entry ${packetId}`);
    const expectedBreakingRevision = entry.breaking_revision - 1;
    const publishedAt = now();
    const statements: D1PreparedStatementLike[] = [
      graphGuardStatement(
        db,
        packetId,
        `AND EXISTS (
           SELECT 1 FROM breaking_pointer bp
           WHERE bp.singleton_id = 1
             AND bp.active_revision = ${Number(expectedBreakingRevision)}
         )`,
      ),
      db
        .prepare(
          `UPDATE story_versions SET publication_state = 'published', published_at = ?
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(publishedAt, packetId),
      db
        .prepare(
          `UPDATE story_claims SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE story_evidence SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE breaking_entries SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE story_asset_references SET publication_state = 'published'
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(packetId),
      db
        .prepare(
          `UPDATE stories SET current_version = ?
           WHERE story_id = ? AND current_version = ?`,
        )
        .bind(story.version, story.story_id, story.expected_current_version),
      db
        .prepare(
          `UPDATE breaking_pointer SET active_revision = ?, updated_at = ?
           WHERE singleton_id = 1 AND active_revision = ?`,
        )
        .bind(entry.breaking_revision, publishedAt, expectedBreakingRevision),
      db
        .prepare(
          `UPDATE publication_packets
           SET publication_state = 'published', published_at = ?
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(publishedAt, packetId),
    ];
    try {
      const results = await db.batch(statements);
      assertChangedExactly(
        results,
        [
          { index: 0, count: 1 },
          { index: 1, count: 1 },
          { index: 2, count: packetExpectedCount(packet, "claims") },
          { index: 3, count: packetExpectedCount(packet, "links") },
          { index: 4, count: packetExpectedCount(packet, "breakingEntries") },
          { index: 5, count: packetExpectedCount(packet, "assets") },
          { index: 6, count: 1 },
          { index: 7, count: 1 },
          { index: 8, count: 1 },
        ],
        "Breaking finalization",
      );
    } catch (cause) {
      return recoverFinalizeConflict(packetId, "breaking", cause);
    }
    return "published";
  }

  async function getPublishedEdition(
    editionId: string,
  ): Promise<PublishedEdition | null> {
    const row = await db
      .prepare(
        `SELECT edition_id, edition_date, edition_revision, edition_kind,
                coverage_state, verified_at, published_at,
                coverage_gaps_json, reader_notices_json
         FROM editions
         WHERE edition_id = ? AND publication_state = 'published'`,
      )
      .bind(editionId)
      .first<{
        edition_id: string;
        edition_date: string;
        edition_revision: number;
        edition_kind: PublishedEdition["edition_kind"];
        coverage_state: PublishedEdition["coverage_state"];
        verified_at: string;
        published_at: string | null;
        coverage_gaps_json: string;
        reader_notices_json: string;
      }>();
    if (row === null || row.published_at === null) return null;
    const entryResult = await db
      .prepare(
        `SELECT ee.story_id, ee.version, ee.section,
                ee.editorial_order AS "order", ee.is_lead AS lead,
                s.slug, sv.language,
                sv.domain, sv.severity, sv.lifecycle_state,
                sv.first_seen_at, sv.event_occurred_at, sv.updated_at,
                sv.title, sv.deck,
                sv.summary, sv.why_it_matters, sv.curiosity_text,
                sv.coverage_state, sv.confidence, sv.published_at
         FROM edition_entries ee
         JOIN stories s ON s.story_id = ee.story_id
         JOIN story_versions sv
           ON sv.story_id = ee.story_id AND sv.version = ee.version
         WHERE ee.edition_id = ?
           AND ee.publication_state = 'published'
           AND sv.publication_state = 'published'
           AND NOT EXISTS (
             SELECT 1 FROM story_visibility_events visibility
             WHERE visibility.story_id = ee.story_id
               AND visibility.visibility_seq = (
                 SELECT max(latest.visibility_seq)
                 FROM story_visibility_events latest
                 WHERE latest.story_id = ee.story_id
               )
               AND visibility.desired_quarantined = 1
           )
         ORDER BY ee.is_lead DESC, ee.section, ee.editorial_order`,
      )
      .bind(editionId)
      .all<{
        story_id: string;
        version: number;
        section: EditionPlacementV1["section"];
        order: number;
        lead: number | boolean;
        slug: string;
        language: string;
        domain: StoryVersionV1["domain"];
        severity: StoryVersionV1["severity"];
        lifecycle_state: StoryVersionV1["lifecycle_state"];
        first_seen_at: string;
        event_occurred_at: string | null;
        updated_at: string;
        title: string;
        deck: string;
        summary: string;
        why_it_matters: string;
        curiosity_text: string | null;
        coverage_state: StoryVersionV1["coverage_state"];
        confidence: StoryVersionV1["confidence"];
        published_at: string;
      }>();
    return {
      edition_id: row.edition_id,
      edition_date: row.edition_date,
      edition_revision: row.edition_revision,
      edition_kind: row.edition_kind,
      coverage_state: row.coverage_state,
      verified_at: row.verified_at,
      published_at: row.published_at,
      coverage_gaps: stringArray(row.coverage_gaps_json),
      reader_notices: stringArray(row.reader_notices_json),
      entries: (entryResult.results ?? []).map((entry) => ({
        story_id: entry.story_id,
        version: entry.version,
        section: entry.section,
        order: entry.order,
        lead: Boolean(entry.lead),
        story: {
          story_id: entry.story_id,
          version: entry.version,
          slug: entry.slug,
          language: entry.language,
          domain: entry.domain,
          severity: entry.severity,
          lifecycle_state: entry.lifecycle_state,
          first_seen_at: entry.first_seen_at,
          event_occurred_at: entry.event_occurred_at,
          updated_at: entry.updated_at,
          title: entry.title,
          deck: entry.deck,
          summary: entry.summary,
          why_it_matters: entry.why_it_matters,
          curiosity_text: entry.curiosity_text,
          coverage_state: entry.coverage_state,
          confidence: entry.confidence,
          published_at: entry.published_at,
        },
      })),
    };
  }

  async function getCurrentEdition(): Promise<PublishedEdition | null> {
    const head = await db
      .prepare(
        `SELECT ep.current_edition_id
         FROM edition_pointer ep
         JOIN editions e ON e.edition_id = ep.current_edition_id
         WHERE ep.singleton_id = 1 AND e.publication_state = 'published'`,
      )
      .first<{ current_edition_id: string }>();
    return head === null ? null : getPublishedEdition(head.current_edition_id);
  }

  async function getCurrentStory(slug: string): Promise<PublishedStory | null> {
    return db
      .prepare(
        `SELECT s.story_id, sv.version, s.slug, sv.language, sv.domain,
                sv.severity, sv.lifecycle_state, sv.first_seen_at,
                sv.event_occurred_at, sv.updated_at, sv.title, sv.deck, sv.summary,
                sv.why_it_matters, sv.curiosity_text, sv.coverage_state,
                sv.confidence, sv.published_at
         FROM stories s
         JOIN story_versions sv
           ON sv.story_id = s.story_id AND sv.version = s.current_version
         WHERE s.slug = ? AND sv.publication_state = 'published'
           AND NOT EXISTS (
             SELECT 1 FROM story_visibility_events visibility
             WHERE visibility.story_id = s.story_id
               AND visibility.visibility_seq = (
                 SELECT max(latest.visibility_seq)
                 FROM story_visibility_events latest
                 WHERE latest.story_id = s.story_id
               )
               AND visibility.desired_quarantined = 1
           )`,
      )
      .bind(slug)
      .first<PublishedStory>();
  }

  async function getActiveBreaking(): Promise<readonly PublishedStory[]> {
    const result = await db
      .prepare(
        `SELECT s.story_id, sv.version, s.slug, sv.language, sv.domain,
                sv.severity, sv.lifecycle_state, sv.first_seen_at,
                sv.event_occurred_at, sv.updated_at, sv.title, sv.deck, sv.summary,
                sv.why_it_matters, sv.curiosity_text, sv.coverage_state,
                sv.confidence, sv.published_at
         FROM breaking_pointer bp
         JOIN breaking_entries be ON be.breaking_revision = bp.active_revision
         JOIN stories s
           ON s.story_id = be.story_id AND s.current_version = be.version
         JOIN story_versions sv
           ON sv.story_id = be.story_id AND sv.version = be.version
         WHERE bp.singleton_id = 1
           AND be.publication_state = 'published'
           AND sv.publication_state = 'published'
           AND NOT EXISTS (
             SELECT 1 FROM story_visibility_events visibility
             WHERE visibility.story_id = be.story_id
               AND visibility.visibility_seq = (
                 SELECT max(latest.visibility_seq)
                 FROM story_visibility_events latest
                 WHERE latest.story_id = be.story_id
               )
               AND visibility.desired_quarantined = 1
           )
         ORDER BY CASE sv.severity WHEN 'critical' THEN 0 ELSE 1 END,
                  sv.published_at DESC, be.story_id`,
      )
      .all<PublishedStory>();
    return (result.results ?? []).map((row) => ({ ...row }));
  }

  return {
    stageEdition,
    finalizeEdition,
    stageBreaking,
    finalizeBreaking,
    getCurrentEdition,
    getPublishedEdition,
    getCurrentStory,
    getActiveBreaking,
  };
}
