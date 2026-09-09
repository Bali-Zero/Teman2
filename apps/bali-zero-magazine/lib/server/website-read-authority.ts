import {
  WEBSITE_READ_CONTRACT, WEBSITE_READ_AUDIENCE, MAGAZINE_CANONICAL_ORIGIN,
  READ_PATH, MEDIA_PATH, MAX_READ_BYTES, isRecord, isDigest, isPublicArticle,
  isPublicDate, isPublicMedia, localOrigin, mediaPath, responseSignatureInput,
  type PublicArticle, type PublicFeed, type PublicMedia, type WebsiteRead,
} from "../contracts/website-read.ts";
import { assetEligibilitySql } from "./asset-eligibility.ts";
import { verifyMachineRequest, type MachineHmacKey, type MachineNonceStore } from "./hmac.ts";
import type { D1DatabaseLike } from "./publication-repository.ts";
import { sha256Hex, hmacSha256Hex, mediaSecurityHeaders } from "./security.ts";
import { verifiedObjectBytes, type ReadonlyMediaBucket } from "./verified-media-bytes.ts";

/**
 * Same schema/current-head/quarantine rules as getCurrentEdition/getCurrentStory,
 * consolidated into ONE D1 prepared SELECT. No D1 session or multi-call batch is
 * represented as a transaction. SQLite statement consistency is exercised by
 * the canonical-migration local fixture; live D1/runtime parity remains unproven.
 * Current-edition scope only: no independent breaking feed or historical fallback.
 */
