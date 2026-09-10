# Astra round 1 — /bot staff-room packet v1

Seat: codex `gpt-6-astra`, `model_reasoning_effort=xhigh`, `--sandbox read-only`, Pro, 2026-09-11 ~02:12–02:26 WITA. Bound to v1 sha256 `757d1824…`/`e03872fe…`/`1a9754d7…`. Verdict: REWORK (14 findings: 10 BLOCKER, 4 MEDIUM). Verbatim final message (`codex exec -o`); client PII: none.

VERDICT: REWORK

Reviewed the supplied v1 files against local `HEAD = origin/main = 074b4fde010aa6d4228decffc568d802ae2914f8`. This **counts as Astra’s reading of v1, not approval**. No repository edits, production queries, sends or embedding calls were made. Historical test results were inspected; the suites were not rerun.

Spec references below resolve to the [staff-room directory](/Users/nuzantara/nuzantara/.worktrees/docs-bot-staff-room/research/operations/2026-09-11-bot-staff-room). Code paths are relative to `apps/backend-rag/backend/` unless stated otherwise.

1. **BLOCKER — D4 promises a sufficiency signal that neither window specifies.**

   **Evidence:** README:33 separates authority, ranking and support, but B1:39 adds provenance only; B2:47 makes relevance primarily rank-derived. Naming a ranking score does not establish whether the retrieved text contains the requested fact.

   I executed the unchanged `calculate_evidence_score` function, extracted through Python AST without application initialization. With the same query, source score `0.9`, and two synthetic contexts—one supplying the requested capital amount, the other explicitly saying it was unspecified—the observed scores were:

   ```text
   support_present_then_missing [0.8, 0.8]
   ```

   This is a counterexample to the current scorer, not an execution of the proposed B2. It demonstrates the distinction B2 must learn to make.

   **Exact edit — README D4; B1 §4; B2.1:**

   > B1 freezes separate contracts for source authority, retrieval ranking and support for the requested fact. Before B2 opens, its design identifies the support-checking method, its inputs, failure behavior and consumer. Neither retrieval rank, source authority nor topical overlap alone establishes sufficiency. Mandatory counterfactual pairs retain entity, language, retrieval provenance and rank while adding or removing the requested fact. B2 must distinguish those pairs without case-ID rules or benchmark-specific exceptions.

2. **BLOCKER — “Pipeline-real value for an off-topic hit at rank k” is undefined, and lowering the nine fixtures could manufacture success.**

   **Evidence:** README D3 and B1:57 assume that the contract table supplies replacement values. Final fused rank does not uniquely determine RRF score: contributing-list ranks and membership matter.

   The installed Qdrant client’s `hybrid/fusion.py:4–27` computes contributions as `1/(2 + zero_based_position)`. Under that local implementation, a document first in one list scores `0.5`; first in both lists scores `1.0`. The formatter then produces respectively `0.6667` and `1.0`. These are arithmetic examples using the local client implementation, **not verification of the deployed server’s configuration**. An irrelevant document can still rank first.

   B1:33’s seventeen score-literal matches also do not identify nine mismatch cases. The committed #5618 brief:26–31 records aggregate eleven/nine counts without the complete node-ID inventory.

   **Exact edit — README D3 and B1.2:**

   > Recover the exact eleven historical failing node IDs, the nine proposed rebases, the other two regressions, and the withdrawn candidate SHA or immutable failure receipt. A score-literal grep is not that inventory. Each pipeline fixture specifies provider/version, contributing ranks, list membership, fusion configuration, raw score, fallback path, formatter transform, boosts and rounding. Final rank alone never determines its value. Preserve existing high-score mismatch challenges; add pipeline-derived variants rather than replacing their difficulty with smaller scores. Assertions remain unchanged. Unrecoverable historical inventory is explicitly unresolved.

