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
    set (same classification as scripts/sentinel-aggregate.py).
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
import sys
from datetime import datetime, timezone
from pathlib import Path

HEALTHY_STATUSES = {"ok", "success", "healthy", "starting", "running"}
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


def run(node: str, registry_path: Path, sidecar_dir: Path) -> dict:
    organs = load_registry(registry_path)
    runtime_wanted = f"{node}_launchd"
    now = datetime.now(timezone.utc)

    report: dict = {
        "schema": 1, "node": node, "checked": 0, "ok": [], "stale": [],
        "dead": [], "never_armed": [], "disabled": [], "skipped_exempt": 0,
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

        entry = {
            "id": oid, "status": status,
            "note": str(payload.get("note", ""))[:200],
            "severity": organ.get("severity_on_silence", "warning"),
            "recovery_action": organ.get("recovery_action", ""),
            "label": (organ.get("recovery_params") or {}).get("label", ""),
        }
        if ts is None:
            entry["age_s"] = None
            entry["note"] = f"malformed sidecar: {entry['note']}"
            report["dead"].append(entry)
            continue

        age = (now - ts).total_seconds()
        entry["age_s"] = int(age)
        if age > DEAD_MULTIPLIER * expected or status not in HEALTHY_STATUSES:
            report["dead"].append(entry)
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
            f"never_armed={len(report['never_armed'])} disabled={len(report['disabled'])}"
        )
        for d in report["dead"]:
            print(f"  DEAD {d['id']} age={d['age_s']}s status={d['status']} ({d['severity']})")
        for oid in report["never_armed"]:
            print(f"  NEVER-ARMED {oid} (ledger's job, not a healer target)")
    return report["exit"]


if __name__ == "__main__":
    sys.exit(main())
