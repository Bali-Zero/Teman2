import { NextRequest, NextResponse } from "next/server";
import { logger } from "@/lib/logger";

/**
 * POST /api/assessment/submit
 *
 * Receives block answers from the assessment page and forwards them
 * as an email to zero@balizero.com via the backend notification service.
 *
 * This route exists so the browser never needs the backend API key.
 * Temporary — will be removed after the assessment.
 */

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://nuzantara-rag.fly.dev";

const API_KEY = process.env.INTERNAL_API_KEY || process.env.API_KEY || "";

interface SubmitBody {
  to: string;
  subject: string;
  body: string;
}

export async function POST(request: NextRequest) {
  try {
    const payload: SubmitBody = await request.json();

    // Only allow sending to zero@balizero.com
    if (payload.to !== "zero@balizero.com") {
      return NextResponse.json({ error: "Invalid recipient" }, { status: 400 });
    }

    // Forward to backend
    const backendUrl = BACKEND_URL.replace(/\/+$/, "").replace(/\/api$/, "");
    const res = await fetch(`${backendUrl}/api/notifications/send-email`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({
        to: payload.to,
        subject: payload.subject,
        body: payload.body,
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      logger.error(`[assessment/submit] Backend error ${res.status}: ${text}`, {
        component: "assessment",
        action: "submit",
      });
      return NextResponse.json(
        { error: "Failed to send email", detail: text },
        { status: res.status },
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error("[assessment/submit] Error:", {
      component: "assessment",
      action: "submit",
      metadata: { error: String(error) },
    });
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
