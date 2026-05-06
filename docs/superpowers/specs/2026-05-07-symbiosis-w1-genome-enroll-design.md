# Symbiosis W1 — Genome Enroll (26 → ~80 organi)

**Date**: 2026-05-07
**Branch**: `feat/symbiosis-W1-genome-enroll-2026-05-07`
**Doctrine ref**: PR #479 (`docs(symbiosis): turn-on plan 2026-05-06 ratified`, merged commit `1b97289283c2f17d049cf401e01afb8e1750e454`)
**Target**: enroll Wave 1 organs in `apps/organism/organism/genome.yaml`, expanding the registry from 26 entries to ~76-79 entries.

---

## 1. Goal

Expand `apps/organism/organism/genome.yaml` from the current 26 registered organs to ~76-79, enrolling all real organs running today on Pro + Mini that are currently invisible to the Innervation Genoma. Registry-only change — zero modifications to organ source code (vincolo inviolabile #5).

Doctrine ratified by Zero on 2026-05-06 14:55 WITA: mata-garuda enrolled exposing **operational metadata only** (heartbeat, last_activity, error_count, items_processed). NO OSINT content via observatory.

## 2. Topology constraints (verified empirically by Zero, 2026-05-06 22:45 WITA)

`launchctl list` on both machines via Tailscale produced this active-active layout for `com.matagaruda.*`:

| Class | Count | Detail |
|---|---|---|
| Pro `com.matagaruda.*` loaded | 16 | full label list verified |
| Mini `com.matagaruda.*` loaded | 15 | via `ssh mini-remote` |
| Active-active duplicates (12) | 12 | `watcher.daily`, `reg-alert.30min`, `kg-linker`, `wr-topic`, `wr2-bridge`, `bridge.adaptive`, `sentinel.daily`, `intel-bridge.daily`, `daily-briefing`, `kita-feed`, `public-channel`, `weekly-digest`, `gap.consumer` |
| Pro-only | 3 | `invalidation-sweep`, `nlm-feeder-stream.hourly`, `nlm-expander.weekly` |
| Mini-only | 2 | `ner-worker.hourly` (Ollama qwen3.5 GPU on Mini), `normalizer.hourly` |

(The 12 + 3 + (15-12)=3 = 31 entries case — Mini-3 already includes the 2 Mini-only above; the 13th Mini service is a distinct duplicate-pair that the verification listed as 12+1, see commit body for breakdown.)

WR2 LaunchAgents on Pro: 16 plist files, 14 not yet enrolled (`wr2.oracle`, `wr2.supervisor`, `wr2.newsletter` already in genome). All scheduled by `wr2.supervisor` daemon — no `StartInterval` / `StartCalendarInterval`.

Pro background `com.nuzantara.*` plists not yet enrolled (~5-8): codex runners (autofix-ci, coverage-improver, overnight-feeder, overnight-runner, research-actor), cost-advisor (daily-cap, weekly), claude-max-usage-watcher, secrets-sync-mini, openclaw-children-watchdog, vector-reindex-check, nb-intel-delta-watcher.hourly, sentinel-meta-watchdog, federation-alert-dispatcher.

## 3. Schema decisions ratified (D1-D8)

**D1 — Validator schema extension.** Add `mini_launchd` to `_RUNTIMES` in `apps/organism/organism/tools/validate_genome.py:30`. Precondition for everything else.

**D2 — Active-active duplicate representation.** Separate entries per machine:

```yaml
- id: mata_garuda.intel_bridge_daily.pro
  runtime: pro_launchd
  ...
  duplicates_id: mata_garuda.intel_bridge_daily.mini
- id: mata_garuda.intel_bridge_daily.mini
  runtime: mini_launchd
  ...
  duplicates_id: mata_garuda.intel_bridge_daily.pro
```

`duplicates_id` is an OPTIONAL convention field (header-documented), validator does not enforce it (validator currently accepts unknown optional fields silently). Strict typing of `duplicates_id` is a future follow-up PR (~30 min).

**D3 — Active-active duplicates are out of scope for this PR.** Resolution of double-firing risk is documented as a P1 STRUCTURAL cicatrix entry (commit 4); cleanup is a separate PR.

**D4 — Target.** ≥75 entries final. Estimate breakdown:
- B1 matagaruda Pro 16 + Mini 15 = 31 entries (with 24 cross-linked via `duplicates_id`, i.e. 12 pairs)
- B2 WR2 Pro 13 (16 plist - 3 already enrolled: oracle, supervisor, newsletter) + Pro background 5-8 = 18-21 entries
- + 26 existing = **~75-78 final**

**D5 — Commit cadence.** WIP commit every ~90 min, push within 30s of every commit. Wave 2 Pro 2026-04-29 used 90-min cadence successfully on similar registry-only work; the 10-min MOS rule applies to large untracked design docs (>5KB), not single-file tracked YAML edits. Branch hijack mitigation: `ps aux | grep -c claude` <3 at session start.

**D6 — `mini_launchd` recovery.** `recovery_action: launchctl_kickstart` with `recovery_params: {host: "mini", label: "<full-label>"}`. Cross-machine kickstart requires SSH via Tailscale alias `mini-remote` (Mini IP `100.93.236.6`), NOT `localhost`. Documented in genome.yaml header preamble.

**D7 — `duplicates_id` typing.** Header-only convention. Validator left untouched. Premature optimization to add a typed schema for it now; future PR if/when strict cross-id resolution is desired.

**D8 — agents/workers classifier.**
- Mata-garuda agents: `grep -l "@register_agent" apps/mata-garuda/mata_garuda/agents/*.py` → 29 decorated files (excluding `__init__.py` which only runs the auto-loader, and `_goid_base.py` which is shared utility). Verified empirically.
- Mata-garuda workers: B2-workers SKIPPED. The plist-driven workers (`ner_worker`, `normalizer`, `gap_consumer`, `kg_linker`, `nlm_feeder`) are already enrolled via the matagaruda plist entries in B1. The remaining `.py` files in `mata_garuda/workers/` (`base_worker`, `classifier_worker`, `contradiction_worker`, `dedup_worker`, `embedder_worker`, `gap_legacy`, `scorer`, `semantic_diff_worker`) are library/utility code OR Redis-stream consumers spawned on-demand by the registry — not standalone organs. Adding them as registry entries would be noise.

## 4. Architecture

**Single PR / 4 commit** on `feat/symbiosis-W1-genome-enroll-2026-05-07`. Registry-only changes confined to:

- `apps/organism/organism/tools/validate_genome.py` (1-line `_RUNTIMES` extension, commit 1)
- `apps/organism/organism/genome.yaml` (header preamble + 50ish new entries across commits 1-3)
- `.claude/rules/cicatrix-scars.md` (1 STRUCTURAL entry, commit 4)
- This design doc (commit 0)

NO modifications to:
- Organ source code (mata-garuda, WR2, Pro background scripts)
- Existing 26 genome entries (their `id`, `dependencies`, `recovery_*` stay byte-identical)
- Plist files in `~/Library/LaunchAgents/`
- `.claude/rules/cicatrix-scars-archive.md`

## 5. Components

### 5.1 Validator extension (commit 1)

`apps/organism/organism/tools/validate_genome.py:30` change:

```python
_RUNTIMES = frozenset({
    "pro_launchd",
    "mini_launchd",   # NEW — Modo B 2-node topology
    "air_launchd",
    "air_cron",
    "fly_machine",
    "vercel_function",
    "github_actions",
    "mcp_session",
    "backend_internal",
})
```

The `air_*` entries stay for archeological reasons (refs in scripts/runbooks, not active paths post-2026-05-05 Air decommission).

### 5.2 Genome.yaml header preamble update (commit 1)

Replace the "149 organi nervosi" cap-promise (lines 1-26) with a doctrine-aligned preamble that:

1. States current target: ~80 registered organs in W1, climbing to 100+ in W2.
2. Documents the `duplicates_id` convention for active-active Pro+Mini organs (cross-references peer; does NOT enforce single runtime).
3. Documents `mini_launchd` runtime + `recovery_params.host: "mini"` requirement for cross-machine kickstart.
4. Re-applies after every `python -m organism.tools.validate_genome --update-checksum` (yaml.safe_dump strips comments, validator-confirmed at line 263).

### 5.3 Genome.yaml entries — Batch B1 matagaruda (commit 2)

31 new entries. Naming: `mata_garuda.<service_underscored>.{pro|mini}`.

Example pair (intel_bridge.daily, active-active):

```yaml
  - id: mata_garuda.intel_bridge_daily.pro
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 90000  # daily cron, 25h grace
    owner_module: apps/mata-garuda/scripts/run_intel_bridge.py
    dependencies:
      - infra.redis
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.matagaruda.intel-bridge.daily
    severity_on_silence: warning
    cicatrix_refs: []
    duplicates_id: mata_garuda.intel_bridge_daily.mini
  - id: mata_garuda.intel_bridge_daily.mini
    runtime: mini_launchd
    type: cron
    expected_hb_seconds: 90000
    owner_module: apps/mata-garuda/scripts/run_intel_bridge.py
    dependencies:
      - infra.redis
    recovery_action: launchctl_kickstart
    recovery_params:
      host: mini
      label: com.matagaruda.intel-bridge.daily
    severity_on_silence: warning
    cicatrix_refs: []
    duplicates_id: mata_garuda.intel_bridge_daily.pro
```

Type derivation rules (`expected_hb_seconds = expected_period + 1h grace`):
- `StartCalendarInterval` daily (single Hour/Minute) → `cron`, `expected_hb_seconds = 86400 + 3600 = 90000`.
- `StartCalendarInterval` weekly (Weekday + Hour/Minute) → `cron`, `expected_hb_seconds = 604800 + 86400 = 691200` (1 day grace for weekly).
- `StartInterval = N` seconds → `cron`, `expected_hb_seconds = N + 3600` (1h grace minimum, scaled if N is small e.g. minutely).
- Neither schedule present + `KeepAlive=true` OR `RunAtLoad=true` → `daemon`, `expected_hb_seconds = 60-180` per organ class.
- Mata-garuda Python agent without plist (orchestrated by meta_agent) → NOT enrolled in B1 (see §5.3 paragraph below).

For the matagaruda agents NOT directly mapped to a plist (e.g. `lhkpn_harvester`, `kemkumham_harvester`, `bkpm_harvester`, `kemlu_harvester`, `imigrasi_harvester`, `arxiv_harvester`, `github_trending_harvester`, `youtube_intel_harvester`, `reddit_listener`, `tavily_research`, `exa_search`, `code_patch_proposer`, `meta_agent`, `meta_cognition_agent`, `dummy_agent`, `source_health_agent`, `ai_digest_agent`, `ai_newsletter_harvester`, `ai_twitter_harvester`): they are NOT enrolled in B1. They are agent classes invoked by the orchestrator and don't have an independent heartbeat — enrolling them creates phantom alerts. B1 covers ONLY the 16 Pro + 15 Mini matagaruda **launchd-loaded** organs.

### 5.4 Genome.yaml entries — Batch B2 WR2 + Pro background (commit 3)

**WR2 Pro 13 entries** (16 plist files - 3 already enrolled: `wr2.oracle`, `wr2.supervisor`, `wr2.newsletter`):

```
canva_apply, connector, dossier_compiler, draft_generator, hardening,
image_generator, learner_nightly, measurer, pg_proxy, sla_worker,
strategos, topic_selector, trend_hunter
```

13 entries, full list. Verified empirically at design time via `ls ~/Library/LaunchAgents/com.balizero.wr2.*.plist` minus genome.yaml current entries.

Naming: `wr2.<service_underscored>` (e.g. `wr2.draft_generator`). All `runtime: pro_launchd`, `type: daemon` (no schedule = supervisor-driven), `expected_hb_seconds: 300-600` (supervisor's tick interval), dependencies include `wr2.supervisor` + relevant infra. Recovery: `launchctl_kickstart` + `host: pro`.

**Pro background 5-8 entries** (selected from these candidates by classify rules §5.3):

| Candidate id | LaunchAgent label | Likely type |
|---|---|---|
| `pro.codex_autofix_ci` | `com.nuzantara.codex-autofix-ci` | cron |
| `pro.codex_coverage_improver` | `com.nuzantara.codex-coverage-improver` | cron |
| `pro.codex_overnight_feeder` | `com.nuzantara.codex-overnight-feeder` | cron |
| `pro.codex_overnight_runner` | `com.nuzantara.codex-overnight-runner` | cron |
| `pro.codex_research_actor` | `com.nuzantara.codex-research-actor` | cron |
| `pro.cost_advisor_daily_cap` | `com.nuzantara.cost-advisor-daily-cap` | cron |
| `pro.cost_advisor_weekly` | `com.nuzantara.cost-advisor-weekly` | cron |
| `pro.claude_max_usage_watcher` | `com.nuzantara.claude-max-usage-watcher` | daemon |
| `pro.openclaw_children_watchdog` | `com.nuzantara.openclaw-children-watchdog` | cron |
| `pro.nb_intel_delta_watcher` | `com.nuzantara.nb-intel-delta-watcher.hourly` | cron |
| `pro.sentinel_meta_watchdog` | `com.nuzantara.sentinel-meta-watchdog` | cron |
| `pro.federation_alert_dispatcher` | `com.nuzantara.federation-alert-dispatcher` | cron |
| `pro.vector_reindex_check` | `com.nuzantara.vector-reindex-check` | cron |
| `pro.secrets_sync_mini` | `com.nuzantara.secrets-sync-mini` | cron |

Selection rule at commit time: enroll only candidates that are (a) launchd-loaded, (b) have a clear schedule OR KeepAlive directive, (c) have a non-empty owner_module that maps to a real script in the monorepo. Skip candidates that are utility wrappers calling other organs already enrolled.

Expected final count: 6-8. If fewer are eligible after applying the rule, the total will dip toward the lower end of the 75-78 final-target range — still ≥75.

### 5.5 Cicatrix entry (commit 4)

`.claude/rules/cicatrix-scars.md` new entry under "STRUCTURAL" section:

```
### ⚠️ STRUCTURAL: 12 mata_garuda LaunchAgents active-active Pro+Mini (2026-05-07)
```

Body (TRAUMA / ANTIBODY / GOTCHA per file convention):
- TRAUMA: 12 launchd labels loaded simultaneously on Pro AND Mini, dup_resolver `~/scripts/wave1-pro-mini-dup-resolver.sh` is currently inert when Mini is offline (SessionStart 2026-05-04 14:40 confirmed). Risk: double-firing for cron jobs (e.g. `intel-bridge.daily` could publish to garuda:raw twice on the same day — Redis dedup is per-event, not per-source).
- ANTIBODY (proposed, follow-up PR): leader-election by hostname for active-active labels; OR explicit Pro-only / Mini-only split via plist removal on one side; OR shared lock in Redis with TTL=interval. Out of scope for this PR.
- GOTCHA: enrollment in genome.yaml uses `duplicates_id` cross-references but does NOT resolve double-firing — registry is observability, not coordination. The Supervisor will surface heartbeats from both sides; metrics dashboard will show 2× expected `items_processed` until cleanup PR ships. Severity: P1 (operational drift, not crash). Follow-up: dedicated cleanup PR, owner Zero.

## 6. Data flow (per organ)

```
plist file (~/Library/LaunchAgents/com.<ns>.<label>.plist)
   |
   +-> read: Label, ProgramArguments, StartInterval/StartCalendarInterval, KeepAlive, RunAtLoad
   +-> classify: type ∈ {cron, daemon, agent}
   +-> derive: expected_hb_seconds (cron interval + grace; daemon 60-180; agent 0)
   +-> derive: owner_module (relative monorepo path, e.g. apps/mata-garuda/scripts/run_X.py)
   +-> deps: [infra.* ids OR sibling organ ids only — must resolve in genome.yaml]
   +-> recovery_action: launchctl_kickstart
   +-> recovery_params: {host: "pro"|"mini", label: "<full label>"}
   +-> severity: critical (infra) | error (revenue path) | warning (cron) | info (supervisor-managed)
   +-> cicatrix_refs: [] default
   +-> duplicates_id: <peer_id> if active-active
genome.yaml entry (YAML mapping under organs:)
```

## 7. Error handling

- **Validator failure** post-edit: `git reset --soft HEAD^` + edit + recommit. NEVER `--no-verify`. Common causes:
  - Dependency cycle (e.g. typo creating self-ref or peer cycle)
  - Unknown dependency id (typo in `dependencies:` list)
  - Invalid `runtime` / `type` / `recovery_action` / `severity_on_silence` (validator rejects unknown enum values)
  - Checksum mismatch (forgot to re-run `--update-checksum` or the preamble re-apply corrupted YAML structure — validate with `python -c "import yaml; yaml.safe_load(open('apps/organism/organism/genome.yaml'))"`)
- **`yaml.safe_dump` strips comments** after `--update-checksum` (validator line 263, confirmed empirically): re-apply preamble manually via Edit tool, NOT Write (preserves indentation of organs list).
- **Branch hijack mitigation**: WIP commit every ~90 min on the design doc + genome.yaml + validator + cicatrix scope (`git add` explicit paths, NEVER `git add -A` from worktree root), commit, push within 30s. Pre-session check `ps aux | grep -c claude` <3.
- **Plist not found** during enrollment (e.g. `com.matagaruda.foo.plist` referenced in `launchctl list` but file missing): skip the entry, log to commit body as "BLOCKED — file missing, follow-up". Do not invent metadata.
- **Mini SSH unreachable** during validation: validator runs locally on YAML only — does NOT cross-check launchctl on Mini. Mini-side verification is post-merge, owner Zero. If suspected drift, run `ssh mini-remote launchctl print gui/$(id -u)/com.matagaruda.<label>` post-merge to confirm enrollment matches reality.

## 8. Testing

### Pre-commit hook (REQUIRED, runs after every commit)

```bash
python -m organism.tools.validate_genome apps/organism/organism/genome.yaml
```

Exit 0 = PASS. The pre-commit hook is wired upstream (NB-1 ADR-7 HALT-on-mismatch); refusing to commit on checksum / schema failures is an enforced invariant.

### Sample launchctl print round-trip (manual, post-commit)

For each batch, sample 1-2 enrolled organs and verify the plist matches the genome entry:

```bash
launchctl print "gui/$(id -u)/com.nuzantara.cpu-monitor" | grep -E "(Label|StartInterval|KeepAlive|Program)"
# compare against pro.cpu_monitor entry in genome.yaml
```

For Mini-resident organs, post-commit (not blocking, deferred to merge time):

```bash
ssh mini-remote 'launchctl print gui/$(id -u)/com.matagaruda.ner-worker.hourly'
```

### OSINT field leak guard

```bash
git diff main...HEAD -- apps/organism/organism/genome.yaml | grep -E "^\+.*(content|payload|entity|osint)"
```

Must return EMPTY. Any match = abort, clean, recommit. Vincolo inviolabile #3 (mata-garuda enrollment exposes operational metadata only).

### Tri-LLM cross-check (relaxed 2/3, pre-merge)

DeepSeek (always) + Gemini OR NotebookLM (one of two if available — Wave 2 Pro 2026-04-29 confirmed 2/3 sufficient on capacity-exhaustion days). Prompt: "Read genome.yaml after my edits. Identify any LaunchAgents on Pro/Mini that are NOT enrolled but should be." Append findings to PR body.

## 9. Build sequence (4 commits + design doc)

| # | Commit | Files | Validator | Push |
|---|---|---|---|---|
| 0 | `docs(symbiosis): W1 genome enroll design doc` | this file | — | within 30s |
| 1 | `feat(validator): add mini_launchd runtime per Modo B 2-node topology` | validator + genome preamble | PASS | within 30s |
| 2 | `feat(organism): enroll matagaruda Pro 16 + Mini 15 (active-active dup tracking)` | genome.yaml +31 entries | PASS | within 30s |
| 3 | `feat(organism): enroll WR2 Pro 14 + Pro background crons` | genome.yaml +19-22 entries | PASS | within 30s |
| 4 | `docs(cicatrix): document mata_garuda 12 active-active LaunchAgent dup STRUCTURAL P1` | cicatrix-scars.md | PASS | within 30s |

Cumulative target after commit 3: ~76-79 entries. Post-commit-3 the validator must report `✓ genome.yaml valid` for the registry to be in W1-final state. Commit 4 is documentation-only (no genome.yaml change, checksum unaffected).

## 10. PR deliverable

**Title**: `feat(organism): enroll Wave 1 organs in Innervation Genoma (26→~80)`

**Body** (template):

```markdown
## Summary

Wave 1 of the Symbiosis Turn-On Plan (PR #479 Fase 1). Enrolls ~50 new organs
in `apps/organism/organism/genome.yaml`, expanding the registry from 26 to
~76-79 entries.

## Topology decisions

- New runtime `mini_launchd` for Modo B 2-node topology (Pro+Mini)
- Active-active duplicates (12 mata_garuda labels) tracked via `duplicates_id`
  cross-reference field (header-only convention, validator unmodified)
- Cross-machine recovery via `recovery_params.host: "mini"` + Tailscale alias
  `mini-remote`

## Batches

| Batch | Scope | Entries |
|---|---|---|
| B1 | mata_garuda Pro 16 + Mini 15 (active-active) | 31 |
| B2 | WR2 Pro 13 + Pro background crons (5-8) | 18-21 |
| C  | Cicatrix entry: 12 active-active dup P1 STRUCTURAL | 0 (docs) |

Total final: ~75-78 organs (≥75 target met).

## Verification

- [x] Pre-commit `validate_genome` PASS at every commit
- [x] OSINT field leak grep clean (`content|payload|entity|osint` absent in additions)
- [x] Sample `launchctl print` round-trip on Pro (1-2 organs per batch)
- [ ] Mini-side `launchctl print` verification (post-merge, owner Zero)
- [x] Tri-LLM cross-check 2/3: DeepSeek + (Gemini OR NB-1)

## Follow-ups

- P1 cleanup: resolve 12 active-active double-firing (scar entry commit 4)
- Future: strict typing of `duplicates_id` in validator (~30 min PR)
- Future: enrollment of mata-garuda agent classes (orchestrated by meta_agent,
  no independent heartbeat — needs design)

## Refs

- Doctrine: PR #479 (`1b97289283c2f17d049cf401e01afb8e1750e454`)
- NB-1 ADR-7: HALT-on-checksum-mismatch enforcement
- Cicatrix open: branch hijack STRUCTURAL (mitigated via 90-min WIP cadence + push 30s)
```

## 11. Out of scope

- Resolving 12 mata_garuda active-active double-firing (P1 follow-up)
- Strict validator typing of `duplicates_id` (premature optimization)
- Enrollment of mata-garuda agent classes (`lhkpn_harvester`, `arxiv_harvester`, etc — orchestrated by meta_agent, no plist, no independent heartbeat)
- Enrollment of mata-garuda worker library files (`base_worker`, `classifier_worker`, etc — utility code, not standalone organs)
- Enrollment of `nuz-sync` (explicitly quarantined by 2026-04-29 branch hijack scar — recovery loop danger)
- Pruning the existing 26 entries (no change to existing registry semantics)
- Touching `redundancies.yaml` (separate concern: chi è duplicato, not chi esiste)
- Code changes to organs (vincolo inviolabile #5)
