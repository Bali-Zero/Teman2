---
date: 2026-08-28
domain: operations
part: 00 cross-part synthesis
scope: "Synthesis of the 16 Beyond-SOTA lane reports (B1-B9, F1-F4, X1-X3) — shared disease, consolidated P0s, genuine strengths, beyond-SOTA plays, Zero-only decisions"
sources: [the 16 lane reports in this directory]
status: DONE
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# Beyond-SOTA program — synthesis of 16 lanes

**Program:** Zero's 2026-08-28 mandate — partition the whole Nuzantara system into coherent parts,
one Fable 5 deep-research lane each: measure the anatomy, research the world's best in that sector,
recommend how to reach and then exceed SOTA. All 16 lanes completed across three quota windows
(~66,000 words, ~270 distinct sources, every anatomy claim file:line-anchored on `origin/main
@ 11a3c89a2e`). Lane verdicts are **LEADS, not facts** (W65/W100): re-probe on disk before building
on any recommendation.

---

## 1. The one shared disease

Fifteen of sixteen lanes independently converged on the same generating belief, each in its local
dialect: **"the written artifact is presumed in force"** — superscar family #2 (*esiste ≠ armato*)
operating at every scale of the organism, not just at cron level.

- **B1**: hybrid search + reranker fully implemented, flags off in prod — retrieval is dense-only.
- **B3**: "every organ measures itself; nothing measures the client" — breaker closed read as alive,
  answer written to ledger read as delivered.
- **B5**: "the organism ships emitters and calls them features" — token minted but no page exchanges
  it, preferences saved but never consulted, 503 checkout called a product.
- **B6**: askability is comment discipline, not a compiler invariant; truth-freshness gates declared
  in the OpenAPI contract, unimplemented.
- **B8**: DeepSeek retired in doctrine 2026-07-19 yet still a voting Consiglio seat in code.
- **B9**: 47k lines of evaluator with zero CI/cron wiring — "muscles without the mirror".
- **F1**: IndexNow route with zero callers; CWV beacons falling into a logger.
- **F2**: magic-link exchange endpoint with zero frontend callers — upload→checkout unreachable by
  construction while every half is individually green.
- **F3**: a ~1,000-line unified omnichannel inbox orphaned (no inbound links); an admin dashboard
  maintained toward a DNS-dead deploy target.
- **F4**: Sentry wiring conditional on a DSN env — a missing var silently ships zero observability;
  a 20% coverage gate presumed protective.
- **X1**: `test_auto_merge_whitelist.py` red 24/73 and executed by no workflow; doctrine says 27
  required contexts, the snapshot has 11.
- **X2**: Tailscale ACL PROPOSED-not-applied; 84% of plists grandfathered against their own genome.
- **X3**: the control plane (`~/.claude/hooks/`) unversioned — scar family #1 applied to the immune
  system itself.

