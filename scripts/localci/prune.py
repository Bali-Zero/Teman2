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
REF_WINDOW_H = 48           # a plan this young names its images
MAX_IMAGES_PER_RECIPE = 2   # per recipe: the newest, and the next one only while a plan of the last 48 h names it
IN_FLIGHT_GRACE_H = 6       # beyond the cap, an image a plan named this recently is a tick in flight: kept
FULL_DAYS, VERDICT_DAYS = 7, 30
RECIPE_LABEL = "org.nuzantara.localci.recipe"
TAG_RE = re.compile(r"localci-deps:[0-9a-f]{16}\b")
ID_RE = re.compile(r"sha256:[0-9a-f]{64}")
RUN_TS_RE = re.compile(r"-(\d{8}T\d{6}Z)$")
BULK = ("call-graph.json", "higher-order-call-graph.json")   # Pysa's, 77-114 MB each (Pro, 2026-10-08); taint-output.json is the verdict
VERDICT = ("status.json", "hosted_compare.json", "state/plan.json")
HOST_PATH = "/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/"
CANDIDATE_IMAGE = "localci-candidate:1"
MATRIX = Path(__file__).resolve().parent / "contexts_matrix.yaml"   # the BASE matrix the wrapper extracted beside this file


def _runner():
    spec = importlib.util.spec_from_file_location("localci_runner_for_prune", Path(__file__).resolve().parent / "runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def protected(tag: str, stand_ins: frozenset = frozenset()) -> bool:
    """The never-list: the candidate and base images and every service stand-in the BASE matrix names (2026-10-08 07:48Z: an
    age prune removed localci-candidate:1, postgres:15 and redis:7 and blocked every contained context for a tick)."""
    return tag.startswith(NEVER) or tag in stand_ins


def never(tag: str, stand_ins: frozenset = frozenset()) -> bool:
    return not tag.startswith(DEPS_PREFIX) or protected(tag, stand_ins)


def never_rule(tag: str, stand_ins: frozenset = frozenset()) -> str:
    if tag in stand_ins:
        return "service stand-in of the BASE matrix: never pruned"
    if tag.startswith(NEVER):
        return "never-list (the candidate or a base image): never pruned"
    return "not a localci-deps image: never pruned"


def stand_ins(matrix: Path) -> frozenset:
    """Every value of every `service_images` map in the matrix (BASE image -> local stand-in), read, never hardcoded."""
    import yaml   # the merger's venv carries PyYAML, as the runner's matrix reader needs it

    found, todo = set(), [yaml.safe_load(matrix.read_text())]
    while todo:
        node = todo.pop()
        if isinstance(node, dict):
            if isinstance(node.get("service_images"), dict):
                found.update(str(v) for v in node["service_images"].values())
            todo.extend(node.values())
        elif isinstance(node, list):
            todo.extend(node)
    return frozenset(found)


def _ts(text: str) -> float | None:
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?", text or "")
    try:   # docker's Created carries nanoseconds: two builds in one second are still ordered
        return calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) + float(m.group(2) or 0) if m else None
    except ValueError:
        return None


def run_age_h(run: Path, now_s: float) -> float | None:
    """A run's age from the timestamp the merger put in its name (removing files changes a directory's mtime, never its name)."""
    m = RUN_TS_RE.search(run.name)
    t = calendar.timegm(time.strptime(m.group(1), "%Y%m%dT%H%M%SZ")) if m else None
    return None if t is None else (now_s - t) / 3600


