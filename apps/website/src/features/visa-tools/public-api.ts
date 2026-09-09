/** Narrow public adapter. Cookie-bound VOA and all authenticated operations stay with their owner. */
export type PublicVisaKind = "clock" | "match";
export const validReference = (value: string) =>
  /^[A-Za-z0-9_-]{1,200}$/.test(value);
const responseHeaders = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
};
const reply = (body: unknown, status = 200) =>
  Response.json(body, { status, headers: responseHeaders });
const isRecord = (v: unknown): v is Record<string, unknown> =>
  Boolean(v && typeof v === "object" && !Array.isArray(v));
const string = (v: unknown, max = 8000): v is string =>
  typeof v === "string" && v.length <= max;
const integer = (v: unknown, max = 1e12): v is number =>
  Number.isSafeInteger(v) && Number(v) >= 0 && Number(v) <= max;
const strings = (v: unknown): v is string[] =>
  Array.isArray(v) && v.length <= 40 && v.every((item) => string(item, 8000));
export function validDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value))
    return false;
  const date = new Date(`${value}T00:00:00Z`);
  return (
    Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
  );
}
function inputFor(
  kind: PublicVisaKind,
  value: unknown,
): Record<string, unknown> | null {
  if (!isRecord(value)) return null;
  if (kind === "clock") {
    if (
      Object.keys(value).some(
        (key) => !["visa_type", "entry_date", "in_country_now"].includes(key),
      ) ||
      !string(value.visa_type, 12) ||
      !/^[A-Z0-9]+$/.test(value.visa_type) ||
      !validDate(value.entry_date) ||
      value.in_country_now !== true
    )
      return null;
    return {
      visa_type: value.visa_type,
      entry_date: value.entry_date,
      in_country_now: true,
    };
  }
  if (
    Object.keys(value).some(
      (key) =>
        !["nationality", "purpose", "duration_months", "budget_band"].includes(
          key,
        ),
    ) ||
    typeof value.nationality !== "string" ||
    !/^[A-Z]{2,3}$/.test(value.nationality) ||
    ![
      "work_remote",
      "investor",
      "work_employee",
      "family",
      "long_tourism",
      "retirement",
      "student",
      "other",
    ].includes(String(value.purpose)) ||
    !integer(value.duration_months, 60) ||
    value.duration_months < 1 ||
    !["under_50m", "50m_500m", "over_500m"].includes(String(value.budget_band))
  )
    return null;
  return {
    nationality: value.nationality,
    purpose: value.purpose,
    duration_months: value.duration_months,
    budget_band: value.budget_band,
  };
}
export interface ClockResult {
  hash: string;
  visa_type: string;
  entry_date: string;
  expiry_date: string;
  extensions_possible: number;
  extension_days: number;
  checkpoints: { label: string; at: string; title: string; body: string }[];
}
export interface MatchResult {
  hash: string;
  recommended_visa: string | null;
  reason: string;
  estimated_cost_idr: number | null;
  cost_source: string | null;
  processing_days: number | null;
  pre_arrival_steps: string[];
  alternatives: string[];
  referral_mode: boolean;
  nationality: string;
  purpose: string;
  duration_months: number;
  budget_band: string;
}
export function projectResult(
  kind: PublicVisaKind,
  value: unknown,
  reference: string,
): ClockResult | MatchResult | null {
  if (!isRecord(value) || value.hash !== reference) return null;
  if (kind === "clock") {
    if (
      !string(value.visa_type, 20) ||
      !validDate(value.entry_date) ||
      !validDate(value.expiry_date) ||
      !integer(value.extensions_possible, 100) ||
      !integer(value.extension_days, 3650) ||
      !Array.isArray(value.checkpoints) ||
      value.checkpoints.length > 40 ||
      !value.checkpoints.every(
        (cp) =>
          isRecord(cp) &&
          string(cp.label, 100) &&
          validDate(cp.at) &&
          string(cp.title, 500) &&
          string(cp.body),
      )
    )
      return null;
    return {
      hash: reference,
      visa_type: value.visa_type,
      entry_date: value.entry_date,
      expiry_date: value.expiry_date,
      extensions_possible: value.extensions_possible,
      extension_days: value.extension_days,
      checkpoints: value.checkpoints.map((cp) => ({
        label: cp.label,
        at: cp.at,
        title: cp.title,
        body: cp.body,
      })),
    };
  }
  if (
    !(value.recommended_visa === null || string(value.recommended_visa, 30)) ||
    !string(value.reason) ||
    !(value.estimated_cost_idr === null || integer(value.estimated_cost_idr)) ||
    !(value.cost_source === null || string(value.cost_source, 200)) ||
    !(value.processing_days === null || integer(value.processing_days, 1000)) ||
    !strings(value.pre_arrival_steps) ||
    !strings(value.alternatives) ||
    typeof value.referral_mode !== "boolean" ||
    !string(value.nationality, 3) ||
    !string(value.purpose, 80) ||
    !integer(value.duration_months, 60) ||
    !string(value.budget_band, 80)
  )
    return null;
  return {
    hash: reference,
    recommended_visa: value.recommended_visa,
    reason: value.reason,
    estimated_cost_idr: value.estimated_cost_idr,
    cost_source: value.cost_source,
    processing_days: value.processing_days,
    pre_arrival_steps: value.pre_arrival_steps,
    alternatives: value.alternatives,
    referral_mode: value.referral_mode,
    nationality: value.nationality,
    purpose: value.purpose,
    duration_months: value.duration_months,
    budget_band: value.budget_band,
  };
}
async function readBounded(
  body: ReadableStream<Uint8Array> | null,
  maximum: number,
) {
  if (!body) throw new Error("Empty body");
  const reader = body.getReader();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    void reader.cancel().catch(() => {});
  }, 8000);
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (timedOut) throw new Error("Body timed out");
      if (part.done) break;
      size += part.value.byteLength;
      if (size > maximum) {
        await reader.cancel();
        throw new Error("Body too large");
      }
      chunks.push(part.value);
    }
  } finally {
    clearTimeout(timer);
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  return JSON.parse(
    new TextDecoder("utf-8", { fatal: true }).decode(bytes),
  ) as unknown;
}
function configuredBase(): URL | null {
  const raw = process.env.WEBSITE_VISA_PUBLIC_BASE_URL;
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (
      (url.protocol !== "https:" && !(local && url.protocol === "http:")) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      url.pathname !== "/"
    )
      return null;
    return url;
  } catch {
    return null;
  }
}
export async function publicVisaRequest(
  request: Request,
  kind: PublicVisaKind,
  reference?: string,
): Promise<Response> {
  const post = request.method === "POST";
  if (
    (post && reference) ||
    (!post && request.method !== "GET") ||
    (!post && !reference) ||
    (reference && !validReference(reference))
  )
    return reply({ error: "Not found" }, 404);
  if (
    post &&
    (request.headers.get("origin") !== new URL(request.url).origin ||
      request.headers.get("sec-fetch-site") === "cross-site")
  )
    return reply({ error: "Same-origin request required" }, 403);
  const base = configuredBase();
  if (!base)
    return reply(
      {
        error:
          "The public visa service is not connected in this preview. No check was submitted.",
      },
      503,
    );
  let body: Record<string, unknown> | null = null;
  if (post) {
    if (
      !request.headers
        .get("content-type")
        ?.toLowerCase()
        .startsWith("application/json")
    )
      return reply({ error: "JSON required" }, 415);
    try {
      body = inputFor(kind, await readBounded(request.body, 4096));
    } catch {
      return reply({ error: "Invalid or oversized request" }, 400);
    }
    if (!body) return reply({ error: "Invalid public answers" }, 400);
  }
  const url = new URL(
    `/api/visa/${kind}${reference ? `/${reference}` : ""}`,
    base,
  );
  try {
    const response = await fetch(url, {
      method: post ? "POST" : "GET",
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(8000),
      headers: {
        Accept: "application/json",
        ...(post ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok)
      return reply(
        {
          error:
            response.status === 404
              ? "This result is unavailable or has expired."
              : "The visa service could not complete this request.",
        },
        response.status === 404 ? 404 : response.status === 429 ? 429 : 503,
      );
    const result = await readBounded(response.body, 65536);
    if (post) {
      if (
        !isRecord(result) ||
        typeof result.hash !== "string" ||
        !validReference(result.hash)
      )
        throw new Error("Invalid result reference");
      return reply({ hash: result.hash }, response.status === 201 ? 201 : 200);
    }
    const projected = projectResult(kind, result, reference!);
    if (!projected) throw new Error("Invalid result shape");
    return reply(projected);
  } catch {
    return reply(
      { error: "The visa service is unavailable. No result can be confirmed." },
      503,
    );
  }
}
