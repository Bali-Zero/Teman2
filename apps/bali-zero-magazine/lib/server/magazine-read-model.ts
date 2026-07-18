import { headers } from "next/headers";

import type { RoleAllowlist, Viewer } from "./authorization";
import { authorize } from "./authorization";
import { requireViewer } from "./identity";
import type { D1DatabaseLike } from "./publication-repository";
import { getMagazineBindings } from "./runtime-bindings";

export const DOMAIN_SECTIONS = [
  { key: "immigration", label: "Immigration" },
  { key: "company-investment", label: "Company & Investment" },
  { key: "tax", label: "Tax" },
  { key: "property", label: "Property" },
  { key: "regulation-compliance", label: "Regulation & Compliance" },
] as const;

export type StoryCardView = Readonly<{
  slug: string;
  domain: string;
  severity: string;
  title: string;
  deck: string;
  summary: string;
  whyItMatters: string;
  curiosityText: string | null;
  coverageState: string;
  confidence: string;
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
  kind: "standard" | "quiet";
  coverageState: "complete" | "partial";
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
  sourceType: string;
  publishedAt: string | null;
  retrievedAt: string;
  note: string | null;
}>;

export type ClaimView = Readonly<{
  kind: "fact" | "numeric" | "analysis";
  text: string;
  numericValue: string | null;
  numericUnit: string | null;
  asOf: string | null;
  evidence: readonly EvidenceView[];
}>;

export type StoryDetailView = Readonly<{
  story: StoryCardView;
  language: string;
  lifecycleState: string;
  firstSeenAt: string;
  updatedAt: string;
  contributors: readonly string[];
  claims: readonly ClaimView[];
  currentVisibility: "Visible now";
  hasSupersededHistory: boolean;
  history: readonly Readonly<{
    version: number;
    state: string;
    publishedAt: string | null;
  }>[];
}>;

type EditionRow = Readonly<{
  edition_id: string;
  edition_date: string;
  edition_revision: number;
  edition_kind: string;
  coverage_state: string;
  verified_at: string;
  published_at: string;
  coverage_gaps_json: string;
  reader_notices_json: string;
}>;

type StoryRow = Readonly<{
  story_id: string;
  version: number;
  slug: string;
  language?: string;
  domain: string;
  section?: string;
  editorial_order?: number;
  severity: string;
  lifecycle_state: string;
  title: string;
  deck: string;
  summary: string;
  why_it_matters: string;
  curiosity_text: string | null;
  coverage_state: string;
  confidence: string;
  first_seen_at?: string;
  updated_at?: string;
  published_at: string;
  desired_quarantined?: number | boolean | null;
  media_alt_text?: string | null;
}>;

type SourceRow = Readonly<{
  display_name: string;
  health: SourceStatusView["health"];
  verified_at: string | null;
}>;

type ClaimRow = Readonly<{
  claim_id: string;
  claim_kind: ClaimView["kind"];
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
  source_type: string;
  published_at: string | null;
  retrieved_at: string;
  evidence_note: string | null;
}>;

function parseRoleAllowlist(raw: string | undefined): RoleAllowlist {
  if (raw === undefined) throw new TypeError("role allowlist is required");
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null) {
    throw new TypeError("role allowlist is invalid");
  }
  const candidate = parsed as Partial<RoleAllowlist>;
  return {
    version: candidate.version ?? "",
    analysts: candidate.analysts ?? [],
    operators: candidate.operators ?? [],
  };
}

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

