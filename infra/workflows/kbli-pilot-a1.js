// ============================================================================================
// SUPERSEDED (2026-07-18) — DO NOT DISPATCH FOR A NEW RUN.
// This script's D5 refutation seat is NOT blind: d5Prompt(code, d1Result) below
// embeds D1's own proposal (`JSON.stringify(d1Result)`) directly in the refuter's prompt, so its
// "re-derive BEFORE reading the proposal" instruction is anchoring theater, not an independent
// verification (conductor verification finding, 2026-07-18 — see infra/workflows/kbli-batch-a-
// lot.js's own "D5 BLIND-REFUTATION FIX" comment, which names this exact file/defect verbatim).
// This script's measured m1 blind-concordance baseline (0.917, pinned in
// data/kbli-filiera/batch-reports/batchA-calibration.md) is therefore INVALID as a calibration
// figure — it measures agreement with an anchored refuter, not independent concordance. See
// research/operations/2026-07-18-kbli-batch-a-plan.md §8 amendment A-4 (m1 BREACH on Lot 1 root-
// caused to exactly this same-family/anchored-pair blindness: true blind concordance measured
// 5/13 = 0.385, far below the 0.917 this file produced).
// USE infra/workflows/kbli-batch-a-lot.js INSTEAD — it has a truly blind d5Prompt(code) (no D1
// parameter, no reference to D1's output) plus a deterministic diffD1D5() compiler, and is the
// calibration-enforced runner for all Batch A lots going forward.
// This file remains on main ONLY as a historical/archaeology artifact (the validated 15-code
// method pilot whose STRUCTURE the batch runner adapted) and carries a hard entry guard below so
// it cannot be re-dispatched by accident and its anchored numbers mistaken for a valid baseline.
// ============================================================================================
//
// kbli-pilot-a1.js — GARUDA-FILIERA pilot A1 per-code adjudication (D1 -> D5 -> D2).
//
// Companion docs: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (§2 seats,
// §3 D0-D6 protocol) + research/operations/2026-07-17-kbli-pilot-a1-preregistration.md (the
// FROZEN 15-code pilot plan + acceptance criteria this run is measured against).
//
// THREE-LAYER DIVISION OF LABOR (workflow doc §1 — enforced by construction, not convention):
// this script is the MECHANICAL layer. It fans out to LLM seats (Sonnet 5, "extractor ≠
// refuter" per-code) and returns their structured PROPOSALS — it never writes the data plane
// (data/kbli-filiera/** is guard-protected, infra/claude-hooks/data-plane-registry.json).
// The caller feeds this script's return value to `scripts/kbli_filiera/dossier_assemble.py`
// (the ONLY sanctioned writer) as that compiler's `--proposals` input, one invocation per code.
// An LLM here never manufactures a deterministic fact (Garuda law) — dossier_assemble.py
// independently recomputes op_id from the payload, so nothing here can spoof idempotency either.
//
// EVIDENCE INPUT: `args.evidenceRoot` must be a LOCAL directory already populated by
// `scripts/kbli_filiera/dossier_pull.py --out <evidenceRoot>` — one subdirectory per code,
// each containing canonical.json, oss/, crosswalk/, pp28/ (or their ABSENT/NOT_APPLICABLE
// verdicts) and evidence-index.json. This script does not fetch or render anything itself —
// every seat is instructed to Read the ALREADY-RENDERED PNGs, never to re-derive from a raw PDF.
//
// PER-CODE PIPELINE (workflow doc §3):
//   - innocenceControl codes (no pp28_sources, OSS-native — pre-registration "Innocence
//     controls") get ONE short verification prompt: "does anything need changing?" — any
//     proposed change is itself a finding of over-extraction, not a legitimate discovery.
//   - all other codes: D1 (Sonnet) proposes the 2020<->2025 crosswalk mapping with
//     uraian-level rationale, reading the crosswalk/pp28 renders. D5 (a SEPARATE agent
//     invocation, blind — never shown D1's proposal until it has already re-derived its own
//     answer) independently re-derives and then compares — "generator != grader", workflow
//     doc §3 D5. Disagreement (D1.needs_quarantine OR D5.refuted) -> quarantined, D2 skipped.
//     D2 (self-confirming image extraction, red-team F8 locator-poisoning guard) runs ONLY
//     when D1 concluded `licensing_inherits: true` and the pair was not quarantined.
//
// HOW TO RUN:
//   Workflow({ scriptPath: "infra/workflows/kbli-pilot-a1.js", args: {
//     codes: ["68112", "51103", ..., { code: "65121", innocenceControl: true }, ...],
//     evidenceRoot: "/Users/nuzantara/nuzantara-vault-evidence/pilot-a1",
//   }})
// Returns { evidenceRoot, results: [...], quarantinedCodes: [...], summary: {...} } — the
// caller (Fable session, per workflow doc §1 "mente immobile") reads quarantined codes for
// its own D6 adjudication and drives dossier_assemble.py for every code, quarantined or not
// (a quarantine is itself a recorded D5 event, never a dropped one).

