import {
  createPublicationRepository,
  type D1DatabaseLike,
  type D1PreparedStatementLike,
  type PublishedStory,
} from "../../../../bali-zero-magazine/lib/server/publication-repository";
import {
  isAssetEligible,
  type AssetEligibilityState,
} from "../../../../bali-zero-magazine/lib/server/asset-eligibility";

export const MAGAZINE_ORIGIN = "https://bali-zero-magazine.antonellosiano.chatgpt.site";
export const FIXTURE_ARTWORK = "/assets/editorial-fixture.svg";
export type MagazinePublicationOptions = Readonly<{
  provenance: "fixture" | "publisher";
  approvedEvidenceOrigins?: readonly string[];
}>;
export type MagazineArticle = Readonly<{
  slug: string;
  title: string;
  category: PublishedStory["domain"];
  publicationState: "published";
  visibility: "visible";
  publishedAt: string;
  updatedAt: string;
  revision: number;
  lifecycleState: PublishedStory["lifecycle_state"];
  canonicalUrl: string;
  summary: string;
  whyItMatters: string;
  evidence: readonly Readonly<{ publisher: string; citation: string | null; url: string | null }>[];
  revisions: readonly Readonly<{ version: number; publishedAt: string }>[];
  image: Readonly<{ src: string; alt: string }> | null;
}>;
export type MagazinePublicationEnvelope = Readonly<{
  version: 2;
  publisher: "bali-zero-magazine";
  status: "ready" | "empty" | "withdrawn" | "unpublished" | "unavailable" | "malformed";
  articles: readonly MagazineArticle[];
  provenance: MagazinePublicationOptions["provenance"];
}>;

class MalformedPublication extends Error {}

function text(value: unknown, max = 2000): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) {
    throw new MalformedPublication();
  }
  return value;
}

function timestamp(value: unknown): string {
  const result = text(value, 40);
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{3})?Z$/.test(result) ||
      !Number.isFinite(Date.parse(result)) ||
      new Date(result).toISOString().slice(0, 19) !== result.slice(0, 19)) {
    throw new MalformedPublication();
  }
  return result;
}

function positiveInteger(value: unknown): number {
  if (!Number.isSafeInteger(value) || (value as number) < 1) throw new MalformedPublication();
  return value as number;
}

// The legacy repository also owns writes. This capability wrapper makes this
// consumer SELECT-only and refuses unsuccessful/missing D1 result envelopes.
function readOnlyDatabase(database: D1DatabaseLike): D1DatabaseLike {
  function statement(source: D1PreparedStatementLike): D1PreparedStatementLike {
    return {
      bind: (...values) => statement(source.bind(...values)),
      run: async () => { throw new Error("Read-only publication consumer"); },
      first: async <T,>() => source.first<T>(),
      all: async <T,>() => {
        const result = await source.all<T>();
        if (result.success === false || !Array.isArray(result.results)) throw new Error("Publication read unavailable");
        return result;
      },
    };
  }
  return {
    prepare: (sql) => {
      if (!/^\s*(?:\/\*[\s\S]*?\*\/\s*)?SELECT\b/i.test(sql)) throw new Error("Read-only publication consumer");
      return statement(database.prepare(sql));
    },
    batch: async () => { throw new Error("Read-only publication consumer"); },
  };
}

type Candidate = Readonly<{
  slug: string;
  entry_state: string;
  current_state: string | null;
  current_version: number;
  quarantined: number;
}>;

