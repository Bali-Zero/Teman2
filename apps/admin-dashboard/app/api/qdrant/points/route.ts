import { NextResponse } from "next/server";
import { QdrantClient } from "@qdrant/js-client-rest";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const client = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const collection = searchParams.get("collection");
  const limit = 20;
  const offset = searchParams.get("offset");

  if (!collection) {
    return NextResponse.json({ error: "Collection required" }, { status: 400 });
  }

  try {
    const response = await client.scroll(collection, {
      limit,
      with_payload: true,
      with_vector: false,
      offset: offset || undefined,
    });

    return NextResponse.json(response);
  } catch (error) {
    logger.error("Qdrant Scroll Error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
