// =============================================================================
// INTERNAL-LEAK GATE — measured on the REAL canonical, not on fixtures.
//
// The editorial pass authored the 1,559 articles by narrating the JSON record,
// so pipeline vocabulary reached readers. Two distinct leaks, measured
// 2026-07-25 on `data/KBLI_2025_FINAL_CLEAN.json`:
//
//   (a) SYMBOLS — `OK_or_HIGHER_RISK`, `BPS_ONLY`, … : 908 "By the numbers"
//       cells + 725 occurrences in editorial prose. CURED at render by
//       `humanizeIntelBlock` (kbli-status-labels.ts). This file proves the cure
//       covers the whole catalogue, on the real data, and stays at zero.
//
//   (b) RAW FIELD NAMES — `l4_bali_blocked is false`, `pma_max_asing`, … on 392
//       codes. NOT curable by a label map: the sentences have to be rewritten.
//       That is a data-plane job (editorial regeneration). Until then this file
//       PINS the debt with a ratchet: the count may fall, never rise. A silent
//       re-growth is the failure mode this gate exists to make impossible.
//
// Rationale for gating (b) instead of ignoring it: an unmeasured defect that
// only a human eye can see is a defect that grows. Superscar #2 — "esiste ≠
// armato": a cure with no probe is a cure you cannot prove tomorrow.
// =============================================================================

import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

import { deriveProvenance } from "./kbli-provenance";
import {
  INTERNAL_ENUM_LABELS,
  humanizeInternalEnums,
  humanizeIntelBlock,
} from "./kbli-status-labels";
import type { KBLIRawDataFile } from "./kbli-types";

// Anchored to this file, not to cwd: the gate must give the same verdict whether
// vitest is invoked from apps/mouth (CI) or from the repo root (local sweep).
const DATA_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  "../../data/KBLI_2025_FINAL_CLEAN.json",
);
const GOLD_PATH = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  "../../data/kbli-gold-all.json",
);

/**
 * Every string anywhere under `intel_2026`, collected GENERICALLY.
 *
 * Deliberately NOT an allow list of known fields: an allow list is blind to the
 * next field somebody adds, and that is exactly how `whoThisIsFor` (1,186
 * records, rendered at kbli/[code]/page.tsx) escaped both the cure and the first
 * draft of this gate. Walking everything makes the gate fail-closed — a new
 * reader-facing field is covered the day it appears.
 *
 * The two structural keys skipped here MUST match `INTEL_NON_READER_KEYS` in the
 * cure; they are re-declared rather than imported so this gate keeps an
 * independent opinion of what a reader sees, instead of grading the cure with
 * the cure's own definition.
 */
const NON_READER_KEYS = new Set(["_l3_regen", "coverImage"]);

function readerFacingStrings(node: unknown, acc: string[] = []): string[] {
  if (typeof node === "string") {
    acc.push(node);
  } else if (Array.isArray(node)) {
    for (const item of node) readerFacingStrings(item, acc);
  } else if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(
      node as Record<string, unknown>,
    )) {
      if (!NON_READER_KEYS.has(key)) readerFacingStrings(value, acc);
    }
  }
  return acc;
}

function loadCanonical() {
  const parsed = JSON.parse(
    fs.readFileSync(DATA_PATH, "utf-8"),
  ) as KBLIRawDataFile;
  return parsed.data;
}

const SYMBOL_RE = new RegExp(
  `(?<![A-Za-z0-9_])(${Object.keys(INTERNAL_ENUM_LABELS)
    .sort((a, b) => b.length - a.length)
    .join("|")})(?![A-Za-z0-9_])`,
);

/**
 * Raw canonical field names. Word-boundary anchored (never bare substring,
 * superscar #3) and ordered longest-first only for reporting clarity.
 */
const RAW_FIELD_NAMES = [
  "l4_bali_blocked",
  "l4_bali",
  "per_skala_disputed",
  "per_skala_legacy",
  "per_skala",
  "_l2_status",
  "_l2_source",
  "_data_note",
  "pp28_sources",
  "status_mapping",
  "ruang_lingkup",
  "intel_2026",
  "pma_max_asing",
  "pma_kondisi",
  "bps_2020_ancestors",
];
const FIELD_RE = new RegExp(
  `(?<![A-Za-z0-9_])(${RAW_FIELD_NAMES.join("|")})(?![A-Za-z0-9_])`,
);

