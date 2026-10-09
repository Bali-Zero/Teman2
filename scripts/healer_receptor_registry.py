#!/usr/bin/env python3
"""healer_receptor_registry.py — the healer's registry-driven receptor.

DNA/GENOME mutation (research/operations/2026-07-06-dna-self-healing-genome.md §4c):
the healer discovers its patients from organs_registry.yaml + the local heartbeat
sidecar dir — ZERO hardcoded organ lists. An organ born via organ_birth.py
(registry entry + heartbeat gene, enforced by the conformance gate) is covered
by the healer on its next tick with no healer edits: coverage auto-extends as
the organism grows.

Panel-hardened semantics (red-team 2026-07-06):
  - an organ with NO sidecar on this node is NEVER_ARMED, not dead — kills the
    registry-vs-deployment race (merge lands before install) and registry
    runtime-drift false positives (mata_garuda entries saying mini, running on
    Pro). Arming debt is the LEDGER's job (G7/W81), not this receptor's.
  - sidecar status 'disabled' is EXEMPT (kill-switch or wrong-node guard wrote
    it) — the healer must never resurrect an intentionally-stopped organ.
  - registry entries with enabled: false or expected_hb_seconds <= 0 are skipped
    (liveness-exempt by declaration).
  - dead = sidecar age > 3 × expected_hb_seconds, or status not in the healthy
    set (same classification as scripts/sentinel-aggregate.py) — EXCEPT, on
    Pro, a fresh sidecar whose unhealthy status comes with the producer's own
    proof that its detector completed: that organ is ALIVE WITH FINDINGS (it
    ran on time and honestly reported what it found), listed under `findings`,
    never `dead`. The proof is a closed allowlist of live producer shapes
    (_COMPLETION_PROOF, one entry per producer); anything else stays dead with a note.
  - malformed sidecar = dead with note (the organ's writer is broken — W54:
    a timestamp-format drift once killed a staleness check silently).
  - Mini legacy dialect (~/heartbeat/<label>.ts) is NOT read — declared blind
    spot, surfaced in the JSON output so the blindness is visible, not silent.

Exit codes (consumed by infra/healer/healer-run.sh receptor 4):
  0 = no dead organs · 1 = dead organs found (actionable) · 2 = receptor broken
  (registry unreadable etc.) — the healer treats 2 as ACTIONABLE TOO: a broken
  receptor is silent coverage loss (#2 Esiste≠Armato) and is itself curable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

HEALTHY_STATUSES = {"ok", "success", "healthy", "starting", "running"}
CURES = {"session", "owner"}
# The same entity proprioception.py's launchd classifier reads in a log_marker:
# the macOS TCC denial text. "Permission denied" (EACCES, a chmod) is NOT it.
TCC_DENIAL = "operation not permitted"
LAUNCHCTL_NOT_FOUND = 113
EXEMPT_STATUSES = {"disabled"}
DEAD_MULTIPLIER = 3
_REEXEC_GUARD_ENV = "_HEALER_REGISTRY_REEXEC_DONE"
# Project venvs known to carry PyYAML (see apps/backend-rag/requirements*.txt) —
# checked in order, first match wins. Kept short and repo-relative on purpose:
# this is a same-machine self-heal, not a general interpreter search.
_YAML_VENV_CANDIDATES = (
    "apps/backend-rag/.venv/bin/python3",
    ".venv/bin/python3",
)


def _yaml_importable() -> bool:
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


def _find_yaml_venv(repo_root: Path) -> Path | None:
    for rel in _YAML_VENV_CANDIDATES:
        candidate = repo_root / rel
        if candidate.is_file():
            return candidate
    return None


def _reexec_with_yaml_if_needed() -> None:
    """Whatever invoked us as bare `python3` may resolve to a system
    interpreter without PyYAML (Homebrew python3, W-mini 2026-07-17:
    ModuleNotFoundError crashed this receptor with exit 2 on every tick).
    Re-exec once under a project venv that has it before giving up."""
    if _yaml_importable():
        return
    if os.environ.get(_REEXEC_GUARD_ENV):
        return  # already retried — let the real ImportError surface as exit 2
    candidate = _find_yaml_venv(Path(__file__).resolve().parent.parent)
    if candidate is None:
        return
    env = dict(os.environ, **{_REEXEC_GUARD_ENV: "1"})
    os.execve(str(candidate), [str(candidate), str(Path(__file__).resolve()), *sys.argv[1:]], env)


def parse_ts(value) -> datetime | None:
    """Both live ts dialects: ISO-8601 string (G2 gene) AND numeric epoch
    (Pro fleet heartbeat lib writes float seconds — first healer-pro tick
    classified 14 healthy organs false-"dead" when this only read ISO)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def load_registry(path: Path) -> list[dict]:
    import yaml  # deferred: fail-visible via exit 2, not ImportError at --help

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    organs = data.get("organs")
    if not isinstance(organs, list):
        raise ValueError("organs_registry.yaml: organs is not a list")
    return organs


