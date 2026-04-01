// =============================================================================
// KBLI 2025 Gold Codes
// All 1,563 codes now have gold-tier editorial content (Batch A + B + C).
// Gold content is loaded from data/kbli-gold-all.json at build time.
// This module reads the gold JSON directly to avoid circular dependencies.
// =============================================================================

import fs from "fs";
import path from "path";

let _goldCodes: Set<string> | null = null;

function loadGoldCodes(): Set<string> {
  if (_goldCodes) return _goldCodes;
  try {
    const jsonPath = path.join(process.cwd(), "data", "kbli-gold-all.json");
    const raw = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
    _goldCodes = new Set(Object.keys(raw.data ?? raw));
    return _goldCodes;
  } catch {
    _goldCodes = new Set();
    return _goldCodes;
  }
}

/** Set of all KBLI codes with gold-tier editorial content */
export const GOLD_CODES: Set<string> = loadGoldCodes();
