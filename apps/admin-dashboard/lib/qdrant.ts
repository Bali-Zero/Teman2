import { QdrantClient } from "@qdrant/js-client-rest";

export function createQdrantClient(): QdrantClient {
  return new QdrantClient({
    url: process.env.QDRANT_URL,
    apiKey: process.env.QDRANT_API_KEY,
    checkCompatibility: false,
  });
}