describe("internal-leak gate (real canonical)", () => {
  const records = loadCanonical();

  it("loads the full catalogue", () => {
    expect(records.length).toBe(1559);
  });

  it("the raw data still carries the symbol leak this cure exists for", () => {
    // Guilt side of the gate: if this ever hits zero the cure has become
    // unnecessary at render (the data was fixed upstream) and this file should
    // be revisited rather than left asserting a cure nothing needs.
    const leaking = records.filter((r) =>
      readerFacingStrings(r.intel_2026).some((s) => SYMBOL_RE.test(s)),
    );
    expect(leaking.length).toBeGreaterThan(0);
  });

  it("ZERO internal symbols survive the render-layer cure, across all 1,559", () => {
    const survivors: { code: string; sample: string }[] = [];
    for (const r of records) {
      for (const s of readerFacingStrings(humanizeIntelBlock(r.intel_2026))) {
        const m = s.match(SYMBOL_RE);
        if (m) survivors.push({ code: r.kode_kbli_2025, sample: m[0] });
      }
    }
    expect(survivors.slice(0, 10)).toEqual([]);
    expect(survivors.length).toBe(0);
  });

  it("l4_bali.reason is cured too — it is a tooltip AND is embedded in the FAQ answer", () => {
    // 8 codes narrate "Previous status: OK_or_HIGHER_RISK" inside the Bali reason,
    // which kbli-faq.ts splices verbatim into a client-facing answer.
    const leaking = records.filter(
      (r) =>
        typeof r.l4_bali?.reason === "string" &&
        SYMBOL_RE.test(r.l4_bali.reason),
    );
    expect(leaking.length).toBeGreaterThan(0); // guilt: the defect is real
    for (const r of leaking) {
      expect(SYMBOL_RE.test(humanizeInternalEnums(r.l4_bali!.reason!))).toBe(
        false,
      );
    }
  });

  it("INNOCENCE: `_data_note` is evidence and must stay verbatim, symbols included", () => {
    // 88 codes cite the canonical record AS PROOF of a divergence — e.g.
    // "carries canonical status_mapping='CODICE_RINUMERATO', pp28_sources=[…]".
    // KBLIDivergence renders this verbatim as an audit trail. Rewriting a quoted
    // symbol would edit the evidence, so the cure must NOT reach this field: no
    // loader humanises `_data_note`, and this test fails if one ever starts.
    const withSymbol = records.filter(
      (r) => typeof r._data_note === "string" && SYMBOL_RE.test(r._data_note),
    );
    expect(withSymbol.length).toBeGreaterThan(0);

    const provenanceNotes = records
      .map((r) => deriveProvenance(r).dataNote)
      .filter((n): n is string => typeof n === "string");
    const stillQuoting = provenanceNotes.filter((n) => SYMBOL_RE.test(n));
    expect(stillQuoting.length).toBe(withSymbol.length);
  });

  it("covers the GOLD layer too — the surface the code page renders directly", () => {
    // The gold layout on /kbli/[code] renders gold.whatChanged & co. straight
    // from getGoldContent(), never through transformCode's merged intel. The
    // first draft of this cure missed it entirely: 113 of 428 gold codes were
    // still printing symbols. A canonical-only gate cannot see this file, so it
    // is measured here explicitly.
    const gold = JSON.parse(fs.readFileSync(GOLD_PATH, "utf-8"));
    const entries: Record<string, unknown> = gold.data ?? gold;
    const codes = Object.keys(entries);
    expect(codes.length).toBeGreaterThan(400);

    // GUILT is anchored on a FIXTURE, not on live data — and that change is the
    // point, not a workaround.
    //
    // This assertion used to read `expect(rawLeaking.length).toBeGreaterThan(0)`
    // against the gold file itself: it proved the render-layer cure was real by
    // checking the defect still existed upstream. That works only while the DATA
    // is broken. On 2026-07-26 the data-layer cure (L2.4,
    // scripts/kbli_filiera/cure_l23_whatchanged_language.py) removed the last 16
    // enum tokens from gold, and this line went red — not because the render
    // cure regressed, but because its live guilt subject was fixed.
    //
    // A guard whose guilt depends on production still being broken deletes
    // itself the day you fix production, and takes the protection with it. So
    // guilt now lives on a synthetic record, where it is permanent, and the live
    // file carries the stronger claim instead: nothing leaks, before OR after.
    const [sampleToken] = Object.keys(INTERNAL_ENUM_LABELS);
    const fixture = { whatYouNeed: `This code is marked ${sampleToken}.` };
    expect(readerFacingStrings(fixture).some((s) => SYMBOL_RE.test(s))).toBe(
      true,
    ); // guilt: the render cure has something to remove
    expect(
      readerFacingStrings(humanizeIntelBlock(fixture)).some((s) =>
        SYMBOL_RE.test(s),
      ),
    ).toBe(false); // ...and it removes it

    // Defence in depth: gold is clean at rest (data-layer cure) AND after the
    // render layer runs (render cure). Either alone would be enough today; both
    // together mean a regression in one is not a client-facing leak.
    const rawLeaking = codes.filter((c) =>
      readerFacingStrings(entries[c]).some((s) => SYMBOL_RE.test(s)),
    );
    expect(rawLeaking).toEqual([]);

    const curedLeaking = codes.filter((c) =>
      readerFacingStrings(humanizeIntelBlock(entries[c])).some((s) =>
        SYMBOL_RE.test(s),
      ),
    );
    expect(curedLeaking).toEqual([]);
  });

  it("pins the raw-field-name debt with a ratchet — it may fall, never rise", () => {
    // Measured 2026-07-25 on the canonical: 392 codes narrate a raw field name
    // (`l4_bali_blocked is false`, `pma_max_asing`, …) inside editorial prose.
    // Only an editorial rewrite can remove these; a label map cannot. When a
    // regeneration lot lands, LOWER this number — never raise it.
    const BASELINE = 392;
    const leaking = records.filter((r) =>
      readerFacingStrings(r.intel_2026).some((s) => FIELD_RE.test(s)),
    );
    expect(leaking.length).toBeLessThanOrEqual(BASELINE);
  });
});