export const WEBSITE_SNAPSHOT_SQL = `/* website:single-statement-snapshot */
WITH candidates AS (
  SELECT entry.story_id AS entry_story_id, entry.publication_state AS entry_state,
    story.slug, story.current_version, version.version AS actual_version,
    version.publication_state AS current_state, version.packet_id,
    version.title, version.domain, version.lifecycle_state, version.summary,
    version.why_it_matters, version.published_at, version.updated_at,
    COALESCE((SELECT visibility.desired_quarantined FROM story_visibility_events visibility
      WHERE visibility.story_id = entry.story_id ORDER BY visibility.visibility_seq DESC LIMIT 1), 0) AS quarantined,
    COALESCE((SELECT max(visibility.visibility_seq) FROM story_visibility_events visibility
      WHERE visibility.story_id = entry.story_id), 0) AS visibility_seq
  FROM edition_entries entry
  LEFT JOIN stories story ON story.story_id = entry.story_id
  LEFT JOIN story_versions version ON version.story_id = story.story_id AND version.version = story.current_version
  WHERE entry.edition_id = (SELECT current_edition_id FROM edition_pointer WHERE singleton_id = 1)
  ORDER BY entry.is_lead DESC, entry.editorial_order, entry.section, entry.story_id
)
SELECT json_object(
  'pointerCount', (SELECT count(*) FROM edition_pointer WHERE singleton_id = 1),
  'editionId', (SELECT current_edition_id FROM edition_pointer WHERE singleton_id = 1),
  'revision', (SELECT current_revision FROM edition_pointer WHERE singleton_id = 1),
  'editionRevision', (SELECT edition_revision FROM editions WHERE edition_id = (SELECT current_edition_id FROM edition_pointer WHERE singleton_id = 1)),
  'editionState', (SELECT publication_state FROM editions WHERE edition_id = (SELECT current_edition_id FROM edition_pointer WHERE singleton_id = 1)),
  'placementCount', (SELECT json_array_length(placements_json) FROM editions WHERE edition_id = (SELECT current_edition_id FROM edition_pointer WHERE singleton_id = 1)),
  'publishedAt', (SELECT published_at FROM editions WHERE edition_id = (SELECT current_edition_id FROM edition_pointer WHERE singleton_id = 1)),
  'publishedCount', (SELECT count(*) FROM editions WHERE publication_state = 'published'),
  'unpublishedCount', (SELECT count(*) FROM editions WHERE publication_state IN ('building', 'failed')) +
    (SELECT count(*) FROM story_versions WHERE publication_state IN ('building', 'failed')),
  'candidateCount', (SELECT count(*) FROM candidates),
  'candidates', json((SELECT json_group_array(json_object(
    'slug', c.slug, 'version', c.current_version, 'actualVersion', c.actual_version,
    'entryState', c.entry_state, 'currentState', c.current_state,
    'quarantined', c.quarantined, 'visibilitySeq', c.visibility_seq,
    'article', CASE WHEN c.quarantined = 0 AND c.entry_state = 'published' AND c.current_state = 'published' THEN json_object(
      'slug', c.slug, 'title', c.title, 'category', c.domain,
      'publicationState', 'published', 'visibility', 'visible',
      'publishedAt', c.published_at, 'updatedAt', c.updated_at,
      'revision', c.current_version, 'lifecycleState', c.lifecycle_state,
      'canonicalUrl', '${MAGAZINE_CANONICAL_ORIGIN}/stories/' || c.slug,
      'summary', c.summary, 'whyItMatters', c.why_it_matters, 'image', NULL,
      'evidence', json((SELECT json_group_array(json_object('publisher', e.publisher, 'citation', e.document_citation, 'url', e.canonical_url)) FROM (
        SELECT DISTINCT evidence.publisher, evidence.document_citation, evidence.canonical_url
        FROM story_evidence link JOIN story_claims claim
          ON claim.packet_id = link.packet_id AND claim.story_id = link.story_id AND claim.version = link.version AND claim.claim_id = link.claim_id
        JOIN evidence_refs evidence ON evidence.evidence_id = link.evidence_id
        WHERE link.packet_id = c.packet_id AND link.story_id = c.entry_story_id AND link.version = c.current_version
          AND link.publication_state = 'published' AND claim.publication_state = 'published'
        ORDER BY evidence.publisher, evidence.canonical_url, evidence.document_citation LIMIT 31
      ) e)),
      'revisions', json((SELECT json_group_array(json_object('version', h.version, 'publishedAt', h.published_at)) FROM (
        SELECT version, published_at FROM story_versions
        WHERE story_id = c.entry_story_id AND version <= c.current_version AND publication_state IN ('published', 'superseded')
        ORDER BY version LIMIT 101
      ) h))
    ) ELSE NULL END,
    'asset', json(CASE WHEN c.quarantined = 0 AND c.entry_state = 'published' AND c.current_state = 'published' THEN
      (SELECT json_object('key', a.r2_key, 'statusSeq', COALESCE((SELECT max(event.status_seq) FROM asset_status_events event WHERE event.asset_id = source.asset_id), 0),
        'public', json_object('slug', c.slug, 'version', c.current_version, 'sha256', a.sha256,
          'mimeType', a.mime_type, 'byteCount', a.byte_count, 'width', a.width, 'height', a.height, 'alt', source.alt_text))
      FROM story_asset_references reference JOIN assets a ON a.sha256 = reference.asset_sha256
      JOIN asset_sources source ON source.canonical_sha256 = a.sha256
      WHERE reference.packet_id = c.packet_id AND reference.story_id = c.entry_story_id AND reference.version = c.current_version
        AND reference.publication_state = 'published' AND ${assetEligibilitySql("source")}
      ORDER BY source.created_at DESC, a.sha256, source.asset_id LIMIT 1)
      ELSE NULL END)
  )) FROM (SELECT * FROM candidates LIMIT 101) c))
) AS snapshot`;

export type PublicReadApproval = Readonly<{
  approvedEvidenceOrigins: readonly string[];
  /** slug/version -> digest of exact reviewed PublicArticle (image is null). */
  articleDigests: Readonly<Record<string, string>>;
  /** slug/version -> digest of exact approved public media descriptor/bytes hash. */
  mediaDigests: Readonly<Record<string, string>>;
}>;

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (isRecord(value)) return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}
export function publicApprovalDigest(value: PublicArticle | PublicMedia): Promise<string> {
  return sha256Hex(new TextEncoder().encode(canonicalJson(value)));
}
class MalformedRead extends Error {}
class UnapprovedRead extends Error {}

