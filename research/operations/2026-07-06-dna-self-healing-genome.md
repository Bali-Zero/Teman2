# DNA / GENOME — self-healing as an inherited trait, not a retrofit

---
date: 2026-07-06
domain: operations
mandate: Zero — "non un vaccino ma una mutazione reale del nostro genoma: concedere a tutto il corpo il self-healing e renderlo in estensione automatica via che l'organismo si espande"
method: modus Gear 3 (GROUND on-disk census → analysis → mutation design → build)
sources:
  - apps/organism/organism/organs_registry.yaml (120 organs, verified 2026-07-06)
  - scripts/lib/heartbeat.sh · scripts/sentinel-aggregate.py · scripts/proprioception.py
  - infra/healer/healer-run.sh · infra/home-fork/declared-pairs.json (14 pairs)
  - infra/guard-conformance/{registry.json,check_guard_conformance.py} (pattern donor)
  - live probes: ssh mini (14 launchd labels, 3 cron, 1 heartbeat sidecar),
    ssh pro (130 heartbeat sidecars, organism.supervisor running)
---

## Executive summary

The organism already possesses every gene self-healing needs — heartbeat, registry
entry, declared-pair, kill-switch, node assignment, hardened LLM spawn, arming
ledger. What it lacks is **inheritance**. Today each gene is implanted by hand,
organ by organ (horizontal transmission: copy-paste from the last healthy organ).
The result is exactly what a biologist would predict: the oldest, most-tended
tissue (Pro) is gene-rich; the newest tissue (Mini) is gene-poor; and the healer
itself — born five days after the last registry edit — carries none of its own
genes.

The mutation this document designs moves the genes **from the organ's body to
the birth mechanism**: a generator that imprints them at scaffold time, a CI gate
that refuses organs born without them, and a healer that discovers its patients
from the registry instead of a hardcoded list. After the mutation, coverage
extends itself: a new organ that merges is *by construction* visible to the
healer, with zero edits to the healer.

## §1 — Gene census (what already exists, and who enforces it)

