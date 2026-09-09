import { retainedApiPaths, retainedPath } from "../retained-routes";
import { legacyOriginForHeaders } from "./legacy-origin";

const responseHeaders = {
  "cache-control": "no-store", "referrer-policy": "no-referrer",
  "x-robots-tag": "noindex, nofollow, noarchive",
};

export function retainedHandoff(request: Request): Response {
  if (!["GET", "HEAD"].includes(request.method)) return new Response(null, { status: 405, headers: { ...responseHeaders, allow: "GET, HEAD" } });
  const url = new URL(request.url);
  const path = retainedPath(url.pathname);
  if (!path) return new Response(null, { status: 404, headers: responseHeaders });
  if (path.startsWith("/static/") && (url.search || url.hash)) return new Response(null, { status: 404, headers: responseHeaders });
  const origin = legacyOriginForHeaders(request.headers, request.url);
  if (!origin) {
    const html = '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Continue with Bali Zero</title><style>body{margin:0;background:#F7F4EE;color:#1D2C3B;font:18px/1.7 system-ui}main{max-width:42rem;padding:12vh 24px;margin:auto}a{color:#A44B36;text-underline-offset:4px}h1{font:2.5rem/1.2 Georgia,serif}a{display:inline-block;padding:12px 0}</style><main><p>BALI ZERO</p><h1>This service is temporarily unavailable here.</h1><p>We cannot open the service safely from this address. Your application or saved plan has not been changed.</p><p><a href="/contact">Contact the team for help</a></p><p><a href="/services">Explore services</a></p></main></html>';
    return new Response(request.method === "HEAD" ? null : html, { status: 503, headers: { ...responseHeaders, "content-type": "text/html; charset=utf-8", "retry-after": "300" } });
  }
  const target = new URL(path + url.search + url.hash, origin);
  return new Response(null, { status: 307, headers: { ...responseHeaders, location: target.href } });
}

export function retainedApiUnavailable(request: Request): Response {
  const known = retainedApiPaths.some((pattern) => pattern.test(new URL(request.url).pathname));
  if (request.method === "HEAD") return new Response(null, { status: known ? 503 : 404, headers: responseHeaders });
  return Response.json({ error: known ? "This operation is available only in the owning product application." : "Unknown operation.", code: known ? "PRODUCT_OWNER_REQUIRED" : "NOT_FOUND" }, { status: known ? 503 : 404, headers: responseHeaders });
}
