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

Worst-case actuation: the honest acceptance target is **~33 minutes**
(PRODUCER_INTERVAL_S=900s/15min, PLUS DEFAULT_SILENCE_THRESHOLD_S=1080s/18min
-- itself PRODUCER_INTERVAL_S + SILENCE_MARGIN_S, see that constant's own
comment for why the margin exists and must never be zero) -- NOT the
report's original optimistic "<20 min" figure, which undercounted the
probe's own interval, and revised up from an earlier "~30min" once the
margin fix (item 2) widened the threshold past PRODUCER_INTERVAL_S exactly.
This organ's own poll cadence (StartInterval in its plist, chosen at
300s/5min -- see the plist and its install script) is deliberately much
shorter than either of those two so its own polling lag only adds a small
amount on top of the ~33min figure, rather than compounding it materially.
A sustained-`unknown` outage (never silence, never `fail` -- see
UNKNOWN_ESCALATION_STREAK) actuates on roughly the SAME rough timescale
(PRODUCER_INTERVAL_S * UNKNOWN_ESCALATION_STREAK ~= 45min), not faster --
declared, not hidden.

---------------------------------------------------------------------------
DECLARED, NOT FIXED (Codex sol xhigh refuter round, 2026-08-29) -- named so
the next reader does not rediscover these, and does not mistake silence
here for an oversight.
---------------------------------------------------------------------------
- Repeated actuation has no DISPATCH LATCH. Telegram's own dedup (the
  `voa-deadman-fire` key, mute-ladder in tg_notify.py) prevents alert
  SPAM, but it does not, and cannot, prevent a real-fire implementation
  from dispatching `gh workflow run garuda-arm.yml` more than once for the
  same sustained condition -- Telegram dedup and GitHub Actions dispatch
  are two entirely different systems with no shared state. A dispatch
  latch (a persisted "have I already fired for this incident" marker,
  analogous to UnknownStreakState but for the ACT of firing, not the
  DECISION to) is therefore a PREREQUISITE for authorizing real-fire, not
  an optional hardening step layered on after -- Needs-ruling item 2 should
  be read as including this.
- The blast-radius message (`blast_radius_message()` / GARUDA_ARM_SECRETS)
  is a HARDCODED COPY of `.github/workflows/garuda-arm.yml`'s secret list,
  read once (2026-08-29) and pasted in, not derived from or pinned to any
  particular revision of that workflow. If the workflow's own secret list
  changes, this module's copy silently goes stale and the dry-run log
  under-reports (or over-reports) the real blast radius again -- exactly
  the class of bug the PR-3 GROUND FINDING exists to prevent, just moved
  one layer down. No CI check ties the two together today.
- The kill switch (`VOA_DEADMAN_ENABLED`, read by the wrapper) has NO
  EXPIRY. An operator who disables a tick to silence a known-noisy period
  and forgets to re-enable it leaves this organ silently dark forever,
  with no reminder, no TTL, no periodic "still disabled" notice.
- Absence fires IMMEDIATELY (`fire_silence_absent`), not after an observed
  silence window like every other silence flavor -- defensible (an absent
  heartbeat means the probe never ran at all, so there is no "was healthy
  a moment ago" grace period to extend it), but this has a real bootstrap-
  order caveat: on a BRAND NEW install, before the probe's very first
  successful tick has ever completed, this organ can fire on its very
  first run, purely because nothing has been written yet. That is a
  premature signal during initial bring-up, not a false one -- worth an
  operator's awareness during install, not a code change here.
- The wrapper's own `mktemp` call (`OUT="$(mktemp ...)"`) is unchecked --
  unlike this module's test corpus (which uses a require_tmpdir/
  require_tmpfile idiom specifically because an unchecked mktemp failure
  misattributes every downstream failure to the wrong component), the
  WRAPPER itself does not guard this. Left as-is: fixing it is a wrapper
  change, out of scope for this module-level round, and mktemp failing on
  a live Mini (vs. a test sandbox) is a rare, different-shaped risk.
- The plist's `StandardOutPath`/`StandardErrorPath` point under `~/logs`,
  which must already exist for launchd to redirect into it -- the install
  script does `mkdir -p "$HOME/logs"` before installing, so this is
  ordinarily fine, but the plist itself carries no such guarantee if ever
  loaded by a path other than that installer.

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
import math
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

# The producer's OWN write cadence (scripts/probes/voa_journey_probe.mjs via
# com.nuzantara.voa-probe.plist's StartInterval). Named so the silence
# threshold below is DERIVED from it with an explicit margin, never a bare
# literal that happens to equal it (refuter HIGH -- see SILENCE_MARGIN_S).
PRODUCER_INTERVAL_S = 900.0  # 15 min

