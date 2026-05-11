# Symbiosis W1 — Genome Enroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `apps/organism/organism/genome.yaml` from 26 to ~75-78 enrolled organs in 4 atomic commits on `feat/symbiosis-W1-genome-enroll-2026-05-07`, validator pre-commit PASS at every step.

**Architecture:** Registry-only edits to 3 files (`apps/organism/organism/tools/validate_genome.py`, `apps/organism/organism/genome.yaml`, `.claude/rules/cicatrix-scars.md`). Zero changes to organ source code. New runtime `mini_launchd` for Modo B 2-node topology; `duplicates_id` cross-link convention for 12 active-active mata_garuda labels.

**Tech Stack:** Python (validator only), YAML (genome registry), launchd plist files (read-only inspection), pre-commit hook with `python -m organism.tools.validate_genome`.

**Spec ref:** [`docs/superpowers/specs/2026-05-07-symbiosis-w1-genome-enroll-design.md`](../specs/2026-05-07-symbiosis-w1-genome-enroll-design.md) (commit `c4be7db87`).

**Doctrine ref:** PR #479 `1b9728928` Symbiosis Turn-On Plan ratified 2026-05-06 14:55 WITA.

---

## File map

| File                                                | Action                                                                     | Touched in    |
| --------------------------------------------------- | -------------------------------------------------------------------------- | ------------- |
| `apps/organism/organism/tools/validate_genome.py`   | Modify (1-line `_RUNTIMES` extension)                                      | Task 1        |
| `apps/organism/organism/genome.yaml`                | Modify (preamble + 50ish entries across 3 commits)                         | Tasks 1, 2, 3 |
| `apps/organism/tests/tools/test_validate_genome.py` | Modify (add `mini_launchd` runtime test, if file exists; otherwise create) | Task 1        |
| `.claude/rules/cicatrix-scars.md`                   | Modify (1 STRUCTURAL entry)                                                | Task 4        |

Working directory: `/Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1` (worktree on branch `feat/symbiosis-W1-genome-enroll-2026-05-07`).

---

## Pre-flight (run ONCE before Task 1)

- [ ] **P.1: Confirm worktree state**

```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
git status
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
```

Expected output:

- `On branch feat/symbiosis-W1-genome-enroll-2026-05-07`
- HEAD = `c4be7db87` (design-doc commit) or later
- Working tree clean

If working tree is not clean, STOP and reconcile before proceeding.

- [ ] **P.2: Confirm pre-commit hook exists and runs validator**

```bash
ls -la .git/hooks/pre-commit 2>&1 | head -3
git config --get core.hooksPath
ls -la apps/organism/organism/tools/post_commit_hook.py 2>&1 | head -3
```

Note: `apps/organism/organism/tools/post_commit_hook.py` is the in-tree post-commit hook reference. The pre-commit invocation pattern is `python -m organism.tools.validate_genome apps/organism/organism/genome.yaml`. If the hook is missing, the validator must be invoked manually after every edit (Task steps below include the manual invocation).

- [ ] **P.3: Locate and run the existing validator on the unmodified file**

```bash
cd apps/organism
python -m organism.tools.validate_genome organism/genome.yaml
echo "exit=$?"
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: `✓ genome.yaml valid (organism/genome.yaml)` and exit code 0.

If exit code is non-zero, STOP — the registry is broken on `main` and must be fixed first.

- [ ] **P.4: Confirm validator test file location**

```bash
find apps/organism -name "test_validate_genome*" -o -name "tests/tools/*" 2>&1 | head -10
ls apps/organism/tests/ 2>&1
```

If `apps/organism/tests/tools/test_validate_genome.py` exists, modify it in Task 1. If not, create it in Task 1.

- [ ] **P.5: Pre-session concurrent-claude check (branch hijack antibody)**

```bash
ps aux | grep -c "[c]laude"
```

Expected: 1 or 2 (current session + max one claude-max-usage-watcher cron tick). If 3+, STOP and ask Zero which to kill (cicatrix branch hijack STRUCTURAL).

---

## Task 1: Validator extension (`mini_launchd` runtime) + genome.yaml header preamble

**Goal of this task:** add `mini_launchd` to the validator's allowed runtimes and update `genome.yaml` header to document the new runtime + `duplicates_id` convention. Final state: validator PASS on the modified genome.yaml; checksum recomputed.

**Files:**

- Modify: `apps/organism/organism/tools/validate_genome.py:28-37` (extend `_RUNTIMES`)
- Modify: `apps/organism/organism/tools/validate_genome.py:71-79` (no change — checksum function stays as-is, just verify)
- Modify: `apps/organism/tests/tools/test_validate_genome.py` (add test for `mini_launchd`; if missing, create)
- Modify: `apps/organism/organism/genome.yaml:1-26` (replace header preamble)

### Step 1.1: Write the failing test for `mini_launchd` runtime

- [ ] **1.1.a: Locate or create the test file**

If `apps/organism/tests/tools/test_validate_genome.py` exists, open it and append the test below. Otherwise create the file with this content (the imports section adapts to existing convention if the file already exists).

```python
"""Tests for organism.tools.validate_genome."""
from __future__ import annotations

from organism.tools.validate_genome import (
    _RUNTIMES,
    compute_checksum,
    validate_data,
)


def _organ(**overrides):
    base = {
        "id": "test.organ",
        "runtime": "pro_launchd",
        "type": "daemon",
        "expected_hb_seconds": 60,
        "owner_module": "tests/fixtures/test.py",
        "dependencies": [],
        "recovery_action": "launchctl_kickstart",
        "severity_on_silence": "warning",
    }
    base.update(overrides)
    return base


def test_mini_launchd_is_an_allowed_runtime():
    """`mini_launchd` must be in the runtime allowlist (Modo B 2-node topology)."""
    assert "mini_launchd" in _RUNTIMES


def test_validate_data_accepts_mini_launchd_runtime():
    organs = [_organ(runtime="mini_launchd")]
    data = {
        "version": 1,
        "checksum_algo": "sha256",
        "checksum": compute_checksum(organs),
        "organs": organs,
    }
    errors = validate_data(data)
    assert errors == []


def test_validate_data_rejects_unknown_runtime():
    organs = [_organ(runtime="plan9_rcd")]
    data = {
        "version": 1,
        "checksum_algo": "sha256",
        "checksum": compute_checksum(organs),
        "organs": organs,
    }
    errors = validate_data(data)
    assert any("invalid runtime 'plan9_rcd'" in err for err in errors)
