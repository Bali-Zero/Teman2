export const meta = {
  name: "kbli-triangle-pilot",
  description:
    "KBLI card audit — deterministic Layer-0 already run; this fans out the LLM Layer-2 editorial/regulatory check over the 50 pilot codes with propose≠grade + adversarial refuter on fresh regulatory context, then synthesizes a ledger.",
  whenToUse:
    "After scripts/kbli_triangle/sweep.py has produced _out/pilot-codes.json + FINDINGS.jsonl. Validates the LLM layer on a representative sample before the full 756-text run.",
  phases: [
    {
      title: "Load",
      detail: "read pilot codes + their editorial findings + dataset slice",
    },
    {
      title: "Propose",
      detail:
        "one analyzer per code proposes corrected editorial text, grounded",
    },
    {
      title: "Refute",
      detail:
        "independent skeptic refutes each proposal on FRESH regulatory context",
    },
    {
      title: "Synthesize",
      detail: "merge survivors into a ledger; flag the rest report-only",
    },
  ],
};

// Work-list is built deterministically by a single loader agent that returns the
// FLAT list of {code, field} pairs — every R-EDIT-CAND finding in FINDINGS.jsonl.
// No code-file gating: the full editorial set IS the work. (Reading + emitting the
// flat list is mechanical; a schema'd agent does it without truncation risk because
// it returns rows, not a nested map.)
phase("Load");
const loaded = await agent(
  `You are the loader for the KBLI Triangle FULL run. Do exactly this and nothing else:
1. Read scripts/kbli_triangle/_out/FINDINGS.jsonl (JSON-lines; ~825 rows).
2. Keep ONLY rows where rule_id == "R-EDIT-CAND".
3. Return a JSON object { rows: [ {code, field}, ... ] } with ONE entry per kept row — there should be 756 of them. Do not deduplicate, do not summarize, do not cap. Use the exact "code" and "field" values from each row.
Return ONLY that object.`,
  {
    label: "load-full",
    phase: "Load",
    schema: {
      type: "object",
      properties: {
        rows: {
          type: "array",
          items: {
            type: "object",
            properties: {
              code: { type: "string" },
              field: { type: "string" },
            },
            required: ["code", "field"],
          },
        },
      },
      required: ["rows"],
    },
  },
);

const work = ((loaded && loaded.rows) || []).map((r) => ({
  code: r.code,
  field: r.field,
  evidence: "",
}));
const distinctCodes = new Set(work.map((w) => w.code)).size;
log(
  `Layer-2 FULL: ${work.length} editorial fields across ${distinctCodes} codes`,
);
if (work.length < 100) {
  log(
    `WARNING: expected ~756 fields but got ${work.length} — loader may have truncated; aborting to avoid a partial ledger.`,
  );
  return { error: "loader_undercount", got: work.length, expected: 756 };
}

// Per-field pipeline: propose (grounded) → refute (fresh skeptic) → carry verdict.
// generator≠grader is enforced by two separate agent() calls with disjoint prompts.
const VERDICT = {
  type: "object",
  properties: {
    code: { type: "string" },
    field: { type: "string" },
    is_misleading: { type: "boolean" },
    suggested_value: { type: "string" },
    regulatory_basis: { type: "string" },
    confidence: { type: "string", enum: ["HIGH", "MEDIUM", "LOW"] },
  },
  required: ["code", "field", "is_misleading", "confidence"],
};

const REFUTE = {
  type: "object",
  properties: {
    code: { type: "string" },
    field: { type: "string" },
    refuted: { type: "boolean" },
    reason: { type: "string" },
  },
  required: ["code", "field", "refuted"],
};

