/**
 * The ONE reader of WEBSITE_PUBLIC_ORIGIN.
 *
 * Before this module the variable had three independent readers with two
 * different absent-cases: robots.ts fell back to `Disallow: /` while sitemap.ts
 * and the root layout fell back to the literal `https://balizero.com`. Absent in
 * production, that combination blocks every crawler while the sitemap and every
 * canonical keep claiming the production host — a site that looks correct in
 * every log and is invisible to search. Undefined here means "not public yet",
 * and every consumer must say the same thing.
 */
export function publicOrigin(): string | undefined {
  const configured = process.env.WEBSITE_PUBLIC_ORIGIN;
  if (!configured) return undefined;
  return configured.replace(/\/+$/, "");
}
