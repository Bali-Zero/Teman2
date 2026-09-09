import type { JournalArticle } from "../content/journal";
import { isArticleSlug } from "./article-slug";
import { retainedImage } from "./retained-assets";

// Version 1 remains the isolated MDX characterization proof. Version 2 below
// is the Magazine boundary consumed by the website's server pages.
const editorialOrigin = "https://balizero.com";
const categories = new Set(["visas", "business", "taxes", "property", "living", "trends"]);

export interface EditorialFeed {
  readonly status: "ready" | "empty" | "unavailable" | "malformed" | "withdrawn" | "unpublished";
  readonly articles: readonly JournalArticle[];
  readonly rejected: number;
  readonly provenance?: "fixture" | "publisher";
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function projectArticle(value: unknown): JournalArticle | null {
  if (!record(value) || value.publicationState !== "published" || value.noIndex !== false) return null;
  const { slug, category, title, coverImage, publishedAt } = value;
  if (!isArticleSlug(slug)) return null;
  if (typeof category !== "string" || !categories.has(category)) return null;
  if (typeof title !== "string" || !title.trim() || title.length > 500) return null;
  const image = retainedImage(coverImage);
  if (!image) return null;

  // Missing dates stay missing. Never substitute creation time or today's date.
  let date: JournalArticle["date"] = null;
  if (publishedAt !== null) {
    if (typeof publishedAt !== "string" || !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z)?$/.test(publishedAt)) return null;
    const parsed = new Date(publishedAt);
    if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== publishedAt.slice(0, 10)) return null;
    date = {
      iso: parsed.toISOString(),
      label: new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(parsed),
    };
  }

  return {
    slug, title: title.trim(), category,
    image: { ...image, alt: title.trim() }, date,
    sourceUrl: `${editorialOrigin}/${category}/${slug}`,
    finalSourceUrl: null,
    // Publishing state does not certify an independent destination check.
    verificationStatus: "pending",
  };
}

/** Same consumer contract for an in-process publisher or decoded HTTP payload. */
export async function readEditorialFeed(read: () => Promise<unknown>): Promise<EditorialFeed> {
  try {
    const payload = await read();
    if (!record(payload) || payload.version !== 1 || !Array.isArray(payload.articles)) {
      return { status: "unavailable", articles: [], rejected: 0 };
    }
    const articles: JournalArticle[] = [];
    const seen = new Set<string>();
    let rejected = 0;
    for (const row of payload.articles) {
      const article = projectArticle(row);
      if (!article || seen.has(article.sourceUrl)) { rejected++; continue; }
      seen.add(article.sourceUrl);
      articles.push(article);
    }
    return { status: articles.length ? "ready" : rejected ? "unavailable" : "empty", articles, rejected };
  } catch {
    return { status: "unavailable", articles: [], rejected: 0 };
  }
}


const magazineOrigin = "https://bali-zero-magazine.antonellosiano.chatgpt.site";
const magazineCategories = new Set(["immigration", "company", "tax", "property", "compliance", "general"]);
const terminalStates = new Set(["empty", "unavailable", "malformed", "withdrawn", "unpublished"]);

function text(value: unknown, limit: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= limit;
}

function publicDate(value: unknown): JournalArticle["date"] {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) return null;
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().replace(".000Z", "Z") !== value.replace(".000Z", "Z")) return null;
  return { iso: value, label: new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(parsed) };
}

function approvedSource(value: unknown, origins: readonly string[]): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password && !url.search && !url.hash && origins.includes(url.origin);
  } catch { return false; }
}

