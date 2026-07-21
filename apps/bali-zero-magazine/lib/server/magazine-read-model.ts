import { headers } from "next/headers.js";

import type {
  ClaimKind,
  EditionPlacementV1,
  StoryVersionV1,
} from "../contracts/publication.ts";
import type { Viewer } from "./authorization.ts";
import { authorize, parseRoleAllowlist } from "./authorization.ts";
import { isAssetEligible } from "./asset-eligibility.ts";
import { requireViewer } from "./identity.ts";
import type {
  D1DatabaseLike,
  PublishedEdition,
  PublishedStory,
} from "./publication-repository.ts";
import { createPublicationRepository } from "./publication-repository.ts";
import { getMagazineBindings } from "./runtime-bindings.ts";

export const DOMAIN_SECTIONS = [
  { key: "immigration", label: "Immigration" },
  { key: "company", label: "Company & Investment" },
  { key: "tax", label: "Tax" },
  { key: "property", label: "Property" },
  { key: "compliance", label: "Regulation & Compliance" },
] as const satisfies readonly Readonly<{
  key: EditionPlacementV1["section"];
  label: string;
}>[];

export type StoryCardView = Readonly<{
  slug: string;
  domain: StoryVersionV1["domain"];
  severity: StoryVersionV1["severity"];
  title: string;
  deck: string;
  summary: string;
  whyItMatters: string;
  curiosityText: string | null;
  coverageState: StoryVersionV1["coverage_state"];
  confidence: StoryVersionV1["confidence"];
  publishedAt: string;
  imageAlt: string;
}>;

export type SourceStatusView = Readonly<{
  name: string;
  health: "healthy" | "delayed" | "degraded" | "unavailable" | "unknown";
  verifiedAt: string | null;
}>;

export type EditionView = Readonly<{
  date: string;
  revision: number;
  kind: PublishedEdition["edition_kind"];
  coverageState: PublishedEdition["coverage_state"];
  verifiedAt: string;
  publishedAt: string;
  coverageGaps: readonly string[];
  readerNotices: readonly string[];
}>;

export type FrontPageView = Readonly<{
  edition: EditionView | null;
  hero: StoryCardView | null;
  breaking: readonly StoryCardView[];
  dispatches: readonly StoryCardView[];
  sections: readonly Readonly<{
    key: (typeof DOMAIN_SECTIONS)[number]["key"];
    label: string;
    stories: readonly StoryCardView[];
  }>[];
  curiosity: StoryCardView | null;
  sourceSystems: readonly SourceStatusView[];
  unavailable: boolean;
}>;

export type EvidenceView = Readonly<{
  publisher: string;
  citation: string | null;
  canonicalUrl: string | null;
  sourceType: "official" | "journalism" | "research" | "dataset";
  publishedAt: string | null;
  retrievedAt: string;
  note: string | null;
}>;

export type ClaimView = Readonly<{
  kind: ClaimKind;
  text: string;
  numericValue: string | null;
  numericUnit: string | null;
  asOf: string | null;
  evidence: readonly EvidenceView[];
}>;

export type ImageProvenanceView = Readonly<{
  altText: string;
  source: string;
  sourceUrl: string | null;
  rightsBasis: string;
  rightsStatus: "approved";
  usageStatus: "approved";
  dlpStatus: "passed";
  sanitizationStatus: "passed";
  perceptualDedupStatus: "unique" | "intentional-reuse";
  createdAt: string;
}>;

export type StoryTimelineEvent = Readonly<{
  kind: "publication" | "amendment" | "quarantine" | "restoration";
  label: string;
  occurredAt: string;
  version: number;
}>;

export type StoryDetailView = Readonly<{
  story: StoryCardView;
  language: string;
  section: EditionPlacementV1["section"];
  lifecycleState: StoryVersionV1["lifecycle_state"];
  firstSeenAt: string;
  eventOccurredAt: string | null;
  updatedAt: string;
  verifiedAt: string | null;
  contributors: readonly string[];
  claims: readonly ClaimView[];
  currentVisibility: "Visible now";
  imageProvenance: ImageProvenanceView | null;
  timeline: readonly StoryTimelineEvent[];
}>;