**Structural cure (recurs across lanes):** consumer-boundary gates — a flow is *done* only when the
consuming end is exercised (B5's P0-2 CI gate "no route without a caller", B3's client-side outcome
telemetry, X1's enforce-or-quarantine, X2's pull-mode converger, B9/X3's armed eval harnesses). One
pattern, five lanes; build it once as a reusable gate family.

## 2. Consolidated P0s (deduplicated, ranked)

1. **⏰ Hard deadline — defuse the R9 staging bomb before 2026-09-02** (X1). `harness-floor.yml`
   stages only pack+brief into `/tmp/evidence-check/` while R9 resolves `council_run` against the
   pack dir → every Gear-3 PR fails the required check by construction from 2/9. Acceptance:
   fixture-PR pair (one that must pass, one that must fail).
2. **🔓 Security duo.** (a) The live tailnet is allow-all with an unauthenticated writable ttyd
   shell on Pro — apply `policy.hujson` + kill/credential ttyd (`operator[GUI]`, X2). (b) The auth
   split-brain: 13 non-test frontend gates trust localStorage `isAuthenticated()` while real auth is
   the httpOnly cookie (F2/F3/F4) — one cookie-backed session hook, grep-zero acceptance.
3. **💰 Revenue chain — three small PRs make the VOA funnel sellable** (F2/B5): land the magic-link
   consumer route (steps 3-6 are unreachable today), arm Xendit live mode with a webhook event
   ledger + reconciliation cron, instrument the money funnel with the already-parity-tested event
   taxonomy (today it emits zero `app_*` events while the free funnel is fully instrumented).
4. **🪞 Wire the measurement layer that already exists.** One golden-harness pattern, five
   consumers: retrieval golden set in CI (B1), `multi_turn_eval` nightly + merge gate (B9),
   golden-task harness for the operating loop itself (X3), client-side outcome telemetry (B3),
   DORA-5 + claim-correction rate (X1). The organism has built nearly all the measuring code; none
   of it runs on a schedule.
5. **📦 Arm what is built and off**: hybrid+rerank staged per collection against the golden set
   (B1); decide arm-or-archive for the dark `autonomous_lab` backend (B9, Zero call).
6. **👻 Purge ghosts and forks**: DeepSeek's Consiglio seat (B8), vendor WR3's 13 agents into the
   repo with lint_home_fork pairs (B8), version `~/.claude/hooks/` (X3), fix the X1 doctrine-drift
   numbers (97≠167 pairs, 27≠11 contexts).
7. **🛡️ Reliability probes**: nightly WAL-continuity probe + second non-Fly off-site backup
   provider + off-fleet dead-man's switch (B7/X2) — the exact probe class whose absence hid the
   dead WAL until 2026-08-09.
8. **🔍 SEO demand layer**: build the ~20 money-query pages GSC proves are unserved; one PR killing
   all fabricated signals (llms.txt drift, hreflang triple-same-URL, fabricated lastmod) with
   vitest guards (F1).

## 3. Genuinely ahead of industry (measured, not claimed)

- **Cicatrix institutional memory** (~130 scars → 10 CI-budgeted families, 6/10 executable
  antidotes) — no public peer found (X3).
- **Adversarial generator≠grader culture** with family-exclusion verification — stronger than the
  LLM-as-judge mitigation literature (X3, X1).
- **Ed25519/RFC-8785-signed, hash-chained, append-only rule packs** read from the DB (B6) — audit
  discipline unheard-of in small-firm legal-tech.
- **Monthly containerized restore drill** — "backups are restores" practiced, not preached (B7).
- **Fact-gate with per-claim provenance taxonomy + fail-closed publish ledger** (B8).
- **5-gate abstain policy SSOT + CRAG grading in the hot path** (B1).
- **tool_authorizer + fail-closed confirmation service** (B9); **87+87 error/loading boundaries +
  frontend-live-sentinel** (F4); **review queue with 15-min leases + dry-run transparency** (F3);
  **1,559-page provenance-gated KBLI SSG surface** (F1).

## 4. Beyond-SOTA plays (the moat moves)

1. **Review/pack provenance as a public asset**: sign Evidence Packs as sigstore attestations on
   merge commits (X1) + a public transparency log of rule-pack hashes (B6) — turns internal audit
   rigor into a sellable trust asset no competitor has.
2. **Regulatory-watcher → content freshness auto-PRs** (F1): the only organism with a licensed
   regulatory pipeline feeding a programmatic SEO surface.
3. **Error budgets that re-route the agent fleet** (B7) and **evidence-earned maturation** — cell
   lifecycle phases advance on green eval runs, not age (B9).
4. **Tokens-per-business-commit as a standing daily metric** (X3) — the 8.6M-tokens→10-commits
   autopsy became doctrine; make it a number on the scoreboard.
5. **Palette-as-agent-command-line + draft-first "Zantara risolve" inbox** (F3); **weekly GEO
   citation telemetry using the existing subscriptions** (F1).

## 5. §Solo-operatore — decisions reserved to Zero (consolidated)

Business calls, spend, and risk the lanes explicitly refused to decide:

1. ttyd shell kill/credential + tailnet ACL apply (`operator[GUI]`) — X2.
2. Xendit live key + callback token; fee-absorption cap on invoice links — B5/F2.
3. Magic-link landing page choice (product decision, guessed wrong once) — B5.
4. Prune/noindex the ~3,300 zero-demand scraper articles (scaled-content risk ruling) — F1.
5. Canonical-inbox ruling (5 implementations, none canonical) + admin-dashboard
   redeploy-or-archive + `/dream` fate — F3.
6. Prod flag-flips on live traffic (hybrid/rerank staging plan) + any reranker spend — B1.
7. `autonomous_lab` arm-or-archive; does an eval-red block the bot lane? — B9.
8. AI-involvement disclosure wording on published surfaces — B8.
9. localStorage-gate risk acceptance until the auth refactor lands — F3/F4.
10. Eval/observability attention budget (what the fleet reads daily vs weekly) — X3/B9.

## 6. Suggested first two weeks

Week 1: defuse R9 (before 2/9) · security duo (a: operator, b: session) · magic-link consumer.
Week 2: Xendit live + webhook ledger · one golden-harness pattern landed and reused (B1 retrieval +
B9 multi_turn_eval as first two consumers) · ghost purge (DeepSeek seat, WR3 vendoring).
Everything else follows the per-report P1/P2 order. Every verdict above: re-verify on disk first.

## Sources

The 16 lane reports in this directory (B1-B9, F1-F4, X1-X3), each with its own 12-28 external
sources; program spec in `00-MANDATE-AND-PARTITION.md`.
