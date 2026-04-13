import { NextResponse } from "next/server";
import { OpenAI } from "openai";
import { QdrantClient } from "@qdrant/js-client-rest";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const {
      query,
      collection = "knowledge_base",
      limit = 5,
    } = await request.json();

    if (!query) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 });
    }

    // Initialize clients lazily to prevent build-time errors when secrets are missing
    const openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });

    const qdrant = new QdrantClient({
      url: process.env.QDRANT_URL,
      apiKey: process.env.QDRANT_API_KEY,
    });

    // 1. Generate Embedding
    const embeddingResponse = await openai.embeddings.create({
      model: "text-embedding-3-small",
      input: query,
    });
    const vector = embeddingResponse.data[0].embedding;

    // 2. Search in Qdrant
    const searchResult = await qdrant.search(collection, {
      vector: vector,
      limit: limit,
      with_payload: true,
    });

    return NextResponse.json({
      results: searchResult,
      vector_preview: vector.slice(0, 5), // Show first 5 dims for debug
    });
  } catch (error) {
    logger.error("RAG Search Error:", error);
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
}