function magazineArticle(value: unknown, fixture: boolean, sourceOrigins: readonly string[]): JournalArticle | null {
  if (!record(value) || value.publicationState !== "published" || value.visibility !== "visible") return null;
  const { slug, title, category, summary, whyItMatters, revision, lifecycleState } = value;
  if (typeof slug !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) || slug.length > 160) return null;
  if (!text(title, 500) || typeof category !== "string" || !magazineCategories.has(category)) return null;
  if (!text(summary, 4000) || !text(whyItMatters, 4000)) return null;
  if (!Number.isSafeInteger(revision) || (revision as number) < 1) return null;
  if (!["developing", "verified", "amended"].includes(lifecycleState as string)) return null;
  const canonical = magazineOrigin + "/stories/" + slug;
  if (value.canonicalUrl !== canonical) return null;
  const date = publicDate(value.publishedAt), updatedAt = publicDate(value.updatedAt);
  if (!date || !updatedAt) return null;
  let image: JournalArticle["image"] = null;
  if (value.image !== null) {
    if (!record(value.image) || !text(value.image.alt, 500)) return null;
    // The Magazine media response is CORP same-origin. Until delivery is proven,
    // public records are text-led. Only this owned illustration is local proof.
    if (!fixture || value.image.src !== "/assets/editorial-fixture.svg") return null;
    image = { src: value.image.src, alt: value.image.alt };
  }
  if (!Array.isArray(value.evidence) || value.evidence.length < 1 || value.evidence.length > 30) return null;
  const evidence: NonNullable<JournalArticle["editorial"]>["evidence"][number][] = [];
  for (const item of value.evidence) {
    if (!record(item) || !text(item.publisher, 200) || (item.citation !== null && !text(item.citation, 1000))) return null;
    if (item.url !== null && !approvedSource(item.url, sourceOrigins)) return null;
    if (item.url === null && item.citation === null) return null;
    evidence.push({ publisher: item.publisher, citation: item.citation, url: item.url });
  }
  if (!Array.isArray(value.revisions) || !value.revisions.length || value.revisions.length > 100) return null;
  const revisions: NonNullable<JournalArticle["editorial"]>["revisions"][number][] = [];
  let previous = 0;
  for (const item of value.revisions) {
    if (!record(item) || !Number.isSafeInteger(item.version) || (item.version as number) <= previous || (item.version as number) > (revision as number)) return null;
    const publishedAt = publicDate(item.publishedAt);
    if (!publishedAt) return null;
    previous = item.version as number;
    revisions.push({ version: previous, publishedAt });
  }
  if (previous !== revision || revisions.at(-1)?.publishedAt.iso !== date.iso) return null;
  return {
    slug, title, category, image, date, sourceUrl: canonical, finalSourceUrl: null,
    verificationStatus: fixture ? "development-only" : "pending",
    editorial: { summary, whyItMatters, revision: revision as number, amended: lifecycleState === "amended", updatedAt, evidence, revisions },
  };
}

/** Atomic allowlist decoder. A corrupt response never becomes an empty edition. */
export async function readMagazineFeed(
  read: () => Promise<unknown>,
  policy: { allowFixture?: boolean; approvedEvidenceOrigins?: readonly string[] } = {},
): Promise<EditorialFeed> {
  const failure = (status: "unavailable" | "malformed"): EditorialFeed => ({ status, articles: [], rejected: 0 });
  try {
    const payload = await read();
    if (!record(payload) || payload.version !== 2 || payload.publisher !== "bali-zero-magazine" || !Array.isArray(payload.articles)) return failure("malformed");
    if (payload.provenance !== "fixture" && payload.provenance !== "publisher") return failure("malformed");
    const fixture = payload.provenance === "fixture";
    if (fixture && !policy.allowFixture) return failure("malformed");
    const provenance = payload.provenance;
    if (terminalStates.has(payload.status as string) && payload.articles.length === 0) {
      return { status: payload.status as EditorialFeed["status"], articles: [], rejected: 0, provenance };
    }
    if (payload.status !== "ready" || !payload.articles.length || payload.articles.length > 100) return failure("malformed");
    const articles: JournalArticle[] = [], seen = new Set<string>();
    for (const row of payload.articles) {
      const article = magazineArticle(row, fixture, policy.approvedEvidenceOrigins ?? []);
      if (!article || seen.has(article.sourceUrl)) return failure("malformed");
      seen.add(article.sourceUrl); articles.push(article);
    }
    return { status: "ready", articles, rejected: 0, provenance };
  } catch { return failure("unavailable"); }
}
