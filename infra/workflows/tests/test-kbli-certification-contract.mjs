#!/usr/bin/env node
// test-kbli-certification-contract.mjs — regression test for the certification-contract patch
// shipped to infra/workflows/kbli-batch-a-lot.js by the GARUDA-FILIERA Batch A Lot 6 conductor
// gate (BLOCKER 2, mandatory — research/operations/2026-07-19-kbli-batch-a-lot6-conductor-gate.md
// §3.4/§5.3).
//
// WHY THIS FILE EXISTS (and why it is NOT a pytest-regex contract test like
// scripts/kbli_filiera/tests/test_lot_runner_contract.py): the runner is a Workflow-DSL script —
// it uses a top-level `export const meta` (ESM-only syntax) AND top-level `await`/`return`
// (illegal in a plain ES module or a bare Function body). It is never executed by
// `node <file>.js` directly; the harness that runs it supplies `args`/`agent`/`log`/`phase`/
// `parallel` as injected bindings and wraps the body specially. There is no existing
// infra/workflows/tests/ harness in this repo (checked: no .mjs test file exists here before
// this PR, and PRs #2776/#2778 shipped their runner changes with ONLY the pytest regex-contract
// tests under scripts/kbli_filiera/tests/test_lot_runner_contract.py — never a node-executable
// behavioral test). This file is new: it loads the ACTUAL runner source, strips only the one
// ESM-only token (`export ` before `const meta`), compiles the rest as an AsyncFunction body
// (top-level `await`/`return` are both legal inside a function), and drives it end-to-end with a
// stub `agent()` — so the assertions below exercise the REAL diffD1D5()/factsInventoryUnverified()/
// adjudicateCode() logic, not a re-implementation of it.
//
// Run: node infra/workflows/tests/test-kbli-certification-contract.mjs
// (no dependencies beyond Node's own node:assert/node:fs/node:path — Node >=18)

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RUNNER_PATH = path.resolve(__dirname, "../kbli-batch-a-lot.js");

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

/**
 * Compile the runner source into a callable async function, with a stubbed `agent()` that
 * returns whatever the test supplies via `answers` (keyed by the seat label prefix: "D1:",
 * "D5:", "D2:"). `log`/`phase` are no-ops; `parallel` mirrors the harness's real semantics
 * (an array of zero-arg thunks, run concurrently, resolved in order).
 */
function compileRunner() {
  let src = readFileSync(RUNNER_PATH, "utf8");
  // The harness's real loader handles `export const meta` specially; for this standalone
  // compile we only need the executable body, so strip the one ESM-only token.
  src = src.replace(/^export const meta/m, "const meta");
  return new AsyncFunction("args", "agent", "log", "phase", "parallel", src);
}

function makeAgentStub(answers) {
  const calls = [];
  return async function agent(_prompt, opts) {
    calls.push(opts.label);
    const kind = opts.label.split(":")[0]; // "D1" | "D5" | "D2"
    if (!(kind in answers)) {
      throw new Error(
        `test stub: no canned answer for seat ${kind} (label=${opts.label})`,
      );
    }
    const value = answers[kind];
    return typeof value === "function" ? value(opts) : value;
  };
}

async function parallelStub(thunks) {
  return Promise.all(thunks.map((fn) => fn()));
}

async function runLot({
  code,
  d1,
  d5,
  d2,
  innocenceControl = false,
  runnerBlobSha256,
}) {
  const runnerFn = compileRunner();
  const agent = makeAgentStub({ D1: d1, D5: d5, D2: d2 });
  const args = {
    lot_id: "TEST-LOT",
    // an innocenceControl code must NOT also be an in-scope member (the runner's own
    // misusedAsInnocence guard refuses that combination) — membership only marks in_scope=true
    // for the ordinary member path.
    codes: [innocenceControl ? { code, innocenceControl: true } : code],
    evidenceRoot: "/tmp/does-not-matter-for-this-stub",
    membership: {
      members: [{ kode_kbli_2025: code, in_scope: !innocenceControl }],
    },
    ...(runnerBlobSha256 ? { runnerBlobSha256 } : {}),
  };
  const result = await runnerFn(
    args,
    agent,
    () => {},
    () => {},
    parallelStub,
  );
  return result.results[0];
}

// ---------------------------------------------------------------------------
// Fixture builders — minimal valid D1/D5/D2 payloads per schema, varied only in the fields each
// test cares about.
// ---------------------------------------------------------------------------

