# B1.2 inventory — the eleven, by inventory and not by grep

Base sha `1d726045c9`. Every line below was re-read from disk on this base by the Dux, not
taken from a child's report. Paths are relative to `apps/backend-rag/backend/tests/`.

## The nine "impossible cosine" fixtures — RECOVERED

| #   | node id                                                                                                                                                 | line     | literal today                                                   |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | --------------------------------------------------------------- |
| 1   | `unit/services/rag/agentic/test_abstain_bypass_policy.py::TestTrustedToolDetection::test_successful_but_irrelevant_vector_hit_stays_below_abstain_gate` | :294     | `sources=[{"score": 0.91}]`                                     |
| 2   | `unit/services/rag/agentic/test_reasoning.py::TestCalculateEvidenceScore::test_no_keyword_overlap`                                                      | :212     | `sources = [{"score": 0.9}]`                                    |
| 3   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_stop_words_only_query_keyword_ratio_zero`                               | :196     | `[{"score": 0.8}]`                                              |
| 4   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_short_words_only_yields_near_zero`                                      | :207     | `[{"score": 0.8}]`                                              |
| 5   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_entity_mismatch_company_vs_visa`                                        | :256     | `[{"score": 0.6}]`                                              |
| 6   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_semantic_penalty_not_applied_when_final_score_at_or_below_015`          | :284     | `[{"score": 0.35}]  # cosine 0.35 < 0.5, would trigger penalty` |
| 7   | `services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::test_kitas_query_with_kbli_results_low_score`                                 | :34, :35 | `"score": 0.85` and `"score": 0.75` (two sources, one test)     |
| 8   | `services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::test_nonsense_query_zero_score`                                               | :57      | `"score": 0.8`                                                  |
| 9   | `services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::test_entity_type_mismatch_detection`                                          | :148     | `sources = [{"id": 1, "score": 0.9}]`                           |

**Excluded on purpose, verified:** `test_abstain_bypass_policy.py:311` also reads `0.91`, but it
belongs to `test_relevant_vector_hit_can_pass_through_relevance_path`, a different and untouched
test that expects the score to PASS. A score-literal grep would have swept it in; that is the
concrete reason D3 forbids the grep as an inventory method.

**Row 6 is the corroboration of F-B1.1a, in the repo's own words.** Its inline comment says
`cosine 0.35 < 0.5, would trigger penalty` — the fixture exists to exercise
`reasoning_utils.py:665`, and the measured pipeline floor of 0.5082 says that branch cannot be
entered from any live path. The fixture is not merely using an unreachable number; it is the only
witness to a guard production never runs.

## The tenth — NAMED, NOT LOCATED

PR #5618's body, verbatim: _"It regressed eleven standing abstain tripwires: nine let an off-topic
query clear the gate on cosine alone, and one newly discarded a perfect lexical match (over-abstain,
the opposite direction)."_ That tenth is a behaviour gap in the withdrawn design, not a fictional
cosine, so it is **not** a fixture re-base candidate. No file or line for it appears in any source.

## The eleventh — UNRESOLVED

Three independent sources — the #5618 PR body, `evidence/2026-09/agent-nuzantara-ops-bot-wa-evidence-e34da839/brief.yml:26-31`,
and the rc1a commit message — all assert **eleven** and all itemise **nine plus one**. 9 + 1 = 10.
Nothing anywhere names the eleventh. Recorded as explicitly unresolved per D3, never guessed.

## The withdrawn candidate SHA — UNRESOLVED, with an immutable receipt

Not in #5618's eight pre-squash commits, not in `git log --all`, not in `git fsck --unreachable`,
not findable by GitHub commit search on its distinctive phrases. Receipt in lieu of the SHA:
`gh api repos/Bali-Zero/Teman2/actions/runs?branch=agent/nuzantara/ops/bot-wa-evidence&per_page=100`
over three pages returns **255 runs spanning 2026-09-03T11:35Z → 2026-09-09T17:17Z whose
conclusions are only `success` or `cancelled` — zero `failure`, ever.** #5618 was squash-merged as
`2cd3cf84b8` and its branch ref deleted. So the verifier run that found the eleven regressions was
never a CI run: it ran out of band and its pytest output was never committed. That is the honest
end of the trail, and it is why the eleventh cannot be recovered rather than merely has not been.

## The sibling artifact B1.2 consumes — and the reason it cannot be adopted as it stands

