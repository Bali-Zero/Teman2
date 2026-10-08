"""B6: the merger prunes what it wrote, and journals it (docs/specs/localci-sovereign-2026-10-07.md, phase B, step B6).

Deps images go by explicit tag when no plan of the last 48 h names them, they are not the newest image of their recipe and they
were built more than 48 h ago; `localci-candidate:*` and `localci-deps-base:*` are never in a removal set (2026-10-08 07:48Z: an
age prune removed the candidate image and blocked every contained context for a tick). Run directories keep everything for 7
days, then lose `logs/` and the Pysa call graphs, and after 30 days keep only their three verdict files. `decisions.jsonl` and
everything outside `<state>/runs` are never touched. One `{"kind": "prune"}` journal line says what went, by which rule, and the
free GB of the docker VM and of the host before and after.
"""
from __future__ import annotations

import calendar
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

DEPS_PREFIX = "localci-deps:"
NEVER = ("localci-candidate:", "localci-deps-base:")
REF_WINDOW_H = 48
FULL_DAYS, VERDICT_DAYS = 7, 30
RECIPE_LABEL = "org.nuzantara.localci.recipe"
TAG_RE = re.compile(r"localci-deps:[0-9a-f]{16}\b")
ID_RE = re.compile(r"sha256:[0-9a-f]{64}")
RUN_TS_RE = re.compile(r"-(\d{8}T\d{6}Z)$")
BULK = ("call-graph.json", "higher-order-call-graph.json")   # Pysa's, 77-125 MB each (2026-10-08); taint-output.json is the verdict
VERDICT = ("status.json", "hosted_compare.json", "state/plan.json")
HOST_PATH = "/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/"
CANDIDATE_IMAGE = "localci-candidate:1"