```

If the test file already exists with similar fixtures, reuse the existing fixture helper instead of duplicating `_organ`.

- [ ] **1.1.b: Run the test to verify it fails**

```bash
cd apps/organism
python -m pytest tests/tools/test_validate_genome.py::test_mini_launchd_is_an_allowed_runtime -v 2>&1 | tail -20
echo "exit=$?"
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: FAIL with `AssertionError` because `mini_launchd` is not in the current `_RUNTIMES` frozenset. Exit code 1.

If the test infra is different (e.g. pytest collection ignores `tests/tools/`), invoke pytest with the explicit path: `python -m pytest <full-path-to-file>::<test_name> -v`. Adjust the working dir or set `PYTHONPATH` until collection succeeds.

### Step 1.2: Make the test pass — extend `_RUNTIMES`

- [ ] **1.2.a: Edit `validate_genome.py` line 28-37**

Open `apps/organism/organism/tools/validate_genome.py` and replace the `_RUNTIMES` frozenset:

```python
# Allowed enum values per 07_innervation_protocol.md §2.2.
_RUNTIMES = frozenset({
    "pro_launchd",
    "mini_launchd",  # 2026-05-07 — Modo B 2-node topology (Pro+Mini)
    "air_launchd",
    "air_cron",
    "fly_machine",
    "vercel_function",
    "github_actions",
    "mcp_session",
    "backend_internal",
})
```

- [ ] **1.2.b: Run the new tests**

```bash
cd apps/organism
python -m pytest tests/tools/test_validate_genome.py -v 2>&1 | tail -30
echo "exit=$?"
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: 3 tests PASS (`test_mini_launchd_is_an_allowed_runtime`, `test_validate_data_accepts_mini_launchd_runtime`, `test_validate_data_rejects_unknown_runtime`). Exit code 0. Existing tests in the file (if any) continue to pass.

### Step 1.3: Update genome.yaml header preamble

The current header (lines 1-26) promises "149 organi nervosi" and gives Wave-0 instructions. Replace it to reflect W1 reality + new conventions.

- [ ] **1.3.a: Read current preamble**

```bash
sed -n '1,32p' apps/organism/organism/genome.yaml
```

Confirm lines 1-26 are the preamble and line 27 starts the actual data (`version: 1`).

- [ ] **1.3.b: Replace preamble**

Edit `apps/organism/organism/genome.yaml`. Replace lines 1-26 (the comment block ending right before `version: 1`) with:

```yaml
# Genoma — registry of nervous organs in the Nuzantara Innervation system.
#
# This file is the SINGLE SOURCE OF TRUTH for "what organs exist, where they
# run, what their expected heartbeat is, and how to recover them when silent".
#
# Authoritative spec: docs/innervation-2026-04-29/07_innervation_protocol.md §2.
# Doctrine ref: PR #479 (Symbiosis Turn-On Plan ratified 2026-05-06).
# Validation: `python -m organism.tools.validate_genome` (pre-commit hook + CI).
# HALT-on-checksum-mismatch (NB-1 ADR-7).
#
# Wave 1 scope (2026-05-07): registry expanded from 26 to ~75-78 organs.
# Includes mata_garuda Pro+Mini active-active labels, WR2 Pro daemons under
# wr2.supervisor, and Pro background crons. Wave 2 target: 100+ organs.
#
# Conventions
#
# - Active-active organs (same label loaded simultaneously on Pro AND Mini)
#   are enrolled as TWO separate entries — one per machine — with the
#   `runtime` field distinguishing them. The optional `duplicates_id` field
#   cross-references the peer entry on the other machine. Validator does
#   NOT enforce duplicates_id (header-only convention; future PR may type
#   it strictly). Resolution of double-firing is tracked separately —
#   see cicatrix-scars.md "12 mata_garuda LaunchAgents active-active".
#
# - `mini_launchd` runtime entries set `recovery_params.host: "mini"` and
#   `recovery_params.label: <full-launchd-label>`. Cross-machine recovery
#   requires SSH via the Tailscale alias `mini-remote` (Mini IP
#   100.93.236.6), NOT localhost. The Supervisor MUST resolve `host: "mini"`
#   to a remote launchctl invocation; never attempt local kickstart of a
#   Mini-resident organ.
#
# Editing notes for future Claudes
#
# - Run `python -m organism.tools.validate_genome --update-checksum` after
#   every edit. The validator REJECTS the file when the recorded checksum
#   does not match the canonical SHA256 (NB-1 ADR-7 enforcement).
# - `yaml.safe_dump` (used by --update-checksum) STRIPS comments. Re-apply
#   this header BY HAND after every checksum recompute, OR switch to
#   ruamel.yaml in a follow-up. For W1 we tolerate the manual step.
# - `dependencies` MUST resolve to ids in this file. External infra (PG,
#   Redis, Qdrant) gets explicit `infra.*` entries below.
# - Branch-hijack antibody: WIP commit + push within 30s of any edit when
#   working in a long Claude session (see cicatrix-scars STRUCTURAL).
```

The exact existing-line replacement uses your editor's Edit tool. Verify the replacement preserves the blank line before `version: 1`.

### Step 1.4: Recompute checksum + re-apply preamble

`yaml.safe_dump` strips comments — the preamble disappears. The fix is to recompute, then re-apply.

- [ ] **1.4.a: Run `--update-checksum`**

```bash
cd apps/organism
python -m organism.tools.validate_genome organism/genome.yaml --update-checksum
echo "exit=$?"
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: prints `checksum updated: <new-sha256>`, exit code 0.

- [ ] **1.4.b: Verify the preamble was stripped**

```bash
head -5 apps/organism/organism/genome.yaml
```

Expected: starts with `version: 1` (no comment block). Confirms the strip happened.

- [ ] **1.4.c: Re-apply preamble via Edit**

Edit `apps/organism/organism/genome.yaml`. Insert the preamble from step 1.3.b BEFORE line 1 (`version: 1`). Use the Edit tool's exact-match feature on `version: 1\nchecksum_algo: sha256` to insert the preamble right above it.

- [ ] **1.4.d: Run validator to confirm**

