import { parseStrictJson, VISA_ORACLE_MAX_RESPONSE_BYTES } from "./_lib/strict-json";

const MAX_REQUEST = 32 * 1024;
const KEY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const HEADERS = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" };

/** Server configuration only. There is deliberately no production fallback. */
export function oracleBackendUrl(value: string | undefined): URL | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.username || url.password || url.search || url.hash || url.pathname !== "/") return null;
    if (url.protocol !== "https:" && !(url.protocol === "http:" && isLoopback(url))) return null;
    return url;
  } catch { return null; }
}

export function isLoopback(url: URL): boolean {
  return ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
}

function failure(status: number): Response {
  return Response.json({ error: "Visa Oracle evaluation unavailable", status }, { status, headers: HEADERS });
}

async function readBounded(body: ReadableStream<Uint8Array> | null, limit: number): Promise<string> {
  if (!body) return "";
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let size = 0, result = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel(); throw new RangeError("body limit"); }
      result += decoder.decode(value, { stream: true });
    }
    return result + decoder.decode();
  } finally { reader.releaseLock(); }
}

/** Anonymous same-origin boundary. Only the idempotency key and JSON cross it.
 * The canonical client validates the complete response, including malformed-200
 * human-review semantics. The real backend owns request DTO validation.
 */
export async function forwardOracleEvaluation(
  request: Request,
  backendOrigin = process.env.WEBSITE_VISA_ORACLE_BACKEND_URL,
  fetchImpl: typeof fetch = fetch,
  proofLane = process.env.WEBSITE_VISA_ORACLE_LOCAL_PROOF,
): Promise<Response> {
  if (request.method !== "POST") return failure(405);
  const incoming = new URL(request.url);
  const origin = request.headers.get("origin");
  // Next may construct request.url from its internal listener hostname.
  // Host is the browser's actual target authority; do not trust forwarded-host.
  const host = request.headers.get("host") ?? incoming.host;
  if (origin) {
    try {
      const caller = new URL(origin);
      if (caller.origin !== origin || caller.host !== host || caller.protocol !== incoming.protocol) return failure(403);
    } catch { return failure(403); }
  }
  if (request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !== "application/json") return failure(415);
  const key = request.headers.get("idempotency-key");
  if (!key || !KEY.test(key)) return failure(400);
  const length = request.headers.get("content-length");
  if (length && !/^\d+$/.test(length)) return failure(400);
  if (length && Number(length) > MAX_REQUEST) return failure(413);
  let body: string;
  try {
    body = await readBounded(request.body, MAX_REQUEST);
    const parsed = parseStrictJson(body, MAX_REQUEST);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return failure(400);
  } catch (error) { return failure(error instanceof RangeError ? 413 : 400); }
  const backend = oracleBackendUrl(backendOrigin);
  if (proofLane && (proofLane !== "unsigned-proposal" || !backend || !isLoopback(backend))) return failure(503);
  if (!backend || backend.origin === incoming.origin || backend.origin === `${incoming.protocol}//${host}` ||
      (isLoopback(backend) && isLoopback(incoming) && backend.port === incoming.port)) return failure(503);
  const url = new URL("/api/visa-oracle/evaluate?traffic_source=real", backend);
  const timeout = AbortSignal.timeout(10_000);
  try {
    const response = await fetchImpl(url, {
      method: "POST", body,
      headers: { "Content-Type": "application/json", Accept: "application/json", "Idempotency-Key": key },
      redirect: "manual", cache: "no-store", credentials: "omit",
      signal: AbortSignal.any([request.signal, timeout]),
    });
    if (response.status >= 300 && response.status < 400) { await response.body?.cancel(); return failure(502); }
    if (response.status !== 200) { await response.body?.cancel(); return failure(response.status >= 400 ? response.status : 502); }
    const proof = response.headers.get("X-Visa-Local-Proof");
    const unsigned = proof === "unsigned-proposal-no-db-test-seal";
    // Explicit local-only lane: an unsigned response cannot be presented by
    // the reference preview, or silently substituted when proposal is selected.
    if ((proofLane === "unsigned-proposal") !== unsigned) {
      await response.body?.cancel(); return failure(502);
    }
    const result = await readBounded(response.body, VISA_ORACLE_MAX_RESPONSE_BYTES);
    const json = response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() === "application/json";
    return new Response(result, { status: 200, headers: { ...HEADERS, "Content-Type": json ? "application/json" : "text/plain", ...(isLoopback(backend) && proof ? { "X-Visa-Local-Proof": proof } : {}) } });
  } catch { return failure(timeout.aborted ? 504 : 502); }
}
