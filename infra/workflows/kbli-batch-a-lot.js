// kbli-batch-a-lot.js — GARUDA-FILIERA Batch A parameterized LOT runner.
//
// Adaptation of infra/workflows/kbli-pilot-a1.js (the validated 15-code method pilot) into a
// repeatable, calibration-enforced runner over `data/kbli-filiera/membership/batch-a-members.json`'s
// 114 in-scope A-serving codes, split into taxonomy-ordered lots per
// research/operations/2026-07-18-kbli-batch-a-plan.md §8 amendment A-2 ("lot-shape rule").
//
// Companion docs: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (§2 seats, §3
// D0-D6 protocol) + research/operations/2026-07-18-kbli-batch-a-plan.md (§3 acceptance criteria,
// §4 writers, §5 calibration/lots, §6 degradation) + research/operations/2026-07-17-kbli-pilot-a1-
// results.md (the measured pilot this lot runner is calibrated against).
//
// THREE-LAYER DIVISION OF LABOR (unchanged from the pilot, workflow doc §1): this script is the
// MECHANICAL layer. It fans out to LLM seats (Sonnet 5, "extractor != refuter" per-code) and
// returns their structured PROPOSALS plus a deterministic LOT REPORT — it never writes the data
// plane (data/kbli-filiera/** is guard-protected, infra/claude-hooks/data-plane-registry.json).
// The caller feeds this script's `results` to `scripts/kbli_filiera/dossier_assemble.py`
// (the ONLY sanctioned writer), one invocation per code, exactly like the pilot.
//
// CALIBRATION ENFORCEMENT (plan §5, NEW vs the pilot): m1 (blind-concordance), m2 (certification
// rate), m3 (refutation-category registry) and m4 (tokens/dossier ceiling) are PINNED LITERALS
// below, copied verbatim from data/kbli-filiera/batch-reports/batchA-calibration.json — never
// re-derived at runtime (same "PINNED LITERAL" discipline as
// scripts/kbli_filiera/emit_batch_calibration.py's own PILOT_A1 dict; Workflow scripts have no
// filesystem/network primitive of their own — every existing script under infra/workflows/ reads
// files ONLY through an agent() call, never `node:fs` — so a pinned literal, drift-guarded by
// scripts/kbli_filiera/tests/test_lot_runner_contract.py against the calibration JSON, is the
// correct mechanism here, not a fabricated runtime read). m5 (gold-set hit rate) is DELIBERATELY
// NOT computed here: the gold sets are digest-blind by design (plan §5, "blind to lanes") and
// this script must never attempt to reverse them (e.g. by hashing the lot's own codes against the
// calibration digests) — that adjudication is reserved for the CONDUCTOR, post-lot.
//
// MEMBERSHIP GATE (NEW vs the pilot): a lot REFUSES to run if any requested code is not an
// in-scope member of Batch A. Because this script cannot read
// data/kbli-filiera/membership/batch-a-members.json itself (no fs primitive — see above), the
// CALLER must pass the file's already-parsed contents as `args.membership` verbatim. This keeps
// the membership check itself 100% deterministic pure-JS (no LLM in a hard refusal gate — an
// LLM asked to transcribe a 114-row array is exactly the kind of "manufactured deterministic
// fact" the workflow doc's Garuda law forbids).
//
// LEASE GUARD (NEW vs the pilot, which had none): plan §2 P3 requires every dossier claim to go
// through `agent_lock:kbli-dossier:<code>` (scripts/agent_lease.py) BEFORE the code is touched.
// This script cannot acquire the lease itself — no Workflow script in this repo invokes a
// shell/subprocess (verified against kbli-pilot-a1.js, verify-template.js, modus-bench.js: none
// of the three call bash/exec) and inventing that primitive here would be new infra, which the
// brief explicitly forbids. Per spec this SKIPS acquisition and emits a loud per-code WARN naming
// the exact command the CALLER must run first — an observability signal, not an enforced gate.
//
// EVIDENCE INPUT: identical contract to the pilot — `args.evidenceRoot` must already be populated
// by `scripts/kbli_filiera/dossier_pull.py --out <evidenceRoot>` for every code in this lot.
//
// VERDICT TAXONOMY (NEW vs the pilot — closes pilot-report criterion #6's documented deviation):
// every code, INCLUDING the innocence-control branch, resolves to ONLY the frozen three tokens
// certified | quarantined | abstained. The pilot's innocence branch emitted a 4th vocabulary
// (`boring_as_expected` / `unexpected_finding`) — that vocabulary is NOT used anywhere below
// except in this normalization comment: boring_as_expected -> certified (innocence:true),
// unexpected_finding -> quarantined (an unexpected proposed change on an innocence control is
// itself a finding of over-extraction, same bar as the pilot held it to).
//
// D5 BLIND-REFUTATION FIX (2026-07-18, conductor verification — BLOCKING finding, fixed before
// merge): the first draft of this script copied kbli-pilot-a1.js's d5Prompt(code, d1Result)
// VERBATIM, which embeds `JSON.stringify(d1Result)` directly in the refuter's prompt — the model
// sees D1's answer from token one, so the "re-derive BEFORE reading the proposal" instruction is
// anchoring theater, not a blind refutation (plan §3/A4, red-team F5: "the D5 refuter re-extracts
// blind (render + code, NEVER the extractor's answer); the COMPILER diffs the two extractions —
// only a match certifies"). NOTE: the merged pilot itself has this identical defect
// (kbli-pilot-a1.js:246-257) — out of scope to fix here, flagged separately. Fixed here: D5
// (d5Prompt(code) below) receives ONLY the code + evidence dir + out-of-scope notice, NEVER any
// other seat's output, and returns its OWN independent structured conclusion (D5_SCHEMA:
// mapping_type, licensing_inherits, problem_found, problem_category, rationale,
// evidence_locators — no "verdict" field: D5 does not decide certified/quarantined, it only
// reports what IT independently found). The verdict is computed by `diffD1D5()`, pure
// deterministic JS, never a seat: fields agree + no problem -> certified; fields agree + both
// flag a problem -> quarantined (category = D5's, `category_mismatch` flagged if D1's own
// category differs); ANY divergence on mapping_type/licensing_inherits/problem_found ->
// quarantined + `divergent:true`, category taken from whichever side actually flagged a problem
// — never averaged, never code-picked beyond this one rule.
//
// ABSTAIN-CLASS SCOPE (plan §8 amendment A-1): `pma_status`, `l4_bali` and `TKA` facets depend on
// the deferred P1-v2 vault wave (Perpres 10/49, Bali Gubernur overlay, Kepmenaker 228/2019) and
// are OUT OF SCOPE for every seat in this pass. D1 and D5 each carry an independent, optional
// `abstain: {needed, facet}` field (ADDITION beyond the conductor's literal D5-diff spec, kept to
// preserve this plan §8 A-1 requirement, which the diff rule above does not otherwise cover) —
// either seat flagging `abstain.needed=true` forces the code's final verdict to `abstained`,
// overriding the diff result (a scope-boundary claim is stronger than "the visible facts agree").
// The innocence branch is unaffected by any of the above (single-seat, no D1/D5 split) and keeps
// its own `verdict` enum with `abstained` directly.
//
// HOW TO RUN:
//   Workflow({ scriptPath: "infra/workflows/kbli-batch-a-lot.js", args: {
//     lot_id: "A-L1",
//     codes: ["01287", "01700", ..., { code: "65121", innocenceControl: true }, ...],
//     evidenceRoot: "/path/to/dossier_pull.py --out output",
//     membership: <parsed contents of data/kbli-filiera/membership/batch-a-members.json>,
//   }})
// Returns { evidenceRoot, lotId, codes, results, lotReport } — the caller drives
// dossier_assemble.py per code and adjudicates lotReport.limits_breached (plan §5 pause/resume
// protocol: any breach pauses the lane at the lot boundary, conductor-signed resume required).

