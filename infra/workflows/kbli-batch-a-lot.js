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
// every seat, INCLUDING the innocence-control branch, emits ONLY the frozen three tokens
// certified | quarantined | abstained. The pilot's innocence branch emitted a 4th vocabulary
// (`boring_as_expected` / `unexpected_finding`) — that vocabulary is NOT used anywhere below
// except in this normalization comment: boring_as_expected -> certified (innocence:true),
// unexpected_finding -> quarantined (an unexpected proposed change on an innocence control is
// itself a finding of over-extraction, same bar as the pilot held it to).
//
// ABSTAIN-CLASS SCOPE (plan §8 amendment A-1): `pma_status`, `l4_bali` and `TKA` facets depend on
// the deferred P1-v2 vault wave (Perpres 10/49, Bali Gubernur overlay, Kepmenaker 228/2019) and
// are OUT OF SCOPE for every seat in this pass — a seat that would need one of those classes to
// decide MUST verdict `abstained` (pending-evidence), never guess.
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
        "per code, in parallel: lease-guard WARN -> D1 propose -> D5 blind-refute -> D2 (conditional) extract; innocence controls get a single short verification prompt, all emitting the frozen certified|quarantined|abstained taxonomy",
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
const outOfScope = CODES.map((c) => c.code).filter(
  (code) => !inScopeCodes.has(code),
);
if (outOfScope.length) {
  throw new Error(
    `kbli-batch-a-lot: lot ${lotId} REFUSED — ${outOfScope.length} code(s) not in-scope per the ` +
      `membership artifact (plan §1 "Batch A scope = the 114 A-serving codes ONLY"): ${outOfScope.join(", ")}`,
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
// fact (Garuda law, workflow doc §1). Identical to the pilot's D1/D2 shape; D5 gains
// `refutation_category` (closed registry, plan §5 m3) and the innocence branch is rewritten onto
// the frozen 3-token taxonomy (see header note). --------------------------------------------

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
    refutation_category: {
      type: "string",
      enum: [
        "code_collision",
        "illegitimate_inheritance",
        "wrong_authority_level",
        "phantom_source_pointer",
        "source_absent_in_vault",
        "OTHER_NEW_CATEGORY",
      ],
      description:
        "REQUIRED when refuted=true — classify into the plan §5 CLOSED registry. If none of the " +
        "5 named categories fit, use the literal sentinel OTHER_NEW_CATEGORY — never invent a new " +
        "label; a genuinely new category is itself a program-level finding (automatic lot pause, " +
        "plan §5), not a place to be creative with taxonomy.",
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
  "three, do NOT guess — verdict abstained (pending-evidence) and say which facet blocked you.";

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
    `from a KBLI-2020-vintage PP28 source that would need image-verified row extraction (D2).`
  );
}

function d5Prompt(code, d1Result) {
  const dir = evidenceDirFor(code);
  return (
    `D5 independent verification — KBLI-2025 code ${code} (GARUDA-FILIERA Batch A lot ${lotId}, ` +
    `workflow doc §3 D5, "blind re-extraction... agreement certifies, divergence quarantines"). ` +
    `${OUT_OF_SCOPE_NOTICE} You are the REFUTER, not the author — you did not write the proposal below ` +
    `and are not grading your own work. Read the SAME evidence D1 had access to (${dir}/canonical.json, ` +
    `${dir}/crosswalk/*.png, ${dir}/pp28/*.png, or their ABSENT/NOT_APPLICABLE verdicts) and ` +
    `independently re-derive the crosswalk mapping and licensing-inheritance conclusion BEFORE reading ` +
    `the proposal. Only after you have your own answer, compare it against the proposal: does your ` +
    `independent read AGREE, or does it REFUTE? Default refuted=true when uncertain — a refuter that ` +
    `rubber-stamps because it cannot be bothered to re-derive is worse than no refuter at all. If ` +
    `refuted=true, you MUST also set refutation_category to the ONE closed-registry label ` +
    `(code_collision / illegitimate_inheritance / wrong_authority_level / phantom_source_pointer / ` +
    `source_absent_in_vault) that best fits your reason — or the literal sentinel OTHER_NEW_CATEGORY ` +
    `if genuinely none fit (never invent a new label).\n\n` +
    `D1 PROPOSAL TO VERIFY:\n${JSON.stringify(d1Result, null, 2)}`
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

async function adjudicateCode(code) {
  leaseGuardWarn(code);

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
  // concordance (m1): D1's own caution flag and D5's independent refutation point the SAME way.
  // Operational definition for THIS runner (documented, not a re-derivation of the pilot's
  // undocumented arithmetic — the pilot's "11/12" was a conductor's own read, not computed by
  // any script): concordant iff d1.needs_quarantine === d5.refuted.
  const concordant = Boolean(d1 && d5 && d1.needs_quarantine === d5.refuted);
  const abstained = Boolean(!quarantined && d5 && d5.verdict === "abstained");
  const verdict = quarantined
    ? "quarantined"
    : abstained
      ? "abstained"
      : "certified";

  let d2 = null;
  if (!quarantined && !abstained && d1 && d1.licensing_inherits === true) {
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
    innocence: false,
    d1,
    d5,
    d2,
    quarantined,
    concordant,
    verdict,
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

const refutedWithCategory = adjudicated.filter((r) => r.d5 && r.d5.refuted);
const categoriesSeen = Array.from(
  new Set(
    refutedWithCategory.map((r) => r.d5.refutation_category).filter(Boolean),
  ),
);
const missingCategory = refutedWithCategory
  .filter((r) => !r.d5.refutation_category)
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
    `m3 data-gap: refuted dossier(s) missing refutation_category: ${missingCategory.join(", ")}`,
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