# Refuter-caught HIGH: with threshold == producer interval EXACTLY, a probe
# tick delayed by even one second makes the last-good heartbeat register as
# stale, and this organ's own 300s poll cadence (see the plist) guarantees a
# sample will land inside that false window sooner or later. A false fire
# darkens a LIVE funnel -- the worst possible direction for this organ to
# err in, the mirror image of everything `_NEVER_FIRE_VERDICTS` protects
# against on the verdict side. This margin must be comfortably larger than
# ordinary launchd scheduling jitter (single-digit to low-tens-of-seconds on
# this fleet) without materially slowing real detection: 180s costs 3 of a
# ~18min detection budget while easily swallowing routine jitter.
# THE MARGIN MUST NEVER BE ZERO -- `DEFAULT_SILENCE_THRESHOLD_S ==
# PRODUCER_INTERVAL_S` recreates exactly the bug this constant exists to
# prevent, silently, the next time someone "simplifies" this file.
SILENCE_MARGIN_S = 180.0  # 3 min

DEFAULT_SILENCE_THRESHOLD_S = PRODUCER_INTERVAL_S + SILENCE_MARGIN_S  # 1080.0 / 18 min

# Refuter-caught CRITICAL: a SUSTAINED, always-FRESH `unknown` verdict (a
# genuine DNS/TLS/routing outage the probe cannot attribute to production)
# never fires under the four-state lattice alone -- by design, a single
# `unknown` is an unattributable blip (see module docstring + PR-2's own
# refutation) and firing on it would be exactly the self-inflicted-outage
# class this organ must not cause. The cure is DURATION, not the
# instantaneous verdict: see UnknownStreakState / apply_unknown_streak_
# escalation below, which layer ONTO classify()'s per-tick Decision rather
# than folding into it (classify() stays a pure function of ONE
# observation; duration is cross-tick state, persisted separately because
# each tick is a fresh process).
#
# Why 3: at PRODUCER_INTERVAL_S=900s, 3 consecutive DISTINCT unknown
# observations span >=1800s (30 min) of continuous unattributable failure
# -- comfortably longer than a single transient blip (900s, which stays
# healthy) while still bounded well inside one work session. This ADDS to,
# not instead of, the ~30-35min worst case already declared for
# silence/fail below: an outage that manifests ONLY as sustained `unknown`
# (never silence, never fail) actuates on roughly the same rough timescale,
# not faster -- declared here, not hidden.
UNKNOWN_ESCALATION_STREAK = 3

# Defensive bound, not a tight fit to the schema -- the real contract is
# well under 1 KiB. Refuter MEDIUM: without SOME bound, a corrupted/runaway
# write (or a symlink pointed at the wrong file entirely) means this organ
# reads an unbounded amount into memory before even attempting to parse it.
_MAX_HEARTBEAT_BYTES = 65536  # 64 KiB

# Real-fire gate: an explicit, UNAMBIGUOUS literal -- deliberately NOT
# "true"/"1"/"yes", which an operator could set by habit thinking it is an
# ordinary boolean env var. Never .lower()'d/.strip()'d: exact byte match
# only, so no amount of casing/whitespace guessing enables it by accident.
_REAL_FIRE_ENV = "VOA_DEADMAN_REAL_FIRE"
_REAL_FIRE_MAGIC = "REAL_FIRE_CONFIRMED_BY_ZERO"

TG_GATEWAY = _REPO / "scripts" / "tg_notify.py"
FIRE_DEDUP_KEY = "voa-deadman-fire"
TEST_ALERT_DEDUP_KEY = "voa-deadman-test-alert"

