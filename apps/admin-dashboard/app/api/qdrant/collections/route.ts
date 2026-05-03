import { NextResponse } from "next/server";
import { QdrantClient } from "@qdrant/js-client-rest";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const client = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY,
});

export async function GET() {
  try {
    const response = await client.getCollections();

    // Enrich with info if possible (count)
    const collectionsWithStats = await Promise.all(
      response.collections.map(async (col) => {
        try {
          const info = await client.getCollection(col.name);
          return {
            name: col.name,
            vectors_count: info.points_count,
            status: info.status,
          };
        } catch (e) {
          return { name: col.name, error: "Failed to fetch details" };
        }
      }),
    );

    return NextResponse.json({ collections: collectionsWithStats });
  } catch (error) {
    logger.error("Qdrant Collections Error:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : String(error),
        details:
          error instanceof Error && error.cause
            ? String(error.cause)
            : undefined,
        url: process.env.QDRANT_URL,
      },
      { status: 500 },
    );
  }
}
