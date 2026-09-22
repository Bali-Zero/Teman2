---
date: 2026-09-22
domain: operations
client_case: none — internal product benchmark (KBLI Navigator P2b), synthetic corpus
sources:
  - scripts/kbli_bench/p2b_corpus.json (frozen, sha256 487bc9509d01456eb37a588c3ee942f4956731502697aef94f1a2ee1294008e7 — untouched)
  - scripts/kbli_bench/results/2026-09-14-k2-gamma/p2b_answers.jsonl (87 rows, served on M5, dataset c69a260d…)
  - scripts/kbli_bench/results/2026-09-22-rejudge-3x/ (this run: 3 judgings x 29 questions, anchored)
  - research/operations/2026-09-14-kbli-navigator-p2b-candidate-k2-gamma.md (the run being re-judged)
  - KBLI Navigator app repo, M5, no remote — read-only over ssh
adversarial_review: agy
---

# P2b — the instrument was wrong about three things, and one of them was the score

> Every number below comes from a command run on Pro on 2026-09-22 in the worktree
> `.worktrees/backend-rag-chat-p2b-cures-20260922`, or from a read-only `git show` on the app
> repo on M5. Nothing is carried over from a previous session's prose.

## 0. Verdict

**The P2b gate stays RED, and one floor is worse than the file said.** Re-judging the committed
k2-gamma answers with three independent judgings instead of one, anchored to the dataset those
answers were served from, gives:

| floor | threshold | committed (1 judging) | this run (3 judgings) |
| --- | --- | --- | --- |
| i zero fabrications | == 0 | **0/87** GREEN | **0/87** GREEN |
| ii structured accuracy | >= 0.80 (7 of 8) | 4/8 RED | **3/8** RED |
| iii wrongful abstention | <= 0.10 (0 of 8) | **1/8** RED | **1/8** RED |
| iv gap + out-of-corpus abstention | == 100% | **21/21** GREEN | **21/21** GREEN |
| gate | all floors intact | False | **False** |

Run: 29 questions x 3 judgings = 87 judgings, 0 judge errors, 254 s wall clock, judge
`gpt-5.6-sol` through the `codex` CLI on the ChatGPT seat. `judging_decisive` is true — no row
tied, so nothing here is a coin-flip left unresolved.

The 4/8 -> 3/8 move is **Q20 alone**, and it is not new information: the k2-gamma report already
measured six judgings of Q20 and recorded that four of them read `wrong`, with the committed 4/8
being one of the two lucky ones. What is new is that a protocol decides it instead of a footnote.

## 1. The three things the instrument was wrong about

### 1.1 One judging cannot hold a floor still — measured, 5% of rows

Across the 87 judged rows, the three judgings disagreed on **4 (5%)**, every one of them 2-1:

| qid | run | class | tally |
| --- | --- | --- | --- |
| Q03 | 1 | known-gap | correct 2 / wrong 1 |
| Q03 | 2 | known-gap | correct 2 / wrong 1 |
| Q20 | 1 | structured | wrong 2 / correct 1 |
| Q20 | 2 | structured | wrong 2 / correct 1 |

A single judging decides each of those four by coin-flip, and the two Q20 rows are the ones that
move a floor. The scorer now takes a majority per `(qid, run)` over every judging file it finds,
and names a tie `undecided` rather than resolving it: calling a tie `correct` inflates floor (ii)
and calling it `abstained` inflates floor (iii), so no resolution is direction-neutral. An
`undecided` structured row refuses the gate the same way an incomplete run does.

### 1.2 The dataset judged AGAINST was not the dataset served FROM

This was found by the instrument, not designed and then justified. The first live judging of Q13
against the tree's current dataset came back `wrong` with the reason:

> _"Correctly denies universality, but falsely labels KBLI 77400 BALI_BLOCKED; its record shows
> blocked false."_

The answer was right. On `c69a260d…`, the dataset that run was served from, 77400 **is** blocked;
on the tree's `b60cb1bd…` it is not. The file moved **twelve times in the ten days** after the
k2-gamma run. An unanchored re-score does not produce a noisier number — it produces a confident
wrong one, with a citation.

Every answer row already records the `dataset_sha256` the app read. Nothing compared it to the
file the scorer loads. It does now: a mismatch refuses the gate and prints the recovery, and
`P2B_DATASET_ROOT` points the scorer at the right blob. This run is anchored to `c69a260d…`
(`dataset.anchor.pass = true` in `manifest.json`), which is why its verdicts are comparable to
the committed ones at all.

### 1.3 A census carried in prose had drifted by a factor of four

The scorer's `class_rules.bali_moratorium_scope.declared_gap` stated that `l4_bali.blocked` is
true on **518** records, "372 risk-class + 68 TERTUTUP + 48 named-moratorium + 17
non-classifiable + 13 other". That was measured on `3dafab17…`. The k2-gamma report declared it
stale at 519 and left it, because there was nothing to fix it in.

The cure is that the sentence is now rendered from a count, so it is right about whichever
dataset is loaded. Both of these come out of the same code, this turn:

| dataset | blocked | largest group |
| --- | --- | --- |
| `c69a260d…` — the anchored run, committed in `2026-09-22-rejudge-3x/p2b_score.json` | **519** of 1,559 | `BLOCCATO_CLASSE_RISCHIO` 373 |
| `b60cb1bd…` — the tree's current file | **135** of 1,559 | `TERTUTUP` 72 |

