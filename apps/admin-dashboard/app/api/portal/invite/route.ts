import { NextResponse } from "next/server";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * The backend keys client invitations on an integer primary key
 * (`portal_invite.py::get_client_invitations(client_id: int)`), so anything that is
 * not a plain positive integer is not a client id — it is a path segment trying to
 * escape the endpoint it was interpolated into.
 *
 * Without this, `?clientId=../../../../<path>` is normalised away by `fetch` and the
 * proxy calls an arbitrary backend route while forwarding the caller's authorization
 * and cookie headers (CodeQL js/request-forgery, alert #8318).
 */
export function isValidClientId(raw: string | null): raw is string {
  return raw !== null && /^[1-9][0-9]{0,17}$/.test(raw);
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const authHeader = request.headers.get("authorization") ?? "";
    const cookieHeader = request.headers.get("cookie") ?? "";

    const res = await fetch(`${BACKEND_URL}/api/portal/invite/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authHeader ? { authorization: authHeader } : {}),
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    logger.error("Portal invite proxy error:", error);
    return NextResponse.json(
      { error: "Failed to send invitation" },
      { status: 500 },
    );
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const clientId = searchParams.get("clientId");
    if (!isValidClientId(clientId)) {
      return NextResponse.json(
        { error: "clientId must be a positive integer" },
        { status: 400 },
      );
    }

    const authHeader = request.headers.get("authorization") ?? "";
    const cookieHeader = request.headers.get("cookie") ?? "";

    const res = await fetch(
      `${BACKEND_URL}/api/portal/invite/client/${clientId}`,
      {
        headers: {
          ...(authHeader ? { authorization: authHeader } : {}),
          ...(cookieHeader ? { cookie: cookieHeader } : {}),
        },
      },
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    logger.error("Portal invite history proxy error:", error);
    return NextResponse.json(
      { error: "Failed to fetch invite history" },
      { status: 500 },
    );
  }
}