def plan_refs(runs: Path, now_s: float) -> tuple[dict, dict, dict, list, set]:
    """Tags and image ids named by a plan of the last 48 h (tag -> youngest age in hours), each tag's recipe as the plans
    read it (the check whose job names it: `ctx.backend-tests` -> `backend-tests`), and the plans that could not be read —
    any of which may name an image, so none is removed while one exists — and what the run in progress names (a run of the
    last 48 h with no status.json yet). A half-written plan still names what its text names."""
    recent, ids, recipes, unreadable, in_progress = {}, {}, {}, [], set()
    for plan in sorted(runs.glob("*/state/plan.json")) if runs.is_dir() else []:
        try:
            raw = plan.read_text(errors="replace")
            age_h = (now_s - plan.stat().st_mtime) / 3600
        except OSError as exc:
            unreadable.append(f"{plan.parent.parent.name}: {type(exc).__name__}")
            continue
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = None
        for name, spec in (doc.get("checks") or {}).items() if isinstance(doc, dict) else []:
            for job in (spec.get("jobs") or []) if isinstance(spec, dict) else []:
                for tag in TAG_RE.findall(str((job or {}).get("deps") or "")):
                    recipes.setdefault(tag, set()).add(name[4:] if name.startswith("ctx.") else name)
        if age_h <= REF_WINDOW_H:
            for tag in TAG_RE.findall(raw):
                recent[tag] = min(recent.get(tag, age_h), age_h)
            for iid in ID_RE.findall(raw):
                ids[iid] = min(ids.get(iid, age_h), age_h)
            if not (plan.parent.parent / "status.json").exists():
                in_progress |= set(TAG_RE.findall(raw)) | set(ID_RE.findall(raw))
    return recent, ids, {t: sorted(r)[0] for t, r in recipes.items()}, unreadable, in_progress