export const meta = {
  name: "kbli-pilot-a1",
  description:
    "GARUDA-FILIERA per-code adjudication (D1 crosswalk proposal -> D5 blind refutation -> D2 self-confirming extraction) over evidence already pulled by dossier_pull.py",
  whenToUse:
    "Pilot A1 (and, per Zero's 2026-07-16 GO, later batches) of the KBLI Filiera per-code reconstruction program — never for a code whose evidence has not already been pulled locally.",
  phases: [
    {
      title: "Adjudicate",
      detail:
        "per code, in parallel: D1 propose -> D5 blind-refute -> D2 (conditional) extract; innocence controls get a single short verification prompt",
    },
    {
      title: "Collect",
      detail:
        "return the full structured result per code — this script never writes data/kbli-filiera/** itself",
    },
  ],
};

// ----- input (args) — defensive parse, matching modus-bench.js's lesson (run wf_b0ad36b1-80d:
// the harness can deliver `args` as a JSON-encoded STRING) -----------------------------------
const A = (typeof args === "string" ? JSON.parse(args) : args) || {};

// ----- SUPERSEDED entry guard (2026-07-18) — see the file-header block above. This script's D5
// seat is anchored (d5Prompt(code, d1Result) below embeds D1's own proposal), so it must never be
// dispatched as a fresh run whose numbers could be mistaken for a valid calibration baseline. The
// escape hatch exists ONLY for archaeology/resume of the already-measured historical pilot run
// itself — never flip it on for new codes. New runs MUST use infra/workflows/kbli-batch-a-lot.js.
if (A.allowAnchoredPilot !== true) {
  throw new Error(
    "kbli-pilot-a1.js is SUPERSEDED (2026-07-18): its D5 seat is anchored -- d5Prompt(code, " +
      "d1Result) embeds D1's own proposal in the refuter's prompt, so 're-derive before reading " +
      "the proposal' is anchoring theater, not a blind refutation. Its measured m1 concordance " +
      "(0.917) is invalid as a calibration baseline (see research/operations/2026-07-18-kbli-" +
      "batch-a-plan.md §8 amendment A-4). Use infra/workflows/kbli-batch-a-lot.js (blind " +
      "d5Prompt(code) + deterministic diffD1D5() compiler) for any new run. Pass " +
      "args.allowAnchoredPilot === true ONLY to resume or archive the historical pilot run itself.",
  );
}

const evidenceRoot = A.evidenceRoot;
if (!evidenceRoot || typeof evidenceRoot !== "string") {
  throw new Error(
    "kbli-pilot-a1: args.evidenceRoot is required (local dir already populated by dossier_pull.py --out)",
  );
}
const rawCodes = Array.isArray(A.codes) ? A.codes : [];
if (!rawCodes.length) {
  throw new Error(
    "kbli-pilot-a1: args.codes must be a non-empty array of codes or {code, innocenceControl}",
  );
}
const CODES = rawCodes.map((c) =>
  typeof c === "string"
    ? { code: c, innocenceControl: false }
    : { code: String(c.code), innocenceControl: !!c.innocenceControl },
);

// ----- schemas — every non-deterministic proposal is FORCED into a structured shape a
// downstream compiler (dossier_assemble.py) can validate against evidence pointers before it
// ever lands as a fact (Garuda law, workflow doc §1) -------------------------------------------

const RENDER_REF = {
  type: "object",
  required: ["file", "page"],
  properties: {
    file: {
      type: "string",
      description: "the rendered PNG's rel_path under the code's evidence dir",
    },
    page: { type: "number" },
    row: { type: "string" },
  },
};

const D1_SCHEMA = {
  type: "object",
  required: [
    "mappings",
    "confidence",
    "needs_quarantine",
    "licensing_inherits",
  ],
  properties: {
    mappings: {
      type: "array",
      items: {
        type: "object",
        required: ["kbli2020", "kbli2025", "mapping_type", "rationale"],
        properties: {
          kbli2020: { type: "string" },
          kbli2025: { type: "string" },
          mapping_type: {
            type: "string",
            enum: ["ONE_TO_ONE", "SPLIT", "MERGE", "COLLISION", "NO_MAPPING"],
          },
          rationale: {
            type: "string",
            description:
              "uraian-level semantic rationale — title-similarity-only is FORBIDDEN (kbli-navigator SKILL.md §4.2)",
          },
          lampiran_page_refs: { type: "array", items: RENDER_REF },
        },
      },
    },
    confidence: { type: "string", enum: ["high", "medium", "low"] },
    needs_quarantine: { type: "boolean" },
    licensing_inherits: {
      type: "boolean",
      description:
        "true if this code's licensing facts are inherited from a KBLI-2020-vintage PP28 source and D2 extraction is needed",
    },
    notes: { type: "string" },
  },
};

