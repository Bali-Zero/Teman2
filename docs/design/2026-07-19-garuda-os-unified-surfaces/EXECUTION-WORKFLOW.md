# GARUDA OS — Agentic Execution Workflow

|                |                                                                                         |
| -------------- | --------------------------------------------------------------------------------------- |
| **Status**     | PROPOSED — operating procedure for the WS1–WS4 implementation train                     |
| **Date**       | 2026-07-20                                                                              |
| **Author**     | Kimi (external agent) — grounded in repo inventory of 2026-07-20                        |
| **Companion**  | `PLAN.md` (merged, #2850) — this document is the _how_; the PLAN is the _what_          |
| **Hard rules** | Generator ≠ grader · Legge 5 (operator merges/publishes) · worktree discipline · no PII |

---

## 1. The cast — who does what

| Actor                   | Role in this train                                                                                                                                                          | Invoked via                                                 |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Operator (Zero)**     | Merge authority, scope calls, publishes. The only merger.                                                                                                                   | `gh pr merge`                                               |
| **Claude Code session** | **Verifier/grader** — independent review, tests, merge prep on every PR                                                                                                     | interactive session                                         |
| **Kimi (builder)**      | Implementation PRs: tokens, components, portal pass. Never merges.                                                                                                          | kimi CLI / Desktop                                          |
| **Codex CLI "spalla"**  | Adversarial second opinion on **non-UI** diffs (BLOCKER/MEDIUM/LOW/LGTM)                                                                                                    | `/codex-second-opinion` → `.claude/scripts/codex-spalla.sh` |
| **Tri-LLM panel**       | Automated review gate on every `agent/*` PR head: Codex gpt-5.5 + Claude Opus 4.7 + Kimi K3. All-live-green = clean; any red = red; <2 live = inconclusive. **Review-only** | Pro LaunchAgent, `scripts/async_review_supervisor.py`       |
| **agy (Gemini)**        | Research, external benchmarks, token archaeology                                                                                                                            | CLI                                                         |
| **frontend-browser**    | Visual QA of rendered pages (kita/my) — the only sanctioned "eyes" for UI work                                                                                              | `.claude/agents/frontend-browser.md` (read-only)            |
| **merge-train**         | PR serialization — currently Phase 0 DRY-RUN; not relied on                                                                                                                 | `scripts/merge_train.py`                                    |

Routing notes:

- **`codex-second-opinion` is NOT for visual/UI work** (its own anti-pattern A3) — UI diffs go to `frontend-browser` + human eye.
- **Kimi K3 sits on the Tri-LLM panel since 2026-07-19** — on Kimi-authored PRs the panel still reviews independently (review-only); builder ≠ verifier is preserved by the Claude-session + operator layers.

## 2. The chain — every task, every WS

One loop per task, mapped on the `modus` skill (gear 2 standard for most; gear 3 profondo for WS1 token surgery):

1. **STADIO-ZERO** (mandatory entry gate): memory hits (`mem query "<domain>"` + cicatrix grep), hot-files **verified on disk**, PII scope (Law 2), falsifiable acceptance criteria written down.
2. **GROUND** — `reuse-first`: find the existing working code before writing new (e.g. `packages/core/components` 18+ already tested).
3. **WORKTREE** — `agent-session-discipline`: `python scripts/agent_start.py --lane frontend --task-id <slug> --base-branch origin/main` (lane `frontend`; `mouth` is Subhi-reserved). Never in main checkout.
4. **BUILD** — narrowest diff; `karpathy-discipline` (no silent assumptions, no hypertrophy, no collateral changes).
5. **VERIFY** — empirical only (`/verify` rule: cite tool output from this turn, never from context): unit tests, `pytest`/`jest` as applicable, AA contrast computed, screenshots via frontend-browser for UI.
6. **ADVERSARIAL** — non-UI diff → codex spalla; UI diff → frontend-browser run; research/audit docs dropped in `research/` → R1 gate requires a **cross-family** `adversarial_review:` seat **in the same commit**.
7. **PR** — small (<80K chars diff — the Tri-LLM truncation budget), conventional title, body with contract-compliance block. Push note: `docs/**/*.html` currently trips the pre-push classifier into a false-positive FULL suite — `--no-verify` is acceptable **for docs-only pushes**, always disclosed in the PR body.
8. **GATES** — CI green (incl. inventory-check: register new docs in `docs/DOCS_INVENTORY.md` via `docs_audit.py --regen-only` args from `docs-guardian.yml`); Tri-LLM live verdict; Claude session verifies.
9. **MERGE** — operator only. Then **CAPTURE**: `/scar` for every trauma (severity + antibody), `mem save` for durable lessons.

## 3. The train — per workstream

### WS1 — Token reconciliation + FactBadge (gear 3, first PR)

- **Builder**: Kimi. **Adversarial**: codex spalla (token diffs are logic, not visual). **Verifier**: Claude session.
- **Skills**: stadio-zero, reuse-first (merge _into_ `packages/core`, don't fork), karpathy.
- **Gate notes**: `packages/design-system` deprecation = repo-wide signal — announce in PR body; single ThemeProvider removal touches `src/components/providers/` (list every consumer in the PR).
- **DoD**: one token SSOT; `FactBadge` + tests green; zero consumers of the legacy `next-themes` path; frontend smoke (`mouth` build) green.

### WS2 — kita. components (gear 2, after Phase 4 waiver)

- **Prerequisite**: `packages/core` Phase 4 waiver / governance update (PLAN §7.5) — obtained _before_ opening.
- **Builder**: Kimi. **Visual QA**: frontend-browser on `/dashboard`, `/clients`, `/process`. **Verifier**: Claude session.
- **Skills**: stadio-zero, reuse-first (`StatChips`, `Money`, `ProgressRing` exist — extend, don't clone).
- **DoD**: `SystemPulse` + `ComplianceRadar` (+ pipeline/dock if waiver allows) with unit tests; semantic tokens only in touched files; visual baseline captured.

### WS3 — my. portal day pass (gear 2, page-by-page PRs)

- **Builder**: Kimi. **Visual QA**: frontend-browser on `/portal` home, matters, billing (light theme).
- **Skills**: stadio-zero, karpathy (one page per PR — no hypertrophy).
- **AA rule**: copper family ≥ 4.5:1 for small text (computed, cited in PR); `#b5633a` reserved to large text/UI.
- **DoD**: Lighthouse a11y ≥ 95 per page; zero hex drift in diff; screenshots attached.

### WS4 — Governance (gear 2)

- Token-lint CI rule (new hardcoded brand hexes = fail) + visual regression on 5 screens + theme-key reconciliation to `bz-theme` with one-time migration.
- **Gate note**: new workflow files are CODEOWNERS-locked (`/.github/workflows/`) → expect operator review by design.

## 4. Transversal rules (always on)

- **PII (Law 2)**: fictional rows/IDs only in mockups, tests, screenshots; CRM data stays read-only and is never transcribed into artifacts.
- **Memory protocol**: `mem query` before building (domain scars), `mem save` after merging (durable lessons); never present recalled context as a fresh query.
- **Scar protocol**: every gate bite, flake, or false positive that cost >10 min → `/scar` entry (TRAUMA/ANTIBODY/GOTCHA). Candidates already visible: prepush allowlist vs `docs/**/*.html`; inventory-check wall-clock drift vs PR latency.
- **PR size discipline**: <80K chars diff; HTML artifacts are minified-or-single per PR; split early, not after a red gate.
- **CLI-first execution**: build sessions run in CLI (shared memory, hooks, spalla, mem); Desktop for design review and demos.

## 5. PR cadence

`WS1` → `token-lint` → `WS2 components (1-2 PRs)` → `WS3 portal (3+ small PRs)` → `WS4 governance`. One workstream's merge unlocks the next; no parallel lanes on the same files.
