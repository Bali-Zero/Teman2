import { NextResponse } from "next/server";
import { QdrantClient } from "@qdrant/js-client-rest";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const COLLECTION = "legal_unified_hybrid";

const client = new QdrantClient({
  url: process.env.QDRANT_URL,
  apiKey: process.env.QDRANT_API_KEY,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get("limit") || "50"), 100);
  const offsetParam = searchParams.get("offset");
  const search = searchParams.get("search") || "";
  const regulationType = searchParams.get("regulation_type") || "";

  try {
    // Build filter
    const mustConditions: Record<string, unknown>[] = [];

    if (regulationType) {
      mustConditions.push({
        key: "regulation_type",
        match: { value: regulationType },
      });
    }

    if (search) {
      // Text search on the text field
      mustConditions.push({
        key: "text",
        match: { text: search },
      });
    }

    const filter =
      mustConditions.length > 0 ? { must: mustConditions } : undefined;

    // Use scroll for pagination
    const scrollParams: Record<string, unknown> = {
      limit,
      with_payload: true,
      with_vector: false,
      filter,
    };

    // Handle offset (Qdrant uses point ID for offset in scroll)
    if (offsetParam && !isNaN(parseInt(offsetParam))) {
      // For numeric offset, we skip by making multiple small scrolls
      // This is a workaround since Qdrant scroll uses point_id not numeric offset
      // For simplicity, we'll use a different approach: limit + skip simulation
      const skipCount = parseInt(offsetParam);

      // Get all up to offset + limit
      const bigScroll = await client.scroll(COLLECTION, {
        limit: skipCount + limit,
        with_payload: true,
        with_vector: false,
        filter,
      });

      const chunks = bigScroll.points.slice(skipCount).map((point) => {
        const payload = point.payload as Record<string, unknown>;
        return {
          id: point.id,
          text: payload?.text || "",
          regulation_type: payload?.regulation_type || "",
          document_number: payload?.document_number || payload?.number || "",
          year: payload?.year || 0,
          pasal: payload?.pasal || payload?.article_number || null,
          ayat: payload?.ayat || null,
          huruf: payload?.huruf || null,
          doc_title: payload?.doc_title || payload?.title || null,
          hierarchy_path: payload?.hierarchy_path || null,
          chunk_type: payload?.chunk_type || null,
          section_title: payload?.section_title || null,
          metadata: payload,
        };
      });

      return NextResponse.json({ chunks });
    }

    // Normal scroll from start
    const result = await client.scroll(COLLECTION, scrollParams);

    const chunks = result.points.map((point) => {
      const payload = point.payload as Record<string, unknown>;
      return {
        id: point.id,
        text: payload?.text || "",
        regulation_type: payload?.regulation_type || "",
        document_number: payload?.document_number || payload?.number || "",
        year: payload?.year || 0,
        pasal: payload?.pasal || payload?.article_number || null,
        ayat: payload?.ayat || null,
        huruf: payload?.huruf || null,
        doc_title: payload?.doc_title || payload?.title || null,
        hierarchy_path: payload?.hierarchy_path || null,
        chunk_type: payload?.chunk_type || null,
        section_title: payload?.section_title || null,
        metadata: payload,
      };
    });

    return NextResponse.json({
      chunks,
      next_offset: result.next_page_offset,
    });
  } catch (error) {
    logger.error("Legal Chunks Error:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : String(error),
        collection: COLLECTION,
      },
      { status: 500 },
    );
  }
}