```bash
cd apps/organism
python -m organism.tools.validate_genome organism/genome.yaml
echo "exit=$?"
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: `✓ genome.yaml valid` and exit code 0. Comments do not affect checksum (validator parses YAML, hashes only the `organs` list).

### Step 1.5: Commit + push within 30s

- [ ] **1.5.a: Stage scoped paths**

```bash
git add apps/organism/organism/tools/validate_genome.py
git add apps/organism/organism/genome.yaml
git add apps/organism/tests/tools/test_validate_genome.py
git status --short
```

Expected: 3 files staged with `M` or `A` markers, no other paths.

- [ ] **1.5.b: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(validator): add mini_launchd runtime per Modo B 2-node topology

Extends `_RUNTIMES` allowlist in apps/organism/organism/tools/validate_genome.py
to include `mini_launchd` for organs running on Mini-Pro2.local (Modo B
companion node, post-Air decommission 2026-05-05).

Updates genome.yaml header preamble to document:
- Wave 1 scope (26 → ~75-78 organs)
- `duplicates_id` cross-link convention for active-active Pro+Mini organs
- `recovery_params.host: "mini"` + Tailscale alias `mini-remote` for
  cross-machine recovery via SSH

Adds 3 unit tests for the validator runtime allowlist.

Doctrine ref: PR #479 Symbiosis Turn-On Plan (1b9728928).
Spec: docs/superpowers/specs/2026-05-07-symbiosis-w1-genome-enroll-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **1.5.c: Push within 30s**

```bash
git push origin feat/symbiosis-W1-genome-enroll-2026-05-07
```

Expected: push success, branch already tracked.

---

## Task 2: Enroll matagaruda Pro 16 + Mini 15 (Batch B1)

**Goal of this task:** add 31 entries to `genome.yaml` (16 Pro + 15 Mini), with 12 cross-linked pairs via `duplicates_id`. Validator PASS at end. Header preamble re-applied.

**Files:**

- Modify: `apps/organism/organism/genome.yaml` (append 31 entries to `organs:` list)

### Step 2.1: Reference table — labels, schedules, peer mapping

The 12 active-active duplicate pairs (verified via Zero's launchctl listing 2026-05-06 22:45 WITA):

| Short label          | Pro id                               | Mini id                               | Schedule             | Type   | expected_hb_seconds |
| -------------------- | ------------------------------------ | ------------------------------------- | -------------------- | ------ | ------------------- |
| `watcher.daily`      | `mata_garuda.watcher_daily.pro`      | `mata_garuda.watcher_daily.mini`      | SCI Hour=6           | cron   | 90000               |
| `reg-alert.30min`    | `mata_garuda.reg_alert_30min.pro`    | `mata_garuda.reg_alert_30min.mini`    | SI=1800              | cron   | 5400                |
| `kg-linker`          | `mata_garuda.kg_linker.pro`          | `mata_garuda.kg_linker.mini`          | SI=3600              | cron   | 7200                |
| `wr-topic`           | `mata_garuda.wr_topic.pro`           | `mata_garuda.wr_topic.mini`           | SCI Weekday=3 Hour=8 | cron   | 691200              |
| `wr2-bridge.hourly`  | `mata_garuda.wr2_bridge_hourly.pro`  | `mata_garuda.wr2_bridge_hourly.mini`  | SI=3600              | cron   | 7200                |
| `bridge.adaptive`    | `mata_garuda.bridge_adaptive.pro`    | `mata_garuda.bridge_adaptive.mini`    | SI=60                | daemon | 180                 |
| `sentinel.daily`     | `mata_garuda.sentinel_daily.pro`     | `mata_garuda.sentinel_daily.mini`     | SCI Hour=2           | cron   | 90000               |
| `intel-bridge.daily` | `mata_garuda.intel_bridge_daily.pro` | `mata_garuda.intel_bridge_daily.mini` | SCI Hour=6 Min=30    | cron   | 90000               |
| `daily-briefing`     | `mata_garuda.daily_briefing.pro`     | `mata_garuda.daily_briefing.mini`     | SCI Hour=7           | cron   | 90000               |
| `kita-feed.daily`    | `mata_garuda.kita_feed.pro`          | `mata_garuda.kita_feed.mini`          | SCI Hour=5           | cron   | 90000               |
| `public-channel`     | `mata_garuda.public_channel.pro`     | `mata_garuda.public_channel.mini`     | SCI Hour=2 Min=15    | cron   | 90000               |
| `weekly-digest`      | `mata_garuda.weekly_digest.pro`      | `mata_garuda.weekly_digest.mini`      | SCI Weekday=0 Hour=8 | cron   | 691200              |
| `gap.consumer`       | `mata_garuda.gap_consumer.pro`       | `mata_garuda.gap_consumer.mini`       | SI=600               | cron   | 4200                |

13 pairs noted, 12 stated in topology brief — discrepancy on `gap.consumer`. **Resolution at commit time:** if Mini's `launchctl list` shows `gap.consumer` (verify with `ssh mini-remote launchctl list | grep matagaruda.gap.consumer`), enroll the pair; otherwise enroll Pro-only and document as Pro-only in §5.4 of spec follow-up. Default to enrolling the pair — adding a phantom Mini entry is a smaller error than missing a real organ, and `duplicates_id` flags it for review.

3 Pro-only entries:
| Short label | id | Schedule | Type | expected_hb_seconds |
|---|---|---|---|---|
| `invalidation-sweep` | `mata_garuda.invalidation_sweep.pro` | SCI Hour=4 Min=13 | cron | 90000 |
| `nlm-feeder-stream.hourly` | `mata_garuda.nlm_feeder_stream_hourly.pro` | SI=3600 | cron | 7200 |
| `nlm-expander.weekly` | `mata_garuda.nlm_expander_weekly.pro` | SCI Weekday=0 Hour=9 | cron | 691200 |

2 Mini-only entries:
| Short label | id | Schedule | Type | expected_hb_seconds | Note |
|---|---|---|---|---|---|
| `ner-worker.hourly` | `mata_garuda.ner_worker_hourly.mini` | SI=3600 (Mini plist) | cron | 7200 | Requires Mini Ollama qwen3.5 GPU |
| `normalizer.hourly` | `mata_garuda.normalizer_hourly.mini` | SI=3600 (Mini plist) | cron | 7200 | Mini-only |

Mini plist schedules are not visible from Pro filesystem; the `expected_hb_seconds` is derived from the label suffix `.hourly` + standard 1h grace.

### Step 2.2: Construct entries — single canonical template

- [ ] **2.2.a: Open genome.yaml at the end of the organs list**

```bash
tail -20 apps/organism/organism/genome.yaml
grep -n "^  - id:" apps/organism/organism/genome.yaml | tail -5
```

Confirm the last existing entry is `pro.organism_control_panel` and identify the line number where new entries should be inserted (immediately after the last `cicatrix_refs: []` of the last organ).

- [ ] **2.2.b: Append matagaruda entries**

Append the following block AFTER the last existing organ entry, BEFORE any trailing whitespace or EOF:

(Single canonical example with full schema; the remaining entries follow the same template — substitute `id`, `runtime`, `recovery_params.host`, `recovery_params.label`, `duplicates_id`, schedule-derived `expected_hb_seconds`, and `owner_module`.)

```yaml
# === Wave 1 — mata_garuda Pro+Mini (active-active 12 dup pairs + 3 Pro-only + 2 Mini-only) ===
# Topology verified by Zero 2026-05-06 22:45 WITA via launchctl on both nodes.
# Resolution of double-firing: out of scope, see cicatrix-scars.md.
- id: mata_garuda.watcher_daily.pro
  runtime: pro_launchd
  type: cron
  expected_hb_seconds: 90000
  owner_module: apps/mata-garuda/scripts/run_watcher.sh
  dependencies:
    - infra.redis
  recovery_action: launchctl_kickstart
  recovery_params:
    host: pro
    label: com.matagaruda.watcher.daily
  severity_on_silence: warning
  cicatrix_refs: []
  duplicates_id: mata_garuda.watcher_daily.mini
