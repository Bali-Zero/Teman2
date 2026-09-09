import type { Dirent } from "node:fs";
import * as fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";
import { isJournalCategory } from "../../content/journal-categories";
import { isArticleSlug } from "../article-slug";

export const articleArchiveMaxBytes = 250_000;
const articleArchiveMemoMaxAgeMs = 5 * 60 * 1000;

// Exact reading order from Mouth's getArticleByLocale. Originals remain
// read-only in the publisher content tree.
export const articleFolders: Record<string, readonly string[]> = {
  visas: ["immigration"],
  business: ["business", "business_regulations", "news"],
  taxes: ["tax-legal", "tax"],
  property: ["property"],
  living: ["lifestyle", "digital-nomad", "bali_news"],
  trends: ["emerging_trends", "tech", "social_media"],
};

const categoryAliases: Record<string, string> = {
  immigration: "visas",
  business_regulations: "business",
  news: "business",
  "tax-legal": "taxes",
  tax: "taxes",
  lifestyle: "living",
  "digital-nomad": "living",
  bali_news: "living",
  emerging_trends: "trends",
  tech: "trends",
  social_media: "trends",
};
const record = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const iso = (value: unknown): unknown =>
  value instanceof Date ? value.toISOString() : value;

export interface AuthoredArticleSource {
  frontmatter: Record<string, unknown>;
  value: Record<string, unknown>;
}

export type ArticleArchiveRead =
  | Readonly<{ status: "absent" }>
  | Readonly<{ status: "rejected" }>
  | Readonly<{ status: "ready"; source: string }>;

export type AuthoredEnglishArticleRead =
  | Readonly<{ status: "absent" }>
  | Readonly<{ status: "rejected" }>
  | Readonly<{ status: "ready"; article: AuthoredArticleSource }>;

export interface AuthoredArchiveEntry extends AuthoredArticleSource {
  category: string;
  slug: string;
}

interface ArchiveFolderSnapshot {
  category: string;
  folder: string;
  canonicalFolder: string;
  files: Dirent<string>[];
  mtimeMs: number;
}

interface ArticleArchiveMemo {
  fingerprint: string;
  cachedAt: number;
  entries: AuthoredArchiveEntry[];
}

let articleArchiveMemo: ArticleArchiveMemo | null = null;

export function resetArticleArchiveMemo(): void {
  articleArchiveMemo = null;
}

export function articleArchiveRoot(): string {
  return path.resolve(process.cwd(), "../mouth/src/content/articles");
}

function contained(canonicalRoot: string, candidate: string): boolean {
  return candidate.startsWith(canonicalRoot + path.sep);
}

async function canonicalArchiveRoot(): Promise<{
  root: string;
  canonicalRoot: string;
} | null> {
  const root = articleArchiveRoot();
  try {
    return { root, canonicalRoot: await fs.realpath(root) };
  } catch {
    return null;
  }
}

async function readArchiveFile(
  root: string,
  canonicalRoot: string,
  folder: string,
  filename: string,
): Promise<ArticleArchiveRead> {
  const unresolvedFile = path.join(root, folder, filename);
  let file: string;
  try {
    file = await fs.realpath(unresolvedFile);
  } catch {
    try {
      await fs.lstat(unresolvedFile);
      return { status: "rejected" };
    } catch {
      return { status: "absent" };
    }
  }
  if (!contained(canonicalRoot, file)) return { status: "rejected" };
  try {
    const info = await fs.stat(file);
    if (!info.isFile() || info.size > articleArchiveMaxBytes)
      return { status: "rejected" };
    return { status: "ready", source: await fs.readFile(file, "utf8") };
  } catch {
    return { status: "rejected" };
  }
}

export async function readArticleArchiveFile(
  folder: string,
  filename: string,
): Promise<ArticleArchiveRead> {
  const archive = await canonicalArchiveRoot();
  if (!archive) return { status: "absent" };
  return readArchiveFile(archive.root, archive.canonicalRoot, folder, filename);
}

/** Decode authored YAML and inert MDX into the one shape accepted by the
 * public publication gate. Path identity wins; conflicting frontmatter is
 * rejected, while an omitted identity is filled from the path. */
