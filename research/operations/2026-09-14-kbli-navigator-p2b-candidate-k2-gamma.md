# KBLI Navigator P2b — the k2-gamma candidate: one build, one 87-row run, gate RED

> Mission SAETTA-K2 (BLUE, host M5), window W-K-GAMMA, task-id `k2-gamma`. Every number here
> comes from a command run on 2026-09-13/14 (UTC) on M5 and from the files under
> `scripts/kbli_bench/results/2026-09-14-k2-gamma/`. The app repo has no remote; its half of this
> window is branch `k2/gamma` (head `10f05f9`, evidence in `docs/gates/2026-09-14-k2-gamma/`).

## 0. Verdict

**The P2b gate is RED on the candidate, under both scorers.**

| floor | threshold | origin/main scorer (`8664b1ba30`, #6428) | row-identity scorer (`c3f4bb32`, unshipped) |
|---|---|---|---|
| i zero fabrications | == 0 | **0/87** GREEN | **0/87** GREEN |
| ii structured accuracy | >= 0.80 (7 of 8) | **4/8** RED | **3/8** RED |
| iii wrongful abstention | <= 0.10 (0 of 8) | **1/8** RED | **1/8** RED |
| iv gap + out-of-corpus abstention | == 100% | **21/21** GREEN | **21/21** GREEN |
| gate | all floors + intact run | **False** | **False** |

Run integrity, both: 87 rows = 29 x 3, `complete=True`, categories `{answered: 87}`, no
synthesized row, no duplicate, 0 runner errors, one dataset sha on every row.

The two score files disagree on exactly one question, **Q20**, on the SAME answers:
`correct/correct/correct` in the main-scorer judging, `wrong/wrong/correct` in the row-identity
judging. The two judge prompts differ (sha256 `a4c5f0b1…` and `0f4d792c…`), so a single pair
cannot separate judge variance from prompt sensitivity. Measured afterwards by re-judging Q20
twice more with EACH byte-identical prompt (`q20_repeat_judgings/`): main prompt `wrong/wrong/correct`
twice, row-identity prompt `wrong/wrong/correct` once and `correct/correct/correct` once. The same
prompt yields both outcomes, so the flip is judge variance, and across the six judgings Q20's
majority is `wrong` in four. Only Q20 was re-judged: holding the other seven structured verdicts
(identical in both full judgings), floor (ii) reads 3/8 in four of the six Q20 judgings and 4/8 in
two, and the committed main score (4/8) is one of those two. No outcome turns the gate green.

**Why two scorers.** The window brief asked for scoring "under the row-identity contract". That
contract (`scripts/kbli_bench/ROW_IDENTITY_CONTRACT.md` on branch `agent/air-m5/ops/k2-row-identity`,
never pushed) was BLOCKED at its final gate: its section-7 served digest does not hash
`persyaratan_served`/`kewajiban_served`, and its monorepo half never shipped. This PR does not
carry that code. The canonical, reproducible score is origin/main's; the row-identity score is
filed beside it as a declared secondary so a ruled contract can be compared against it.

Reproduced from this branch: `python3 scripts/kbli_bench/score_p2b.py score
scripts/kbli_bench/p2b_corpus.json scripts/kbli_bench/results/2026-09-14-k2-gamma/p2b_answers.jsonl
scripts/kbli_bench/results/2026-09-14-k2-gamma/main_scorer/judge_verdicts` exits 0 and its
output is JSON-equal to `main_scorer/p2b_score.json` (the committed file is prettier-formatted by the
repo's pre-commit hook; the scorer itself prints `indent=1`).

## 1. Manifest (§C.4.5 fields, generated from the bundle — `manifest.json`)

| field | value |
|---|---|
| app commit built and run | `69933ab8c3cdd163724bca675c4d6341b27e40d7` (branch `k2/gamma`; `Sources/` byte-identical at head `b44f29a`) |
| variant | `internal` (`BZVariant=internal`, `com.balizero.kbli-navigator.internal`, universal x86_64+arm64, ad-hoc signed) |
| build | `./build.sh --variant internal`, BUILD_RC=0, 2026-09-13T17:39:58Z -> 17:41:37Z |
| bundle_sha256 | `72c7b4c646159dd12723f2ec215c5a1fa5323f169a0f56ec83760fcf71e6a282` (sorted per-file sha256 lines, 46 files) |
| bundle executable sha256 | `60b0ed64c3287cfad2bb8c763754c46f499430e9c84498fec96e7a080e84d861` |
| dataset_sha256 | `c69a260dba597d6b172996da7b99460f1498c3bb9d9df6f2ca6c9e4f782b2b40` — bundle, app `Resources/`, every answer row, and `data/source_documents/` on origin/main |
| runtime | `~/.local/share/kbli-navigator/runtime/codex-cli-0.147.0/bin/codex.js`, `--version` = `codex-cli 0.147.0` |
| marker_fingerprint | none — internal variant; the BKPM marker is not consulted and BKPM chat stays off by construction |
| corpus | `scripts/kbli_bench/p2b_corpus.json` sha256 `487bc950…` (frozen, not amended) |
| run | 2026-09-13T17:42:41Z -> 18:00:32Z, serving `gpt-5.6-terra` through `KBLICodexRunner` (production argv) |
| judge | `gpt-5.6-sol`, same runtime, `--ignore-user-config --ignore-rules`, one call per question, no retry, 29/29 parsed, both judgings |

**The codex pin (window deliverable 1)** is now an explicit allow-list in the app:
`allowedVersions = ["codex-cli 0.147.0"]`, exact membership, one test per allowed version, refusals
above and below (0.148.0, 0.154.0, 0.147.1, 0.146.0, 0.146.9, suffix, prefix, floor, non-zero
exit, stderr-only), `KBLI_CODEX_BIN` proven to resolve the binary without widening the list.
Measured at absolute paths: app runtime and Homebrew answer 0.147.0, the mise copies 0.154.0, and
no install answering 0.148.0 exists on disk — so the old 0.148.0 pin is not re-admitted.
Five app suites at `b44f29a`: `SUITES_RC=0`. App council: codex-gpt-5.6-sol OK and
agy-gemini-3.1-pro OK on `20ac1be..b44f29a` after one DEFECT each, both cured at depth 1.

## 2. Before -> after (floors compared; scores are not like for like)

BEFORE is window A's AFTER run (app `54772e0`, dataset `3dafab17…`, window-A scorer), read from
the app repo's `docs/gates/2026-09-13-window-a/p2b/p2b_score_after.json`. Between the two runs the
brain moved (6 commits touch `Sources/`: fab83f7, 26659ec, 29805ec, c0e4984, 3ee637f, 69933ab), the
dataset moved to the canonical `c69a260d…`, and the scorer moved — no delta is attributed to any
one of them, and none to the allow-list, which changes nothing about serving when the version is allowed.

| floor | BEFORE | AFTER (main scorer) |
|---|---|---|
| i | 1/87 RED | 0/87 GREEN |
| ii | 4/8 RED | 4/8 RED |
| iii | 1/8 RED | 1/8 RED |
| iv | 19/21 RED | 21/21 GREEN |

| structured qid | BEFORE | AFTER main / row-identity | named cause (judge reason or gate reason, this run) |
|---|---|---|---|
| Q05 | wrong x3 | wrong x3 / wrong x3 | 68111 supported; the answer never states 68200 is absent from the KBLI 2025 catalogue |
| Q11 | wrong x3 | wrong x3 / wrong x3 | package holds 56101 and 56303; the answer never presents 56101 as the unblocked option |
| Q13 | abstained x3 | abstained/correct/abstained (both) | runs 1 and 3 rejected by the app's answer gate: `percentCodeMismatch` on the user's own 51% |
| Q20 | wrong/correct/correct | correct x3 / wrong/wrong/correct | judge variance on identical prompts; majority `wrong` in 4 of 6 judgings (section 0) |
| Q21 | correct x3 | correct x3 (both) | |
| Q22 | correct x3 | correct/correct/abstained (both) | run 3 rejected by the gate: `percentCodeMismatch(25200, claimed 100, actual 49)` on a negated 100% |
| Q23 | wrong x3 | wrong x3 (both) | names only 64330; never states the Low + Medium-Low class scope |
| Q26 | correct x3 | wrong/correct/correct (both) | run 1 reports the Bali axis as OPEN beside a 0% cap; the package headline for 79122 is NATIONALLY_CLOSED (app verdicttest) |

Packages were identical across the three runs for every question.

## 3. Q23 — a leftover, not a cure

No field-predicate retrieval tier was built. Measured: all 1,559 records of `c69a260d…` carry the
identical `l4_bali.moratorium` block (rule, effective 2026-05-13, source letter), and Q23's package
(`39001,64330,86105,88907,98100`, identical on all three runs) therefore already carries the rule.
The failure is the answer reporting one code's verdict instead of the class rule. A field-predicate
tier would make Q23's retrieval earned rather than lexical luck, but would not by itself change that
answer. Question it would address: **Q23**. No lexical re-weight was made.

## 4. What goes back to the lane that owns it

- The app answer gate over-matches a user's own figure and a negated figure: Q13 runs 1/3, Q22 run 3.
- Answer framing against the served verdict: Q11, Q23, Q26 run 1; Q05's absent-code statement.
- Q20's judge variance: one sol judging per question cannot hold floor (ii) still; a judging protocol with repeats is the harness lane's to decide.
- The row-identity contract rewrite and its re-gate; then re-score `p2b_answers.jsonl` (kept for that).
- Hand-check: the judge reason of every structured row and the raw answers of Q05 r1, Q13 r1/r3,
  Q20 r1, Q22 r3, Q23 r1-3, Q26 r1 were read; the seeded random sample was not hand-read.
