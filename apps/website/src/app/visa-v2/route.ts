import type { NextRequest } from "next/server";
export function GET(_request: NextRequest) {
  return new Response(null, {
    status: 308,
    headers: {
      Location: "/visa-oracle",
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
    },
  });
}
export const HEAD = GET;