export const meta = {
  name: "kbli-batch-a-lot",
  description:
    "GARUDA-FILIERA Batch A calibration-enforced lot runner (D1 crosswalk proposal -> D5 blind refutation -> D2 self-confirming extraction) over evidence already pulled by dossier_pull.py, gated on membership and reporting m1-m4 control limits per lot",
  whenToUse:
    "Every Batch A lot (plan §8 amendment A-2: contiguous taxonomy-ordered segments of >=10 codes), per Zero's 2026-07-17 Batch A GO. Never for a code whose evidence has not already been pulled locally, and never for a code outside the pinned membership artifact.",
  phases: [
    {
      title: "Preflight",
      detail:
        "refuse the lot if codes is empty, any code is out-of-scope per the membership artifact, or a code is malformed",
    },
    {
      title: "Adjudicate",
      detail:
        "per code, in parallel: lease-guard WARN -> D1 propose -> D5 independently re-derive (blind — never shown D1's proposal) -> compiler diffD1D5() decides certified|quarantined -> D2 (conditional) extract; innocence controls get a single short verification prompt, all resolving to the frozen certified|quarantined|abstained taxonomy",
    },
    {
      title: "Report",
      detail:
        "compute the deterministic LOT REPORT (m1/m2/m3 against the pinned calibration limits; m4 flagged not-computable in-script; m5 reserved for the conductor) — this script never pauses/resumes, it only reports",
    },
  ],
};

// ----- input (args) — defensive parse, matching modus-bench.js's lesson (run wf_b0ad36b1-80d:
// the harness can deliver `args` as a JSON-encoded STRING) -----------------------------------
const A = (typeof args === "string" ? JSON.parse(args) : args) || {};

const lotId = A.lot_id;
if (!lotId || typeof lotId !== "string") {
  throw new Error('kbli-batch-a-lot: args.lot_id is required (e.g. "A-L1")');
}

const evidenceRoot = A.evidenceRoot;
if (!evidenceRoot || typeof evidenceRoot !== "string") {
  throw new Error(
    "kbli-batch-a-lot: args.evidenceRoot is required (local dir already populated by dossier_pull.py --out)",
  );
}