3. **BLOCKER — B1’s writable perimeter cannot deliver provenance end to end.**

   **Evidence:**

   - `services/rag/agentic/tools.py:279–288` reconstructs source dictionaries and retains `score` while dropping provenance. That file is outside B1’s writable list.
   - `core/reranker.py:169–180` and `services/rag/reranker.py:345–352` overwrite `score` with reranker output while preserving the previous value as `vector_score`.
   - `services/search/search_service.py:1100–1103` returns cached results before formatting; existing cached results can lack the new field.
   - `_reasoning_evidence.py:356–381` has a trusted-tool `0.85` bypass as well as the ordinary scorer call.
   - FAQ and KG fast paths in `orchestrator_core.py:428–440,1084–1103` bypass the ordinary scorer; they should not be inaccurately described as ordinary numeric-score writers.

   The hash itself is not the missing mechanism: `wa_package_builder.py:434–453` hashes full chunks **and** `evidence_inputs`. Provenance retained in chunks can therefore be covered without gratuitous duplication. Current projections at `:289` and `:595` still lose it.

   **Exact edit — B1 §2 and B1.1:**

   > Extend B1’s additive perimeter to the source projection in `tools.py` and the actual reranker score writers. Freeze a producer-to-consumer inventory covering hybrid, dense fallback, both rerankers, curated injection, caches, trusted-tool evidence and FAQ/KG bypasses. Preserve existing numeric behavior. Cached or legacy values without provenance are explicitly unknown; never infer a kind from numeric magnitude. Bypass routes have explicit documented contracts rather than invented retrieval scores.
   >
   > Tests cross producer, formatter/reranker, source projection, package construction, DLP/capping, canonical serialization and scorer input. Changing provenance changes the package digest. Pin compatibility with in-flight packages. State whether provenance lives in hashed chunks, `evidence_inputs`, or both, and prove that the scorer receives the same provenance whose bytes were sealed.

4. **BLOCKER — The benchmark can be gamed through context substitution, empty cells and post-freeze changes.**

   **Evidence:** In `test_evidence_cross_language.py:207–212`, the boolean expected label selects the context. Simply changing rows 4, 7 and 8 to `False` swaps their company context for `UNRELATED_CONTEXT`; that does **not** test relevant-but-insufficient evidence.

   B1:58 permits either relabeling or filling the missing facts. README:59 permits appending to a file whose SHA is supposedly frozen. B2:62 declares the benchmark wrong when live measurements disagree, protecting the scorer from falsification. Neither “correct band” nor complete cell occupancy is specified.

   **Exact edit — README D2; B1.3; B2.1 and §6:**

   > Each case independently stores query, actual context, provenance fixture, expected answerability, requested fact, supporting span or missing-fact explanation, language pair and expected gate outcomes. Expected labels never select inputs. Preserve the original insufficient contexts; enriched sufficient counterparts are additional cases.
   >
   > Define the five reporting strata and their precedence. Generic overlap and company prefix are nuisance properties, not universal proof of insufficiency; include sufficient counterparts where appropriate. Every required cell has a positive denominator. With four EN/ID query-context combinations, require at least three sufficient cases and one case from each of the four negative strata per combination: at least 28 cases.
   >
   > Freeze the case manifest, contexts, labels, numerical band boundaries and baseline hash after independent label review. Keep B2 supplements in a separate file. Report mandatory-set results separately from independently selected validation cases. Zero errors means zero observed errors on those sets, not a population error-rate guarantee. Disagreement suspends acceptance for adjudication; it does not automatically invalidate the benchmark.

5. **BLOCKER — Scorer acceptance does not establish safe final delivery; `context_length` is misstated.**

   **Evidence:** B2:35 calls `context_length` a count of retrieved vector chunks. `wa_package_builder.py:527–548,599–604` actually counts sealed chunks, including synthetic curated content, while excluding the separate pricing block.

   `wa_finalize.py:204–224` also checks answer length. More fundamentally, `:822–845` intentionally permits substantive, cautioned answers with `abstain=true`. Its comments explicitly preserve the ruled distinction between a confidence label and discarding advice. A positive insufficient score below the label threshold can therefore pass B2’s classification metric while substantive text is still sent.

   **Exact edit — B2 §1, §2 and B2.1:**

   > Preserve `context_length = len(sealed chunks)`, including curated chunks and excluding the separate PricingTool block. Pin empty, curated-only, vector-only and pricing-only packages through finalization.
   >
   > Report generation-gate, label-gate and final-delivery outcomes separately. Mandatory insufficiency negatives cross the real finalizer with substantive candidate text; classification results alone cannot establish absence of unsupported delivered advice. Preserve legitimate cautioned answers under the existing ruling. Any change to that delivery policy must be explicitly specified and reviewed, never introduced incidentally through thresholds or telemetry.

   **Additional edit — README D5:**

   > Freeze existing tripwire queries, contexts and assertions. The only planned removals are the two named strict-xfail markers after their unchanged assertions pass. Pipeline-derived scenarios are additions. Do not restore the deliberately removed `pt`, `rp` or `cv` identifier shortcuts.