type SourceRow = Readonly<{
  display_name: string;
  health: SourceStatusView["health"];
  verified_at: string | null;
}>;

type ClaimRow = Readonly<{
  claim_id: string;
  claim_kind: ClaimKind;
  normalized_text: string;
  numeric_value: string | null;
  numeric_unit: string | null;
  as_of: string | null;
}>;

type EvidenceRow = Readonly<{
  claim_id: string;
  publisher: string;
  document_citation: string | null;
  canonical_url: string | null;
  source_type: EvidenceView["sourceType"];
  published_at: string | null;
  retrieved_at: string;
  evidence_note: string | null;
}>;

type AssetRow = Readonly<{
  alt_text: string;
  source: string;
  source_url: string | null;
  rights_basis: string;
  usage_status: string;
  dlp_status: string;
  sanitization_status: string;
  perceptual_dedup_status: string;
  created_at: string;
  status: string;
  rights_status: string;
}>;

export async function requireMagazineViewer(): Promise<Viewer | null> {
  try {
    const runtime = getMagazineBindings();
    const roleAllowlist = parseRoleAllowlist(runtime.ROLE_ALLOWLIST_JSON);
    const viewer = await requireViewer(await headers(), {
      actorKeySecret: runtime.ACTOR_KEY_SECRET ?? "",
      roleAllowlist,
    });
    return authorize(viewer, "magazine:read", roleAllowlist).allowed
      ? viewer
      : null;
  } catch {
    return null;
  }
}

function dbBinding(): D1DatabaseLike | null {
  return getMagazineBindings().DB ?? null;
}

function normalizeEdition(edition: PublishedEdition): EditionView {
  return {
    date: edition.edition_date,
    revision: edition.edition_revision,
    kind: edition.edition_kind,
    coverageState: edition.coverage_state,
    verifiedAt: edition.verified_at,
    publishedAt: edition.published_at,
    coverageGaps: edition.coverage_gaps,
    readerNotices: edition.reader_notices,
  };
}

function normalizeStory(
  story: PublishedStory,
  asset: ImageProvenanceView | null,
): StoryCardView {
  return {
    slug: story.slug,
    domain: story.domain,
    severity: story.severity,
    title: story.title,
    deck: story.deck,
    summary: story.summary,
    whyItMatters: story.why_it_matters,
    curiosityText: story.curiosity_text,
    coverageState: story.coverage_state,
    confidence: story.confidence,
    publishedAt: story.published_at,
    imageAlt: asset?.altText ?? `Editorial visual context for ${story.title}`,
  };
}

async function readSourceStatus(
  db: D1DatabaseLike,
): Promise<readonly SourceStatusView[]> {
  const result = await db
    .prepare(
      `/* magazine:source-status */
       SELECT system.display_name, system.health,
              (SELECT run.verified_at FROM collector_runs run
               WHERE run.system_id = system.system_id
               ORDER BY run.verified_at DESC LIMIT 1) AS verified_at
       FROM source_systems system
       ORDER BY CASE system.readiness WHEN 'required' THEN 0 ELSE 1 END,
                system.display_name`,
    )
    .all<SourceRow>();
  return (result.results ?? []).map((row) => ({
    name: row.display_name,
    health: row.health,
    verifiedAt: row.verified_at,
  }));
}