The branch carries **three** unpushed commits, and the pack cites all three (the first draft of
this inventory recorded only the first — the staff room caught it, and the correction matters
because the second commit is a design question, not a duplicate):

| sha                                        | subject                                                                          | what it is                                         |
| ------------------------------------------ | -------------------------------------------------------------------------------- | -------------------------------------------------- |
| `92f40801235cf33b32a8d71f241b6400cad64536` | test(bot): rebase nine abstain tripwires on measured embedding cosines           | the rebase + `measured_cosines.py`                 |
| `30a0205dab`                               | test(bot): guard abstain fixtures against unmeasured cosines                     | a 192-line guard, `test_measured_cosines_guard.py` |
| `84bf272a24`                               | docs(evidence): brief for the nine abstain tripwires rebased on measured cosines | the lane's brief; branch tip                       |

A local keep-ref `refs/keep/rc1a-2026-09-11 -> 84bf272a24` protects all three from a broker reap or
a graveyard sweep. **Read the table by sha** (`git show 92f4080123:apps/backend-rag/backend/tests/fixtures/measured_cosines.py`),
never from the working tree.

### The guard commit inherits the same false premise, and B1's own vocabulary is what refutes it

`30a0205dab`'s message says it "flagged exactly the seven >= 0.8 fixtures of the nine and nothing
else in backend/tests" — that is a guard that judges a score by its MAGNITUDE, on the assumption
that a high number is an implausible cosine. Under the measured pipeline a high number is entirely
plausible: a result ranked first in BOTH prefetch lists fuses to 1.0 and formats to 1.0, and the
curated block is minted at a literal 1.0. So that guard would flag legitimate pipeline values while
passing a fictional 0.4. `core/score_provenance.py`'s first rule already states the principle that
refutes it — a kind is declared by the writer that mints the value and is NEVER inferred from
magnitude, because magnitudes overlap across kinds by construction.

**B1.2 keeps the guard's INTENT and inverts its test.** The guard B1.2 ships is the one `B1-design.md`
§4 specifies: it fails if a tripwire fixture declares a source `score` without a `score_kind` from
the frozen vocabulary. Provenance-based, not magnitude-based — it cannot be fooled by a plausible
number and cannot punish an implausible-looking true one.

### The rebase commit

Commit `92f40801235cf33b32a8d71f241b6400cad64536` (worktree
`.worktrees/backend-rag-rc1a-fixtures-real-cosines`, branch
`agent/nuzantara/backend-rag/rc1a-fixtures-real-cosines`, **never pushed**, broker lease ORPHAN)
rebases these same nine onto real `text-embedding-3-small` cosines measured in one API request
(20 texts, 216 prompt tokens) inside the prod `rag` container at 2026-09-10T18:03Z.

Its own docstring states the premise the whole commit rests on: _"A `sources[].score` in a
scorer fixture stands for the cosine the retriever would return for (query, retrieved chunk)."_
**That premise is false.** `sources[].score` is what `wa_package_builder.py:289` forwards out of
`result_formatter.py:89` — `1/(1+distance)` over a server-side RRF output on the hybrid path,
`1/(2-cos)` on the dense path. It is never a cosine on either. Its measured values span 0.04-0.51
and the measured live floor is 0.5082 hybrid / 0.5 dense, so **every one of them is below the
floor**: as impossible as the 0.35-0.91 they replace, in the other direction.

Two further divergences from D3/D5: the commit MOVES the inputs in place ("only the fictional
inputs moved") where D3 requires the originals PRESERVED with variants ADDED, and its table is
keyed on `(query, context)` text pairs so it cannot express contributing ranks, list membership or
fusion configuration — the fields D3 makes mandatory.

**What B1.2 does with it.** The cosines are sound as `score_raw` on the DENSE path, which is the
one path with a real cosine behind the number, and the correct fixture value is one transform away:

| measured cosine | → `score` = 1/(2−cos) |
| --------------- | --------------------- |
| 0.04            | 0.5102                |
| 0.14            | 0.5376                |
| 0.16            | 0.5435                |
| 0.30            | 0.5882                |
| 0.51            | 0.6711                |

All five land above the 0.5082 hybrid floor, inside the live band. B1.2 therefore ADDS variants
that carry the measured cosine as `score_raw`, the derived value as `score`, and
`score_kind = dense_formatted`, beside the nine preserved originals — and makes **no new embedding
call**, so D3's "no embedding API call is needed" holds without reopening any allowance.