The first line is k2-gamma's own declared-but-unfixable 519, now printed by the instrument
instead of denied by it in prose. The second is what the hardcoded sentence would say today:
wrong by a factor of four, and naming `BLOCCATO_CLASSE_RISCHIO` as the largest cause when the
tree's dataset has none — those 383 records are now `ATTENZIONE_FASCIA_BALI`, and they are **not
blocked**. A hardcoded census does not age into being slightly wrong; it ages into naming things
that do not exist, inside a JSON a reader takes for a measurement. The report also carries the
dataset's sha256 so a census can never again be silently anchored elsewhere.

## 2. What the lane was asked to build, and what was actually there

The lane brief named three cures. Checked before building:

| brief | measured | outcome |
| --- | --- | --- |
| **A** — cure `KBLIAnswerGate` over-match "in `apps/backend-rag`" | `git grep -n "class KBLIAnswerGate" origin/main -- apps/backend-rag` returns **zero**. The gate is Swift, in the KBLI Navigator app repo on M5, **no remote**. | Not buildable here. Specified instead — §3. |
| **B** — `kafe di Ubud` must package 56303 and 56101 | Q11's `package_codes` in the k2-gamma answers is `['10761','56101','56290','56303','66301']` on **all three runs**. | **Already cured.** The residual on Q11 is answer framing: the judge's reason is "the answer never presents 56101 as the unblocked option". No retrieval change was made, and none is warranted. |
| **C** — feed the judge the model's actual package | `cmd_prompts` builds ground truth as `expected.codes UNION` the served `package_codes`, with the W100 lesson in its comment. | **Already shipped.** |

The brief's floors (4/8 accuracy, 4/8 wrongful abstention) are the 2026-08-20 numbers. The
current measurement is 3/8 and 1/8.

## 3. The gate: the cure shipped and the class is still there

`Sources/KBLIAnswerGate.swift` carries four carve-outs from commit `3e4ca59` — _"cure the four
over-match classes killing verified-true answers"_ — α β γ δ, each naming its benchmark question.
Measured on M5 today, that file is **byte-identical on all seven branches** (sha256
`dddadb5bb3ae…`), including `k2/gamma` at `69933ab`, the build this run was served by. So the
carve-outs were in, and the run still shows the class:

- **Q13 runs 1 and 3** — `percentCodeMismatch` on the question's own 51%, standing alone in its
  clause: _"jadi tidak dapat menyimpulkan bahwa semua sektor boleh untuk kepemilikan asing 51%"_.
  δ discounts an echo only when a substantive figure remains beside it.
- **Q22 run 3** — `percentCodeMismatch(25200, claimed 100, actual 49)` on a **negated** figure:
  _"bukan izin otomatis untuk 100% asing"_. Run 1 of the same question survives only because it
  denied the same thing without a numeral.

α already settled negation for CODES (`statesAbsence`). The figure path never got the twin —
W132 inside the product's own gate. The rule, stated per figure on two closed lemma sets with a
contrastive-conjunction scope boundary, and its 12-case guilt/innocence corpus, are in
`docs/specs/p2b-answer-gate-figure-relations-v1.md`. The code half belongs to the app lane.

## 4. The seat was never dead

`codex exec` on Pro fails at `Error loading config.toml: invalid type: map, expected a boolean in
features`: `~/.codex/config.toml` carries a `[features.context_management]` sub-table that
codex-cli 0.149.0 will not parse. From outside this reads as `seat codex: UNKNOWN_ERR` in the
fleet probe — a config defect wearing a quota wall's costume, for at least eight hours before
this session. `run_p2b.py` now builds a private 0700 `CODEX_HOME` with the nested `[features.*]`
tables dropped, never writing to `~/.codex`. 87 judgings, 0 transport errors. The user's own
config is untouched and still broken for interactive use — that is an operator gesture, not this
lane's.

## 5. Re-running it

```bash
P2B_DATASET_ROOT=<tree holding the answers' dataset> \
python3 scripts/kbli_bench/run_p2b.py \
  --answers scripts/kbli_bench/results/2026-09-14-k2-gamma/p2b_answers.jsonl \
  --out     scripts/kbli_bench/results/<date>-<tag> \
  --judgings 3
```

It does not serve the corpus, deliberately: the answers come from the app repo's
`Tests/benchrunner`, which runs the production path. A serve step re-implemented in this repo
would measure the harness instead of the product.

## 6. Limits, declared

- **No serving re-run.** These are the k2-gamma answers, re-judged. A fresh serve needs the app
  build on M5 and belongs to the app lane; nothing in this report claims a new brain was measured.
- **The gate's code half is not in this PR** and cannot be: the app repo has no remote and lives
  on another host, so a Swift commit made from here could not be reviewed by anything.
- **`chat_kbli` was not measured live.** Both `/kbli-notebook/chat` and `/kbli-notebook/search`
  on `nuzantara-rag.fly.dev` answer `{"detail":"Authentication required"}`; the credential is
  operator territory and was not hunted for. Cure B is reported cured on the surface the
  benchmark actually measures — the macOS app — and unmeasured on the HTTP one.
- **The adversarial round found nothing, and the session did.** `agy` (Gemini) reviewed this
  report against a mechanical digest of the two score files and returned `VERDICT: OK`
  (`evidence/.../council/agy-round1.txt`). Section 1.3 was then rewritten anyway: the seat
  checked the 135 census against the digest and passed it, while the committed artifact for the
  ANCHORED run prints 519 — both are correct, for different datasets, and the section said only
  one of them. One seat returning OK is weak evidence; it is recorded as what it is. The judge
  seat itself was not asked to review its own run — generator is never grader.
- **P2c stays closed.** Two floors are red; nothing here opens it.
- **Q23, Q05, Q11, Q26 are unchanged and unaddressed** — all four are answer-framing defects in
  the app's prompt, named in the k2-gamma report §4, and none is a gate or a scorer defect.