const rawCodes = Array.isArray(A.codes) ? A.codes : [];
if (!rawCodes.length) {
  throw new Error(
    "kbli-batch-a-lot: args.codes must be a non-empty array of codes or {code, innocenceControl} — lot REFUSED",
  );
}
const CODES = rawCodes.map((c) =>
  typeof c === "string"
    ? { code: c, innocenceControl: false }
    : { code: String(c.code), innocenceControl: !!c.innocenceControl },
);

// ----- membership gate (deterministic, pure-JS — no LLM in a hard refusal gate) ---------------
const membership = A.membership;
if (!membership || !Array.isArray(membership.members)) {
  throw new Error(
    "kbli-batch-a-lot: args.membership is required — pass the ALREADY-PARSED contents of " +
      "data/kbli-filiera/membership/batch-a-members.json (an object with a `members` array of " +
      "{kode_kbli_2025, in_scope}). This script cannot read the file itself (no fs primitive in " +
      "the Workflow sandbox) and membership is a deterministic fact, never an LLM transcription.",
  );
}
const inScopeCodes = new Set(
  membership.members
    .filter((m) => m && m.in_scope === true)
    .map((m) => String(m.kode_kbli_2025)),
);
// In-scope membership is required ONLY for non-innocence codes (plan §1 "Batch A scope = the 114
// A-serving codes ONLY" governs the codes actually being adjudicated as Batch A members).
// Innocence controls are BY DESIGN non-members — OSS-native clean codes used as a sanity check on
// the pipeline itself (see the usage example above: `{ code: "65121", innocenceControl: true }`,
// same class as the pilot's 65121/85202/85579) — so requiring them to ALSO be in-scope contradicts
// the script's own contract. FIXED 2026-07-18: this over-match blocked a real lot dispatch (run
// wf_3477eb84-e75, "REFUSED: 2 code(s) not in-scope: 65121, 85202" — both legitimate controls).
const outOfScope = CODES.filter((c) => !c.innocenceControl)
  .map((c) => c.code)
  .filter((code) => !inScopeCodes.has(code));
if (outOfScope.length) {
  throw new Error(
    `kbli-batch-a-lot: lot ${lotId} REFUSED — ${outOfScope.length} code(s) not in-scope per the ` +
      `membership artifact (plan §1 "Batch A scope = the 114 A-serving codes ONLY"): ${outOfScope.join(", ")}`,
  );
}
// Guard the OTHER direction: an in-scope Batch A member cannot ALSO be flagged as an innocence
// control. A real member has real obligations to adjudicate — using it as a "nothing should
// change here" sanity check would either mask a genuine miss (if it silently passes) or produce a
// spurious quarantine (if the pipeline correctly finds real work to do on it).
const misusedAsInnocence = CODES.filter(
  (c) => c.innocenceControl && inScopeCodes.has(c.code),
).map((c) => c.code);
if (misusedAsInnocence.length) {
  throw new Error(
    `kbli-batch-a-lot: lot ${lotId} REFUSED — ${misusedAsInnocence.length} code(s) marked ` +
      `innocenceControl are actually in-scope Batch A members per the membership artifact (a ` +
      `member cannot double as an innocence control): ${misusedAsInnocence.join(", ")}`,
  );
}

// Lot-shape rule (plan §8 amendment A-2: "lot = contiguous taxonomy-ordered segment of >=10
// codes"). NOT a hard refusal here — the conductor forms lots, this is a courtesy WARN so a
// too-small lot's m1/m2 statistics get flagged as unreliable rather than silently trusted.
if (CODES.length < 10) {
  log(
    `WARN lot ${lotId} has only ${CODES.length} code(s) — amendment A-2 defines a lot as >=10 ` +
      `codes; m1/m2 on a smaller lot are statistically thin (one quarantine in a 2-code lot is a ` +
      `spurious breach). Proceeding, but the conductor should treat this lot's control-limit ` +
      `verdicts with reduced confidence.`,
  );
}

// ----- calibration control limits — PINNED LITERAL (plan §5; conductor-fixed from pilot A1,
// written EXACTLY as data/kbli-filiera/batch-reports/batchA-calibration.json, never re-derived).
// scripts/kbli_filiera/tests/test_lot_runner_contract.py parses THIS file as text and asserts
// these numeric literals match the calibration JSON byte-for-byte — that test is the drift guard,
// not a runtime read. Gold sets (m5) are deliberately excluded — see header note. -----------
const CALIBRATION = {
  m1_blind_concordance_floor: 0.75,
  m2_certification_rate_floor: 0.2,
  m2_certification_rate_ceiling: 0.85,
  m3_refutation_categories: [
    "code_collision",
    "illegitimate_inheritance",
    "wrong_authority_level",
    "phantom_source_pointer",
    "source_absent_in_vault",
  ],
  m4_tokens_per_dossier_ceiling: 400000,
};

// ----- lease guard (SKIP-with-WARN — see header note; per-code, before that code's adjudication
// starts) ----------------------------------------------------------------------------------
function leaseGuardWarn(code) {
  log(
    `LEASE-GUARD SKIPPED (no bash/exec primitive available to Workflow scripts — verified against ` +
      `every infra/workflows/*.js; spec says "do not invent new infra") — code=${code} lot=${lotId} ` +
      `MUST be leased by the CALLER before this run: ` +
      `python3 scripts/agent_lease.py acquire kbli-dossier:${code} --task-id <lot ${lotId} run id> ` +
      `--ttl-s 900 (plan §2 P3: "every dossier claim goes through agent_lock:kbli-dossier:<code>. ` +
      `No lease, no touch."). This is an observability WARN only, not an enforced gate.`,
  );
}

