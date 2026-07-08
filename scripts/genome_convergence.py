#!/usr/bin/env python3
"""genome_convergence.py — deterministic PICKER for the genome convergence mission.

CONVERGENCE v2 (research/operations/2026-07-06-dna-self-healing-genome.md §CONVERGENCE,
panel-hardened by Codex+Grok+GLM round 2): the healer retrofits genes into ONE
grandfathered organ at a time — but only an organ this picker declares ELIGIBLE.
Eligibility is deterministic and conservative; no candidate = honest empty (exit 3),
zero LLM spend. The picker never edits anything.

Eligibility rails (each one traces to a panel finding):
  R1 payload in-perimeter — genome machinery, hooks, workflows, healer itself,
     mandates, backend-rag, mouth, migrations are EXCLUDED (Codex 8: the healer
     must not touch the contract it is judged by).
  R2 schedule ≤ 24h — StartInterval ≤ 86400 or a daily StartCalendarInterval;
     weekly/monthly organs break days later, natural proof too slow (Codex 6).
  R3 retrofittable genes only — missing ⊆ {G1,G2,G4,G5,G9,G10}; G6 (spawn) and
     G8 (KeepAlive) are semantics changes, human-gated (GLM d); G3 (pair
     declaration) needs a live-promotion decision, human-gated.
  R4 live parity — if the payload is a declared HOME pair, the live copy must be
     blob-identical to repo canon RIGHT NOW on its node (Grok rail 1 / GLM S3);
     local node checked directly, pro checked via read-only ssh. Unverifiable =
     ineligible.
  R5 bash wrapper, anchorable — repo wrapper exists, is .sh, has a shebang.
  R6 JSON dialect only — organs on Mini's legacy ~/heartbeat/*.ts protocol are
     skipped until the one-cut migration (GLM S4).

Output: JSON plan for the ONE chosen organ (smallest missing-set first — fastest
wins shrink the baseline soonest), or {"eligible": 0} with per-organ skip reasons.

Exit codes: 0 = candidate emitted · 3 = no eligible candidate · 2 = picker broken.
"""
from __future__ import annotations

import argparse
import json
import plistlib
import re
import socket
import subprocess
import sys
from pathlib import Path

REPO = Path(
    subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() or "."
).resolve()

GENES_PATH = REPO / "infra/organ-conformance/genes.json"
PAIRS_PATH = REPO / "infra/home-fork/declared-pairs.json"

RETROFITTABLE = {"G1_registry", "G2_heartbeat", "G4_node_guard",
                 "G5_kill_switch", "G9_fail_visible", "G10_single_instance"}

# R1 — the machinery the convergence mission must never touch (Codex 8).
FORBIDDEN_PATH_PARTS = (
    "infra/organ-conformance/", "infra/healer/", "infra/claude-hooks/",
    ".github/", "infra/guard-conformance/", "infra/scar-gates/",
    "apps/backend-rag/", "apps/mouth/", "migrations",
    # PII-adjacent runtime (SYMBIOSIS Law 2): the WhatsApp mirror chain is
    # never a target for autonomous edits — operator retrofits only.
    "apps/wa-mirror/", "wa-mirror",
)
FORBIDDEN_WRAPPERS = (
    "scripts/organ_birth.py", "scripts/genome_retrofit.py",
    "scripts/genome_convergence.py", "scripts/healer_receptor_registry.py",
)

HOSTNAME_NODES = {"Mini-Pro2": "mini", "Nuzantara": "pro"}


def _sh(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return 255, f"{type(exc).__name__}: {exc}"


def schedule_ok(plist_path: Path) -> tuple[bool, str]:
    try:
        payload = plistlib.loads(plist_path.read_bytes())
    except Exception as exc:  # noqa: BLE001
        return False, f"plist unreadable: {exc}"
    if payload.get("KeepAlive"):
        return True, "daemon (KeepAlive) — always-on, natural proof immediate"
    interval = payload.get("StartInterval")
    if isinstance(interval, int) and 0 < interval <= 86400:
        return True, f"StartInterval {interval}s"
    cal = payload.get("StartCalendarInterval")
    if cal is not None:
        entries = cal if isinstance(cal, list) else [cal]
        # daily = no Weekday/Day/Month constraint in any entry
        if all(not ({"Weekday", "Day", "Month"} & set(e.keys())) for e in entries):
            return True, "daily StartCalendarInterval"
        return False, "weekly/monthly calendar trigger (R2: proof too slow — operator)"
    return False, "no recognizable schedule ≤24h (R2)"


def resolve_repo_wrapper(plist_path: Path, ka_mod, basename_index) -> Path | None:
    try:
        payload = plistlib.loads(plist_path.read_bytes())
    except Exception:  # noqa: BLE001
        return None
    argv = ka_mod.extract_argv(payload)
    wrapper, _reason = ka_mod.resolve_wrapper(argv, REPO, basename_index)
    return wrapper


def live_parity(pair: dict, node_of_this_host: str | None) -> tuple[bool, str]:
    """R4: live HOME copy blob == repo canon blob, on the pair's node, NOW."""
    repo_rel = pair["repo"]
    rc, canon_blob = _sh(["git", "-C", str(REPO), "rev-parse", f"origin/main:{repo_rel}"])
    if rc != 0:
        return False, f"canon blob unresolvable for {repo_rel}"
    live = pair["live"]
    machines = [m for m in pair.get("machines", []) if m in ("pro", "mini")] or ["mini"]
    for machine in machines:
        if machine == node_of_this_host:
            rc, live_blob = _sh(["git", "hash-object", str(Path(live).expanduser())])
        else:
            rc, live_blob = _sh(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", machine,
                 f"git hash-object {live}"], timeout=25)
        if rc != 0:
            return False, f"live blob unreadable on {machine} (R4: unverifiable = ineligible)"
        if live_blob.splitlines()[-1] != canon_blob:
            return False, f"live copy DIVERGED from canon on {machine} (R4 — do not clobber)"
    return True, f"live==canon on {'+'.join(machines)}"