def _runner():
    spec = importlib.util.spec_from_file_location("localci_runner_for_prune", Path(__file__).resolve().parent / "runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def never(tag: str) -> bool:
    return not tag.startswith(DEPS_PREFIX) or tag.startswith(NEVER)


def _ts(text: str) -> float | None:
    try:
        return float(calendar.timegm(time.strptime(text[:19], "%Y-%m-%dT%H:%M:%S")))
    except (TypeError, ValueError):
        return None


def run_age_h(run: Path, now_s: float) -> float | None:
    """A run's age from the timestamp the merger put in its name (removing files changes a directory's mtime, never its name)."""
    m = RUN_TS_RE.search(run.name)
    t = calendar.timegm(time.strptime(m.group(1), "%Y%m%dT%H%M%SZ")) if m else None
    return None if t is None else (now_s - t) / 3600


def plan_refs(runs: Path, now_s: float) -> tuple[dict, set, dict]:
    """Tags and image ids named by a plan of the last 48 h (tag -> youngest age in hours), and each tag's recipe as the plans
    read it: the check whose job names it (`ctx.backend-tests` -> `backend-tests`)."""
    recent, ids, recipes = {}, set(), {}
    for plan in sorted(runs.glob("*/state/plan.json")) if runs.is_dir() else []:
        try:
            raw = plan.read_text(errors="replace")
            age_h = (now_s - plan.stat().st_mtime) / 3600
            doc = json.loads(raw)
        except (OSError, ValueError):
            continue
        for name, spec in (doc.get("checks") or {}).items() if isinstance(doc, dict) else []:
            for job in (spec.get("jobs") or []) if isinstance(spec, dict) else []:
                for tag in TAG_RE.findall(str((job or {}).get("deps") or "")):
                    recipes.setdefault(tag, set()).add(name[4:] if name.startswith("ctx.") else name)
        if age_h <= REF_WINDOW_H:
            for tag in TAG_RE.findall(raw):
                recent[tag] = min(recent.get(tag, age_h), age_h)
            ids |= set(ID_RE.findall(raw))
    return recent, ids, {t: sorted(r)[0] for t, r in recipes.items()}


def _docker(docker: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([docker, *args], capture_output=True, text=True, timeout=timeout)


def deps_images(docker: str) -> list[dict]:
    r = _docker(docker, "image", "ls", "--format", "{{.Repository}}:{{.Tag}}")
    if r.returncode != 0:
        raise RuntimeError(f"docker image ls rc={r.returncode}: {r.stderr.strip()[:200]}")
    out = []
    for tag in sorted({ln.strip() for ln in r.stdout.splitlines() if ln.strip().startswith(DEPS_PREFIX)}):
        i = _docker(docker, "image", "inspect", "--format", "{{.Id}}|{{.Created}}|{{.Size}}|{{json .Config.Labels}}", tag)
        if i.returncode != 0:
            continue
        iid, created, size, labels = (i.stdout.strip().split("|", 3) + ["", "", "", "null"])[:4]
        try:
            labels = json.loads(labels) or {}
        except ValueError:
            labels = {}
        out.append({"tag": tag, "id": iid, "created": _ts(created), "gb": round(int(size) / 1e9, 2) if size.isdigit() else None,
                    "label_recipe": labels.get(RECIPE_LABEL) if isinstance(labels, dict) else None})
    return out


def image_decisions(images: list[dict], recent: dict, ids: set, recipes: dict, now_s: float) -> list[dict]:
    """Every deps image with `remove` and the rule that decided it. Kept: named by a plan of the last 48 h (by tag or id), built
    in the last 48 h, the newest of its recipe, or in the never-list. A recipe nothing records is the image's own: it is kept."""
    for im in images:
        im["recipe"] = im.get("label_recipe") or recipes.get(im["tag"]) or f"unknown:{im['tag']}"
    newest = {}
    for im in images:
        if im["created"] is not None and (im["recipe"] not in newest or im["created"] > newest[im["recipe"]]["created"]):
            newest[im["recipe"]] = im
    out = []
    for im in images:
        age_h = None if im["created"] is None else round((now_s - im["created"]) / 3600, 1)
        if never(im["tag"]):
            why = "never-list (candidate and base images are never pruned)"
        elif im["tag"] in recent or im["id"] in ids:
            why = f"named by a plan of the last {REF_WINDOW_H} h" + (f" ({recent[im['tag']]:.1f} h ago)" if im["tag"] in recent else " (by id)")
        elif age_h is None or age_h < REF_WINDOW_H:
            why = f"built {age_h} h ago, under {REF_WINDOW_H} h"
        elif newest.get(im["recipe"]) is im:
            why = f"the newest image of recipe {im['recipe']}"
        else:
            out.append({**im, "remove": True, "rule": f"no plan of the last {REF_WINDOW_H} h names it, built {age_h} h ago, not the newest of "
                                                      f"recipe {im['recipe']} (newest {newest[im['recipe']]['tag']})"})
            continue
        out.append({**im, "remove": False, "rule": why})
    return out


def trim_runs(runs: Path, now_s: float, dry: bool) -> dict:
    """7 days full; then `logs/` and the Pysa call graphs go; after 30 days only VERDICT stays. Symlinks are removed as links."""
    out = {"trimmed_7d": [], "trimmed_30d": [], "freed_gb": 0.0}
    freed = 0
    for run in sorted(p for p in runs.iterdir() if p.is_dir() and not p.is_symlink()) if runs.is_dir() else []:
        age_h = run_age_h(run, now_s)
        if age_h is None or age_h < FULL_DAYS * 24:
            continue
        doomed = []
        for root, dirs, files in os.walk(run):
            rel_root = Path(root).relative_to(run)
            for f in files + [d for d in dirs if (Path(root) / d).is_symlink()]:
                rel = (rel_root / f).as_posix()
                if (age_h >= VERDICT_DAYS * 24 and rel not in VERDICT) or (age_h < VERDICT_DAYS * 24 and (rel == "logs" or rel.startswith("logs/") or f in BULK)):
                    doomed.append(Path(root) / f)
        if not doomed:
            continue
        for p in doomed:
            freed += p.lstat().st_size
            if not dry:
                p.unlink()
        if not dry:
            for root, dirs, _ in sorted(os.walk(run, topdown=False), key=lambda w: -len(w[0])):
                if root != str(run) and not os.listdir(root):
                    os.rmdir(root)
        out["trimmed_30d" if age_h >= VERDICT_DAYS * 24 else "trimmed_7d"].append(run.name)
    out["freed_gb"] = round(freed / 1e9, 2)
    return out


def host_free_gb(path: str) -> float:
    return round(shutil.disk_usage(path).free / 1e9, 1)


def vm_free_gb(docker: str, state: Path) -> float | None:
    gb, _ = _runner()._probe_free_gb(docker, CANDIDATE_IMAGE, state)   # B3's probe: df -Pk / in a throwaway candidate container
    return None if gb is None else round(gb, 1)


def prune(state: Path, docker: str, dry: bool = False, fstrim: bool = False, colima: str = "colima", host_path: str = HOST_PATH,
          now_s: float | None = None) -> dict:
    now_s = time.time() if now_s is None else now_s
    runs = state / "runs"
    rec = {"kind": "prune", "dry_run": dry, "vm_free_gb": {"before": vm_free_gb(docker, state)}, "host_free_gb": {"before": host_free_gb(host_path)}}
    recent, ids, recipes = plan_refs(runs, now_s)
    decided = image_decisions(deps_images(docker), recent, ids, recipes, now_s)
    removed, errors = [], []
    for im in (d for d in decided if d["remove"]):
        if never(im["tag"]):   # belt and braces: a removal set never carries the never-list
            continue
        r = None if dry else _docker(docker, "image", "rm", im["tag"])
        (removed if r is None or r.returncode == 0 else errors).append(
            {"tag": im["tag"], "gb": im["gb"], "rule": im["rule"], **({"error": r.stderr.strip()[:200]} if r is not None and r.returncode else {})})
    rec["images"] = {"removed" if not dry else "would_remove": removed, "kept": [{"tag": d["tag"], "rule": d["rule"]} for d in decided if not d["remove"]],
                     "errors": errors}
    if removed and not dry:
        b = _docker(docker, "builder", "prune", "-f", "--filter", "until=24h", timeout=600)
        rec["builder_prune"] = {"rc": b.returncode, "tail": (b.stdout or b.stderr).strip()[-120:]}
    rec["runs"] = trim_runs(runs, now_s, dry)
    rec["vm_free_gb"]["after"] = vm_free_gb(docker, state)
    rec["host_free_gb"]["after"] = host_free_gb(host_path)
    if fstrim and removed and not dry:   # the VM gives its freed blocks back to the host's sparse disk only on a trim
        try:
            t = subprocess.run([colima, "ssh", "--", "sudo", "fstrim", "-av"], capture_output=True, text=True, timeout=900)
            rec["fstrim"] = {"rc": t.returncode, "tail": (t.stdout or t.stderr).strip()[-160:]}
        except (OSError, subprocess.TimeoutExpired) as e:
            rec["fstrim"] = {"rc": None, "tail": type(e).__name__}
        rec["host_free_gb"]["after_fstrim"] = host_free_gb(host_path)
    return rec
