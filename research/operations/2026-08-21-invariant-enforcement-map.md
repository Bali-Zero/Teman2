---
date: 2026-08-21
domain: compliance
client_case: none
adversarial_review: kimi-k3
sources:
  - research/operations/2026-08-21-world-patterns-import-map.md
  - CLAUDE.md (root, origin/main)
  - .claude/rules/cicatrix-superscar.md (origin/main)
  - .github/CODEOWNERS
  - .github/workflows/*.yml (97 workflow files + 2 non-workflow siblings, repo-inventoried)
  - `gh api repos/:owner/:repo/branches/main/protection` (live, this session)
discovered_by: session audit (world-practice import map lever #4, constraint pinning)
---

# Invariant enforcement map — which HARD rules are a hook/CI gate, and which are prose (2026-08-21)

**Mandate**: build lever #4 from `research/operations/2026-08-21-world-patterns-import-map.md`
§2.3 — that document cites a measured result (arXiv 2606.22528, cross-family): a governance rule
visible in context runs at 0% violations; the same rule, dropped from the summary by context
compaction, runs at 38%. This repo's own antidote is CLAUDE.md §7: "if a critical rule is
violable, write a hook — documentation does not suffice." The question this audit answers is
narrow and empirical: **for each HARD/NEVER/MANDATORY/absolute invariant this repo states in
prose, is there actually something outside the context window that would catch a violation** —
and if there is, does it **block a merge**, or does it just print a warning nobody is required to
read?

**Method**: every claim below was checked against a live artifact in this session — a script
read in full, a workflow's job name diffed against the live `required_status_checks.contexts`
pulled via `gh api` (not assumed from a filename), or a test actually executed. Per W107/W81
("existing ≠ armed", "the probe that measures a disease can have it"), a workflow that runs but
is not in that live required-contexts list is recorded as **advisory**, not enforced — it can be
red on `main` forever without blocking anything.

**Numbers**: **24 invariants** enumerated from CLAUDE.md (root) + `~/.claude/CLAUDE.md`.
**8 enforced-and-required** (a red run blocks merge) · **9 enforced-but-advisory-or-client-side**
(a real check exists and can fail, but either is not in branch-protection's required list so a red
run doesn't block anything, or is a `.husky/pre-commit` hook whose own remediation path — caught
live in this PR's own commit — is the exact `--no-verify` bypass Golden Rule #12 bans) · **6
enforced-nowhere** (nothing outside the prompt would catch a violation). One of the 24
(`alembic/env.py`) turned out to name a file that **does not exist anywhere in this repository** —
not a gap in enforcement, a phantom citation in the doctrine itself.

---

## §1 — The map

Legend: 🟢 enforced + required (blocks merge) · 🟡 enforced but advisory (can be red, doesn't
block) · 🔴 enforced nowhere · 👻 phantom (names something that doesn't exist)

| # | Invariant (source) | Status | Enforcement, cited |
|---|---|---|---|
| 1 | Anthropic SDK banned — no `ANTHROPIC_API_KEY`, no paid `Anthropic(api_key=...)` (CLAUDE.md §5) | 🟡 | `catE-sovereignty-lint.yml` — blocks NEW paid-constructor sites beyond the 3-site committed baseline (`catE-paid-anthropic-baseline.txt`) and bans `ANTHROPIC_API_KEY=<value>` assignment. **Confirmed absent from `required_status_checks.contexts`** (live `gh api` pull, this session) — the workflow's own header says so too: "NON-REQUIRED by design ... flip to required only after it proves stable". |
| 2 | No hardcoded secrets (Golden Rule #6) | 🟢 | `Detect Secrets` (required) + `test_golden_rule_6_no_hardcoded_secrets` in `apps/backend-rag/backend/tests/compliance/test_golden_rules.py`, collected by `backend/tests/` under the required `Backend Tests (Python)` job (`tests.yml:649`, `PYTHONPATH=.:../crm-cell pytest backend/tests/ ...`). |
| 3 | PricingTool only — never hardcode a price (Golden Rule #11) | 🔴 | `test_golden_rules.py` covers rules #3/#5/#6/#8 only — **no #11 tripwire**. Scattered feature-specific tests exist (`test_whatsapp_persona_no_hardcoded_pricing.py`, `test_templates_no_hardcoded_prices.py`) but each guards one surface, not the invariant generally — a new hardcoded price in a new surface has no test to fail. |
| 4 | Clean logging — no `print()` in production code (Golden Rule #8) | 🟢 | `test_golden_rule_8_no_print_statements` (same file/job as #2) + ruff `T20` (flake8-print) armed in `apps/backend-rag/pyproject.toml:325` with per-file CLI-script exemptions. |
| 5 | Type hints required (Golden Rule #5) | 🟢 | `test_golden_rule_5_type_hints`, same job. |
| 6 | Path discipline — absolute imports (Golden Rule #3) | 🟢 | `test_golden_rule_3_no_relative_imports`, same job. |
| 7 | Persistent async httpx client, never ad-hoc `AsyncClient()` (Golden Rule #10) | 🟡 | `lint-golden-rule-10.yml` delegates to a real regression test (`test_no_httpx_violators.py`). **Not in required_status_checks** — can fail red without blocking. |
| 8 | Commit discipline — never `--no-verify`/`--amend` on a pushed commit | 🔴 | Structurally unenforceable after the fact by a server-side CI gate (`--no-verify` skips the hooks that would object, by definition, before anything reaches GitHub). Session-prose + `.claude/rules/cicatrix-superscar.md` scar record only. |
| 9 | Embedding model FROZEN — `text-embedding-3-small`, 1536 dims | 🟢 | `apps/backend-rag/backend/tests/test_data_invariant_tripwires.py:103-123` asserts the literal string + dimension count is still present in the source; collected by the same required `backend/tests/` run. |
| 10 | Evidence-scoring thresholds — 5 named gates, one SSOT, generation≠label divergence intentional | 🟢 | `test_abstain_threshold_convergence.py` + `test_abstain_policy_hardening.py`, same collection path. |
| 11 | Postgres MCP — read-only for agents | 🟢 | Structural, at the DB-role level, not CI: `nuzantara_readonly` role carries 255 SELECT grants, zero INSERT/UPDATE/DELETE/CREATE (CLAUDE.md §10). Not bypassable by a diff — would need `fly ssh`/direct prod-DB access, itself operator-only. |
| 12 | Migration PRs auto-run Squawk lint (CLAUDE.md §11) | 🟡 | `migration-lint.yml` job named `Lint` runs Squawk. **Not in required_status_checks** — "auto-run" is true, "gates the merge" is not. |
| 13 | Off-limits file: `apps/backend-rag/backend/prompts/zantara_core.py` | 🟡→🟡+ (this PR) | **Correction, caught by this session's own commit, not by reasoning about the file tree**: `.husky/pre-commit` Gate 1 (`.husky/pre-commit:404-411`) DOES block a staged commit whose diff names a path matching the basename `zantara_core\.py` — real, blocking (`exit 1`), and observed firing live in this PR's own commit. But: (a) **client-side only** — never re-checked server-side, so a PR from a machine without husky, or one opened via the GitHub web UI, is invisible to it; (b) **the hook's own error message tells the author to bypass it** — "Se la modifica è intenzionale, fai unstage e commetti con `--no-verify`" — the exact command Golden Rule #12 names as never-allowed; (c) **basename substring match, not exact path** (`grep -E "zantara_core\.py"`), so a differently-located file sharing that basename would also trip it (over-match, the safer direction, but still the W105/W107 shape). Zero CODEOWNERS entry and zero server-side/CI check remain true — see §2 and §3. New `zantara-core-edit-gate.yml` adds the first server-side signal, non-required by design (see §3). |
| 14 | Off-limits file: `fly.toml` | 🟡 (client-side + toothless label) | Same `.husky/pre-commit` Gate 1 blocks any staged path containing `fly\.toml` — same three caveats as #13 (client-side, `--no-verify`-suggested bypass, basename match — this one is intentionally broad: it blocks ALL three `fly.toml` files in the repo, not just `apps/backend-rag/fly.toml`, which is over-inclusive but the safe direction for a security gate per the hook's own header comment). Server-side: `apps/backend-rag/fly.toml` (the only one CLAUDE.md's deploy doctrine actually means — see #16) has a CODEOWNERS label, but branch protection has **`require_code_owner_reviews: false`, `required_approving_review_count: 0`** (live `gh api` pull) — the label requests a review nobody is required to give. `hot-zone-pr-gate.yml` also matches it into `HOTZONE_MATCH`, but that flag only feeds a `continue-on-error: true` Redis lease check (CI runners can't reach the lease store anyway) — never a block. |
| 15 | Off-limits file: `.env*` | 🟡 (narrow) | Real `.env` files are gitignored (`.gitignore:139 .env*`) so accidental commit is structurally unlikely. `catE-sovereignty-lint.yml` checks `apps/*/.env` world-read **permissions** only (non-required) — nothing checks whether the file's *contents* were edited by automation. |
| 16 | Off-limits file: `alembic/env.py` | 👻 | **This path does not exist anywhere in the repository.** `find . -path "*alembic/env.py"` returns nothing; the only "alembic" hit in the whole tree is `apps/bali-intel-scraper/backend/db/migrations/alembic.ini`, a different app. This repo's live migration system is `apps/backend-rag/backend/db/migrations_v2/` + `migration_manager.py` (both real, both CODEOWNERS Tier-1, per #12). The doctrine line was never updated when the migration system changed — anti-hallucination-blindness family (superscar #6) applied to the doctrine text itself, not to an agent's tool output. |
| 17 | **Final on-disk gate** — Opus 5 at effort `max`/`xhigh`, never cascades to a weaker model, window-dead → task SUSPENDS (CLAUDE.md §5, 2026-08-20 ruling) | 🟡 (self-documented blocked) | Mechanized as a commit status `harness/fable-gate`, published by `scripts/harness_fable_gate.py` and self-defaulted to success for non-Gear-3 diffs by `harness-floor.yml` — a real, working piece of CI machinery. **Confirmed absent from `required_status_checks.contexts`** (live `gh api` pull). The workflow's own header (`harness-floor.yml:48-56`) says this is not an oversight: "adding `harness/fable-gate` to branch protection's required_status_checks ... is BLOCKED, not merely pending", naming two open technical objections and concluding "Both need a design decision." A Gear-3 PR — including one that edits an off-limits file (`modus_green_gate.py`'s "perimeter" set feeds this same gear-floor computation) — can merge today with **no gate verdict published at all**. See §4 — the top finding. **AMENDED 2026-08-22 — SUPERSEDED SAME DAY, kept for history**: #4539 redesigned the gate so the REQUIRED context is the workflow job `Harness floor recompute` (verdicts read via `scripts/ci/harness_gate_read.py`, every workflow write removed, fork read-only tokens no longer a blocker), and #4541/#4543 recorded the promotion; live `gh api` pull 2026-08-22 confirms `Harness floor recompute` IS in `required_status_checks.contexts` (27 contexts, app_id 15368) and `harness-floor.yml`'s header now reads ARMED — NOTHING IS PENDING. The "absent / BLOCKED / needs a design decision" text above is the state as of this map's writing (2026-08-21 ~08:52Z), four hours before the redesign landed — it is NOT the current state. (Residual declared by #4539 itself, not cured: required-check name-spoofing repo-wide, and no attestation of WHO posted a verdict — both in PENDING-ARMS.) |
| 18 | PII/OSINT never in cleartext to a cloud LLM (chat text specifically) | 🔴 (self-declared) | CLAUDE.md §14 states this outcome about itself, verbatim: "il gateway chat non prova oggi clausola ... il gap resta in PENDING-ARMS." Not a discovery of this audit — the doctrine already knows. `cloud_vision_gate` is real but scoped to OCR/vision only. `yield-optimizer-pii-gate-tests.yml` is a real, passing test suite for exactly one named exception surface (the 2026-08-21 WA-digest deroga) — not in required_status_checks, and scoped to that one surface. |
| 19 | No phantom-operator lines in the PENDING-ARMS ledger | 🟢 | `scripts/pending_arms_report.py --strict-phantom`, run as step "No phantom-operator lines in the ledger (strict-phantom gate)" inside job `antidotes` (`immune-enforcement.yml:1063-1066`) — job id `antidotes` matches `required_status_checks.contexts` verbatim. |
| 20 | Ship-lifecycle ownership — arm `gh pr merge --auto` (bare) at PR-open, every L2 PR (CLAUDE.md §2) | 🔴 | `auto-merge-whitelist.yml` auto-arms only for a narrow branch whitelist (`docs/auto-sync-*`, `dependabot/*`, `chore/fmt-*`) — not general session PRs. `merge-queue-watch.yml` watches for **ARMED-but-stuck** and **ejected-without-merge**; nothing watches for **never armed at all**. A session could open a PR and simply never arm it, and no automated signal would say so. |
| 21 | Agent worktree discipline — every session under `.worktrees/<lane>-<task-id>/` (CLAUDE.md, agent PR contract) | 🟡 (client-side only) | `infra/claude-hooks/worktree_isolation.py`, guilt+innocence tested (guard-conformance registry, `command_hooks` surface). Real, but **session-local**: it fires only if the hook is installed and armed on the machine that runs the session (kill switch `AGENT_BROKER_ENABLED=false`), and nothing server-side (CI) can see whether a PR's commits were authored from inside a worktree — there is no commit-trailer or CI check that verifies this after the fact. |
| 22 | Email sender always `zantara@balizero.com`, never `notifications@`/`subhi@`/personal (CLAUDE.md §13) | 🔴 | No lint found. One incidental string match (`scripts/wr2_canva_pdf_render.py`) is the entire footprint; no CI check scans for a wrong `from=` value in the notification service call sites. |
| 23 | Codex sandbox — `read-only`/`workspace-write` only, never `--dangerously-bypass` (CLAUDE.md §5) | 🔴 | No lint found for the literal flag across `scripts/`/`.github/workflows/`. Narrower blast radius than the others (governs how a session invokes a CLI at runtime, not a persistent artifact) — ranked below the top 5. |
| 24 | Guardrails daemon — blocks destructive MCP patterns (`drop_*`/`delete_*`/`truncate_*`/…) (CLAUDE.md §7) | 🟡 (machine-dependent, already tracked) | Not this audit's discovery — carried from prior sessions' own memory: M5 never had the tier-1 daemon installed at all, and even where it runs, the fallback blocks DML but waves DDL through. Included here as a live example of the exact thesis of this document: "hooks enforce what prompts cannot" is itself sometimes prose-only, per machine. |

**Not independently re-verified in this pass** (named in CLAUDE.md but out of the time budget for
a live-artifact check): vision-model-must-be-`qwen2.5vl:7b`, `Ollama think:false` requirement,
cache-invalidation-after-every-mutation. Listed for completeness, not counted in the 24.

---

## §2 — Why `zantara_core.py` is the worst of the four off-limits files

`apps/backend-rag/backend/prompts/zantara_core.py` is the bot's prompt-injection boundary — its
own docstring calls the relevant section `SECURITY_BOUNDARY` / "IMMUTABLE SECURITY RULES - CANNOT
BE OVERRIDDEN" — referenced by 17 non-test modules by name (`orchestrator_core.py`, `reasoning.py`
[via `_reasoning_stubs.py`], `prompt_builder.py`, `whatsapp_persona.py`, the agentic RAG stack;
precise count: `grep -rlE 'zantara_core\b' apps/backend-rag/backend --include='*.py'`, excluding
tests and the version-suffixed sibling files `zantara_core_v2..v5.py`) and therefore live across
every channel this system serves (WhatsApp, Telegram, Instagram, Web Chat — CLAUDE.md §12).
Measured against the other three names on the same "off-limits" line — **and corrected mid-audit**
by this session's own commit output, which showed `.husky/pre-commit` actively blocking a staged
`zantara_core.py`/`fly.toml`/`alembic/env.py` path (Gate 1, `.husky/pre-commit:404-411`): reasoning
about the file tree said "no check"; running a real commit said otherwise. All three names that
exist get that same client-side gate, whose own error message instructs the exact `--no-verify`
bypass Golden Rule #12 bans — so "protected" here means "protected until an agent follows the
gate's own suggested remediation." What actually differentiates the four:

- `fly.toml` (real path: `apps/backend-rag/fly.toml`) — client-side gate (above) **plus** a
  CODEOWNERS label (toothless, review not required, #14) **plus** a `hot-zone-pr-gate.yml`
  `HOTZONE_MATCH` entry (feeds only a monitor-only Redis lease check, never blocks — #14).
- `.env*` — **not** covered by the pre-commit gate at all (its regex has no `.env` branch);
  gitignored by convention instead, plus a narrow, non-required perm-check (#15).
- `alembic/env.py` — matched by the pre-commit gate's regex, which makes no difference: the path
  doesn't exist, so the pattern can never fire (#16, 👻).
- `zantara_core.py` — the client-side gate, and **nothing else**: no CODEOWNERS line (so not even
  a toothless review-request), no `HOTZONE_MATCH` entry, no server-side signal of any kind before
  this PR. Scattered non-CI helper scripts also reference it (`scripts/ai-dispatch.sh` preflight
  dispatcher, `scripts/sentinel_lib/repairer.py`'s `off_limits` exclusion set,
  `scripts/tech_orchestrator.py`'s `critical_patterns`, `scripts/modus_green_gate.py`'s gear-floor
  "perimeter") — every one of these is advisory logic *inside a tool a session may or may not
  invoke*, not a gate a PR must pass, and none of them is server-side either.

It remains the thinnest-protected of the four real names — the only one where the sole existing
signal is the single, bypassable, client-side gate, with nothing behind it. An undeclared edit that
bypasses (or simply never runs) that one gate is an undeclared change to the bot's jailbreak
defenses, silently, across every live surface — the highest blast-radius, cheapest-to-close
server-side gap this audit found, with a clean, low-risk guard shape (exact single-path match, no
content heuristics). Built in §3, as the first server-side signal for this file — deliberately not
a replacement for the existing client-side gate, which stays exactly as bypassable as before.

---

## §3 — What was built

**`scripts/lint_zantara_core_edit_declared.py`** + **`.github/workflows/zantara-core-edit-gate.yml`**.

Shape: does **not** block an edit to `zantara_core.py` outright — CLAUDE.md §2's ship-lifecycle-
ownership doctrine means the session ships without human review by design, so a hard block would
just get routed around. It requires the edit to be **declared**: a PR touching the file must carry
a `Zantara-Core-Edit: <reason>` line in its body, the same vocabulary-token shape this repo already
uses for the R1 gate's `adversarial_review:` line (`lesson_r1_frontmatter_is_vocabulary_not_narrative`
— check for the token's *presence*, never judge the reason's *content*). Enumeration reuses the
repo's own trusted, merge-base-anchored changed-file script (`scripts/ci/hotzone_changed_files.sh`)
rather than re-deriving a second one — the W102 two-dot-diff bug this repo already scarred on lives
in exactly that kind of duplication.

**Landed non-required, by design** — matching this repo's own onboarding convention for a new
signal (`catE-sovereignty-lint.yml`'s own header: observe a review cycle before requiring, per the
W69 BUCO #1 lesson that a required check without a proven zero-false-positive record can
pend-forever). Promoting it into `required_status_checks` is a **branch-protection setting change**,
which CLAUDE.md §13 names explicitly as an operator action ("repo/branch-protection settings ...
are operator actions, not reviewable diffs") — not something this PR or its workflow arms itself.
Tracked in §5.

**Guilt + innocence, verified this session** (`scripts/tests/test_lint_zantara_core_edit_declared.py`,
22 tests after the adversarial-review fix round below, all passing against
`/Users/balizero/.local/share/mise/shims/pytest`):

- Guilt: file touched with no PR body; empty body; unrelated body; a bare `Zantara-Core-Edit:` token
  with nothing after the colon; whitespace-only after the colon; a misspelled token
  (`Zantara-Core-Edited:`); the file touched alongside other, unrelated files; **a literal copy of
  this script's own remediation text, `Zantara-Core-Edit: <reason>`** (found by Kimi K3 — see
  "Adversarial review" below); five other placeholder values (`TODO`/`tbd`/`N/A`/`...`/`reason`).
- Innocence: file not touched at all — with no body, and separately with a body carrying a
  **well-formed, line-start declaration** (proving the guard keys off the changed-file set before
  the body, not just "the body doesn't happen to match" — the first draft's version of this test
  used a mid-line mention that would never have matched the regex regardless of predicate order,
  which proved nothing; also fixed after Kimi's review); a **same-basename file at a different
  path** (`.../tests/fixtures/prompts/zantara_core.py`) touched instead, exact-path match only
  (the W105/W107 basename-vs-path lesson); a real declaration with a reason, case-insensitively,
  anywhere in the body, including sitting among other frontmatter-style lines (mirrors how
  `adversarial_review:` actually appears in practice).

Also run and passing before landing: `ruff check` (clean), `actionlint` on the new workflow (clean),
and — since a new textual guard risks tripping the repo's own required "Every guard proves guilt
AND innocence" gate — `python3 infra/guard-conformance/check_guard_conformance.py` locally: **0
violations**, confirming the new script is correctly out of that registry's `_guard_`-prefix census
(it is a declared-intent check on a structural predicate, not a `_guard_*` textual-matching function
of the over/under-match family #3 that registry targets).

**Deliberately not built**: a guard for `fly.toml`, `.env*`, or a corrected `alembic/env.py` entry
in the same PR. Per the mandate, "do not build a swarm of new gates in one PR" — and each of those
three has a materially different fix shape (branch-protection-setting change for `fly.toml`'s
toothless CODEOWNERS label; content-editing CLAUDE.md to remove the phantom `alembic/env.py`
citation is a docs fix, not a guard; `.env*` already has a narrower, real, non-blocking check). None
is the single cheapest, highest-leverage, cleanest-guard-shape gap the way `zantara_core.py` is.

---

## §4 — Top 5 ENFORCED-NOWHERE (and enforced-but-advisory), ranked by blast radius

1. **Final on-disk gate not required** (#17). The mechanism to make a Gear-3 diff (architecture,
   migrations, cross-system change, off-limits-file touches) physically un-mergeable without a real
   gate verdict is built, wired, and self-documented as deliberately not yet armed. Blast radius:
   the entire class of change this repo's doctrine calls its highest-scrutiny tier ships exactly
   like every other PR today. Not new — already tracked as blocked-pending-a-design-decision in the
   workflow's own comments as of 2026-08-10 — but not previously written up outside that comment
   block, and worth a §5 line of its own given how much downstream doctrine (off-limits files, gear
   ceiling, WR2 content gate) funnels into this one unarmed status.
   **AMENDED 2026-08-22: RESOLVED SAME DAY** — #4539/#4541/#4543 redesigned and promoted the gate;
   the required context `Harness floor recompute` is live in branch protection (verified 2026-08-22).
   See the amendment on row #17 for the mechanism and the two residuals #4539 itself declared.
2. **Ship-lifecycle "arm every PR" has no watchdog for the never-armed case** (#20). The organism
   already has the *shape* of this antidote (`pending_arms_report.py`'s ledger-staleness pattern,
   `merge-queue-watch.yml`'s armed-but-stuck detector) — extending either to "PR open >Nh, author is
   an agent identity, no auto-merge armed, no `operator[...]` label" is a natural next PR, not
   attempted here (scope discipline, §3).
3. **`zantara_core.py` had zero server-side visibility before this session, and its only existing
   protection is a client-side gate whose own remediation path is the exact bypass command Golden
   Rule #12 bans** (#13). First server-side signal closed this PR, non-required (§3).
4. **PII/OSINT cleartext-to-cloud boundary for ordinary chat text** (#18). Self-declared by the
   doctrine itself, not a new finding — ranked here for blast radius (client PII), not novelty.
5. **PricingTool-hardcode has no repo-wide guard** (#3). Real client-money risk; not built here
   because the honest guard shape is a heuristic content scan (price-like literals near
   pricing-adjacent keywords), which is exactly the guard-over-match shape superscar #3 warns
   against building without extensive guilt/innocence work first — a bigger, separate PR.

**Enforced-but-advisory worth flagging separately** (not "nothing catches it" — "it's caught and
then ignored by construction"): the Anthropic-SDK paid-endpoint ban (#1), the async-httpx-client
pattern (#7), and Squawk migration lint (#12) can all go red on `main` today without blocking a
single merge, because none is in `required_status_checks`. None is new to this audit — each
workflow's own header already explains why it isn't required yet — but collecting all three in one
place makes visible that "enforced" in this repo's CI inventory does not, by itself, mean
"required".

---

## §5 — Solo-operatore

Everything below requires a human action this session correctly did not take:

- **Promoting any advisory check to required** (`harness/fable-gate`, `catE-sovereignty-lint`,
  `lint-golden-rule-10`, migration-lint's `Lint` job, the new `zantara-core-edit-declared`) is a
  branch-protection `required_status_checks` change — CLAUDE.md §13 names "repo/branch-protection
  settings" explicitly as operator, not session, territory.
- **The `harness/fable-gate` arming decision** specifically (#17) has two named open objections
  in `harness-floor.yml:48-56` (self-publish chicken-and-egg; `GITHUB_TOKEN` read-only on the
  default-publish steps) that the file's own author already deferred as needing "a design
  decision" — re-litigating that design call is not this audit's mandate.
- **Fixing the phantom `alembic/env.py` citation** (#16) is a one-line CLAUDE.md edit (replace with
  `migrations_v2/` + `migration_manager.py`, which are the real, already-CODEOWNERS-Tier-1
  equivalents) — technically within session authority to just make, but left as a named,
  citable finding here rather than silently folded into this PR's diff, since CLAUDE.md itself is
  a CODEOWNERS Tier-1 path and a drive-by doctrine edit inside an audit PR is exactly the kind of
  scope-creep the mandate said not to do ("Do NOT build a swarm of new gates in one PR" — this
  extends the same discipline to doctrine edits).

---

## Adversarial review

Cross-family grader: **Kimi K3** (`kimi -p … -m kimi-code/k3`), fresh context, given the pre-fix
draft of this document and told to attack it — the class of check CLAUDE.md §6 requires for a
research/audit deliverable (generator≠grader), matching the pattern the imported
world-patterns-import-map itself used.

**Run detail, declared, same shape as that document's own review**: the invocation was killed by
this session's own time budget (~4m40s) after producing ~30KB of review reasoning but before
emitting a final formatted answer. The objections below are real findings taken from that
in-progress reasoning trace, not a clean pass — recorded honestly rather than re-run to
completion, since the findings that did land were concrete and independently re-verified against
the live tree before being accepted.

**Verified independently and confirmed by the live `gh api` pull this session already had**: Kimi
re-derived, from the same document, that `harness/fable-gate`, `catE-sovereignty-lint`, the
migration-lint `Lint` job, and the new `zantara-core-edit-declared` are all absent from
`required_status_checks.contexts`, and that `require_code_owner_reviews:false` /
`required_approving_review_count:0` hold — rows #1, #12, #14, #17 confirmed by a second read of the
same live artifact, not merely re-stated. Also confirmed: job id `antidotes` is in the required
list (row #19), `Backend Tests (Python)` and `Detect Secrets` are required (row #2), CODEOWNERS
has no `zantara_core.py` line and does have `fly.toml` at lines 77-78 (§2).

**Accepted and fixed** (4):

1. **Workflow file count was wrong** — "98 files" counted `catE-paid-anthropic-baseline.txt` and
   the disabled `ai-pr-review.yml.disabled-...` sibling alongside the 97 real `.yml` workflows.
   Fixed in the frontmatter sources line.
2. **"~20 modules" for `zantara_core.py` importers was an eyeballed guess** — re-run precisely as
   `grep -rlE 'zantara_core\b' apps/backend-rag/backend --include='*.py'`, excluding tests and the
   version-suffixed sibling files (`zantara_core_v2.py`..`v5.py`, which are separate prompt
   variants, not importers of the base file): **17**, not ~20. Fixed in §2, §3, and the script's own
   docstring/error message (`scripts/lint_zantara_core_edit_declared.py`).
3. **The "innocence: hostile body" test proved nothing about precedence.** Its PR body mentioned
   the token text mid-line ("... mentions Zantara-Core-Edit: in passing"), which the `^`-anchored
   regex would never have matched regardless of whether the guard checked the changed-file set or
   the body first — a test that passes for the wrong reason. Rewritten to use a well-formed,
   line-start declaration in the body of a PR that does *not* touch the target file, which actually
   exercises predicate order.
4. **Real guilt-test gap, not just a wording nit**: the script's own remediation message suggests
   `Zantara-Core-Edit: <reason>` — Kimi noted that `\S` matches `<`, so a lazy author who copy-pastes
   that literal suggestion verbatim would satisfy the regex while declaring nothing. Confirmed live
   (`python3 -c "..."` reproduction, see the script's inline comment) and fixed with a small,
   case-insensitive placeholder denylist (`<reason>`, `reason`, `todo`, `tbd`, `...`, `n/a`, `na`) —
   the narrowest fix that closes the specific hole without turning the check into a content-quality
   heuristic (which would reopen the guard-over-match risk this whole guard was built to avoid).
   Guilt tests added for the literal placeholder and five siblings; a mutation check (temporarily
   reasoning through the regex without the denylist) confirmed the placeholder would otherwise have
   passed.

**A fifth correction, not from Kimi — from running this session's own commit.** The pre-fix draft
(and Kimi's review of it) both said `zantara_core.py` had "no CI check, nothing" beyond scattered
non-blocking helper-script references. Committing this very PR's files printed `.husky/pre-commit`
actively blocking on staged off-limits paths (Gate 1) — a real, live, blocking client-side gate
that had gone unnoticed by grepping `.github/workflows/` and CODEOWNERS, because it lives in
neither. Corrected in rows #13/#14 and §2: the honest finding was never "zero protection", it was
"the only protection is one bypassable client-side gate, and the bypass it names is a banned
command" — a more precise and, if anything, more load-bearing version of the same conclusion. Left
in as a demonstration of the discipline this whole document argues for: reasoning about a file tree
is not the same as running the thing, and this session's own anti-hallucination rule ("mai citare
output di un tool senza averlo eseguito in QUESTO turn") caught a gap in its own earlier reasoning
only because a real command was run, not because the earlier claim was double-checked harder.

**Raised, not accepted as a fix in this PR** — recorded rather than silently dropped:

- Kimi raised a rename-detection question (does `hotzone_changed_files.sh`'s changed-file
  enumeration, and GitHub's own `paths:` trigger filter, correctly see a `git mv` of
  `zantara_core.py` as "touched"?) but did not reach a confident conclusion before being cut off,
  noting GitHub's own documented behavior for path-filtered *required* checks already avoids the
  worst failure mode (a skipped path-filtered check reports success, not pending-forever). Since
  this workflow is explicitly non-required (§3), a residual rename blind spot — if real — has no
  merge-blocking consequence today; worth a follow-up probe before any future promotion to
  required, not before landing this PR.
- Kimi flagged that a genuine, well-intentioned declaration written as natural prose ("this PR
  edits the file to fix X" with no line-start `Zantara-Core-Edit:` label) would be rejected —
  correct, and intentional: this mirrors the R1 gate's own existing convention
  (`adversarial_review: <value>` requires the same exact vocabulary-token shape, not a prose
  mention), and the failure message names the exact required format. Loosening the match to accept
  free-form prose would reopen exactly the under-match risk (superscar #3, family gemello) a
  vocabulary-token check exists to avoid.