// ----- schemas — every non-deterministic proposal is FORCED into a structured shape a downstream
// compiler (dossier_assemble.py) can validate against evidence pointers before it ever lands as a
// fact (Garuda law, workflow doc §1). D1/D2 keep the pilot's shape (D1 gains an optional
// problem_category + abstain field); D5 is REWRITTEN into an independent-conclusion shape with no
// "verdict" field (see the D5 BLIND-REFUTATION FIX header note — the compiler decides the verdict,
// never the seat); the innocence branch stays on the frozen 3-token taxonomy. ------------------

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

// closed refutation/problem-category registry (plan §5 m3) — shared by D1's optional
// problem_category and D5's own, so the compiler diff (diffD1D5(), per-code adjudication section
// below) can compare them directly. Declared before both schemas: referenced by both.
const REFUTATION_CATEGORIES = [
  "code_collision",
  "illegitimate_inheritance",
  "wrong_authority_level",
  "phantom_source_pointer",
  "source_absent_in_vault",
];

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
    problem_category: {
      type: "string",
      enum: [...REFUTATION_CATEGORIES, "OTHER_NEW_CATEGORY"],
      description:
        "REQUIRED when needs_quarantine=true — classify into the plan §5 CLOSED registry (mirrors " +
        "D5's own problem_category so the compiler can diff them). Literal sentinel " +
        "OTHER_NEW_CATEGORY if genuinely none fit — never invent a new label.",
    },
    abstain: {
      type: "object",
      description:
        "set ONLY if this code's determination genuinely requires an OUT-OF-SCOPE facet " +
        "(pma_status/l4_bali/TKA, plan §8 A-1) — never guess, flag instead.",
      properties: {
        needed: { type: "boolean" },
        facet: { type: "string" },
      },
    },
    notes: { type: "string" },
  },
};