function d1Clean(overrides = {}) {
  return {
    mappings: [
      {
        kbli2020: "80200",
        kbli2025: "80190",
        mapping_type: "ONE_TO_ONE",
        rationale: "test fixture",
      },
    ],
    confidence: "high",
    needs_quarantine: false,
    licensing_inherits: false,
    ...overrides,
  };
}

function d5Clean({ exposedFactsInventory, ...overrides } = {}) {
  return {
    mapping_type: "ONE_TO_ONE",
    licensing_inherits: false,
    problem_found: false,
    rationale: "test fixture — independently re-derived, agrees with D1",
    exposed_facts_inventory: exposedFactsInventory ?? [],
    ...overrides,
  };
}

// Derived-fact fixture builder (contract refinement #2, Lot 7 gate §3.5/§5.4): a per_skala tier's
// base facts (kategori_risiko, jangka_waktu) plus one derived fiktif_positif entry, varied only in
// whether the base facts are verified and whether/how the derivation is cited.
function derivedFactInventory({
  tier = "Besar",
  riskValue = "Menengah Tinggi",
  baseFactsVerified = true,
  fiktifStatus = "verified",
  fiktifCitation,
} = {}) {
  const suffix = tier ? `:${tier}` : "";
  return [
    {
      field: `kategori_risiko${suffix}`,
      value: riskValue,
      source_locator: baseFactsVerified ? "PP28 render p.23 row 5" : "",
      vintage: baseFactsVerified ? "2020" : "",
      status: baseFactsVerified ? "verified" : "absent",
    },
    {
      field: `jangka_waktu${suffix}`,
      value: "7",
      source_locator: baseFactsVerified ? "PP28 render p.23 row 5" : "",
      vintage: baseFactsVerified ? "2020" : "",
      status: baseFactsVerified ? "verified" : "absent",
    },
    {
      field: `fiktif_positif${suffix}`,
      value: "true",
      source_locator: "",
      vintage: "",
      status: fiktifStatus,
      ...(fiktifCitation ? { derivation_citation: fiktifCitation } : {}),
    },
  ];
}

const VALID_MT_CITATION = {
  script: "scripts/derive_fiktif_positif.py",
  instrument: "PP 28/2025",
  article: "225(1)",
  vintage: "2025",
};

// ---------------------------------------------------------------------------
// TEST 1 (GUILT, the key case from the mandate): a per_skala tier with
// kategori_risiko=Tinggi + perizinan=[] + no resolvable source must NOT certify, even though
// D1/D5 concordantly agree clean on {mapping_type, licensing_inherits, problem_found} — the exact
// shape that let 80190 through the first time (licensing_inherits=false skips D2 entirely).
// ---------------------------------------------------------------------------

async function test_unverified_tinggi_fact_blocks_certification() {
  const result = await runLot({
    code: "80190",
    d1: d1Clean(),
    d5: d5Clean({
      exposedFactsInventory: [
        {
          field: "kategori_risiko",
          value: "Tinggi",
          source_locator: "",
          vintage: "",
          status: "absent",
        },
        {
          field: "derived_license",
          value: "NIB + Izin",
          source_locator: "",
          vintage: "",
          status: "absent",
        },
      ],
    }),
    d2: null,
  });

  assert.equal(
    result.verdict,
    "quarantined",
    `expected quarantined (unverified Tinggi fact must block certification), got ${result.verdict}`,
  );
  assert.equal(
    result.facts_inventory_failed,
    true,
    "facts_inventory_failed must be true",
  );
  assert.equal(
    result.category,
    "source_absent_in_vault",
    `expected category source_absent_in_vault, got ${result.category}`,
  );
  console.log(
    "PASS: unverified Tinggi fact + perizinan=[] + no resolvable source -> quarantined",
  );
}

// ---------------------------------------------------------------------------
// TEST 2 (INNOCENCE, mandatory per the mandate): a record with a FULLY VERIFIED per-field
// inventory CAN still be certified — proves the gate does not make certification impossible by
// construction.
// ---------------------------------------------------------------------------

async function test_fully_verified_inventory_can_still_certify() {
  const result = await runLot({
    code: "59201",
    d1: d1Clean({
      mappings: [
        {
          kbli2020: "59201",
          kbli2025: "59201",
          mapping_type: "ONE_TO_ONE",
          rationale: "self-referencing, clean",
        },
      ],
    }),
    d5: d5Clean({
      exposedFactsInventory: [
        {
          field: "kategori_risiko",
          value: "Rendah",
          source_locator: "OSS RBA risk endpoint, 2025 record",
          vintage: "2025",
          status: "verified",
        },
      ],
    }),
    d2: null,
  });

  assert.equal(
    result.verdict,
    "certified",
    `expected certified (fully verified inventory must not be blocked), got ${result.verdict}`,
  );
  assert.equal(
    result.facts_inventory_failed,
    false,
    "facts_inventory_failed must be false",
  );
  assert.equal(
    result.category,
    null,
    "a certified verdict must carry no category",
  );
  console.log(
    "PASS: fully verified per-field inventory -> still certified (not impossible by construction)",
  );
}