| Gene | What it is | Canonical implementation | Enforcement today |
|---|---|---|---|
| **G1 REGISTRY** | Entry in `organs_registry.yaml` (id, runtime, type, expected_hb_seconds, owner_module, recovery_action, severity) | `apps/organism/organism/organs_registry.yaml` (120 organs) | pre-commit checksum validator — but only *internal consistency* of the file **when touched**; nothing forces a new organ INTO it |
| **G2 HEARTBEAT** | Sidecar `~/.organism/last_seen/<id>.json` written every run | `scripts/lib/heartbeat.sh` (`organism_heartbeat <id> <status> [note]`, atomic, never breaks caller) | none — voluntary. Consumed by `sentinel-aggregate.py` (ok/stale/dead vs `expected_hb_seconds`) |
| **G3 DECLARED-PAIR** | live HOME copy ↔ repo canon, per machine | `infra/home-fork/declared-pairs.json` (14 pairs) | `lint_home_fork.py --check` (sha256) + `--discover` (undeclared payloads) — superscar #1 antidote |
| **G4 NODE** | `runtime: pro_launchd\|mini_launchd\|fly_machine` — anti split-brain (#10) | registry field + `test_genome_no_active_active.py` | registry-level only; **wrappers do not self-check** `node≠hostname → graceful-exit` |
| **G5 KILL-SWITCH** | `<ORGAN>_ENABLED=false` honored by the wrapper | convention (`HEALER_ENABLED`, `REPOMAP_ENABLED`, `BRANCH_CLEANUP_ENABLED`…) | none — convention only |
| **G6 SPAWN-HARDENED** | headless `claude -p` with the 4 gotchas cured: bypass-acceptance flag, `cd $REPO` (folder-trust), W84 ssh-localhost trampoline (TCC is per-binary), `</dev/null` + `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` | `infra/healer/healer-run.sh` (reference), regulatory-watcher wrapper (partial) | none — each new LLM cron re-discovers the hangs |
| **G7 LEDGER** | PENDING-ARMS line at birth (built≠armed, W81) | `.claude/skills/modus/PENDING-ARMS.md` | modus discipline (manual) + `pending_arms_report.py --strict` (>48h overdue) |
| **G8 KEEPALIVE-SANE** | plist KeepAlive vs payload nature (#7 daemon-vs-cron) | — | `lint_plist_keepalive.py` (repo-side lint, exists but not in CI) |
| **G9 FAIL-VISIBLE** | `set -u`, log function, no swallowed exceptions, heartbeat on error paths | convention | none |

**Watchers that close the loop** (the immune cells that read the genes):
`sentinel-aggregate.py` (Pro: registry + last_seen → per-organ verdict),
`organism.supervisor` + actuators (Pro launchd, running: `launchctl_kickstart`,
`fly_machines_start`, `restart_agent`, `adopt_module` — the latter is a real
**birth-adoption mechanism** already, but only for *app modules* on `new_module`
git events, not for launchd/cron organs), `heartbeat-watchdog.sh` (Mini, legacy
dialect), the **healer** (Mini, 3 hardcoded receptors), `proprioception.py`
(8 boundary probes).

## §2 — Gap analysis (where the genes are missing)

Verified live 2026-07-06:

1. **Mini is gene-poor tissue.** 14 launchd labels + 3 cron jobs run on Mini;
   the registry knows 4 organs as `mini_launchd`; exactly **1 heartbeat sidecar**
   exists on Mini (`mini.healer.json` — written by the newest organ, ironically).
   The healer's registry-facing eyes would see almost nothing on its own machine.
2. **Two heartbeat dialects.** Pro speaks `~/.organism/last_seen/<id>.json`
   (130 sidecars); Mini's migrated cron jobs speak the legacy
   `~/heartbeat/<label>.ts` protocol watched by `heartbeat-watchdog.sh` +
   `job-ownership.yaml`. Speciation: the healer and sentinel read only the first
   dialect. Any genome work must pick ONE (the JSON dialect — richer, consumed
   by more organs) and treat the `.ts` dialect as grandfathered.
3. **Registry drift.** The four `mata_garuda.*.mini` entries claim `mini_launchd`
   but their labels (`com.matagaruda.sentinel.hourly`, `intel-bridge.daily`,
   `ner.adaptive`, …) run TODAY on Pro (verified via `launchctl list` on both).
   The registry is a snapshot that nothing reconciles against `launchctl` reality
   — G1 without a freshness probe is W90 waiting to happen.
4. **The healer itself is off-genome.** Born 2026-07-05/06: it has G2 (writes a
   sidecar), G3 (3 declared pairs), G5, G6 (it is the reference implementation),
   G7 (ledger lines closed with proofs) — but **no G1 registry entry**. The organ
   that cures by reading receptors is invisible to the registry-driven watchers.
5. **No birth gate.** Nothing at merge time rejects a new plist+wrapper missing
   genes. `guard-conformance` proves this gate-shape works (registry.json +
   checker + sentinel-pattern workflow, live since #1973) — but it covers
   textual guards, not organs.
6. **Horizontal transmission everywhere.** `healer-run.sh` got its genes because
   one session hand-copied them from scars; the next organ will get whatever its
   author remembers. Gene presence correlates with author memory, not with birth.

## §3 — META-PATTERN (the malattia-delle-malattie)

> **The organism transmits its genes horizontally (copy-paste between organs),
> not vertically (inheritance at birth).** Every gap in §2 is one symptom of
> this single defect: genes exist as *examples* to imitate, not as *properties*
> of being born. The registry drifts because registration is a separate manual
> act; Mini is gene-poor because its organs were born in a hurry during
> migration; the healer is off-registry because its birth checklist lived in a
> session's head. The defective belief: "an organ is its wrapper+plist" — no,
> **an organ is wrapper+plist+its entries in the shared nervous system**, and
> anything that creates the first two without the rest is creating dark tissue.

Secondary pattern: **watchers exist per-node, genes are fleet-wide** — sentinel
on Pro, watchdog dialect on Mini, healer on Mini-with-repo-write. The genome
must be node-aware (G4) precisely because the immune system is distributed.

## §4 — The mutation (what we build)

Four pieces, smallest-that-works, each reusing an existing pattern:

### 4a. Birth generator — `scripts/organ_birth.py`
`python3 scripts/organ_birth.py --id mini.foo --node mini --schedule 3600 --kind cron|daemon|llm-cron`
emits: plist (KeepAlive semantics per kind, G8-clean), wrapper skeleton with
G2 heartbeat (success AND error paths), G5 kill-switch, G9 `set -u`+log, G6
hardened-spawn block when `--kind llm-cron`, G4 node-guard
(`hostname ≠ assigned node → graceful exit 0`), plus: G1 registry YAML snippet
(with checksum-update command), G3 declared-pair JSON snippet, G7 PENDING-ARMS
line. The generator does NOT auto-append to shared files (single-writer safety);
it prints ready-to-paste blocks and writes plist+wrapper files. Genes by default;
opting OUT requires deleting code, not remembering to add it.

### 4b. Conformance-at-birth gate — `infra/organ-conformance/`
Mirror of `guard-conformance`: `genes.json` (gene definitions + grandfather
baseline of today's organs) + `check_organ_conformance.py` + sentinel-pattern
workflow (always triggers on PR; path-decision inside the job; required-check
arming = operator). For every **new or modified** plist under `infra/` +
its resolved wrapper: assert G2 (heartbeat call present), G5 (kill-switch env),
G8 (delegates to `lint_plist_keepalive.py`), G9 (`set -u` or equivalent),
G6 (if wrapper invokes `claude -p`: must carry `--strict-mcp-config`,
`</dev/null`, and a TCC strategy — trampoline or SSH-context assertion),
G1 (organ id present in `organs_registry.yaml`), G3 (if plist targets a HOME
payload: pair declared). Existing organs are grandfathered in `genes.json`
(report-only) so the gate lands green; the baseline shrinks as organs get cured.
**The gate applies to itself**: the healer plist+wrapper must pass it (they will
be the first non-grandfathered entries), and the checker ships with guilt AND
innocence fixture tests per the #3 discipline.

### 4c. Healer discovery-from-registry — receptor 4
`scripts/healer_receptor_registry.py --node mini`: reads `organs_registry.yaml`
+ `~/.organism/last_seen/`, filters organs whose `runtime` matches this node,
classifies dead/stale per `expected_hb_seconds` (same semantics as
sentinel-aggregate: dead = age > 3× expected, or status ≠ ok), exits 1 with a
JSON summary when dead organs exist. `healer-run.sh` adds it as Receptor 4 —
**zero hardcoded organ lists**. Auto-extension becomes real: organ born via 4a
→ registry entry + heartbeat gene → healer sees it on the next tick, unchanged.
(Enabled organs only; `expected_hb_seconds: 0` = liveness-exempt, skipped.)

### 4d. Healer-pro — DESIGN ONLY (`infra/healer/HEALER-PRO-DESIGN.md`)
Node-scoped twin on Pro: same wrapper skeleton, same receptors filtered
`--node pro`, but constitution inverted on ONE axis — **it may cure the Pro
runtime (launchctl kickstart per registry `recovery_action`, HOME-copy refresh
FROM repo canon per declared-pairs, log evidence) and may NEVER write the repo**
(no worktree, no PR, no push: single-writer for the repo stays the Mini healer).
M5 excluded by design (interactive laptop, no daemon fleet). Install is
operator-gated (new plist on Pro = operator GO), tracked in PENDING-ARMS.

## §5 — What auto-extension means, concretely

Before: new organ → author remembers 0-9 genes → healer blind unless someone
edits healer-run.sh → drift discovered months later by a TAC.
After: new organ → `organ_birth.py` scaffolds genes → CI gate refuses the PR if
genes were stripped → merge ⇒ registry entry + heartbeat exist ⇒ receptor 4
picks it up on the next 4h tick ⇒ silence beyond 3× expected_hb becomes an
ACTIONABLE the healer triages — cure in-perimeter, Telegram otherwise.
The healer's coverage grows monotonically with the organism, with no healer edits.

## §6 — Solo-operatore (physical / strategic boundary)

1. **Required-check arming** of `organ-conformance` on main = branch-protection
   change (same as guard-conformance) — operator-only, PENDING-ARMS line.
2. **Healer-pro install GO** (new plist on Pro) — design lands with this PR;
   installation waits for explicit GO.
3. **mata_garuda registry runtime drift** (4 entries say mini, run on Pro):
   cure = registry edit + checksum, mechanically trivial BUT it rewrites the
   nervous-system's map of a 29-label constellation — proposed as a follow-up
   PR for operator review, not folded silently into this one.
4. **Mini legacy heartbeat dialect** (`~/heartbeat/*.ts`): migrating Mini cron
   jobs to the JSON dialect touches live Mini wrappers — grandfathered for now;
   receptor 4 covers only the JSON dialect (declared, fail-visible in its output).

## §Panel — red-team outcomes (Gemini 3.1 Pro + Codex GPT-5.5, 2026-07-06)

Spec-review rule honored (DeepSeek seat dead HTTP 402 since 07-02; NB not
consulted — internal architecture, no regulatory facts). Gemini returned 10
findings; dispositions, all folded into the build:

1. **Registry-vs-deploy race** (catastrophic) → receptor semantics: organs with
   NO sidecar on this node are `never_armed` (report-only; arming debt is the
   G7 ledger's job) — a merged-but-not-installed organ can never trigger a cure.
2. **Kill-switch blindness** (catastrophic) → G5 now REQUIRES the disabled
   heartbeat; receptor treats `status=disabled` as exempt. The healer cannot
   resurrect an intentionally-stopped organ.
3. **Missing idempotency gene** (critical) → **G10_single_instance added to the
   genome** (pidfile + liveness probe + trap; mandatory for llm-cron).
4. **Grandfather trap** (high) → baseline is per-plist allowed-missing; touching
   an old organ fails only on REGRESSION, never demands full retrofit.
5. **Deferred mata_garuda drift split-brain** (high) → same cure as (1): the 4
   drifted entries have no Mini sidecars → `never_armed`, not dead. Verified
   live against the real registry: exit 0, zero false ACTIONABLE.
6. **First-run invisibility** (medium) → residual accepted DECLARED: an organ
   that dies before its first heartbeat is the ledger's arming-proof line
   (birth checklist requires "first heartbeat verified"), not the receptor's.
7. **Gate blindspots outside infra/** (medium) → scan_roots = infra + apps +
   scripts, git-tracked plists (141 found day one, vs ~40 under infra/ alone).
8. **Node-guard silence** (medium) → G4 wrong-node exit writes
   `status=disabled note=wrong-node` on ITS host's sidecar — visible, exempt.
9. **Manual splicing friction** (low) → `organ_birth.py --apply` writes registry
   entry (+checksum) and declared-pairs in the author's worktree directly.
10. **Legacy dialect blindness** (low) → declared in receptor output
    (`blind_spots` field), §6.4 unchanged.

Codex (xhigh) ran as second seat; its verdict is folded into the PR thread if
it lands after this file freezes — declared here either way (no silent seats).

## §4-BUILT — what shipped (same PR as this document)

- `infra/organ-conformance/{genes.json, check_organ_conformance.py,
  test_organ_conformance.py}` + `.github/workflows/organ-conformance.yml`
  (sentinel pattern). Day-one run: 141 plists scanned, 140 grandfathered
  report-only, 0 regressions — and the healer plist is the FIRST fully
  conformant organ (0 missing genes, not grandfathered), proven by test.
- `scripts/organ_birth.py` — 10-gene imprinting generator; e2e test proves a
  born organ passes the gate with zero missing genes (vertical inheritance).
- `scripts/healer_receptor_registry.py` + healer-run.sh Receptor 4 + mandate
  §receptor-4 semantics + `mini.healer` registry entry (checksum updated).
- `infra/healer/HEALER-PRO-DESIGN.md` (design only, install operator-gated).
- 3 PENDING-ARMS lines (required-check flip · healer-pro install · receptor-4
  Mini HOME arming).

## §7 — Risks & rollback

- Gate too eager → sentinel pattern + grandfather baseline keeps existing PRs
  green; worst case the workflow is not yet required, so it cannot block main.
- Receptor 4 noisy (registry drift = false DIVERGED-equivalents) → it reports
  only organs whose node matches AND that are enabled AND expected_hb>0; the
  healer mandate already triages false positives (proven on proprioception FPs).
- Generator drift vs gate (two definitions of "the genes") → `genes.json` is the
  single source; the generator reads it at runtime to decide which blocks to
  emit; a gate/generator divergence becomes a failing fixture test.
- Kill switches: `HEALER_ENABLED=false` (healer), delete/ignore the workflow
  (gate — not yet required), generator is inert unless invoked.
