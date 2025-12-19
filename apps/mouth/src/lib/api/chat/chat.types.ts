// Backend RAG response
export interface AgenticQueryResponse {
  answer: string;
  sources: Array<{ title?: string; content?: string }>;
  context_length: number;
  execution_time: number;
  route_used: string | null;
}

