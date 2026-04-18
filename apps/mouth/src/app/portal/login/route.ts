import type { NextRequest } from "next/server";
import { sanitizeRedirect } from "@/lib/auth/sanitizeRedirect";

export function GET(request: NextRequest): Response {
  const raw = request.nextUrl.searchParams.get("redirect");
  const safe = sanitizeRedirect(raw);
  const qs = safe ? `?redirect=${encodeURIComponent(safe)}` : "";
  const target = new URL(`/portal/login-upgraded${qs}`, request.nextUrl.origin);
  return Response.redirect(target, 308);
}
