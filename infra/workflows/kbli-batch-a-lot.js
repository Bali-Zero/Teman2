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
    "source_absent_in_vault",
    "payload_cross_contamination",
    "unresolvable_source_pointer",
    "mapping_metadata_false",
  ],
  m4_tokens_per_dossier_ceiling: 400000,
};

// ----- journal provenance (Lot 7 gate adversarial MINOR #5, §5.6b — mandatory cure deliverable):
// every seat call must be traceable to EXACTLY which prompt/schema/runner-version produced a
// given verdict, without trusting a neutral label alone ("a future audit can prove which
// prompt/schema produced which verdict without trusting neutral labels"). This script has no
// fs/network/crypto primitive of its own (see the header notes on the lease guard and the
// membership gate) — sha256Hex below is a minimal, dependency-free SHA-256 (FIPS 180-4) over a
// UTF-8 string, so prompt/schema hashing never depends on an assumed runtime global
// (crypto.subtle/node:crypto) that no other infra/workflows/*.js script here relies on either.
function sha256Hex(message) {
  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  let h0 = 0x6a09e667,
    h1 = 0xbb67ae85,
    h2 = 0x3c6ef372,
    h3 = 0xa54ff53a;
  let h4 = 0x510e527f,
    h5 = 0x9b05688c,
    h6 = 0x1f83d9ab,
    h7 = 0x5be0cd19;

  const bytes = [];
  const utf8 = unescape(encodeURIComponent(message));
  for (let i = 0; i < utf8.length; i++) bytes.push(utf8.charCodeAt(i) & 0xff);

  const bitLen = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  bytes.push(0, 0, 0, 0); // high 32 bits of the 64-bit length — always 0 for these message sizes
  const bitLenLow = bitLen >>> 0;
  bytes.push(
    (bitLenLow >>> 24) & 0xff,
    (bitLenLow >>> 16) & 0xff,
    (bitLenLow >>> 8) & 0xff,
    bitLenLow & 0xff,
  );

  const rotr = (x, n) => (x >>> n) | (x << (32 - n));

  for (let chunkStart = 0; chunkStart < bytes.length; chunkStart += 64) {
    const w = new Array(64).fill(0);
    for (let i = 0; i < 16; i++) {
      w[i] =
        ((bytes[chunkStart + i * 4] << 24) |
          (bytes[chunkStart + i * 4 + 1] << 16) |
          (bytes[chunkStart + i * 4 + 2] << 8) |
          bytes[chunkStart + i * 4 + 3]) >>>
        0;
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }

    let a = h0,
      b = h1,
      c = h2,
      d = h3,
      e = h4,
      f = h5,
      g = h6,
      h = h7;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K[i] + w[i]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
    h5 = (h5 + f) >>> 0;
    h6 = (h6 + g) >>> 0;
    h7 = (h7 + h) >>> 0;
  }

  const toHex = (n) => (n >>> 0).toString(16).padStart(8, "0");
  return [h0, h1, h2, h3, h4, h5, h6, h7].map(toHex).join("");
}

// The runner blob sha256 is a SELF-REFERENCE this script cannot resolve from inside itself: it
// has no fs primitive to read its own bytes, and a literal pinned to "the hash of this exact
// file" is a fixed-point problem (inserting the computed hash changes the file, which changes the
// hash). Exactly like args.membership (see the membership-gate header note above), the CALLER
// supplies it — `shasum -a 256 infra/workflows/kbli-batch-a-lot.js` (a PLAIN sha256 of the file's
// bytes, the same value every cure spec's `_provenance` field already pins as "sha256 ..." —
// NOT `git hash-object`, which computes a git-blob SHA-1 over a different, header-prefixed input
// and would never match this constant or args.runnerBlobSha256), computed immediately before
// dispatch; this wires that existing practice into the args contract instead of leaving it
// undiscoverable from inside a run. Absent input WARNs (observability only, same class as the
// lease-guard SKIP) and falls back to the last self-pinned literal, which by construction can lag
// the file's true current bytes by any edit made since the pin was last refreshed by hand.
const RUNNER_BLOB_SHA256_LAST_PINNED =
  "9bb3870fe5bae3c977c8e1ab5895d098e7be86a604d54c0c9f4a6be6a103a609";
