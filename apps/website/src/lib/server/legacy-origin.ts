import { headers } from "next/headers";

type OriginSettings = Readonly<{ legacyOrigin?: string; publicOrigin?: string }>;
const canonicalHost = (value: string): string => value.toLowerCase().replace(/^www\./, "").replace(/\.$/, "");
const localHost = (value: string): boolean => ["localhost", "127.0.0.1", "[::1]"].includes(value);
// These existing mouth front doors redirect/rewrite public paths; they are
// not independent retained origins. In particular visa redirects to apex.
const sharedFrontDoors = new Set(["visa.balizero.com", "tax.balizero.com", "my.balizero.com", "kita.balizero.com", "zantara.balizero.com", "prime.balizero.com"]);

/** Default is allowed only on localhost. A real public host requires an
 * explicit independent upstream AND public origin; no deployment is armed. */
export function resolveLegacyOrigin(requestHosts: readonly string[], settings: OriginSettings = {}): string | null {
  try {
    const hosts = requestHosts.filter(Boolean).flatMap((host) => host.split(",")).map((host) => new URL(`https://${host.trim()}`).hostname);
    if (!hosts.length) return null;
    const local = hosts.every(localHost);
    if (!local && (!settings.legacyOrigin || !settings.publicOrigin)) return null;
    const origin = new URL(settings.legacyOrigin ?? "https://balizero.com");
    if (sharedFrontDoors.has(canonicalHost(origin.hostname))) return null;
    if (origin.protocol !== "https:" || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash || origin.port || localHost(origin.hostname)) return null;
    if (settings.publicOrigin) {
      const publicOrigin = new URL(settings.publicOrigin);
      if (publicOrigin.protocol !== "https:" || publicOrigin.username || publicOrigin.password || publicOrigin.pathname !== "/" || publicOrigin.search || publicOrigin.hash) return null;
      hosts.push(publicOrigin.hostname);
    }
    return hosts.some((host) => canonicalHost(host) === canonicalHost(origin.hostname)) ? null : origin.origin;
  } catch { return null; }
}

export function legacyOriginForHeaders(requestHeaders: Headers, url?: string): string | null {
  return resolveLegacyOrigin([
    ...(url ? [new URL(url).host] : []),
    requestHeaders.get("host") ?? "", requestHeaders.get("x-forwarded-host") ?? "",
  ], { legacyOrigin: process.env.WEBSITE_LEGACY_ORIGIN, publicOrigin: process.env.WEBSITE_PUBLIC_ORIGIN });
}

export async function editorialUpstreamOrigin(): Promise<string> {
  // Tests intentionally have no Next request scope; callers still exercise the
  // same origin resolver. Runtime failures never default to an upstream.
  let requestHeaders: Headers;
  try { requestHeaders = await headers(); }
  catch {
    if (process.env.NODE_ENV !== "test") throw new Error("Editorial request origin unavailable");
    requestHeaders = new Headers({ host: "localhost" });
  }
  const origin = legacyOriginForHeaders(requestHeaders);
  if (!origin) throw new Error("Independent editorial owner unavailable");
  return origin;
}