def pick(limit: int = 1) -> dict:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lint_plist_keepalive", REPO / "scripts/lint_plist_keepalive.py")
    ka_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ka_mod)

    genes_doc = json.loads(GENES_PATH.read_text(encoding="utf-8"))
    grandfathered: dict[str, list[str]] = genes_doc.get("grandfathered", {})
    pairs_doc = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    pairs_by_repo = {p["repo"]: p for p in pairs_doc.get("pairs", [])}

    errors: list[str] = []
    basename_index = ka_mod.build_basename_index(
        [REPO / r for r in genes_doc.get("scan_roots", ["infra", "apps", "scripts"])], errors)

    node_here = HOSTNAME_NODES.get(socket.gethostname().split(".")[0])

    skips: list[dict] = []
    candidates: list[dict] = []

    for rel_path, missing in sorted(grandfathered.items(), key=lambda kv: len(kv[1])):
        entry = {"plist": rel_path, "missing": missing}

        if any(part in rel_path for part in FORBIDDEN_PATH_PARTS):
            entry["skip"] = "R1: genome/constitution-adjacent path"
            skips.append(entry); continue

        not_retrofittable = set(missing) - RETROFITTABLE
        if not_retrofittable:
            entry["skip"] = f"R3: human-gated genes {sorted(not_retrofittable)}"
            skips.append(entry); continue

        plist_path = REPO / rel_path
        if not plist_path.exists():
            entry["skip"] = "plist missing on disk"
            skips.append(entry); continue

        ok, why = schedule_ok(plist_path)
        if not ok:
            entry["skip"] = why
            skips.append(entry); continue
        entry["schedule"] = why

        wrapper = resolve_repo_wrapper(plist_path, ka_mod, basename_index)
        if wrapper is None or not str(wrapper).endswith(".sh"):
            entry["skip"] = "R5: wrapper unresolved or not a bash script"
            skips.append(entry); continue
        wrapper_rel = str(wrapper.relative_to(REPO)) if wrapper.is_relative_to(REPO) else str(wrapper)
        if wrapper_rel in FORBIDDEN_WRAPPERS or any(
                part in wrapper_rel for part in FORBIDDEN_PATH_PARTS):
            entry["skip"] = "R1: wrapper is genome machinery"
            skips.append(entry); continue
        try:
            head = wrapper.read_text(encoding="utf-8", errors="replace")[:200]
        except OSError:
            entry["skip"] = "R5: wrapper unreadable"
            skips.append(entry); continue
        if not head.startswith("#!"):
            entry["skip"] = "R5: no shebang anchor"
            skips.append(entry); continue
        entry["wrapper"] = wrapper_rel

        # R4 hole guard (Grok 2 / GLM S3): a HOME-pointing payload with NO
        # declared pair means the LIVE state is unknowable — the basename
        # fallback that resolved the repo wrapper says nothing about what
        # launchd actually executes. Unverifiable = ineligible.
        try:
            payload = plistlib.loads(plist_path.read_bytes())
            argv = ka_mod.extract_argv(payload)
        except Exception:  # noqa: BLE001
            argv = []
        home_token = next(
            (tok for tok in argv
             if re.match(r"^(?:~|\$HOME|/Users/[^/]+)/(?!Desktop/nuzantara/)", tok)),
            None)
        pair = pairs_by_repo.get(wrapper_rel)
        if home_token and pair is None:
            entry["skip"] = f"R4: HOME payload without declared pair ({home_token}) — live unknowable"
            skips.append(entry); continue
        if pair is not None:
            ok, why = live_parity(pair, node_here)
            if not ok:
                entry["skip"] = why
                skips.append(entry); continue
            entry["pair"] = {**pair, "parity": why}

        candidates.append(entry)
        if len(candidates) >= limit:
            break

    return {
        "schema": 1,
        "eligible": len(candidates),
        "candidates": candidates,
        "skipped": len(skips),
        "skip_reasons": skips[:40],
        "grandfathered_total": len(grandfathered),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Genome convergence picker (deterministic)")
    ap.add_argument("--pick", action="store_true", help="emit the next eligible organ plan")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        report = pick(limit=args.limit if args.pick else 10_000)
    except Exception as exc:  # noqa: BLE001 — picker-broken is its own exit class
        print(json.dumps({"picker_broken": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"grandfathered={report['grandfathered_total']} eligible={report['eligible']} "
              f"skipped={report['skipped']}")
        for c in report["candidates"]:
            print(f"  CANDIDATE {c['plist']} missing={c['missing']} ({c.get('schedule','')})")
    return 0 if report["eligible"] > 0 else 3


if __name__ == "__main__":
    sys.exit(main())
