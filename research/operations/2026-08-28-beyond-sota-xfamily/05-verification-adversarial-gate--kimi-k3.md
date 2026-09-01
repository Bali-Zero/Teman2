---
panel: beyond-sota-xfamily
lane: 05-verification-adversarial-gate
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T18:48:44Z
finished: 2026-08-28T18:58:58Z
duration_s: 614
exit: 0
words: 3994
prompt_sha256_16: 1c4de0b61771db2e
prompt_chars: 18668
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• I'll ground myself in the repo first, then survey SOTA, then write the report. Starting with the core verification files.

• Now measuring guard coverage and the verification CI workflows.

• The scar-gate manifest shows 2/66 armed — a major finding. Now let me parse the guard-conformance registry correctly and check the CI workflows.

• I have all the grounding I need. Note on protocol adaptation: this snapshot is read-only and the brief instructs me to return the report as my final message instead of writing the file — so the `ls -la`/`wc -w` post-write probe does not apply; nothing was written. All `$MEM`/`MEM:` memory files are **unavailable** (outside the snapshot); I used the repo's own scar/ledger copies instead and flag every place where that mattered.

  ---

  ```
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 5/13 — Verification, adversarial review & final gate
  model: Moonshot Kimi K3 (pinned lane)
  sources: 15
  repo_files_verified: 33
  ---
  ```

  # Lane 5 — Verification, adversarial review & the final gate

  ## 0. TL;DR

  Nuzantara's verification architecture is **structurally ahead of anything surveyed** in one dimension — it treats *verification artifacts themselves* as the primary attack surface (guards need guilt+innocence proofs, canaries get linted for tautology, the verifiers get verified) — while remaining **behind SOTA in judge science**: no position-swap, no self-enhancement measurement, no preregistration, and a disabled CI AI-review that delivered literally zero comments in its last 100 runs. Biggest measured gap: the scar-gate manifest arms **2 of 66** failure-regression gates; 64 measured diseases are defended by prose. Top-3 moves: (1) arm the scar gates — a 30-day campaign, not a design task; (2) make refuter dispatch run against immutable `git archive` snapshots with seat-parentage + inter-rater logging in the evidence pack (the W100/W113/torn-read line, mechanized); (3) build a judge-bias calibration probe so the flat-sub fleet's graders are *measured*, not trusted. Everything here is buildable inside the hard rules: no paid API, CLI-only, Fable nowhere.

  ## 1. How Nuzantara does it today

  **The doctrine stack.** The core principle is written into an executable artifact: `infra/workflows/verify-template.js:18-21` — "judging < generating… A finding survives ONLY if an INDEPENDENT grader on FRESH context could not refute it." The workflow gathers N angled findings with a structured schema (`claim`, `evidence`, `source` must be "real URL/file:line you actually checked, or INFERENCE", `confidence` enum at `verify-template.js:69-97`), then dispatches 1–5 skeptics per finding with **"Default to refuted=true when uncertain"** (`:138`) and majority-not-refuted survival (`:149`). This is calibrated adversariality, not consensus — the file header says so explicitly.

  **The final gate.** `.claude/skills/modus/SKILL.md` Gate taxonomy (§Arsenal) defines four distinct gates and the seats: final on-disk gate = **Opus 5 xhigh, all gears, no cascade, never delegated**; Gear-3 harness verdict gate = Opus 5 xhigh rotating AZ→A2→A3→A1; Gear-2 = Opus 5 + CI. `.claude/skills/final-gate-discipline/SKILL.md` operationalizes it: re-read the actual diff yourself, name reviewer parentage before citing consensus (scar W100 cited inline), and answer **five questions with a command run NOW** before saying "done" — who calls it, what doc describes it, what will expire, can the probe say yes, where does the work live (`SKILL.md:36-55`). `.claude/commands/verify.md` is the atomic version: never cite output from the context buffer, only from a tool call executed this turn.

  **Cross-family refuters.** `.claude/commands/codex-second-opinion.md` dispatches Codex CLI (GPT-5.5/5.6, xhigh, OAuth-only, `--sandbox read-only`) as the adversarial "spalla", with anti-pattern guards (empty diff → hard refuse; transcripts to disk; BLOCKER copies to `docs/codex-reviews/`). `docs/decisions/2026-05-03-codex-spalla-architecture.md` records why: PR #181 BLOCKER catch as the existence proof, DIY-over-plugin because the official path needs a paid API key. The modus council composition (SKILL.md §Council) fixes three heterogeneous seats: Gemini constructive / Codex red-team / Kimi K3 refuter, then a sequential Opus-5 gate that is "never concurrent with or counted among" the reviewers. `docs/runbooks/review-gate.md` adds an H24 Pro LaunchAgent posting a tri-LLM review *comment* on every `agent/*` PR — informational only, fail-closed on truncated diffs, W64-hardened quorum (`compute_outcome` only counts reviewers that actually ran).

  **Mechanized guard verification.** This is where the organism is genuinely unusual. `infra/guard-conformance/registry.json` censuses **14 guard surfaces / 38 guards; all 38 carry both a guilt test and an innocence test** (verified by parsing the JSON this session). `.github/workflows/guard-conformance.yml` makes it a **required check** ("Every guard proves guilt AND innocence" is in the live branch-protection context list, verified via `gh api` — 11 required contexts today). `hook-innocence-gate.yml` is the vaccine for the command hooks ("all 7 command-matching hooks shipped with ZERO innocence tests"). `verify-the-verifiers.yml` is the meta-gate: sha256-pinned, CODEOWNERS-guarded, isolated-runner so "the agent cannot disarm this from its local machine". `catC-canary-tautology-lint.yml` exists because a shipped canary was `if disarm in f"{disarm} python3 hook.py"` — a tautology reporting false ARMED. `p1s2-mutation-incremental.yml` runs AST-diff incremental mutation testing **with hidden canary mutants** so "the agent under test cannot game the mutation score". `infra/claude-hooks/guard_fuzz_harness.py` generates a combinatorial corpus of shell shapes (quotes, heredocs, ssh-wrapping) and checks both decision channels of a guard — proactive over/under-match discovery instead of "one more hand-written pair after each live false-block". `infra/claude-hooks/gate_coverage.py` instruments every PreToolUse gate's exit paths because command hooks **fail open** on timeout/crash. `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py` pins the two silent-corruption invariants (frontend lead-source ⊆ backend enum; the frozen embedding model). `scripts/evidence_pack_lint.py` (37 top-level defs) lints evidence packs: `check_dissent_nonempty_on_gear3`, `check_lanes_build_seat_diversity`, `check_pii_scan_clean`, `compute_floor` — the deterministic gear floor recomputed by CI (`harness-floor.yml`), so "il modello può solo alzare la classe, mai abbassarla". `infra/retracted-claims/registry.json` + lint fails CI if a retracted claim reappears. `scripts/tests/` holds 439 entries.

  **What died.** `.github/workflows/ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate`: sampled 10/100 runs, **every one failed identically** on a CI workspace-trust dialog ~4s in, reported green anyway (superscar #2), and posted **zero advisory comments on any sampled PR**. Disabled with the reason written into the filename — which is itself a verification practice.

  ## 2. Scars & ledger evidence

  The scar corpus is the most honest measurement of this area. Grep-verified this session:

  - **Superscar #6 — anti-hallucination blindness** (`.claude/rules/cicatrix-superscar.md:140`): the four-generation line W65→W90→W100→W113. W65 "even the refuter hallucinates"; W90 "even the ground truth ages" (a stale NotebookLM verifier "confirming" pre-resolution numbers); **W100: same-family blind agreement certified 7 FALSE-clean out of 8 — 54% of the lot** (`cicatrix-scars.md:760`), with the killer gotcha: "an IAA between same-family seats is a FALSE FRIEND metric; 0.923 Sonnet-vs-Sonnet measured transcription fidelity, not truth… never cite an IAA without declaring the seats' parentage"; **W113: "the sentence I write WHILE retracting is a new claim, and no adversarial round looks at it"** — corrections are scrutinized *less* than originals.
  - **Superscar #3 — guard over/under-match** (`cicatrix-superscar.md:103`): W83/W84/W85/W91/W92 on one hook; W94 (under-match *born from an over-match cure*); W95 (the anti-reward-hacking linter over-matching a fixture named `test_client`, blind to `async def`); W116 (cure was dead code on the only path it existed for; the cure-of-the-cure nearly summed two defects to zero).
  - **W120** (`cicatrix-scars.md:1166`): the sentinel for family #2 was itself unarmed — `class` vs `classification` key drift made the overdue-alarm branch dead code, "an alarm that doesn't ring is indistinguishable from a healthy world", atop a ledger carrying 280 tech-debt overdue. **W121**: mutation testing ran on poisoned bytecode — the instrument judging whether the corpus bites was judging different bytes than the disk.
  - **AMENDMENTS** (`.claude/skills/modus/AMENDMENTS.md`) — the loop's own misfire log: a refuter approved a half-false pricing claim caught only by gate re-fetch (2026-07-02); verify lanes returned **literal placeholder verdicts ("test", "PENDING") that passed the schema because verdict was typed as string** (2026-07-19); a refuter pointed at a **live worktree returned a fabricated CRITICAL finding from a torn read** (2026-08-23); auto-merge armed at PR-open raced the refuter and the unjudged diff entered the merge queue (2026-08-01); grader output consumed through `| tail -70` silently cut the two most severe findings (2026-07-16).
  - **PENDING-ARMS** grep rows: a "published but NOT REQUIRED" harness gate caught only because "the orchestrator happened to re-read branch protection… i.e. by attention, which is exactly what the mechanization was meant to replace" (resolved by the 2026-08-21 redesign — "Harness floor recompute" is now a required context); an advisory fullstack smoke that has *never been green*, 13 fail/17 skip/0 success, because "advisory means nothing blocks and nobody looks".
  - **Re-measured correction statistic**: the 2026-08-22 AMENDMENTS entry measured 27/200 commits correcting a previous commit's claim (20–22/8). My re-measurement: `git log --since="14 days ago"` = 859 commits; a subject-line heuristic (correct/fix-of-fix/re-measure/retro/false-premise patterns) finds **39/859 ≈ 4.5%** — with exemplars like "the tripwire guarded the wrong enum" (#5173), "correct Q0's false premise" (#5041), "a refuter claim I accepted without measuring is false, and it is in a comment on main" (#4880). Heuristic stated, so the two numbers aren't comparable directly; the *shape* (a persistent correction-of-correction class) is confirmed either way.
  - **Scar-gate arming: 2/66** (`infra/scar-gates/MANIFEST.json`: `armed: 2`, `prose_only_debt: 64`). The antidote architecture exists; the antidote is mostly unwritten.
  - `$MEM` items the brief lists (MEMORY_VERIFICATION_RULES.md's 43 rules, five lesson files) live in the operator's home memory dir — outside this snapshot, **unavailable to me**. The repo-side equivalents I did verify (verify.md, final-gate-discipline, the scar line) cover the same doctrine; the exact 43-rule corpus I cannot cite.

  ## 3. World SOTA survey

  | System/practice | Source (date) | Mechanism | Measured effect | Transfer here |
  |---|---|---|---|---|
  | LLM-as-judge bias taxonomy | [Zheng et al., NeurIPS 2023](https://arxiv.org/abs/2306.05685) | position/verbosity/self-enhancement bias; swap-and-average calibration | GPT-4 judge >80% human agreement | Direct: Nuzantara has family-exclusion but no position-swap or self-preference measurement |
  | Fair evaluators / position calibration | [Wang et al. 2023](https://arxiv.org/abs/2305.17926) | balanced position calibration, multiple-evidence calibration | ranking flips purely by reordering | Direct for council verdicts |
  | Reward tampering curriculum | [Denison et al. (Anthropic) 2024](https://arxiv.org/abs/2406.10162) | training on gameable envs generalizes to test-editing, reward-overwriting | tampering persists after sycophancy training (4/100k) | Partial: no training here, but justifies hidden canary mutants + CoT-free guards |
  | CoT monitoring for misbehavior | [Baker et al. (OpenAI) 2025](https://arxiv.org/abs/2503.11926) | monitor reasoning traces for reward hacking; training against monitor → obfuscation | monitor catches hacks; penalizing CoT hides intent | Limited: CLI-only fleet can't train, but "never let the grader's own output be optimized against" transfers |
  | Mutation testing at Google | [Petrović et al., TSE 2022](https://arxiv.org/pdf/2102.11378) | diff-scoped mutants in code review, developer-feedback loop, mutant suppression | deployed to 1000s of devs; ~24M mutants | Direct: p1s2 gate is this, diff-scoped; Nuzantara adds hidden canaries (Google doesn't publish that) |
  | TestGen-LLM | [Alshahwan et al. (Meta) 2024](https://arxiv.org/abs/2402.09171) | LLM test improvement with build/pass/coverage filters before human review | 73% of improvements accepted; 75% of classes got valid cases | Direct: no equivalent here; tripwires are hand-written |
  | CriticGPT | [McAleese et al. (OpenAI) 2024](https://arxiv.org/abs/2407.00215) | RLHF-trained critic on bug-seeded code; human+critic teams | critics catch more bugs than humans in 63%; teams beat either alone | Partial: same-family critic — Nuzantara's cross-family rule is stronger on bias, weaker on specialization |
  | AWS Zelkova / Automated Reasoning | [AWS GA announcement, Aug 2025](https://aws-news.com/article/2025-08-06-minimize-ai-hallucinations-and-deliver-up-to-99-verification-accuracy-with-automated-reasoning-checks-now-available) | translate policy+output to SMT, prove validity | ~1B SMT calls/day (CAV 2022); "up to 99%" verification accuracy | Partial: heavy; but policy-as-SMT maps to guard guilt/innocence formalization |
  | SWE-bench Verified | [OpenAI 2024, via Epoch AI](https://epoch.ai/benchmarks/swe-bench-verified) | human-validated 500-sample subset; hidden FAIL_TO_PASS tests | industry-standard agent grading | Direct as *method*: hidden tests the agent can't see = Nuzantara's canary mutants |
  | Cursor Bugbot learned rules | [Cursor blog, Apr 2026](https://cursor.com/blog/bugbot-learning) | review→developer-reaction feedback loop generates rules | resolution rate 52%→78.13% over 50,310 PRs; next-best 63% | Direct: Nuzantara has the scar corpus (a richer feedback signal) but no per-gate learning loop |
  | Agentic PR-review field | [Greptile benchmarks, Jul 2025](https://www.greptile.com/benchmarks) (self-reported) | full-repo context review | 82%/58%/44% catch (Greptile/Bugbot/CodeRabbit) — vendor numbers, unfalsifiable recall | Context: the disabled ai-pr-review action was this class, delivered 0 |
  | Independent FP measurement | [Signal65, Mar 2026](https://signal65.com/wp-content/uploads/2026/03/Signal65-Insights_Evaluating-AI-Code-Review-Tools.pdf) | third-party false-positive counting | Bugbot 3 FP vs Copilot 41 FP on same PRs | Direct: Nuzantara already distrusts vendor green; this is the measurement discipline to copy |
  | Google Critique / code review | [SWE Book ch.19](https://abseil.io/resources/swe-book/html/ch19.html) | human review mandatory, ML-suggested edits, readability tiers | 97% dev satisfaction (secondary) | Partial: solo owner *does not review code* — the entire Nuzantara design replaces this row |
  | AI safety via debate | [Irving et al. 2018](https://arxiv.org/abs/1805.00899) + Khan et al. 2024 | adversarial debate before a judge; debate helps *unreliable* judges | debate > consultancy for weak judges | Direct: verify-template is debate-ish but skeptics don't see each other; no preregistered protocol |
  | OSS-Fuzz | [github.com/google/oss-fuzz](https://github.com/google/oss-fuzz) | continuous fuzzing as a service, 1,000+ projects | tens of thousands of bugs found | Partial: guard_fuzz_harness is this idea at guard-scope — already ahead in targeting |

  The five that matter most. **(1) Zheng/Wang judge science** — the only surveyed discipline Nuzantara clearly lacks: its graders are never debiased or calibrated, and W100 is the empirical proof that this bites. **(2) Google's mutation-at-scale** — proves diff-scoped mutation in review is industrial-strength; Nuzantara's hidden-canary variant is a genuine delta. **(3) Bugbot's learning loop** — the mechanism that matters is not the model, it's converting review outcomes into rules; Nuzantara's scar corpus is the same idea at organizational scale but with 2/66 arming, the loop is open. **(4) Baker's CoT monitoring** — the transferable insight is negative: any signal you optimize against stops being a signal; Nuzantara's "canary the agent cannot see" is the right counter. **(5) AWS automated reasoning** — shows the ceiling when verification is proof rather than test; aspirational, low transfer at this scale.

  ## 4. Position vs SOTA

  | Sub-dimension | Position | Evidence |
  |---|---|---|
  | Generator≠grader doctrine, cross-family exclusion | **AHEAD** | verify-template.js + council composition + W100 parentage rule; no surveyed system enforces family-diverse grading org-wide |
  | Guard conformance (guilt+innocence per guard) | **AHEAD** | 38/38 guards dual-proven, required CI check; nothing surveyed has this census |
  | Meta-verification (verify the verifiers, canary tautology lint, sha256 meta-gate) | **AHEAD** | verify-the-verifiers.yml + catC workflow; quis-custodiet answered by immutability |
  | Mutation testing | **AT/AHEAD** | p1s2 incremental + hidden canary mutants ≈ Google's diff-scoped practice plus anti-gaming |
  | Judge calibration (position-swap, self-enhancement, preregistration) | **BEHIND** | no swap, no bias telemetry, verdict protocols not preregistered (W100, AMENDMENTS 2026-07-19 placeholders) |
  | AI PR review in CI | **BEHIND** | action disabled after measured zero value; SOTA is Bugbot's 78% resolution loop |
  | Test generation automation | **BEHIND** | no TestGen-LLM analog; tripwires are manual |
  | Formal methods | **BEHIND** | nothing SMT/property-based at Zelkova class |
  | Reward-hacking detection | **AT** | anti-reward-hacking linter exists (W95) but itself hit over-match; no trace monitoring (impossible CLI-only, and Baker says don't optimize against it anyway) |
  | Failure-history-as-verification-asset (scar corpus → gates) | **AHEAD in design, BEHIND in arming** | MANIFEST.json: 2/66 armed |

  ## 5. Beyond-SOTA recommendations

  **R1 — Arm the scar gates: 66 measured diseases → executable regression gates.**
  What: a 30-day campaign writing `infra/scar-gates/test_W*.py` for the top ~30 scars by recidiva (families #2, #3, #6 first), most of which already have a probe somewhere in the corpus. Why beyond-SOTA: nobody — not Google, not Bugbot — has an organizational failure corpus mechanically converted into a regression suite; Google's mutation loop learns from developer reactions, this learns from *autopsies*. The asymmetry is the scar corpus itself (296 KB of measured failures). Cost: flat-sub tokens only, ~2 grader dispatches per gate; gear 2. Risk: family #3 (a gate that over/under-matches the disease it pins) — mitigated because guard-conformance already forces guilt+innocence on each. Metric: `prose_only_debt` 64 → ≤34 in 30 days; recurrence count of armed-family scars per 30d → 0. Kill: if armed gates flake >5% of runs (they become noise, W69-class). First PR: arm 5 gates (W82-style, reusing existing tripwire tests) + MANIFEST flips, ≤200 lines.

  **R2 — Immutable-snapshot refuter dispatch with seat-parentage and IAA logging.**
  What: a `scripts/refuter_dispatch.sh` that does `git archive <sha>` into a scratch dir (the AMENDMENTS 2026-08-23 proposal, unbuilt), plus two evidence-pack fields enforced by `evidence_pack_lint.py`: `refuter_snapshot_sha` and a `seat_lineage` block; persist every grader verdict to a JSONL so inter-rater agreement *by family pair* becomes a computed number (W100's "never cite IAA without parentage" made a metric). Why beyond-SOTA: CriticGPT, Bugbot, Greptile all grade with one model family and none publish judge-agreement telemetry; Zheng et al. show agreement-without-parentage is a false friend. Metric: torn-read/fabricated refuter findings per month (baseline: audit last 10 refuter runs; AMENDMENTS shows ≥2 recent); IAA-by-family-pair published per Gear-3 run. Cost: ~150-line script + linter checks; gear 2. Risk: #9 (a frozen SHA that drifts from what merged — mitigated: CI recomputes the floor on the real diff anyway). Kill: if snapshot dispatch adds >10 min p50 latency.

  **R3 — Correction-channel adversarial pass (the W113 cure).**
  What: for commits whose subject/body claims a correction, a lint extracts the *added* natural-language claims and routes the diff through the existing R1 adversarial gate — closing the hole where "the sentence written while retracting" gets zero scrutiny. Why beyond-SOTA: no surveyed system treats corrections as a distinct risk class; the retracted-claims registry is the foundation nobody else has. Metric: correction-of-correction rate (13.5% measured 20–22/8; ~4.5% by my looser 14-day heuristic) → <2%. Cost: gear 2, ~250 lines. Risk: #2 (a lint that runs but nobody reads) — must be a required-context sentinel, not advisory; the never-green advisory smoke in PENDING-ARMS is the cautionary row. Kill: if it false-blocks >10% of correction PRs in the first 2 weeks, demote to warn-only and recalibrate.

  **R4 — Judge-bias calibration probe for the fleet.**
  What: a monthly `scripts/judge_bias_probe.py`: each grading seat scores an anonymized, position-swapped battery of historical verdicts (some authored by itself). Outputs per-seat position-bias and self-enhancement deltas, appended to MODEL_ROSTER.md. Why beyond-SOTA: Zheng/Wang published the biases; no engineering org *continuously measures its own graders'* biases — and the flat-sub fleet makes this free at the margin. Metric: position-swap flip rate and self-preference delta per seat, trend over 90 days; council seats with flip rate >20% get rotated out of solo-verdict roles. Cost: flat-sub tokens, one cron; gear 2. Risk: #6 (probe battery itself hallucinated — every item must be a historical verdict with a known-true resolution). Kill: if two consecutive months show all deltas <5%, run quarterly.

  **R5 — Scar-derived mutation operators.**
  What: extend `p1s2-mutation-incremental`'s mutant generator with operators *mined from the scar corpus* — each armed scar becomes a mutant that reintroduces its disease (swap `class`→`classification` per W120, strip a `!=` per W94, drop the `--union` flag per the 2026-08-23 row). Why beyond-SOTA: mutation testing worldwide uses generic operators; failure-history-guided operators aim the fuzzer at the shapes that *actually* kill this organism. Metric: scar-mutant kill rate of the current suite (expect uncomfortable numbers on first run — that discomfort is the product); suite improvement tracked as kill-rate delta per PR touching hot zones. Cost: gear 3 design, gear 2 build; ~400 lines. Risk: #1 (mutation driver environment drift — W121 says the instrument itself can be poisoned; keep the bytecode-freshness check). Kill: if scar-mutants are 100% killed on arrival for 3 consecutive monthly batches, the suite has caught up — declare victory and bank it.

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 1–30) — close the measured holes.** R1 first tranche (5→15 gates armed); R2 script + linter fields; R4 probe first run (baseline numbers). First PRs: (a) "Arm 5 scar gates (family #2/#6)" — `infra/scar-gates/test_W*.py`, `MANIFEST.json` — gear 2, acceptance: `verify_the_verifiers.py` runs all 5 green and CI check stays required; (b) "Refuter immutable-snapshot dispatch" — `scripts/refuter_dispatch.sh` + modus SKILL.md clause — gear 2, acceptance: a refuter dispatched against a SHA cannot see working-tree bytes (prove with a sentinel edit); (c) "Seat lineage + IAA log in evidence packs" — `scripts/evidence_pack_lint.py`, pack schema — gear 2, acceptance: a Gear-3 pack lacking `seat_lineage` fails lint.

  **Wave 2 (days 31–60) — R3 correction gate + R1 to ≤34 prose debt; R4 first trend report.** First PR: "Correction-claim adversarial lint" — `scripts/lint_correction_claims.py` + sentinel workflow — gear 2, acceptance: a fixture commit with a false correction claim goes red, an honest one goes green (guilt+innocence, by the repo's own rule).

  **Wave 3 (days 61–90) — R5 scar-mutants pilot on the two hottest suites (hooks + guardrails); decide R1 completion (66/66) by measured flake budget.** First PR: "Scar-derived mutants for hook surfaces" — `scripts/mutation_incremental.py` operator pack — gear 3, acceptance: ≥1 scar-mutant survives the current suite (proving the operators find real holes) or a documented zero-survivor report with the suite diff that earned it.

  ## 7. Needs-ruling

  Only one true business decision: **re-enabling CI AI PR review.** The disabled action's fix is mechanical (write `hasTrustDialogAccepted` into the runner's `.claude.json`, then pin the model), but it spends GitHub Actions minutes and an OAuth window on every qualifying PR (~80 runs/day previously) — that is a token/spend trade-off under CLAUDE.md §5 and Zero's 2026-08-20 token-cuts posture. Recommendation if approved: re-enable only on Gear-3 PRs, cross-family (Codex review in CI, not same-family), with R2's lineage fields so its verdicts join the IAA log. Any paid review SaaS (Greptile-class) is a non-starter under the flat-subscription rule — not tabled.

  ## 8. §Meta-pattern

  One defective belief generates nearly everything above: **"the artifact that names a verification is the verification."** Green-shaped is read as green: a published status context that isn't required (superscar #2; the harness-gate PENDING-ARMS row), a canary that returns ARMED by construction (catC tautology), a placeholder verdict that passes a string-typed schema (AMENDMENTS 2026-07-19), a `sensitive:` flag nothing reads, an alarm branch that can never fire (W120), an advisory check that was born red and nobody looks at. The second-order belief, subtler and more expensive, is that **scrutiny is allocated by novelty, not by risk**: original claims get rounds of adversarial review while corrections, retractions, and gate output itself sail through — W113 ("no adversarial round looks at the sentence that replaces"), the correction-of-correction statistic, and the refuter's own fabricated findings all live there. The organism's genuine edge — it has already *named* both diseases in its scar corpus — is exactly why R1–R3 are cheap: the diagnosis is done; what remains is arming.

  ## 9. Sources

  1. [Zheng et al., Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (NeurIPS 2023)](https://arxiv.org/abs/2306.05685) — accessed 2026-08-28 — the canonical LLM-judge bias taxonomy.
  2. [Wang et al., Large Language Models are not Fair Evaluators (2023)](https://arxiv.org/abs/2305.17926) — 2026-08-28 — position-swap calibration mechanism.
  3. [Denison et al. (Anthropic), Sycophancy to Subterfuge (2024)](https://arxiv.org/abs/2406.10162) — 2026-08-28 — primary evidence reward-gaming generalizes to test tampering.
  4. [Baker et al. (OpenAI), Monitoring Reasoning Models for Misbehavior (2025)](https://arxiv.org/abs/2503.11926) — 2026-08-28 — CoT monitoring and the obfuscation risk of optimizing against the monitor.
  5. [Petrović et al., Practical Mutation Testing at Scale — a View from Google (TSE 2022)](https://arxiv.org/pdf/2102.11378) — 2026-08-28 — industrial mutation testing reference.
  6. [Alshahwan et al. (Meta), TestGen-LLM (2024)](https://arxiv.org/abs/2402.09171) — 2026-08-28 — 73% acceptance, the measured bar for LLM test improvement.
  7. [McAleese et al. (OpenAI), LLM Critics Help Catch LLM Bugs / CriticGPT (2024)](https://arxiv.org/abs/2407.00215) — 2026-08-28 — critic beats human reviewers in 63% of comparisons.
  8. [AWS, Automated Reasoning checks GA (Aug 2025)](https://aws-news.com/article/2025-08-06-minimize-ai-hallucinations-and-deliver-up-to-99-verification-accuracy-with-automated-reasoning-checks-now-available) — 2026-08-28 — SMT-backed verification in production generative AI.
  9. [Epoch AI, SWE-bench Verified benchmark page](https://epoch.ai/benchmarks/swe-bench-verified) — 2026-08-28 — hidden-test grading methodology.
  10. [Cursor, Bugbot learned rules (Apr 2026)](https://cursor.com/blog/bugbot-learning) — 2026-08-28 — review-feedback learning loop, 78.13% resolution over 50,310 PRs.
  11. [Greptile AI Code Review Benchmarks (Jul 2025)](https://www.greptile.com/benchmarks) — 2026-08-28 — vendor catch-rate numbers, cited with self-report caveat.
  12. [Signal65, Evaluating AI Code Review Tools (Mar 2026)](https://signal65.com/wp-content/uploads/2026/03/Signal65-Insights_Evaluating-AI-Code-Review-Tools.pdf) — 2026-08-28 — rare independent false-positive measurement.
  13. [Google SWE Book, ch.19 Critique](https://abseil.io/resources/swe-book/html/ch19.html) — 2026-08-28 — primary description of Google's review tooling.
  14. [Irving et al., AI Safety via Debate (2018)](https://arxiv.org/abs/1805.00899) — 2026-08-28 — foundational adversarial-oversight framing.
  15. [google/oss-fuzz](https://github.com/google/oss-fuzz) — 2026-08-28 — continuous-fuzzing-as-infrastructure reference for the guard fuzz harness comparison.

  ---

  `status: complete` — sections 0–9 delivered. Caveats declared inline: the `$MEM` files (43 verification rules, five lesson memories) were outside this snapshot and are cited as unavailable, not summarized; the 14-day correction re-measure uses a stated subject-line heuristic and is not directly comparable to the 27/200 figure; Greptile catch rates are vendor-self-reported.

