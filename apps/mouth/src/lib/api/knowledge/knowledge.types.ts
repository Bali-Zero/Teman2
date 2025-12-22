// Knowledge/Search API types - defined directly to avoid dependency on generated files
export enum TierLevel {
  S = 'S',
  A = 'A',
  B = 'B',
  C = 'C',
  D = 'D',
}

export interface ChunkMetadata {
  book_title: string;
  book_author: string;
  tier: TierLevel;
  min_level: number;
  chunk_index: number;
  page_number?: number | null;
  language?: string;
  topics?: Array<string>;
  file_path: string;
  total_chunks: number;
}

export interface SearchResult {
  text: string;
  metadata: ChunkMetadata;
  similarity_score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

// Re-export with Knowledge prefix for consistency
export type KnowledgeChunkMetadata = ChunkMetadata;
export type KnowledgeSearchResult = SearchResult;
export type KnowledgeSearchResponse = SearchResponse;