# Identity gate (refuter CRITICAL): a fresh `pass` from a DIFFERENT probe, a
# staging run, or a `--dry-run` heartbeat must never be accepted as proof
# THIS production funnel is healthy. `voa_journey_probe.mjs`'s own contract
# header says every heartbeat -- dry-run or real -- carries `mode` for
# exactly this reason ("so any consumer that somehow receives one can
# reject a dry-run object outright"); this organ now actually does.
_EXPECTED_PROBE_IDENTITY = "voa_journey"
_PRODUCTION_MODE = "full"

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

    NO RETRY ON READ (refuter-checked, not an oversight): the producer
    (voa_journey_probe.mjs) writes a per-PID-random `<path>.<pid>.<random>.
    tmp` then RENAMES it over this target -- rename on one filesystem is
    atomic, so a reader of the TARGET path can only ever observe the fully-
    formed PREVIOUS content or the fully-formed NEW content, never a torn
    intermediate state. A retry, a "read twice and compare" stable-read
    check, or a last-known-good snapshot would all be solving a problem
    that does not exist given the producer's own write discipline; adding
    one would be complexity with no risk it closes. See
    test_concurrent_write_via_temp_file_and_rename_is_never_observed_torn
    for the pin -- do not "fix" this into existence.
    """
    p = Path(path)

    # Refuter MEDIUM (item 7): a FIFO/socket/device sitting at this path
    # would make `read_bytes()` below BLOCK FOREVER (unlike a directory,
    # which raises IsADirectoryError immediately) -- and launchd will not
    # start a SECOND instance of this organ while the first hangs, so a
    # hang here is the watcher itself going dark. Reject before ever
    # attempting the read. `is_file()` follows symlinks (a symlink to a
    # regular file is fine; a symlink to a FIFO is correctly rejected); a
    # BROKEN symlink makes `.exists()` False, which correctly falls
    # through to the ordinary FileNotFoundError path below, not this one.
    # NOTE (declared, not fixed): a genuinely WEDGED network mount can make
    # even `.exists()`/`.stat()` themselves block -- this check closes the
    # FIFO/device/socket class fully, but does not fully close a stalled-
    # mount hang, which would need a timeout-wrapped read this organ does
    # not implement.
    try:
        if p.exists() and not p.is_file():
            return HeartbeatRead(False, "unreadable_not_a_regular_file")
    except OSError:
        pass  # fall through; read_bytes()'s own except clauses classify this

    # Refuter MEDIUM (item 7, size bound): stat before read so a corrupted
    # or runaway write does not get read fully into memory before this
    # organ even attempts to parse it. The real contract is well under
    # 1 KiB; _MAX_HEARTBEAT_BYTES is a defensive bound, not a schema fit.
    try:
        if p.stat().st_size > _MAX_HEARTBEAT_BYTES:
            return HeartbeatRead(False, "unreadable_too_large")
    except OSError:
        pass  # fall through; read_bytes() below classifies the real cause

    try:
        raw = p.read_bytes()
    except FileNotFoundError:
        return HeartbeatRead(False, "absent")
    except OSError as exc:
        # A plain directory is caught by the proactive is_file() check
        # above -- `IsADirectoryError` reaching HERE would only be a
        # narrow TOCTOU race (directory created in the gap between that
        # check and this read). No dedicated except-arm for it: a
        # dedicated arm here would be dead code under every test this
        # module can deterministically construct (exactly the class of
        # hazard the coordinator's gate found in `_NEVER_FIRE_VERDICTS`),
        # so the race case is left to fall through to this generic
        # handler, still correctly classified as
        # "unreadable_IsADirectoryError".
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
    # kind of contract violation this organ must not paper over. Refuter
    # LOW (item 8): `!= 1` alone is NOT exact -- `True == 1` and `1.0 == 1`
    # both hold in Python, so a `schema: true` or `schema: 1.0` heartbeat
    # would have passed a check whose own comment claims strict int
    # identity. `isinstance(..., int)` alone is not enough either (bool IS
    # an int subclass) -- both guards are required together.
    schema_value = data.get("schema")
    if (
        not isinstance(schema_value, int)
        or isinstance(schema_value, bool)
        or schema_value != 1
    ):
        return HeartbeatRead(False, "wrong_schema")

    # Refuter CRITICAL (item 6): identity is not optional. A fresh `pass`
    # from a DIFFERENT probe, a staging run, or a `--dry-run` heartbeat must
    # never be accepted as proof THIS production funnel is healthy. "At
    # minimum" per the gate: probe name + production mode; base_url and
    # probe_version are read but deliberately NOT gated here -- a mismatch
    # there is lower-value signal than a wrong probe name or a non-
    # production mode, and gating on them risks false SILENCE from a probe
    # legitimately pointed at a rotated base_url. Declared, not silently
    # widened beyond what was asked.
    probe_name = data.get("probe")
    if probe_name != _EXPECTED_PROBE_IDENTITY:
        return HeartbeatRead(False, f"wrong_probe_identity:{probe_name!r}")

    mode = data.get("mode")
    if mode != _PRODUCTION_MODE:
        return HeartbeatRead(False, f"non_production_mode:{mode!r}")

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

    # Refuter HIGH (item 5 + item 3): a JSON int has no upper bound --
    # `json.loads` parses an astronomically large integer with no error,
    # but converting it to float (every downstream age/staleness
    # calculation needs a float) raises OverflowError. Python's `json`
    # module ALSO happily accepts the non-RFC8259 literals `NaN`/
    # `Infinity`/`-Infinity` (and `1e309` silently overflows to `inf` at
    # parse time) with no error either. All three are contract violations,
    # not real timestamps -- reject up front so classify() never has to
    # catch an OverflowError mid-decision (which used to crash with NO
    # decision, no P0, no DEADMAN_RESULT line at all -- silence about the
    # crash itself, the worst possible failure mode for a dead-man).
    try:
        ts_epoch_f = float(ts_epoch)
    except OverflowError:
        return HeartbeatRead(False, "invalid_ts_epoch_overflow")
    if not math.isfinite(ts_epoch_f):
        return HeartbeatRead(False, "invalid_ts_epoch_non_finite")

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
# Sustained-unknown escalation (refuter CRITICAL, item 1) -- layered ONTO
# classify()'s per-tick Decision, deliberately NOT folded into it.
# classify() stays a pure function of ONE observation (its own docstring's
# contract); duration is cross-tick state, which this organ persists
# separately because each tick is a fresh process (there is no in-memory
# counter to carry it). See UNKNOWN_ESCALATION_STREAK above for why 3.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class UnknownStreakState:
    consecutive_unknown: int
    last_counted_ts_epoch: float | None


def _unknown_streak_state_path(heartbeat_path: str) -> str:
    """Sibling file to the heartbeat -- NOT the heartbeat itself, so this
    organ's own bookkeeping can never be mistaken for, or corrupt, the
    probe's own contract file."""
    p = Path(heartbeat_path)
    return str(p.with_name(p.name + ".deadman-unknown-streak.json"))