// D5 — the BLIND refuter (plan §3/A4, red-team F5). Receives ONLY code + evidence dir (see
// d5Prompt below) and reports its OWN independent conclusion: no "verdict" field here — D5 never
// decides certified/quarantined itself, that is the deterministic compiler diff's job
// (diffD1D5(), per-code adjudication section below), never a seat's.
const D5_SCHEMA = {
  type: "object",
  required: [
    "mapping_type",
    "licensing_inherits",
    "problem_found",
    "rationale",
  ],
  properties: {
    mapping_type: {
      type: "string",
      enum: ["ONE_TO_ONE", "SPLIT", "MERGE", "COLLISION", "NO_MAPPING"],
      description:
        "your OWN independently-derived crosswalk classification for this code — you have not " +
        "seen and will never be shown any other seat's proposal for this code",
    },
    licensing_inherits: {
      type: "boolean",
      description:
        "your OWN independent conclusion on whether this code's licensing facts inherit from a " +
        "KBLI-2020-vintage PP28 source",
    },
    problem_found: {
      type: "boolean",
      description:
        "true if YOUR OWN independent read surfaces an issue serious enough for conductor triage " +
        "(ambiguous mapping, thin evidence, wrong-mode source, absent source, wrong authority " +
        "level, etc.). Default true when uncertain — a refuter that rubber-stamps because it " +
        "cannot be bothered to re-derive is worse than no refuter at all.",
    },
    problem_category: {
      type: "string",
      enum: [...REFUTATION_CATEGORIES, "OTHER_NEW_CATEGORY"],
      description:
        "REQUIRED when problem_found=true — classify into the plan §5 CLOSED registry. If none of " +
        "the 5 named categories fit, use the literal sentinel OTHER_NEW_CATEGORY — never invent a " +
        "new label; a genuinely new category is itself a program-level finding (automatic lot " +
        "pause, plan §5), not a place to be creative with taxonomy.",
    },
    rationale: {
      type: "string",
      description:
        "uraian-level semantic rationale for your independent conclusion",
    },
    evidence_locators: { type: "array", items: RENDER_REF },
    abstain: {
      type: "object",
      description:
        "set ONLY if this code's determination genuinely requires an OUT-OF-SCOPE facet " +
        "(pma_status/l4_bali/TKA, plan §8 A-1) — never guess, flag instead.",
      properties: {
        needed: { type: "boolean" },
        facet: { type: "string" },
      },
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

// Frozen taxonomy end-to-end (pilot-report criterion #6 fix): the innocence branch emits ONLY
// certified | quarantined | abstained — never the pilot's 4-token vocabulary.
const INNOCENCE_SCHEMA = {
  type: "object",
  required: ["changes_proposed", "verdict"],
  properties: {
    changes_proposed: {
      type: "array",
      items: { type: "string" },
      description:
        "MUST be empty when verdict=certified — any entry here is itself a finding of over-extraction, not a legitimate regulatory discovery",
    },
    verdict: {
      type: "string",
      enum: ["certified", "quarantined", "abstained"],
      description:
        "certified = nothing needs changing (the frozen-taxonomy normalization of a true innocence " +
        "control); quarantined = an unexpected change is proposed (over-extraction finding, needs " +
        "conductor triage); abstained = the code turns out to depend on an OUT-OF-SCOPE facet " +
        "(pma_status/l4_bali/TKA, plan §8 A-1) that cannot be adjudicated this pass",
    },
    notes: { type: "string" },
  },
};

// ----- prompts ---------------------------------------------------------------------------------

const OUT_OF_SCOPE_NOTICE =
  "OUT OF SCOPE THIS PASS (plan §8 amendment A-1 — the P1-v2 vault wave is deferred): " +
  "pma_status, l4_bali, and TKA facets. If this code's determination would require one of those " +
  "three, do NOT guess.";

function evidenceDirFor(code) {
  return `${evidenceRoot}/${code}`;
}

function innocencePrompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `INNOCENCE CONTROL — KBLI-2025 code ${code} (GARUDA-FILIERA Batch A lot ${lotId}, OSS-native, no ` +
    `pp28_sources — the dossier MUST come out boring). ${OUT_OF_SCOPE_NOTICE} Read ${dir}/canonical.json, ` +
    `${dir}/evidence-index.json, and every file under ${dir}/oss/, ${dir}/crosswalk/, ${dir}/pp28/ ` +
    `(renders or their ABSENT/NOT_APPLICABLE verdict). Verify that NOTHING needs changing. Hold ` +
    `yourself to the pilot's bar: any proposed change here is itself a finding of over-extraction in ` +
    `the pipeline, not a legitimate regulatory discovery — do not manufacture a finding to seem ` +
    `thorough. Emit verdict=certified if boring as expected, verdict=quarantined if you find an ` +
    `unexpected change is needed, verdict=abstained only if an out-of-scope facet above blocks you.`
  );
}

function d1Prompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `D1 crosswalk adjudication — KBLI-2025 code ${code} (GARUDA-FILIERA Batch A lot ${lotId}, workflow ` +
    `doc §3 D1). ${OUT_OF_SCOPE_NOTICE} Read ${dir}/canonical.json for the code's own record ` +
    `(pp28_sources, sektor_id, per_skala), then read every PNG under ${dir}/crosswalk/*.png (BPS Vol.2 ` +
    `Lampiran 5/10 rendered page hits) and ${dir}/pp28/*.png (PP28 lampiran rendered page hits) — where ` +
    `a layer instead has an ABSENT.json or NOT_APPLICABLE.json, read that and record the layer as ` +
    `absent/not-applicable rather than guessing. Adjudicate the 2020<->2025 crosswalk mapping with ` +
    `uraian-level SEMANTIC rationale from the rendered text — title-similarity alone is FORBIDDEN ` +
    `(kbli-navigator SKILL.md §4.2, "il contesto batte il titolo" — signature of a wrong remap: ` +
    `mapping_type=SPLIT applied as a single code + boilerplate reasoning). Every digit you cite from a ` +
    `render is evidence only because you looked at the IMAGE, never because pdftotext said so (OCR ` +
    `trap: "68112" can render as "681t2"). Set needs_quarantine=true if the mapping is ambiguous or the ` +
    `evidence is thin. Set licensing_inherits=true only if this code's licensing facts visibly come ` +
    `from a KBLI-2020-vintage PP28 source that would need image-verified row extraction (D2). If one ` +
    `of the three out-of-scope facets above blocks your determination, set abstain={needed:true, ` +
    `facet:"<name>"} instead of guessing. If needs_quarantine=true, also set problem_category to the ` +
    `ONE closed-registry label (code_collision / illegitimate_inheritance / wrong_authority_level / ` +
    `phantom_source_pointer / source_absent_in_vault) that best fits your reason — or the literal ` +
    `sentinel OTHER_NEW_CATEGORY if genuinely none fit (never invent a new label).`
  );
}

function d5Prompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `D5 independent verification — KBLI-2025 code ${code} (GARUDA-FILIERA Batch A lot ${lotId}, plan ` +
    `§3/A4: "the D5 refuter re-extracts blind — render + code, NEVER the extractor's answer; the ` +
    `COMPILER diffs the two extractions, only a match certifies"). ${OUT_OF_SCOPE_NOTICE} You are a ` +
    `SEPARATE, BLIND, independent adjudicator for this code — you have NOT been shown, and will never ` +
    `be shown, any other seat's proposal or conclusion for this code, before or after your own answer. ` +
    `Read ${dir}/canonical.json for the code's own record (pp28_sources, sektor_id, per_skala), then ` +
    `every PNG under ${dir}/crosswalk/*.png (BPS Vol.2 Lampiran 5/10 rendered page hits) and ` +
    `${dir}/pp28/*.png (PP28 lampiran rendered page hits) — or their ABSENT/NOT_APPLICABLE verdicts. ` +
    `Independently derive your OWN crosswalk mapping_type and licensing_inherits conclusion, exactly as ` +
    `if you were the first and only adjudicator ever assigned this code. Title-similarity alone is ` +
    `FORBIDDEN (kbli-navigator SKILL.md §4.2, "il contesto batte il titolo"). Every digit you cite from ` +
    `a render is evidence only because you looked at the IMAGE, never because pdftotext said so (OCR ` +
    `trap: "68112" can render as "681t2"). Set problem_found=true (default when uncertain) if the ` +
    `mapping is ambiguous, the evidence is thin, or you find any of: same-digit cross-vintage collision, ` +
    `illegitimate licensing inheritance, wrong authority level, a phantom/wrong source pointer, or a ` +
    `source absent from the vault — a refuter that rubber-stamps because it cannot be bothered to ` +
    `re-derive is worse than no refuter at all. If problem_found=true, set problem_category to the ONE ` +
    `closed-registry label that best fits, or the literal sentinel OTHER_NEW_CATEGORY if genuinely none ` +
    `fit (never invent a new label). If one of the three out-of-scope facets above blocks your ` +
    `determination, set abstain={needed:true, facet:"<name>"} instead of guessing. The WORKFLOW, not ` +
    `you, compares your conclusion against D1's — that comparison happens entirely outside your context.`
  );
}