function emptyFeed(status: PublicFeed["status"]): PublicFeed {
  return { version: 2, publisher: "bali-zero-magazine", status, articles: [], provenance: "fixture" };
}

export async function readWebsiteSnapshot(db: Pick<D1DatabaseLike, "prepare">, approval: PublicReadApproval): Promise<WebsiteRead> {
  const result = await db.prepare(WEBSITE_SNAPSHOT_SQL).first<{ snapshot: string }>();
  if (!result || typeof result.snapshot !== "string" || result.snapshot.length > MAX_READ_BYTES) throw new Error("Read unavailable");
  const raw: unknown = JSON.parse(result.snapshot);
  if (!isRecord(raw) || raw.pointerCount !== 1 || !Array.isArray(raw.candidates) ||
    !Number.isSafeInteger(raw.publishedCount) || (raw.publishedCount as number) < 0 ||
    !Number.isSafeInteger(raw.unpublishedCount) || (raw.unpublishedCount as number) < 0 ||
    !Number.isSafeInteger(raw.candidateCount) || raw.candidateCount !== raw.candidates.length || raw.candidates.length > 100) throw new MalformedRead();
  let feed: PublicFeed;
  const media: PublicMedia[] = [];
  if (raw.editionId === null) {
    if (raw.revision !== 0 || raw.publishedCount !== 0 || raw.candidates.length) throw new MalformedRead();
    feed = emptyFeed(raw.unpublishedCount ? "unpublished" : "empty");
  } else {
    if (raw.editionState !== "published" || !isPublicDate(raw.publishedAt) ||
      raw.placementCount !== raw.candidateCount ||
      !Number.isSafeInteger(raw.revision) || (raw.revision as number) < 1 || raw.revision !== raw.editionRevision) throw new MalformedRead();
    const articles: PublicArticle[] = [];
    const seen = new Set<string>();
    let withdrawn = 0, unpublished = 0;
    for (const candidate of raw.candidates) {
      if (!isRecord(candidate) || typeof candidate.slug !== "string" || candidate.version !== candidate.actualVersion || candidate.actualVersion === null ||
        ![0, 1].includes(candidate.quarantined as number) || !["building", "published", "failed"].includes(candidate.entryState as string) ||
        !["building", "published", "superseded", "failed"].includes(candidate.currentState as string)) throw new MalformedRead();
      if (seen.has(candidate.slug)) continue;
      seen.add(candidate.slug);
      if (candidate.quarantined === 1) { withdrawn++; continue; }
      if (candidate.currentState === "superseded") throw new MalformedRead();
      if (candidate.entryState !== "published" || candidate.currentState !== "published") { unpublished++; continue; }
      if (!isPublicArticle(candidate.article, approval.approvedEvidenceOrigins)) throw new MalformedRead();
      const article = candidate.article;
      const key = `${article.slug}/${article.revision}`;
      if (!isDigest(approval.articleDigests[key]) || await publicApprovalDigest(article) !== approval.articleDigests[key]) throw new UnapprovedRead();
      articles.push(article);
      if (candidate.asset !== null) {
        if (!isRecord(candidate.asset) || !isPublicMedia(candidate.asset.public) ||
          candidate.asset.key !== `assets/sha256/${candidate.asset.public.sha256}.png`) throw new MalformedRead();
        const asset = candidate.asset.public;
        if (asset.slug !== article.slug || asset.version !== article.revision) throw new MalformedRead();
        if (await publicApprovalDigest(asset) === approval.mediaDigests[key]) media.push(asset);
      }
    }
    feed = articles.length ? { ...emptyFeed("ready"), articles } : emptyFeed(withdrawn ? "withdrawn" : unpublished ? "unpublished" : "empty");
  }
  // Includes the authority head and visibility/status sequence counters: an
  // observed withdrawal/reinstate or edition change invalidates old media URLs.
  const snapshotId = await sha256Hex(new TextEncoder().encode(canonicalJson({ raw, feed, media })));
  return { contract: WEBSITE_READ_CONTRACT, snapshotId, canonicalAccess: "unverified", feed, media };
}

