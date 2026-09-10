# Astra round 2 — /bot staff-room packet v2

Seat: codex `gpt-6-astra`, `xhigh`, read-only, Pro, 2026-09-11 ~02:30–02:53 WITA. Bound to v2 sha256 `7b66c8a2…`/`b2c977a0…`/`a13f0b7d…`, against `origin/main = 4c48ca065b`. Verdict: REWORK (round-1 findings 2,3,6,7,8,10,13,14 RESOLVED; 1,4,5,9,11,12 PARTIAL → 15–20 BLOCKER, 21 MEDIUM). Verbatim verdict block from the session log (the `-o` file captured only the post-hook coda).

VERDICT: REWORK

Reviewed [README](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room/README.md), [B1](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room/B1-design.md) and [B2](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room/B2-engine.md) against `origin/main = HEAD = 4c48ca065b3e6df2b7b04cc68579bd299957b836`.

| Round-1 finding                                                            | Status       | V2 evidence or remaining gap                                                                                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. D4 lacks a specified sufficiency signal**                             | **PARTIAL**  | README:35,52 and B1:59 require measured candidates and staff-room selection before B2. However, the selection criteria and execution permissions conflict. See **15**.                                                                                                                                                     |
| **2. Undefined rank-derived values; weakening the nine fixtures**          | **RESOLVED** | README:34; B1:32–33,56–57 require exact eleven-case inventory, immutable historical evidence, contributing lists/ranks, fusion, transforms and additive variants preserving original challenges. B1.1 now reproduces the table itself; rc1a is not a dependency.                                                           |
| **3. Incomplete provenance perimeter**                                     | **RESOLVED** | B1:31,39–40,56 cover projection, both rerankers, cache, curated injection, trusted-tool evidence, documented FAQ/KG bypasses, serialization and digest compatibility. Unknown provenance cannot be inferred from magnitude.                                                                                                |
| **4. Benchmark substitution, empty cells and mutable labels**              | **PARTIAL**  | README:33 and B1:58 resolve independent inputs, ≥28 cases, denominators, preserved insufficient contexts, separate supplements, independent validation and freezing. The blanket assertion freeze still protects the known-wrong golden expectations. See **16**.                                                          |
| **5. Scoring success confused with safe delivery; wrong `context_length`** | **PARTIAL**  | B2:30,35 correctly define sealed chunks, including curated and excluding pricing. README:39 preserves D8; B2:48(g) exercises the real finalizer. Its delivery report has no explicit pass/fail contract. See **17**.                                                                                                       |
| **6. Frozen telemetry cannot reach the writer**                            | **RESOLVED** | README:64; B2:34,42,51 explicitly permit the narrow `CodexLegResult`/completion carrier and fenced worker write. B2.3b precedes #5337; #5337 must restart from a fresh base. Veto logic remains outside B2.                                                                                                                |
| **7. Wrong migration directory and missing-column deployment interval**    | **RESOLVED** | B2:43,50–51,69 correctly separate schema from writer, require applied-schema proof before B2.3b opens, and retain nullable columns/history during routine writer rollback. The migration-manager citation needs updating, not the sequence. See **21**.                                                                    |
| **8. Dead-writer Bites; ambiguous “abstained” semantics**                  | **RESOLVED** | README:37 defines the timestamp as successful send with a frozen true evidence label, distinct from refusal. B2:51 requires isolated-DB fence/failure tests and declares live telemetry unproven until B3 correlation. B1:58 makes the shipped reporting harness its immediate consumer.                                   |
| **9. “Read-only retrieval” can invoke prohibited services**                | **PARTIAL**  | B2:49 now bans embedding, expansion, paid reranking, cache writes and fallbacks, and aborts on missing vectors. However, no approved query-vector artifact is identified or handed over. See **18**.                                                                                                                       |
| **10. RC2/RC3 runtime dependencies and ownership**                         | **RESOLVED** | README:25–29,53–54,68 and B2:41,71 distinguish file ownership from runtime prerequisites. RC2 records **22**, RC3 records the amended text, and Fable owns corner closure. These remain receipt-gated claims, not production actions verified by this review.                                                              |
| **11. Council doctrine and executable R9**                                 | **PARTIAL**  | B2:56 correctly specifies the canonical panel, qualifying seats, journal schema and pack-relative `council_run`. The actual R9 probe passed Codex+Kimi and rejected Codex+GLM. B2:57 nevertheless permits Kimi to build while Kimi remains the mandatory refuter. See **20**.                                              |
| **12. Incorrect counts, citations and attribution**                        | **PARTIAL**  | README:14,18–20 fixes historical test attribution, coordinator-versus-child attribution, corpus distinctions and traffic inference. Remaining citation/count corrections are listed in **21**.                                                                                                                             |
| **13. Missing shared budget enforcement**                                  | **RESOLVED** | README:71; B1:28,73–76; B2:62–65 name the shared deadline mechanism, inherited remaining time, bounded renewal, retained attempts/reservations, continuation ceiling and zero ship reserve.                                                                                                                                |
| **14. Migration incorrectly requires Zero; imperator approval unclear**    | **RESOLVED** | README:9,51,79,86 and B2:50 restore the BLUE Dux’s additive-migration release responsibility. Under `army-map.md:98–99`, an explicit **ACCEPT bound to these hashes would constitute Astra’s approval**, requiring Fable’s approval of identical bytes and Zero’s opening instruction. **This REWORK grants no approval.** |