// ---------------------------------------------------------------------------
// TEST 3 (INNOCENCE): a genuinely empty per_skala (no client-facing facts to verify at all)
// legitimately returns an empty inventory — vacuously fine, must not block certification.
// ---------------------------------------------------------------------------

async function test_genuinely_empty_inventory_is_vacuously_fine() {
  const result = await runLot({
    code: "59140",
    d1: d1Clean({
      mappings: [
        {
          kbli2020: "59140",
          kbli2025: "59140",
          mapping_type: "ONE_TO_ONE",
          rationale: "self-referencing, no per_skala rows at all",
        },
      ],
    }),
    d5: d5Clean({ exposedFactsInventory: [] }),
    d2: null,
  });

  assert.equal(
    result.verdict,
    "certified",
    `expected certified (empty inventory on a genuinely fact-free record is vacuously fine), got ${result.verdict}`,
  );
  assert.equal(result.facts_inventory_failed, false);
  console.log(
    "PASS: genuinely empty exposed_facts_inventory does not block certification",
  );
}

// ---------------------------------------------------------------------------
// TEST 4 (GUILT): the gate is fail-closed if D5 omits exposed_facts_inventory entirely (should
// never happen given the schema's `required`, but the deterministic function must not silently
// pass a malformed/missing inventory through to certification).
// ---------------------------------------------------------------------------

async function test_missing_inventory_fails_closed() {
  const d5Malformed = d5Clean();
  delete d5Malformed.exposed_facts_inventory;

  const result = await runLot({
    code: "80190",
    d1: d1Clean(),
    d5: d5Malformed,
    d2: null,
  });

  assert.equal(
    result.verdict,
    "quarantined",
    `expected quarantined (missing exposed_facts_inventory must fail closed), got ${result.verdict}`,
  );
  assert.equal(result.facts_inventory_failed, true);
  console.log(
    "PASS: missing exposed_facts_inventory fails closed (never a silent pass-through)",
  );
}

// ---------------------------------------------------------------------------
// TEST 5 (INNOCENCE): certification becomes STRICTER only — the patch must never interfere with
// an ALREADY-quarantined verdict (divergent D1/D5), regardless of what exposed_facts_inventory
// says. Proves factsInventoryFailed can only ever demote, never promote or otherwise alter a
// non-certified path.
// ---------------------------------------------------------------------------

async function test_already_quarantined_path_is_unaffected_by_the_patch() {
  const result = await runLot({
    code: "75009",
    d1: d1Clean({ needs_quarantine: false }), // D1 clean
    d5: d5Clean({
      mapping_type: "SPLIT", // D5 diverges from D1 -> quarantined by the pre-existing divergence rule
      problem_found: true,
      problem_category: "wrong_authority_level",
      exposedFactsInventory: [
        {
          field: "kategori_risiko",
          value: "Menengah Tinggi",
          source_locator: "p.408 row 3",
          vintage: "2020",
          status: "verified",
        },
      ], // fully verified — irrelevant, D1/D5 already diverged before this gate runs
    }),
    d2: null,
  });

  assert.equal(
    result.verdict,
    "quarantined",
    `expected quarantined via the pre-existing divergence rule regardless of a verified inventory, got ${result.verdict}`,
  );
  assert.equal(
    result.category,
    "wrong_authority_level",
    "category must come from the divergence rule (diff.category), not be overwritten by the facts-inventory gate",
  );
  assert.equal(
    result.facts_inventory_failed,
    false,
    "factsInventoryFailed must be false when preD2Verdict was never 'certified' in the first place",
  );
  console.log(
    "PASS: an already-quarantined (divergent) verdict is untouched by the certification-contract patch",
  );
}

// ---------------------------------------------------------------------------
// TESTS 6-9 (contract refinement #2, Lot 7 gate §3.5/§5.4): the derived-fact certification rule.
// A rule-DERIVED entry (fiktif_positif / derived_license) can never carry its own page/row locator
// — it is a legal consequence, not a printed fact — so status="verified" alone must not be
// sufficient; it additionally needs its base facts verified AND a correctly-articled derivation
// citation. This is the mechanism that keeps a record shaped like the 41013 innocence control
// (Lot 7 gate §3.5: base facts known, fiktif_positif asserted true, no citable provenance)
// quarantined even under a seat that has correctly internalized "a derived fact needs no locator
// of its own" — the NEW guilt case this refinement targets is a seat marking status="verified"
// on that basis alone, without ever checking or citing the actual derivation rule.
// ---------------------------------------------------------------------------