export function decodeAuthoredArticleSource(
  source: string,
  category: string,
  slug: string,
): AuthoredArticleSource | null {
  if (
    !isJournalCategory(category) ||
    !isArticleSlug(slug) ||
    source.length > articleArchiveMaxBytes ||
    !/^---\r?\n/.test(source)
  )
    return null;
  try {
    const { data, content } = matter(source);
    if (
      !record(data) ||
      (Object.hasOwn(data, "slug") && data.slug !== slug) ||
      (Object.hasOwn(data, "category") &&
        (categoryAliases[String(data.category)] ?? data.category) !== category)
    )
      return null;
    const image = record(data.image) ? data.image : {};
    return {
      frontmatter: data,
      value: {
        ...data,
        category,
        slug,
        content,
        status: data.status ?? "published",
        publishedAt: iso(data.publishedAt),
        updatedAt: iso(data.updatedAt),
        coverImage: data.coverImage ?? image.src,
        coverImageAlt: data.coverImageAlt ?? image.alt,
      },
    };
  } catch {
    return null;
  }
}

export async function readAuthoredEnglishArticle(
  category: string,
  slug: string,
): Promise<AuthoredEnglishArticleRead> {
  if (!isJournalCategory(category) || !isArticleSlug(slug))
    return { status: "rejected" };
  const archive = await canonicalArchiveRoot();
  if (!archive) return { status: "absent" };
  for (const folder of articleFolders[category]) {
    const file = await readArchiveFile(
      archive.root,
      archive.canonicalRoot,
      folder,
      `${slug}.mdx`,
    );
    if (file.status === "absent") continue;
    if (file.status === "rejected") return file;
    const article = decodeAuthoredArticleSource(file.source, category, slug);
    return article ? { status: "ready", article } : { status: "rejected" };
  }
  return { status: "absent" };
}

/** List base English editions only. Detail reads still pass through
 * decodePublicArticle before any catalog entry can be displayed. */
export async function listAuthoredEnglishArticles(): Promise<
  AuthoredArchiveEntry[]
> {
  const archive = await canonicalArchiveRoot();
  if (!archive) return [];
  const snapshots: ArchiveFolderSnapshot[] = [];
  const fingerprintParts: string[] = [];
  for (const [category, folders] of Object.entries(articleFolders)) {
    if (!isJournalCategory(category)) continue;
    for (const folder of folders) {
      let canonicalFolder: string;
      try {
        canonicalFolder = await fs.realpath(path.join(archive.root, folder));
      } catch {
        fingerprintParts.push(`${category}/${folder}:absent`);
        continue;
      }
      if (!contained(archive.canonicalRoot, canonicalFolder)) {
        fingerprintParts.push(`${category}/${folder}:rejected`);
        continue;
      }
      try {
        const [info, files] = await Promise.all([
          fs.stat(canonicalFolder),
          fs.readdir(canonicalFolder, { withFileTypes: true }),
        ]);
        if (!info.isDirectory()) {
          fingerprintParts.push(`${category}/${folder}:not-directory`);
          continue;
        }
        snapshots.push({
          category,
          folder,
          canonicalFolder,
          files,
          mtimeMs: info.mtimeMs,
        });
        fingerprintParts.push(
          `${category}/${folder}:${info.mtimeMs}:${files.length}`,
        );
      } catch {
        fingerprintParts.push(`${category}/${folder}:unreadable`);
      }
    }
  }

  const fingerprint = fingerprintParts.join("|");
  const now = Date.now();
  if (
    articleArchiveMemo?.fingerprint === fingerprint &&
    now - articleArchiveMemo.cachedAt >= 0 &&
    now - articleArchiveMemo.cachedAt < articleArchiveMemoMaxAgeMs
  ) {
    return articleArchiveMemo.entries;
  }

  const entries: AuthoredArchiveEntry[] = [];
  const identities = new Set<string>();
  for (const { category, folder, files } of snapshots) {
    for (const entry of files) {
      if (
        !(entry.isFile() || entry.isSymbolicLink()) ||
        !entry.name.endsWith(".mdx")
      )
        continue;
      const slug = entry.name.slice(0, -4);
      if (/\.(?:en|id|it|fr|ru)$/.test(slug) || !isArticleSlug(slug)) continue;
      const identity = `${category}/${slug}`;
      if (identities.has(identity)) continue;
      identities.add(identity);
      const file = await readArchiveFile(
        archive.root,
        archive.canonicalRoot,
        folder,
        entry.name,
      );
      if (file.status !== "ready") continue;
      const article = decodeAuthoredArticleSource(file.source, category, slug);
      if (article) entries.push({ category, slug, ...article });
    }
  }
  articleArchiveMemo = { fingerprint, cachedAt: now, entries };
  return entries;
}