The cited source locations retain their stated meaning except the corrections below. The installed `hybrid/fusion.py` confirms the **local client** formula; it does not establish deployed-server configuration. The formatter and strict-penalty source support the raw-zero → `0.5` observation. R9 was exercised in memory; application test collection was blocked by the read-only environment’s unavailable writable temporary directory, so no fresh pytest pass is claimed.

15. **BLOCKER — B1.4’s acceptance and execution contract is internally inconsistent.**

    **Evidence:** B1:59 requires **every candidate** to distinguish the pairs, including the unchanged-scorer control already documented as returning `0.8 / 0.8`. A differently wrong decision could also satisfy “distinguish.” B1:20 prohibits generation calls while B1:59 requires model judgments. Listing “PII posture” does not constrain the eventual Codex input: [wa_package_builder.py:576](/Users/nuzantara/nuzantara/apps/backend-rag/backend/services/rag/agentic/wa_package_builder.py:576) redacts package fields, but the scorer still receives the original `query` at line 597.

    **Exact edit:** Replace B1:59’s universal success requirement with:

    > Measure every candidate, including failures and the unchanged-scorer control. The selected method must correctly classify both members of every ≥8 independently labelled pair; an unknown result does not count as successful discrimination. It receives only inputs obtainable at runtime, never expected labels, supporting-span annotations or case IDs. Any requested-fact extraction must be part of the measured method.

    Add a narrowly scoped exception to B1:20,41 permitting these **synthetic classification probes** through the authorized local/subscription routes. Specify the invocation, model/rubric identity, timeout and failure handling. Require the selected method’s unavailable/unknown result to remain distinguishable from “supported.”

    For candidate (iii), require any production-bound design to consume the **redacted query and capped redacted context**, without the reversal map or raw-query argument; outputs and receipts remain synthetic/redacted.

    **Keep B1:76:** it already supplies the correct fallback—no qualifying candidate means B2 cannot open and the staff room redesigns. No additional fallback is missing.

16. **BLOCKER — The assertion freeze preserves three known false-positive expectations.**

    **Evidence:** B1:58 correctly classifies the three capital/duration cases as insufficient with their original contexts. But README:36 and B2:48(e–f) freeze existing assertions. The checked-in [golden test](/Users/nuzantara/nuzantara/apps/backend-rag/backend/tests/unit/services/rag/agentic/test_evidence_cross_language.py:179) still labels those cases `True` at lines 183,186–187, selects context from that label at 207–212, and requires acceptance at 216.

    **Exact edit:** Narrow README:D5 and B2.1(e–f) with one named exception:

    > B1.3 records the independently reviewed correction of these three golden cases while preserving their original query/context inputs. B2.1 replaces the defective label-selected golden loop with fixed-input cases and corrected expectations, reported by the balanced language/stratum cells. This exception does not permit changing genuine safety-tripwire assertions or weakening high-score mismatch challenges.

    Activate those corrected assertions with B2.1’s scorer change, so B1 remains behavior-preserving. My round-1 blanket freeze was too broad; v3 must correct it.

17. **BLOCKER — B2.1(g) specifies delivery observations without delivery acceptance criteria.**

    **Evidence:** README:D8 and B2:35 clearly prohibit changing `wa_finalize` policy. Existing [finalizer tests](/Users/nuzantara/nuzantara/apps/backend-rag/backend/tests/unit/services/integrations/test_wa_finalize.py:508) protect both refusal and legitimate cautioned delivery. However, B2:48(g) allows a report merely to classify an unsupported substantive answer as “released as cautioned.” The current [delivery predicate](/Users/nuzantara/nuzantara/apps/backend-rag/backend/services/integrations/wa_finalize.py:204) checks positive context length, positive evidence and sufficient text length—not requested-fact support.

    **Exact edit:** Extend B2.1(g) to require:

    > Freeze synthetic candidate texts, case references and independently reviewed expected dispositions before the candidate run. Report baseline and candidate frozen evidence inputs, final disposition, reason and content verdict. Identical finalizer inputs must retain identical policy outcomes; the legitimate grounded-cautioned positive control must still release. Unsupported substantive advice is an acceptance failure even when labelled “cautioned.”

    Add:

    > If this cannot pass under unchanged D8, suspend for staff-room adjudication; do not alter `wa_finalize`, redefine `context_length`, or change threshold/telemetry semantics to manufacture suppression.

