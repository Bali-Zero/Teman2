import { NextResponse } from "next/server";
import { QdrantClient } from "@qdrant/js-client-rest";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const COLLECTION = "legal_unified_hybrid";

const client = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY,
});

export async function GET() {
  try {
    // Get collection info for total count
    const info = await client.getCollection(COLLECTION);
    const totalChunks = info.points_count || 0;

    // Sample points to build stats (we can't aggregate in Qdrant, so we sample)
    const sampleSize = 1000;
    const sample = await client.scroll(COLLECTION, {
      limit: sampleSize,
      with_payload: ["regulation_type", "year"],
      with_vector: false,
    });

    const byType: Record<string, number> = {};
    const byYear: Record<string, number> = {};

    for (const point of sample.points) {
      const payload = point.payload as Record<string, unknown>;

      const regType = String(payload?.regulation_type || "UNKNOWN");
      byType[regType] = (byType[regType] || 0) + 1;

      const year = payload?.year ? String(payload.year) : "UNKNOWN";
      byYear[year] = (byYear[year] || 0) + 1;
    }

    // Scale up if we sampled less than total
    const scaleFactor = totalChunks / Math.max(sample.points.length, 1);
    if (scaleFactor > 1) {
      for (const key of Object.keys(byType)) {
        byType[key] = Math.round(byType[key] * scaleFactor);
      }
      for (const key of Object.keys(byYear)) {
        byYear[key] = Math.round(byYear[key] * scaleFactor);
      }
    }

    return NextResponse.json({
      stats: {
        total_chunks: totalChunks,
        by_regulation_type: byType,
        by_year: byYear,
      },
    });
  } catch (error) {
    logger.error("Legal Stats Error:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : String(error),
        collection: COLLECTION,
      },
      { status: 500 },
    );
  }
}
