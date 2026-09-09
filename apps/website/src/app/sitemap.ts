import { readFile } from "node:fs/promises";
import path from "node:path";
import type { MetadataRoute } from "next";
import { journalCategories } from "../content/journal-categories";
import { getAllCodes, getSections } from "../features/kbli/catalog.server";
import { loadPublicCatalog } from "../lib/server/public-catalog";

const staticPaths = [
  "/",
  "/services",
  "/services/immigration",
  "/services/company-setup",
  "/services/tax",
  "/services/property",
  "/news",
  "/visa-oracle",
  "/team",
  "/contact",
  "/about",
  "/kbli",
  "/kbli-explorer",
  "/kbli/sectors",
  "/kbli/builder",
  "/kbli/decoder",
  "/property/eligibility",
  "/tax-calendar",
  "/taxes/gap",
  "/book",
  "/zoning",
  "/privacy",
  "/terms",
  "/llms.txt",
  "/llms-full.txt",
  "/llms-id.txt",
] as const;

const visaToolPaths = [
  "/visa/match",
  "/visa/clock",
  "/visa/second-home",
  "/visa/second-home/id",
  "/visa/second-home/it",
  "/visa/second-home/studio",
] as const;

function publicOrigin(): string {
  return (process.env.WEBSITE_PUBLIC_ORIGIN || "https://balizero.com").replace(
    /\/+$/,
    "",
  );
}

async function kbliLastModified(): Promise<string | undefined> {
  try {
    const source = await readFile(
      path.resolve(process.cwd(), "../mouth/data/kbli-dataset-version.json"),
      "utf8",
    );
    const value: unknown = JSON.parse(source);
    if (
      value &&
      typeof value === "object" &&
      "lastModified" in value &&
      typeof value.lastModified === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(value.lastModified)
    ) {
      return value.lastModified;
    }
  } catch {
    // A missing sidecar only removes lastModified; it never removes KBLI URLs.
  }
  return undefined;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = publicOrigin();
  const [articles, datasetDate] = await Promise.all([
    loadPublicCatalog(),
    kbliLastModified(),
  ]);
  const entries: MetadataRoute.Sitemap = [];
  const seen = new Set<string>();
  const add = (pathname: string, lastModified?: string): void => {
    const url = new URL(pathname, `${origin}/`).toString();
    if (seen.has(url)) return;
    seen.add(url);
    entries.push({ url, ...(lastModified ? { lastModified } : {}) });
  };

  for (const pathname of [...staticPaths, ...visaToolPaths]) add(pathname);
  for (const category of journalCategories) add(`/${category.slug}`);
  for (const article of articles) {
    add(
      `/${article.category}/${article.slug}`,
      article.publishedAt || undefined,
    );
  }
  for (const code of getAllCodes()) add(`/kbli/${code.code}`, datasetDate);
  for (const section of getSections()) {
    if (section.codeCount > 0 && /^[A-Z]$/.test(section.id)) {
      add(`/kbli/sectors/${section.id}`);
    }
  }

  return entries;
}
