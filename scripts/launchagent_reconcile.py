#!/usr/bin/env python3
"""launchagent_reconcile.py — inventory/reconcile report for ~/Library/LaunchAgents.

C3 of the WR2 next-level plan (research/operations/2026-06-30-wr2-next-level-plan.md,
D6): the LaunchAgents dir accreted 300+ entries (live plists + .bak/.disabled/archive
dirs) across months of cutovers. This tool RECONCILES three sources of truth —

    files on disk  ×  launchctl loaded state  ×  repo canon (infra/launchagents)

— and emits a categorized report. It is a SIGNALER, not an actuator (W81 antidote:
"reconciliation-report che allarma, non auto-attuatore"; W33: the operator decides
what gets disabled).

Categories (multi-tag — one file can appear in several):
  junk                file that is not a live `*.plist` (`.bak-*`, `.disabled-*`,
                      `.pre-*`, stray files). Parsed anyway: a backup still carries
                      a Label and may be the ONLY on-disk copy of a loaded job.
  zombie-loaded       label loaded in launchd with NO live plist file declaring it.
  present-not-loaded  live plist on disk whose label is not loaded (Esiste≠Armato).
  broken-target       live plist whose launch target does not exist on disk.
  repo-divergent      live plist that differs from its repo twin beyond the
                      env-specific keys (EnvironmentVariables, *Path, WorkingDirectory).
  home-fork-target    live plist whose payload lives under $HOME outside the repo /
                      deploy clone and is not a symlink into them (superscar #1).

What this tool does NOT do:
  - runtime health (exit codes × log content) → scripts/launchd_liveness_detector.py (W84)
  - bootout/unload/disable — NEVER (W33 kill-switch: operator-only)

--apply deletes ONLY `junk` files, and only when ALL of:
  - age >= --min-age-days (age = the YOUNGER of mtime and any filename-embedded
    YYYYMMDD stamp — a lying mtime must make the file look newer, not older)
  - the file is NOT the loaded source of its label (launchctl print path check)
  - a live `*.plist` with the SAME parsed Label exists (supersession proof) OR the
    file does not parse as a plist at all. A backup that is the only copy of its
    label is PROTECTED (only-copy) and left to the operator.

Keying is by parsed Label, never by filename (real drift observed:
com.matagaruda.kita-feed.daily.plist carries Label=com.matagaruda.kita-feed).

Scope: labels/files matching --prefixes (default: the organism's families).
Apple/Google/Homebrew agents are out of scope unless --all.

Usage:
    python3 scripts/launchagent_reconcile.py                # report only (default)
    python3 scripts/launchagent_reconcile.py --json         # machine-readable
    python3 scripts/launchagent_reconcile.py --apply        # delete eligible junk
    python3 scripts/launchagent_reconcile.py --alert        # Telegram summary

Stdlib-only, runs on macOS system python3 (3.9+).
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import plistlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_PREFIXES = (
    "com.balizero.",
    "com.nuzantara.",
    "com.matagaruda.",
    "ai.flowkit.",
    "ai.openclaw.",
    "com.osint-nexus.",
)

# Keys that legitimately differ per machine — excluded from the repo-divergence
# compare (red-team 2026-07-02 finding #7: raw byte-compare cries wolf on HOME,
# log paths, TCC cutovers).
ENV_SPECIFIC_KEYS = (
    "EnvironmentVariables",
    "StandardOutPath",
    "StandardErrorPath",
    "WorkingDirectory",
)

# Interpreters whose argv[1] is the real payload (best-effort, report-only).
INTERPRETERS = ("bash", "zsh", "sh", "python", "python3", "env", "node")

# Roots that plausibly host launchd wrapper/canon scripts, walked RECURSIVELY
# (basename match). A flat top-level-only search (pre-2026-07-07) missed real
# canons living one level deeper — infra/healer/, infra/mini-scripts/,
# scripts/mini-migration/, apps/backend-rag/scripts/ — and mis-flagged 7 of 15
# live findings as "no repo canon" while a byte-identical twin existed nearby.
# apps/*/scripts (not all of apps/) mirrors the top-level scripts/ convention
# without walking the ~36k-file app source trees.
CANON_EXCLUDE_DIRNAMES = {
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build", ".next", ".git", ".worktrees",
}


def _build_canon_index(repo_dir: Path) -> dict:
    """basename -> sorted candidate repo paths, built once per run (not once
    per target — the walk cost is paid a single time)."""
    index: dict = {}
    roots = [repo_dir / "scripts", repo_dir / "infra"]
    if (repo_dir / "apps").is_dir():
        roots.extend(sorted((repo_dir / "apps").glob("*/scripts")))
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in CANON_EXCLUDE_DIRNAMES]
            for fn in filenames:
                index.setdefault(fn, []).append(Path(dirpath) / fn)
    for paths in index.values():
        paths.sort(key=str)
    return index

# Path fragments that mark a RUNTIME (venv interpreter, pyenv shim…), not a
# payload: a `~/venvs/x/bin/python` under $HOME is infrastructure, not a
# HOME-fork of repo code — the fork signal lives in the script it runs.
RUNTIME_MARKERS = ("/venv/", "/.venv/", "/venvs/", "/.pyenv/", "/node_modules/")


def _is_runtime(path: Path) -> bool:
    s = str(path)
    if any(m in s for m in RUNTIME_MARKERS):
        return True
    return path.parent.name == "bin" and any(
        path.name.startswith(i) for i in (*INTERPRETERS, "uvicorn", "gunicorn")
    )

_NAME_STAMP_RE = re.compile(r"(20\d{6})")


# ─────────────────────────────────────────────────────────────────────────
# launchctl adapters (injectable for tests)
# ─────────────────────────────────────────────────────────────────────────

def launchctl_list_text() -> str:
    """Raw `launchctl list` output; empty string on any failure."""
    try:
        return subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=20
        ).stdout
    except Exception:  # noqa: BLE001 — degrade to "loaded state unknown"
        return ""


def parse_loaded_labels(text: str) -> set:
    """Labels from `launchctl list` (PID\tStatus\tLabel; header skipped)."""
    labels = set()
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[2] == "Label":
            continue
        labels.add(parts[2].strip())
    return labels


def launchctl_loaded_path(label: str) -> Optional[str]:
    """The `path = ...` launchd reports for a loaded label (deletion protection:
    never delete the file launchd is actually running from). None if unknown."""
    try:
        out = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r"^\s*path = (.+)$", out, re.MULTILINE)
    return m.group(1).strip() if m else None


# ─────────────────────────────────────────────────────────────────────────
# plist helpers
# ─────────────────────────────────────────────────────────────────────────

def parse_plist(path: Path) -> Optional[dict]:
    """plistlib first; on failure fall back to `plutil -convert xml1`.

    launchd is more lenient than expat: real plists in this fleet carry
    `--apply` inside XML comments (`--` is illegal in XML comments), which
    plistlib rejects while launchd loads them fine (observed 2026-07-02 on 5
    live agents that would otherwise misclassify as zombies). plutil parses
    like launchd and re-emits canonical XML without comments.
    """
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 — try the lenient parser before giving up
        pass
    try:
        out = subprocess.run(
            ["plutil", "-convert", "xml1", "-o", "-", str(path)],
            capture_output=True, timeout=20,
        )
        if out.returncode != 0:
            return None
        data = plistlib.loads(out.stdout)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 — genuinely unparseable
        return None


def resolve_targets(plist: dict) -> list:
    """Candidate payload paths launchd would touch: Program, argv[0], and — when
    argv[0] is an interpreter — the first absolute-path argument after it.
    Best-effort by design (report-only; the liveness detector owns health)."""
    targets = []
    prog = plist.get("Program")
    if isinstance(prog, str):
        targets.append(prog)
    args = plist.get("ProgramArguments")
    if isinstance(args, list) and args:
        argv0 = str(args[0])
        targets.append(argv0)
        base = Path(argv0).name
        if any(base.startswith(i) for i in INTERPRETERS):
            for a in args[1:]:
                s = str(a)
                if s.startswith("/"):
                    targets.append(s)
                    break
    # dedupe, preserve order
    seen = set()
    out = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def canonical_for_compare(plist: dict) -> dict:
    return {k: v for k, v in plist.items() if k not in ENV_SPECIFIC_KEYS}


def name_stamp_age_days(name: str, now: datetime) -> Optional[float]:
    """Age from a YYYYMMDD embedded in the filename, if any."""
    m = _NAME_STAMP_RE.search(name)
    if not m:
        return None
    try:
        stamped = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0.0, (now - stamped).total_seconds() / 86400.0)


def effective_age_days(path: Path, now: datetime) -> float:
    """The YOUNGER of mtime-age and filename-stamp-age: a lying mtime (chmod,
    xattr, copy) must make a file look NEWER — never older — for --apply."""
    mtime_age = max(
        0.0,
        (now - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).total_seconds() / 86400.0,
    )
    stamp_age = name_stamp_age_days(path.name, now)
    return min(mtime_age, stamp_age) if stamp_age is not None else mtime_age


def in_scope(name: str, prefixes) -> bool:
    return any(name.startswith(p) for p in prefixes)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


# ─────────────────────────────────────────────────────────────────────────
# The reconcile pass
# ─────────────────────────────────────────────────────────────────────────

def reconcile(
    agents_dir: Path,
    repo_dir: Path,
    loaded_labels: Optional[set],
    prefixes=DEFAULT_PREFIXES,
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Pure inventory pass. loaded_labels=None means launchctl was unavailable —
    loaded-state categories are skipped (degrade-open, never mass-misclassify)."""
    home = home or Path.home()
    now = now or datetime.now(timezone.utc)
    repo_infra = repo_dir / "infra" / "launchagents"
    repo_root = repo_dir.resolve()
    deploy_root = (home / "Desktop" / "nuzantara-deploy").resolve()

    # Canon index for wrapper scripts (basename match, built once). A HOME
    # target whose repo canon is byte-identical is NOT a fork — it is the
    # W84-safe placement (launchd payloads deliberately live OUTSIDE ~/Desktop
    # because launchd can lose its TCC grant there). The disease is DRIFT,
    # not location.
    canon_index = _build_canon_index(repo_dir)

    def _repo_canon_for(target: Path) -> Optional[Path]:
        candidates = canon_index.get(target.name)
        if not candidates:
            return None
        for cand in candidates:
            if filecmp.cmp(str(cand), str(target), shallow=False):
                return cand
        return candidates[0]

    live: dict = {}      # label -> {file, plist}
    junk: list = []
    archive_dirs: list = []
    unparseable_live: list = []

    for entry in sorted(agents_dir.iterdir()):
        if entry.is_dir():
            archive_dirs.append(entry.name)
            continue
        if not entry.is_file():
            continue
        if entry.name.endswith(".plist"):
            data = parse_plist(entry)
            if data is None:
                unparseable_live.append(entry.name)
                continue
            label = str(data.get("Label", entry.stem))
            if not (in_scope(label, prefixes) or in_scope(entry.name, prefixes)):
                continue
            live[label] = {"file": entry, "plist": data}
        else:
            data = parse_plist(entry)
            label = str(data.get("Label")) if data and data.get("Label") else None
            if not (in_scope(entry.name, prefixes) or (label and in_scope(label, prefixes))):
                continue
            junk.append({
                "file": entry,
                "label": label,
                "age_days": round(effective_age_days(entry, now), 1),
            })

    live_labels = set(live.keys())

    zombie_loaded = []
    present_not_loaded = []
    if loaded_labels is not None:
        scoped_loaded = {l for l in loaded_labels if in_scope(l, prefixes)}
        zombie_loaded = sorted(scoped_loaded - live_labels)
        present_not_loaded = sorted(live_labels - loaded_labels)

    broken_target = []
    home_fork_target = []
    canon_paired = []
    repo_divergent = []
    repo_symlinked = []

    for label, info in sorted(live.items()):
        f: Path = info["file"]
        plist: dict = info["plist"]
        targets = resolve_targets(plist)

        if targets and not Path(targets[0]).exists():
            broken_target.append({"label": label, "file": f.name, "target": targets[0]})

        for t in targets:
            tp = Path(t)
            if not tp.exists():
                continue
            rp = tp.resolve()
            if _is_runtime(rp):
                continue  # venv/pyenv interpreter = runtime, not a fork
            if not _is_under(rp, home):
                continue
            if _is_under(rp, repo_root) or _is_under(rp, deploy_root):
                continue
            if _is_under(rp, agents_dir.resolve()):
                continue
            canon = _repo_canon_for(rp)
            if canon is not None and filecmp.cmp(str(canon), str(rp), shallow=False):
                canon_paired.append({"label": label, "file": f.name, "target": t,
                                     "canon": str(canon.relative_to(repo_root))})
            else:
                detail = (
                    f"DIVERGED from canon {canon.relative_to(repo_root)}" if canon is not None
                    else "no repo canon (basename not found under scripts/, infra/, or apps/*/scripts/)"
                )
                home_fork_target.append({"label": label, "file": f.name, "target": t,
                                         "detail": detail})
            break

        twin = repo_infra / f.name
        if twin.is_file():
            if f.is_symlink() and _is_under(f.resolve(), repo_root):
                repo_symlinked.append(f.name)
            else:
                repo_plist = parse_plist(twin)
                if repo_plist is not None and canonical_for_compare(plist) != canonical_for_compare(repo_plist):
                    repo_divergent.append({"label": label, "file": f.name})

    return {
        "scanned_at": now.isoformat(),
        "agents_dir": str(agents_dir),
        "launchctl_available": loaded_labels is not None,
        "live_count": len(live),
        "live_labels": sorted(live_labels),
        "junk": [
            {"file": j["file"].name, "label": j["label"], "age_days": j["age_days"]}
            for j in junk
        ],
        "_junk_paths": {j["file"].name: j["file"] for j in junk},
        "_live_by_label": {l: str(i["file"]) for l, i in live.items()},
        "archive_dirs": archive_dirs,
        "unparseable_live": unparseable_live,
        "zombie_loaded": zombie_loaded,
        "present_not_loaded": present_not_loaded,
        "broken_target": broken_target,
        "home_fork_target": home_fork_target,
        "canon_paired": canon_paired,
        "repo_divergent": repo_divergent,
        "repo_symlinked": repo_symlinked,
    }