const D5_SCHEMA = {
  type: "object",
  required: ["refuted", "reasons", "verdict"],
  properties: {
    refuted: {
      type: "boolean",
      description:
        "default true when uncertain — blind re-derivation must independently agree, not just fail to object",
    },
    reasons: { type: "array", items: { type: "string" } },
    verdict: {
      type: "string",
      enum: ["certified", "quarantined", "abstained"],
    },
  },
};

const D2_SCHEMA = {
  type: "object",
  required: ["per_skala_rows", "self_confirmed"],
  properties: {
    per_skala_rows: {
      type: "array",
      items: {
        type: "object",
        required: ["skala_usaha", "kategori_risiko", "render_ref"],
        properties: {
          skala_usaha: { type: "array", items: { type: "string" } },
          kategori_risiko: { type: "string" },
          perizinan: { type: "array", items: { type: "string" } },
          persyaratan: { type: "array", items: { type: "string" } },
          kewajiban: { type: "array", items: { type: "string" } },
          render_ref: RENDER_REF,
        },
      },
    },
    self_confirmed: {
      type: "object",
      required: ["code_appears_in_row", "neighboring_codes"],
      description: "locator-poisoning guard (workflow doc §3 D2, red-team F8)",
      properties: {
        code_appears_in_row: { type: "boolean" },
        neighboring_codes: { type: "array", items: { type: "string" } },
      },
    },
  },
};

const INNOCENCE_SCHEMA = {
  type: "object",
  required: ["changes_proposed", "verdict"],
  properties: {
    changes_proposed: {
      type: "array",
      items: { type: "string" },
      description:
        "MUST be empty for a true innocence control — any entry here is itself a finding of over-extraction, not a legitimate discovery",
    },
    verdict: {
      type: "string",
      enum: ["boring_as_expected", "unexpected_finding"],
    },
    notes: { type: "string" },
  },
};

// ----- prompts ---------------------------------------------------------------------------------

function evidenceDirFor(code) {
  return `${evidenceRoot}/${code}`;
}

function innocencePrompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `INNOCENCE CONTROL — KBLI-2025 code ${code} (GARUDA-FILIERA pilot A1, pre-registration ` +
    `"Innocence controls": OSS-native, no pp28_sources — the dossier MUST come out boring). ` +
    `Read ${dir}/canonical.json, ${dir}/evidence-index.json, and every file under ${dir}/oss/, ` +
    `${dir}/crosswalk/, ${dir}/pp28/ (renders or their ABSENT/NOT_APPLICABLE verdict). Verify ` +
    `that NOTHING needs changing. Hold yourself to the bar in the pre-registration: any proposed ` +
    `change here is itself a finding of over-extraction in the pipeline, not a legitimate ` +
    `regulatory discovery — do not manufacture a finding to seem thorough.`
  );
}

function d1Prompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `D1 crosswalk adjudication — KBLI-2025 code ${code} (workflow doc §3 D1). Read ${dir}/canonical.json ` +
    `for the code's own record (pp28_sources, sektor_id, per_skala), then read every PNG under ` +
    `${dir}/crosswalk/*.png (BPS Vol.2 Lampiran 5/10 rendered page hits) and ${dir}/pp28/*.png (PP28 ` +
    `lampiran rendered page hits) — where a layer instead has an ABSENT.json or NOT_APPLICABLE.json, ` +
    `read that and record the layer as absent/not-applicable rather than guessing. Adjudicate the ` +
    `2020<->2025 crosswalk mapping with uraian-level SEMANTIC rationale from the rendered text — ` +
    `title-similarity alone is FORBIDDEN (kbli-navigator SKILL.md §4.2, "il contesto batte il titolo" — ` +
    `signature of a wrong remap: mapping_type=SPLIT applied as a single code + boilerplate reasoning). ` +
    `Every digit you cite from a render is evidence only because you looked at the IMAGE, never because ` +
    `pdftotext said so (OCR trap: "68112" can render as "681t2"). Set needs_quarantine=true if the mapping ` +
    `is ambiguous or the evidence is thin. Set licensing_inherits=true only if this code's licensing facts ` +
    `visibly come from a KBLI-2020-vintage PP28 source that would need image-verified row extraction (D2).`
  );
}

