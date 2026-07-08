---
date: 2026-07-03
domain: operations
client_case: none
sources:
  - scripts/docs_sync.py + .github/workflows/docs-sync.yml (read this session)
  - scripts/docs_audit.py + scripts/docs_guardian.sh + .github/workflows/docs-guardian.yml
  - scripts/docs_link_fixer.py, scripts/docs_history_analyzer.py, scripts/generate_automations_reference.py
  - scripts/build_repomap.sh + Pro crontab/LaunchAgents (probed live via ssh)
  - two parallel disk sweeps (dead-paths, undocumented-organs), 2026-07-02
  - PRs #1936 (drift fixes), #1939 (generation extension), PR3 (this file + freshness report)
---

# Documentation-as-organ — system map (GEAR 3, 2026-07-02/03)

**Mandate**: make the system MAPPED and AUTO-DOCUMENTED. Doctrine: hand-written
docs rot (W86 / doc-drift family) — the deliverable is GENERATION + FRESHNESS
GATES, not more prose. This file is the map of what exists, what was drifting,
what changed, and what remains operator-only.

## 1. The doc-organ system (as found on disk, verified this session)

| Organ | Kind | Output | Armed? (probed, not assumed) |
| ----- | ---- | ------ | ---------------------------- |
| `scripts/docs_sync.py` (DocSentinel) | generator (DOCSYNC markers) | README.md, docs/AI_ONBOARDING.md — **+ INDEX.md, docs/runbooks/README.md since PR #1939**; CLAUDE.md was a DEAD target (markers removed in F44) until PR #1939 dropped it | ✅ CI gate `docs-sync.yml` (PR+push) + called by docs_guardian.sh |
| `.github/workflows/docs-sync.yml` | CI gate | fails PR if markers stale | ✅ — **paths extended in #1939** to every generation input (W86 antidote) |
| `scripts/docs_audit.py` | generator + classifier | docs/DOCS_INVENTORY.md (LIVE/STALE/ARCHIVED, broken links, orphans) — scope: `docs/**/*.md` only | ✅ CI gate `docs-guardian.yml` (PRs touching docs/**) + weekly cron |
| `scripts/docs_guardian.sh` | weekly cron (L0 inventory, L1 auto-archive PR, L2.5 Claude link-fixer) | auto-PRs | ✅ Pro crontab `0 5 * * 0` via cron-state.sh (probed: `ssh pro crontab -l`) |
| `scripts/docs_link_fixer.py` | LLM repairer (claude CLI OAuth) | link fixes inside guardian PRs | ✅ via guardian |
| `scripts/docs_history_analyzer.py` | generator | docs/DOCS_TRENDS.md (monthly trend mining) | ❌ **NOT armed** — no crontab/plist anywhere; output 69d old vs 31d cadence |
| `scripts/generate_automations_reference.py` | generator (scans LIVE crontab+launchctl on Pro+Mini) | docs/AUTOMATIONS_REFERENCE.md | ⚠️ on-demand only, no cadence — last regen 2026-05-31; root cause of the 45% plist-coverage gap |
| `scripts/build_repomap.sh` | generator | `~/.nuzantara-repomap.txt` (session context inject) | ✅ `com.nuzantara.repomap.15min` plist on Pro (probed) |
| `scripts/doc_freshness_report.py` | **NEW (PR3)** reconciliation signaler | markdown/JSON report, 4 sections | on-demand + `doc-freshness.yml` workflow_dispatch; report-only, exit 0 (W81: signaler, not actuator; W84: no new daemon) |
| INDEX.md | atlas — hand-written narrative **+ generated enumerable section since #1939** | — | narrative part gated only by freshness report |
| VADEMECUM.md / SYMBIOSIS.md | operator voice (Legge 5 — never rewritten by agents) | — | out of generation scope by design |
| `scripts/automation_catalog.json` | hand-maintained catalog | — | `_updated: 2026-04-16` — 2.5 months stale |

## 2. Drift measured (evidence, 2026-07-02)

- **15 dead path references** across the atlas: README.md 8 (7 deleted apps +
  `packages/kb`→`apps/kb`), AI_ONBOARDING.md 4, INDEX.md 1 (`apps/federation`,
  deleted in 5c06a2fd5), VADEMECUM.md 2 (aspirational, never existed).
- **AI_ONBOARDING.md onboarded AIs onto a decommissioned machine**: the QUICK
  START peer-check still targeted Air M4 (`antonellosiano@Nuzantara-9`,
  decommissioned 2026-05-05) with `[Pro] or [Air]` prefixes.
- **Hand-written numbers contradicting generated blocks in the same file**:
  README said "20 apps / 88 routers / 244 services / 10 collections / 93,283
  documents" while its own DOCSYNC block 2 lines away said 30 / 329 / 635 / 12
  / 104,154.
- **A DOCSYNC marker with no generator**: `FEATURE_FLAGS` in README looked
  auto-synced; no template exists for it (nothing in scripts/, .github/).
- **4 of 6 docs_sync templates defined but planted nowhere** (BACKEND_STATS,
  VECTOR_STATS, EMBEDDING_FROZEN, LIVING_ORGANS — the last one lost its home
  in the T2.7 CLAUDE.md refactor and nobody noticed).
- **7 apps in NO documentation at all** (autonomous-lab, kb, kbli-navigator,
  nlm-bridge, openclaw-hgt-coordinator, osint-nexus-ui, team-agent); 9 apps
  have no README.md.
- **52/116 LaunchAgent plists documented nowhere** (neither
  automation_catalog.json nor AUTOMATIONS_REFERENCE.md).
- **19/33 runbooks orphans** (referenced by no other markdown).
- **Doc↔code gap** (freshness report §4): 15 apps whose code moved ≥30d after
  their README was last touched; worst: `apps/evaluator` (README 165d old,
  code 11d — gap 153d).
- One behavioral contradiction: AI_ONBOARDING note 3 said "`--no-verify` is
  OK" vs CLAUDE.md §8.12 "never `--no-verify`".

## 3. What changed (3 small PRs, auto-merged)

1. **PR #1936 — drift fixes** (content only): the 13 fixable dead refs, the
   Air-M4 onboarding block, the contradicting hand-written stats, the lying
   FEATURE_FLAGS marker demoted to an honest hand-maintained comment,
   `--no-verify` note aligned. DOCS_INVENTORY regenerated in the same commit.
2. **PR #1939 — generation extension**: 4 new stdlib-only extractors in
   docs_sync.py (`git ls-files`-based for local↔CI determinism): runbooks
   index → generated `docs/runbooks/README.md` (33 runbooks); workflows meta
   (anchored to `export const meta`); repo skills frontmatter (YAML
   folded-scalar aware); LaunchAgent documentation-coverage signaler. INDEX.md
   gains an auto-generated section (full 30-app table via the replanted
   LIVING_ORGANS template + workflows + skills + coverage). CI gate paths
   extended to all generation inputs; 10 unit tests run in the gate.
   Falsification probe passed: a new tracked runbook flips `--check` to rc=1.
3. **PR3 — freshness report**: `scripts/doc_freshness_report.py`
   (deterministic, zero-LLM, report-only): atlas dead-path scan, organ-arming
   ages vs declared cadence, coverage (plists 55%, apps without README),
   doc↔code pairing. 6 unit tests incl. innocence AND guilt fixtures (#3
   family). Armed via `doc-freshness.yml` workflow_dispatch (fetch-depth 0
   for git ages) + runnable from the existing guardian cron. This map file.

**Numbers (Law 7, before → after)**: atlas dead paths 15 → **0**
(script-verified); apps enumerated in the atlas 13 → **30** (mechanical);
runbooks indexed 0 → **33**; markers-without-generator 1 → 0; dead docs_sync
targets 1 → 0; unplanted templates 4 → 3 (see §5); plist coverage unchanged at
**55% but now VISIBLE** in INDEX.md and re-measured on every regen.

## 4. §Meta-pattern (the malattia-delle-malattie)

Every finding above is one disease: **documentation is trusted in proportion
to how auto-generated it LOOKS, not how auto-generated it IS.**

- A DOCSYNC marker with no generator (FEATURE_FLAGS) is the pure form: the
  costume of automation worn by frozen hand-writing.
- INDEX.md pointing to "auto-synced metrics in CLAUDE.md" after F44 removed
  those markers: the POINTER to automation outlived the automation.
- Hand-written counts beside a generated block: the reader cannot tell which
  number is alive, so both inherit the credibility of the generated one.
- AUTOMATIONS_REFERENCE.md: generated once, never re-armed — "generated" in
  provenance but hand-frozen in behavior (Esiste≠Armato, W81, at the
  doc layer).
- LIVING_ORGANS: a working generator whose OUTPUT SLOT was refactored away —
  automation without a home is indistinguishable from no automation.

The single defective belief: *"writing documentation = documenting"*. A doc
that enumerates changing reality is a RUNTIME, not an artifact — it needs an
arming state, a cadence, and a gate, exactly like a daemon. The structural
antidote shipped here: every enumerable section is either (a) generated with
its inputs in the CI gate's paths, or (b) explicitly labeled hand-maintained,
or (c) measured by the freshness report. No fourth state — "looks generated" —
is allowed to exist.

Corollary (measurement honesty): PR #1939's generated runbook index kills the
*orphan metric* for runbooks (every runbook now has ≥1 inbound ref) without
killing the *disease* (nobody contextually points at them). The freshness
report's doc↔code section keeps the real signal. When a fix satisfies the
metric, re-derive what the metric was a proxy FOR.

## 5. §Solo-operatore (physical / strategic / operator-only)

1. **VADEMECUM.md aspirational refs** (`PRICING_REFERENCE.md`,
   `VISA_TYPES_REFERENCE.md`, VADEMECUM:413-414): operator voice (Legge 5) —
   decide: write those reference docs, or delete the two lines. Not touched
   by agents.
2. **Arm docs_history_analyzer.py** (DOCS_TRENDS, monthly): needs a new cron
   entry — new crons are operator-gated (AUTONOMOUS_OPS L2). Suggested: one
   line in the Pro crontab next to docs-guardian, monthly.
3. **Give generate_automations_reference.py a cadence**: it must run on Pro
   (scans live crontab+launchctl on Pro+Mini via ssh). Suggested: append to
   the existing docs-guardian Sunday cron line. This single arming closes
   most of the 45%-undocumented-plist gap mechanically.
4. **automation_catalog.json strategy call**: hand-maintained, 2.5 months
   stale, 46 entries vs 117 plists. Either commit to feeding it (it is the
   declared source in VADEMECUM §1) or demote it and let
   AUTOMATIONS_REFERENCE.md (generated) be canonical. Contradictory truth
   sources are the W86 disease at the catalog level.
5. **9 apps without README.md** (`autonomous-lab`, `cell`, `kb`,
   `kbli-navigator`, `nlm-bridge`, `openclaw-hgt-coordinator`,
   `osint-nexus-ui`, `research`, `team-agent`): the generated INDEX table now
   shows them with an EMPTY role cell — the gap is visible. Writing the
   READMEs needs owner knowledge of intent (some are operator experiments).
6. **3 remaining unplanted templates** (BACKEND_STATS, VECTOR_STATS,
   EMBEDDING_FROZEN): decide to plant (e.g. EMBEDDING_FROZEN into
   AI_ONBOARDING's frozen-model section) or delete. Left untouched to keep
   PR #1939 scoped; they are inert but re-create the "defined, planted
   nowhere" state this mandate found.
7. **Fleet alignment**: Pro/Mini/M5 main checkouts must pull post-merge —
   Pro and Mini pulls are hook/sibling-blocked, M5 airborne (existing
   PENDING-ALIGN lines in `.claude/skills/modus/PENDING-ARMS.md` carry this;
   the weekly guardian cron on Pro runs from the Pro main checkout, so its
   docs_sync copy stays v1 until that pull lands — outputs stay correct, it
   simply won't regenerate the new markers until then).

## 6. Operating rules going forward (the loop, one paragraph)

Adding a runbook / workflow / repo skill / plist / app README → run
`python scripts/docs_sync.py` in the same commit (the `docs-sync.yml` gate
fails the PR otherwise — probed, it bites). Weekly: docs-guardian (Pro cron)
refreshes the inventory, auto-archives orphans, auto-fixes links. On demand /
suspicion: `python scripts/doc_freshness_report.py` (or the `doc-freshness`
workflow_dispatch) shows dead paths, un-armed organs, coverage, and doc↔code
gaps — report-only, the human decides. Hand-written narrative (SYMBIOSIS,
VADEMECUM, INDEX prose) stays human; everything enumerable is generated.
