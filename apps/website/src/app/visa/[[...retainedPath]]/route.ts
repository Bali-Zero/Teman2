import type { NextRequest } from "next/server";
import { retainedHandoff } from "../../../lib/server/retained-handoff";

export function GET(request: NextRequest) {
  if (new URL(request.url).pathname.replace(/\/$/, "") === "/visa") return new Response(null, { status: 307, headers: { Location: "/visa-oracle", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
  return retainedHandoff(request);
}
export const HEAD = GET;
