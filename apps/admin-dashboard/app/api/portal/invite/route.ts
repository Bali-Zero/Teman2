import { NextResponse } from "next/server";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

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
    if (!clientId) {
      return NextResponse.json({ error: "clientId required" }, { status: 400 });
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
