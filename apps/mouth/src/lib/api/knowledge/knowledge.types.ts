import type { ChunkMetadata, SearchResponse, SearchResult, TierLevel } from '../../../../lib/api/generated';

// Knowledge/Search API types (reuse generated OpenAPI models to avoid duplication)
export type KnowledgeChunkMetadata = ChunkMetadata;
export type KnowledgeSearchResult = SearchResult;
export type KnowledgeSearchResponse = SearchResponse;
export { TierLevel };

