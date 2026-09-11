#!/usr/bin/env python3
"""Guard: an organ whose heartbeat sidecar is written by
scripts/launchagent-state-bridge.py (a 300s StartInterval poller, per
launchd) cannot beat more often than the poller's own polling interval.

Cicatrix-superscar #2 (Esiste≠Armato) instance, measured live on Pro
2026-08-31: `wr2.pg_proxy` declares `expected_hb_seconds: 60` while its
sidecar is refreshed only every ~300s by the bridge — it read as falsely
DEAD (severity `critical`) across multiple healer ticks while verifiably
alive. Three more registry entries share the same arithmetic mistake.

This test asserts the INVARIANT, reading all three numbers from source —
none hardcoded:
  1. the bridge's poll interval  <- a plist's `StartInterval` (plistlib)
  2. the bridge's organ set      <- every `organ_id="..."` literal in
     scripts/launchagent-state-bridge.py (BRIDGED_LABELS *and*
     BRIDGED_TCP_PROBES alike — both refresh on the SAME poller tick)
  3. the declared threshold      <- organs_registry.yaml's
     `expected_hb_seconds` per organ

If any of the three cannot be read, this test FAILS — it never skips. A
guard that silently skips on a broken read is the exact defect this test
exists to catch (superscar #2 antidote).

--- Deviation from the obvious plist source, found and fixed 2026-08-31 ---
The live plist lives at
`infra/launchagents/_snapshot-live/com.nuzantara.launchagent-state-bridge.plist`
on Pro's disk, but that whole directory is a disaster-recovery mirror that
`.gitignore` documents as living ONLY on the `chore/plist-snapshot-dr`
branch — ignored on every working branch, main included. It is present on
Pro's live checkout purely as an untracked side effect of a daily cron;
`git worktree add` (this repo's mandatory pattern for every agent session)
never materializes it, and neither does any CI checkout. Verified
empirically before writing this test: `git ls-files` returns nothing for
that path, and a fresh worktree cut from origin/main lacks the file
entirely — a test wired to it could never be proven GREEN anywhere except
one machine's dirty disk. So the poller interval is read instead from a
committed, byte-verified fixture copy of that same live plist (see
scripts/tests/fixtures/organ_heartbeat_cadence/README.md for the full
provenance note) — a real plist, parsed by the real plistlib code path,
just living somewhere every checkout actually has it. This also sidesteps
a second tension in the obvious source: content mirrored from
`~/Library/LaunchAgents` is arguably itself a live-machine read, which
this guard is required to avoid.

--- Why the fixture is the ONLY arithmetic source (no live-preferred read) ---
An earlier revision of this test preferred `_snapshot-live` when present and
fell back to the fixture otherwise. That is itself the exact disease this
guard exists to cure, one level up: Pro's live checkout and every other
checkout (CI, a fresh worktree) would silently compute the invariant from
two DIFFERENT numbers with nothing anywhere flagging that they disagree. If
the bridge's real interval ever drifted from the fixture, Pro would judge
organs by one required-margin and CI by another — an instrument answering
whichever question the machine it runs on happens to pose, exactly the
under-match this repo's cicatrix family #3 doctrine warns about (silent
per-machine divergence in a guard's own verdict). So
`test_bridge_fed_organs_declare_a_safe_multiple_of_the_poller_interval`
below reads ONLY the committed fixture — there is exactly one verdict,
everywhere, always. `test_fixture_plist_matches_live_snapshot_when_present`
is the armed drift check: it compares the fixture against the live
snapshot WHENEVER the live snapshot is present (only ever true on Pro's
live checkout, the one place the ground truth is observable) and is the
ONLY assertion in this file allowed to skip — and only for the one
legitimate reason, the live snapshot's absence, named explicitly in the
skip reason. The arithmetic test itself never skips.

Only organs present in BOTH the bridge and the registry are in scope: an
id the bridge writes but the registry never declares is not iterated by
the healer at all (scripts/healer_receptor_registry.py discovers its
patients from the registry, not the bridge), so it cannot be falsely
flagged by a check that never runs on it.

Exemption logic mirrors scripts/healer_receptor_registry.py lines 128-129
verbatim (`organ.get("enabled") is False` / `expected_hb_seconds <= 0` =>
skip) — an organ the healer itself never checks for liveness is out of
scope here too.
"""
from __future__ import annotations

import plistlib
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# The literal, obvious source. NEVER read by the arithmetic test below (see
# "Why the fixture is the ONLY arithmetic source" above) — used only by
# test_fixture_plist_matches_live_snapshot_when_present, the drift check
# that runs when this happens to be present (in practice, only on Pro's
# own live checkout).
_LIVE_SNAPSHOT_PLIST = (
    REPO_ROOT
    / "infra/launchagents/_snapshot-live/com.nuzantara.launchagent-state-bridge.plist"
)
# The SOLE source for the arithmetic test (see this directory's README.md
# for full provenance) — the only copy guaranteed present in a fresh
# origin/main checkout, a CI runner, or the worktree every agent session is
# required to use. Extension is deliberately `.plist.fixture`, NOT `.plist`:
# infra/organ-conformance/check_organ_conformance.py discovers every tracked
# `*.plist` as a candidate organ, and this fixture — a verbatim copy of a
# real LaunchAgent — is structurally indistinguishable from one (found live
# 2026-08-31; see this directory's README.md "Why the extension is
# .plist.fixture" for the full story, including why a path-based exemption
# in the gate was rejected in favor of this rename).
_FIXTURE_PLIST = (
    Path(__file__).resolve().parent
    / "fixtures/organ_heartbeat_cadence/com.nuzantara.launchagent-state-bridge.plist.fixture"
)

