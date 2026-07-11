import { NextResponse } from "next/server";
import {
  postAutonomousLabCancel,
  type LabCancelMutationPayload,
} from "@/lib/autonomous-lab";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ runId: string }> | { runId: string };
};

export async function POST(request: Request, context: RouteContext) {
  const { runId } = await context.params;
  try {
    const payload = (await request.json()) as LabCancelMutationPayload;
    const result = await postAutonomousLabCancel(runId, payload);
    return NextResponse.json(result);
  } catch (error) {
    logger.error("Autonomous Lab cancel proxy error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "request failed" },
      { status: 502 },
    );
  }
}
