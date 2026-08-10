#!/usr/bin/env python3
"""verify_connectome.py — re-walk the declared system arteries and detect silent edge death.

The connectome (docs/connectome/edges/*.yaml) is the empirical census of every
producer→consumer edge in the Nuzantara organism (PG channels, queues, launchd
fleet, GH workflows, sync daemons, HOME-forks, webhooks, hooks, MCP servers).
This verifier re-probes the edges that carry a runnable probe and reports drift
against the declared status — the antibody for the recurring disease class
"edges die silently" (W55/W62/W64/W67/W70/W71 family).

Classification per edge:
  CONFIRMED   probe outcome matches declared status
  REGRESSED   declared healthy (ALIVE/ARMED/GATING/...) but probe FAILED  ← the alarm
  RECOVERED   declared dead-ish but probe PASSED (census is stale — update it)
  STATIC      no probe declared/derivable (documentation-only edge)
  SKIPPED     probe targets an unreachable machine

Probe spec (optional per edge):
  probe:
    type: cmd | file_exists | file_age_max_h | grep | launchd_label | md5_pair
    via: local | ssh:<host>          # default local
    # type=cmd:           cmd: "...", expect_regex: "..." (optional)
    # type=file_exists:   path: "~/..."
    # type=file_age_max_h: path: "~/...", max_age_h: 26
    # type=grep:          path: "...", pattern: "..."
    # type=launchd_label: label defaults to edge id; bad_exit_ok: false
    # type=md5_pair:      path_a: "...", path_b: "..." (DRIFTED edges: pass = still drifted? no:
    #                     pass = files identical; declare expected: identical|drifted)

Kind-default probes (when no explicit probe):
  kind=launchd on the current/reachable machine → launchd_label(id)

Usage:
  apps/backend-rag/.venv/bin/python scripts/verify_connectome.py [--json out.json]
      [--edges-dir docs/connectome/edges] [--only-kind launchd] [--machine auto]
      [--no-ssh]

Exit codes: 0 = no REGRESSED · 1 = at least one REGRESSED · 2 = loader error.

Healthy-declared statuses: ALIVE, ARMED, GATING, SCHEDULED_ALIVE, IDENTICAL,
ALIVE-ACTIVE, ALIVE (mechanism), RUN_ONLY. Everything else counts as dead-ish
for RECOVERED detection. Substring match on the first token before whitespace.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("verify_connectome")

HEALTHY_PREFIXES = (
    "ALIVE",
    "ARMED",
    "GATING",
    "SCHEDULED_ALIVE",
    "IDENTICAL",
    "RUN_ONLY",
    "OK",
)

SSH_HOSTS: dict[str, str] = {
    # logical machine -> ssh alias (LAN-first: Tailscale degrades silently)
    "pro": "pro-lan",
}

PROBE_TIMEOUT_S = 30

# ssh's own failures (name resolution, connect, auth) exit 255; anything else is
# the remote command's status passed through. Only the former is a flap.
SSH_TRANSPORT_RC = 255
PROBE_SSH_ATTEMPTS = 3
PROBE_RETRY_BACKOFF_S = 1.0


def detect_machine() -> str:
    user = getpass.getuser()
    host = socket.gethostname().lower()
    if user == "balizero":
        return "m5"
    if "mini" in host:
        return "mini"
    if user == "nuzantara":
        return "pro"
    return "unknown"


def is_healthy(declared: str) -> bool:
    head = (declared or "").strip().upper()
    return any(head.startswith(p) for p in HEALTHY_PREFIXES)


LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

#: Where a retirement is *declared* rather than merely performed. The live dir
#: records what happened to the file; the repo records what we MEANT.
REPO_LAUNCHAGENTS_DIR = Path(__file__).resolve().parent.parent / "infra" / "launchagents"

#: Suffix fragments that ASSERT an intentional retirement.
#:
#: `bak`/`pre-` are deliberately NOT here. A backup is not a retirement: a job
#: that was backed up and then LOST looks exactly like `<label>.plist.bak-*`
#: with no active plist, and treating that as a firebreak would mask a genuine
#: silent death — the one thing this function promises never to do (W94: the
#: fix of an over-match births the under-match twin). The bare `.bak` suffix
#: below predates this list and is kept as-is; narrowing it is a separate
#: question with its own measurement to do.
RETIREMENT_MARKERS = ("disabled", "superseded", "retired", "archived")


def _asserts_retirement(suffix: str) -> bool:
    """Judge the SUFFIX, never the whole filename.

    The label is part of the filename, so `com.balizero.retired-feeder.plist.example`
    would read as a retirement under a whole-name test — a template excusing a job
    that was never installed. Every predicate is a place where a form can lie about
    an entity (W105); this one is asked about the part that carries the assertion.
    """
    low = suffix.lower()
    return any(m in low for m in RETIREMENT_MARKERS) or low == "bak"


def plist_intentionally_disabled(label: str) -> str | None:
    """If a LaunchAgent plist for `label` exists ONLY in a retired/renamed form,
    the edge is a deliberate firebreak, not a regression. Returns the filename.

    An active plist == exactly '<label>.plist'. An active-but-dead plist still has
    '<label>.plist' present → returns None → it still REGRESSES (a genuine silent
    death is never masked).

    TWO PLACES, because a retirement can be recorded in either (2026-08-09).
    `com.balizero.wr2.newsletter` was retired on 2026-07-15 — superseded by a Fly
    daily task — and the retirement was declared IN THE REPO
    (`…plist.disabled-2026-07-15-superseded-by-fly-daily-task`), while the live dir
    kept only `…plist.bak-tcc-20260716` from the July TCC move. Looking solely at
    `~/Library/LaunchAgents` therefore read a deliberate retirement as a regression,
    and `verify-connectome` — the guardian of the guardians — alarmed every morning
    at 07:30 on the CORRECT state (W116).

    Nobody saw it: both of its P0s were dropped `p0_overflow`, so the false alarm
    was invisible AND the channel was proven unable to carry a true one.

    TWO IDIOMS as well as two places (added 2026-08-09, hours after the above went
    live and left exactly one label still REGRESSED). A retirement is recorded
    EITHER by renaming the plist with a marker suffix OR by moving the untouched
    plist into a marker-named directory — `com.balizero.nextdns-tamper-detect.weekly`
    was retired by PR #3891 with "bootout + plist moved to `.retired-2026-08-09/`",
    where the file still carries its exact name. Covering one idiom does not halve
    the false alarms; it only changes WHICH deliberate retirement is mistaken for a
    silent death (W107).
    """
    if not label.startswith("com."):
        return None
    if LAUNCHAGENTS_DIR.is_dir() and (LAUNCHAGENTS_DIR / f"{label}.plist").exists():
        return None
    prefix = f"{label}.plist."
    for directory in (LAUNCHAGENTS_DIR, REPO_LAUNCHAGENTS_DIR):
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob(f"{prefix}*")):
            if _asserts_retirement(f.name[len(prefix):]):
                return f.name

    # TWO IDIOMS, not one (found by PROVE-LIVE of the suffix cure above, same day).
    # The suffix rename is only how SOME retirements are recorded. The other way this
    # organism retires a LaunchAgent is to MOVE the untouched plist into a dated
    # directory: PR #3891 retired `com.balizero.nextdns-tamper-detect.weekly` with
    # "bootout + plist moved to `.retired-2026-08-09/`", so on disk the file is still
    # named exactly `<label>.plist` and `glob("<label>.plist.*")` cannot see it. The
    # first cure shipped, went live on Pro, and left that label as the one remaining
    # REGRESSED — a guardian still alarming every morning on a deliberate retirement,
    # which is the exact disease the first cure existed to end (W116). Curing one
    # idiom of two does not halve the noise; it only changes WHICH intentional
    # retirement is mistaken for a regression (W107).
    #
    # The directory NAME is judged by the same marker vocabulary as a suffix, never
    # the path as a whole: a label may itself contain "retired", and `infra/launchagents`
    # holds a legitimate `wrappers/` subdirectory that must never read as a firebreak
    # (W105 — the entity, not the form). Immediate children only: a recursive walk of
    # an unknown tree would be both a cost and a surprise, and every retirement idiom
    # measured on this fleet is exactly one level deep.
    for directory in (LAUNCHAGENTS_DIR, REPO_LAUNCHAGENTS_DIR):
        if not directory.is_dir():
            continue
        for sub in sorted(p for p in directory.iterdir() if p.is_dir()):
            if not _asserts_retirement(sub.name):
                continue
            if (sub / f"{label}.plist").exists():
                return f"{sub.name}/{label}.plist"
            for f in sorted(sub.glob(f"{prefix}*")):
                if _asserts_retirement(f.name[len(prefix):]):
                    return f"{sub.name}/{f.name}"
    return None


@dataclass
class ProbeResult:
    ok: bool
    detail: str = ""


@dataclass
class EdgeReport:
    edge_id: str
    kind: str
    machine: str
    declared: str
    verdict: str
    detail: str = ""
    source_file: str = ""


_SSH_INVOCATION_RE = re.compile(r"(?:^|[|;&]\s*|\bthen\s+|\bdo\s+)ssh\s")


def _ssh_bearing(cmd: str, via: str) -> bool:
    """Does this probe cross the network via ssh — however it was spelled?

    `via: ssh:<host>` is the obvious half. The other half is a `type: cmd` probe
    that shells out to ssh itself and therefore runs with via=local, which is how
    the ssh_link edges are actually declared:

        probe: { type: cmd, cmd: "ssh -o ConnectTimeout=8 pro-lan true" }

    Keying the retry off `via` alone missed exactly the edge whose flap motivated
    it. Anchored to a command position (start of line, after a pipe/semicolon/&,
    after then/do) and requiring trailing whitespace, so a path that merely
    contains the letters — `test -e ~/.ssh/config` — is not mistaken for an
    invocation.
    """
    return via.startswith("ssh:") or bool(_SSH_INVOCATION_RE.search(cmd))


def _run(cmd: str, via: str, no_ssh: bool) -> ProbeResult:
    """Run one probe, retrying only when the ssh TRANSPORT failed.

    A single attempt makes this verifier report the network instead of the
    organism. This fleet's aliases resolve over mDNS, which blips: one failed
    `ssh true` in ssh_reachable() marks the whole machine unreachable, so every
    edge on it becomes SKIPPED and any ssh-probed edge declared healthy flips to
    REGRESSED — a false alarm plus a silently blanked census. Measured on m5
    during a real blip: 1 REGRESSED (`Could not resolve hostname`) and 194 of 354
    edges SKIPPED, from that one name lookup.

    What is retried is deliberately narrow. ssh reserves exit 255 for its OWN
    failures and otherwise passes the remote command's status through, so 255 /
    timeout / spawn-error are the transport, while any other non-zero is a real
    verdict from a probe that actually ran (`launchctl list | grep` exiting 1
    means the label is absent — retrying that would only make a true negative
    slow). Probes that never touch ssh are never retried: no transport to flap.

    Retrying does not make a dead link green — measured the same day: pro-lan
    failed 5/5 real attempts with rc 255, and stays REGRESSED. What changes is
    that a link which comes back on attempt 2 no longer costs the census a
    machine.

    Every retry is recorded in the returned detail — a verifier that quietly
    papers over a flaky link is the disease it exists to catch (cicatrix #8).
    """
    if via.startswith("ssh:"):
        if no_ssh:
            return ProbeResult(False, "ssh disabled (--no-ssh)")
        host = via.split(":", 1)[1]
        full = ["ssh", "-o", "ConnectTimeout=8", host, cmd]
    else:
        full = ["/bin/bash", "-lc", cmd]

    is_ssh = _ssh_bearing(cmd, via)
    attempts = PROBE_SSH_ATTEMPTS if is_ssh else 1
    detail = ""

    for attempt in range(1, attempts + 1):
        transport_failed = False
        try:
            proc = subprocess.run(
                full, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S
            )
        except subprocess.TimeoutExpired:
            detail, transport_failed = f"timeout {PROBE_TIMEOUT_S}s", True
        except OSError as exc:
            detail, transport_failed = f"spawn error: {exc}", True
        else:
            out = (proc.stdout or "") + (proc.stderr or "")
            detail = out.strip()[:300]
            if proc.returncode == 0:
                if attempt > 1:
                    detail = f"[ok after {attempt} attempts] {detail}".strip()
                return ProbeResult(True, detail)
            # Remote command ran and said no — that is an answer, not a flap.
            if not (is_ssh and proc.returncode == SSH_TRANSPORT_RC):
                return ProbeResult(False, detail)
            transport_failed = True

        if not transport_failed or attempt == attempts:
            break
        time.sleep(PROBE_RETRY_BACKOFF_S * attempt)

    suffix = f" [transport failed {attempts}x]" if attempts > 1 else ""
    return ProbeResult(False, (detail + suffix).strip()[:300])


def _expand(path: str, via: str) -> str:
    # ~ expansion must happen on the TARGET machine for ssh probes
    return os.path.expanduser(path) if via == "local" else path


def _normalize_via(via: str, this_machine: str) -> str:
    """An explicit ssh:<alias> that points at THIS machine must run locally.

    The alias only resolves from OTHER machines (e.g. pro-lan exists on M5,
    not on the Pro itself) — without this, a Pro-side cron self-ssh-fails
    every pro-edge into a false REGRESSED.
    """
    if via.startswith("ssh:") and SSH_HOSTS.get(this_machine) == via.split(":", 1)[1]:
        return "local"
    return via


def run_probe(edge: dict[str, Any], no_ssh: bool, this_machine: str) -> ProbeResult | None:
    """Return ProbeResult, or None if the edge has no runnable probe."""
    probe = edge.get("probe")
    kind = edge.get("kind", "")
    machine = str(edge.get("machine", "")).lower()

    # Kind-default probe: launchd label liveness
    if probe is None and kind == "launchd":
        label = edge.get("id", "")
        if not label.startswith("com."):
            return None
        probe = {"type": "launchd_label", "label": label}
        if machine and machine != this_machine:
            if machine in SSH_HOSTS:
                probe["via"] = f"ssh:{SSH_HOSTS[machine]}"
            else:
                return ProbeResult(False, f"machine {machine} unreachable (no ssh map)")

    if probe is None:
        return None

    via = _normalize_via(probe.get("via", "local"), this_machine)
    ptype = probe.get("type", "cmd")

    if ptype == "cmd":
        res = _run(probe["cmd"], via, no_ssh)
        if res.ok and probe.get("expect_regex"):
            if not re.search(probe["expect_regex"], res.detail, re.MULTILINE):
                return ProbeResult(False, f"regex miss: {res.detail[:120]}")
        return res

    if ptype == "file_exists":
        path = probe["path"]
        if via == "local":
            ok = Path(_expand(path, via)).exists()
            return ProbeResult(ok, path if ok else f"ENOENT {path}")
        return _run(f"test -e {shlex.quote(path)}", via, no_ssh)

    if ptype == "file_age_max_h":
        path, max_h = probe["path"], float(probe.get("max_age_h", 26))
        if via == "local":
            p = Path(_expand(path, via))
            if not p.exists():
                return ProbeResult(False, f"ENOENT {path}")
            age_h = (time.time() - p.stat().st_mtime) / 3600
            return ProbeResult(age_h <= max_h, f"age {age_h:.1f}h (max {max_h}h)")
        cmd = (
            f'python3 -c "import os,time,sys;'
            f"p={path!r};"
            f's=os.stat(os.path.expanduser(p));'
            f'a=(time.time()-s.st_mtime)/3600;'
            f'print(f\'age {{a:.1f}}h\');'
            f'sys.exit(0 if a<={max_h} else 1)"'
        )
        return _run(cmd, via, no_ssh)

    if ptype == "grep":
        path, pattern = probe["path"], probe["pattern"]
        return _run(f"grep -qE {shlex.quote(pattern)} {shlex.quote(path)}", via, no_ssh)

    if ptype == "launchd_label":
        label = probe.get("label", edge.get("id", ""))
        res = _run(f"launchctl list | grep -F {shlex.quote(label)}", via, no_ssh)
        if not res.ok:
            return ProbeResult(False, f"label not loaded: {label}")
        if not probe.get("bad_exit_ok", True):
            # column 2 of launchctl list = last exit status
            m = re.search(r"^\S+\s+(-?\d+)\s", res.detail)
            if m and m.group(1) not in ("0", "-"):
                return ProbeResult(False, f"last exit {m.group(1)}")
        return res

    if ptype == "md5_pair":
        pa, pb = probe["path_a"], probe["path_b"]
        expected = probe.get("expected", "identical")

        def _md5(path: str, pvia: str) -> str | None:
            if pvia == "local":
                fp = Path(_expand(path, "local"))
                if not fp.exists():
                    return None
                return hashlib.md5(fp.read_bytes()).hexdigest()
            r = _run(f"md5 -q {shlex.quote(path)}", pvia, no_ssh)
            return r.detail.split()[0] if r.ok and r.detail else None

        via_a = _normalize_via(probe.get("via_a", via), this_machine)
        via_b = _normalize_via(probe.get("via_b", via), this_machine)
        ha, hb = _md5(pa, via_a), _md5(pb, via_b)
        if ha is None or hb is None:
            return ProbeResult(False, f"missing copy a={ha is not None} b={hb is not None}")
        same = ha == hb
        ok = same if expected == "identical" else not same
        return ProbeResult(ok, "identical" if same else f"DRIFT {ha[:8]}≠{hb[:8]}")

    return ProbeResult(False, f"unknown probe type {ptype}")


def load_edges(edges_dir: Path) -> list[tuple[dict[str, Any], str]]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.error("PyYAML required — run under apps/backend-rag/.venv")
        sys.exit(2)
    out: list[tuple[dict[str, Any], str]] = []
    for f in sorted(edges_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.error("YAML parse failure in %s: %s", f.name, exc)
            sys.exit(2)
        for edge in doc.get("edges", []):
            if isinstance(edge, dict) and edge.get("id"):
                out.append((edge, f.name))
    return out


def ssh_reachable(no_ssh: bool) -> set[str]:
    if no_ssh:
        return set()
    reachable = set()
    for machine, alias in SSH_HOSTS.items():
        r = _run("true", f"ssh:{alias}", no_ssh=False)
        if r.ok:
            reachable.add(machine)
    return reachable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--edges-dir", default="docs/connectome/edges")
    parser.add_argument("--json", dest="json_out", default=None)
    parser.add_argument("--only-kind", default=None)
    parser.add_argument("--machine", default="auto")
    parser.add_argument("--no-ssh", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    this_machine = detect_machine() if args.machine == "auto" else args.machine
    edges_dir = Path(args.edges_dir)
    if not edges_dir.is_dir():
        logger.error("edges dir not found: %s", edges_dir)
        return 2

    edges = load_edges(edges_dir)
    reachable = ssh_reachable(args.no_ssh)
    logger.info(
        "machine=%s edges=%d ssh_reachable=%s", this_machine, len(edges), sorted(reachable)
    )

    reports: list[EdgeReport] = []
    for edge, src in edges:
        if args.only_kind and edge.get("kind") != args.only_kind:
            continue
        declared = str(edge.get("status", "UNKNOWN"))
        machine = str(edge.get("machine", "")).lower()

        # Skip probes that need an unreachable remote machine
        needs_remote = machine not in ("", this_machine, "github", "cloud", "fly")
        if needs_remote and machine not in reachable and machine != this_machine:
            probe = edge.get("probe")
            derivable = probe is not None or edge.get("kind") == "launchd"
            if derivable:
                reports.append(
                    EdgeReport(edge["id"], edge.get("kind", ""), machine, declared,
                               "SKIPPED", f"{machine} unreachable", src)
                )
                continue

        result = run_probe(edge, args.no_ssh, this_machine)
        if result is None:
            reports.append(
                EdgeReport(edge["id"], edge.get("kind", ""), machine, declared,
                           "STATIC", "", src)
            )
            continue

        healthy = is_healthy(declared)
        if result.ok and healthy:
            verdict = "CONFIRMED"
        elif result.ok and not healthy:
            verdict = "RECOVERED"
        elif not result.ok and healthy:
            # Before calling a failed-probe healthy edge REGRESSED, distinguish a
            # deliberate firebreak (plist intentionally renamed *.disabled-*) and a
            # completed one-shot (its sentinel exists on disk) from a true silent
            # death — both are "Esiste≠Armato" (#2): census says ALIVE but the
            # activation state on disk says intentionally-not-armed.
            disabled_as = (
                plist_intentionally_disabled(edge["id"])
                if (machine in ("", this_machine) and edge.get("kind") == "launchd")
                else None
            )
            sentinel = edge.get("oneshot_sentinel")
            sentinel_present = bool(
                sentinel and Path(os.path.expanduser(str(sentinel))).exists()
            )
            if disabled_as:
                verdict = "DISABLED"
                result = ProbeResult(False, f"intentional firebreak: {disabled_as}")
            elif sentinel_present:
                verdict = "COMPLETED"
                result = ProbeResult(False, f"one-shot done: sentinel {sentinel}")
            else:
                verdict = "REGRESSED"
        else:
            verdict = "CONFIRMED"  # declared dead, still dead
        reports.append(
            EdgeReport(edge["id"], edge.get("kind", ""), machine, declared,
                       verdict, result.detail, src)
        )

    counts: dict[str, int] = {}
    for r in reports:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    regressed = [r for r in reports if r.verdict == "REGRESSED"]
    recovered = [r for r in reports if r.verdict == "RECOVERED"]

    logger.info("verdicts: %s", counts)
    for r in regressed:
        logger.warning("REGRESSED %-50s [%s/%s] %s", r.edge_id, r.kind, r.machine, r.detail)
    for r in recovered:
        logger.info("RECOVERED %-50s [%s/%s] — update census status", r.edge_id, r.kind, r.machine)

    if args.json_out:
        payload = {
            "ts": time.time(),
            "machine": this_machine,
            "counts": counts,
            "reports": [r.__dict__ for r in reports],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=1))
        logger.info("json written: %s", args.json_out)

    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
