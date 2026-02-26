import fs from "fs";
import path from "path";
import type { KBLIGoldContent } from "./kbli-types";

interface GoldDataFile {
  metadata: {
    description: string;
    generated: string;
    totalCodes: number;
    batchACodes: number;
    batchBCodes: number;
  };
  data: Record<string, KBLIGoldContent>;
}

let _cache: Record<string, KBLIGoldContent> | null = null;

function loadGoldData(): Record<string, KBLIGoldContent> {
  if (_cache) return _cache;

  const jsonPath = path.join(process.cwd(), "data", "kbli-gold-all.json");
  try {
    const raw: GoldDataFile = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
    _cache = raw.data;
    return _cache;
  } catch {
    process.stderr.write(`[kbli-gold] Failed to load: ${jsonPath}\n`);
    _cache = {};
    return _cache;
  }
}

export function getGoldContent(code: string): KBLIGoldContent | null {
  return loadGoldData()[code] ?? null;
}

export function hasGoldContent(code: string): boolean {
  return code in loadGoldData();
}

export function getGoldCodes(): string[] {
  return Object.keys(loadGoldData());
}