def _renamed_away_disabled_plist(agents_dir: Path, label: str) -> bool:
    """A `<label>.plist` renamed to `<label>.plist.disabled-*` (W-mini convention
    since 2026-09-25, e.g. `.disabled-20260925-owner-pro`) means the job was
    deliberately unloaded. Its stale sidecar remains a visible dead finding, but
    this entity proof makes its cure owner-only instead of spawning a session."""
    if not label or not agents_dir.is_dir():
        return False
    if (agents_dir / f"{label}.plist").exists():
        return False
    return any(agents_dir.glob(f"{label}.plist.disabled-*"))


def _tcc_denial(value: object) -> bool:
    return TCC_DENIAL in str(value).lower()


def _launchctl_print(label: str) -> tuple[bool | None, str]:
    """Loaded state plus the job's `last exit` lines (read-only).

    True = loaded, False = launchd answers "service not found" (113), None =
    unprobeable. Only the `last exit ...` lines are evidence: the rest of the
    print (program, arguments, environment) is configuration, not a verdict."""
    if not label:
        return None, ""
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""
    if result.returncode == LAUNCHCTL_NOT_FOUND:
        return False, ""
    if result.returncode != 0:
        return None, ""
    exit_lines = [
        ln.strip() for ln in result.stdout.splitlines()
        if ln.strip().startswith("last exit")
    ]
    return True, "\n".join(exit_lines)


def _dead_cure(
    organ: dict,
    payload: dict,
    agents_dir: Path,
    loaded: bool | None,
    launchctl_evidence: str,
) -> str:
    """Owner only on explicit entity/evidence; ambiguity defaults to session.

    An undeclared cure value raises: run() fails, main() exits 2 and the
    healer reads registry-receptor-broken (visible), never a silent skip."""
    declared = organ.get("cure", "session")
    if declared not in CURES:
        raise ValueError(f"organ {organ.get('id', '<no-id>')}: invalid cure {declared!r}")
    if declared == "owner":
        return "owner"
    if (
        _tcc_denial(payload.get("status", ""))
        or _tcc_denial(payload.get("note", ""))
        or _tcc_denial(launchctl_evidence)
    ):
        return "owner"
    label = (organ.get("recovery_params") or {}).get("label", "")
    owner_note = organ.get("owner_note") or organ.get("disabled_reason")
    if loaded is False and (
        _renamed_away_disabled_plist(agents_dir, label) or bool(owner_note)
    ):
        return "owner"
    return "session"


def _note_proof(pattern: str) -> Callable[[dict], str | None]:
    regex = re.compile(pattern)

    def proof(payload: dict) -> str | None:
        match = regex.match(str(payload.get("note", "")))
        return f"note:{match.group(0).strip()}" if match else None

    return proof