function d5Prompt(code, d1Result) {
  const dir = evidenceDirFor(code);
  return (
    `D5 independent verification — KBLI-2025 code ${code} (workflow doc §3 D5, "blind re-extraction... ` +
    `agreement certifies, divergence quarantines"). You are the REFUTER, not the author — you did not ` +
    `write the proposal below and are not grading your own work. Read the SAME evidence D1 had access to ` +
    `(${dir}/canonical.json, ${dir}/crosswalk/*.png, ${dir}/pp28/*.png, or their ABSENT/NOT_APPLICABLE ` +
    `verdicts) and independently re-derive the crosswalk mapping and licensing-inheritance conclusion ` +
    `BEFORE reading the proposal. Only after you have your own answer, compare it against the proposal: ` +
    `does your independent read AGREE, or does it REFUTE? Default refuted=true when uncertain — a ` +
    `refuter that rubber-stamps because it cannot be bothered to re-derive is worse than no refuter at all.\n\n` +
    `D1 PROPOSAL TO VERIFY:\n${JSON.stringify(d1Result, null, 2)}`
  );
}

function d2Prompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `D2 image-verified extraction — KBLI-2025 code ${code} (workflow doc §3 D2, self-confirming, ` +
    `red-team F8 locator-poisoning guard). Read every PNG under ${dir}/pp28/*.png. Extract per_skala rows ` +
    `(skala_usaha, kategori_risiko, perizinan, persyaratan, kewajiban) DIRECTLY FROM THE IMAGE TEXT — never ` +
    `infer a value from the code number or from prior knowledge of similar codes. Self-confirming guard: ` +
    `independently confirm the code string "${code}" (or its cited KBLI-2020 pp28 source) ACTUALLY appears ` +
    `in the row you read, and report the codes of the NEIGHBORING rows in the same table — a mismatch there ` +
    `is how a locator-poisoning error gets caught before it becomes a certified fact. Every field carries a ` +
    `render_ref {file, page, row}.`
  );
}

// ----- per-code adjudication ---------------------------------------------------------------

async function adjudicateInnocence(code) {
  const verdict = await agent(innocencePrompt(code), {
    label: `innocence:${code}`,
    phase: "Adjudicate",
    schema: INNOCENCE_SCHEMA,
    model: "sonnet",
  });
  return {
    code,
    innocenceControl: true,
    innocence_verdict: verdict,
    quarantined: verdict && verdict.verdict === "unexpected_finding",
    seatInvocations: 1,
  };
}

async function adjudicateCode(code) {
  const d1 = await agent(d1Prompt(code), {
    label: `D1:${code}`,
    phase: "Adjudicate",
    schema: D1_SCHEMA,
    model: "sonnet",
  });

  const d5 = await agent(d5Prompt(code, d1), {
    label: `D5:${code}`,
    phase: "Adjudicate",
    schema: D5_SCHEMA,
    model: "sonnet",
  });

  const quarantined = Boolean(
    (d1 && d1.needs_quarantine) || (d5 && d5.refuted),
  );

  let d2 = null;
  if (!quarantined && d1 && d1.licensing_inherits === true) {
    d2 = await agent(d2Prompt(code), {
      label: `D2:${code}`,
      phase: "Adjudicate",
      schema: D2_SCHEMA,
      model: "sonnet",
    });
  }

  return {
    code,
    innocenceControl: false,
    d1,
    d5,
    d2,
    quarantined,
    seatInvocations: d2 ? 3 : 2,
  };
}

// ----- run ---------------------------------------------------------------------------------

phase("Adjudicate");
const results = await parallel(
  CODES.map(
    ({ code, innocenceControl }) =>
      () =>
        innocenceControl ? adjudicateInnocence(code) : adjudicateCode(code),
  ),
);

phase("Collect");
const settled = results.filter(Boolean);
const quarantinedCodes = settled
  .filter((r) => r.quarantined)
  .map((r) => r.code);
log(
  `${settled.length}/${CODES.length} codes adjudicated — ${quarantinedCodes.length} quarantined: ${quarantinedCodes.join(", ") || "none"}`,
);

// NOTE (pre-registration acceptance criterion #8): per-seat token/wall-time metrics belong to
// the harness's own run-log, not fabricated here — `seatInvocations` is the one measurement
// this script can compute deterministically from which agent() calls actually ran.
return {
  evidenceRoot,
  codes: CODES.map((c) => c.code),
  results: settled,
  quarantinedCodes,
  summary: {
    total: CODES.length,
    adjudicated: settled.length,
    quarantined: quarantinedCodes.length,
    innocenceControls: CODES.filter((c) => c.innocenceControl).length,
    totalSeatInvocations: settled.reduce(
      (sum, r) => sum + (r.seatInvocations || 0),
      0,
    ),
  },
};
