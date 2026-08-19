import type { NextRequest } from "next/server";

export type SameOriginJsonFailure = {
  error: "json_required" | "cross_site_request";
  status: 403 | 415;
};

export function sameOriginJsonFailure(
  request: NextRequest,
): SameOriginJsonFailure | null {
  const mediaType = request.headers
    .get("content-type")
    ?.split(";", 1)[0]
    ?.trim()
    .toLowerCase();
  if (mediaType !== "application/json") {
    return { error: "json_required", status: 415 };
  }

  const origin = request.headers.get("origin");
  if (origin !== null && origin !== request.nextUrl.origin) {
    return { error: "cross_site_request", status: 403 };
  }

  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite !== null && fetchSite.toLowerCase() !== "same-origin") {
    return { error: "cross_site_request", status: 403 };
  }
  return null;
}
