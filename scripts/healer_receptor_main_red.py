#!/usr/bin/env python3
"""healer_receptor_main_red.py — receptor 8: a REQUIRED check red on main.

RULING (Zero, 2026-09-09): "tutto ciò che succede nel sistema non deve aspettare
me per un fix". A required status check that is red on `main` stalls the whole
merge queue (every armed PR inherits the red and sits BLOCKED) and, until this
receptor, nothing in the organism *sensed* it: the healer's seven receptors look
at organs, ledgers, hooks and sessions — never at the branch every PR must pass.

WHAT "RED ON MAIN" MEANS HERE (measured 2026-09-09 before writing this):
main's HEAD commit was a docs-only merge, so `Backend Static (Python)` was
`skipped` on it — while the same context was `failure` two commits earlier and
every PR was BLOCKED on exactly that. A receptor that reads HEAD only would have
said GREEN. So, per required context, this walks main's history from HEAD back
(`--depth`, default 20) to the newest check-run whose conclusion is not
skipped/neutral: that conclusion IS the effective state of the context on main.
`in_progress` on HEAD is PENDING (neither red nor green, stop walking).

For each red context it collects what a curing session needs to start without a
blind rerun: the run/job URL, the failed steps of the failing job and the tail
of that job's log (ANSI/timestamps stripped, capped). It NEVER calls
`gh run rerun` — "never rerun a red check before you know WHY it is red"
(Builder Contract §1); the test suite asserts the absence of that call.

ESCALATION + DEDUPE: one HIGH pending line per (context, sha) is appended to
`shared/escalations_pro.jsonl` (the LIVE board every SessionStart surfaces
HIGH-first, so ANY Claude session — not only the healer — picks it up). The
(context, sha) pair is remembered in the state file; a later tick on the same
red appends nothing. When the context turns green on a newer sha, a
`status: resolved` line is appended for the same `job` so the board nets it out
(escalations_alert_sessionstart.sh resolution semantics).

CURE LANE: the healer mandate's curable perimeter excludes `.github/workflows/**`
and `apps/**`, which is where a required-check red usually lives; the escalation
therefore names `cure_lane.owner = "session"` (first Claude session that reads
the board) with a suggested branch `agent/<host>/infra/main-red-<context-slug>`.
The healer wrapper still goes ACTIONABLE on exit 1 (a healer session triages
per its mandate: cure if under scripts/infra/docs, otherwise leave the HIGH row
to the next session — it is already on the board).

Kill switch: `HEALER_MAIN_RED_OFF=1` (exit 0, `{"disabled": true}`).

Exit codes (same contract as healer_receptor_registry.py):
  0 = no required context red · 1 = red found (actionable) · 2 = receptor BLIND
  (required contexts or main history unreadable via gh) — actionable too.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ESCALATIONS = REPO_ROOT / "shared" / "escalations_pro.jsonl"
DEFAULT_STATE = Path("~/.organism/healer/main_red_state.json")
KILL_SWITCH_ENV = "HEALER_MAIN_RED_OFF"
JOB_PREFIX = "main-required-red:"

RED = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
NOT_A_VERDICT = {"skipped", "neutral", None, ""}
LOG_TAIL_LINES = 25
LOG_TAIL_CHARS = 1500
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[0-9:.]+Z\s?")
_JOB_URL_RE = re.compile(r"/actions/runs/(\d+)/job/(\d+)")

GhFn = Callable[[str], object]


# --------------------------------------------------------------------------
# gh transport (swapped for a dict-backed fake in tests)
# --------------------------------------------------------------------------
class GhError(RuntimeError):
    pass


def gh_api(path: str) -> object:
    """`gh api <path>`; raises GhError on non-zero exit or non-JSON output.
    Job logs (`.../logs`) come back as text and are returned as str."""
    cmd = ["gh", "api", path]
    if path.endswith("/logs"):  # raw job log: gh refuses ANSI unless told; we strip it ourselves
        cmd.append("--allow-escape-sequences")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhError((proc.stderr or proc.stdout).strip()[:300])
    if path.endswith("/logs"):
        return proc.stdout
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise GhError(f"non-JSON from gh api {path}: {exc}") from exc


# --------------------------------------------------------------------------
# sensing
# --------------------------------------------------------------------------
def required_contexts(gh: GhFn, branch: str) -> list[str]:
    out: list[str] = []
    prot = gh(f"repos/{{owner}}/{{repo}}/branches/{branch}/protection/required_status_checks")
    for c in (prot or {}).get("contexts") or []:
        if c not in out:
            out.append(c)
    try:  # rulesets are optional — their absence is not blindness
        rules = gh(f"repos/{{owner}}/{{repo}}/rules/branches/{branch}")
    except GhError:
        rules = []
    for r in rules or []:
        if r.get("type") != "required_status_checks":
            continue
        for c in (r.get("parameters") or {}).get("required_status_checks") or []:
            ctx = c.get("context")
            if ctx and ctx not in out:
                out.append(ctx)
    return out


def main_shas(gh: GhFn, branch: str, depth: int) -> list[str]:
    commits = gh(f"repos/{{owner}}/{{repo}}/commits?sha={branch}&per_page={depth}")
    return [c["sha"] for c in commits or [] if c.get("sha")]


def check_runs(gh: GhFn, sha: str) -> list[dict]:
    data = gh(f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs?per_page=100")
    return list((data or {}).get("check_runs") or [])


def effective_state(contexts: list[str], shas: list[str], gh: GhFn) -> dict[str, dict]:
    """Per context: the newest non-skipped conclusion walking main from HEAD."""
    pending = {c: None for c in contexts}
    for depth, sha in enumerate(shas):
        unresolved = [c for c, v in pending.items() if v is None]
        if not unresolved:
            break
        runs = check_runs(gh, sha)
        for ctx in unresolved:
            mine = [r for r in runs if r.get("name") == ctx]
            if not mine:
                continue
            if depth == 0 and any(r.get("status") != "completed" for r in mine):
                pending[ctx] = {"state": "pending", "sha": sha, "depth": 0}
                continue
            verdicts = [r for r in mine if r.get("conclusion") not in NOT_A_VERDICT]
            if not verdicts:
                continue
            newest = sorted(verdicts, key=lambda r: r.get("completed_at") or "", reverse=True)[0]
            concl = newest.get("conclusion")
            pending[ctx] = {
                "state": "red" if concl in RED else "green",
                "conclusion": concl,
                "sha": sha,
                "depth": depth,
                "url": newest.get("html_url") or newest.get("details_url") or "",
            }
    return {c: (v or {"state": "unknown", "sha": None, "depth": None}) for c, v in pending.items()}


def _clean_log_tail(text: str) -> str:
    lines = [_TS_RE.sub("", _ANSI_RE.sub("", ln)).rstrip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    # The raw tail of a GitHub job log is post-job cleanup boilerplate (git
    # credential scrubbing), never the failure. Window around the LAST
    # `##[error]` marker instead; fall back to the plain tail without one.
    errs = [i for i, ln in enumerate(lines) if "##[error]" in ln]
    if errs:
        i = errs[-1]
        window = lines[max(0, i - LOG_TAIL_LINES + 3): i + 3]
    else:
        window = lines[-LOG_TAIL_LINES:]
    return "\n".join(window)[-LOG_TAIL_CHARS:]


def enrich(gh: GhFn, url: str) -> dict:
    """Failed steps + log tail of the failing job named by a check-run URL.
    Best-effort: any gh failure here degrades to an empty field, never to
    blindness — the red itself was already sensed."""
    m = _JOB_URL_RE.search(url or "")
    empty = {"run_id": None, "job_id": None, "job": None, "failed_steps": [], "failed_jobs": [], "log_tail": ""}
    if not m:
        return empty
    run_id, job_id = m.group(1), m.group(2)
    # Every failed job of the run, not only the check's own: a required context is
    # often an AGGREGATOR ("Assert every upstream job succeeded") whose cause sits
    # in a sibling job that is not itself required (measured 2026-09-09: `Backend
    # Tests (Python)` red because `Backend Static (Python)` failed on pip-audit).
    failed_jobs: list[dict] = []
    try:
        jobs = (gh(f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs?per_page=100") or {}).get("jobs") or []
        for j in jobs:
            if j.get("conclusion") in RED:
                failed_jobs.append({"id": str(j.get("id")), "name": j.get("name"),
                                    "completed_at": j.get("completed_at") or "",
                                    "steps": [s.get("name") for s in j.get("steps") or []
                                              if s.get("conclusion") in RED]})
    except (GhError, AttributeError):
        pass
    own = next((j for j in failed_jobs if j["id"] == job_id), None)
    # log tail from the ROOT cause: the failed job that finished FIRST — a real
    # failure completes before the aggregators that fail because of it
    root = min(failed_jobs, key=lambda j: j["completed_at"]) if failed_jobs else None
    tail = ""
    if root:
        try:
            tail = _clean_log_tail(str(gh(f"repos/{{owner}}/{{repo}}/actions/jobs/{root['id']}/logs")))
        except GhError:
            pass
    return {"run_id": run_id, "job_id": job_id, "job": own["name"] if own else None,
            "failed_steps": own["steps"] if own else [], "failed_jobs": failed_jobs,
            "log_job": root["name"] if root else None, "log_tail": tail}


# --------------------------------------------------------------------------
# board + state
# --------------------------------------------------------------------------
def _slug(ctx: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ctx.lower()).strip("-")


def _load_state(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _append(path: Path, line: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def reconcile(reds: dict[str, dict], greens: set[str], *, state: dict, escalations: Path,
              writer: str, host: str, now: float) -> dict:
    """Append HIGH lines for NEW (context, sha) reds, resolved lines for contexts
    that were open and are now green. Returns {'escalated': [...], 'resolved': [...]}."""
    escalated = state.setdefault("escalated", {})
    open_ctx = state.setdefault("open", {})
    out = {"escalated": [], "resolved": []}
    for ctx, info in reds.items():
        key = f"{ctx}@{info['sha']}"
        job = JOB_PREFIX + _slug(ctx)
        if key in escalated:
            continue
        line = {
            "job": job,
            "type": "main_required_red",
            "priority": "HIGH",
            "status": "pending",
            "error_summary": (
                f"required check '{ctx}' is {info.get('conclusion')} on main@{info['sha'][:10]} "
                f"(depth {info.get('depth')}); failed jobs: "
                + "; ".join(f"{j['name']} [{', '.join(j['steps'])}]" for j in info.get("failed_jobs") or [])
            ),
            "context": ctx,
            "sha": info["sha"],
            "run_url": info.get("url", ""),
            "failed_job": info.get("job"),
            "failed_steps": info.get("failed_steps", []),
            "failed_jobs": [{"name": j["name"], "steps": j["steps"]} for j in info.get("failed_jobs") or []],
            "log_job": info.get("log_job"),
            "log_tail": info.get("log_tail", ""),
            "cure_lane": {
                "owner": "session",
                "branch": f"agent/{host}/infra/main-red-{_slug(ctx)}",
                "note": "read failed_steps + log_tail first; never rerun blind (Builder Contract §1); "
                        "healer perimeter excludes .github/workflows/** and apps/**",
            },
            "machine": writer,
            "_writer": writer,
            # ts is a NUMBER: scripts/sentinel_lib/escalations.py sorts the board on the
            # raw value, and one string next to the floats every other writer emits
            # makes read_all_escalations() raise TypeError (gate finding on #6002).
            "ts": now,
        }
        _append(escalations, line)
        escalated[key] = now
        open_ctx[ctx] = info["sha"]
        out["escalated"].append(key)
    for ctx in list(open_ctx):
        if ctx in greens:
            job = JOB_PREFIX + _slug(ctx)
            _append(escalations, {"job": job, "type": "main_required_red", "status": "resolved",
                                  "resolved_at": now, "ts": now, "machine": writer,
                                  "_writer": writer, "context": ctx})
            del open_ctx[ctx]
            out["resolved"].append(ctx)
    return out


# --------------------------------------------------------------------------
def run(*, gh: GhFn = gh_api, branch: str = "main", depth: int = 20, escalate: bool = True,
        state_path: Path = DEFAULT_STATE, escalations: Path = DEFAULT_ESCALATIONS,
        writer: str | None = None, now: float | None = None) -> tuple[int, dict]:
    if os.environ.get(KILL_SWITCH_ENV) == "1":
        return 0, {"disabled": True, "kill_switch": KILL_SWITCH_ENV}
    now = time.time() if now is None else now
    host = socket.gethostname().split(".")[0].lower() or "unknown"
    writer = writer or host
    try:
        contexts = required_contexts(gh, branch)
        shas = main_shas(gh, branch, depth)
    except (GhError, KeyError, TypeError) as exc:
        return 2, {"blind": True, "error": str(exc)[:300], "branch": branch}
    if not contexts or not shas:
        return 2, {"blind": True, "error": "no required contexts or no commits readable", "branch": branch}
    try:
        states = effective_state(contexts, shas, gh)
    except (GhError, KeyError, TypeError) as exc:
        return 2, {"blind": True, "error": f"check-runs unreadable: {str(exc)[:300]}", "branch": branch}
    reds = {c: dict(v) for c, v in states.items() if v["state"] == "red"}
    for ctx, info in reds.items():
        info.update(enrich(gh, info.get("url", "")))
        states[ctx] = info  # the report carries the enriched view too
    greens = {c for c, v in states.items() if v["state"] == "green"}
    report = {"branch": branch, "head": shas[0], "depth_scanned": len(shas),
              "required": contexts, "states": states, "red": sorted(reds),
              "board": {"escalated": [], "resolved": []}}
    if escalate:
        state = _load_state(Path(state_path).expanduser())
        report["board"] = reconcile(reds, greens, state=state, escalations=Path(escalations),
                                    writer=writer, host=host, now=now)
        _save_state(Path(state_path).expanduser(), state)
    return (1 if reds else 0), report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--branch", default="main")
    ap.add_argument("--depth", type=int, default=20, help="commits walked back from HEAD per context")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-escalate", action="store_true", help="sense only: no board line, no state write")
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--escalations", default=str(DEFAULT_ESCALATIONS))
    ap.add_argument("--writer", default=None, help="machine tag for the board line (default: hostname)")
    a = ap.parse_args(argv)
    rc, report = run(branch=a.branch, depth=a.depth, escalate=not a.no_escalate,
                     state_path=Path(a.state), escalations=Path(a.escalations), writer=a.writer)
    if a.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if report.get("disabled"):
            print(f"disabled ({KILL_SWITCH_ENV}=1)")
        elif report.get("blind"):
            print(f"BLIND: {report.get('error')}")
        else:
            for ctx, v in report["states"].items():
                print(f"{v['state']:8} {ctx}  @{(v.get('sha') or '')[:10]} depth={v.get('depth')}")
            print(f"board: +{len(report['board']['escalated'])} escalated, "
                  f"{len(report['board']['resolved'])} resolved")
    return rc


if __name__ == "__main__":
    sys.exit(main())