BRIDGE_SCRIPT_PATH = REPO_ROOT / "scripts/launchagent-state-bridge.py"
REGISTRY_PATH = REPO_ROOT / "apps/organism/organism/organs_registry.yaml"

#: Every repo-relative path this guard reads. A change to ANY of these — not
#: just the registry — can regress the invariant this file checks (e.g. the
#: bridge gaining a new bridged organ whose registry threshold is too low
#: touches only scripts/launchagent-state-bridge.py, never the registry).
#: `.github/workflows/organ-conformance.yml` must trigger this file's test
#: on a change to any member, in BOTH its `push.paths` list (post-merge
#: arming) and its in-job `git diff --name-only` pathspec (PR-time
#: relevance) — see cicatrix #2 (Esiste≠Armato): a guard that only ever
#: runs inside the continue-on-error `scripts/tests/` sweep gates nothing.
#: `test_organ_heartbeat_workflow_wiring.py` asserts both lists are a
#: superset of this set, so the correspondence is CALCULATED, not a
#: second copy someone has to remember to update by hand.
GUARD_READ_SET: frozenset[str] = frozenset(
    {
        "scripts/tests/test_organ_heartbeat_exceeds_poller_interval.py",
        "scripts/tests/test_organ_heartbeat_workflow_wiring.py",
        "scripts/launchagent-state-bridge.py",
        "scripts/tests/fixtures/organ_heartbeat_cadence/com.nuzantara.launchagent-state-bridge.plist.fixture",
        "apps/organism/organism/organs_registry.yaml",
    }
)

# Three missed poller ticks before calling an organ dead is the standard
# this repo already uses elsewhere (scripts/healer_receptor_registry.py's
# DEAD_MULTIPLIER = 3) — one late poller run must never look like an
# outage on its own.
REQUIRED_MULTIPLE = 3

_ORGAN_ID_RE = re.compile(r'organ_id\s*=\s*"([^"]+)"')


def _load_plist_interval(path: Path) -> int | None:
    """Return StartInterval from `path`, or None if unreadable/unusable.
    plutil and plistlib are known to disagree on some plists in this repo
    (2026-08-31 discovery) — plistlib is authoritative here."""
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            data = plistlib.load(fh)
    except Exception:  # noqa: BLE001 - deliberate: any parse failure -> None
        return None
    interval = data.get("StartInterval")
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        return None
    return interval


def _read_poller_interval_seconds() -> int:
    """The SOLE arithmetic source — deliberately the fixture only, never a
    live-preferred read. See this file's module docstring ("Why the fixture
    is the ONLY arithmetic source") for why: preferring a live snapshot when
    present would let this guard compute a different verdict on Pro than
    everywhere else, silently, the moment the two ever disagreed."""
    interval = _load_plist_interval(_FIXTURE_PLIST)
    if interval is not None:
        return interval
    pytest.fail(
        f"cannot read the bridge's poll interval from the committed fixture "
        f"{_FIXTURE_PLIST} — missing or unparseable. This must fail, not "
        "skip."
    )


def _read_bridge_organ_ids() -> set[str]:
    """Every `organ_id="..."` literal in the bridge source — covers both
    BRIDGED_LABELS (launchctl-fed) and BRIDGED_TCP_PROBES (socket-fed):
    both are (re)written on the SAME poller tick, so the invariant applies
    to either kind identically."""
    if not BRIDGE_SCRIPT_PATH.is_file():
        pytest.fail(f"cannot read bridge organ set: {BRIDGE_SCRIPT_PATH} does not exist")
    text = BRIDGE_SCRIPT_PATH.read_text(encoding="utf-8")
    ids = set(_ORGAN_ID_RE.findall(text))
    if not ids:
        pytest.fail(
            f'parsed zero organ_id="..." literals out of {BRIDGE_SCRIPT_PATH} '
            "— the regex or the source shape changed; this must fail loudly, "
            'never be read as "the bridge covers nothing"'
        )
    return ids


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


def _is_liveness_exempt(organ: dict) -> bool:
    """Mirrors scripts/healer_receptor_registry.py:128-129 verbatim — an
    organ the healer itself never checks for liveness cannot be falsely
    flagged dead by it, so it is out of scope for this guard too."""
    if organ.get("enabled") is False:
        return True
    expected = organ.get("expected_hb_seconds") or 0
    if not isinstance(expected, (int, float)) or isinstance(expected, bool) or expected <= 0:
        return True
    return False


