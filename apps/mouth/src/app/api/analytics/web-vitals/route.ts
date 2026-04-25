import { NextResponse } from "next/server";
import { logger } from "@/lib/logger";

/**
 * Ingest endpoint for client-side Core Web Vitals beacons.
 *
 * Kept intentionally minimal: we log each metric and return 204. A downstream
 * pipeline (Grafana / BigQuery / custom store) can subscribe to the log stream
 * or be plugged in here. This keeps the PR self-contained while giving us a
 * stable endpoint the frontend can target.
 *
 * The endpoint is a no-op in development.
 */

export const runtime = "edge";
export const dynamic = "force-dynamic";

const ALLOWED_METRICS = new Set(["CLS", "INP", "LCP", "TTFB", "FCP", "FID"]);
const ALLOWED_RATINGS = new Set(["good", "needs-improvement", "poor"]);

interface Payload {
  name?: string;
  value?: number;
  rating?: string;
  id?: string;
  navigationType?: string;
  url?: string;
}

export async function POST(request: Request) {
  let body: Payload;
  try {
    body = (await request.json()) as Payload;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  if (
    !body.name ||
    typeof body.value !== "number" ||
    !ALLOWED_METRICS.has(body.name) ||
    (body.rating && !ALLOWED_RATINGS.has(body.rating))
  ) {
    return NextResponse.json({ ok: false, error: "invalid_metric" }, { status: 400 });
  }

  logger.info("[web-vitals]", {
    component: "WebVitalsAPI",
    action: "metric",
    metadata: {
      metric: body.name,
      value: body.value,
      rating: body.rating ?? "unknown",
      url: body.url ?? request.headers.get("referer") ?? null,
      id: body.id ?? null,
      navigationType: body.navigationType ?? null,
    },
  });

  return new Response(null, { status: 204 });
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "web-vitals",
    hint: "POST a { name, value, rating, id, navigationType, url } payload.",
  });
}
