#!/usr/bin/env python3
"""Guard: a SELF-REPORTING `type: cron` organ (writes its own heartbeat once
per run, NOT fed by scripts/launchagent-state-bridge.py's 300s poller) cannot
declare `expected_hb_seconds` too close to its own plist's `StartInterval`.

Cicatrix-superscar #2 (Esiste≠Armato) instance, sibling of
scripts/tests/test_organ_heartbeat_exceeds_poller_interval.py (#5431/#5440) —
measured 2026-09-01 while that PR's own gate was in review: 37 `type: cron`
organs (repo-wide plist scan; 33 if the scan is narrowed to
infra/launchagents/ only — see "Why the count differs from the PR #5440
review" below) declare `expected_hb_seconds` below 3x their OWN plist's
`StartInterval`, 19 of them at exactly 1.00x.

--- Why this is a DIFFERENT population from #5431/#5440 ---
#5431 fixed organs whose heartbeat sidecar is refreshed by an EXTERNAL
poller (the bridge, every 300s) regardless of the organ's own schedule — the
constraint there is the poller's cadence. This guard covers organs that
write their OWN heartbeat, once per run: the sidecar's age cycles from ~0
(right after a run finishes) up to ~StartInterval (right before the next run
is due), then resets. The two populations are read from different sources
(the bridge's 300s poll interval vs. each organ's own plist) and are
disjoint by construction below: any organ_id also emitted by the bridge is
excluded here (it is #5431/#5440's, not this guard's — its sidecar's refresh
cadence is the poller's, not its own schedule).

--- Why the floor is NOT a blind copy of #5431's 3x ---
#5431's 3x is calibrated to "three missed POLLER writes" — the poller is an
independent process with no correlation to the organ's own health; a missed
write there is just one bad poll cycle. For a SELF-REPORTING cron, the
equivalent unit is a missed RUN, and the actual danger measured here is not
uniform across ratios:

  ratio < 1/3   -- structurally guaranteed false DEAD (age > 3x expected is
                   reachable within a single ON-TIME cycle, zero missed runs
                   needed; the same mechanism #5431 fixed, just for the
                   organ's own interval instead of the poller's). Only one
                   organ measured here falls in this band: wr2.deploy_puller
                   (0.167x) — spot-checked against its own plist header
                   (infra/launchagents/com.balizero.wr2.deploy-puller.plist,
                   "Hourly pull" is deliberate, documented since Sprint C1)
                   before concluding the REGISTRY value was the bug, not the
                   plist.
  ratio in [1/3, 1) -- age exceeds `expected_hb_seconds` for a real fraction
                   of every ON-TIME cycle (STALE, per scripts/sentinel-
                   aggregate.py's STALE_MULTIPLIER=1.0 / DEAD_MULTIPLIER=3.0
                   and the identical classification in
                   scripts/healer_receptor_registry.py). STALE does not page
                   (healer-run.sh receptor 4: "never-armed / disabled /
                   stale organs do NOT trigger"; sentinel-aggregate.py's
                   `_ESCALATE_STATUSES = ("dead", "starved")` excludes it
                   too) but it is a real, recurring, non-actionable-noise
                   defect on every dashboard/aggregate.json read.
  ratio == 1.0  -- zero margin: any launchd scheduling jitter or nonzero run
                   duration pushes age past `expected_hb_seconds` right at
                   the cycle boundary, guaranteeing a transient STALE blip
                   every cycle. Still not DEAD under the current 3x
                   DEAD_MULTIPLIER (that would need age > 3x StartInterval,
                   i.e. ~2 full missed runs) — narrower risk than the
                   ratio<1/3 band, but a real "first line of defense is
                   gone" regression with no headroom left to absorb.

So the chosen floor is a SEVERITY-TIERED multiple of each organ's own
`StartInterval`, not a flat 3x:
  - severity_on_silence in {critical, error}: >= 1.5x -- matches the
    multiple ALREADY used, apparently deliberately, by two other critical
    organs in this same population (pro.fly_restart_loop_detector,
    pro.supervisor_liveness_watchdog) that this guard does NOT need to
    touch. Cost: DEAD (3x expected = 4.5x StartInterval) fires after ~3
    missed runs -- the fastest floor this guard enforces, because these
    organs are the ones whose own failure degrades the organism's ability
    to notice OTHER organs failing (pro.healer / mini.healer chief among
    them: "the healer itself" -- raised from 1.0x, a flat zero-margin
    value, to 1.5x, not the laxer 2.0x default; see the per-organ comments
    landed alongside the registry fix for the full reasoning).
  - everything else (warning/info): >= 2.0x -- tolerates one full missed
    run of silence before the organ even shows up as STALE (which, per
    above, does not page). Cost: DEAD (3x expected = 6x StartInterval)
    fires after ~5 missed runs for the least urgent tier -- an explicit,
    named trade of slower detection for zero false alarms on ordinary
    launchd jitter, mirroring #5431's own framing ("trades permanent false
    alarms for none, at no real cost" -- detection here was never faster
    than one StartInterval anyway, since the sidecar can't be fresher than
    the organ's own last run).

This guard reads all three numbers from source -- none hardcoded:
  1. each organ's own plist StartInterval  <- every git-tracked `*.plist`
     in the repo (plistlib), keyed by `Label`
  2. the organ set + declared threshold    <- organs_registry.yaml
  3. the bridge's organ set (to EXCLUDE)   <- every `organ_id="..."`
     literal in scripts/launchagent-state-bridge.py (identical regex to
     test_organ_heartbeat_exceeds_poller_interval.py, kept independent on
     purpose: importing across guard files would let one guard's bug hide
     the other's)

If any of the three cannot be read, this test FAILS -- it never skips (same
discipline as the sibling #5431 guard; superscar #2's own antidote).

--- Why the plist source here is a repo-wide git-ls-files scan, not a fixture ---
Unlike the bridge's own plist (a single, DR-mirror-only file living outside
every checkout except Pro's live disk -- #5431's reason for a committed
fixture copy), EVERY plist this guard needs is an ordinary git-tracked file
already present in a fresh `origin/main` checkout, a CI runner, or this
repo's mandatory agent worktree. No fixture indirection is needed or wanted:
reading the fixture-workaround pattern here would be applying #5431's
specific TCC/DR-mirror antidote to a population that never had that disease.
`_snapshot-live/` is still explicitly excluded below, defense-in-depth,
even though `git ls-files` cannot return a gitignored path in the first
place.

--- Why the count differs from the PR #5440 review's 33/18 ---
That review's 33 (18 at exactly 1.00x) was reproduced here EXACTLY by
narrowing the plist scan to `infra/launchagents/*.plist` only. This guard's
repo-wide scan finds 4 more (37 total, 19 at 1.00x): two real, live,
`launchctl load`-installed plists under apps/organism/organism/launchd/
(README.md in that directory documents the install command directly) and
two more under docs/infra/launchagents/ (a `docs/` path that is nonetheless
the literal `PLIST_DIR` `scripts/enable_cron_jobs.sh` installs from -- not
documentation, a second live install root with a misleading path prefix).
Narrowing the scan to `infra/launchagents/` would have silently left these
4 organs (including pro.claude_max_watcher, exactly 1.00x) uncovered by a
guard whose whole point is complete coverage -- so this guard intentionally
scans every tracked `*.plist`, not one canonical-looking directory.

--- Explicitly OUT OF SCOPE (not silently dropped -- named here) ---
  - Organs whose plist uses `StartCalendarInterval` instead of
    `StartInterval` (48 measured 2026-09-01): a clock-time schedule (e.g.
    "daily at 05:00") has different margin semantics (DST, calendar-day
    boundaries) that a seconds-multiple floor does not model honestly.
  - Organs with NO tracked plist matching their `recovery_params.label` at
    all (26 measured 2026-09-01): a distinct defect class (a registry entry
    pointing at a plist that was never committed, or a runtime that isn't
    actually a plain launchd job) -- worth its own investigation, not a
    heartbeat-margin question, and out of this guard's and this PR's scope.
  - Organs already covered by test_organ_heartbeat_exceeds_poller_interval.py
    (the bridge's organ_id set) -- excluded here, not because they are safe,
    but because they are that guard's responsibility, not this one's.
"""
from __future__ import annotations

