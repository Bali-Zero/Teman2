import { cache } from "react";
import { isArticleSlug } from "../article-slug";
import { isJournalCategory } from "../../content/journal-categories";
import { editorialUpstreamOrigin } from "./legacy-origin";

export interface CatalogEntry { slug: string; category: string; title: string; excerpt: string; tags: string[]; publishedAt: string }
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
export class EditorialHttpError extends Error {
  constructor(readonly status: number) { super("Editorial read unavailable"); }
}

export async function readEditorialJson(path: string, fresh = false): Promise<unknown> {
  const response = await fetch(await editorialUpstreamOrigin() + path, {
    redirect: "error", ...(fresh ? { cache: "no-store" as const } : { next: { revalidate: 60 } }), signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new EditorialHttpError(response.status);
  if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("Invalid editorial response");
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Empty editorial response");
  let size = 0, body = "";
  const decoder = new TextDecoder();
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      size += part.value.length;
      if (size > 2_000_000) throw new Error("Editorial read too large");
      body += decoder.decode(part.value, { stream: true });
    }
    return JSON.parse(body + decoder.decode());
  } finally { await reader.cancel(); }
}

/** Read every page of the exposed catalog. Never use the legacy q endpoint:
 * it searches a first-200 fallback and ignores pagination. Metadata is NOT
 * publication authority; each displayed result still requires a detail read. */
export const loadPublicCatalog = cache(async (): Promise<CatalogEntry[]> => {
  const entries: CatalogEntry[] = [], identities = new Set<string>();
  let total: number | undefined;
  do {
    const data = await readEditorialJson(`/api/blog/articles?limit=200&offset=${entries.length}`);
    if (!record(data) || !Array.isArray(data.articles) || data.articles.length > 200 ||
      !Number.isSafeInteger(data.total) || (data.total as number) < 0 || (data.total as number) > 100_000 ||
      total !== undefined && data.total !== total) throw new Error("Incomplete editorial catalog");
    total = data.total as number;
    if (!data.articles.length && entries.length < total) throw new Error("Editorial pagination stalled");
    for (const raw of data.articles) {
      if (!record(raw) || !isArticleSlug(raw.slug) ||
        typeof raw.category !== "string" || !isJournalCategory(raw.category) || typeof raw.title !== "string" || !raw.title.trim() || raw.title.length > 500) throw new Error("Malformed editorial entry");
      const identity = `${raw.category}/${raw.slug}`;
      if (identities.has(identity)) throw new Error("Editorial pagination repeated an entry");
      identities.add(identity);
      entries.push({ slug: raw.slug, category: raw.category, title: raw.title,
        excerpt: typeof raw.excerpt === "string" ? raw.excerpt.slice(0, 4000) : "",
        tags: Array.isArray(raw.tags) ? raw.tags.filter((v): v is string => typeof v === "string" && v.length <= 100).slice(0, 50) : [],
        publishedAt: typeof raw.publishedAt === "string" ? raw.publishedAt : "" });
    }
    if (entries.length > total || typeof data.hasMore === "boolean" && data.hasMore !== (entries.length < total)) throw new Error("Inconsistent editorial total");
  } while (entries.length < total);
  return entries;
});

const normalize = (value: string): string => value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
export function selectCatalog(catalog: readonly CatalogEntry[], query: { q?: string; category?: string }): CatalogEntry[] {
  const phrase = normalize(query.q ?? ""), terms = phrase.split(" ").filter(Boolean);
  return catalog.flatMap((entry) => {
    if (query.category && entry.category !== query.category) return [];
    const title = normalize(entry.title), haystack = normalize([entry.title, entry.slug, entry.excerpt, entry.category, ...entry.tags].join(" "));
    if (!terms.every((term) => haystack.includes(term))) return [];
    const score = !phrase ? 0 : title === phrase ? 3 : title.includes(phrase) ? 2 : 1;
    return [{ entry, score }];
  }).sort((a, b) => b.score - a.score || b.entry.publishedAt.localeCompare(a.entry.publishedAt) || `${a.entry.category}/${a.entry.slug}`.localeCompare(`${b.entry.category}/${b.entry.slug}`)).map(({ entry }) => entry);
}
