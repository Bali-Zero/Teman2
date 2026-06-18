// =============================================================================
// L4 Bali-status adapter — reads schema-v2 l4_bali for the navigator.
// The sovereign-local layer: national PMA openness (L2) != Bali registrability (L4).
// Schema source: data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json (regenerable via populator).
// Build-time only (Next.js static gen). Falls back gracefully if the schema isn't present yet.
// =============================================================================
import fs from 'fs';
import path from 'path';
import type { BaliStatus } from '@/components/kbli/BaliStatusBadge';

export interface BaliL4 {
  status: BaliStatus;
  reason: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  needsReview: boolean;
  from2020?: string;
  moratorium: { rule: string; effective: string; source: string; virtualOffice: string };
}

let _cache: Record<string, BaliL4> | null = null;

function loadSchema(): Record<string, BaliL4> {
  if (_cache) return _cache;
  const candidates = [
    path.join(process.cwd(), '../../data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json'),
    path.join(process.cwd(), 'data/kbli_schema_v2/KBLI_2025_SCHEMA_V2.json'),
  ];
  const file = candidates.find((p) => fs.existsSync(p));
  const out: Record<string, BaliL4> = {};
  if (!file) {
    _cache = out;
    return out; // graceful: navigator works without L4 until schema is built/shipped
  }
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
  _cache = out;
  return out;
}

/** Bali L4 status for a 5-digit KBLI code, or null if unknown. */
export function getBaliL4(kode: string): BaliL4 | null {
  return loadSchema()[kode] ?? null;
}

/** True if a PMA (foreign-owned) company is effectively blocked in Bali for this code. */
export function isBlockedInBali(kode: string): boolean {
  const l4 = getBaliL4(kode);
  if (!l4) return false;
  return ['BLOCCATO_CLASSE_RISCHIO', 'CHIUSO_BALI', 'TERTUTUP'].includes(l4.status);
}