async function readApprovedAsset(
  db: D1DatabaseLike,
  storyId: string,
  version: number,
): Promise<ImageProvenanceView | null> {
  const result = await db
    .prepare(
      `/* magazine:story-assets */
       SELECT source.alt_text, source.source, source.source_url,
              source.rights_basis, source.usage_status, source.dlp_status,
              source.sanitization_status, source.perceptual_dedup_status,
              source.created_at,
              COALESCE((SELECT status.status
                FROM asset_status_events status
                WHERE status.asset_id = source.asset_id
                ORDER BY status.status_seq DESC LIMIT 1), source.status) AS status,
              COALESCE((SELECT rights.rights_status
                FROM asset_status_events rights
                WHERE rights.asset_id = source.asset_id
                ORDER BY rights.status_seq DESC LIMIT 1), source.rights_status) AS rights_status
       FROM story_asset_references reference
       JOIN assets asset ON asset.sha256 = reference.asset_sha256
       JOIN asset_sources source ON source.canonical_sha256 = asset.sha256
       WHERE reference.story_id = ? AND reference.version = ?
         AND reference.publication_state = 'published'
       ORDER BY source.created_at DESC`,
    )
    .bind(storyId, version)
    .all<AssetRow>();
  const safe = (result.results ?? []).find((asset) => isAssetEligible(asset));
  return safe === undefined
    ? null
    : {
        altText: safe.alt_text,
        source: safe.source,
        sourceUrl: safe.source_url,
        rightsBasis: safe.rights_basis,
        rightsStatus: "approved",
        usageStatus: "approved",
        dlpStatus: "passed",
        sanitizationStatus: "passed",
        perceptualDedupStatus: safe.perceptual_dedup_status as
          | "unique"
          | "intentional-reuse",
        createdAt: safe.created_at,
      };
}

async function cardsForStories(
  db: D1DatabaseLike,
  stories: readonly PublishedStory[],
): Promise<readonly StoryCardView[]> {
  return Promise.all(
    stories.map(async (story) =>
      normalizeStory(
        story,
        await readApprovedAsset(db, story.story_id, story.version),
      ),
    ),
  );
}

async function composeFrontPage(
  db: D1DatabaseLike,
  edition: PublishedEdition | null,
  includeBreaking: boolean,
): Promise<FrontPageView> {
  const sourceSystems = await readSourceStatus(db);
  if (edition === null) return emptyFrontPage(sourceSystems, false);

  const sectionOrder = new Map<string, number>(
    DOMAIN_SECTIONS.map((section, index) => [section.key, index]),
  );
  const orderedEntries = [...edition.entries].sort(
    (left, right) =>
      left.order - right.order ||
      (sectionOrder.get(left.section) ?? DOMAIN_SECTIONS.length) -
        (sectionOrder.get(right.section) ?? DOMAIN_SECTIONS.length),
  );
  const cards = await cardsForStories(
    db,
    orderedEntries.map((entry) => entry.story),
  );
  const entriesWithCards = orderedEntries.map((entry, index) => ({
    entry,
    card: cards[index],
  }));
  const hero = entriesWithCards.find(({ entry }) => entry.lead)?.card ?? null;
  const nonHero = entriesWithCards.filter(({ entry }) => !entry.lead);
  const repository = createPublicationRepository(db);
  const breaking = includeBreaking
    ? await cardsForStories(db, await repository.getActiveBreaking())
    : [];
  return {
    edition: normalizeEdition(edition),
    hero,
    breaking,
    dispatches: nonHero.slice(0, 4).map(({ card }) => card),
    sections: DOMAIN_SECTIONS.map((section) => ({
      ...section,
      stories: nonHero
        .filter(({ entry }) => entry.section === section.key)
        .map(({ card }) => card),
    })),
    curiosity: cards.find((story) => story.curiosityText?.trim()) ?? null,
    sourceSystems,
    unavailable: false,
  };
}

function emptyFrontPage(
  sourceSystems: readonly SourceStatusView[],
  unavailable: boolean,
): FrontPageView {
  return {
    edition: null,
    hero: null,
    breaking: [],
    dispatches: [],
    sections: DOMAIN_SECTIONS.map((section) => ({ ...section, stories: [] })),
    curiosity: null,
    sourceSystems,
    unavailable,
  };
}