async function readImage(
  db: D1DatabaseLike,
  storyId: string,
  version: number,
  provenance: MagazinePublicationOptions["provenance"],
): Promise<MagazineArticle["image"]> {
  const assets = await db.prepare(`/* website:public-assets */
    SELECT source.alt_text, source.source, source.rights_basis, source.usage_status,
      source.dlp_status, source.sanitization_status, source.perceptual_dedup_status,
      COALESCE((SELECT event.status FROM asset_status_events event
        WHERE event.asset_id = source.asset_id ORDER BY event.status_seq DESC LIMIT 1), source.status) AS status,
      COALESCE((SELECT event.rights_status FROM asset_status_events event
        WHERE event.asset_id = source.asset_id ORDER BY event.status_seq DESC LIMIT 1), source.rights_status) AS rights_status
    FROM story_asset_references reference
    JOIN assets asset ON asset.sha256 = reference.asset_sha256
    JOIN asset_sources source ON source.canonical_sha256 = asset.sha256
    WHERE reference.story_id = ? AND reference.version = ? AND reference.publication_state = 'published'
    ORDER BY source.created_at DESC, source.asset_id`)
    .bind(storyId, version).all<AssetEligibilityState>();
  const eligibleAsset = assets.results!.find((asset) => isAssetEligible(asset));
  // The legacy public route is /api/story-media/{slug}, never /api/media/{hash}.
  // Its CORP same-origin response is not a verified delivery boundary for this
  // separate website. Publisher media stays absent pending that release decision.
  return provenance === "fixture" && eligibleAsset?.rights_basis === "internal-owned"
    ? { src: FIXTURE_ARTWORK, alt: text(eligibleAsset.alt_text, 400) }
    : null;
}

async function articleFor(
  db: D1DatabaseLike,
  story: PublishedStory,
  options: MagazinePublicationOptions,
): Promise<MagazineArticle> {
  const slug = text(story.slug, 140);
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) throw new MalformedPublication();
  const revision = positiveInteger(story.version);
  const publishedAt = timestamp(story.published_at);
  const updatedAt = timestamp(story.updated_at);
  const categories = ["immigration", "company", "tax", "property", "compliance", "general"];
  const lifecycles = ["developing", "verified", "amended"];
  if (!categories.includes(story.domain) || !lifecycles.includes(story.lifecycle_state)) throw new MalformedPublication();

  const evidenceResult = await db.prepare(`/* website:public-evidence */
    SELECT DISTINCT evidence.publisher, evidence.document_citation, evidence.canonical_url
    FROM story_evidence link
    JOIN story_claims claim ON claim.story_id = link.story_id
      AND claim.version = link.version AND claim.claim_id = link.claim_id
      AND claim.publication_state = 'published'
    JOIN evidence_refs evidence ON evidence.evidence_id = link.evidence_id
    WHERE link.story_id = ? AND link.version = ? AND link.publication_state = 'published'
    ORDER BY evidence.publisher, evidence.canonical_url`)
    .bind(story.story_id, revision)
    .all<{ publisher: string; document_citation: string | null; canonical_url: string | null }>();
  const evidence = evidenceResult.results!.map((row) => {
    let url: string | null = null;
    if (row.canonical_url !== null) {
      let parsed: URL;
      try { parsed = new URL(row.canonical_url); } catch { throw new MalformedPublication(); }
      if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.search || parsed.hash ||
          !(options.approvedEvidenceOrigins ?? []).includes(parsed.origin)) throw new MalformedPublication();
      url = parsed.href;
    }
    const citation = row.document_citation === null ? null : text(row.document_citation, 500);
    if (url === null && citation === null) throw new MalformedPublication();
    return { publisher: text(row.publisher, 200), citation, url };
  });
  if (!evidence.length) throw new MalformedPublication();

  const history = await db.prepare(`/* website:public-revisions */
    SELECT version, published_at FROM story_versions
    WHERE story_id = ? AND version <= ? AND publication_state IN ('published', 'superseded')
    ORDER BY version`).bind(story.story_id, revision)
    .all<{ version: number; published_at: string | null }>();
  const revisions = history.results!.map((row) => ({
    version: positiveInteger(row.version), publishedAt: timestamp(row.published_at),
  }));
  if (!revisions.some((row) => row.version === revision && row.publishedAt === publishedAt)) throw new MalformedPublication();

  const image = await readImage(db, story.story_id, revision, options.provenance);
  return {
    slug, title: text(story.title, 240), category: story.domain,
    publicationState: "published", visibility: "visible", publishedAt, updatedAt,
    revision, lifecycleState: story.lifecycle_state,
    canonicalUrl: `${MAGAZINE_ORIGIN}/stories/${slug}`,
    summary: text(story.summary), whyItMatters: text(story.why_it_matters),
    evidence, revisions, image,
  };
}