- id: mata_garuda.watcher_daily.mini
  runtime: mini_launchd
  type: cron
  expected_hb_seconds: 90000
  owner_module: apps/mata-garuda/scripts/run_watcher.sh
  dependencies:
    - infra.redis
  recovery_action: launchctl_kickstart
  recovery_params:
    host: mini
    label: com.matagaruda.watcher.daily
  severity_on_silence: warning
  cicatrix_refs: []
  duplicates_id: mata_garuda.watcher_daily.pro
```

For each remaining organ, follow the template substituting:

- `id` from §2.1 reference table
- `runtime`: `pro_launchd` or `mini_launchd`
- `type`: from reference table (almost all `cron`; `bridge_adaptive` is `daemon` because SI=60 + heartbeat scope)
- `expected_hb_seconds`: from reference table
- `owner_module`: derived from the plist `ProgramArguments`. For matagaruda use the relative monorepo path; e.g. `intel-bridge.daily` → `apps/mata-garuda/scripts/run_intel_bridge.py`, `kg-linker` → `apps/mata-garuda/mata_garuda/workers/kg_linker.py`, `gap.consumer` → `apps/mata-garuda/mata_garuda/workers/gap_consumer.py`. If the `ProgramArguments` references a wrapper under `~/scripts/` instead of an in-repo script, set `owner_module: scripts/<wrapper>` (relative to monorepo root, even if the file lives in `~/scripts/` — document the indirection in commit body).
- `dependencies`: `[infra.redis]` for all matagaruda except: (a) `bridge_adaptive` add `infra.postgres`, (b) `kita_feed` and `public_channel` and `weekly_digest` and `daily_briefing` add `infra.postgres` (they read CRM data), (c) `intel_bridge_daily` add `wr2.supervisor` (publishes to wr2 events).
- `recovery_params.host`: `pro` or `mini` matching `runtime`
- `recovery_params.label`: full launchd label (with dotted suffixes preserved, e.g. `com.matagaruda.intel-bridge.daily`)
- `severity_on_silence`: `warning` for cron jobs; `error` for `bridge_adaptive` (Pro-Mini link daemon)
- `duplicates_id`: peer id for active-active; OMIT for Pro-only and Mini-only

The full block is ~31 entries × ~12 lines each ≈ 380 lines added.

- [ ] **2.2.c: Verify YAML parses**

```bash
python -c "import yaml; yaml.safe_load(open('apps/organism/organism/genome.yaml'))"
echo "exit=$?"
```

Expected: exit code 0 (silent success). Any parse error means indentation or syntax broke — fix before continuing.

### Step 2.3: Recompute checksum + re-apply preamble

- [ ] **2.3.a: Update checksum**

```bash
cd apps/organism
python -m organism.tools.validate_genome organism/genome.yaml --update-checksum
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: prints `checksum updated: <sha256>`, exit code 0.

- [ ] **2.3.b: Re-apply preamble (yaml.safe_dump strips comments)**

Confirm preamble is gone:

```bash
head -3 apps/organism/organism/genome.yaml
```

If first line is `version: 1` (no preamble), insert the preamble from Task 1 step 1.3.b above `version: 1` using Edit tool.

- [ ] **2.3.c: Validator PASS**