const results = await pipeline(
  work,
  // STAGE 1 — PROPOSE (grounded; reads the actual field + the structural verdict)
  (item) =>
    agent(
      `KBLI editorial-truth analyzer. Code ${item.code}, field ${item.field}.
The deterministic layer flagged this field as a possible foreign-ownership go-ahead on a code whose STRUCTURAL verdict is l4_bali.blocked (a PT PMA cannot register it in Bali).
Do this, grounding every claim:
1. Read source_documents/KBLI_2025_FINAL_CLEAN.json, find the record for ${item.code} (kode_kbli_2025), and read intel_2026.${item.field.split(".").pop()} plus l4_bali (status, reason, blocked) plus pma_status.
2. Decide: does the editorial text actually mislead — i.e. does it invite a PT PMA setup that the structural verdict forbids? Mind that "open nationally" is true and NOT misleading by itself; only an unqualified Bali-PMA go-ahead is.
3. If misleading: write a corrected text that keeps the national-open truth but states the Bali block, citing the regulation already in l4_bali.reason / moratorium.source. Never invent a regulation; cite only what the record or Perpres 10/2021·49/2021 / B.27.000/642 supports.
Return the verdict object.`,
      {
        label: `propose:${item.code}:${item.field.split(".").pop()}`,
        phase: "Propose",
        schema: VERDICT,
      },
    ),
  // STAGE 2 — REFUTE (independent skeptic, FRESH context, tries to destroy the claim)
  (proposal, item) => {
    if (!proposal || !proposal.is_misleading) {
      // nothing claimed misleading → nothing to refute; pass through as clean.
      return {
        code: item.code,
        field: item.field,
        verdict: proposal,
        refute: { refuted: false, reason: "no claim" },
      };
    }
    return agent(
      `KBLI adversarial refuter. A prior analyzer claims field ${item.field} on code ${item.code} is MISLEADING and proposes this replacement:
"${(proposal.suggested_value || "").slice(0, 400)}"
with regulatory basis: "${proposal.regulatory_basis || "(none)"}".
Your job is to REFUTE it. Read source_documents/KBLI_2025_FINAL_CLEAN.json for ${item.code} YOURSELF (do not trust the prior analyzer). Check:
- Is the code REALLY blocked for a PT PMA in Bali, or did the analyzer over-read? (l4_bali.blocked, pma_status, presence of a Besar scale)
- Does the cited regulation actually say what the proposal claims? If the basis is vague or fabricated, refute.
- Is the original text actually fine (e.g. it already qualifies the Bali status)?
Default to refuted=true if you are not confident the original is genuinely misleading. Return the refute object.`,
      {
        label: `refute:${item.code}:${item.field.split(".").pop()}`,
        phase: "Refute",
        schema: REFUTE,
      },
    ).then((r) => ({
      code: item.code,
      field: item.field,
      verdict: proposal,
      refute: r,
    }));
  },
);

phase("Synthesize");
const clean = results.filter(Boolean);
const confirmed = clean.filter(
  (r) => r.verdict && r.verdict.is_misleading && r.refute && !r.refute.refuted,
);
const survived_rate = clean.length
  ? Math.round((100 * confirmed.length) / clean.length)
  : 0;

const ledger = confirmed.map((r) => ({
  code: r.code,
  field: r.field,
  severity: "MED",
  suggested_value: r.verdict.suggested_value,
  regulatory_basis: r.verdict.regulatory_basis,
  confidence: r.verdict.confidence,
  proposed_by: "llm-layer2",
  verified_by: "fresh-refuter",
}));

log(
  `Layer-2 pilot done: ${clean.length} fields judged, ${confirmed.length} survived the refuter (${survived_rate}%)`,
);

return {
  pilot_fields: clean.length,
  confirmed_misleading: confirmed.length,
  survived_rate_pct: survived_rate,
  ledger,
  refuted_examples: clean
    .filter(
      (r) =>
        r.verdict && r.verdict.is_misleading && r.refute && r.refute.refuted,
    )
    .slice(0, 8)
    .map((r) => ({
      code: r.code,
      field: r.field,
      refuter_reason: r.refute.reason,
    })),
};