import plistlib
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "apps/organism/organism/organs_registry.yaml"
BRIDGE_SCRIPT_PATH = REPO_ROOT / "scripts/launchagent-state-bridge.py"

# Severity-tiered floor -- see module docstring for the argument. Keyed by
# severity_on_silence; anything not in the critical/error tier gets the
# laxer default.
_FAST_TIER_SEVERITIES = frozenset({"critical", "error"})
_FAST_TIER_MULTIPLE = 1.5
_DEFAULT_MULTIPLE = 2.0

_ORGAN_ID_RE = re.compile(r'organ_id\s*=\s*"([^"]+)"')


def _required_multiple(severity: str) -> float:
    return _FAST_TIER_MULTIPLE if severity in _FAST_TIER_SEVERITIES else _DEFAULT_MULTIPLE


def _is_violation(expected_hb_seconds: float, start_interval: float, severity: str) -> bool:
    """Pure predicate, unit-tested directly below (guilt + innocence) and
    used by the registry-wide scan test. Never inlined into the scan loop
    so the rule itself has a regression test independent of the current
    registry's contents."""
    return expected_hb_seconds < _required_multiple(severity) * start_interval


def _tracked_plist_paths() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.fail(f"cannot list tracked files via `git ls-files`: {exc}")
    paths = [
        p for p in out.splitlines()
        if p.lower().endswith(".plist") and "_snapshot-live" not in p
    ]
    if not paths:
        pytest.fail(
            "git ls-files returned zero tracked *.plist files -- the repo "
            "layout changed or the command is broken; this must fail, not "
            "be read as \"no plists to check\""
        )
    return paths