```bash
cd apps/organism
python -m organism.tools.validate_genome organism/genome.yaml
echo "exit=$?"
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: `✓ genome.yaml valid` and exit code 0.

### Step 2.4: OSINT field leak guard

- [ ] **2.4.a: Grep diff for forbidden tokens**

```bash
git diff apps/organism/organism/genome.yaml | grep -E "^\+.*(content|payload|entity|osint)" || echo "CLEAN"
```

Expected: prints `CLEAN` (no matches in additions). If any match, the entry contains forbidden OSINT-content metadata — fix the offending line before commit. Operational metadata (heartbeat, last_activity, error_count) is allowed; OSINT payload content is NOT.

### Step 2.5: Sample launchctl print round-trip

- [ ] **2.5.a: Verify Pro-resident sample**

```bash
launchctl print "gui/$(id -u)/com.matagaruda.intel-bridge.daily" 2>&1 | grep -E "(StartCalendarInterval|Hour|Minute|RunAtLoad)" | head -10
```

Expected: shows Hour=6 Minute=30 — matches `expected_hb_seconds=90000` (daily + 1h grace).

If launchctl reports "Could not find service" the plist is loaded but with a different domain. Run `launchctl list | grep matagaruda` to confirm. Mini-resident organs (`ner-worker.hourly`, `normalizer.hourly`) cannot be cross-checked from Pro — defer to post-merge verification by Zero.

### Step 2.6: WIP commit + push within 30s

- [ ] **2.6.a: Stage scoped paths**

```bash
git add apps/organism/organism/genome.yaml
git status --short
```

Expected: only `genome.yaml` modified. No other paths.

- [ ] **2.6.b: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(organism): enroll matagaruda Pro 16 + Mini 15 (active-active dup tracking)

Adds 31 mata_garuda entries to apps/organism/organism/genome.yaml:
- 12 active-active dup pairs (Pro+Mini same label) cross-linked via
  duplicates_id (header-only convention)
- 3 Pro-only (invalidation-sweep, nlm-feeder-stream.hourly, nlm-expander.weekly)
- 2 Mini-only (ner-worker.hourly Ollama-bound, normalizer.hourly)

Naming: mata_garuda.<service_underscored>.{pro|mini}
Recovery: launchctl_kickstart with recovery_params.host distinguishing
machines. Mini-side recovery requires SSH via Tailscale alias mini-remote.

OSINT field leak grep CLEAN. Operational metadata only — no content/payload
fields exposed (vincolo inviolabile #3).

Validator pre-commit PASS. Checksum recomputed, preamble re-applied.

Resolution of 12 active-active double-firing: P1 STRUCTURAL cicatrix entry
in following commit. NOT addressed in this PR.

Doctrine ref: PR #479 Symbiosis Turn-On Plan (1b9728928).
Spec: docs/superpowers/specs/2026-05-07-symbiosis-w1-genome-enroll-design.md §5.3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **2.6.c: Push within 30s**

```bash
git push origin feat/symbiosis-W1-genome-enroll-2026-05-07
```

Expected: push success.

---

## Task 3: Enroll WR2 Pro 13 + Pro background crons 5-8 (Batch B2)

**Goal of this task:** add 18-21 entries to `genome.yaml`. WR2 Pro 13 (16 plist - 3 already enrolled: oracle, supervisor, newsletter) + 5-8 selected Pro background crons. Validator PASS at end. Header preamble re-applied.

**Files:**

- Modify: `apps/organism/organism/genome.yaml`

### Step 3.1: WR2 reference table

| Short label            | id                     | Schedule              | Type   | expected_hb_seconds | Notes                  |
| ---------------------- | ---------------------- | --------------------- | ------ | ------------------- | ---------------------- |
| `wr2.canva-apply`      | `wr2.canva_apply`      | none                  | daemon | 600                 | supervisor-driven      |
| `wr2.connector`        | `wr2.connector`        | SCI Hour=4            | cron   | 90000               | daily                  |
| `wr2.dossier-compiler` | `wr2.dossier_compiler` | SCI Hour=4 Min=30     | cron   | 90000               | daily                  |
| `wr2.draft-generator`  | `wr2.draft_generator`  | none                  | daemon | 600                 | supervisor-driven      |
| `wr2.hardening`        | `wr2.hardening`        | none                  | daemon | 600                 | supervisor-driven      |
| `wr2.image-generator`  | `wr2.image_generator`  | none                  | daemon | 600                 | supervisor-driven      |
| `wr2.learner-nightly`  | `wr2.learner_nightly`  | SCI Hour=3            | cron   | 90000               | daily nightly          |
| `wr2.measurer`         | `wr2.measurer`         | none                  | daemon | 600                 | supervisor-driven      |
| `wr2.pg-proxy`         | `wr2.pg_proxy`         | KA=true RAL=true      | daemon | 60                  | true daemon, KeepAlive |
| `wr2.sla-worker`       | `wr2.sla_worker`       | none                  | daemon | 600                 | supervisor-driven      |
| `wr2.strategos`        | `wr2.strategos`        | SCI Weekday=0 Hour=22 | cron   | 691200              | weekly                 |
| `wr2.topic-selector`   | `wr2.topic_selector`   | SCI Hour=5 Min=10     | cron   | 90000               | daily                  |
| `wr2.trend-hunter`     | `wr2.trend_hunter`     | none                  | daemon | 600                 | supervisor-driven      |

13 entries. All `runtime: pro_launchd`, all `recovery_action: launchctl_kickstart`, all `recovery_params: {host: pro, label: com.balizero.wr2.<short>}`.

Dependencies:

- All depend on `wr2.supervisor` (already enrolled)
- `wr2.pg_proxy` adds `infra.postgres`
- `wr2.canva_apply`, `wr2.image_generator` add no infra (external API)
- `wr2.dossier_compiler`, `wr2.measurer`, `wr2.sla_worker` add `infra.postgres`
- `wr2.connector`, `wr2.draft_generator`, `wr2.hardening`, `wr2.strategos`, `wr2.topic_selector`, `wr2.trend_hunter`, `wr2.learner_nightly` add `infra.postgres` and `infra.redis`

`owner_module`: extracted from plist `ProgramArguments`. WR2 plists use `~/.openclaw/bin/wr2/wr2-script-wrapper.sh` with the actual Python script as second arg. Use the inner Python path relative to monorepo root, e.g. `apps/war-room/scripts/wr2_draft_generator.py`. Verify the path exists in the repo before committing; if it doesn't, set `owner_module: scripts/wr2/<name>.py` and document the indirection in commit body.

`severity_on_silence`:

- `wr2.pg_proxy`, `wr2.supervisor` (already enrolled): critical
- WR2 daemons supervisor-driven: warning (supervisor will detect first)
- WR2 cron daily/weekly: warning
- `wr2.draft_generator`, `wr2.image_generator`: error (revenue path)

### Step 3.2: Pro background reference table — apply selection rule

Per spec §5.4 selection rule: enroll only candidates that are (a) launchd-loaded, (b) have a clear schedule OR KeepAlive directive, (c) have a non-empty owner_module that maps to a real script in the monorepo.

Empirical schedule data (verified 2026-05-07 design phase):

| Candidate                       | id                                | Schedule                             | Type        | expected_hb_seconds | Selection   |
| ------------------------------- | --------------------------------- | ------------------------------------ | ----------- | ------------------- | ----------- |
| `codex-autofix-ci`              | `pro.codex_autofix_ci`            | SCI Min=15 (hourly)                  | cron        | 7200                | ENROLL      |
| `codex-coverage-improver`       | `pro.codex_coverage_improver`     | SCI Hour=3                           | cron        | 90000               | ENROLL      |
| `codex-overnight-feeder`        | `pro.codex_overnight_feeder`      | SCI Hour=21 Min=30                   | cron        | 90000               | ENROLL      |
| `codex-overnight-runner`        | `pro.codex_overnight_runner`      | SCI Hour=22                          | cron        | 90000               | ENROLL      |
| `codex-research-actor`          | `pro.codex_research_actor`        | SCI Hour=6                           | cron        | 90000               | ENROLL      |
| `cost-advisor-daily-cap`        | `pro.cost_advisor_daily_cap`      | SCI Hour=8                           | cron        | 90000               | ENROLL      |
| `cost-advisor-weekly`           | `pro.cost_advisor_weekly`         | SCI Weekday=1 Hour=7                 | cron        | 691200              | ENROLL      |
| `claude-max-usage-watcher`      | `pro.claude_max_usage_watcher`    | SCI present but H/M/W empty (verify) | INVESTIGATE | INVESTIGATE         | INVESTIGATE |
| `openclaw-children-watchdog`    | `pro.openclaw_children_watchdog`  | SI=300                               | cron        | 3900                | ENROLL      |
| `nb-intel-delta-watcher.hourly` | `pro.nb_intel_delta_watcher`      | SI=3600                              | cron        | 7200                | ENROLL      |
| `sentinel-meta-watchdog`        | `pro.sentinel_meta_watchdog`      | SI=600                               | cron        | 4200                | ENROLL      |
| `federation-alert-dispatcher`   | `pro.federation_alert_dispatcher` | KA=true (daemon)                     | daemon      | 180                 | ENROLL      |
| `vector-reindex-check`          | `pro.vector_reindex_check`        | SCI Weekday=1 Hour=9                 | cron        | 691200              | ENROLL      |
| `secrets-sync-mini`             | `pro.secrets_sync_mini`           | SCI Hour=4 Min=30                    | cron        | 90000               | ENROLL      |

Select 6-8 highest-signal organs to keep B2 size moderate. Recommended priority enrollment (8 entries): `codex_autofix_ci`, `codex_overnight_runner`, `cost_advisor_daily_cap`, `openclaw_children_watchdog`, `nb_intel_delta_watcher`, `sentinel_meta_watchdog`, `federation_alert_dispatcher`, `secrets_sync_mini`. Defer 6 lower-priority codex/cost runners to a later wave.

For `claude_max_usage_watcher`, inspect the plist directly:

```bash
plutil -p ~/Library/LaunchAgents/com.nuzantara.claude-max-usage-watcher.plist | grep -A5 -E "(StartInterval|StartCalendarInterval|KeepAlive)"
```

If a real schedule emerges (e.g. multiple StartCalendarInterval entries inside an array), enroll with computed `expected_hb_seconds`. If the schedule is genuinely undefined, defer enrollment — do NOT invent metadata.

### Step 3.3: Construct + insert WR2 + Pro background entries

- [ ] **3.3.a: Append entries (template same as Task 2)**

Append a new section block after the matagaruda entries from Task 2:

```yaml
# === Wave 1 — WR2 Pro 13 (under wr2.supervisor) ===
- id: wr2.pg_proxy
  runtime: pro_launchd
  type: daemon
  expected_hb_seconds: 60
  owner_module: apps/war-room/scripts/wr2_pg_proxy.py
  dependencies:
    - infra.postgres
    - wr2.supervisor
  recovery_action: launchctl_kickstart
  recovery_params:
    host: pro
    label: com.balizero.wr2.pg-proxy
  severity_on_silence: critical
  cicatrix_refs: []