function d2Prompt(code) {
  const dir = evidenceDirFor(code);
  return (
    `D2 image-verified extraction — KBLI-2025 code ${code} (GARUDA-FILIERA Batch A lot ${lotId}, ` +
    `workflow doc §3 D2, self-confirming, red-team F8 locator-poisoning guard). ${OUT_OF_SCOPE_NOTICE} ` +
    `Read every PNG under ${dir}/pp28/*.png. Extract per_skala rows (skala_usaha, kategori_risiko, ` +
    `perizinan, persyaratan, kewajiban) DIRECTLY FROM THE IMAGE TEXT — never infer a value from the ` +
    `code number or from prior knowledge of similar codes. Self-confirming guard: independently confirm ` +
    `the code string "${code}" (or its cited KBLI-2020 pp28 source) ACTUALLY appears in the row you ` +
    `read, and report the codes of the NEIGHBORING rows in the same table — a mismatch there is how a ` +
    `locator-poisoning error gets caught before it becomes a certified fact. Every field carries a ` +
    `render_ref {file, page, row}.`
  );
}

// ----- per-code adjudication ---------------------------------------------------------------

function normalizeVerdict(verdict) {
  return ["certified", "quarantined", "abstained"].includes(verdict)
    ? verdict
    : "quarantined"; // fail-closed: an out-of-taxonomy verdict is treated as needing conductor triage
}

async function adjudicateInnocence(code) {
  leaseGuardWarn(code);
  const raw = await agent(innocencePrompt(code), {
    label: `innocence:${code}`,
    phase: "Adjudicate",
    schema: INNOCENCE_SCHEMA,
    model: "sonnet",
  });
  const verdict = raw ? normalizeVerdict(raw.verdict) : "quarantined";
  return {
    code,
    innocenceControl: true,
    innocence: true,
    innocence_verdict: raw,
    verdict,
    quarantined: verdict === "quarantined",
    seatInvocations: 1,
  };
}

// ----- D1/D5 compiler diff (plan §3/A4) — DETERMINISTIC, pure JS, never a seat: "the COMPILER
// diffs the two extractions — only a match certifies". Neither derive function receives the
// OTHER seat's raw output; each reduces ITS OWN seat's schema down to the four substantive fields
// the diff compares, so the diff itself never has to know each schema's original shape. ---------

function deriveD1Comparable(d1) {
  const mappingTypes = Array.isArray(d1 && d1.mappings)
    ? Array.from(
        new Set(d1.mappings.map((m) => m && m.mapping_type).filter(Boolean)),
      )
    : [];
  // a code's overall crosswalk shape is one label even when D1 proposed multiple mapping rows
  // (a SPLIT/MERGE still has ONE mapping_type describing the code's own relationship); if D1's
  // own rows disagree on the label that is itself worth surfacing, not silently resolved here.
  const mapping_type =
    mappingTypes.length === 1
      ? mappingTypes[0]
      : mappingTypes.length > 1
        ? "MIXED"
        : null;
  return {
    mapping_type,
    licensing_inherits: d1 ? d1.licensing_inherits === true : null,
    problem_found: d1 ? Boolean(d1.needs_quarantine) : true,
    problem_category: (d1 && d1.problem_category) || null,
  };
}

function deriveD5Comparable(d5) {
  return {
    mapping_type: d5 ? d5.mapping_type || null : null,
    licensing_inherits: d5 ? d5.licensing_inherits === true : null,
    problem_found: d5 ? Boolean(d5.problem_found) : true,
    problem_category: (d5 && d5.problem_category) || null,
  };
}