def _read_label_to_start_interval() -> dict[str, int]:
    """Every tracked plist's Label -> StartInterval (only entries with a
    positive int StartInterval; StartCalendarInterval-scheduled plists are
    silently absent from this map by construction -- see module docstring
    "Explicitly OUT OF SCOPE", they are not silently miscounted, they are
    named as excluded)."""
    label_to_interval: dict[str, int] = {}
    for rel in _tracked_plist_paths():
        path = REPO_ROOT / rel
        try:
            with path.open("rb") as fh:
                data = plistlib.load(fh)
        except Exception as exc:  # noqa: BLE001 - a present-but-corrupt tracked plist must fail
            pytest.fail(f"cannot parse tracked plist {rel} with plistlib: {exc}")
        label = data.get("Label")
        interval = data.get("StartInterval")
        if not label:
            continue
        if isinstance(interval, int) and not isinstance(interval, bool) and interval > 0:
            label_to_interval[label] = interval
    if not label_to_interval:
        pytest.fail(
            "parsed zero (Label, StartInterval) pairs out of every tracked "
            "*.plist -- the plist population or plistlib itself changed "
            "shape; this must fail loudly"
        )
    return label_to_interval


def _read_registry_organs() -> dict[str, dict]:
    if not REGISTRY_PATH.is_file():
        pytest.fail(f"cannot read registry: {REGISTRY_PATH} does not exist")
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    organs = data.get("organs") if isinstance(data, dict) else None
    if not isinstance(organs, list) or not organs:
        pytest.fail(f"{REGISTRY_PATH}: 'organs' is not a non-empty list")
    by_id: dict[str, dict] = {}
    for organ in organs:
        oid = organ.get("id") if isinstance(organ, dict) else None
        if not oid:
            pytest.fail(f"{REGISTRY_PATH}: organ entry with no 'id': {organ!r}")
        by_id[oid] = organ
    return by_id


def _read_bridge_organ_ids() -> set[str]:
    """Independent read of the same regex test_organ_heartbeat_exceeds_
    poller_interval.py uses -- deliberately not imported from that file, so
    a bug in one guard's parsing cannot silently hide a bug in the other's
    scope-exclusion."""
    if not BRIDGE_SCRIPT_PATH.is_file():
        pytest.fail(f"cannot read bridge organ set: {BRIDGE_SCRIPT_PATH} does not exist")
    text = BRIDGE_SCRIPT_PATH.read_text(encoding="utf-8")
    ids = set(_ORGAN_ID_RE.findall(text))
    if not ids:
        pytest.fail(
            f'parsed zero organ_id="..." literals out of {BRIDGE_SCRIPT_PATH} '
            "-- the regex or the source shape changed; this must fail loudly"
        )
    return ids


def _is_liveness_exempt(organ: dict) -> bool:
    """Mirrors scripts/healer_receptor_registry.py:128-129 verbatim (same
    exemption test_organ_heartbeat_exceeds_poller_interval.py uses) -- an
    organ the healer itself never checks for liveness is out of scope here
    too."""
    if organ.get("enabled") is False:
        return True
    expected = organ.get("expected_hb_seconds") or 0
    if not isinstance(expected, (int, float)) or isinstance(expected, bool) or expected <= 0:
        return True
    return False


