#!/usr/bin/env python3
"""voa_deadman.py — dead-man receptor for the VOA public-funnel probe.

L07-PR3. Watches the heartbeat `scripts/probes/voa_journey_probe.mjs` (PR-2)
writes, NOT the probe process — a dead probe and a probe that is genuinely
reporting `fail` are different states this organ must be able to tell apart
(superscar #2: silence and failure are different, and folding them together
is exactly how a guardian goes green-over-dead).

---------------------------------------------------------------------------
THE FOUR-STATE LATTICE (read `verdict`, never infer it) -- two must NEVER fire
---------------------------------------------------------------------------
The probe writes one of four `verdict` values (its own header is the
authority on their meaning; restated here only as this organ's firing rule):

    pass     funnel confirmed working end to end             -> NEVER fire
    dark     page serves the Next 404 template (flag OFF)    -> NEVER fire
             (this is the pre-launch NORMAL state today -- a dead-man that
             fires on `dark` fires on every single tick, and an alarm that
             always fires is an alarm nobody reads)
    fail     page public but journey broken (or a dark page
             with a broken API leg)                          -> FIRE
    unknown  transport/DNS/TLS failure -- unattributable to
             production                                       -> NEVER fire
             (this organ's only power is to turn a PUBLIC funnel off; firing
             because a probe's own network hiccuped would be exactly the
             "outage the probe itself caused" class PR-2's own refutation
             already forced a fourth verdict to prevent, one layer up)

Silence (heartbeat missing, unreadable, malformed, wrong schema, or its
`ts_epoch` older than the silence threshold) -> FIRE. A heartbeat this organ
cannot parse AT ALL is treated as SILENCE, never as healthy: failing open
here would disarm the whole organ (see `read_heartbeat`).

---------------------------------------------------------------------------
PR-3 GROUND FINDING (2026-08-29) — `garuda-arm.yml` is not a one-flag toggle
---------------------------------------------------------------------------
`gh workflow run garuda-arm.yml -f garuda_public_enabled=false` describes a
much smaller action than that workflow performs (read from
`.github/workflows/garuda-arm.yml` at origin/main, 2026-08-29):

  * it takes THREE required inputs (`garuda_public_enabled`,
    `garuda_environment` default `PRODUCTION`, `stage_only` default `false`);
  * one dispatch rewrites EIGHT Fly secrets on `nuzantara-rag`, not one --
    see `GARUDA_ARM_SECRETS` below, extracted from that workflow's own
    `add_if_nonempty` call list;
  * and it RESTARTS the app unless `stage_only=true`.

This organ's whole justification is that its only power is to turn a public
funnel OFF -- a small, safe, one-directional act. A dry-run that only says
"would set garuda_public_enabled=false" is a dry-run nobody can consent to
on the basis of, because the real action re-tags `GARUDA_ENVIRONMENT`,
overwrites four hardcoded config values, possibly re-sets two payment
secrets, and bounces production. `blast_radius_message()` below is built
once from `GARUDA_ARM_SECRETS` so the dry-run log AND the Telegram alert say
the identical, complete thing -- never a shortened paraphrase.

`stage_only` -- does it avoid the restart while still darkening the funnel?
The backend reads `GARUDA_PUBLIC_ENABLED` PER REQUEST, never cached at
mount (`apps/backend-rag/backend/app/routers/garuda_voa_public.py`,
`_public_enabled()` docstring: "read PER REQUEST, not at mount ... the flag
can be flipped without a restart"). That is true of the APPLICATION code.
It says nothing about whether an ALREADY-RUNNING Fly Machine's process
actually observes a NEW value for an OS environment variable set by
`flyctl secrets set --stage` without a restart -- and the workflow's own
comment on `stage_only` answers that directly: "the app is NOT restarted --
they take effect on the next deploy instead of now." That is an explicit
statement that a staged secret does NOT reach the running process until it
restarts or redeploys, regardless of how the app reads it. So
`blast_radius_message()` below states `stage_only=false` (the value that
restarts immediately) as what an actual fire would need, not
`stage_only=true`. This reading is inferred from the workflow's own
committed documentation, NOT confirmed against live Fly machine behaviour
-- `flyctl` on Mini has no usable credential today (`no access token
available`, carried as `operator[gui]`), so this organ cannot probe the
live secret set or the live env-injection semantics. Flag this for
verification before any future PR builds real-fire on top of it.

`garuda_environment` for a real fire should be READ from the live app, not
assumed -- this organ never constructs concrete `-f` values at all (see
"NEVER INVOKES gh workflow run" below), so that requirement falls to
whichever future PR implements real-fire, not to this one.

---------------------------------------------------------------------------
DRY-RUN ONLY. NEVER INVOKES `gh workflow run`. NO EXCEPTIONS, NO CODE PATH.
---------------------------------------------------------------------------
Real-fire authority for this organ is Zero's alone (Needs-ruling item 2 in
the L07-deploy spec) -- an automated organ gaining authority over a public
business surface needs an explicit go, not an env var an operator can set
by habit. Until that ruling lands, THIS FILE CONTAINS NO CODE THAT INVOKES
`gh workflow run`, `gh`, or any Fly-mutating command, in any code path --
`real_fire_enabled()` below is a forward-looking GATE CHECK ONLY: even when
it reports itself armed, `run_once()` does not call anything, it only logs
that the gate claims to be armed and that this build refuses to act on it.
A future PR implementing real-fire replaces that refusal with an actual
invocation, once Zero has ruled.

The gate itself is deliberately hard to trip by accident: the ONLY value of
`VOA_DEADMAN_REAL_FIRE` that arms it is the exact literal
`REAL_FIRE_CONFIRMED_BY_ZERO` -- not `1`/`true`/`yes`, which read like an
ordinary boolean env var an operator could set out of habit or copy-paste
and would otherwise silently claim an authority nobody granted.

---------------------------------------------------------------------------
COLOCATION RISK (refuter-flagged, declared honestly, not mitigated here)
---------------------------------------------------------------------------
The probe and this dead-man both run on Mini -- a single failure domain. If
Mini itself goes down, BOTH the watcher and the watched die together, and
neither the probe's own silence nor this organ's own silence gets reported
anywhere except the shared `mini.*` organism bridge (which is itself on
Mini). This build does not attempt to mitigate that; it only names it,
per the plan's explicit instruction not to claim a false safety margin.

Worst-case actuation: the honest acceptance target is **~30 minutes**
(the probe's own 900s/15min interval, PLUS the 900s/15min silence
threshold below) -- NOT the report's original optimistic "<20 min" figure,
which undercounted the probe's own interval. This organ's own poll cadence
(StartInterval in its plist, chosen at 300s/5min -- see the plist and its
install script) is deliberately much shorter than either of those two so
its own polling lag only adds a small amount on top of the ~30min figure,
rather than compounding it materially.

---------------------------------------------------------------------------
SELF-PROBE (channel liveness, `--test-alert`)
---------------------------------------------------------------------------
An alarm whose healthy state is silence needs a way to distinguish
"nothing to report" from "the alert channel itself is dead" -- same
discipline as `.github/workflows/cron-fly-watcher.yml`'s `test_alert`
workflow_dispatch input. `--test-alert` sends a REAL P0 through
`scripts/tg_notify.py` (tier=p0, so delivery is confirmed via Telegram's own
API response, not just spooled) regardless of the current heartbeat state,
on demand -- an operator (or a future, separate, less-frequent cron) can
invoke it any time to prove the channel end-to-end.

---------------------------------------------------------------------------
ORGANISM GENES (apps/organism/organism/organs_registry.yaml: mini.voa_deadman)
---------------------------------------------------------------------------
G1_registry — this organ's row in organs_registry.yaml, `dependencies:
  [mini.voa_probe]` (this organ reads what that one writes).
G2_heartbeat — owned by the WRAPPER (infra/launchagents/wrappers/
  voa-deadman-wrapper.sh), not this payload script, matching the house
  pattern in voa-probe-wrapper.sh: the wrapper reports THIS RUN's liveness
  to `~/.organism/last_seen/mini.voa_deadman.json`, mapped from this
  script's exit code AND the `DEADMAN_RESULT` trailer line it prints (exit
  code alone cannot distinguish "fire because verdict=fail" from "fire
  because the heartbeat went silent", and those deserve different notes).
G5_kill_switch — `VOA_DEADMAN_ENABLED` (default true), read by the WRAPPER,
  same split as VOA_PROBE_ENABLED/VOA_PROBE_CRON_ENABLED: this is the
  RUNTIME switch (silence one tick); `VOA_DEADMAN_CRON_ENABLED` is the
  INSTALL-time switch (whether the job exists on this host at all), read
  only by infra/launchagents/install_voa_deadman.sh.
G10 (single-instance, advisory) — DELIBERATELY NOT TAKEN. See
  voa-deadman-wrapper.sh's header for the reasoning (idempotent read, no
  mutating action exists to double-fire, and tg_notify's own dedup already
  suppresses a redundant overlapping alert).

Usage:
    python3 scripts/probes/voa_deadman.py                # one tick
    python3 scripts/probes/voa_deadman.py --test-alert    # channel self-probe
    VOA_PROBE_HEARTBEAT=/tmp/x.json python3 ... voa_deadman.py --heartbeat /tmp/x.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_HEARTBEAT_PATH = str(Path.home() / "logs" / "voa-probe-heartbeat.json")
DEFAULT_SILENCE_THRESHOLD_S = 900.0  # 15 min, per the plan's "Silence or red 15 min -> fire"

# Real-fire gate: an explicit, UNAMBIGUOUS literal -- deliberately NOT
# "true"/"1"/"yes", which an operator could set by habit thinking it is an
# ordinary boolean env var. Never .lower()'d/.strip()'d: exact byte match
# only, so no amount of casing/whitespace guessing enables it by accident.
_REAL_FIRE_ENV = "VOA_DEADMAN_REAL_FIRE"
_REAL_FIRE_MAGIC = "REAL_FIRE_CONFIRMED_BY_ZERO"

TG_GATEWAY = _REPO / "scripts" / "tg_notify.py"
FIRE_DEDUP_KEY = "voa-deadman-fire"
TEST_ALERT_DEDUP_KEY = "voa-deadman-test-alert"

_KNOWN_VERDICTS = frozenset({"pass", "dark", "fail", "unknown"})
_NEVER_FIRE_VERDICTS = frozenset({"pass", "dark", "unknown"})

# The exact blast radius `gh workflow run garuda-arm.yml` performs on ONE
# dispatch, read from `.github/workflows/garuda-arm.yml` at origin/main
# (2026-08-29, PR-3 GROUND FINDING -- see module docstring). This is NOT
# "would set garuda_public_enabled=false": it rewrites all eight of these
# and restarts the app unless stage_only=true. Order matches the workflow's
# own `add_if_nonempty` call sequence.
GARUDA_ARM_SECRETS: tuple[str, ...] = (
    "GARUDA_PUBLIC_ENABLED",
    "GARUDA_ENVIRONMENT",
    "GARUDA_PUBLIC_BASE_URL",
    "GARUDA_MAGIC_LINK_BASE_URL",
    "GARUDA_XENDIT_FEE_BPS",
    "GARUDA_XENDIT_FEE_FIXED_IDR",
    "GARUDA_XENDIT_SECRET_KEY",
    "GARUDA_XENDIT_CALLBACK_TOKEN",
)


def blast_radius_message() -> str:
    """The FULL blast radius of a `garuda-arm.yml` dispatch -- every secret
    it rewrites plus the restart. Built once so both the dry-run log and the
    Telegram alert say the identical, complete thing (PR-3 GROUND FINDING;
    superscar #2 -- "a dry-run that under-reports the real action is a
    dry-run nobody can consent to on the basis of").
    """
    lines = [
        f"gh workflow run garuda-arm.yml would rewrite {len(GARUDA_ARM_SECRETS)} "
        "Fly secrets on nuzantara-rag:",
    ]
    lines += [f"  - {name}" for name in GARUDA_ARM_SECRETS]
    lines.append(
        "...and RESTART the app immediately (stage_only=false is the value that "
        "actually darkens the funnel now -- stage_only=true defers to the next "
        "deploy per the workflow's own documented behaviour; see module docstring)."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Heartbeat reading (superscar #2: a heartbeat this organ cannot parse AT
# ALL is SILENCE, never silently healthy -- failing open here disarms the
# whole organ)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HeartbeatRead:
    ok: bool
    problem: str  # "" if ok, else a short machine code (see read_heartbeat)
    data: dict | None = None


def read_heartbeat(path: str) -> HeartbeatRead:
    """Read + validate the probe's heartbeat contract (PR-2's schema).

    Every failure mode returns ok=False with a DISTINCT `problem` code so a
    caller (and this module's own tests) can tell "the file is absent" apart
    from "the file exists but is not JSON" apart from "it parses but the
    contract fields are wrong shape" -- all three are SILENCE-eligible, but
    an operator debugging a false fire needs to know which one happened.
    """
    p = Path(path)
    try:
        raw = p.read_bytes()
    except FileNotFoundError:
        return HeartbeatRead(False, "absent")
    except IsADirectoryError:
        return HeartbeatRead(False, "unreadable_is_a_directory")
    except OSError as exc:
        return HeartbeatRead(False, f"unreadable_{exc.__class__.__name__}")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return HeartbeatRead(False, "malformed_not_utf8")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return HeartbeatRead(False, "malformed_json")

    if not isinstance(data, dict):
        # A JSON array/scalar/null is not this contract's shape at all.
        return HeartbeatRead(False, "malformed_json")

    # `schema` must be EXACTLY the int 1 -- strict, not "truthy" or
    # coercible, because a schema drift on the probe side is precisely the
    # kind of contract violation this organ must not paper over.
    if data.get("schema") != 1:
        return HeartbeatRead(False, "wrong_schema")

    verdict = data.get("verdict")
    if not isinstance(verdict, str) or verdict not in _KNOWN_VERDICTS:
        # An unrecognized verdict string (typo, future schema the probe
        # gained that this organ was never taught, or outright garbage) is
        # a contract violation, not a value we can safely map to "healthy".
        # Treating it as SILENCE is the conservative read: a probe that
        # starts emitting values outside its own documented enum is itself
        # a signal worth escalating, not one to shrug off.
        return HeartbeatRead(False, "unrecognized_verdict")

    ts_epoch = data.get("ts_epoch")
    # bool is a subclass of int in Python -- `ts_epoch: true` must not be
    # accepted as a numeric timestamp.
    if isinstance(ts_epoch, bool) or not isinstance(ts_epoch, (int, float)):
        return HeartbeatRead(False, "invalid_ts_epoch")

    return HeartbeatRead(True, "", data)


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    fire: bool
    state: str  # canonical machine label, see values below
    reason: str  # human-readable, safe to print/alert on
    age_s: float | None = None


def classify(hb: HeartbeatRead, now_epoch: float, silence_threshold_s: float) -> Decision:
    """The single place that decides fire-or-not. See module docstring's
    four-state lattice for the rule this implements.
    """
    if not hb.ok:
        return Decision(
            True,
            f"fire_silence_{hb.problem}",
            f"heartbeat unreadable/unparseable: {hb.problem}",
        )

    data = hb.data or {}
    verdict = data["verdict"]
    ts_epoch = float(data["ts_epoch"])
    # Negative age_s means the heartbeat is timestamped in the FUTURE
    # (clock skew between this host and whatever wrote it). That is an
    # oddity worth noting, never grounds to fire on its own: age_s > 
    # silence_threshold_s is false by construction for any negative value,
    # so a future-dated heartbeat can never trip the staleness branch below
    # -- it falls straight through to the verdict-based rule instead.
    age_s = now_epoch - ts_epoch

    # Staleness FIRST: even a heartbeat that says verdict="pass" is not
    # evidence the funnel works NOW if it was written well past the
    # silence threshold -- it is evidence the probe stopped running.
    if age_s > silence_threshold_s:
        return Decision(
            True,
            "fire_silence_stale",
            f"heartbeat is {age_s:.0f}s old (> {silence_threshold_s:.0f}s silence threshold)",
            age_s,
        )

    # `_NEVER_FIRE_VERDICTS` GOVERNS the fire/no-fire boolean below -- it is
    # not a decorative restatement of the branches. A verdict is
    # fire-eligible iff it is NOT a member of that set (equivalently: this
    # organ fires on exactly `_KNOWN_VERDICTS - _NEVER_FIRE_VERDICTS`, which
    # today is just `{"fail"}`). The branches below never independently
    # decide the boolean; they only supply the per-verdict STATE LABEL and
    # REASON STRING, which a set cannot express and which carry genuinely
    # different, worth-keeping prose. This split is deliberate (found by an
    # adversarial mutation pass that removed "dark"/"unknown" from the set
    # and got 43/43 green, because the set was dead code hardcoded around):
    # mutating `_NEVER_FIRE_VERDICTS` now FLIPS `fire` for that verdict even
    # though the prose below still describes the old, correct behaviour --
    # printing e.g. `state=healthy_dark fire=True` is the bug becoming
    # VISIBLE, not a bug a stale-looking green hid.
    fire_for_verdict = verdict not in _NEVER_FIRE_VERDICTS

    if verdict == "fail":
        return Decision(
            fire_for_verdict,
            "fire_fail",
            data.get("reason") or "probe reported verdict=fail",
            age_s,
        )
    if verdict == "dark":
        return Decision(
            fire_for_verdict,
            "healthy_dark",
            "flag deliberately OFF pre-launch -- healthy, never fires",
            age_s,
        )
    if verdict == "unknown":
        return Decision(
            fire_for_verdict,
            "healthy_unknown",
            "unattributable transport failure -- cannot act on it, never fires",
            age_s,
        )
    # verdict == "pass" is the only remaining member of _KNOWN_VERDICTS.
    assert verdict == "pass", f"unreachable: unhandled known verdict {verdict!r}"
    return Decision(
        fire_for_verdict, "healthy_pass", "funnel confirmed working end to end", age_s
    )


# --------------------------------------------------------------------------
# Real-fire gate (forward-looking scaffolding -- see module docstring;
# no code path in this file ever invokes `gh workflow run`)
# --------------------------------------------------------------------------


def real_fire_enabled() -> bool:
    """Whether the (unimplemented) real-fire path CLAIMS to be armed.

    PIN: the default is OFF, and the ONLY value that flips it is the exact
    literal `REAL_FIRE_CONFIRMED_BY_ZERO` -- not "true"/"1"/"yes" and not
    any case/whitespace variant of the magic literal itself. Even when this
    returns True, `run_once()` below NEVER invokes `gh workflow run` -- that
    action does not exist anywhere in this file (Needs-ruling item 2, Zero's
    explicit go required before it is ever implemented).
    """
    return os.environ.get(_REAL_FIRE_ENV, "") == _REAL_FIRE_MAGIC


# --------------------------------------------------------------------------
# Telegram (routed through the ONE gateway -- scripts/tg_notify.py -- never
# a direct call, so this file never embeds api.telegram.org itself)
# --------------------------------------------------------------------------


def _resolve_python3() -> str:
    for candidate in ("/usr/bin/python3", "/opt/homebrew/bin/python3"):
        if Path(candidate).is_file():
            return candidate
    return sys.executable


def send_telegram_p0(source: str, dedup_key: str, text: str) -> tuple[bool, str]:
    """Route one P0 through scripts/tg_notify.py. Returns (delivered, verdict).

    `delivered` is True only when the gateway's own machine-readable verdict
    is "sent" (`tg_gateway_verdict.gateway_delivered` -- for tier=p0 this
    means `send_telegram()` read Telegram's own API response and got
    `ok: true` back, i.e. delivery is CONFIRMED, not merely attempted).
    Never raises: a Telegram failure must not crash this organ's own tick.
    """
    if not TG_GATEWAY.is_file():
        return False, f"gateway missing at {TG_GATEWAY}"
    try:
        res = subprocess.run(
            [
                _resolve_python3(),
                str(TG_GATEWAY),
                "--tier",
                "p0",
                "--source",
                source,
                "--dedup-key",
                dedup_key,
                "--",
                text,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 — never raises
        return False, f"subprocess error: {exc.__class__.__name__}: {exc}"
    verdict = extract_gateway_verdict(res.stderr)
    return gateway_delivered(verdict), (verdict or f"no verdict (rc={res.returncode})")


def run_test_alert(source: str = "voa-deadman-selftest") -> bool:
    """On-demand channel-liveness self-probe (cron-fly-watcher.yml's
    `test_alert` discipline, ported to this cron-not-workflow organ): sends
    a REAL P0 through the gateway regardless of the current heartbeat state,
    so an operator can prove the alert channel end-to-end at any time,
    independent of whether a fire condition currently exists.
    """
    text = (
        "voa-deadman test alert -- channel liveness self-probe "
        f"(ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})."
    )
    delivered, verdict = send_telegram_p0(source, TEST_ALERT_DEDUP_KEY, text)
    print(f"[voa-deadman] test-alert delivered={delivered} verdict={verdict}")
    return delivered


# --------------------------------------------------------------------------
# The tick
# --------------------------------------------------------------------------


def _build_fire_text(decision: Decision, heartbeat_path: str) -> str:
    lines = [
        f"VOA dead-man: FIRE-eligible ({decision.state}) -- {decision.reason}",
        f"heartbeat={heartbeat_path}",
    ]
    if decision.age_s is not None:
        lines.append(f"age={decision.age_s:.0f}s")
    lines.append("")
    lines.append(blast_radius_message())
    lines.append("")
    lines.append(
        "DRY-RUN ONLY: no `gh workflow run` invoked. Real-fire requires Zero's "
        "explicit go (Needs-ruling item 2)."
    )
    return "\n".join(lines)


def run_once(
    heartbeat_path: str,
    silence_threshold_s: float,
    now_epoch: float | None = None,
) -> tuple[Decision, str | None]:
    """One tick: read, classify, and (if fire-eligible) log the full blast
    radius + send one real Telegram P0. Returns (decision, telegram_verdict).

    Side effects are limited to stdout `print()` and, only when firing, one
    subprocess call to the Telegram gateway -- no env mutation, no file
    writes, no `gh` invocation ever.
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    hb = read_heartbeat(heartbeat_path)
    decision = classify(hb, now_epoch, silence_threshold_s)

    print(f"[voa-deadman] state={decision.state} fire={decision.fire} reason={decision.reason!r}")

    tg_verdict: str | None = None
    if decision.fire:
        text = _build_fire_text(decision, heartbeat_path)
        print("[voa-deadman] --- DRY-RUN FIRE DECISION (full blast radius) ---")
        print(text)
        print("[voa-deadman] --- end dry-run fire decision ---")
        if real_fire_enabled():
            print(
                f"[voa-deadman] {_REAL_FIRE_ENV} is set to the confirmed literal, but this "
                "build has NO code path that invokes `gh workflow run` -- refusing, per "
                "Needs-ruling item 2 (Zero's explicit go required before real-fire is ever "
                "implemented)."
            )
        delivered, verdict = send_telegram_p0("voa-deadman", FIRE_DEDUP_KEY, text)
        tg_verdict = verdict
        print(f"[voa-deadman] telegram delivered={delivered} verdict={verdict}")
    else:
        print("[voa-deadman] no fire -- healthy state, no alert sent")

    # Trailer line the wrapper (or a human) can grep for a compact summary
    # without re-parsing the prose above.
    print(
        f"DEADMAN_RESULT state={decision.state} fire={decision.fire} "
        f"real_fire_gate={'armed' if real_fire_enabled() else 'disabled'} "
        f"tg_verdict={tg_verdict or 'n/a'}"
    )
    return decision, tg_verdict


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VOA dead-man receptor (dry-run only)")
    parser.add_argument(
        "--heartbeat",
        default=None,
        help="override heartbeat path (else VOA_PROBE_HEARTBEAT env, else the probe's own default)",
    )
    parser.add_argument("--silence-threshold-s", type=float, default=None)
    parser.add_argument(
        "--test-alert",
        action="store_true",
        help="send a real self-probe Telegram message and exit (does not read the heartbeat)",
    )
    args = parser.parse_args(argv)

    if args.test_alert:
        return 0 if run_test_alert() else 1

    heartbeat_path = args.heartbeat or os.environ.get("VOA_PROBE_HEARTBEAT", DEFAULT_HEARTBEAT_PATH)
    threshold = args.silence_threshold_s
    if threshold is None:
        threshold = float(
            os.environ.get("VOA_DEADMAN_SILENCE_THRESHOLD_S", DEFAULT_SILENCE_THRESHOLD_S)
        )

    mode_note = (
        "REAL-FIRE GATE ARMED (still dry-run only -- no `gh workflow run` invocation "
        "exists in this build)"
        if real_fire_enabled()
        else "dry-run mode (default)"
    )
    print(f"[voa-deadman] {mode_note}")

    decision, _ = run_once(heartbeat_path, threshold)
    return 1 if decision.fire else 0


if __name__ == "__main__":
    sys.exit(main())