export async function readCurrentFrontPage(): Promise<FrontPageView> {
  const db = dbBinding();
  if (db === null) return emptyFrontPage([], true);
  try {
    const edition = await createPublicationRepository(db).getCurrentEdition();
    return composeFrontPage(db, edition, true);
  } catch {
    return emptyFrontPage([], true);
  }
}

function parseEditionKey(
  value: string,
): { date: string; revision: number } | null {
  const match = /^(\d{4}-\d{2}-\d{2})-r([1-9]\d*)$/.exec(value);
  return match === null
    ? null
    : { date: match[1], revision: Number.parseInt(match[2], 10) };
}

export async function readArchivedEdition(
  editionKey: string,
): Promise<FrontPageView | null> {
  const parsed = parseEditionKey(editionKey);
  const db = dbBinding();
  if (parsed === null || db === null) return null;
  try {
    const pointer = await db
      .prepare(
        `/* magazine:edition-id-by-key */
         SELECT edition_id FROM editions
         WHERE edition_date = ? AND edition_revision = ?
           AND publication_state = 'published'`,
      )
      .bind(parsed.date, parsed.revision)
      .first<{ edition_id: string }>();
    if (pointer === null) return null;
    const edition = await createPublicationRepository(db).getPublishedEdition(
      pointer.edition_id,
    );
    return edition === null ? null : composeFrontPage(db, edition, false);
  } catch {
    return null;
  }
}

function httpsUrlOrNull(value: string | null): string | null {
  if (value === null) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password
      ? parsed.href
      : null;
  } catch {
    return null;
  }
}

async function readStorySectionAndVerification(
  db: D1DatabaseLike,
  storyId: string,
  version: number,
  fallback: StoryVersionV1["domain"],
): Promise<{
  section: EditionPlacementV1["section"];
  verifiedAt: string | null;
}> {
  const row = await db
    .prepare(
      `/* magazine:story-publication-metadata */
       SELECT entry.section, edition.verified_at
       FROM edition_entries entry
       JOIN editions edition ON edition.edition_id = entry.edition_id
       WHERE entry.story_id = ? AND entry.version = ?
         AND entry.publication_state = 'published'
         AND edition.publication_state = 'published'
       ORDER BY edition.edition_revision DESC LIMIT 1`,
    )
    .bind(storyId, version)
    .first<{
      section: EditionPlacementV1["section"];
      verified_at: string;
    }>();
  return {
    section: row?.section ?? fallback,
    verifiedAt: row?.verified_at ?? null,
  };
}

async function readTimeline(
  db: D1DatabaseLike,
  story: PublishedStory,
): Promise<readonly StoryTimelineEvent[]> {
  const [historyResult, visibilityResult] = await Promise.all([
    db
      .prepare(
        `/* magazine:story-history */
         SELECT version, lifecycle_state, publication_state, published_at
         FROM story_versions
         WHERE story_id = ? AND publication_state IN ('published', 'superseded')
         ORDER BY version`,
      )
      .bind(story.story_id)
      .all<{
        version: number;
        lifecycle_state: StoryVersionV1["lifecycle_state"];
        publication_state: "published" | "superseded";
        published_at: string | null;
      }>(),
    db
      .prepare(
        `/* magazine:story-visibility-history */
         SELECT story_version, desired_quarantined, created_at
         FROM story_visibility_events
         WHERE story_id = ?
         ORDER BY visibility_seq`,
      )
      .bind(story.story_id)
      .all<{
        story_version: number;
        desired_quarantined: number;
        created_at: string;
      }>(),
  ]);

  const versions = historyResult.results ?? [];
  const timeline: StoryTimelineEvent[] = versions.flatMap((item) => {
    if (item.published_at === null) return [];
    const stateLabel =
      item.publication_state === "superseded" ? " — currently superseded" : "";
    return [
      {
        kind: item.lifecycle_state === "amended" ? "amendment" : "publication",
        label: `Revision published — lifecycle ${item.lifecycle_state}${stateLabel}`,
        occurredAt: item.published_at,
        version: item.version,
      },
    ];
  });
  for (const event of visibilityResult.results ?? []) {
    timeline.push({
      kind: event.desired_quarantined === 1 ? "quarantine" : "restoration",
      label: event.desired_quarantined === 1 ? "Quarantined" : "Restored",
      occurredAt: event.created_at,
      version: event.story_version,
    });
  }
  return timeline.sort(
    (left, right) => Date.parse(left.occurredAt) - Date.parse(right.occurredAt),
  );
}

