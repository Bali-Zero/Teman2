export interface AgenticQueryResponse {
  answer: string;
  sources: Array<{ title?: string; content?: string }>;
  context_length: number;
  execution_time: number;
  route_used: string | null;
  tools_called?: number;
  total_steps?: number;
  debug_info?: {
    giant_key_points?: string[];
    giant_warnings?: string[];
    cell_corrections?: Array<{ correction: string; severity?: string; source?: string }>;
    cell_enhancements?: string[];
    cell_calibrations?: string[];
    [key: string]: unknown;
  };
}