# ... [12 more WR2 entries following the same template — substitute id/schedule/owner_module/dependencies/severity per §3.1 reference table]

# === Wave 1 — Pro background crons (selected by §5.4 rule) ===
- id: pro.codex_autofix_ci
  runtime: pro_launchd
  type: cron
  expected_hb_seconds: 7200
  owner_module: scripts/codex/codex_autofix_ci.sh
  dependencies: []
  recovery_action: launchctl_kickstart
  recovery_params:
    host: pro
    label: com.nuzantara.codex-autofix-ci
  severity_on_silence: info
  cicatrix_refs: []
# ... [7 more Pro background entries following the same template]
```

`owner_module` for Pro background crons: extracted from plist `Program` or `ProgramArguments`. Use the path relative to monorepo root if it lives in the repo; otherwise prefix `~/scripts/<name>.sh` indicates a user-script wrapper — document via `owner_module: scripts/<wrapper-relative-name>.sh` with a comment in commit body.

- [ ] **3.3.b: Verify YAML parses**

```bash
python -c "import yaml; yaml.safe_load(open('apps/organism/organism/genome.yaml'))"
echo "exit=$?"
```

Expected: exit 0.

### Step 3.4: Recompute checksum + re-apply preamble + validator PASS

- [ ] **3.4.a: Update checksum**

```bash
cd apps/organism && python -m organism.tools.validate_genome organism/genome.yaml --update-checksum && cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

- [ ] **3.4.b: Re-apply preamble**

(Same procedure as Task 1.4.c / Task 2.3.b — confirm with `head -3` and use Edit if missing.)

- [ ] **3.4.c: Validator PASS**

```bash
cd apps/organism && python -m organism.tools.validate_genome organism/genome.yaml && cd /Users/nuzantara/Desktop/nuzantara/.worktrees/symbiosis-W1
```

Expected: `✓ genome.yaml valid` and exit 0.

### Step 3.5: OSINT leak guard + sample launchctl round-trip

- [ ] **3.5.a: Grep diff for forbidden tokens**

```bash
git diff apps/organism/organism/genome.yaml | grep -E "^\+.*(content|payload|entity|osint)" || echo "CLEAN"
```

Expected: `CLEAN`.

- [ ] **3.5.b: Sample launchctl round-trip on Pro-resident WR2 organ**

```bash
launchctl print "gui/$(id -u)/com.balizero.wr2.draft-generator" 2>&1 | grep -E "(KeepAlive|RunAtLoad|Program)" | head -10
```

Expected: matches the entry's `type: daemon` (no schedule visible, supervisor-driven).

### Step 3.6: WIP commit + push within 30s

- [ ] **3.6.a: Stage**

```bash
git add apps/organism/organism/genome.yaml
git status --short
```

- [ ] **3.6.b: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(organism): enroll WR2 Pro 13 + Pro background crons (B2)

Adds 18-21 entries to apps/organism/organism/genome.yaml:
- WR2 Pro 13 (16 plist - 3 already enrolled: oracle, supervisor, newsletter)
  All depend on wr2.supervisor; pg_proxy KeepAlive=true daemon (severity
  critical), revenue-path daemons (draft_generator, image_generator) severity
  error, others warning.
- Pro background crons 5-8 (selected by §5.4 rule: launchd-loaded + clear
  schedule + non-utility): codex_autofix_ci, codex_overnight_runner,
  cost_advisor_daily_cap, openclaw_children_watchdog, nb_intel_delta_watcher,
  sentinel_meta_watchdog, federation_alert_dispatcher, secrets_sync_mini.

Excluded from B2:
- claude_max_usage_watcher (schedule investigation deferred — plist has
  StartCalendarInterval but H/M/W fields empty in current grep; needs
  manual plutil -p inspection before enrollment)
- 6 lower-priority codex/cost runners (defer to W2 wave)

OSINT field leak grep CLEAN. Operational metadata only.

Validator pre-commit PASS. Checksum recomputed, preamble re-applied.

Doctrine ref: PR #479 Symbiosis Turn-On Plan (1b9728928).
Spec: docs/superpowers/specs/2026-05-07-symbiosis-w1-genome-enroll-design.md §5.4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **3.6.c: Push within 30s**

```bash
git push origin feat/symbiosis-W1-genome-enroll-2026-05-07
```

---

## Task 4: Cicatrix entry — 12 mata_garuda active-active dup STRUCTURAL P1

**Goal of this task:** document the discovered active-active double-firing risk as a STRUCTURAL P1 cicatrix entry. Doc-only commit, no genome.yaml change. Follow the project's established TRAUMA / ANTIBODY / GOTCHA convention used in `.claude/rules/cicatrix-scars.md`.

**Files:**

- Modify: `.claude/rules/cicatrix-scars.md` (insert new entry under "STRUCTURAL" section)

### Step 4.1: Read existing cicatrix-scars.md structure

- [ ] **4.1.a: Inspect file**