/** Read existing publisher state without binding production or changing visibility. */
export async function readMagazinePublication(
  database: D1DatabaseLike,
  options: MagazinePublicationOptions,
): Promise<MagazinePublicationEnvelope> {
  const envelope = (status: MagazinePublicationEnvelope["status"], articles: readonly MagazineArticle[] = []): MagazinePublicationEnvelope => ({
    version: 2, publisher: "bali-zero-magazine", status, articles, provenance: options.provenance,
  });
  try {
    const db = readOnlyDatabase(database);
    const repository = createPublicationRepository(db);
    const edition = await repository.getCurrentEdition();
    if (edition === null) {
      const state = await db.prepare(`/* website:edition-absence */
        SELECT (SELECT count(*) FROM editions WHERE publication_state = 'published') AS published,
          (SELECT count(*) FROM editions WHERE publication_state IN ('building', 'failed')) +
          (SELECT count(*) FROM story_versions WHERE publication_state IN ('building', 'failed')) AS unpublished,
          (SELECT count(*) FROM edition_pointer WHERE current_edition_id IS NOT NULL) AS pointer`)
        .first<{ published: number; unpublished: number; pointer: number }>();
      if (!state) throw new MalformedPublication();
      if (state.published || state.pointer) return envelope("malformed");
      return envelope(state.unpublished ? "unpublished" : "empty");
    }
    timestamp(edition.published_at);
    // Edition entries pin historic versions. Read candidate identities separately
    // so a superseded pin cannot hide its current amendment or revive old text.
    const candidates = await db.prepare(`/* website:edition-current-candidates */
      SELECT story.slug, entry.publication_state AS entry_state,
        version.publication_state AS current_state, story.current_version,
        COALESCE((SELECT visibility.desired_quarantined FROM story_visibility_events visibility
          WHERE visibility.story_id = story.story_id ORDER BY visibility.visibility_seq DESC LIMIT 1), 0) AS quarantined
      FROM edition_entries entry
      JOIN stories story ON story.story_id = entry.story_id
      LEFT JOIN story_versions version ON version.story_id = story.story_id AND version.version = story.current_version
      WHERE entry.edition_id = ? ORDER BY entry.is_lead DESC, entry.editorial_order, entry.section`)
      .bind(edition.edition_id).all<Candidate>();
    const articles: MagazineArticle[] = [];
    let withdrawn = 0;
    let unpublished = 0;
    const seen = new Set<string>();
    for (const candidate of candidates.results!) {
      if (candidate.quarantined === 1) { withdrawn += 1; continue; }
      if (candidate.entry_state !== "published" || candidate.current_state !== "published") { unpublished += 1; continue; }
      if (seen.has(candidate.slug)) continue;
      seen.add(candidate.slug);
      const story = await repository.getCurrentStory(candidate.slug);
      if (story === null || story.version !== candidate.current_version) throw new Error("Publication changed during read");
      const article = await articleFor(db, story, options);
      const current = await repository.getCurrentStory(candidate.slug);
      if (current === null || current.version !== story.version) throw new Error("Publication changed during read");
      articles.push(article);
    }
    const finalEdition = await repository.getCurrentEdition();
    if (finalEdition?.edition_id !== edition.edition_id) throw new Error("Publication changed during read");
    // A later candidate's reads may observe an earlier candidate being withdrawn
    // or amended. Recheck the whole assembled set, not just each local read.
    // This detects observed changes; separate D1 reads are not a snapshot guarantee.
    const finalArticles: MagazineArticle[] = [];
    for (const article of articles) {
      const current = await repository.getCurrentStory(article.slug);
      if (current === null || current.version !== article.revision) throw new Error("Publication changed during read");
      const image = article.image === null ? null : await readImage(db, current.story_id, current.version, options.provenance);
      finalArticles.push({ ...article, image });
    }
    return envelope(finalArticles.length ? "ready" : withdrawn ? "withdrawn" : unpublished ? "unpublished" : "empty", finalArticles);
  } catch (error) {
    return envelope(error instanceof MalformedPublication ? "malformed" : "unavailable");
  }
}
