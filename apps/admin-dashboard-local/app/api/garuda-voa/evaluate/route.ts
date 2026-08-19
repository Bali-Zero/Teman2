import { NextRequest, NextResponse } from "next/server";
import { isAllowedCockpitHost } from "@/lib/cockpit-host";
import { hasValidCockpitSession } from "@/lib/cockpit-session";
import { sameOriginJsonFailure } from "@/lib/cockpit-request-guard";
import {
  GARUDA_PREVIEW_MAX_REQUEST_BYTES,
  GarudaPreviewAdapterError,
  runGarudaPreview,
} from "@/lib/garuda-preview-adapter";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PRIVATE_HEADERS = {
  "cache-control": "no-store, max-age=0",
  "x-robots-tag": "noindex, nofollow, noarchive",
};

function privateJson(body: unknown, status: number = 200) {
  return NextResponse.json(body, { status, headers: PRIVATE_HEADERS });
}

export async function POST(request: NextRequest) {
  // Defense in depth: this route verifies both boundaries independently of
  // middleware, so matcher drift can never turn the engine into a public API.
  if (!isAllowedCockpitHost(request.headers.get("host"))) {
    return privateJson({ error: "forbidden" }, 403);
  }
  const guardFailure = sameOriginJsonFailure(request);
  if (guardFailure) {
    return privateJson({ error: guardFailure.error }, guardFailure.status);
  }
  if (!(await hasValidCockpitSession(request))) {
    return privateJson({ error: "unauthorized" }, 401);
  }

  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (
    Number.isFinite(declaredLength) &&
    declaredLength > GARUDA_PREVIEW_MAX_REQUEST_BYTES
  ) {
    return privateJson({ error: "request_too_large" }, 413);
  }

  const rawBody = await request.text();
  if (Buffer.byteLength(rawBody, "utf8") > GARUDA_PREVIEW_MAX_REQUEST_BYTES) {
    return privateJson({ error: "request_too_large" }, 413);
  }

  try {
    const result = await runGarudaPreview(rawBody);
    if ("ok" in result && result.ok === false) {
      const isOperatorInputError =
        result.error === "invalid_request" ||
        result.error === "request_too_large";
      return privateJson(
        { error: result.error ?? "invalid_request" },
        isOperatorInputError ? 400 : 503,
      );
    }
    return privateJson(result);
  } catch (error) {
    if (error instanceof GarudaPreviewAdapterError) {
      const status = error.code === "invalid_request" ? 400 : 503;
      return privateJson({ error: error.code }, status);
    }
    return privateJson({ error: "preview_unavailable" }, 503);
  }
}