```bash
wc -l .claude/rules/cicatrix-scars.md
head -10 .claude/rules/cicatrix-scars.md
grep -n "^### ⚠️ STRUCTURAL:" .claude/rules/cicatrix-scars.md | head -10
```

Note the existing entry headings to match style. The most recent STRUCTURAL entries are about test infrastructure mocks, branch hijack, backend `/health` masking, EventBus PG LISTEN/NOTIFY, plist corruption, and 53 LaunchAgents Pro KeepAlive.

### Step 4.2: Insert new STRUCTURAL entry

- [ ] **4.2.a: Edit file**

Insert the new entry as the FIRST STRUCTURAL entry (top of the STRUCTURAL section, immediately before the existing "Test infrastructure mock != production stack" entry that opens the file). Match the existing TRAUMA / ANTIBODY / GOTCHA template.

```markdown
### ⚠️ STRUCTURAL: 12 mata_garuda LaunchAgents active-active Pro+Mini (2026-05-07)

_Discovered: 2026-05-06 22:45 WITA during Symbiosis W1 genome enrollment audit (Zero verified via launchctl list on both nodes via Tailscale) · Severity: P1 · Workaround: TBD (cleanup in dedicated follow-up PR)_

**TRAUMA:** 12 launchd labels are loaded SIMULTANEOUSLY on Pro AND Mini, both producing the same heartbeat at the same schedule. Verified labels (Pro+Mini both):
```

watcher.daily, reg-alert.30min, kg-linker, wr-topic, wr2-bridge.hourly,
bridge.adaptive, sentinel.daily, intel-bridge.daily, daily-briefing,
kita-feed.daily, public-channel, weekly-digest, gap.consumer

```

For cron jobs (most of the list above), this means the same agent/script runs **twice** per scheduled tick — once on Pro, once on Mini. Concrete blast radius depends per-organ:

- `intel-bridge.daily`: publishes to Redis stream `garuda:raw`. Stream entries deduped per-event-id but the harvester emits a NEW event-id per run → two distinct daily entries containing identical OSINT content.
- `regulation-alert.30min`: posts to Telegram. Alerts will fire twice (Pro and Mini both deliver to the same chat_id).
- `kg-linker`: writes to PostgreSQL knowledge graph. Concurrent writes may produce duplicate edges if the dedup logic is per-call rather than per-content-hash.
- `weekly-digest`, `daily-briefing`: same email or Telegram digest sent twice.
- `public-channel`: same scheduled post published twice.

The double-firing was masked until 2026-05-04 because Mini was offline most of April; the dup_resolver `~/scripts/wave1-pro-mini-dup-resolver.sh --check` reports zero conflicts when Mini is offline. The risk only materialises during Mini-up windows.

`~/scripts/wave1-pro-mini-dup-resolver.sh` exists with `--check` and `--resolve` modes but was never invoked because the Wave-1 catalogue assumed single-source plists; the 12 active-active labels are NOT in the resolver's protected list.

**ANTIBODY (proposed, NOT yet implemented — follow-up PR):**

1. **Decision per organ** — for each of the 12, decide: (a) Pro-only and unload from Mini, (b) Mini-only and unload from Pro, or (c) leader-election. Rationale per organ depends on resource locality (e.g. `kg-linker` writes to local Postgres on Pro; `nlm-feeder-stream` reaches NotebookLM CLI which is Pro-only). Default for the 12: prefer (a) Pro-only since Pro has the canonical CRM data and external API tokens.

2. **Plist removal** — `launchctl bootout gui/$(id -u)/com.matagaruda.<label>` + `rm ~/Library/LaunchAgents/com.matagaruda.<label>.plist` on the LOSING side. Update `genome.yaml` to drop the corresponding `mini` or `pro` entry once the launchd state is reconciled.

3. **Resolver hardening** — extend `wave1-pro-mini-dup-resolver.sh` protected list to cover the 12 labels with `--resolve` mode that picks the canonical owner per organ. Run via cron after each Mini-up event (heartbeat from `secrets-sync-mini` could trigger).

4. **Test** — register new test in `apps/organism/tests/test_genome_no_active_active.py` that scans `genome.yaml` for entries sharing identical `recovery_params.label` across `pro` and `mini` hosts, fails CI if any pair is found OUTSIDE an explicit allowlist (which starts empty post-cleanup).

Until the cleanup PR ships, the registry shows 12 dup pairs cross-linked via `duplicates_id` — observability without coordination. The Supervisor will surface 2× heartbeats per tick on these labels until reconciled.

**GOTCHA:**

- `genome.yaml` `duplicates_id` is a HEADER-ONLY convention. The validator does NOT enforce it. A future refactor that drops `duplicates_id` accidentally will not surface in CI.
- The dup_resolver's `--check` mode returns "0 conflicts, Mini offline" when Mini is unreachable. Operators reading this output may conclude "no dups exist" — incorrect when Mini is up.
- Cron jobs on Pro and Mini may run at slightly offset wall-clock times because the 2 machines have independent clock skew. Expect a 0-5s window where both fire before either completes — race conditions in shared state (Redis SETNX, Postgres advisory lock) are NOT mitigated by this PR.
- Mata-garuda agents that emit to `garuda:raw` Redis stream pass through Nuzantara's CRM consumer; double-firing inflates `items_processed` metric by 2× until cleanup. Dashboards built on raw counts will misreport — note in dashboard query: filter by `host_pro_or_mini` if the producer label distinguishes.
- The 13th entry `gap.consumer` was reported as 12 in the topology brief but appears active-active in our enrollment; verify post-merge with Zero whether it's a dup pair or Pro-only. If Pro-only, drop the `mini` enrollment and remove the `duplicates_id` cross-link in a small follow-up commit.

**Related:** Wave-1 dup resolver `~/scripts/wave1-pro-mini-dup-resolver.sh [--check|--resolve]` (Pro-local, idle 2026-05-04 14:40 with Mini offline). MEMORY.md ref: "Wave-1 dup resolver" entry.

Brainstorm artifacts: none yet (this entry is post-discovery during the W1 enrollment). Future agents implementing the cleanup follow-up PR should reference this scar + the W1 PR (`feat(organism): enroll Wave 1 organs in Innervation Genoma`) as the inventory source.
```

- [ ] **4.2.b: Verify the file still parses as Markdown** (no broken anchors / runaway code fences)

```bash
wc -l .claude/rules/cicatrix-scars.md
grep -c "^### " .claude/rules/cicatrix-scars.md
```

Expected: line count grew by ~75 lines, `###` heading count +1.

### Step 4.3: Commit + push within 30s

- [ ] **4.3.a: Stage**

```bash
git add .claude/rules/cicatrix-scars.md
git status --short
```

Expected: only `cicatrix-scars.md` modified.