def _pulse_proof(payload: dict) -> str | None:
    """apps/cell/cell/main.py: a completed pulse writes exactly pulse_count, tier
    and action; a pulse that THREW writes pulse_count and `error`."""
    metadata = payload.get("metadata")
    completed = (
        isinstance(metadata, dict)
        and set(metadata) == {"pulse_count", "tier", "action"}
        and type(metadata["pulse_count"]) is int
        and metadata["pulse_count"] >= 0
    )
    return "metadata.pulse_count" if completed else None


# Closed allowlist, one entry per live producer: the organ, the status its
# detector writes when it COMPLETED and found something, and that run's sidecar
# shape. The crash / cannot-verify path writes another status or shape and stays
# dead. Not listed, so dead: pro.visa_freshness_sentinel ("rc=1" is STALE or an
# uncaught exception), prose, "detector_rc=N" alone.
_COMPLETION_PROOF = {
    # kbli-surface-conformance-run.sh: rc 1 WITH the report header
    "pro.kbli_surface_conformance": ("error", _note_proof(r"detector_rc=1 result=divergence(?:\s|$)")),
    # launchd-liveness-detector.sh: alarm count parsed from the detector's JSON
    "pro.launchd_liveness": ("degraded", _note_proof(r"[1-9][0-9]* alarm\(s\)(?:\s|$)")),
    # meta_one_steward.py: a completed tick (a crash writes "error" + the exception text)
    "pro.meta_one_steward": ("warning", _note_proof(r"token=(?:alive|dead)$")),
    # run_sentinel_cell.py: red is a completed pulse with a finding; exceptions
    # write fail and stay dead. The note carries only bounded operational tokens.
    "mata_garuda.sentinel_hourly.pro": (
        "warning",
        _note_proof(r"^pulse=red action=[A-Za-z0-9_.-]+ pulse=[0-9]+(?:\s|$)"),
    ),
    "cell.organism": ("fail", _pulse_proof),
    # ops/pro_disk_floor_tick.sh: a completed df read writes the free GB at note start;
    # 60-100 GB is `warning`. Under 60 GB is `error` ("failed: ...") and stays dead, so it
    # still spawns; "skipped: ..." and "free space unreadable" never read the disk.
    "pro.disk_floor": ("warning", _note_proof(r"free_gb=[0-9]+\.[0-9] on /\S+ \(ok > [0-9]+, failed < [0-9]+\)")),
}