const runnerBlobSha256 =
  typeof A.runnerBlobSha256 === "string" && A.runnerBlobSha256.trim()
    ? A.runnerBlobSha256.trim()
    : (() => {
        log(
          `WARN lot ${lotId} did not supply args.runnerBlobSha256 (shasum -a 256 ` +
            `infra/workflows/kbli-batch-a-lot.js, computed by the CALLER before dispatch — this ` +
            `script cannot read its own file, no fs primitive; NOT git hash-object, which produces ` +
            `a different SHA-1 git-blob value) — falling back to the last self-pinned literal ` +
            `${RUNNER_BLOB_SHA256_LAST_PINNED}, which may be STALE relative to this run's actual ` +
            `file bytes. Observability WARN only, not an enforced gate.`,
        );
        return RUNNER_BLOB_SHA256_LAST_PINNED;
      })();

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
  "source_absent_in_vault",
  "payload_cross_contamination",
  "unresolvable_source_pointer",
  "mapping_metadata_false",
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
    "exposed_facts_inventory",
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
    // CERTIFICATION-CONTRACT PATCH (2026-07-19, Lot 6 conductor gate BLOCKER 2, mandatory — see
    // the factsInventoryUnverified() note below, adjudication section, for the full rationale).
    // REQUIRED on every D5 answer, for a Batch-A member and for a reused non-member code alike
    // (adjudicateCode() is the sole dispatch path for both) — regardless of pp28_sources being
    // empty or licensing_inherits' value: an empty pp28_sources array is NEVER, by itself, a
    // reason to skip this inventory.
    exposed_facts_inventory: {
      type: "array",
      description:
        "Enumerate EVERY client-facing fact this code's canonical record actually asserts, across " +
        "every per_skala tier: kategori_risiko, jangka_waktu, scope_uraian (when present), " +
        "fiktif_positif, and the license type the frontend derives from risk when perizinan is " +
        'empty (Tinggi -> "NIB + Izin", Menengah Tinggi/Menengah Rendah -> "NIB + Sertifikat ' +
        'Standar", Rendah -> "NIB", per PP 28/2025 Pasal 124(4)). A record with ZERO client-facing ' +
        "facts (e.g. a genuinely empty per_skala) returns an empty list — that is the only case an " +
        'empty list is honest. For every fact you DO list, mark status="verified" ONLY if you can ' +
        "cite EITHER (a) a page/row locator AND a vintage (2020 vs 2025) for it from the rendered " +
        "evidence (PP28/crosswalk), OR (b) — ONLY for a record whose canonical carries the marker " +
        "_l2_source=OSS_RBA_resiko_2025 — the matching OSS probe file under this code's dossier " +
        'oss/ directory (e.g. oss/ruang_lingkup.json) with vintage "2025", since that record class ' +
        'has no PP28/crosswalk render to cite; otherwise mark status="absent". An empty ' +
        "pp28_sources array is NEVER, by itself, a reason to mark a fact absent. Do not guess a " +
        'locator to make the list look complete — an "absent" entry is not a failure on your part, ' +
        "it is the honest answer this field exists to capture.",
      items: {
        type: "object",
        required: ["field", "value", "status"],
        properties: {
          field: {
            type: "string",
            description:
              "one of kategori_risiko / jangka_waktu / scope_uraian / fiktif_positif / " +
              "derived_license, optionally suffixed with the per_skala tier it came from (e.g. " +
              '"kategori_risiko:Besar"). fiktif_positif and derived_license are DERIVED facts — ' +
              "a rule-derived legal consequence, never a printed table cell — and REQUIRE a " +
              "derivation_citation (below) whenever you mark them verified (contract refinement " +
              "#2, Lot 7 gate §3.5/§5.4).",
          },
          value: { type: "string" },
          source_locator: {
            type: "string",
            description:
              "a page/row citation from the rendered evidence (PP28/crosswalk PNGs) when " +
              'status="verified" — OR, ONLY for a record whose canonical carries the marker ' +
              "_l2_source=OSS_RBA_resiko_2025, a citation of the matching OSS probe file under " +
              "this code's dossier oss/ directory (e.g. oss/ruang_lingkup.json, vintage 2025) " +
              "instead, since that record class has no PP28/crosswalk render to point at; never " +
              "guess a locator either way; empty string when absent. For a DERIVED field " +
              "(fiktif_positif/derived_license) this stays empty even when verified=true — a " +
              "derived fact is never a page/row citation, see derivation_citation instead.",
          },
          vintage: {
            type: "string",
            description:
              "2020 or 2025 — which vintage's row grounds this fact; empty string when absent",
          },
          status: { type: "string", enum: ["verified", "absent"] },
          derivation_citation: {
            type: "object",
            description:
              'REQUIRED when field is fiktif_positif or derived_license AND status="verified" ' +
              "(contract refinement #2, Lot 7 gate §3.5/§5.4, precondition for Lot 8): a rule-" +
              "derived fact is a LEGAL CONSEQUENCE the OSS-RBA platform attaches automatically " +
              "once the BASE facts (kategori_risiko, jangka_waktu, SAME per_skala tier) are " +
              "themselves verified with a locator — it is never a page/row citation of its own. " +
              'Cite the versioned formula: script="scripts/derive_fiktif_positif.py", ' +
              'instrument="PP 28/2025", article="225(1)" when the base kategori_risiko is ' +
              '"Menengah Tinggi" (Sertifikat Standar deemed verified on SLA miss), ' +
              'article="230" when the base kategori_risiko is "Tinggi" (Izin auto-issued), or ' +
              'article="124(4)" ONLY for the SEPARATE derived_license field (never for ' +
              'fiktif_positif) — plus a vintage (e.g. "2025"). Omit entirely when the field is ' +
              'not derived, or when its own status is "absent".',
            properties: {
              script: { type: "string" },
              instrument: { type: "string" },
              article: { type: "string" },
              vintage: { type: "string" },
            },
          },
        },
      },
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

// INNOCENCE_SCHEMA + innocencePrompt() are RETIRED (2026-07-19, Lot 5 conductor gate second-signing
// BLOCKER — see the SYMMETRIC BLIND TREATMENT v2 note above adjudicateInnocence() below). They used
// to give the control branch its OWN schema and prompt; the schema's field descriptions ("MUST be
// empty when verdict=certified", "the frozen-taxonomy normalization of a TRUE INNOCENCE CONTROL")
// told the seat it was grading a control expected to come out boring — the Lot 4 fix neutralized the
// PROMPT wording, but the SCHEMA still leaked the exact same information on a different channel (the
// guard-fix-begets-twin-bug shape, scar family #3, THIRD instance in this program). The only durable
// fix is for a control to receive the IDENTICAL schema+prompt pair (D1_SCHEMA/d1Prompt,
// D5_SCHEMA/d5Prompt, D2_SCHEMA/d2Prompt) a member code gets — so there is no longer any
// innocence-specific schema or prompt to leak from. Do not reintroduce either under any name; the
// contract test (test_lot_runner_contract.py) fails on a re-added seat-visible innocence marker on
// ANY channel (prompt body, schema property, `label`/`phase`/`model` passed to `agent()`), not just
// the wording channel that bit last time.

// ----- prompts ---------------------------------------------------------------------------------

const OUT_OF_SCOPE_NOTICE =
  "OUT OF SCOPE THIS PASS (plan §8 amendment A-1 — the P1-v2 vault wave is deferred): " +
  "pma_status, l4_bali, and TKA facets. If this code's determination would require one of those " +
  "three, do NOT guess.";

function evidenceDirFor(code) {
  return `${evidenceRoot}/${code}`;
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
    `source_absent_in_vault / payload_cross_contamination / unresolvable_source_pointer / ` +
    `mapping_metadata_false) that best fits your reason — or the literal ` +
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
    `determination, set abstain={needed:true, facet:"<name>"} instead of guessing. Independent of all ` +
    `that, and regardless of whether pp28_sources is empty (an empty pp28_sources array is NEVER a ` +
    `reason to skip this — a BPS_ONLY/empty-pp28_sources record can still carry live client-facing ` +
    `facts), populate exposed_facts_inventory: list every kategori_risiko/jangka_waktu/scope_uraian/ ` +
    `fiktif_positif fact this code's per_skala rows actually assert, plus the license the frontend ` +
    `would derive from risk when perizinan is empty (Tinggi -> "NIB + Izin", Menengah Tinggi/Menengah ` +
    `Rendah -> "NIB + Sertifikat Standar", Rendah -> "NIB"), each marked verified only when you can ` +
    `cite EITHER a page/row locator and a vintage for it from the rendered evidence (PP28/crosswalk), ` +
    `OR — ONLY if this code's canonical carries the marker _l2_source=OSS_RBA_resiko_2025 — the ` +
    `matching OSS probe file under this code's dossier oss/ directory (e.g. oss/ruang_lingkup.json, ` +
    `vintage 2025), since that record class has no PP28/crosswalk render to cite; otherwise absent. A ` +
    `genuinely empty per_skala returns an empty list; never guess a locator either way to make the ` +
    `list look complete. DERIVED-FACT RULE (contract refinement #2, Lot 7 gate §3.5/§5.4): ` +
    `fiktif_positif and derived_license are never a printed table cell — they are a LEGAL ` +
    `CONSEQUENCE the OSS-RBA platform attaches automatically once the BASE facts (kategori_risiko, ` +
    `jangka_waktu, same per_skala tier) are themselves verified. Mark one of these two fields ` +
    `verified ONLY when (a) that tier's kategori_risiko AND jangka_waktu are ALSO listed as ` +
    `verified with a locator in this SAME inventory, AND (b) you cite the versioned derivation ` +
    `formula in derivation_citation: script="scripts/derive_fiktif_positif.py", ` +
    `instrument="PP 28/2025", article="225(1)" when the base kategori_risiko is "Menengah Tinggi" ` +
    `(Sertifikat Standar deemed verified on SLA miss), article="230" when the base kategori_risiko ` +
    `is "Tinggi" (Izin auto-issued), or article="124(4)" ONLY for the SEPARATE derived_license ` +
    `field (never for fiktif_positif) — plus a vintage. If the base facts are absent, or you cannot ` +
    `cite the versioned formula, mark the derived field absent too — never verified from the code's ` +
    `own plausibility alone. The WORKFLOW, not you, compares your conclusion against D1's — that ` +
    `comparison happens entirely outside your context.`
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

// SYMMETRIC BLIND TREATMENT v2 (2026-07-19, Lot 5 conductor gate SECOND SIGNING — §1 BLOCKER, §6
// meta-pattern "the guard-fix-begets-twin-bug shape now has a THIRD instance in this program"):
// Lot 4 neutralized the innocence PROMPT's wording, but INNOCENCE_SCHEMA (now retired, see the note
// above d1Prompt) still leaked the control's nature and expected outcome on a DIFFERENT seat-visible
// channel — both control seats' own notes self-identified as "innocence control" even with the
// neutral prompt in place. The prompt-fix begat its schema-shaped twin, same family as W83->W84 (the
// noise-strip fix that spawned the cross-line over-match): a blindness fix is only done when the
// ENTIRE seat-visible surface is symmetric, not just the one channel that bit last time.
//
// The fix: an innocence control no longer gets ANY schema or prompt of its own. It is dispatched
// through adjudicateCode() — the EXACT function a member code uses (same d1Prompt/D1_SCHEMA,
// d5Prompt/D5_SCHEMA, d2Prompt/D2_SCHEMA, same `label`/`phase`/`model` shape passed to agent(), same
// diffD1D5() compiler diff) — so there is no separate prompt text, no separate schema property
// description, and no separate label/meta value left to leak the control's identity on ANY channel.
// The seat that produces `adjudication` below is never told, directly or indirectully, that this
// code is a control.
//
// Only AFTER the seat-blind adjudication returns does this function do anything innocence-specific,
// and that work is 100% deterministic JS the seat never executes or sees: it re-tags the identical
// result as an innocence-control record (innocenceControl/innocence flags) and derives a legacy-
// shaped `innocence_verdict` summary for conductor readability. Nothing here can leak forward into
// the NEXT seat call, because there is no next seat call — adjudicateCode() has already finished.
async function adjudicateInnocence(code) {
  const adjudication = await adjudicateCode(code);
  const innocence_verdict = {
    verdict: adjudication.verdict,
    changes_proposed:
      adjudication.verdict === "quarantined"
        ? [adjudication.category || "unresolvable_source_pointer"]
        : [],
    notes:
      `runner-side normalization of the member D1/D5/D2 pipeline (adjudicateCode) result — ` +
      `concordant=${adjudication.concordant}, divergent=${adjudication.divergent}`,
  };
  // Journal provenance control_tag_applied_after (Lot 7 gate adversarial MINOR #5, §5.6b): the
  // NAME itself documents when this happens — strictly AFTER the seat-blind adjudicateCode() call
  // above has already returned, deterministic JS only, never seen or executed by any seat. This is
  // the exact same "delegate then relabel" shape this function already uses for
  // innocenceControl/innocence below (see the SYMMETRIC BLIND TREATMENT v2 header note) — a
  // control's seat calls are 100% identical to a member's up to and including the seat dispatch
  // itself; only the ALREADY-RETURNED provenance record is tagged, never anything passed TO a seat.
  const seat_provenance = adjudication.seat_provenance
    ? Object.fromEntries(
        Object.entries(adjudication.seat_provenance).map(([seat, prov]) => [
          seat,
          prov ? { ...prov, control_tag_applied_after: true } : prov,
        ]),
      )
    : adjudication.seat_provenance;
  return {
    ...adjudication,
    seat_provenance,
    innocenceControl: true,
    innocence: true,
    innocence_verdict,
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

// CERTIFICATION-CONTRACT PATCH (2026-07-19, Lot 6 conductor gate BLOCKER 2, mandatory — see
// research/operations/2026-07-19-kbli-batch-a-lot6-conductor-gate.md §3.4/§5.3): the certification
// path used to let a "certified" verdict through the moment D1/D5 agreed on {mapping_type,
// licensing_inherits, problem_found} — it never checked whether the record's OWN client-facing
// facts (risk tier, timeframe, scope, fiktif_positif, and the license the frontend DERIVES from
// risk when perizinan is empty, apps/mouth/src/lib/kbli-derive.ts:25 licenseForRisk) actually
// carry a verifiable source. For 80190, licensing_inherits=false meant the compound D2 guard just
// below (`preD2Verdict==="certified" && d1.licensing_inherits===true` — UNCHANGED by this patch,
// D2 itself is not touched) never fired at all, and the record's four Tinggi/7-day/security-scope
// tiers were certified with zero provenance. factsInventoryUnverified() is a SECOND, INDEPENDENT
// gate: it runs on every preliminary "certified" verdict regardless of licensing_inherits, and
// regardless of whether pp28_sources is empty — the circular "N/A because pp28_sources is empty"
// read is exactly what let 80190 through, and an empty pp28_sources array is NEVER, by itself, a
// reason to skip this check. D5 (the blind refuter, already reading canonical.json + evidence for
// every code) is the one seat asked to inventory every exposed fact with a verified/absent
// per-entry provenance tag (D5_SCHEMA.exposed_facts_inventory, required — see above); this
// function's ONLY job is to refuse certification the moment ANY entry is not "verified". A
// genuinely empty per_skala legitimately returns an empty inventory (nothing to verify) — the ONE
// case this gate treats as vacuously fine, matching the gate's own corollary that "the certifiable
// class" is not "codes that assert nothing" but "codes whose every exposed fact carries a verified
// locator+vintage".
//
// DERIVED-FACT CERTIFICATION RULE (contract refinement #2, 2026-07-19 Lot 7 conductor gate
// §3.5/§5.4, precondition for Lot 8 — mandatory cure deliverable): the patch above treats EVERY
// exposed_facts_inventory entry the same way (verified needs a page/row locator) — but a rule-
// DERIVED entry (fiktif_positif / derived_license) can never legitimately carry one: it is not
// printed anywhere in the lampiran, it is a LEGAL CONSEQUENCE the OSS-RBA platform attaches
// automatically once its BASE facts are known (UU Cipta Kerja 6/2023's silenzio-assenso flip,
// codified PP 28/2025 Pasal 225(1) for Menengah Tinggi / Pasal 230 for Tinggi; Pasal 124(4) is the
// SEPARATE derived-license rule — scripts/derive_fiktif_positif.py encodes the exact boolean rule,
// reused here BY REFERENCE in prose/citation form, never re-implemented independently). The Lot 7
// gate's fail-closed demotion of the 41013 innocence control (§3.5, adversarial BLOCKER, corrected
// legal base) proved the PRE-refinement contract had no way to EVER certify a record honestly
// asserting this fact — every "verified" fiktif_positif/derived_license entry would need a
// page/row locator that structurally cannot exist. This refinement is the honest ceiling the gate
// report names: "base facts verified + derivation rule cited", never "every field has a table
// cell".
const DERIVED_FIELDS = ["fiktif_positif", "derived_license"];

function fieldBaseName(field) {
  const s = String(field || "");
  const i = s.indexOf(":");
  return i === -1 ? s : s.slice(0, i);
}

function fieldTierSuffix(field) {
  const s = String(field || "");
  const i = s.indexOf(":");
  return i === -1 ? null : s.slice(i + 1);
}

function isDerivedField(field) {
  return DERIVED_FIELDS.includes(fieldBaseName(field));
}

function findInventoryEntry(inventory, baseName, tier) {
  const wanted = tier ? `${baseName}:${tier}` : baseName;
  return inventory.find((e) => e && e.field === wanted) || null;
}

// Pasal 225(1) PP 28/2025 governs Menengah Tinggi (Sertifikat Standar deemed verified on SLA
// miss); Pasal 230 governs Tinggi (Izin auto-issued); Pasal 124(4) is the SEPARATE derived-LICENSE
// rule (never cited for fiktif_positif itself). The article choice depends on the BASE
// kategori_risiko VALUE, not the derived field's own name — a fiktif_positif entry never carries
// its own risk tier, it inherits the tier from the base fact it is derived from.
function expectedArticleFor(field, riskValue) {
  if (fieldBaseName(field) === "derived_license") return "124(4)";
  const risk = String(riskValue || "").trim();
  if (risk === "Menengah Tinggi") return "225(1)";
  if (risk === "Tinggi") return "230";
  return null; // neither eligible tier -> no derivation rule applies at all (guilt path below)
}

// Conductor gate cure #1 (2026-07-19, scar family #3 guard-over-match — anti cite-everything):
// a bare `.includes(expectedArticle)` substring check validates a citation that lists MULTIPLE
// articles at once ("225(1), 230" would satisfy BOTH tiers' expectedArticle via substring) and
// false near-matches ("1230" contains "230" as a substring). Normalize the article (strip a
// leading "Pasal " prefix, case-insensitive, then trim) and require EXACT equality with
// expectedArticle — a citation must name ONE article, unambiguously, matching the base risk
// tier's actual rule, never a superset or a substring collision.
function normalizeArticle(article) {
  return String(article || "")
    .replace(/^\s*pasal\s+/i, "")
    .trim();
}

function derivationCitationValid(entry, expectedArticle) {
  const c = entry && entry.derivation_citation;
  if (!c || typeof c !== "object") return false;
  if (c.script !== "scripts/derive_fiktif_positif.py") return false;
  if (!/28\s*\/\s*2025/.test(String(c.instrument || ""))) return false;
  if (!expectedArticle || normalizeArticle(c.article) !== expectedArticle)
    return false;
  if (!String(c.vintage || "").trim()) return false;
  return true;
}

// A derived-class entry is UNVERIFIED (regardless of its own status field) unless ALL THREE hold:
// (a) its BASE facts (kategori_risiko AND jangka_waktu, SAME per_skala tier) are THEMSELVES
// verified with a non-empty source_locator in this SAME inventory — GUILT: base facts absent ->
// derived absent -> no certification; (b) it cites a versioned derivation formula whose article
// matches the base risk tier's actual rule — INNOCENCE: base verified + formula cited -> derived
// verified -> certification possible; (c) a base risk tier that is NEITHER Menengah Tinggi NOR
// Tinggi has no derivation rule to cite at all — a seat asserting fiktif_positif=verified on a
// Rendah/Otomatis tier (where the rule does not apply) cannot be verified by this rule either.
function derivedEntryUnverified(entry, inventory) {
  const tier = fieldTierSuffix(entry.field);
  const riskEntry = findInventoryEntry(inventory, "kategori_risiko", tier);
  const jwEntry = findInventoryEntry(inventory, "jangka_waktu", tier);
  const baseFactsVerified =
    Boolean(riskEntry) &&
    riskEntry.status === "verified" &&
    Boolean(riskEntry.source_locator) &&
    Boolean(jwEntry) &&
    jwEntry.status === "verified" &&
    Boolean(jwEntry.source_locator);
  if (!baseFactsVerified) return true;
  const expectedArticle = expectedArticleFor(entry.field, riskEntry.value);
  if (!expectedArticle) return true;
  if (!derivationCitationValid(entry, expectedArticle)) return true;
  return false;
}

function factsInventoryUnverified(d5) {
  const inventory =
    d5 && Array.isArray(d5.exposed_facts_inventory)
      ? d5.exposed_facts_inventory
      : null;
  if (inventory === null) return true; // missing entirely -> fail-closed, cannot certify
  return inventory.some((entry) => {
    if (!entry || entry.status !== "verified") return true;
    if (isDerivedField(entry.field))
      return derivedEntryUnverified(entry, inventory);
    return false;
  });
}

// Journal provenance wrapper (Lot 7 gate adversarial MINOR #5, §5.6b): wraps a single seat
// agent() call and computes, ALONGSIDE the real answer (never wrapping/replacing it — every
// caller below still gets the raw D1/D5/D2 answer shape untouched), a provenance record: the
// seat's own label, sha256 of the FULL prompt text actually sent, sha256 of the response schema
// object, and the runner blob sha256 (resolved once above, from args.runnerBlobSha256 or its
// pinned fallback). Returns { answer, provenance } — callers destructure both.
async function callSeat(promptText, opts) {
  const answer = await agent(promptText, opts);
  const provenance = {
    label: opts.label,
    promptSha256: sha256Hex(promptText),
    schemaSha256: sha256Hex(JSON.stringify(opts.schema)),
    runnerBlobSha256,
  };
  return { answer, provenance };
}

async function adjudicateCode(code) {
  leaseGuardWarn(code);

  const d1Call = await callSeat(d1Prompt(code), {
    label: `D1:${code}`,
    phase: "Adjudicate",
    schema: D1_SCHEMA,
    model: "sonnet",
  });
  const d1 = d1Call.answer;

  // D5 is a SEPARATE, blind adjudicator — receives ONLY code+evidence, NEVER d1's proposal (plan
  // §3/A4, red-team F5; see the D5 BLIND-REFUTATION FIX header note).
  const d5Call = await callSeat(d5Prompt(code), {
    label: `D5:${code}`,
    phase: "Adjudicate",
    schema: D5_SCHEMA,
    model: "sonnet",
  });
  const d5 = d5Call.answer;

  const diff = diffD1D5(deriveD1Comparable(d1), deriveD5Comparable(d5));

  const abstainNeeded =
    Boolean(d1 && d1.abstain && d1.abstain.needed) ||
    Boolean(d5 && d5.abstain && d5.abstain.needed);
  // an out-of-scope-facet claim from EITHER seat overrides the diff outright — "the visible facts
  // agree" is a weaker claim than "this needs evidence we don't have this pass" (plan §8 A-1).
  const preD2Verdict = abstainNeeded ? "abstained" : diff.verdict;

  // CERTIFICATION-CONTRACT PATCH (Lot 6 gate BLOCKER 2) — independent of D2/licensing_inherits,
  // gated purely on D5's own exposed_facts_inventory (see factsInventoryUnverified() above).
  // Computed here (before D2 dispatch) but only ever DEMOTES the final verdict below, never
  // promotes one — certification becomes STRICTER only.
  const factsInventoryFailed =
    preD2Verdict === "certified" && factsInventoryUnverified(d5);

  let d2 = null;
  let d2Call = null;
  if (preD2Verdict === "certified" && d1 && d1.licensing_inherits === true) {
    d2Call = await callSeat(d2Prompt(code), {
      label: `D2:${code}`,
      phase: "Adjudicate",
      schema: D2_SCHEMA,
      model: "sonnet",
    });
    d2 = d2Call.answer;
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
  // the same class of miss can't reach "certified" again. Category=unresolvable_source_pointer
  // (closed registry, plan §5 m3, v2 label — renamed from phantom_source_pointer per plan A-5:
  // text-hunt evidence cannot establish nonexistence): "the cited row/source doesn't actually
  // confirm the code" is precisely what a failed self-confirmation means.
  const d2SelfConfirmFailed =
    d2 !== null &&
    (!d2.self_confirmed ||
      d2.self_confirmed.code_appears_in_row !== true ||
      !Array.isArray(d2.per_skala_rows) ||
      d2.per_skala_rows.length === 0);

  const verdict =
    d2SelfConfirmFailed || factsInventoryFailed ? "quarantined" : preD2Verdict;
  const quarantined = verdict === "quarantined";
  const category = quarantined
    ? d2SelfConfirmFailed
      ? "unresolvable_source_pointer"
      : factsInventoryFailed
        ? "source_absent_in_vault"
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
    facts_inventory_failed: factsInventoryFailed,
    seatInvocations: d2 ? 3 : 2,
    // journal provenance (Lot 7 gate adversarial MINOR #5, §5.6b): per-seat label + prompt sha256
    // + schema sha256 + runner blob sha256, so a future audit can prove which prompt/schema
    // produced which verdict without trusting neutral labels. D2 stays null when D2 never ran
    // (mirrors d2's own null-when-not-dispatched shape above).
    seat_provenance: {
      D1: d1Call.provenance,
      D5: d5Call.provenance,
      D2: d2Call ? d2Call.provenance : null,
    },
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