- [ ] **4.3.b: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(cicatrix): document mata_garuda 12 active-active LaunchAgent dup STRUCTURAL P1

New STRUCTURAL entry in .claude/rules/cicatrix-scars.md documenting the
12 mata_garuda labels found loaded simultaneously on Pro AND Mini during
Symbiosis W1 genome enrollment audit (Zero verified 2026-05-06 22:45 WITA
via launchctl on both nodes via Tailscale).

Severity: P1. Cleanup follow-up PR pending — this commit is post-mortem
documentation only, no code/genome change. Cleanup work scope: per-organ
canonical-side decision, plist removal on losing side, resolver hardening
extension, CI test guarding genome.yaml against unallowed dup pairs.

Risk per-organ documented (cron double-firing, metric inflation, race
conditions in shared state). Observability is now in place via
duplicates_id header-only convention added in W1 PR.

Refs:
- W1 PR (this branch) — registry observability layer
- ~/scripts/wave1-pro-mini-dup-resolver.sh — exists, idle since
  2026-05-04 14:40 with Mini offline
- MEMORY.md "Wave-1 dup resolver" entry

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **4.3.c: Push within 30s**

```bash
git push origin feat/symbiosis-W1-genome-enroll-2026-05-07
```

---

## Post-implementation tasks

### Task 5: Tri-LLM cross-check pre-merge (relaxed 2/3)

**Goal:** identify any LaunchAgents on Pro/Mini that are NOT enrolled but should be. DeepSeek (always) + Gemini OR NotebookLM (one of two if available — Wave 2 Pro 2026-04-29 confirmed 2/3 sufficient).

- [ ] **5.1: DeepSeek review**

```bash
deepseek "Read https://github.com/Balizero1987/Teman2/blob/feat/symbiosis-W1-genome-enroll-2026-05-07/apps/organism/organism/genome.yaml at HEAD. Identify any plist on Pro (~/Library/LaunchAgents/com.{nuzantara,balizero,matagaruda,cell}.*.plist) that LOOKS like an organ but is NOT enrolled. Return a list with reasons. Skip files known to be quarantined (nuz-sync, twitter/.disabled-2026-04-30/)."
```

(Or paste the genome.yaml contents directly into a DeepSeek query if URL fetching isn't supported.)

- [ ] **5.2: Gemini OR NotebookLM review (one of two)**

```bash
# Try Gemini first
gemini -m gemini-3.1-pro-preview -p "Same prompt as DeepSeek. Cross-check."

# If Gemini hits rate limit (429), fall back to NotebookLM:
# Open NB-1 (architecture ground truth) and ask the same question.
```

- [ ] **5.3: Reconcile findings**

Append findings to PR body. If a critical missing organ is identified by both reviewers (or by 1/2 with high confidence), add a follow-up commit to enroll it BEFORE merge. If findings are minor or duplicate of what's already enrolled, document as known-shortlist for W2.

### Task 6: Open the PR

- [ ] **6.1: Push final state**

```bash
git push origin feat/symbiosis-W1-genome-enroll-2026-05-07
git log origin/feat/symbiosis-W1-genome-enroll-2026-05-07 --oneline | head -10
```

Expected: 5 commits visible — design doc + 4 enrollment commits.

- [ ] **6.2: Create PR**

```bash
gh pr create --title "feat(organism): enroll Wave 1 organs in Innervation Genoma (26→~76)" --body "$(cat <<'EOF'
## Summary

Wave 1 of the Symbiosis Turn-On Plan (PR #479 Fase 1). Enrolls ~50 new organs
in `apps/organism/organism/genome.yaml`, expanding the registry from 26 to
~75-78 entries.

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
- Future: enrollment of remaining Pro background crons (6 codex/cost runners
  deferred from B2)

## Refs

- Doctrine: PR #479 (`1b97289283c2f17d049cf401e01afb8e1750e454`)
- Design: `docs/superpowers/specs/2026-05-07-symbiosis-w1-genome-enroll-design.md`
- Plan: `docs/superpowers/plans/2026-05-07-symbiosis-w1-genome-enroll.md`
- NB-1 ADR-7: HALT-on-checksum-mismatch enforcement
- Cicatrix open: branch hijack STRUCTURAL (mitigated via 90-min WIP cadence + push 30s)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

---

## Self-review checklist (run after Task 4 commit, before Task 5)

- [ ] Spec coverage:
  - §3 D1 (validator extension) → Task 1 ✓
  - §3 D2 (active-active separate entries + duplicates_id) → Task 2 ✓
  - §3 D3 (cicatrix entry as discovery, not pre-mortem) → Task 4 ✓
  - §3 D4 (target ≥75) → Task 2 + Task 3 sum to 26+31+18..21 = 75-78 ✓
  - §3 D5 (90-min WIP commit + push 30s) → all task commits include push step ✓
  - §3 D6 (mini_launchd recovery_params.host) → Task 1 preamble + Task 2 entries ✓
  - §3 D7 (header-only duplicates_id) → Task 1 preamble doc + Task 2 entries; validator NOT touched ✓
  - §3 D8 (mata-garuda agent classes NOT in B1, only launchd-loaded) → Task 2 reference table covers 16+15 = 31, agent classes excluded ✓
- [ ] Placeholder scan: no "TBD" or "TODO" in plan steps that affect implementation ✓ (one "INVESTIGATE" entry for `claude_max_usage_watcher` — flagged explicitly with manual-inspection command, not a placeholder)
- [ ] Type consistency:
  - `duplicates_id` (singular) used consistently in spec + plan ✓
  - `recovery_params.host` (lowercase value `"pro"` or `"mini"`) consistent ✓
  - `expected_hb_seconds` formula `period + 1h grace` (1d grace for weekly) consistent ✓
  - Naming convention `<namespace>.<service_underscored>.{pro|mini}` consistent ✓

---

## Risk + rollback summary

| Risk                                    | Detection                                         | Rollback                                                         |
| --------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------- |
| Validator failure on commit             | pre-commit hook                                   | `git reset --soft HEAD^` + edit + recommit                       |
| YAML parse error                        | `python -c "import yaml; yaml.safe_load(...)"`    | manual inspection of last edit, fix indentation                  |
| Branch hijack                           | `ps aux \| grep -c "[c]laude"` >2                 | recover from `.git/objects` dangling blobs (cf. STRUCTURAL scar) |
| OSINT field leak                        | grep guard step in each task                      | drop offending line, recommit                                    |
| Phantom Mini-side enrollment            | post-merge `ssh mini-remote launchctl list`       | small follow-up commit removing entry                            |
| Preamble lost after `--update-checksum` | `head -3 genome.yaml` shows `version: 1` directly | re-apply via Edit tool from spec §5.2                            |
