/** Local read contract only. No deployment route or credential binding is armed. */
export const WEBSITE_READ_CONTRACT = "magazine.website-read.local.v1";
export const WEBSITE_READ_AUDIENCE = "website-local-read";
export const MAGAZINE_CANONICAL_ORIGIN = "https://bali-zero-magazine.antonellosiano.chatgpt.site";
export const READ_PATH = "/v1/edition";
export const MEDIA_PATH = "/v1/story-media";
export const WEBSITE_MEDIA_PATH = "/api/journal-media";
export const MAX_READ_BYTES = 1024 * 1024;
export const MAX_PUBLIC_MEDIA_BYTES = 12 * 1024 * 1024;

export type PublicArticle = Readonly<{
  slug: string; title: string;
  category: "immigration" | "company" | "tax" | "property" | "compliance" | "general";
  publicationState: "published"; visibility: "visible";
  publishedAt: string; updatedAt: string; revision: number;
  lifecycleState: "developing" | "verified" | "amended";
  canonicalUrl: string; summary: string; whyItMatters: string;
  evidence: readonly Readonly<{ publisher: string; citation: string | null; url: string | null }>[];
  revisions: readonly Readonly<{ version: number; publishedAt: string }>[];
  image: null;
}>;
export type PublicFeed = Readonly<{
  version: 2; publisher: "bali-zero-magazine";
  status: "ready" | "empty" | "withdrawn" | "unpublished" | "unavailable" | "malformed";
  articles: readonly PublicArticle[]; provenance: "fixture";
}>;
export type PublicMedia = Readonly<{
  slug: string; version: number; sha256: string; mimeType: "image/png";
  byteCount: number; width: number; height: number; alt: string;
}>;
export type WebsiteRead = Readonly<{
  contract: typeof WEBSITE_READ_CONTRACT;
  snapshotId: string;
  canonicalAccess: "unverified";
  feed: PublicFeed;
  media: readonly PublicMedia[];
}>;

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function isDigest(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
}
export function isSlug(value: unknown): value is string {
  return typeof value === "string" && value.length <= 140 && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
}
export function isPositive(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) > 0;
}
export function isPublicText(value: unknown, limit: number): value is string {
  // This is syntax validation, not semantic PII detection. Exact reviewed
  // projection digests below are the separate disclosure authorization.
  return typeof value === "string" && value.trim().length > 0 && value.length <= limit &&
    !/[<>\u0000-\u001f\u007f\u202a-\u202e\u2066-\u2069]/u.test(value);
}
export function isPublicDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{3})?Z$/.test(value)) return false;
  return Number.isFinite(Date.parse(value)) && new Date(value).toISOString().replace(".000Z", "Z") === value.replace(".000Z", "Z");
}
export function isApprovedUrl(value: unknown, origins: readonly string[]): value is string {
  if (typeof value !== "string" || value.length > 1500) return false;
  try {
    const url = new URL(value);
    return url.href === value && url.protocol === "https:" && !url.username && !url.password &&
      !url.search && !url.hash && origins.includes(url.origin);
  } catch { return false; }
}
export function hasKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).sort().join(",") === [...keys].sort().join(",");
}

export function isPublicArticle(value: unknown, origins: readonly string[]): value is PublicArticle {
  if (!isRecord(value) || !hasKeys(value, ["slug", "title", "category", "publicationState", "visibility", "publishedAt", "updatedAt", "revision", "lifecycleState", "canonicalUrl", "summary", "whyItMatters", "evidence", "revisions", "image"])) return false;
  if (!isSlug(value.slug) || !isPositive(value.revision) || value.publicationState !== "published" || value.visibility !== "visible" || value.image !== null) return false;
  if (!["immigration", "company", "tax", "property", "compliance", "general"].includes(value.category as string) || !["developing", "verified", "amended"].includes(value.lifecycleState as string)) return false;
  if (!isPublicText(value.title, 240) || !isPublicText(value.summary, 2000) || !isPublicText(value.whyItMatters, 2000)) return false;
  if (!isPublicDate(value.publishedAt) || !isPublicDate(value.updatedAt) || value.canonicalUrl !== `${MAGAZINE_CANONICAL_ORIGIN}/stories/${value.slug}`) return false;
  if (!Array.isArray(value.evidence) || !value.evidence.length || value.evidence.length > 30) return false;
  if (!value.evidence.every((item: unknown) => isRecord(item) && hasKeys(item, ["publisher", "citation", "url"]) &&
    isPublicText(item.publisher, 200) && (item.citation === null || isPublicText(item.citation, 500)) &&
    (item.url === null || isApprovedUrl(item.url, origins)) && (item.url !== null || item.citation !== null))) return false;
  if (!Array.isArray(value.revisions) || !value.revisions.length || value.revisions.length > 100) return false;
  let previous = 0;
  for (const item of value.revisions) {
    if (!isRecord(item) || !hasKeys(item, ["version", "publishedAt"]) || !isPositive(item.version) ||
      item.version <= previous || item.version > value.revision || !isPublicDate(item.publishedAt)) return false;
    previous = item.version;
  }
  return previous === value.revision && value.revisions.at(-1).publishedAt === value.publishedAt;
}

export function isPublicMedia(value: unknown): value is PublicMedia {
  return isRecord(value) && hasKeys(value, ["slug", "version", "sha256", "mimeType", "byteCount", "width", "height", "alt"]) &&
    isSlug(value.slug) && isPositive(value.version) && isDigest(value.sha256) && value.mimeType === "image/png" &&
    isPositive(value.byteCount) && value.byteCount <= MAX_PUBLIC_MEDIA_BYTES &&
    isPositive(value.width) && value.width <= 8192 && isPositive(value.height) && value.height <= 8192 &&
    value.width * value.height <= 40_000_000 && isPublicText(value.alt, 400);
}

export function localOrigin(value: string): string {
  const url = new URL(value);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port ||
    url.username || url.password || url.pathname !== "/" || url.search || url.hash) throw new TypeError("Local read origin required");
  return url.origin;
}

export function mediaPath(prefix: string, snapshot: string, media: PublicMedia): string {
  return `${prefix}/${media.slug}/${media.version}/${media.sha256}?snapshot=${snapshot}`;
}

export function responseSignatureInput(path: string, nonce: string, status: number, mime: string, digest: string): string {
  return [WEBSITE_READ_CONTRACT, path, nonce, String(status), mime, digest].join("\n");
}
