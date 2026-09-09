import { isArticleSlug } from "./article-slug";
import { isJournalCategory } from "../content/journal-categories";
import { retainedAssetPath } from "./retained-assets";

/** Original product-owner routes available to the guarded fallback bridge.
 * Explicit website routes take precedence: this registry describes fallback
 * eligibility, not which public pages still use the original presentation. */
export const retainedRoutes = [
  { family: "visa", pattern: /^\/visa(?:\/(?:privacy|terms|match(?:\/[A-Za-z0-9_-]{1,200})?|clock(?:\/[A-Za-z0-9_-]{1,200})?|second-home(?:\/(?:it|id|studio))?|voa(?:\/(?:auth(?:\/continue)?|(?:upload|checkout)\/[A-Za-z0-9_-]{1,200}|orders\/[A-Za-z0-9_-]{1,200}(?:\/return)?|[A-Za-z0-9_-]{1,200}))?))?$/, source: "apps/mouth/src/app/visa/", owner: "mouth" },
  { family: "visa-oracle", pattern: /^\/visa-oracle(?:\/(?:privacy|unlock))?$/, source: "apps/mouth/src/app/(visa-oracle)/visa-oracle/", owner: "mouth" },
  { family: "kbli", pattern: /^\/kbli(?:\/(?:\d{5}|builder|decoder|sectors(?:\/[A-Za-z0-9_-]{1,100})?))?$/, source: "apps/mouth/src/app/kbli/", owner: "mouth" },
  { family: "kbli-explorer", pattern: /^\/kbli-explorer$/, source: "apps/mouth/src/app/kbli-explorer/page.tsx", owner: "mouth" },
  { family: "tax-calendar", pattern: /^\/tax-calendar$/, source: "apps/mouth/src/app/(tax-calendar)/tax-calendar/page.tsx", owner: "mouth" },
  { family: "tax-gap", pattern: /^\/taxes\/gap$/, source: "apps/mouth/src/app/taxes/gap/page.tsx", owner: "mouth" },
  { family: "property", pattern: /^\/property\/eligibility$/, source: "apps/mouth/src/app/property/eligibility/page.tsx", owner: "mouth" },
  { family: "legal", pattern: /^\/(?:v2\/(?:privacy|terms|cookies)|privacy|terms)$/, source: "apps/mouth/src/app/{v2,visa}/{privacy,terms,cookies}/", owner: "mouth" },
  { family: "company-retained", pattern: /^\/v2\/company\/(?:press|careers)$/, source: "apps/mouth/src/app/v2/company/", owner: "mouth" },
  { family: "editorial-feed", pattern: /^\/feed$/, source: "apps/mouth/src/app/feed/route.ts", owner: "mouth" },
  { family: "book", pattern: /^\/book(?:\/[a-z0-9-]{1,200})?$/, source: "apps/mouth/src/app/(book)/book/", owner: "mouth" },
  { family: "property-research", pattern: /^\/(?:zoning|prime(?:\/proposal\/[A-Za-z0-9_-]{1,200})?)$/, source: "apps/mouth/src/app/{prime,zoning}/", owner: "mouth" },
] as const;

const aliases: Readonly<Record<string, string>> = {
  "/visa/second-home-e33": "/visa/second-home", "/visa-v2": "/visa-oracle", "/tax/gap": "/taxes/gap",
};

export function retainedPath(pathname: string): string | null {
  const path = pathname.replace(/\/$/, "") || "/";
  if (path.includes("%") || path.includes("\\") || path.includes("//")) return null;
  const canonical = aliases[path] ?? path.replace(/^\/kbli-navigator(?=\/|$)/, "/kbli");
  if (retainedRoutes.some((route) => route.pattern.test(canonical))) return canonical;
  if (canonical === "/legacy/news") return "/news";
  if (canonical === "/legacy/visa/voa") return "/visa/voa";
  if (canonical === "/legacy/prime") return "/prime";
  if (/^\/legacy\/visa\/(?:voa|clock|match)\/[A-Za-z0-9_-]{1,200}$/.test(canonical)) return canonical.slice("/legacy".length);
  if (canonical.startsWith("/legacy/static/")) return retainedAssetPath(canonical.slice("/legacy".length));
  const parts = canonical.split("/");
  if (parts.length === 4 && parts[1] === "legacy" && isJournalCategory(parts[2]) && isArticleSlug(parts[3])) return `/${parts[2]}/${parts[3]}`;
  return null;
}

/** Public edition exits must go through the guarded owner handoff, not back
 * onto the same URL when this app eventually serves the public hostname. */
export function publishedEditionHref(value: string): string {
  try {
    const url = new URL(value, "https://balizero.com");
    if (url.origin !== "https://balizero.com" || url.username || url.password) return "/legacy/news";
    const parts = url.pathname.split("/");
    return parts.length === 3 && isJournalCategory(parts[1]) && isArticleSlug(parts[2])
      ? `/legacy${url.pathname}${url.search}${url.hash}` : "/legacy/news";
  } catch { return "/legacy/news"; }
}

/** These dependencies execute only AFTER navigation reaches their product
 * owner. A request accidentally sent to marketing receives an explicit 503. */
export const retainedApiPaths: readonly RegExp[] = [
  /^\/api\/visa\/(?:match|clock)(?:\/(?:[A-Za-z0-9_-]{1,200}|email))?$/,
  /^\/api\/visa\/voa\/eligibility-checks(?:\/[A-Za-z0-9_-]{1,200}(?:\/documents)?)?$/,
  /^\/api\/visa\/voa\/orders(?:\/[A-Za-z0-9_-]{1,200}(?:\/browser-return-observations)?)?$/,
  /^\/api\/visa\/voa\/auth\/(?:magic-links(?:\/preview)?|sessions)$/,
  /^\/api\/(?:visa-oracle-unlock|property\/analyze)$/,
  /^\/api\/visa-oracle\/evaluate$/,
  /^\/api\/v1\/visa-oracle\/(?:recommend|chat|handoff)$/,
  /^\/api\/v1\/kbli-notebook\/(?:search|chat|inspect\/\d{5})$/,
  /^\/api\/kbli\/gold(?:\/\d{5})?$/,
  /^\/api\/og(?:\/book|\/kbli\/\d{5})?$/,
  /^\/api\/tax-calendar\/(?:deadlines|ical)$/,
  /^\/api\/blog\/(?:articles(?:\/[a-z]+\/[a-z0-9-]{1,200}(?:\/views)?)?|homepage-hero|newsletter\/(?:subscribe|confirm|unsubscribe|preferences)|ask)$/,
  /^\/api\/analytics\/(?:funnel-event|web-vitals)$/,
  /^\/api\/prime\/(?:chat|zoning|zones-geojson|v2\/(?:regulations|analyze|portfolio|predict|proposal(?:\/[A-Za-z0-9_-]{1,200})?|density|intelligence|resolve|temporal))$/,
];