6. **BLOCKER — B2.3 cannot obtain frozen telemetry within its stated perimeter.**

   **Evidence:** `wa_codex_leg.py:598–607` parses sealed evidence and `:928–945` passes it to finalization, but `CodexLegResult` at `:415–436` lacks those fields; successful completion at `:964` returns text and reason. The worker receives that result at `wa_outbox_worker.py:1000–1017`.

   `wa_finalize.py:753–772` has neither an outbox ID nor a DB handle. Reading the broker afterward cannot repair the loss: `wa_broker.py:789–808` clears the package and evidence during consumption. README:62 forbids the required carrier file because of #5337.

   **Exact edit — README sibling table; B2 §2 and B2.3:**

   > B2 owns the additive frozen-evidence carrier in `wa_codex_leg.py::CodexLegResult` and completed-result construction, plus the outbox worker’s fenced persistence. It carries the sealed evidence label, score and opaque package reference; it never recomputes evidence or infers it from reply text. `wa_finalize` remains free of DB writes.
   >
   > This is a narrow exception to the `wa_codex_leg.py` prohibition. #5337 remains suspended and its veto logic untouched. These lanes share a file and must be serialized; reopening #5337 requires a fresh base after this change.
   >
   > Persist telemetry under the existing outbox ID, claim token and expected-status fence. Test retries, stale claims, takeovers, failed sends and discarded completions. Unscored/scripted routes retain NULL evidence rather than manufacturing scores.

7. **BLOCKER — The migration directory is wrong, and migration-plus-writer deployment has a missing-column interval.**

   **Evidence:** B2:34 names `backend/db/migrations/`. The runner discovers `migrations_v2` at `db/migration_manager.py:311–322`; `.github/workflows/migration-lint.yml:104` selects that directory for Squawk.

   `.github/workflows/fly-deploy.yml:262–282` explicitly states that pre-deploy migration runs use the **previous image**; new SQL is applied after the new image starts. A writer shipped alongside its migration can encounter absent columns.

   B2:66’s “migration down + revert” also conflicts with `AUTONOMOUS_OPS.md:163` on preserving applied migration files and could remove columns while their writer remains active.

   **Exact edit — B2 §2, §3, §4 and §7:**

   > Split B2.3 into B2.3a, schema only, and B2.3b, telemetry carrier/writer. Use `apps/backend-rag/backend/db/migrations_v2/NNN_wa_outbox_evidence.sql`, with forward SQL above `-- === ROLLBACK ===`. Add nullable columns without defaults or backfill. Select the number against fresh main and active migration PRs; do not reserve a number from this review.
   >
   > Require migration-number lint, Squawk, green `backend.db.migrate apply-all --dry-run`, and isolated up/down/up validation. B2.3b opens only after B2.3a’s fresh-image migration job and schema probe pass.
   >
   > Normal rollback retires the writer and retains nullable columns and applied migration history. Production schema down is a separately authorized destructive operation after dependent writers are drained.