def _docker(docker: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([docker, *args], capture_output=True, text=True, timeout=timeout)


def all_tags(docker: str) -> list[str]:
    r = _docker(docker, "image", "ls", "--format", "{{.Repository}}:{{.Tag}}")
    if r.returncode != 0:
        raise RuntimeError(f"docker image ls rc={r.returncode}: {r.stderr.strip()[:200]}")
    return sorted({ln.strip() for ln in r.stdout.splitlines() if ln.strip()})


def deps_images(docker: str, tags: list[str] | None = None) -> list[dict]:
    out = []
    for tag in (t for t in (all_tags(docker) if tags is None else tags) if t.startswith(DEPS_PREFIX)):
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


def image_decisions(images: list[dict], recent: dict, ids: dict, recipes: dict, now_s: float, in_progress: set = frozenset(),
                    stand_ins: frozenset = frozenset()) -> list[dict]:
    """Every deps image with `remove` and the rule that decided it. Per recipe, newest first, MAX_IMAGES_PER_RECIPE slots held
    by distinct images: the newest holds one; an image a plan of the last 48 h names takes a free one; beyond them an image is
    kept only when a plan named it under IN_FLIGHT_GRACE_H ago (a tick in flight). An image no plan of the window names takes
    no slot and goes. The never-list and what the run in progress names are always kept. A recipe nothing records is the
    image's own."""
    for im in images:
        im["recipe"] = im.get("label_recipe") or recipes.get(im["tag"]) or f"unknown:{im['tag']}"
    newest, by_recipe = {}, {}
    for im in images:
        by_recipe.setdefault(im["recipe"], []).append(im)
        if im["created"] is not None and (im["recipe"] not in newest or im["created"] > newest[im["recipe"]]["created"]):
            newest[im["recipe"]] = im
    rules = {}
    for r, ims in by_recipe.items():
        slots = set()   # image ids holding a slot: a tag of an image that already holds one keeps it too
        for im in sorted(ims, key=lambda o: (o["created"] is None, -(o["created"] or 0), o["tag"])):
            ref = min([h for h in (recent.get(im["tag"]), ids.get(im["id"])) if h is not None], default=None)
            top = newest.get(r)
            if never(im["tag"], stand_ins):
                why = never_rule(im["tag"], stand_ins)
            elif im["tag"] in in_progress or im["id"] in in_progress:
                why = "named by the run in progress (no status.json yet)"
            elif top is None or im["created"] is None or im["created"] == top["created"]:
                why = f"the newest image of recipe {r}"   # an image built at the same instant, or undated, ranks with it
                slots.add(im["id"])
            elif im["id"] in slots:
                why = f"another tag of an image recipe {r} keeps"
            elif ref is not None and len(slots) < MAX_IMAGES_PER_RECIPE:
                slots.add(im["id"])
                why = f"slot {len(slots)} of {MAX_IMAGES_PER_RECIPE} of recipe {r}, named by a plan {ref:.1f} h ago"
            elif ref is not None and ref < IN_FLIGHT_GRACE_H:
                why = f"beyond the cap of {MAX_IMAGES_PER_RECIPE} of recipe {r}, named {ref:.1f} h ago: a tick in flight"
            elif ref is not None:
                rules[im["tag"]] = (True, f"recipe {r} already keeps {MAX_IMAGES_PER_RECIPE} images (newest {top['tag']}): beyond the cap, "
                                          f"its youngest plan is {ref:.1f} h old")
                continue
            else:
                rules[im["tag"]] = (True, f"not the newest of recipe {r} (newest {top['tag']}) and no plan of the last 48 h names it")
                continue
            rules[im["tag"]] = (False, why)
    return [{**im, "remove": rules[im["tag"]][0], "rule": rules[im["tag"]][1]} for im in images]


def trim_runs(runs: Path, now_s: float, dry: bool) -> dict:
    """7 days full; then `logs/` and the Pysa call graphs go; after 30 days only VERDICT stays. Symlinks are removed as links."""
    out = {"trimmed_7d": [], "trimmed_30d": [], "freed_gb": 0.0}
    if runs.is_symlink():   # the prune never leaves the merger's state dir: a linked runs/ is someone else's tree
        return {**out, "refused": f"{runs} is a symlink"}
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
    try:   # B3's probe: df -Pk / in a throwaway candidate container; a measurement, never a reason to stop the prune
        gb, _ = _runner()._probe_free_gb(docker, CANDIDATE_IMAGE, state)
    except Exception:   # noqa: BLE001 — a missing or older runner.py reads as unmeasured
        return None
    return None if gb is None else round(gb, 1)


def prune(state: Path, docker: str, dry: bool = False, fstrim: bool = False, colima: str = "colima", host_path: str = HOST_PATH,
          now_s: float | None = None, matrix: Path = MATRIX) -> dict:
    now_s = time.time() if now_s is None else now_s
    runs = state / "runs"
    rec = {"kind": "prune", "dry_run": dry, "vm_free_gb": {"before": vm_free_gb(docker, state)}, "host_free_gb": {"before": host_free_gb(host_path)}}
    recent, ids, recipes, unreadable, in_progress = plan_refs(runs, now_s)
    errors = [{"plan": u, "error": "unreadable: no image is removed while a plan cannot be read"} for u in unreadable]
    try:
        keep = stand_ins(matrix)
    except Exception as exc:   # noqa: BLE001 — a never-list that cannot be read is incomplete: nothing is removed
        keep = frozenset()
        errors.append({"matrix": str(matrix), "error": f"unreadable ({type(exc).__name__}): no image is removed without the stand-in list"})
    tags = all_tags(docker)
    decided = image_decisions(deps_images(docker, tags), recent, ids, recipes, now_s, in_progress, keep)
    for d in decided if errors else []:
        d.update(remove=False, rule=f"kept: {len(errors)} input(s) unreadable, see errors") if d["remove"] else None
    never_kept = [{"tag": t, "rule": never_rule(t, keep)} for t in tags if protected(t, keep)]
    removed = []
    for im in (d for d in decided if d["remove"]):
        if never(im["tag"], keep):   # belt and braces: a removal set never carries the never-list
            continue
        r = None if dry else _docker(docker, "image", "rm", im["tag"])
        (removed if r is None or r.returncode == 0 else errors).append(
            {"tag": im["tag"], "gb": im["gb"], "rule": im["rule"], **({"error": r.stderr.strip()[:200]} if r is not None and r.returncode else {})})
    rec["images"] = {"removed" if not dry else "would_remove": removed, "errors": errors,
                     "kept": [{"tag": d["tag"], "rule": d["rule"]} for d in decided if not d["remove"]] + never_kept}
    if not dry:   # the build cache grows with every deps build, whether or not an image went
        try:
            b = _docker(docker, "builder", "prune", "-f", "--filter", "until=24h", timeout=600)
            rec["builder_prune"] = {"rc": b.returncode, "tail": (b.stdout or b.stderr).strip()[-120:]}
        except (OSError, subprocess.SubprocessError) as e:
            rec["builder_prune"] = {"rc": None, "tail": type(e).__name__}
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
    rec["failed"] = [k for k in ("builder_prune", "fstrim") if k in rec and rec[k]["rc"] != 0] + (["images"] if errors else [])
    return rec
