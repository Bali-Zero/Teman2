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
import fs from 'fs';
import path from 'path';
import type { BaliStatus } from '@/components/kbli/BaliStatusBadge';

export interface BaliL4 {
  status: BaliStatus;
  reason: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  needsReview: boolean;
  /** Authoritative "a PT PMA cannot register this in Bali" flag from the dataset.
   *  undefined when the source (schema-v2) predates the flag → fall back to status list. */
  blocked?: boolean;
  from2020?: string;
  moratorium: { rule: string; effective: string; source: string; virtualOffice: string };
}

let _cache: Record<string, BaliL4> | null = null;

const EMPTY_MORATORIUM = { rule: '', effective: '', source: '', virtualOffice: '' };

// Primary path: l4_bali injected flat into the live KBLI data file (ships to Vercel).
function loadFromLiveData(): Record<string, BaliL4> | null {
  const candidates = [
    path.join(process.cwd(), 'data', 'kbli-2025.json'),
    path.resolve(process.cwd(), '..', 'nuzantara', 'source_documents', 'KBLI_2025_FINAL_CLEAN.json'),
    path.resolve(process.cwd(), '..', '..', 'data', 'source_documents', 'KBLI_2025_FINAL_CLEAN.json'),
  ];
  const file = candidates.find((p) => fs.existsSync(p));
  if (!file) return null;
  const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
  const records = data.data ?? data.records ?? [];
  const out: Record<string, BaliL4> = {};
  let found = 0;
  for (const rec of records) {
    const kode = String(rec.kode_kbli_2025 ?? rec.kode_kbli ?? rec.kode ?? rec.code ?? '').trim();
    const l4 = rec.l4_bali;
    if (!kode || !l4?.status) continue;
    found++;
    const m = l4.moratorium ?? {};
    out[kode] = {
      status: l4.status as BaliStatus,
      reason: l4.reason ?? '',
      confidence: l4.confidence ?? 'MEDIUM',
      needsReview: !!l4.needs_review,
      blocked: typeof l4.blocked === 'boolean' ? l4.blocked : undefined,
      from2020: l4.from_2020 ?? undefined,
      moratorium: {
        rule: m.rule ?? '',
        effective: m.effective ?? '',
        source: m.source ?? '',
        virtualOffice: m.virtual_office ?? m.virtualOffice ?? '',
      },
    };
  }
  return found > 0 ? out : null;
}

// Fallback path: read the nested schema-v2 (local dev only — gitignored, absent on Vercel).
function loadFromSchemaV2(): Record<string, BaliL4> {
  const candidates = [
    path.join(process.cwd(), '../../data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json'),
    path.join(process.cwd(), 'data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json'),
  ];
  const file = candidates.find((p) => fs.existsSync(p));
  const out: Record<string, BaliL4> = {};
  if (!file) return out;
  const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
  for (const rec of data.records ?? []) {
    const l4 = rec.l4_bali;
    if (!l4?.bali_status) continue;
    const v = l4.bali_status.value;
    const m = l4.moratorium ?? {};
    out[rec.kode] = {
      status: v.status as BaliStatus,
      reason: v.reason ?? '',
      confidence: l4.bali_status.provenance?.confidence ?? 'MEDIUM',
      needsReview: !!l4.needs_human_review,
      from2020: v.from_2020,
      moratorium: {
        rule: m.rule ?? '',
        effective: m.effective ?? '',
        source: m.source ?? '',
        virtualOffice: m.virtual_office ?? '',
      },
    };
  }
  return out;
}

function loadSchema(): Record<string, BaliL4> {
  if (_cache) return _cache;
  // graceful: navigator works without L4 if neither source is present
  _cache = loadFromLiveData() ?? loadFromSchemaV2();
  return _cache;
}

// silence unused-var lint for the shared empty constant if tree-shaken
void EMPTY_MORATORIUM;

/** Bali L4 status for a 5-digit KBLI code, or null if unknown. */
export function getBaliL4(kode: string): BaliL4 | null {
  return loadSchema()[kode] ?? null;
}

/** True if a PMA (foreign-owned) company is effectively blocked in Bali for this code.
 *  Prefer the authoritative `blocked` flag from the dataset (covers NEEDS_REVIEW_NO_OSS_SCOPE,
 *  CHIUSO_PMA_NO_BESAR, etc. that a status-name list would miss — superscar #3); fall back to the
 *  status list only when the source has no explicit flag (schema-v2). */
export function isBlockedInBali(kode: string): boolean {
  const l4 = getBaliL4(kode);
  if (!l4) return false;
  if (typeof l4.blocked === 'boolean') return l4.blocked;
  return ['BLOCCATO_CLASSE_RISCHIO', 'CHIUSO_BALI', 'TERTUTUP'].includes(l4.status);
}