def run(
    node: str,
    registry_path: Path,
    sidecar_dir: Path,
    launchagents_dir: Path | None = None,
    launchctl_probe: Callable[[str], tuple[bool | None, str]] | None = None,
) -> dict:
    organs = load_registry(registry_path)
    runtime_wanted = f"{node}_launchd"
    now = datetime.now(timezone.utc)
    agents_dir = launchagents_dir or (Path.home() / "Library" / "LaunchAgents")
    probe_launchctl = launchctl_probe or _launchctl_print

    report: dict = {
        "schema": 1, "node": node, "checked": 0, "ok": [], "stale": [],
        "dead": [], "dead_session": 0, "dead_owner": 0, "findings": [],
        "never_armed": [], "disabled": [], "skipped_exempt": 0,
        "blind_spots": [
            "legacy dialect ~/heartbeat/<label>.ts not read (grandfathered, "
            "see genome doc §6.4)"
        ],
    }

    for organ in organs:
        if organ.get("runtime") != runtime_wanted:
            continue
        if organ.get("enabled") is False:
            report["skipped_exempt"] += 1
            continue
        expected = organ.get("expected_hb_seconds") or 0
        if not isinstance(expected, (int, float)) or expected <= 0:
            report["skipped_exempt"] += 1
            continue

        oid = organ.get("id", "<no-id>")
        report["checked"] += 1
        sidecar = sidecar_dir / f"{oid}.json"
        if not sidecar.exists():
            report["never_armed"].append(oid)
            continue

        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            ts = parse_ts(payload.get("ts", ""))
            status = str(payload.get("status", ""))
        except (OSError, json.JSONDecodeError):
            payload, ts, status = {}, None, "<malformed>"

        if status in EXEMPT_STATUSES:
            report["disabled"].append(oid)
            continue

        label = (organ.get("recovery_params") or {}).get("label", "")
        # Mini's separate healer is not cure-aware yet; preserve its established
        # disabled exemption while Pro keeps the finding visible as owner-only.
        if (
            node != "pro"
            and organ.get("recovery_action") == "launchctl_kickstart"
            and _renamed_away_disabled_plist(agents_dir, label)
        ):
            report["disabled"].append(oid)
            continue
        entry = {
            "id": oid, "status": status,
            "note": str(payload.get("note", ""))[:200],
            "severity": organ.get("severity_on_silence", "warning"),
            "recovery_action": organ.get("recovery_action", ""),
            "label": label,
        }
        if ts is None:
            entry["age_s"] = None
            entry["note"] = f"malformed sidecar: {entry['note']}"
            is_dead = True
        else:
            age = (now - ts).total_seconds()
            entry["age_s"] = int(age)
            fresh = age <= DEAD_MULTIPLIER * expected
            # Mini's healer is not findings-aware: its classification is unchanged.
            if fresh and node == "pro" and status not in HEALTHY_STATUSES:
                proof_status, proof = _COMPLETION_PROOF.get(oid, (None, None))
                evidence = proof(payload) if status == proof_status else None
                if evidence:
                    entry["state"] = "alive_with_findings"
                    entry["completion_evidence"] = evidence
                    report["findings"].append(entry)
                    continue
                entry["note"] = f"no detector completion evidence: {entry['note']}"
            is_dead = not fresh or status not in HEALTHY_STATUSES

        if is_dead:
            loaded, launchctl_evidence = (None, "")
            if organ.get("recovery_action") == "launchctl_kickstart" and label:
                loaded, launchctl_evidence = probe_launchctl(label)
            entry["cure"] = _dead_cure(
                organ, payload, agents_dir, loaded, launchctl_evidence
            )
            report["dead"].append(entry)
            report[f"dead_{entry['cure']}"] += 1
        elif age > expected:
            report["stale"].append(entry)
        else:
            report["ok"].append(oid)

    report["exit"] = 1 if report["dead"] else 0
    return report


def main(argv: list[str] | None = None) -> int:
    _reexec_with_yaml_if_needed()
    ap = argparse.ArgumentParser(description="Registry-driven dead-organ receptor")
    ap.add_argument("--node", required=True, choices=["mini", "pro"])
    ap.add_argument("--registry", default=None)
    ap.add_argument("--sidecar-dir", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    registry_path = Path(
        args.registry
        or Path(__file__).resolve().parent.parent
        / "apps/organism/organism/organs_registry.yaml"
    )
    sidecar_dir = Path(args.sidecar_dir or Path.home() / ".organism/last_seen")

    try:
        report = run(args.node, registry_path, sidecar_dir)
    except Exception as exc:  # noqa: BLE001 — receptor-broken is its own exit class
        broken = {"schema": 1, "node": args.node, "receptor_broken": f"{type(exc).__name__}: {exc}", "exit": 2}
        print(json.dumps(broken) if args.json else f"RECEPTOR BROKEN: {broken['receptor_broken']}",
              file=sys.stderr if not args.json else sys.stdout)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            f"node={report['node']} checked={report['checked']} ok={len(report['ok'])} "
            f"stale={len(report['stale'])} dead={len(report['dead'])} "
            f"dead_session={report['dead_session']} dead_owner={report['dead_owner']} "
            f"findings={len(report['findings'])} "
            f"never_armed={len(report['never_armed'])} disabled={len(report['disabled'])}"
        )
        for d in report["dead"]:
            print(f"  DEAD {d['id']} age={d['age_s']}s status={d['status']} ({d['severity']})")
        for f in report["findings"]:
            print(f"  FINDINGS {f['id']} age={f['age_s']}s status={f['status']} ({f['completion_evidence']})")
        for oid in report["never_armed"]:
            print(f"  NEVER-ARMED {oid} (ledger's job, not a healer target)")
    return report["exit"]


if __name__ == "__main__":
    sys.exit(main())