def _read_unknown_streak_state(path: str) -> UnknownStreakState:
    """Tolerant read: ANY absent/corrupt/malformed state file is treated as
    "no streak yet" (consecutive_unknown=0, never an error) -- this
    organ's own bookkeeping losing its history must NEVER itself become a
    reason to fire. That would be a second, self-inflicted false-fire
    surface stacked on top of the one this feature exists to close.
    """
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        count = obj.get("consecutive_unknown")
        last = obj.get("last_counted_ts_epoch")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return UnknownStreakState(0, None)
        if last is not None and (isinstance(last, bool) or not isinstance(last, (int, float))):
            return UnknownStreakState(0, None)
        return UnknownStreakState(count, float(last) if last is not None else None)
    except (OSError, ValueError, AttributeError, TypeError):
        return UnknownStreakState(0, None)
    except json.JSONDecodeError:
        return UnknownStreakState(0, None)


def _write_unknown_streak_state(path: str, state: UnknownStreakState) -> None:
    """Atomic write (per-PID temp file + rename), the SAME discipline the
    probe itself uses for its heartbeat -- a torn write here must not
    corrupt a subsequent reader's view. Best-effort: on failure the NEXT
    tick simply re-reads whatever is already on disk (the tolerant read
    above), so a transient write failure degrades to "streak under-counts
    or resets", never a crash.
    """
    try:
        target = Path(path)
        tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps(
                {
                    "consecutive_unknown": state.consecutive_unknown,
                    "last_counted_ts_epoch": state.last_counted_ts_epoch,
                }
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
    except OSError:
        pass


def _next_unknown_streak(
    state: UnknownStreakState, verdict_is_fresh_unknown: bool, ts_epoch: float | None
) -> UnknownStreakState:
    """Pure transition function, kept separate from both the escalation
    decision and all file I/O so the counting rule is independently
    testable. Any observation OTHER than a fresh `unknown` resets the
    streak to zero -- including a SILENCE-classified read, which already
    fires on its own via classify(), so losing the unknown-streak there
    costs nothing.
    """
    if not verdict_is_fresh_unknown:
        return UnknownStreakState(0, None)
    if state.last_counted_ts_epoch is not None and ts_epoch == state.last_counted_ts_epoch:
        # The SAME physical probe observation, re-read by a faster deadman
        # poll (deadman polls every 300s, the producer writes every 900s)
        # -- do NOT double-count it as a second distinct occurrence, or a
        # single real `unknown` tick would satisfy the escalation streak
        # on its own within one producer interval, defeating the entire
        # point of requiring SUSTAINED, DISTINCT observations.
        return state
    return UnknownStreakState(state.consecutive_unknown + 1, ts_epoch)


def apply_unknown_streak_escalation(
    decision: Decision, streak_before: UnknownStreakState, ts_epoch: float | None
) -> tuple[Decision, UnknownStreakState]:
    """Escalate a persistently-fresh `healthy_unknown` to fire-eligible once
    it has recurred, as DISTINCT observations, at least UNKNOWN_ESCALATION_
    STREAK times in a row. Any other decision (healthy_pass, healthy_dark,
    fire_fail, fire_silence_*) passes through completely unchanged and
    resets the streak.
    """
    is_fresh_unknown = decision.state == "healthy_unknown"
    streak_after = _next_unknown_streak(streak_before, is_fresh_unknown, ts_epoch)

    if not is_fresh_unknown:
        return decision, streak_after

    if streak_after.consecutive_unknown >= UNKNOWN_ESCALATION_STREAK:
        return (
            Decision(
                True,
                "fire_sustained_unknown",
                "unattributable transport failure persisted for "
                f"{streak_after.consecutive_unknown} consecutive distinct probe "
                f"observations (>= {UNKNOWN_ESCALATION_STREAK}) -- treating as a "
                "real outage, not a blip",
                decision.age_s,
            ),
            streak_after,
        )
    return decision, streak_after


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
# a direct call, so this file never contacts Telegram's HTTP API directly)
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


def _validate_silence_threshold_s(candidate: float, source: str) -> float:
    """Refuse a threshold that cannot fire (non-finite -- NaN makes every
    comparison False by definition, and `age_s > inf` is False for any
    finite age, so a threshold of `inf` disables silence detection
    entirely) or that fires constantly (<= 0, since any nonnegative real
    age then always exceeds it). Falls back LOUDLY to
    DEFAULT_SILENCE_THRESHOLD_S rather than silently running with a value
    that defeats this organ's one job (refuter HIGH, item 4).
    """
    if math.isfinite(candidate) and candidate > 0:
        return candidate
    print(
        f"[voa-deadman] REFUSING invalid silence threshold from {source}: {candidate!r} "
        f"(must be a finite positive number) -- falling back to default "
        f"{DEFAULT_SILENCE_THRESHOLD_S:.0f}s"
    )
    return DEFAULT_SILENCE_THRESHOLD_S


def resolve_silence_threshold_s(cli_value: float | None, env_value: str | None) -> float:
    """The single place that decides the effective silence threshold from
    (CLI arg, env var, default) -- so both the CLI's own `argparse
    type=float` parse (which accepts "nan"/"inf" exactly like bare
    `float()` does -- there is no separate crash-free path there) and the
    env var's parse get the IDENTICAL validation, never one checked and the
    other not. A non-numeric env value used to raise ValueError BEFORE
    `run_once()` ever started (refuter HIGH, item 4: no decision, no P0, no
    DEADMAN_RESULT line -- the crash itself silent); that is now caught and
    refused loudly, falling back to the default instead.
    """
    if cli_value is not None:
        return _validate_silence_threshold_s(cli_value, "--silence-threshold-s")
    if env_value is not None:
        try:
            parsed = float(env_value)
        except ValueError:
            print(
                f"[voa-deadman] REFUSING non-numeric VOA_DEADMAN_SILENCE_THRESHOLD_S="
                f"{env_value!r} -- falling back to default "
                f"{DEFAULT_SILENCE_THRESHOLD_S:.0f}s"
            )
            return DEFAULT_SILENCE_THRESHOLD_S
        return _validate_silence_threshold_s(parsed, "VOA_DEADMAN_SILENCE_THRESHOLD_S")
    return DEFAULT_SILENCE_THRESHOLD_S


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
    """One tick: read, classify, escalate a sustained `unknown` streak,
    and (if fire-eligible) log the full blast radius + send one real
    Telegram P0. Returns (decision, telegram_verdict).

    Side effects are limited to stdout `print()`, one small streak-state
    file next to the heartbeat (read + best-effort atomic write -- see
    UnknownStreakState), and, only when firing, one subprocess call to the
    Telegram gateway -- no `gh` invocation ever.
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    hb = read_heartbeat(heartbeat_path)
    raw_decision = classify(hb, now_epoch, silence_threshold_s)

    ts_epoch = float(hb.data["ts_epoch"]) if hb.ok and hb.data is not None else None
    streak_path = _unknown_streak_state_path(heartbeat_path)
    streak_before = _read_unknown_streak_state(streak_path)
    decision, streak_after = apply_unknown_streak_escalation(raw_decision, streak_before, ts_epoch)
    _write_unknown_streak_state(streak_path, streak_after)

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
    # Both the CLI's own value (argparse's `type=float` accepts "nan"/"inf"
    # exactly like bare `float()`) and the env var go through the SAME
    # validation -- refuter HIGH, item 4.
    threshold = resolve_silence_threshold_s(
        args.silence_threshold_s, os.environ.get("VOA_DEADMAN_SILENCE_THRESHOLD_S")
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
