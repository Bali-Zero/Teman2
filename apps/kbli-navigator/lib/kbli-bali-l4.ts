// =============================================================================
// L4 Bali-status adapter — the sovereign-local layer.
// National PMA openness (L2) != Bali registrability (L4): the moratorium 2026-05-13
// (Gubernur letter B.27.000/642) blocks ALL low/medium-low risk PMA island-wide.
//
// Data source (PRODUCTION): the `l4_bali` field injected into the SAME tracked file the
// navigator already ships — data/source_documents/KBLI_2025_FINAL_CLEAN.json. This guarantees
// the badge renders on Vercel (the 17MB schema-v2 is gitignored and never reaches the build).
// Falls back to schema-v2 for local dev if the injected field is absent.
// Build-time only (Next.js static gen). Graceful-degrades to no-badge if neither is present.
// =============================================================================
import fs from "fs";
import path from "path";
import type { BaliStatus } from "@/components/kbli/BaliStatusBadge";
import { hasLocatedPmaTuple } from "./kbli-pma-disclosure";

export interface BaliL4 {
  status: BaliStatus;
  reason: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  needsReview: boolean;
  /** Authoritative "a PT PMA cannot register this in Bali" flag from the dataset. */
  blocked: boolean;
  from2020?: string;
  moratorium: {
    rule: string;
    effective: string;
    source: string;
    virtualOffice: string;
  };
}

let _cache: Record<string, BaliL4> | null = null;

const ALLOWED_BALI_STATUSES = new Set([
  "APERTO_BALI_RISCHIO_ALTO",
  "BLOCCATO_CLASSE_RISCHIO",
  "BLOCCATO_DIPENDE_SCOPE",
  "CHIUSO_BALI",
  "CHIUSO_BALI_PROPOSTO",
  "CHIUSO_MORATORIA_BALI",
  "CHIUSO_PMA_NO_BESAR",
  "CHIUSO_REGOLATORE_SETTORIALE",
  "NON_CLASSIFICABILE",
  "OK_or_HIGHER_RISK",
  "TERBATAS",
  "TERTUTUP",
]);

function cleanText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** Pure public boundary used by the file loader and adversarial tests. */
export function discloseBaliL4Record(
  record: Record<string, unknown>,
): BaliL4 | null {
  if (!hasLocatedPmaTuple(record)) return null;
  const candidate = record.l4_bali;
  if (!candidate || typeof candidate !== "object") return null;
  const l4 = candidate as Record<string, unknown>;
  const status = l4.status;
  const blocked = l4.blocked;
  const needsReview = l4.needs_review;
  if (
    typeof status !== "string" ||
    !ALLOWED_BALI_STATUSES.has(status) ||
    typeof blocked !== "boolean" ||
    typeof needsReview !== "boolean"
  ) {
    return null;
  }

  const confidence = ["HIGH", "MEDIUM", "LOW"].includes(String(l4.confidence))
    ? (l4.confidence as BaliL4["confidence"])
    : "MEDIUM";
  const moratorium =
    l4.moratorium && typeof l4.moratorium === "object"
      ? (l4.moratorium as Record<string, unknown>)
      : {};

  return {
    status: status as BaliStatus,
    reason: cleanText(l4.reason),
    confidence,
    needsReview,
    blocked,
    from2020: cleanText(l4.from_2020) || undefined,
    moratorium: {
      rule: cleanText(moratorium.rule),
      effective: cleanText(moratorium.effective),
      source: cleanText(moratorium.source),
      virtualOffice: cleanText(
        moratorium.virtual_office ?? moratorium.virtualOffice,
      ),
    },
  };
}

// Primary path: l4_bali injected flat into the live KBLI data file (ships to Vercel).
function loadFromLiveData(): Record<string, BaliL4> | null {
  const candidates = [
    path.join(process.cwd(), "data", "kbli-2025.json"),
    path.resolve(
      process.cwd(),
      "..",
      "nuzantara",
      "source_documents",
      "KBLI_2025_FINAL_CLEAN.json",
    ),
    path.resolve(
      process.cwd(),
      "..",
      "..",
      "data",
      "source_documents",
      "KBLI_2025_FINAL_CLEAN.json",
    ),
  ];
  const file = candidates.find((p) => fs.existsSync(p));
  if (!file) return null;
  const data = JSON.parse(fs.readFileSync(file, "utf-8"));
  const records = data.data ?? data.records ?? [];
  const out: Record<string, BaliL4> = {};
  let found = 0;
  for (const rec of records) {
    const kode = String(
      rec.kode_kbli_2025 ?? rec.kode_kbli ?? rec.kode ?? rec.code ?? "",
    ).trim();
    const disclosed = discloseBaliL4Record(rec);
    if (!kode || !disclosed) continue;
    found++;
    out[kode] = disclosed;
  }
  return found > 0 ? out : null;
}

// The legacy schema-v2 fallback predates the exact PMA verification tuple.
// Publishing its Bali verdict would bypass the atomic gate, so it intentionally
// contributes no public records until it carries equivalent provenance.
function loadFromSchemaV2(): Record<string, BaliL4> {
  return {};
}

function loadSchema(): Record<string, BaliL4> {
  if (_cache) return _cache;
  // graceful: navigator works without L4 if neither source is present
  _cache = loadFromLiveData() ?? loadFromSchemaV2();
  return _cache;
}

/** Bali L4 status for a 5-digit KBLI code, or null if unknown. */
export function getBaliL4(kode: string): BaliL4 | null {
  return loadSchema()[kode] ?? null;
}

/** True only when the verified public tuple carries an actual boolean block. */
export function isBlockedInBali(kode: string): boolean {
  return getBaliL4(kode)?.blocked === true;
}
