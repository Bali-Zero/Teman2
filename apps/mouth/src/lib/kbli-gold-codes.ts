// =============================================================================
// KBLI 2025 Gold Codes
// 428 of the 1,559 codes carry gold-tier editorial content — NOT all of them.
// (Corrected 2026-07-25: this header claimed "all 1,563 codes". Both halves were
// wrong. 1,563 is the count of a DIFFERENT population — the `kbli_documents`
// superset, which carries 4 retired KBLI-2020 phantom rows the canonical
// catalogue does not have — and the file has held 428 entries throughout.
// A comment is not load-bearing, but a wrong one is how the next reader
// concludes gold mirrors canonical and drops a check that isn't redundant.)
// Gold content is loaded from data/kbli-gold-all.json at build time and
// OVERRIDES the canonical editorial fields wherever an entry exists.
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