export async function readStoryDetail(
  slug: string,
): Promise<StoryDetailView | null> {
  const db = dbBinding();
  if (db === null) return null;
  try {
    const row = await createPublicationRepository(db).getCurrentStory(slug);
    if (row === null) return null;

    const [contributorsResult, claimsResult, evidenceResult, asset, metadata] =
      await Promise.all([
        db
          .prepare(
            `/* magazine:story-contributors */
             SELECT DISTINCT system.display_name
             FROM story_versions version,
                  json_each(version.contributing_system_ids_json) contributor
             JOIN source_systems system ON system.system_id = contributor.value
             WHERE version.story_id = ? AND version.version = ?
             ORDER BY system.display_name`,
          )
          .bind(row.story_id, row.version)
          .all<{ display_name: string }>(),
        db
          .prepare(
            `/* magazine:story-claims */
             SELECT claim_id, claim_kind, normalized_text, numeric_value,
                    numeric_unit, as_of
             FROM story_claims
             WHERE story_id = ? AND version = ?
               AND publication_state = 'published'
             ORDER BY CASE claim_kind WHEN 'fact' THEN 0 WHEN 'numeric' THEN 1 ELSE 2 END,
                      claim_id`,
          )
          .bind(row.story_id, row.version)
          .all<ClaimRow>(),
        db
          .prepare(
            `/* magazine:story-evidence */
             SELECT link.claim_id, evidence.publisher,
                    evidence.document_citation, evidence.canonical_url,
                    evidence.source_type, evidence.published_at,
                    evidence.retrieved_at, evidence.evidence_note
             FROM story_evidence link
             JOIN evidence_refs evidence
               ON evidence.evidence_id = link.evidence_id
             WHERE link.story_id = ? AND link.version = ?
               AND link.publication_state = 'published'
             ORDER BY link.claim_id, evidence.publisher`,
          )
          .bind(row.story_id, row.version)
          .all<EvidenceRow>(),
        readApprovedAsset(db, row.story_id, row.version),
        readStorySectionAndVerification(
          db,
          row.story_id,
          row.version,
          row.domain,
        ),
      ]);
    const evidence = evidenceResult.results ?? [];
    const claims = (claimsResult.results ?? []).map<ClaimView>((claim) => ({
      kind: claim.claim_kind,
      text: claim.normalized_text,
      numericValue: claim.numeric_value,
      numericUnit: claim.numeric_unit,
      asOf: claim.as_of,
      evidence: evidence
        .filter((item) => item.claim_id === claim.claim_id)
        .map((item) => ({
          publisher: item.publisher,
          citation: item.document_citation,
          canonicalUrl: httpsUrlOrNull(item.canonical_url),
          sourceType: item.source_type,
          publishedAt: item.published_at,
          retrievedAt: item.retrieved_at,
          note: item.evidence_note,
        })),
    }));
    return {
      story: normalizeStory(row, asset),
      language: row.language,
      section: metadata.section,
      lifecycleState: row.lifecycle_state,
      firstSeenAt: row.first_seen_at,
      eventOccurredAt: row.event_occurred_at,
      updatedAt: row.updated_at,
      verifiedAt: metadata.verifiedAt,
      contributors: (contributorsResult.results ?? []).map(
        (item) => item.display_name,
      ),
      claims,
      currentVisibility: "Visible now",
      imageProvenance: asset,
      timeline: await readTimeline(db, row),
    };
  } catch {
    return null;
  }
}
