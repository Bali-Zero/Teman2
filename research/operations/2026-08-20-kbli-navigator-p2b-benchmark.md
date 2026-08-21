---
date: 2026-08-20
domain: operations
client_case: none — internal product benchmark (KBLI Navigator Phase 2)
sources:
  - scripts/kbli_bench/p2b_corpus.json (frozen corpus, sha256 487bc9509d01456eb37a588c3ee942f4956731502697aef94f1a2ee1294008e7)
  - scripts/kbli_bench/results/p2b_answers.jsonl (87 rows, this run)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (canonical, sha256 3dafab17f6c48477c34ae562d74d5015faeba74a44fee125ee9267c6c45da2e8)
  - research/operations/2026-08-19-kbli-navigator-phase2-codex-chat-design.md (§8 protocol)
adversarial_review: kimi-k3
---

# KBLI Navigator P2b benchmark — RUN COMPLETE, GATE RED (2 surgical causes, zero fabrication found)

**Verdict: the §8 gate is RED — P2c (OpenClaw deletion + fleet install) is NOT authorized by this
run.** But the red is not "the brain is bad": no layer of the scoring stack found a single invented
regulatory fact in any run (floor i GREEN — coverage stated precisely in §2), and all 21 gap/probe
questions ended in a served abstention (floor iv GREEN, with 4 of 63 gap-side rows gate-converted
rather than model-declared — see §2). The two red floors trace to exactly two curable product
defects: **the post-generation gate over-matches correct answers into refusals** (3 of 8 structured
questions killed; superscar family #3 arriving in the product's own gate), and **one retrieval
miss** (the "kafe" question never got 56303/56101 into the package, and the brain then honestly
abstained). Fix those two, re-run, and the gate is plausibly green — nothing in this run suggests a
third failure mode.

## 1. Manifest (§8)

| item | value |
| --- | --- |
| app repo commits (M5, no remote) | harness `112241c0` · pin bump `6904c47` · test fixture `bc7cacb` · fd-leak fix `8b6081c` |
| bundled dataset | app rev `a5721756d5b2…` — field-diff vs canonical `3dafab17…` on all Swift-decoded fields: ZERO (measured 2026-08-19) |
| codex CLI | `codex-cli 0.148.0` on Pro (auto-updated from 0.147.0 mid-lane; pin bumped + suites re-run, see §5) |
| serving model | `gpt-5.6-terra` (pinned by `KBLICodexRunner.buildArgv()`, stdin-only, ephemeral) |
| judge model | `gpt-5.6-sol` (29 prompts, one per question, all 3 runs inline; STRICT JSON, 29/29 parsed) |
| corpus | 29 questions (8 structured / 18 known-gap / 3 out-of-corpus), sha256 `487bc950…` |
| runs | 3 per question, serial, no per-call retry → 87 rows, 0 transport errors, median 8.5 s, total 770 s. (A first whole-run attempt was refused 87/87 by the version-pin guard after codex auto-updated — discarded wholesale, suites re-run on the new CLI, then this run; see §5.) |
| scoring | `scripts/kbli_bench/score_p2b.py` (deterministic tuple check → sol judge → session hand-check 100 % of 30 flagged + seeded 20 % sample of 17) |
| old brain | OpenClaw `zantara-kbli`: **unreachable, 3 probes** (2026-08-20, verbatim in `scripts/kbli_bench/oldbrain_probes/`) — 7/7-model auth cascade each time |

## 2. Floors (§8, ABSOLUTE) — after the mandatory hand-check layer

| floor | verdict | measured |
| --- | --- | --- |
| (i) zero fabrications in ANY run | **GREEN** | Three layers, coverage stated exactly: deterministic tuple check on all **87 served** texts (0 violations) **and all 87 raw** answers (1 flagged clause: Q13 r1's hypothetical "51 %" sitting next to a verified "100 %" cap — a true-but-ambiguous sentence the gate blocked; zero invented figures); sol judge on all 87; session hand-check on **100 % of the 30 judge-flagged rows + the seeded 20 % sample (17 rows, 9 additional)** — every checked claim traced to a real record field. The ~40 unflagged/unsampled rows carry tuple-check + judge coverage only; the tuple grammar sees figures, not prose — declared limit, mitigated by the fact that all 22 judge fabrication flags dissolved on inspection (§3). |
| (ii) accuracy ≥ 80 % structured | **RED — 4/8 (50 %)** | Correct by majority: Q20, Q21, Q23, Q26. Failed: Q05/Q13/Q22 (gate killed correct answers → served abstention), Q11 (retrieval miss → model abstained). |
| (iii) wrongful abstention ≤ 10 % structured | **RED — 4/8 (50 %)** | Q05, Q13, Q22 (gate rejections of raw answers the hand-check verified correct) **plus Q11** (the model itself abstained on a structured question — caused by the retrieval miss, but a served wrongful abstention regardless of cause). |
| (iv) 100 % abstention on known-gap + probes | **GREEN — 21/21 on the SERVED surface** | 59 of 63 gap-side rows are model-declared abstentions (many adding true record facts, allowed by the corpus' `expected.behavior`); **4 rows (Q08 r1-r2, Q16 r2, Q18 r2) are gate-converted refusals**, not model abstentions — the served outcome is still a safe abstention, and the distinction is declared here for symmetry with floor (iii). |
| (v) new ≥ old | **GREEN (trivially)** | Old brain 0/29 reachable across 3 spaced probes. Declared as measured-absence, never sold as a win. |

**Gate: RED** (floors ii + iii). P2c stays closed; the OpenClaw path is NOT deleted.

## 3. The hand-check layer was load-bearing: the raw judge verdict was wrong on 22 of 30 flags

The sol judge was given, per question, only the §3-allowlisted slice of the records named in
`expected.codes` — but the model answered from its REAL context package (5 retrieved records with
`per_skala`, `l4_bali`, etc.). Result: the judge marked "fabricated" many statements that are
**verbatim-faithful record facts** the judge simply never saw. Every one was re-verified against the
canonical this session (mechanically, then read):

- Q01: 56101 TERBUKA/100 + moratorium-not-blocking — exact record content, incl. `l4_bali.reason`.
- Q03: `perizinan` empty rows, PPSE for 52322, "jangka waktu 7" for 22112 — all true.
- Q19: 29300/61105/66193 requirement lists — all true (66193 "OSS issues only NIB, OJK licenses" is
  the record's own text).
- Q24: "Rp 100 miliar for Lembaga Kliring Berjangka (64993)" — literal `100.000.000.000` in the
  record's `per_skala`.
- Q08: 79110 TERBATAS/100/LSPr-certificate/CHIUSO_BALI_PROPOSTO — all four exact.
- Q23: 64330 CHIUSO_MORATORIA_BALI, effective 2026-05-13, permanent, island-wide, and even the
  "derivation under review" caveat — all from `l4_bali` (runs 1-2 also state the class rule; run 3
  omits it → kept "wrong (incomplete)"; majority correct).
- Q20: "49 % + national single majority" is the exact `pma_kondisi` of 51101; the judge demanded
  extra elements the question never asked. Reclassified correct ×3.
- The cited-code inventories in every flagged answer match `package_codes` exactly (the gate's
  `cited ⊆ package` rule guarantees this by construction).

Zero of the 30 flags survived as a real fabrication. The 20 % random sample (17 rows, 9 not already
covered) read clean: declared abstentions, correct class behavior. One cosmetic artifact: Q15 run 1
contains a single Georgian word ("ამიტომ" = "therefore") mid-Indonesian sentence — no factual
content, noted for completeness.

**Lesson (W65/W100 line): the judge harness under-supplied ground truth and the judge, correctly
obeying "judge ONLY against supplied records", produced 22 false fabrication verdicts. A future
re-run must feed the judge the SAME package the model saw (`package_codes` are in the answers
JSONL), not the expected-codes slice.** This is a benchmark-harness cure, separate from the two
product cures.

## 4. The two product defects the benchmark exists to catch

### 4a. Gate over-match (floors ii+iii driver) — superscar family #3, now in the product's gate

Three distinct over-match classes, each verified against raw answers that were CORRECT:

- **α — negated mention of an absent code (Q05, 3/3 runs).** The raw answer describes 68111
  correctly and says verbatim "Navigator tidak membawa data untuk KBLI 68200" — exactly the
  expected behavior. The gate kills it as `unknownCode(68200)`: under the current rule it is
  **impossible to correctly answer "68200 does not exist"**, because saying so cites the code.
- **β — exception clause quoting the cap it qualifies (Q22, 3/3 runs).** Raw: "49 % … may exceed
  49 % with Menteri Pertahanan approval" — both halves are the record's `pma_max_asing` +
  `pma_kondisi`. The `unverifiablePercentClaim` rule cannot see that the second "49 %" is the same
  verified figure inside a condition sentence.
- **γ — multi-code clause with a single shared cap (Q13, 3/3 runs; also the 4 gap-side rejections
  Q08 r1-r2, Q16 r2, Q18 r2 — measured, 13 kills total = 9 structured + 4 gap-side).** "Codes A, B,
  C are all open up to 100 %" where every named code is verified `pma_max_asing=100` — the clause
  is fully checkable code-by-code, but the multi-code+figure rule rejects it wholesale.

Cure direction (for the P2c-blocking fix): (α) allow a code mention inside an explicit
negative/absence statement, or have the package carry an "absent codes" marker the gate can check;
(β) treat a figure equal to the already-verified cap of the clause's single code as verified even
when repeated; (γ) when every code in the clause has the SAME verified cap equal to the quoted
figure, pass. Each needs guilt+innocence tests per family-#3 discipline (the gate is a guard; its
fix must not open under-match holes).

### 4b. Retrieval miss (Q11): "kafe di Ubud" never retrieves 56303 — whose *judul* contains "kafe"

`package_codes` for all 3 runs: 56290/56400/64330/66193/98100. Neither 56303 (rumah minum /
**kafe**) nor 56101 (restoran) made the package, so the brain honestly reported it had no cafe
code — and the client-facing outcome on a real trap question (56303 is Bali-blocked!) is a miss.
The search scoring in `KBLIContextPackage` needs a look at why a literal judul token lost to
56290/56400. Until cured, Q11 stays red.

## 5. Run integrity events (all cured in-lane, all committed)

1. **codex auto-updated 0.147.0 → 0.148.0 on Pro** between harness freeze and run: the runner's
   fail-closed version pin refused to spawn (87/87 typed errors, zero answers — exactly as
   designed). Pin bumped (`6904c47`) + test fixture (`bc7cacb`) + full suite re-run on the new CLI.
2. **The suite re-run then caught a REAL product bug the P2a green had masked by threshold**: 
   `runCapture` leaked ~4 fds per call (stderr Pipe never read, no explicit close);
   `killByTempDirScan` multiplies it by the machine's process count → measured **2559/2560 fds
   after ONE call** → every later `Pipe()` read 0 bytes → `sweep()` blind. At P2a the same suite
   passed because the process count was lower — green by threshold, not correctness. Fixed at the
   class level (both `runCapture` and `versionMatches`): stderr → `FileHandle.nullDevice`,
   explicit close of both pipe ends (`8b6081c`); post-fix measurement: 5 fds, suites
   `ALL CODEX-RUNNER TESTS PASSED` / `ALL GATE TESTS PASSED`.
3. Old brain probe 3: same 7/7-model auth cascade — third spaced confirmation of absence.

## 6. §Meta-pattern

The malattia-delle-malattie of this run is **superscar #3 (guard-over-match) migrating into the
product itself**: a fail-closed gate written to stop hallucinations is killing verified-true
answers on 3 of 8 structured questions, exactly like the worktree-isolation hook's ten recorded
over-match scars. Same antidote applies: every gate rule needs a guilt AND an innocence corpus
before it ships; the benchmark just supplied the innocence cases for free. Secondary pattern:
**same-family judging with under-supplied context produced 22/30 false verdicts** (W100 —
agreement/verdicts are not truth), which is why §8 made the session hand-check mandatory rather
than advisory.

## Adversarial review

**Declared limit of the hand-check layer**: the hand-checker is the conducting session, which also
wrote this report (generator≈grader within the session, as §8 itself mandates). Mitigation: a
cross-family refuter (**Kimi K3, refute-stance, with direct access to the answers JSONL and
corpus**) attacked the draft and landed 4 real findings, all folded before ship: (1) gap-side gate
kills were 4, not "6" (measured: 13 total = 9 structured + 4 gap-side); (2) Q11 belongs under
wrongful abstention too → floor iii is 4/8, not 3/8; (3) floor iv's "honest declared abstention"
framing hid the 4 gate-converted rows — now stated; (4) floor i's coverage was overstated ("100 %
hand-check" was of the FLAGGED set, not all 87 rows) and near-tautological on served text — now
stated precisely, and the raw-level tuple check (1 ambiguous-but-true clause in 87, zero invented
figures) was run and added in response. The RED verdict itself survived refutation unchanged.

## 7. §Solo-operatore / next actions

- **No operator action required.** The seat healed itself (usage window); never paid, never
  substituted.
- Session-owned next lane (blocking P2c): cure 4a (three gate rules, with guilt+innocence tests)
  and 4b (retrieval scoring), cure the judge-harness gap (§3), then **re-run this exact corpus**
  (same sha) and re-judge. Only a green re-run opens P2c (OpenClaw deletion, build B, fleet
  install).
- Business note (Zero, no action needed): even with the gate red, the served surface never lied —
  the failure mode is over-refusal, which costs helpfulness, not truth. That is the right side to
  fail on for a client-facing tool.