def test_self_reporting_cron_organs_declare_a_safe_multiple_of_their_own_plist_interval():
    label_to_interval = _read_label_to_start_interval()
    registry = _read_registry_organs()
    bridge_ids = _read_bridge_organ_ids()

    cron_ids = {oid for oid, organ in registry.items() if organ.get("type") == "cron"}
    assert cron_ids, "zero type:cron organs in the registry -- the type filter is almost certainly broken"

    # This guard's scope = type:cron organs NOT fed by the bridge poller
    # (that population is test_organ_heartbeat_exceeds_poller_interval.py's,
    # not this guard's -- see module docstring).
    in_scope_ids = sorted(cron_ids - bridge_ids)
    assert in_scope_ids, (
        "zero type:cron organs remain after excluding the bridge's organ set "
        "-- the exclusion logic itself is almost certainly broken "
        f"(cron has {len(cron_ids)} ids, bridge has {len(bridge_ids)} ids)"
    )

    checked = 0
    violations: list[tuple[str, float, float, str, float]] = []
    for oid in in_scope_ids:
        organ = registry[oid]
        if _is_liveness_exempt(organ):
            continue
        label = (organ.get("recovery_params") or {}).get("label")
        interval = label_to_interval.get(label) if label else None
        if interval is None:
            continue  # StartCalendarInterval or no tracked plist -- out of scope, see docstring
        checked += 1
        expected = organ["expected_hb_seconds"]
        severity = organ.get("severity_on_silence", "warning")
        if _is_violation(expected, interval, severity):
            ratio = expected / interval
            violations.append((oid, expected, interval, severity, ratio))

    assert checked > 0, (
        "zero self-reporting cron organs had a resolvable (label, "
        "StartInterval) pair -- the join itself is almost certainly broken, "
        "not \"nothing to check\""
    )

    if violations:
        lines = [
            f"{len(violations)} self-reporting cron organ(s) in "
            f"{REGISTRY_PATH.relative_to(REPO_ROOT)} declare expected_hb_seconds "
            "below a safe multiple of their OWN plist's StartInterval "
            f"(checked {checked} organs total; floor = "
            f"{_FAST_TIER_MULTIPLE}x for severity in {sorted(_FAST_TIER_SEVERITIES)}, "
            f"{_DEFAULT_MULTIPLE}x otherwise).",
            "",
        ]
        for oid, expected, interval, severity, ratio in sorted(violations, key=lambda r: r[4]):
            required = _required_multiple(severity) * interval
            lines.append(
                f"  - {oid}: expected_hb_seconds={expected}s vs its own "
                f"StartInterval={interval}s (ratio={ratio:.3f}x, "
                f"severity_on_silence={severity!r}) < required {required:.0f}s"
            )
        pytest.fail("\n".join(lines))


# --- Guilt + innocence on the rule itself (superscar #3 doctrine: no guard
# without both), independent of whatever the registry currently contains. ---

def test_violation_math_guilt_below_the_fast_tier_floor():
    # critical/error floor is 1.5x -- 1.4x must be flagged.
    assert _is_violation(expected_hb_seconds=1400, start_interval=1000, severity="critical")
    assert _is_violation(expected_hb_seconds=1400, start_interval=1000, severity="error")


def test_violation_math_guilt_below_the_default_floor():
    # warning/info floor is 2.0x -- 1.9x must be flagged.
    assert _is_violation(expected_hb_seconds=1900, start_interval=1000, severity="warning")
    assert _is_violation(expected_hb_seconds=1900, start_interval=1000, severity="info")


def test_violation_math_innocence_at_the_fast_tier_floor():
    # exactly at the floor must PASS (>=, not >) -- matches
    # pro.fly_restart_loop_detector / pro.supervisor_liveness_watchdog,
    # already at 1.5x in the live registry, which this guard must not flag.
    assert not _is_violation(expected_hb_seconds=1500, start_interval=1000, severity="critical")
    assert not _is_violation(expected_hb_seconds=1500, start_interval=1000, severity="error")


def test_violation_math_innocence_at_the_default_floor():
    assert not _is_violation(expected_hb_seconds=2000, start_interval=1000, severity="warning")
    assert not _is_violation(expected_hb_seconds=2000, start_interval=1000, severity="info")


def test_violation_math_innocence_ratio_exactly_one_is_still_flagged_for_every_tier():
    # The exact defect this guard exists to catch: ratio==1.0 must be a
    # violation regardless of severity (it is the "zero margin" case in the
    # module docstring, not a borderline pass).
    for severity in ("critical", "error", "warning", "info"):
        assert _is_violation(expected_hb_seconds=1000, start_interval=1000, severity=severity)
