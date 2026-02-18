// KBLI Gold Codes - Stub for build
export interface GoldCode {
  code: string;
  name: string;
  description?: string;
  category?: string;
}

export const GOLD_CODES: Set<string> = new Set([
  "56101",
  "55194",
  "55111",
  "68110",
  "47911",
  "62011",
  "85499",
  "96102",
  "79110",
  "70201",
]);

export function getGoldCodes(): GoldCode[] {
  return [];
}

export function getGoldCodeById(_id: string): GoldCode | null {
  return null;
}