18. **BLOCKER — B2.2 lacks an identified, approved vector input artifact.**

    **Evidence:** B2:49 specifies retained vectors without naming their source. A related surface **does exist**: [scripts/.rag_canary/embedding_baseline.json](/Users/nuzantara/nuzantara/scripts/.rag_canary/embedding_baseline.json), containing 20 retained vectors of dimension 1536, labelled `text-embedding-3-small`, dated 2026-03-25. It is not Git-tracked and contains reference-text embeddings, not an approved B2 EN/ID query manifest. [rag_canary.py:318](/Users/nuzantara/nuzantara/scripts/rag_canary.py:318) regenerates it through an embedding call.

    **Exact edit:** Add a B2.2 entry prerequisite naming an immutable approved query/vector artifact with:

    > artifact SHA-256, exact synthetic-query-to-vector mapping, model/dimension provenance, language coverage, approval reference and accessible handoff location.

    Add:

    > Existing canary vectors may be reused without embedding only for their exact associated texts, after explicit selection and approval for this sample. They cannot be relabelled as embeddings of different queries. If no suitable artifact exists, the sample remains blocked for staff-room resolution; do not run `save_baseline` or silently generate replacements.

19. **BLOCKER — B2 permits threshold edits in the wrong source location.**

    **Evidence:** B2:34 permits only the **scorer** in `reasoning_utils.py`, while allowing “values only” changes in `_abstain_policy.py`. The actual tax/visa defaults live in [reasoning_utils.py:690](/Users/nuzantara/nuzantara/apps/backend-rag/backend/services/rag/agentic/reasoning_utils.py:690). [_abstain_policy.py:103](/Users/nuzantara/nuzantara/apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py:103) obtains the label threshold through `get_abstain_threshold`.

    **Exact edit:** Change B2:34 to authorize:

    > `reasoning_utils.py::calculate_evidence_score` for B2.1, and only the tax/visa entries of `DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT` for B2.2, subject to its measured acceptance contract. `_abstain_policy.py` retains the existing gate construction and divergence.

    Require B2.2’s report to record the effective thresholds, including whether an existing environment override supersedes the defaults. No environment mutation is implied.

20. **BLOCKER — The optional Kimi builder conflicts with the mandatory Kimi refuter.**

    **Evidence:** B2:56 fixes Kimi K3 on the panel; B2:57 permits Kimi-for-coding to build the harness or carrier tests. Different Kimi seats remain one family. [modus:149](/Users/nuzantara/nuzantara/.claude/skills/modus/SKILL.md:149) excludes a contributing family from its own refuter chain. B1:67–68 has the analogous conflict if Kimi builds and the Codex reviewer falls back to Kimi.

    **Exact edit:** Make B2’s external builder **GLM only** for the specified bounded lane; retain Gemini/Codex/Kimi as independent reviewers.

    For B1, add:

    > If Kimi contributes to the candidate, the Kimi review fallback is unavailable for that candidate. Use the independent Codex reviewer or suspend; alternatively choose GLM as the builder before contribution begins.

    Preserve B2:56’s journal/R9 clause. It is executable as written; GLM’s exclusion from quorum is correctly stated.

21. **MEDIUM — Correct the remaining citation and review-accounting drift.**

    **Evidence and exact edits:**

    - **B2:30:** replace `db/migration_manager.py:311–322` with **`:315–327`**. The `migrations_v2` assignment is now at 323. The migration-lint, previous-image workflow, additive release and rollback references otherwise support v2’s sequence.
    - **README:90:** the recovered round-1 numbered headings contain **10 BLOCKER and 4 MEDIUM**, not 11/3. Preserve the fourteen findings and correct that tally.
    - **B1:80:** remove the unpinned “86 of 87 packs on main” comparison. Cite [harness-floor.yml:983](/Users/nuzantara/nuzantara/.github/workflows/harness-floor.yml:983), which directly establishes the canonical `brief_ref: evidence/brief.yml` staging requirement.

The reading binds to these unchanged outputs of `shasum -a 256`:

```text
7b66c8a2d76602ca4ab2e79c2ac40f89db913bb3e18fe1685ec5fc296b363218  /Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room/README.md
b2c977a0d91696bb467aaa61bdfead85f915f0843304c5bbcb31d1d88961b986  /Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room/B1-design.md
a13f0b7d4f09242c9d56da02ba318e51e323a7beb9695f374c83f144e200b863  /Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room/B2-engine.md
```