def test_bridge_fed_organs_declare_a_safe_multiple_of_the_poller_interval():
    interval = _read_poller_interval_seconds()
    bridge_ids = _read_bridge_organ_ids()
    registry = _read_registry_organs()

    # Scope = bridge ∩ registry. An id the bridge writes but the registry
    # never declares is not iterated by the healer at all (it discovers its
    # patients from the registry) — it cannot be falsely flagged by a check
    # that never runs on it, so it is deliberately excluded here.
    in_scope_ids = sorted(bridge_ids & registry.keys())
    assert in_scope_ids, (
        "zero organs are in both the bridge and the registry — the "
        "intersection logic itself is almost certainly broken (bridge has "
        f"{len(bridge_ids)} ids, registry has {len(registry)} ids)"
    )

    required_min = REQUIRED_MULTIPLE * interval
    violations: list[tuple[str, float, str, float]] = []
    for oid in in_scope_ids:
        organ = registry[oid]
        if _is_liveness_exempt(organ):
            continue
        expected = organ["expected_hb_seconds"]
        if expected < required_min:
            # Sidecar age cycles roughly uniformly across one poller tick
            # (0..interval seconds); a probe reading "stale" at age >
            # expected therefore reads falsely dead for this fraction of
            # every cycle whenever expected < interval.
            pct_false_dead = max(0.0, (interval - expected) / interval * 100)
            violations.append(
                (oid, expected, organ.get("severity_on_silence", "?"), pct_false_dead)
            )

    if violations:
        lines = [
            f"{len(violations)} bridge-fed organ(s) in {REGISTRY_PATH.relative_to(REPO_ROOT)} "
            "declare expected_hb_seconds below a safe multiple of the bridge's own poll "
            "interval — an organ cannot beat faster than the poller writing its heartbeat.",
            f"poller interval (StartInterval, source={_FIXTURE_PLIST.relative_to(REPO_ROOT)}): "
            f"{interval}s",
            f"required minimum ({REQUIRED_MULTIPLE} x interval): {required_min}s",
            "",
        ]
        for oid, expected, severity, pct in violations:
            lines.append(
                f"  - {oid}: expected_hb_seconds={expected}s "
                f"(severity_on_silence={severity!r}) < required {required_min}s "
                f"-> reads falsely dead ~{pct:.0f}% of wall-clock time (a sidecar the "
                f"bridge refreshes only every {interval}s cannot honestly claim "
                f"staleness at {expected}s)"
            )
        pytest.fail("\n".join(lines))


def test_fixture_plist_matches_live_snapshot_when_present():
    """The armed half of the fixture's staleness caveat — NOT the arithmetic
    guard above, which always reads the fixture and never this live path.

    When Pro's live DR snapshot happens to be present (only ever true on
    Pro's own live checkout, as an untracked side effect of its daily
    plist_snapshot_dr.sh cron — see the module docstring), assert it is
    structurally identical to the committed fixture. This is the ONLY
    assertion in this file allowed to skip, and only for the one legitimate
    reason: the live snapshot is a machine-local artifact that cannot exist
    in CI or a fresh worktree by design, not a missing precondition this
    test can do anything about. A present-but-unparseable live snapshot is
    NOT the skip case — that fails loudly, same as everywhere else in this
    file.

    This is where fixture drift actually gets caught: the live snapshot is
    only ever observable on the one machine that also runs the real organs,
    so that is the only place a divergence CAN be caught.
    """
    if not _LIVE_SNAPSHOT_PLIST.is_file():
        pytest.skip(
            f"live DR snapshot absent at {_LIVE_SNAPSHOT_PLIST} — expected "
            "off Pro's live main checkout (that whole directory is "
            "gitignored everywhere else, see this file's module docstring) "
            "— cannot check fixture freshness against it here"
        )

    try:
        with _LIVE_SNAPSHOT_PLIST.open("rb") as fh:
            live_data = plistlib.load(fh)
    except Exception as exc:  # noqa: BLE001 - present-but-corrupt must FAIL, not skip
        pytest.fail(f"cannot parse {_LIVE_SNAPSHOT_PLIST} with plistlib: {exc}")

    with _FIXTURE_PLIST.open("rb") as fh:
        fixture_data = plistlib.load(fh)

    # Deliberately whole-dict, not narrowed to StartInterval: this fixture's
    # only job is standing in for a real, verbatim LaunchAgent plist (see the
    # README's "Why a committed copy exists here" section) — its value is
    # that check_organ_conformance.py, plistlib, and every other reader see
    # a real plist, not a hand-trimmed stub of one. If Label/Program/
    # ProgramArguments/etc. ever drift from the live file, that means this
    # fixture has quietly become a copy of something else entirely (a
    # different organ's plist, a hand-edit, a stale capture) — worth failing
    # loudly on, not narrowing away. Do not "tighten" this to StartInterval
    # alone without re-reading that rationale.
    assert live_data == fixture_data, (
        f"{_FIXTURE_PLIST} has drifted from the live plist at "
        f"{_LIVE_SNAPSHOT_PLIST} — the arithmetic test above always reads "
        "the fixture (never the live file), so a stale fixture silently "
        "changes the required-margin computation everywhere, not just on "
        "this machine. Update the fixture to match live, byte for byte."
    )