function diffD1D5(d1c, d5c) {
  const fieldsAgree =
    d1c.mapping_type === d5c.mapping_type &&
    d1c.licensing_inherits === d5c.licensing_inherits &&
    d1c.problem_found === d5c.problem_found;

  if (fieldsAgree && !d1c.problem_found) {
    return {
      verdict: "certified",
      category: null,
      divergent: false,
      category_mismatch: false,
      concordant: true,
    };
  }
  if (fieldsAgree && d1c.problem_found) {
    const category_mismatch = Boolean(
      d1c.problem_category &&
      d5c.problem_category &&
      d1c.problem_category !== d5c.problem_category,
    );
    return {
      verdict: "quarantined",
      category: d5c.problem_category || d1c.problem_category || null,
      divergent: false,
      category_mismatch,
      concordant: true,
    };
  }
  // ANY divergence (mapping_type/licensing_inherits/problem_found not all equal) -> quarantined,
  // never averaged, never code-picked beyond this rule (plan §3/A4). Category comes from
  // whichever side actually flagged a problem — if both diverge without either flagging, category
  // stays null (an honest "shapes disagree but neither called it a problem" state).
  const category = d5c.problem_found
    ? d5c.problem_category
    : d1c.problem_found
      ? d1c.problem_category
      : null;
  return {
    verdict: "quarantined",
    category: category || null,
    divergent: true,
    category_mismatch: false,
    concordant: false,
  };
}