def junk_apply_eligibility(
    report: dict,
    min_age_days: float,
    loaded_labels: Optional[set],
    loaded_path_fn=launchctl_loaded_path,
) -> list:
    """Per-junk-file verdict: (name, eligible, reason). ALL protections must
    clear for eligible=True — see module docstring."""
    verdicts = []
    live_by_label = report["_live_by_label"]
    junk_paths = report["_junk_paths"]
    for j in report["junk"]:
        name, label, age = j["file"], j["label"], j["age_days"]
        path = junk_paths[name]
        if age < min_age_days:
            verdicts.append((name, False, f"younger than {min_age_days:.0f}d (age {age}d)"))
            continue
        if label is not None:
            if label not in live_by_label:
                verdicts.append((name, False, "only-copy of its label (no live plist) — operator decides"))
                continue
            if loaded_labels is not None and label in loaded_labels:
                lp = loaded_path_fn(label)
                if lp and Path(lp).resolve() == path.resolve():
                    verdicts.append((name, False, "IS the loaded source of its label"))
                    continue
        verdicts.append((name, True, "superseded backup" if label else "not a plist"))
    return verdicts


# ─────────────────────────────────────────────────────────────────────────
# Rendering + alert
# ─────────────────────────────────────────────────────────────────────────

def render_markdown(report: dict, verdicts) -> str:
    lines = [
        "# LaunchAgent reconcile report",
        "",
        f"- scanned: {report['scanned_at']}",
        f"- agents dir: `{report['agents_dir']}`",
        f"- launchctl loaded-state: {'available' if report['launchctl_available'] else 'UNAVAILABLE — loaded categories skipped'}",
        f"- live plists in scope: {report['live_count']}",
        f"- junk files in scope: {len(report['junk'])}",
        f"- archive dirs (never touched): {', '.join(report['archive_dirs']) or '—'}",
        "",
        "> REPORT-ONLY by default. `--apply` deletes junk that cleared every",
        "> protection below. It NEVER unloads/bootouts anything (W33) — zombie and",
        "> divergence findings are for the operator.",
        "> Runtime health (exit-code × log) lives in scripts/launchd_liveness_detector.py (W84).",
        "",
    ]

    def section(title, rows, fmt):
        lines.append(f"## {title} ({len(rows)})")
        if rows:
            lines.extend(fmt(r) for r in rows)
        else:
            lines.append("- none")
        lines.append("")

    section("Zombie loaded (label alive, no live plist file)", report["zombie_loaded"], lambda l: f"- `{l}`")
    section(
        "Present but not loaded (Esiste≠Armato)", report["present_not_loaded"], lambda l: f"- `{l}`"
    )
    section(
        "Broken target", report["broken_target"],
        lambda b: f"- `{b['label']}` → missing `{b['target']}`",
    )
    section(
        "HOME-fork target (superscar #1)", report["home_fork_target"],
        lambda h: f"- `{h['label']}` → `{h['target']}` ({h.get('detail', 'under $HOME, outside repo/deploy, not a repo symlink')})",
    )
    section(
        "Canon-paired HOME target (byte-identical to repo canon — W84-safe placement, not a fork)",
        report.get("canon_paired", []),
        lambda h: f"- `{h['label']}` → `{h['target']}` == `{h['canon']}`",
    )
    section(
        "Repo-divergent (env-specific keys excluded)", report["repo_divergent"],
        lambda d: f"- `{d['file']}`",
    )
    if report["unparseable_live"]:
        section("Unparseable live plists", report["unparseable_live"], lambda n: f"- `{n}`")

    lines.append(f"## Junk files ({len(report['junk'])})")
    if verdicts:
        for name, eligible, reason in verdicts:
            mark = "DELETE-ELIGIBLE" if eligible else "PROTECTED"
            lines.append(f"- [{mark}] `{name}` — {reason}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=10
        )
    except Exception:  # noqa: BLE001 — alerting is best-effort
        pass