async function test_derived_fact_verified_without_citation_blocks_certification() {
  // GUILT: base facts (kategori_risiko, jangka_waktu) verified, fiktif_positif marked verified,
  // but NO derivation_citation at all — must not certify. This is the 41013-motivating shape: a
  // seat that knows "derived facts need no locator" must still be forced to cite the formula.
  const result = await runLot({
    code: "41013",
    d1: d1Clean(),
    d5: d5Clean({
      exposedFactsInventory: derivedFactInventory({
        tier: "Besar",
        riskValue: "Menengah Tinggi",
        baseFactsVerified: true,
        fiktifStatus: "verified",
        fiktifCitation: undefined,
      }),
    }),
    d2: null,
  });
  assert.equal(
    result.verdict,
    "quarantined",
    `expected quarantined (derived fact verified without any derivation_citation must not certify), got ${result.verdict}`,
  );
  assert.equal(result.facts_inventory_failed, true);
  console.log(
    "PASS: derived fact marked verified with no derivation_citation at all -> quarantined",
  );
}

async function test_derived_fact_base_facts_absent_blocks_certification_even_with_citation() {
  // GUILT: base facts absent (no locator) — even a well-formed derivation_citation cannot rescue
  // a derived fact whose own base facts are unverified. "base facts absent -> derived absent ->
  // no certification" (gate report §5.4 guilt test, verbatim).
  const result = await runLot({
    code: "41013",
    d1: d1Clean(),
    d5: d5Clean({
      exposedFactsInventory: derivedFactInventory({
        tier: "Besar",
        riskValue: "Menengah Tinggi",
        baseFactsVerified: false,
        fiktifStatus: "verified",
        fiktifCitation: VALID_MT_CITATION,
      }),
    }),
    d2: null,
  });
  assert.equal(
    result.verdict,
    "quarantined",
    `expected quarantined (base facts absent must block a derived fact regardless of citation), got ${result.verdict}`,
  );
  assert.equal(result.facts_inventory_failed, true);
  console.log(
    "PASS: base facts absent -> derived fact blocked even with a well-formed citation",
  );
}

async function test_derived_fact_wrong_article_for_base_risk_tier_blocks_certification() {
  // GUILT: base risk tier is "Tinggi" (needs Pasal 230), but the citation names Pasal 225(1)
  // (Menengah Tinggi's article) — article/tier mismatch must not certify.
  const result = await runLot({
    code: "80190",
    d1: d1Clean(),
    d5: d5Clean({
      exposedFactsInventory: derivedFactInventory({
        tier: "Besar",
        riskValue: "Tinggi",
        baseFactsVerified: true,
        fiktifStatus: "verified",
        fiktifCitation: VALID_MT_CITATION, // article 225(1) — WRONG for a Tinggi base risk (needs 230)
      }),
    }),
    d2: null,
  });
  assert.equal(
    result.verdict,
    "quarantined",
    `expected quarantined (citation article must match the base risk tier's actual rule), got ${result.verdict}`,
  );
  assert.equal(result.facts_inventory_failed, true);
  console.log(
    "PASS: derivation_citation article mismatched to the base risk tier -> quarantined",
  );
}

async function test_derived_fact_fully_verified_and_correctly_cited_can_certify() {
  // INNOCENCE (mandatory per the mandate): base facts verified with locators AND the derivation
  // formula cited with the article matching the base risk tier (Menengah Tinggi -> 225(1)) ->
  // certification possible. Proves the refinement does not make certification of a genuinely
  // derived fact impossible by construction.
  const result = await runLot({
    code: "59201",
    d1: d1Clean({
      mappings: [
        {
          kbli2020: "59201",
          kbli2025: "59201",
          mapping_type: "ONE_TO_ONE",
          rationale: "self-referencing, clean",
        },
      ],
    }),
    d5: d5Clean({
      exposedFactsInventory: derivedFactInventory({
        tier: "Menengah",
        riskValue: "Menengah Tinggi",
        baseFactsVerified: true,
        fiktifStatus: "verified",
        fiktifCitation: VALID_MT_CITATION,
      }),
    }),
    d2: null,
  });
  assert.equal(
    result.verdict,
    "certified",
    `expected certified (base verified + formula correctly cited must not be blocked), got ${result.verdict}`,
  );
  assert.equal(result.facts_inventory_failed, false);
  console.log(
    "PASS: base facts verified + derivation formula correctly cited -> still certified",
  );
}

