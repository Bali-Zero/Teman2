import type { ExplorerReply } from "./types";

const MAX_RESPONSE = 200_000;
const headers = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};
function fail(status: number, error: string): Response {
  return Response.json({ error }, { status, headers });
}

export function kbliBackendOrigin(
  raw = process.env.WEBSITE_KBLI_BACKEND_URL,
): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (
      (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    )
      return null;
    return url.origin;
  } catch {
    return null;
  }
}

function string(value: unknown, max: number): string | null {
  return typeof value === "string" && value.length <= max ? value : null;
}
export function normalizeReply(value: unknown): ExplorerReply | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const answer = string(record.answer, 60_000);
  if (
    !answer?.trim() ||
    !Array.isArray(record.detected_kbli) ||
    !Array.isArray(record.suggested_queries) ||
    !Array.isArray(record.sources)
  )
    return null;
  if (
    record.detected_kbli.length > 50 ||
    record.suggested_queries.length > 20 ||
    record.sources.length > 50
  )
    return null;
  const codes = record.detected_kbli.filter(
    (code): code is string => typeof code === "string" && /^\d{5}$/.test(code),
  );
  const suggestions = record.suggested_queries.filter(
    (query): query is string =>
      typeof query === "string" && query.length > 0 && query.length <= 1000,
  );
  const sources: ExplorerReply["sources"] = [];
  for (const entry of record.sources.slice(0, 12)) {
    if (!entry || typeof entry !== "object") continue;
    const source = entry as Record<string, unknown>;
    const metadata =
      source.metadata && typeof source.metadata === "object"
        ? (source.metadata as Record<string, unknown>)
        : {};
    const content = string(source.content, 20_000);
    if (!content) continue;
    const code =
      typeof metadata.kode_kbli === "string" &&
      /^\d{5}$/.test(metadata.kode_kbli)
        ? metadata.kode_kbli
        : undefined;
    sources.push({
      label:
        string(metadata.judul, 500) ||
        string(metadata.source, 500) ||
        "Retrieved source",
      code,
      content,
    });
  }
  return {
    answer,
    detected_kbli: [...new Set(codes)],
    suggested_queries: suggestions.slice(0, 5),
    sources,
  };
}

export async function handleExplorerChat(request: Request): Promise<Response> {
  const origin = request.headers.get("origin");
  if (
    request.headers.get("sec-fetch-site") === "cross-site" ||
    (origin && origin !== new URL(request.url).origin)
  )
    return fail(403, "This request must start from the KBLI Explorer.");
  if (
    !request.headers
      .get("content-type")
      ?.toLowerCase()
      .startsWith("application/json")
  )
    return fail(415, "Use a JSON request.");
  const backend = kbliBackendOrigin();
  if (!backend || backend === new URL(request.url).origin)
    return fail(
      503,
      "Assisted answers are currently unavailable. Search or inspect the activity directory instead.",
    );
  try {
    if (Number(request.headers.get("content-length")) > 16_000)
      return fail(413, "The question is too long.");
    const reader = request.body?.getReader();
    if (!reader) return fail(400, "Enter a question.");
    let body = "";
    let size = 0;
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 16_000) {
        await reader.cancel();
        return fail(413, "The question is too long.");
      }
      body += decoder.decode(value, { stream: true });
    }
    body += decoder.decode();
    let input: unknown;
    try {
      input = JSON.parse(body);
    } catch {
      return fail(400, "The request is not valid JSON.");
    }
    const query =
      input && typeof input === "object"
        ? (input as Record<string, unknown>).query
        : undefined;
    if (typeof query !== "string" || !query.trim() || query.length > 4000)
      return fail(400, "Enter a question of up to 4,000 characters.");
    const upstream = await fetch(`${backend}/api/v1/kbli-notebook/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ query: query.trim() }),
      credentials: "omit",
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(20_000)]),
    });
    if (
      !upstream.ok ||
      !upstream.headers.get("content-type")?.includes("application/json")
    )
      return fail(
        502,
        "The assisted answer could not be retrieved. Your question has not produced a result.",
      );
    const stream = upstream.body?.getReader();
    if (!stream) return fail(502, "The answer was empty.");
    let payload = "";
    let bytes = 0;
    const decode = new TextDecoder();
    while (true) {
      const { done, value } = await stream.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_RESPONSE) {
        await stream.cancel();
        return fail(502, "The answer could not be safely displayed.");
      }
      payload += decode.decode(value, { stream: true });
    }
    payload += decode.decode();
    let parsed: unknown;
    try {
      parsed = JSON.parse(payload);
    } catch {
      return fail(502, "The answer format could not be read.");
    }
    const reply = normalizeReply(parsed);
    return reply
      ? Response.json(reply, { headers })
      : fail(502, "The answer format could not be read.");
  } catch {
    return fail(
      502,
      "The assisted answer is unavailable. Try again or use the activity directory.",
    );
  }
}