# ─────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--agents-dir", default=str(Path.home() / "Library" / "LaunchAgents"))
    ap.add_argument("--repo-dir", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--prefixes", default=",".join(DEFAULT_PREFIXES),
                    help="comma-separated label/filename prefixes in scope")
    ap.add_argument("--all", action="store_true", help="no prefix filter (whole dir)")
    ap.add_argument("--min-age-days", type=float, default=30.0)
    ap.add_argument("--apply", action="store_true",
                    help="delete eligible junk files (report mode otherwise)")
    ap.add_argument("--json", action="store_true", help="print JSON to stdout")
    ap.add_argument("--alert", action="store_true", help="send Telegram summary")
    ap.add_argument("--out", default=None, help="markdown report path")
    args = ap.parse_args(argv)

    prefixes = ("",) if args.all else tuple(p for p in args.prefixes.split(",") if p)
    agents_dir = Path(args.agents_dir).expanduser()
    if not agents_dir.is_dir():
        print(f"agents dir not found: {agents_dir}", file=sys.stderr)
        return 2

    text = launchctl_list_text()
    loaded = parse_loaded_labels(text) if text.strip() else None

    report = reconcile(agents_dir, Path(args.repo_dir), loaded, prefixes=prefixes)
    verdicts = junk_apply_eligibility(report, args.min_age_days, loaded)

    md = render_markdown(report, verdicts)
    out = Path(args.out) if args.out else (
        Path.home() / "logs" / f"launchagent-reconcile-{datetime.now(timezone.utc):%Y%m%d}.md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)

    if args.json:
        clean = {k: v for k, v in report.items() if not k.startswith("_")}
        clean["junk_verdicts"] = [
            {"file": n, "eligible": e, "reason": r} for n, e, r in verdicts
        ]
        print(json.dumps(clean, indent=2, default=str))
    else:
        print(md)
    print(f"[launchagent-reconcile] report → {out}", file=sys.stderr)

    deleted = []
    if args.apply:
        junk_paths = report["_junk_paths"]
        for name, eligible, _reason in verdicts:
            if not eligible:
                continue
            try:
                junk_paths[name].unlink()
                deleted.append(name)
                print(f"[apply] deleted {name}", file=sys.stderr)
            except OSError as e:
                print(f"[apply] FAILED to delete {name}: {e}", file=sys.stderr)
        print(f"[apply] deleted {len(deleted)} junk file(s)", file=sys.stderr)

    if args.alert:
        n_eligible = sum(1 for _n, e, _r in verdicts if e)
        send_telegram(
            "LaunchAgent reconcile: "
            f"{report['live_count']} live, {len(report['junk'])} junk "
            f"({n_eligible} delete-eligible), "
            f"{len(report['zombie_loaded'])} zombie, "
            f"{len(report['present_not_loaded'])} not-loaded, "
            f"{len(report['broken_target'])} broken-target, "
            f"{len(report['home_fork_target'])} home-fork, "
            f"{len(report.get('canon_paired', []))} canon-paired, "
            f"{len(report['repo_divergent'])} repo-divergent. "
            f"Report: {out}"
            + (f" — APPLIED: deleted {len(deleted)}" if args.apply else "")
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