// ---------------------------------------------------------------------------
// TESTS 10-11 (Lot 7 gate adversarial MINOR #5, §5.6b): journal provenance. Every seat result
// must carry a per-seat provenance record (label, prompt sha256, schema sha256, runner blob
// sha256); a control's provenance is tagged control_tag_applied_after=true ONLY after the
// seat-blind adjudicateCode() call already returned, never on a member's.
// ---------------------------------------------------------------------------

async function test_seat_provenance_present_and_shaped_on_every_result() {
  const result = await runLot({
    code: "80190",
    d1: d1Clean(),
    d5: d5Clean({
      exposedFactsInventory: [
        {
          field: "kategori_risiko",
          value: "Rendah",
          source_locator: "OSS RBA risk endpoint, 2025 record",
          vintage: "2025",
          status: "verified",
        },
      ],
    }),
    d2: null,
    runnerBlobSha256: "deadbeef".repeat(8),
  });
  assert.ok(
    result.seat_provenance,
    "result must carry a seat_provenance object",
  );
  for (const seat of ["D1", "D5"]) {
    const prov = result.seat_provenance[seat];
    assert.ok(prov, `seat_provenance.${seat} must be present`);
    assert.equal(prov.label, `${seat}:80190`);
    assert.match(
      prov.promptSha256,
      /^[0-9a-f]{64}$/,
      `${seat} promptSha256 must be a 64-hex sha256`,
    );
    assert.match(
      prov.schemaSha256,
      /^[0-9a-f]{64}$/,
      `${seat} schemaSha256 must be a 64-hex sha256`,
    );
    assert.equal(prov.runnerBlobSha256, "deadbeef".repeat(8));
    assert.equal(
      prov.control_tag_applied_after,
      undefined,
      `${seat} provenance on a NON-control result must carry no control_tag_applied_after key`,
    );
  }
  assert.equal(
    result.seat_provenance.D2,
    null,
    "D2 provenance must be null when D2 never ran",
  );
  console.log(
    "PASS: every seat result carries label + prompt sha256 + schema sha256 + runner blob sha256",
  );
}

async function test_control_tag_applied_after_only_tags_innocence_control_results() {
  const result = await runLot({
    code: "65121",
    innocenceControl: true,
    d1: d1Clean({
      mappings: [
        {
          kbli2020: "65121",
          kbli2025: "65121",
          mapping_type: "ONE_TO_ONE",
          rationale: "control, clean",
        },
      ],
    }),
    d5: d5Clean({ exposedFactsInventory: [] }),
    d2: null,
  });
  assert.equal(result.innocenceControl, true);
  for (const seat of ["D1", "D5"]) {
    const prov = result.seat_provenance[seat];
    assert.ok(
      prov,
      `seat_provenance.${seat} must be present on a control result too`,
    );
    assert.equal(
      prov.control_tag_applied_after,
      true,
      `${seat} provenance on a control result must carry control_tag_applied_after=true`,
    );
    // the tag must be ADDITIVE (post-hoc), never displacing the underlying provenance fields
    assert.equal(prov.label, `${seat}:65121`);
    assert.match(prov.promptSha256, /^[0-9a-f]{64}$/);
  }
  console.log(
    "PASS: control_tag_applied_after=true is present on a control's seat provenance, additively",
  );
}

// ---------------------------------------------------------------------------
// runner
// ---------------------------------------------------------------------------

const tests = [
  test_unverified_tinggi_fact_blocks_certification,
  test_fully_verified_inventory_can_still_certify,
  test_genuinely_empty_inventory_is_vacuously_fine,
  test_missing_inventory_fails_closed,
  test_already_quarantined_path_is_unaffected_by_the_patch,
  test_derived_fact_verified_without_citation_blocks_certification,
  test_derived_fact_base_facts_absent_blocks_certification_even_with_citation,
  test_derived_fact_wrong_article_for_base_risk_tier_blocks_certification,
  test_derived_fact_fully_verified_and_correctly_cited_can_certify,
  test_seat_provenance_present_and_shaped_on_every_result,
  test_control_tag_applied_after_only_tags_innocence_control_results,
];

let failed = 0;
for (const t of tests) {
  try {
    await t();
  } catch (err) {
    failed += 1;
    console.error(`FAIL: ${t.name}`);
    console.error(err && err.stack ? err.stack : err);
  }
}

console.log(`\n${tests.length - failed}/${tests.length} passed`);
if (failed > 0) {
  process.exit(1);
}
