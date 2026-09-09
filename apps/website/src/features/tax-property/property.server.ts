import {
  parseAnalyzeInput,
  projectAnalysis,
  projectZones,
  record,
  textValue,
  numberValue,
} from "./property-contract";

const responseHeaders = {
  "Cache-Control": "no-store",
  "X-Robots-Tag": "noindex, nofollow",
  "Referrer-Policy": "no-referrer",
};
function json(value: unknown, status = 200): Response {
  return Response.json(value, { status, headers: responseHeaders });
}
function sameOrigin(request: Request): boolean {
  return (
    request.headers.get("origin") === new URL(request.url).origin &&
    request.headers.get("sec-fetch-site") !== "cross-site"
  );
}
class PropertyUpstreamError extends Error {
  constructor(readonly status: number) {
    super("Property service unavailable");
  }
}
export function propertyOrigin(
  setting = process.env.WEBSITE_PROPERTY_API_ORIGIN,
): string | null {
  try {
    if (!setting) return null;
    const url = new URL(setting);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash ||
      (url.protocol !== "https:" && !(local && url.protocol === "http:"))
    )
      return null;
    return url.origin;
  } catch {
    return null;
  }
}
async function boundedJson(
  response: Response,
  limit = 2_000_000,
): Promise<unknown> {
  if (!response.ok) throw new PropertyUpstreamError(response.status);
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw new Error("Unavailable");
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Unavailable");
  let bytes = 0;
  const decoder = new TextDecoder();
  let body = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > limit) throw new Error("Response too large");
      body += decoder.decode(value, { stream: true });
    }
  } finally {
    await reader.cancel();
  }
  return JSON.parse(body + decoder.decode());
}
async function upstream(
  path: string,
  init: RequestInit = {},
  limit?: number,
): Promise<unknown> {
  const origin = propertyOrigin();
  if (!origin) throw new Error("Not configured");
  const response = await fetch(`${origin}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
    headers: {
      Accept: "application/json",
      ...(init.method === "POST" ? { "Content-Type": "application/json" } : {}),
    },
  });
  return boundedJson(response, limit);
}
export async function analyzeProperty(request: Request): Promise<Response> {
  if (request.method !== "POST")
    return json({ error: "method_not_allowed" }, 405);
  if (!sameOrigin(request)) return json({ error: "same_origin_required" }, 403);
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return json({ error: "json_required" }, 415);
  if (Number(request.headers.get("content-length") ?? 0) > 4096)
    return json({ error: "body_too_large" }, 413);
  let body: unknown;
  try {
    const reader = request.body?.getReader();
    if (!reader) return json({ error: "invalid_input" }, 400);
    const decoder = new TextDecoder();
    let raw = "",
      size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 4096) return json({ error: "body_too_large" }, 413);
        raw += decoder.decode(value, { stream: true });
      }
    } finally {
      await reader.cancel();
    }
    body = JSON.parse(raw + decoder.decode());
  } catch {
    return json({ error: "invalid_input" }, 400);
  }
  const input = parseAnalyzeInput(body);
  if (!input) return json({ error: "invalid_input" }, 400);
  if (!propertyOrigin()) return json({ error: "not_configured" }, 503);
  try {
    const data = projectAnalysis(
      await upstream("/api/prime/v2/analyze", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    );
    if (!["analyzed", "outside_coverage"].includes(data.status))
      return json({ error: "analysis_unavailable" }, 502);
    return json(data);
  } catch {
    return json({ error: "analysis_unavailable" }, 502);
  }
}
export async function getPropertyZones(): Promise<Response> {
  if (!propertyOrigin()) return json({ error: "not_configured" }, 503);
  try {
    return json(
      projectZones(await upstream("/api/prime/zones-geojson", {}, 20_000_000)),
    );
  } catch {
    return json({ error: "map_unavailable" }, 502);
  }
}
/** Upstream GET marks viewed_at. Locally only a same-origin POST opens a proposal;
 * browser prefetch, crawlers, HEAD and cross-site requests cannot mark it viewed. */
export async function openPropertyProposal(
  request: Request,
  context: { params: Promise<{ token: string }> },
): Promise<Response> {
  if (request.method !== "POST")
    return json({ error: "method_not_allowed" }, 405);
  if (!sameOrigin(request)) return json({ error: "same_origin_required" }, 403);
  const { token } = await context.params;
  if (!/^[A-Za-z0-9_-]{6,160}$/.test(token))
    return json({ error: "not_found" }, 404);
  if (!propertyOrigin()) return json({ error: "not_configured" }, 503);
  try {
    const source = record(
      await upstream(`/api/prime/v2/proposal/${encodeURIComponent(token)}`),
    );
    if (source.error)
      return json(
        { error: source.error === "expired" ? "expired" : "not_found" },
        source.error === "expired" ? 410 : 404,
      );
    if (
      numberValue(source.lat) === null ||
      numberValue(source.lng) === null ||
      !textValue(source.zone_code)
    )
      return json({ error: "not_found" }, 404);
    return json({
      lat: source.lat,
      lng: source.lng,
      zone_code: textValue(source.zone_code),
      zone_name: textValue(source.zone_name),
      kbli_code: textValue(source.kbli_code),
      verdict_label: textValue(source.verdict_label),
      verdict_score: numberValue(source.verdict_score),
      created_at: textValue(source.created_at),
      expires_at: textValue(source.expires_at),
      status: textValue(source.status),
      analysis: projectAnalysis(source.analysis),
    });
  } catch (error) {
    if (
      error instanceof PropertyUpstreamError &&
      [404, 410].includes(error.status)
    )
      return json(
        { error: error.status === 410 ? "expired" : "not_found" },
        error.status,
      );
    return json({ error: "proposal_unavailable" }, 502);
  }
}
