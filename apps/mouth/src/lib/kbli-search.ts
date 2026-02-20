// KBLI Search - Stub for build
import type { KBLICode } from "./kbli-types";

export interface SearchResult {
  codes: KBLICode[];
  total: number;
  query: string;
}

export function searchCodes(query: string): SearchResult {
  return {
    codes: [],
    total: 0,
    query,
  };
}

export function searchKBLICodes(_query: string, _limit?: number): KBLICode[] {
  return [];
}