/** Ephemeral proof admission only. Never writes Magazine's ingest nonce table. */
function localNonceStore(now: () => number): MachineNonceStore {
  const used = new Map<string, number>();
  return { insertUnique: async (key, nonce, expiresAt) => {
    for (const [id, expiry] of used) if (expiry <= now()) used.delete(id);
    const id = `${key}/${nonce}`;
    if (used.has(id) || used.size >= 2048) return false;
    used.set(id, expiresAt);
    return true;
  } };
}

export function createLocalWebsiteReadAuthority(options: Readonly<{
  mode: "local-proof";
  origin: string;
  db: Pick<D1DatabaseLike, "prepare">;
  bucket: ReadonlyMediaBucket;
  key: MachineHmacKey;
  approval: () => PublicReadApproval;
  now?: () => number;
}>): (request: Request) => Promise<Response> {
  const origin = localOrigin(options.origin);
  if (options.mode !== "local-proof" || !/^[a-f0-9]{64}$/.test(options.key.secret)) throw new TypeError("Local proof configuration required");
  const now = options.now ?? Date.now;
  const nonceStore = localNonceStore(now);
  return async (request) => {
    const url = new URL(request.url);
    if (url.origin !== origin || request.method !== "GET") return new Response(null, { status: 404, headers: mediaSecurityHeaders() });
    let nonce: string;
    try {
      if (request.headers.has("transfer-encoding") ||
        (request.headers.has("content-length") && request.headers.get("content-length") !== "0")) throw new Error();
      const verified = await verifyMachineRequest(request, {
        audience: WEBSITE_READ_AUDIENCE, currentKey: options.key, nonceStore,
        maxBodyBytes: 1, maxClockSkewSeconds: 30, now,
      });
      if (verified.body.length !== 0) throw new Error();
      nonce = verified.nonce;
    } catch { return Response.json({ error: "unauthorized" }, { status: 401, headers: mediaSecurityHeaders() }); }
    const signed = async (body: Uint8Array, status: number, mime: string): Promise<Response> => {
      const headers = mediaSecurityHeaders({ "Content-Type": mime, "Content-Length": String(body.length) });
      headers.set("x-magazine-response-signature", await hmacSha256Hex(options.key.secret,
        responseSignatureInput(url.pathname + url.search, nonce, status, mime, await sha256Hex(body))));
      return new Response(Uint8Array.from(body).buffer, { status, headers });
    };
    const json = (value: unknown, status = 200) => signed(new TextEncoder().encode(JSON.stringify(value)), status, "application/json");
    try {
      if (url.pathname !== READ_PATH && !url.pathname.startsWith(`${MEDIA_PATH}/`)) return json({ error: "not_found" }, 404);
      if (url.pathname === READ_PATH && url.search) return json({ error: "not_found" }, 404);
      const snapshot = await readWebsiteSnapshot(options.db, options.approval());
      if (url.pathname === READ_PATH) return json(snapshot);
      const asset = snapshot.media.find((item) => mediaPath(MEDIA_PATH, snapshot.snapshotId, item) === url.pathname + url.search);
      if (!asset) return json({ error: "unavailable" }, 409);
      const bytes = await verifiedObjectBytes(options.bucket, `assets/sha256/${asset.sha256}.png`, asset);
      // Object storage awaits are outside SQLite. Re-read a NEW coherent state
      // after bytes resolve; never claim a DB+R2 distributed atomic snapshot.
      const after = await readWebsiteSnapshot(options.db, options.approval());
      if (after.snapshotId !== snapshot.snapshotId || !after.media.some((item) => item.sha256 === asset.sha256 && item.slug === asset.slug && item.version === asset.version)) return json({ error: "unavailable" }, 409);
      return signed(bytes, 200, "image/png");
    } catch (error) {
      if (url.pathname === READ_PATH) return json({
        contract: WEBSITE_READ_CONTRACT, snapshotId: "0".repeat(64), canonicalAccess: "unverified",
        feed: emptyFeed(error instanceof MalformedRead || error instanceof SyntaxError ? "malformed" : "unavailable"), media: [],
      });
      return json({ error: "unavailable" }, 503);
    }
  };
}