8. **BLOCKER — D6’s Bites passes with a completely dead writer, and “abstained” has two meanings.**

   **Evidence:** B2:49 checks column presence and unchanged total row count. Both pass if no telemetry is ever written. A live total count may also change legitimately during deployment.

   The corner at `.agents/skills/bot/SKILL.md:1527–1537` records a timestamp precedent for **what kind of reply was sent**. README D6 instead describes the frozen evidence decision. These differ for a cautioned answer carrying `abstain=true`.

   The worker’s terminal write is fenced at `wa_outbox_worker.py:1378–1398`; submission status is distinct from subsequent delivery receipts at `:1399–1401`.

   **Exact edit — README D6 and B2.3 acceptance:**

   > Define `abstained_at` as the successful-send timestamp for a generated reply whose frozen evidence label was true; it does not mean a refusal stub was delivered. `evidence_score` is the same package’s frozen score. Record final disposition separately in B3.
   >
   > Schema readiness verifies exact types, nullability, defaults and runner application. Check preservation of a fixed pre-migration cohort, not equality of a changing live total.
   >
   > Writer acceptance uses the production carrier and fenced worker persistence with an isolated DB and stubbed sender, asserting both generated outcomes and failure/stale/unscored paths. B2 is then ready for B3; live telemetry remains unproven.
   >
   > B3’s first authorized supported and abstained cases correlate persisted fields with their sealed package references, terminal status, actual delivery acknowledgement and tester content verdict. No production send is added to B2 as a probe.

   **Also replace B1.3’s Bites:**

   > Consumer = the reporting harness shipped in B1.3; observation = its report on this head, including every required denominator, fixture hash and baseline result. B2 is its downstream user.

9. **BLOCKER — B2.2’s “read-only live retriever” is not guaranteed to respect its bans.**

   **Evidence:** `search_service.py:488–506` prepares query embeddings; `core/embeddings.py:394–405` invokes the embeddings client on a miss. The hybrid path writes cache results at `search_service.py:1187–1190`, and fallback paths can invoke further search processing. Synthetic questions do not guarantee that retrieved documents contain no client information.

   B1:41 forbids embedding calls and production writes; B2 inherits those prohibitions. Calling the production retriever is not automatically a read-only, zero-spend action.

   **Exact edit — B2.2:**

   > Execute the sample through a documented, tested no-send/no-generation retrieval harness. Use approved retained synthetic query vectors and read-only retrieval, with query expansion, embedding calls, paid reranking, cache writes and network fallbacks disabled. Abort on a missing vector rather than silently invoking a provider. Inspect the call graph before execution.
   >
   > Synthetic inputs do not authorize exporting retrieved client content. Persist only synthetic fixtures or approved redacted aggregates and opaque references. If new paid calls are required, stop this sample and present the exact provider, count and cost for explicit authorization; the withdrawn embedding allowance is not reused.

10. **MEDIUM — RC2/RC3 are file-disjoint, but their runtime effects are dependencies of B2 and B3.**

**Evidence:** README:48 allows parallel RC2/RC3 work, while B2.2 samples live retrieval without requiring RC2’s deletion/re-ingest completion. Its measurements could therefore describe a corpus different from B3’s. README:50 equates merging backend paths with deployed readiness; it does not require successful migration/data-operation receipts.

**Exact edit — README sequencing and sibling table:**

> B1 may proceed alongside RC2/RC3 within the corrected file perimeter. Before B2.2 samples production, record RC2’s completed data-operation receipt and the collection/version state measured. Before B3, require RC2’s actual deletion/detector verification, RC3’s deployed prompt-content verification, B2’s deployed consumer content and successful schema application. Merge status alone satisfies none of these runtime observations.
>
> B1 consumes and acknowledges dux-rc1a’s pinned formatter table before freezing its contract. Any difference is reconciled explicitly.
>
> The Fable window owns the final corner update. Its close checklist includes the corrected score contract, active/completed lane states, telemetry semantics, B3 result or pending status, and superseded historical claims.

11. **BLOCKER — The stated Gear-3 council can fail both doctrine and executable R9.**

**Evidence:** B2:50 permits “Codex + Kimi or GLM,” only for B2.1. Canonical `.claude/skills/modus/SKILL.md:207–218` specifies Gemini constructive, Codex red-team and Kimi refuter, followed by the independent final gate.

Current `scripts/evidence_pack_lint.py:2789–2793,2844–2868` counts qualifying journal seats from:

```text
codex-gpt-5.6-sol
kimi-code/k3
tp1-qwen3.8-max
```

Executing its current functions produced `GLM_COUNTS False` and `MIGRATION_FLOOR 3`. Thus the migration PR requires its own Gear-3 evidence.

**Exact edit — B2 council, team and budget clauses:**

> Every Gear-3 PR carries its own candidate-bound council evidence. Dispatch the canonical Gemini/Codex/Kimi panel; dispose findings before the fresh Opus gate reads the candidate and all reviews. Codex and Kimi supply R9’s qualifying seats; GLM does not count. Reserve GLM for the external build lane so panel reviewers remain outside the contribution chain.
>
> Record real review outcomes through `scripts/council_journal.py`; qualifying records contain `role=review`, `ok=true` and a timestamp. `council_run` resolves inside that PR’s evidence pack. Check the journal and complete evidence lint before arming. The final gate is sequential and never counted as a council member.

**Additional edit — B1 §5:** change the optional external-builder lane to a mandatory bounded assignment, as required for multi-PR campaigns by `army-map.md:108`.

12. **MEDIUM — Several historical citations and counts are wrong or insufficiently attributed.**

**Evidence and exact replacements:**

**README:14:**

> The cured #5618 evidence brief records 122 passed / 2 xfailed. The current cross-language file contains 124 parameterized cases, including two strict xfails; 53 passed / 2 xfailed was an intermediate result. Historical execution is not a fresh run on this window’s base.

The two cited tests do exist:

- `test_a_question_naming_no_identifier_is_still_language_blind`, line 241.
- `test_one_generic_word_should_not_be_evidence`, line 260.

**README:17:**

> The mandate coordinator recorded 341 passed / 2 xfailed in 8.54 seconds and reproduced the residuals with `--runxfail`: 2 failed, 122 deselected. The recorded baseline was `be45266252f4e1ccbaf19d2b81c73f03af676e05`. Astra’s read-only child inspected the pipeline and issued the BLOCKER; it ran no tests.

That is the attribution in the [addendum:164–168](/Users/nuzantara/nuzantara/.worktrees/backend-rag-bot-cycle-359-360/research/operations/2026-09-11-bot-cycle-359-360-revalidation.md:164).

**README:74; B1:49; B2:30,47:**

> Preserve two distinct corpora: #5337’s historical eleven-sentence veto measurement—nine compliant answers and two genuine splits—and #5615’s checked-in ingest-detector fixtures—nine offenders, four no-figure compliant exemplars and three texts without government-fee mentions, plus review-marker cases. The historical population of 27 compliant rows is not 27 checked-in fixtures.

`test_curated_qa_government_fee_gate.py:26–112,142–143` and its introducing commit establish that distinction. Fee-policy compliance must be reported separately from factual sufficiency; an offender text is not automatically an insufficient-context negative.

Locally verified commit identities are #5618 `2cd3cf84b8b602afbc508c19fba8aafca9766ed5`, #5615 `580b107a817f9dcd3e2d4dc3680ba5ef642f9aef`, and #5613 `99207591bf83899283088dc8ac0ebfffc7c73620`. The formatter table matches the addendum. Current GitHub state/merge timestamps and production counts/container content were not independently verified here; the GitHub lookup failed to connect.

**Add to README’s production paragraph:**

> These production observations are Fable’s dated measurements, linked to their receipt. Absence of recorded outbox rows is not independently verified absence of all inbound traffic or all channel activity.

13. **MEDIUM — Budget enforcement was omitted, although checkpoint delivery was inherited correctly.**

**Evidence:** B1:72–75 and B2:58–61 declare budgets without shared deadline storage, continuation-hop limits or adapter ceilings required by `.claude/skills/modus/battle-window-spec.md:43–48`. The S2 template already carries the corrected `infra/codex-hooks/mandate_budget.py` mechanism.

**Exact edit — B1 §6, inherited by B2 with its six-hour budget:**

> Record one absolute root-mandate deadline through `infra/codex-hooks/mandate_budget.py`. Children and continuations inherit remaining time; renewal does not reset attempts or reservations. Declare continuation hops and adapter tool ceiling at opening. Ship reserve is zero. A capped child checkpoints and returns.