async function adjudicateCode(code) {
  leaseGuardWarn(code);

  const d1 = await agent(d1Prompt(code), {
    label: `D1:${code}`,
    phase: "Adjudicate",
    schema: D1_SCHEMA,
    model: "sonnet",
  });

  // D5 is a SEPARATE, blind adjudicator — receives ONLY code+evidence, NEVER d1's proposal (plan
  // §3/A4, red-team F5; see the D5 BLIND-REFUTATION FIX header note).
  const d5 = await agent(d5Prompt(code), {
    label: `D5:${code}`,
    phase: "Adjudicate",
    schema: D5_SCHEMA,
    model: "sonnet",
  });

  const diff = diffD1D5(deriveD1Comparable(d1), deriveD5Comparable(d5));

  const abstainNeeded =
    Boolean(d1 && d1.abstain && d1.abstain.needed) ||
    Boolean(d5 && d5.abstain && d5.abstain.needed);
  // an out-of-scope-facet claim from EITHER seat overrides the diff outright — "the visible facts
  // agree" is a weaker claim than "this needs evidence we don't have this pass" (plan §8 A-1).
  const preD2Verdict = abstainNeeded ? "abstained" : diff.verdict;

  let d2 = null;
  if (preD2Verdict === "certified" && d1 && d1.licensing_inherits === true) {
    d2 = await agent(d2Prompt(code), {
      label: `D2:${code}`,
      phase: "Adjudicate",
      schema: D2_SCHEMA,
      model: "sonnet",
    });
  }

  // D2 SELF-CONFIRM RETRO-DEMOTE (post-Lot-A-L1 close-out fix, 2026-07-18): a certified verdict
  // whose D2 extraction FAILED its own self-confirming guard (self_confirmed.code_appears_in_row
  // !== true, red-team F8 locator-poisoning check) or came back with EMPTY per_skala_rows must be
  // impossible by construction — "certified" cannot mean "D1/D5 agreed AND we never actually
  // confirmed the row". This is exactly what happened to code 38222 in Lot A-L1: D1 and D5
  // independently agreed clean (preD2Verdict="certified"), but the D2 evidence page only carried
  // the PARENT code 38220, not 38222 itself — self_confirmed.code_appears_in_row=false — and the
  // runner still emitted "certified" because nothing downstream of D2 ever looked at its own
  // self-confirmation result. The conductor caught it at D6 review; this closes the runner gap so
  // the same class of miss can't reach "certified" again. Category=phantom_source_pointer (closed
  // registry, plan §5 m3): "the cited row/source doesn't actually confirm the code" is precisely
  // what a failed self-confirmation means.
  const d2SelfConfirmFailed =
    d2 !== null &&
    (!d2.self_confirmed ||
      d2.self_confirmed.code_appears_in_row !== true ||
      !Array.isArray(d2.per_skala_rows) ||
      d2.per_skala_rows.length === 0);

  const verdict = d2SelfConfirmFailed ? "quarantined" : preD2Verdict;
  const quarantined = verdict === "quarantined";
  const category = quarantined
    ? d2SelfConfirmFailed
      ? "phantom_source_pointer"
      : diff.category
    : null;

  return {
    code,
    innocenceControl: false,
    innocence: false,
    d1,
    d5,
    d2,
    quarantined,
    concordant: diff.concordant,
    verdict,
    category,
    divergent: diff.divergent,
    category_mismatch: diff.category_mismatch,
    d2_self_confirm_failed: d2SelfConfirmFailed,
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

phase("Report");
const settled = results.filter(Boolean);
const adjudicated = settled.filter((r) => !r.innocenceControl);
const innocenceResults = settled.filter((r) => r.innocenceControl);

const certifiedCount = adjudicated.filter(
  (r) => r.verdict === "certified",
).length;
const quarantinedCount = adjudicated.filter(
  (r) => r.verdict === "quarantined",
).length;
const abstainedCount = adjudicated.filter(
  (r) => r.verdict === "abstained",
).length;
const concordantCount = adjudicated.filter((r) => r.concordant).length;

const m1Value = adjudicated.length
  ? concordantCount / adjudicated.length
  : null;
const m2Value = adjudicated.length ? certifiedCount / adjudicated.length : null;

const quarantinedResults = adjudicated.filter(
  (r) => r.verdict === "quarantined",
);
const categoriesSeen = Array.from(
  new Set(quarantinedResults.map((r) => r.category).filter(Boolean)),
);
const missingCategory = quarantinedResults
  .filter((r) => !r.category)
  .map((r) => r.code);
const categoryMismatches = adjudicated
  .filter((r) => r.category_mismatch)
  .map((r) => r.code);
const divergentCodes = adjudicated
  .filter((r) => r.divergent)
  .map((r) => r.code);
const newCategorySeen =
  categoriesSeen.includes("OTHER_NEW_CATEGORY") ||
  categoriesSeen.some((c) => !CALIBRATION.m3_refutation_categories.includes(c));

const limitsBreached = [];
if (m1Value !== null && m1Value < CALIBRATION.m1_blind_concordance_floor) {
  limitsBreached.push(
    `m1 breach: blind-concordance ${m1Value.toFixed(3)} < floor ${CALIBRATION.m1_blind_concordance_floor}`,
  );
}
if (
  m2Value !== null &&
  (m2Value < CALIBRATION.m2_certification_rate_floor ||
    m2Value > CALIBRATION.m2_certification_rate_ceiling)
) {
  limitsBreached.push(
    `m2 breach: certification rate ${m2Value.toFixed(3)} outside [${CALIBRATION.m2_certification_rate_floor}, ${CALIBRATION.m2_certification_rate_ceiling}]`,
  );
}
if (newCategorySeen) {
  limitsBreached.push(
    `m3 breach: refutation category outside the closed registry seen — categoriesSeen=${JSON.stringify(categoriesSeen)}`,
  );
}
if (missingCategory.length) {
  limitsBreached.push(
    `m3 data-gap: quarantined dossier(s) with no problem_category from either seat (divergent on ` +
      `mapping_type/licensing_inherits without either flagging a problem): ${missingCategory.join(", ")}`,
  );
}
// m4 (tokens/dossier) is INTENTIONALLY absent from limitsBreached: per-seat token accounting is a
// harness-level run-log metric (workflowProgress), not observable from inside agent()'s return
// value — the pilot script documented this exact limitation (kbli-pilot-a1.js "NOTE"). Reporting
// a fabricated number here would be worse than reporting none (anti-hallucination discipline).

const lotReport = {
  lot_id: lotId,
  codes: CODES.map((c) => c.code),
  verdicts: settled.map((r) => ({
    code: r.code,
    innocenceControl: r.innocenceControl,
    verdict: r.verdict,
  })),
  m1_blind_concordance: {
    value: m1Value,
    floor: CALIBRATION.m1_blind_concordance_floor,
    breach:
      m1Value !== null && m1Value < CALIBRATION.m1_blind_concordance_floor,
  },
  m2_certification_rate: {
    value: m2Value,
    floor: CALIBRATION.m2_certification_rate_floor,
    ceiling: CALIBRATION.m2_certification_rate_ceiling,
    breach:
      m2Value !== null &&
      (m2Value < CALIBRATION.m2_certification_rate_floor ||
        m2Value > CALIBRATION.m2_certification_rate_ceiling),
  },
  m3_refutation_categories: {
    seen: categoriesSeen,
    closed_registry: CALIBRATION.m3_refutation_categories,
    missing_category_codes: missingCategory,
    category_mismatch_codes: categoryMismatches,
    divergent_codes: divergentCodes,
    breach: newCategorySeen,
  },
  m4_tokens_per_dossier: {
    ceiling: CALIBRATION.m4_tokens_per_dossier_ceiling,
    computable: false,
    note:
      "not observable inside this script (harness run-log metric, not part of agent()'s return " +
      "value — same limitation the pilot documented); conductor cross-references workflowProgress " +
      "against this ceiling post-lot",
  },
  m5_gold_set_hit_rate: {
    reserved_for_conductor: true,
    note:
      "gold sets are digest-blind by design (plan §5) — this script must not attempt to reverse " +
      "them; the conductor computes m5 post-lot after revealing the plaintext lists",
  },
  limits_breached: limitsBreached,
  totals: {
    total: CODES.length,
    adjudicated: adjudicated.length,
    innocenceControls: innocenceResults.length,
    certified: certifiedCount,
    quarantined: quarantinedCount,
    abstained: abstainedCount,
    totalSeatInvocations: settled.reduce(
      (sum, r) => sum + (r.seatInvocations || 0),
      0,
    ),
  },
};

log(
  `lot ${lotId}: ${settled.length}/${CODES.length} codes adjudicated — ` +
    `${certifiedCount} certified, ${quarantinedCount} quarantined, ${abstainedCount} abstained, ` +
    `${innocenceResults.length} innocence controls — limits_breached=${limitsBreached.length ? limitsBreached.join(" | ") : "none"}`,
);

// this script REPORTS, it does not pause/resume itself — plan §5 pause/resume protocol is the
// conductor's, at the lot boundary, on any lotReport.limits_breached entry.
return {
  evidenceRoot,
  lotId,
  codes: CODES.map((c) => c.code),
  results: settled,
  lotReport,
};