function stringArray(raw: string): readonly string[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function normalizeEdition(row: EditionRow): EditionView {
  return {
    date: row.edition_date,
    revision: row.edition_revision,
    kind: row.edition_kind === "quiet" ? "quiet" : "standard",
    coverageState: row.coverage_state === "partial" ? "partial" : "complete",
    verifiedAt: row.verified_at,
    publishedAt: row.published_at,
    coverageGaps: stringArray(row.coverage_gaps_json),
    readerNotices: stringArray(row.reader_notices_json),
  };
}

function normalizeStory(row: StoryRow): StoryCardView {
  return {
    slug: row.slug,
    domain: row.domain,
    severity: row.severity,
    title: row.title,
    deck: row.deck,
    summary: row.summary,
    whyItMatters: row.why_it_matters,
    curiosityText: row.curiosity_text,
    coverageState: row.coverage_state,
    confidence: row.confidence,
    publishedAt: row.published_at,
    imageAlt:
      row.media_alt_text?.trim() || `Editorial visual context for ${row.title}`,
  };
}

function visibleRows(rows: readonly StoryRow[]): readonly StoryRow[] {
  return rows.filter(
    (row) => row.desired_quarantined !== 1 && row.desired_quarantined !== true,
  );
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

async function readEditionStories(
  db: D1DatabaseLike,
  editionId: string,
): Promise<readonly StoryRow[]> {
  const result = await db
    .prepare(
      `/* magazine:edition-stories */
       SELECT story.story_id, version.version, story.slug, version.language,
              version.domain, entry.section,
              entry.editorial_order, version.severity,
              version.lifecycle_state, version.title, version.deck,
              version.summary, version.why_it_matters,
              version.curiosity_text, version.coverage_state,
              version.confidence, version.first_seen_at, version.updated_at,
              version.published_at,
              COALESCE((SELECT visibility.desired_quarantined
                FROM story_visibility_events visibility
                WHERE visibility.story_id = story.story_id
                ORDER BY visibility.visibility_seq DESC LIMIT 1), 0)
                AS desired_quarantined,
              (SELECT asset.alt_text
                FROM story_asset_references reference
                JOIN assets asset ON asset.sha256 = reference.asset_sha256
                WHERE reference.story_id = story.story_id
                  AND reference.version = version.version
                  AND reference.publication_state = 'published'
                  AND COALESCE((SELECT status.status
                    FROM asset_status_events status
                    WHERE status.asset_id = asset.asset_id
                    ORDER BY status.status_seq DESC LIMIT 1), asset.status) = 'verified'
                  AND COALESCE((SELECT rights.rights_status
                    FROM asset_status_events rights
                    WHERE rights.asset_id = asset.asset_id
                    ORDER BY rights.status_seq DESC LIMIT 1), asset.rights_status) = 'approved'
                LIMIT 1) AS media_alt_text
       FROM edition_entries entry
       JOIN stories story ON story.story_id = entry.story_id
       JOIN story_versions version
         ON version.story_id = entry.story_id AND version.version = entry.version
       WHERE entry.edition_id = ?
         AND entry.publication_state = 'published'
         AND version.publication_state = 'published'
       ORDER BY entry.editorial_order`,
    )
    .bind(editionId)
    .all<StoryRow>();
  return visibleRows(result.results ?? []);
}

async function readBreaking(db: D1DatabaseLike): Promise<readonly StoryRow[]> {
  const result = await db
    .prepare(
      `/* magazine:active-breaking */
       SELECT story.story_id, version.version, story.slug, version.language,
              version.domain, 'breaking' AS section, 0 AS editorial_order,
              version.severity, version.lifecycle_state, version.title,
              version.deck, version.summary, version.why_it_matters,
              version.curiosity_text, version.coverage_state,
              version.confidence, version.first_seen_at, version.updated_at,
              version.published_at,
              COALESCE((SELECT visibility.desired_quarantined
                FROM story_visibility_events visibility
                WHERE visibility.story_id = story.story_id
                ORDER BY visibility.visibility_seq DESC LIMIT 1), 0)
                AS desired_quarantined,
              NULL AS media_alt_text
       FROM breaking_pointer pointer
       JOIN breaking_entries entry
         ON entry.breaking_revision = pointer.active_revision
       JOIN stories story ON story.story_id = entry.story_id
       JOIN story_versions version
         ON version.story_id = entry.story_id AND version.version = entry.version
       WHERE pointer.singleton_id = 1
         AND entry.publication_state = 'published'
         AND version.publication_state = 'published'
         AND version.severity IN ('high', 'critical')
       ORDER BY CASE version.severity WHEN 'critical' THEN 0 ELSE 1 END,
                version.published_at DESC`,
    )
    .all<StoryRow>();
  return visibleRows(result.results ?? []);
}

async function composeFrontPage(
  db: D1DatabaseLike,
  editionRow: EditionRow | null,
): Promise<FrontPageView> {
  const sourceSystems = await readSourceStatus(db);
  if (editionRow === null) {
    return emptyFrontPage(sourceSystems, false);
  }
  const rows = await readEditionStories(db, editionRow.edition_id);
  const cards = rows.map(normalizeStory);
  const heroIndex = rows.findIndex((row) => row.section === "hero");
  const hero = cards[heroIndex >= 0 ? heroIndex : 0] ?? null;
  const nonHero = cards.filter((story) => story.slug !== hero?.slug);
  const breaking = (await readBreaking(db)).map(normalizeStory);
  return {
    edition: normalizeEdition(editionRow),
    hero,
    breaking,
    dispatches: nonHero.slice(0, 4),
    sections: DOMAIN_SECTIONS.map((section) => ({
      ...section,
      stories: nonHero.filter((story) => story.domain === section.key),
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
    const edition = await db
      .prepare(
        `/* magazine:current-edition */
         SELECT edition.edition_id, edition.edition_date,
                edition.edition_revision, edition.edition_kind,
                edition.coverage_state, edition.verified_at,
                edition.published_at, edition.coverage_gaps_json,
                edition.reader_notices_json
         FROM edition_pointer pointer
         JOIN editions edition
           ON edition.edition_id = pointer.current_edition_id
         WHERE pointer.singleton_id = 1
           AND edition.publication_state = 'published'`,
      )
      .first<EditionRow>();
    return composeFrontPage(db, edition);
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
    const edition = await db
      .prepare(
        `/* magazine:edition-by-id */
         SELECT edition_id, edition_date, edition_revision, edition_kind,
                coverage_state, verified_at, published_at,
                coverage_gaps_json, reader_notices_json
         FROM editions
         WHERE edition_date = ? AND edition_revision = ?
           AND publication_state = 'published'`,
      )
      .bind(parsed.date, parsed.revision)
      .first<EditionRow>();
    return edition === null ? null : composeFrontPage(db, edition);
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

export async function readStoryDetail(
  slug: string,
): Promise<StoryDetailView | null> {
  const db = dbBinding();
  if (db === null) return null;
  try {
    const row = await db
      .prepare(
        `/* magazine:story-by-slug */
         SELECT story.story_id, version.version, story.slug, version.language,
                version.domain, version.severity, version.lifecycle_state,
                version.title, version.deck, version.summary,
                version.why_it_matters, version.curiosity_text,
                version.coverage_state, version.confidence,
                version.first_seen_at, version.updated_at,
                version.published_at,
                COALESCE((SELECT visibility.desired_quarantined
                  FROM story_visibility_events visibility
                  WHERE visibility.story_id = story.story_id
                  ORDER BY visibility.visibility_seq DESC LIMIT 1), 0)
                  AS desired_quarantined,
                NULL AS media_alt_text
         FROM stories story
         JOIN story_versions version
           ON version.story_id = story.story_id
          AND version.version = story.current_version
         WHERE story.slug = ? AND version.publication_state = 'published'`,
      )
      .bind(slug)
      .first<StoryRow>();
    if (
      row === null ||
      row.desired_quarantined === 1 ||
      row.desired_quarantined === true
    ) {
      return null;
    }

    const [
      contributorsResult,
      claimsResult,
      evidenceResult,
      historyResult,
      assetsResult,
    ] = await Promise.all([
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
      db
        .prepare(
          `/* magazine:story-history */
             SELECT version, lifecycle_state, published_at
             FROM story_versions
             WHERE story_id = ? AND publication_state IN ('published', 'superseded')
             ORDER BY version DESC`,
        )
        .bind(row.story_id)
        .all<{
          version: number;
          lifecycle_state: string;
          published_at: string | null;
        }>(),
      db
        .prepare(
          `/* magazine:story-assets */
             SELECT reference.asset_sha256, asset.alt_text,
                    COALESCE((SELECT status.status
                      FROM asset_status_events status
                      WHERE status.asset_id = asset.asset_id
                      ORDER BY status.status_seq DESC LIMIT 1), asset.status) AS status,
                    COALESCE((SELECT rights.rights_status
                      FROM asset_status_events rights
                      WHERE rights.asset_id = asset.asset_id
                      ORDER BY rights.status_seq DESC LIMIT 1), asset.rights_status) AS rights_status
             FROM story_asset_references reference
             JOIN assets asset ON asset.sha256 = reference.asset_sha256
             WHERE reference.story_id = ? AND reference.version = ?
               AND reference.publication_state = 'published'`,
        )
        .bind(row.story_id, row.version)
        .all<{
          asset_sha256: string;
          alt_text: string;
          status: string;
          rights_status: string;
        }>(),
    ]);

    const safeAsset = (assetsResult.results ?? []).find(
      (asset) =>
        asset.status === "verified" && asset.rights_status === "approved",
    );
    const story = normalizeStory({
      ...row,
      media_alt_text: safeAsset?.alt_text ?? row.media_alt_text,
    });
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
    const history = (historyResult.results ?? []).map((item) => ({
      version: item.version,
      state: item.lifecycle_state,
      publishedAt: item.published_at,
    }));
    return {
      story,
      language: row.language ?? "en",
      lifecycleState: row.lifecycle_state,
      firstSeenAt: row.first_seen_at ?? row.published_at,
      updatedAt: row.updated_at ?? row.published_at,
      contributors: (contributorsResult.results ?? []).map(
        (item) => item.display_name,
      ),
      claims,
      currentVisibility: "Visible now",
      hasSupersededHistory: history.some(
        (item) => item.state === "superseded" || item.version < row.version,
      ),
      history,
    };
  } catch {
    return null;
  }
}