**Add to the ledger-only PR acceptance:**

> `Bites:` consumer = `scripts/pending_arms_report.py`; observation = its `--json --ref origin/main` output containing the new rows after merge.

No missing-ack finding: README:67 imports the complete publication, sender-owned wake-up, same-envelope acknowledgement, fifteen-minute deadline and one-retry procedure.

14. **MEDIUM — The migration is incorrectly put on Zero’s merge queue; technical approval remains with the two imperators.**

**Evidence:** B2:42 and README:43 classify every migration as operator-merge. `AUTONOMOUS_OPS.md:82–90,161–164` reserves migrations **without a green dry-run** as an operator exception. A qualifying additive migration is released by the BLUE Dux.

`army-map.md:98–99` requires both imperator approvals on the same packet hash. This REWORK reading does not approve v1 or future corrected bytes.

**Exact edit — README operator items and Zero’s queue; B2 §3:**

> The BLUE Dux releases the additive migration after its green dry-run and independent gate. It creates no routine Zero merge item; missing prerequisites suspend release.
>
> Zero’s remaining decisions are authorized B3 identities/thread, send window, latency/stop conditions, any requested cadence change, #5337’s priority, and the commercial future of the bot. The existing cadence limit remains binding unless explicitly changed. Do not re-request the four decisions already ruled.
>
> If the design proposes reversing the existing ruled cautioned-answer delivery behavior, submit that exact behavioral change as a separate decision. Score kinds, fixture coverage and migration numbering are technical work.
>
> D1–D7 are proposed technical decisions pending corrected-packet approval by both imperators. Astra’s round-1 status is READ / REWORK, not APPROVED.

The BLUE Opus Dux, fresh Opus gate, top-level gate commissioning, separate push/create/arm commands, bare `gh pr merge --auto`, armed-branch freeze and append-only `merge=union` ledger procedure are otherwise sound. A subagent Dux still requires the level above to commission its gate.

**ASTRA’S OWN ADDITIONS**

Replace B2’s queued B3 paragraph with an explicit acceptance contract carried forward from the addendum:137–160:

> B3 preserves distinct authorized client and team identities and uses synthetic content only. Its mandatory matrix covers:
>
> - Supported client answers versus missing-support abstention/handoff; one all-inclusive PricingTool price without fee splitting.
> - Operational bank/document questions without invented legal citations, paired with substantive legal questions that retain grounded citations.
> - Bare greetings without retries; greeting-plus-question through normal answering; explicit human requests without being swallowed by greeting handling.
> - Team status/task/handoff assistance without sales copy, unsupported CRM claims or cross-client disclosure.
> - DLP and finalization protections across both audiences.
>
> Every case records opaque case/package references, audience, language, runtime code reference, scripted/generated/unclassified route, frozen evidence decision, final disposition, latency, terminal status, delivery acknowledgement and tester content verdict. No phones, raw chat or reversible identity maps enter the artifact.
>
> Delivery is necessary but insufficient: package/API success is not WhatsApp delivery, and delivery alone does not establish correct content. A safe abstention must reach a terminal action rather than disappear into retry/park. A partial battery remains partial; passing the fixed battery is not a zero-error production claim.
>
> Stop on unsupported substantive advice, fee-split leakage, wrong audience, PII exposure or broken delivery. Follow the authorized cadence; no repeated automatic probes.

The formatter observation also needs to remain explicit: an unboosted raw zero becomes **0.5**, and the current penalty uses **strictly `< 0.5`**, so it does not fire there. Fixing provenance is necessary; it does not by itself repair that scoring behavior.

This reading binds to these v1 SHA-256 values:

```text
README.md    757d1824d9e192f026664a7b673c8cc146aa2deb273fef232d298e31b0e98df2
B1-design.md e03872fe437b0e5dc64c085e36ebc0b87392da4502bf574e7f5f8d96de78b6ee
B2-engine.md 1a9754d738aa6af92f68d16f640d4ddd4c288583fb36ce6b6f0d6ec9e2b41bc9
```
