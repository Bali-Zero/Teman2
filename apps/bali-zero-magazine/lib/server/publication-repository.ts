import type {
  ClaimV1,
  EditionPacketV1,
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
  domain: string;
  severity: string;
  lifecycle_state: string;
  title: string;
  deck: string;
  summary: string;
  why_it_matters: string;
  curiosity_text: string | null;
  coverage_state: string;
  confidence: string;
  published_at: string;
}>;

export type PublishedEdition = Readonly<{
  edition_id: string;
  edition_date: string;
  edition_revision: number;
  edition_kind: string;
  coverage_state: string;
  published_at: string;
  entries: readonly Readonly<{
    story_id: string;
    version: number;
    section: string;
    order: number;
  }>[];
}>;

type RepositoryOptions = Readonly<{ now?: () => string }>;
type PacketRow = Readonly<{
  packet_id: string;
  manifest_hash: string;
  packet_kind: "edition" | "breaking";
  publication_state: "building" | "published" | "failed";
}>;

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
  indexes: readonly number[],
  operation: string,
): void {
  if (indexes.some((index) => changes(results[index] ?? {}) !== 1)) {
    throw new Error(
      `CAS conflict: ${operation} affected an unexpected row count`,
    );
  }
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
           domain, severity, lifecycle_state, first_seen_at, updated_at, title,
           deck, summary, why_it_matters, curiosity_text, score_components_json,
           contributing_system_ids_json, coverage_state, confidence,
           asset_digests_json, adapter_version, ruleset_version, publication_state
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'building')`,
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
        story.updated_at,
        story.title,
        story.deck,
        story.summary,
        story.why_it_matters,
        story.curiosity_text,
        json(story.score_components),
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
    statements.push(claimStatement(db, story, claim));
    for (const evidenceId of claim.evidence_ids) {
      statements.push(
        db
          .prepare(
            `INSERT INTO story_evidence(story_id, version, claim_id, evidence_id)
             VALUES (?, ?, ?, ?)`,
          )
          .bind(story.story_id, story.version, claim.claim_id, evidenceId),
      );
    }
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
       ON CONFLICT(evidence_id) DO NOTHING`,
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
  story: StoryVersionV1,
  claim: ClaimV1,
): D1PreparedStatementLike {
  return db
    .prepare(
      `INSERT INTO story_claims(
         claim_id, story_id, version, claim_kind, normalized_text,
         numeric_value, numeric_unit, as_of, breaking_gate
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      claim.claim_id,
      story.story_id,
      story.version,
      claim.claim_kind,
      claim.normalized_text,
      claim.numeric_value,
      claim.numeric_unit,
      claim.as_of,
      claim.breaking_gate,
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
        `SELECT packet_id, manifest_hash, packet_kind, publication_state
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

  async function stageEdition(
    packet: EditionPacketV1,
    manifestHash: string,
  ): Promise<StageResult> {
    if (await checkReplay(packet.packet_id, manifestHash, "edition")) {
      return "replay";
    }
    await verifyStoryIdentities(packet.stories);

    const statements: D1PreparedStatementLike[] = [
      db
        .prepare(
          `INSERT INTO publication_packets(packet_id, manifest_hash, packet_kind, publication_state)
           VALUES (?, ?, 'edition', 'building')`,
        )
        .bind(packet.packet_id, manifestHash),
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
             collector_run_ids_json, breaking_story_ids_json,
             asset_digests_json, coverage_gaps_json, reader_notices_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'building', ?, ?, ?, ?, ?, ?, ?, ?)`,
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
               edition_id, story_id, version, section, editorial_order
             ) VALUES (?, ?, ?, ?, ?)`,
          )
          .bind(
            packet.packet_id,
            placement.story_id,
            placement.version,
            placement.section,
            placement.order,
          ),
      );
    }
    const nextBreakingRevision = packet.expected_breaking_revision + 1;
    for (const storyId of packet.breaking_story_ids) {
      const stagedStory = packet.stories.find(
        (candidate) => candidate.story_id === storyId,
      );
      if (stagedStory !== undefined) {
        statements.push(
          db
            .prepare(
              `INSERT INTO breaking_entries(
                 breaking_revision, story_id, version, packet_id
               ) VALUES (?, ?, ?, ?)`,
            )
            .bind(
              nextBreakingRevision,
              storyId,
              stagedStory.version,
              packet.packet_id,
            ),
        );
      } else {
        statements.push(
          db
            .prepare(
              `INSERT INTO breaking_entries(
                 breaking_revision, story_id, version, packet_id
               )
               SELECT ?, story_id, current_version, ? FROM stories
               WHERE story_id = ?`,
            )
            .bind(nextBreakingRevision, packet.packet_id, storyId),
        );
      }
    }

    try {
      await db.batch(statements);
    } catch (cause) {
      throw new Error("publication staging conflict", { cause });
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
    const statements: D1PreparedStatementLike[] = [
      db
        .prepare(
          `INSERT INTO publication_packets(packet_id, manifest_hash, packet_kind, publication_state)
           VALUES (?, ?, 'breaking', 'building')`,
        )
        .bind(packet.packet_id, manifestHash),
      ...storyStatements(db, packet.packet_id, packet.story),
      db
        .prepare(
          `INSERT INTO breaking_entries(
             breaking_revision, story_id, version, packet_id
           ) VALUES (?, ?, ?, ?)`,
        )
        .bind(
          nextBreakingRevision,
          packet.story.story_id,
          packet.story.version,
          packet.packet_id,
        ),
    ];
    try {
      await db.batch(statements);
    } catch (cause) {
      throw new Error("publication staging conflict", { cause });
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
      db
        .prepare(
          `UPDATE editions
           SET publication_state = CASE
             WHEN publication_state = 'building'
              AND expected_current_revision = (
                SELECT current_revision FROM edition_pointer WHERE singleton_id = 1
              )
              AND expected_breaking_revision = (
                SELECT active_revision FROM breaking_pointer WHERE singleton_id = 1
              )
              AND (SELECT count(*) FROM story_versions WHERE packet_id = ?) = ?
              AND NOT EXISTS (
                SELECT 1 FROM story_versions sv
                JOIN stories s ON s.story_id = sv.story_id
                WHERE sv.packet_id = ? AND (
                  sv.publication_state <> 'building'
                  OR s.current_version <> sv.expected_current_version
                  OR EXISTS (
                    SELECT 1 FROM json_each(sv.asset_digests_json) digest
                    LEFT JOIN assets asset
                      ON asset.sha256 = digest.value
                     AND asset.status = 'verified'
                     AND asset.rights_status = 'approved'
                    WHERE asset.sha256 IS NULL
                  )
                )
              )
             THEN 'published' ELSE '__cas_conflict__' END,
             published_at = ?
           WHERE packet_id = ?`,
        )
        .bind(packetId, stories.length, packetId, publishedAt, packetId),
    ];
    const requiredIndexes = [0];
    for (const story of stories) {
      statements.push(
        db
          .prepare(
            `UPDATE story_versions SET publication_state = 'published', published_at = ?
             WHERE packet_id = ? AND story_id = ? AND version = ?
               AND publication_state = 'building'`,
          )
          .bind(publishedAt, packetId, story.story_id, story.version),
      );
      requiredIndexes.push(statements.length - 1);
      statements.push(
        db
          .prepare(
            `UPDATE stories SET current_version = ?
             WHERE story_id = ? AND current_version = ?`,
          )
          .bind(story.version, story.story_id, story.expected_current_version),
      );
      requiredIndexes.push(statements.length - 1);
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
    requiredIndexes.push(statements.length - 1);
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
    requiredIndexes.push(statements.length - 1);
    statements.push(
      db
        .prepare(
          `UPDATE publication_packets
           SET publication_state = 'published', published_at = ?
           WHERE packet_id = ? AND publication_state = 'building'`,
        )
        .bind(publishedAt, packetId),
    );
    requiredIndexes.push(statements.length - 1);

    try {
      const results = await db.batch(statements);
      assertChangedExactly(results, requiredIndexes, "edition finalization");
    } catch (cause) {
      if (cause instanceof Error && cause.message.startsWith("CAS conflict:")) {
        throw cause;
      }
      throw new Error("CAS conflict: edition finalization rolled back", {
        cause,
      });
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
      db
        .prepare(
          `UPDATE story_versions
           SET publication_state = CASE
             WHEN publication_state = 'building'
              AND expected_current_version = (
                SELECT current_version FROM stories WHERE story_id = ?
              )
              AND ? = (
                SELECT active_revision FROM breaking_pointer WHERE singleton_id = 1
              )
              AND NOT EXISTS (
                SELECT 1 FROM json_each(asset_digests_json) digest
                LEFT JOIN assets asset
                  ON asset.sha256 = digest.value
                 AND asset.status = 'verified'
                 AND asset.rights_status = 'approved'
                WHERE asset.sha256 IS NULL
              )
             THEN 'published' ELSE '__cas_conflict__' END,
             published_at = ?
           WHERE packet_id = ? AND story_id = ? AND version = ?`,
        )
        .bind(
          story.story_id,
          expectedBreakingRevision,
          publishedAt,
          packetId,
          story.story_id,
          story.version,
        ),
      db
        .prepare(
          `UPDATE stories SET current_version = ?
           WHERE story_id = ? AND current_version = ?`,
        )
        .bind(story.version, story.story_id, story.expected_current_version),
      db
        .prepare(
          `INSERT INTO breaking_entries(
             breaking_revision, story_id, version, packet_id
           )
           SELECT ?, story_id, version, ? FROM breaking_entries
           WHERE breaking_revision = ? AND story_id <> ?`,
        )
        .bind(
          entry.breaking_revision,
          packetId,
          expectedBreakingRevision,
          story.story_id,
        ),
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
      assertChangedExactly(results, [0, 1, 3, 4], "Breaking finalization");
    } catch (cause) {
      if (cause instanceof Error && cause.message.startsWith("CAS conflict:")) {
        throw cause;
      }
      throw new Error("CAS conflict: Breaking finalization rolled back", {
        cause,
      });
    }
    return "published";
  }

  async function getPublishedEdition(
    editionId: string,
  ): Promise<PublishedEdition | null> {
    const row = await db
      .prepare(
        `SELECT edition_id, edition_date, edition_revision, edition_kind,
                coverage_state, published_at
         FROM editions
         WHERE edition_id = ? AND publication_state = 'published'`,
      )
      .bind(editionId)
      .first<Omit<PublishedEdition, "entries">>();
    if (row === null || row.published_at === null) return null;
    const entryResult = await db
      .prepare(
        `SELECT ee.story_id, ee.version, ee.section,
                ee.editorial_order AS "order"
         FROM edition_entries ee
         JOIN story_versions sv
           ON sv.story_id = ee.story_id AND sv.version = ee.version
         WHERE ee.edition_id = ? AND sv.publication_state = 'published'
         ORDER BY ee.section, ee.editorial_order`,
      )
      .bind(editionId)
      .all<PublishedEdition["entries"][number]>();
    return {
      ...row,
      published_at: row.published_at,
      entries: entryResult.results ?? [],
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
                sv.severity, sv.lifecycle_state, sv.title, sv.deck, sv.summary,
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

  async function getActiveBreaking(): Promise<readonly string[]> {
    const result = await db
      .prepare(
        `SELECT be.story_id
         FROM breaking_pointer bp
         JOIN breaking_entries be ON be.breaking_revision = bp.active_revision
         JOIN stories s
           ON s.story_id = be.story_id AND s.current_version = be.version
         JOIN story_versions sv
           ON sv.story_id = be.story_id AND sv.version = be.version
         WHERE bp.singleton_id = 1 AND sv.publication_state = 'published'
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
         ORDER BY be.story_id`,
      )
      .all<{ story_id: string }>();
    return (result.results ?? []).map((row) => row.story_id);
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
