"""B6: the merger prunes what it wrote, and journals it (docs/specs/localci-sovereign-2026-10-07.md, phase B, step B6).

Deps images go by explicit tag when no plan of the last 48 h names them and they are not the newest image of their recipe —
whatever their age (the age guard of B6-1 was retired under the cap: per recipe at most MAX_IMAGES_PER_RECIPE images stay, the
newest and the one most plans of the last 48 h name; beyond the slots only the run in progress keeps an image — B8 retired the
clock grace — and under VM_MIN_FREE_GB of VM free space images go fewest plan references first, the newest of a recipe included);
`localci-candidate:*`, `localci-deps-base:*` and every service stand-in of the BASE matrix are never in a removal set
(2026-10-08 07:48Z: an age prune removed the candidate image and the stand-ins and blocked every contained context for a tick). Run directories keep everything for 7
days, then lose `logs/` and the Pysa call graphs, and after 30 days keep only their three verdict files. `decisions.jsonl` and
everything outside `<state>/runs` are never touched. One `{"kind": "prune"}` journal line says what went, by which rule, and the
free GB of the docker VM and of the host before and after.
"""
from __future__ import annotations

import calendar
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

DEPS_PREFIX = "localci-deps:"
NEVER = ("localci-candidate:", "localci-deps-base:")
REF_WINDOW_H = 48           # a plan this young names its images
MAX_IMAGES_PER_RECIPE = 2   # per recipe: the newest, and the one most plans of the last 48 h name
VM_MIN_FREE_GB = 15.0       # B8: under it after the cap, slot-2 images go oldest first (env LOCALCI_VM_MIN_FREE_GB)
BUILDER_CACHE_GB = 4        # B8: the build cache is kept to this budget (env LOCALCI_BUILDER_CACHE_GB), not by age
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
    named = {}   # tag or image id -> how many plans of the last 48 h name it (B8: slot 2 goes to the most named)
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
            for ref in set(TAG_RE.findall(raw)) | set(ID_RE.findall(raw)):
                named[ref] = named.get(ref, 0) + 1
            if not (plan.parent.parent / "status.json").exists():
                in_progress |= set(TAG_RE.findall(raw)) | set(ID_RE.findall(raw))
    return recent, ids, {t: sorted(r)[0] for t, r in recipes.items()}, unreadable, in_progress, named


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
                    stand_ins: frozenset = frozenset(), named: dict | None = None) -> list[dict]:
    """Every deps image with `remove`, `slot` and the rule that decided it. Per recipe, MAX_IMAGES_PER_RECIPE slots held by
    distinct images: the newest holds the first; the others go to the images most plans of the last 48 h name (ties: the
    youngest reference, then the newest image). Beyond the slots an image stays only when the run in progress names it (a run
    of the last 48 h with no status.json; the prune never runs beside the lease holder) — no clock grace (B8). An image no
    plan of the window names takes no slot and goes. The never-list is always kept. A recipe nothing records is its own."""
    named = named or {}
    for im in images:
        im["recipe"] = im.get("label_recipe") or recipes.get(im["tag"]) or f"unknown:{im['tag']}"
    newest, by_recipe = {}, {}
    for im in images:
        by_recipe.setdefault(im["recipe"], []).append(im)
        if im["created"] is not None and (im["recipe"] not in newest or im["created"] > newest[im["recipe"]]["created"]):
            newest[im["recipe"]] = im
    ref_of = lambda im: min([h for h in (recent.get(im["tag"]), ids.get(im["id"])) if h is not None], default=None)  # noqa: E731
    count_of = lambda im: max(named.get(im["tag"], 0), named.get(im["id"], 0))  # noqa: E731
    out = {}
    for r, ims in by_recipe.items():
        top, slots = newest.get(r), {}   # image id -> slot number
        used = {1} if top is not None else set()   # slot 1 is the newest's, even when the run in progress holds it
        rest = []
        for im in ims:
            if never(im["tag"], stand_ins):
                out[im["tag"]] = (False, never_rule(im["tag"], stand_ins), None)
            elif im["tag"] in in_progress or im["id"] in in_progress:
                out[im["tag"]] = (False, "named by the run in progress (no status.json yet)", None)
            elif top is None or im["created"] is None or im["created"] == top["created"]:
                slots[im["id"]] = 1   # an image built at the same instant, or undated, ranks with the newest
                out[im["tag"]] = (False, f"the newest image of recipe {r}", 1)
            else:
                rest.append(im)
        named_rest = sorted((im for im in rest if ref_of(im) is not None),
                            key=lambda im: (-count_of(im), ref_of(im), -(im["created"] or 0), im["tag"]))
        for im in named_rest:
            if im["id"] not in slots and len(used) < MAX_IMAGES_PER_RECIPE:
                used.add(len(used) + 1)
                slots[im["id"]] = len(used)
            if im["id"] in slots:
                out[im["tag"]] = (False, f"slot {slots[im['id']]} of {MAX_IMAGES_PER_RECIPE} of recipe {r}: named by {count_of(im)} plan(s) "
                                         f"of the last 48 h, the youngest {ref_of(im):.1f} h ago", slots[im["id"]])
            else:
                out[im["tag"]] = (True, f"recipe {r} already keeps {MAX_IMAGES_PER_RECIPE} images (newest {top['tag']}): beyond the cap, "
                                        f"named by {count_of(im)} plan(s), the youngest {ref_of(im):.1f} h ago", None)
        for im in rest:
            if ref_of(im) is None and im["id"] in slots:
                out[im["tag"]] = (False, f"another tag of an image recipe {r} keeps", slots[im["id"]])
            elif ref_of(im) is None:
                out[im["tag"]] = (True, f"not the newest of recipe {r} (newest {top['tag']}) and no plan of the last 48 h names it", None)
    return [{**im, "remove": out[im["tag"]][0], "rule": out[im["tag"]][1], "slot": out[im["tag"]][2], "refs": count_of(im),
             "live": im["tag"] in in_progress or im["id"] in in_progress} for im in images]


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


def _env_gb(name: str, default: float) -> float:
    """A GB budget from the environment; a value that is not a finite number >= 0 reads as the default, which the line journals."""
    try:
        v = float(os.environ.get(name, default))
    except ValueError:
        return default
    return v if math.isfinite(v) and v >= 0 else default


SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(B|kB|KB|MB|GB|TB)\s*$")
SIZE_UNITS = {"B": 1, "kB": 1e3, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}   # docker's human sizes are decimal


def build_cache_gb(docker: str) -> float | None:
    """The build cache's size as `docker system df` reports it; None when it cannot be read (a measurement, never a stop)."""
    try:
        r = _docker(docker, "system", "df", "--format", "{{.Type}}|{{.Size}}", timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (r.stdout or "").splitlines() if r.returncode == 0 else []:
        kind, _, size = line.partition("|")
        m = SIZE_RE.match(size) if kind.strip() == "Build Cache" else None
        if m:
            return round(float(m.group(1)) * SIZE_UNITS[m.group(2)] / 1e9, 2)
    return None


def builder_prune(docker: str, rec: dict, budget_gb: float) -> None:
    """`docker builder prune -af --keep-storage`: `-a` because the entries are the layers of images that exist, which are not
    dangling — without it nothing went (Pro, 2026-10-08T17:26Z: 0 B of a 21.8 GB cache). Run after image removals, so the entries
    tied to them go. rc and tail are the last call's, `runs` the count; the cache size is journalled before the first and after the last."""
    bp = rec.setdefault("builder_prune", {"rc": 0, "keep_storage_gb": budget_gb, "cache_gb": {"before": build_cache_gb(docker)}, "runs": 0})
    try:
        b = _docker(docker, "builder", "prune", "-af", "--keep-storage", f"{budget_gb:g}GB", timeout=600)
        rc, tail = b.returncode, (b.stdout or b.stderr).strip()[-120:]
    except (OSError, subprocess.SubprocessError) as e:
        rc, tail = None, type(e).__name__
    bp["runs"] += 1
    bp["tail"] = tail
    bp["rc"] = rc   # the last call's, as ruled; `runs` says how many there were


def prune(state: Path, docker: str, dry: bool = False, fstrim: bool = False, colima: str = "colima", host_path: str = HOST_PATH,
          now_s: float | None = None, matrix: Path = MATRIX) -> dict:
    now_s = time.time() if now_s is None else now_s
    runs = state / "runs"
    rec = {"kind": "prune", "dry_run": dry, "vm_free_gb": {"before": vm_free_gb(docker, state)}, "host_free_gb": {"before": host_free_gb(host_path)}}
    recent, ids, recipes, unreadable, in_progress, named = plan_refs(runs, now_s)
    errors = [{"plan": u, "error": "unreadable: no image is removed while a plan cannot be read"} for u in unreadable]
    try:
        keep = stand_ins(matrix)
    except Exception as exc:   # noqa: BLE001 — a never-list that cannot be read is incomplete: nothing is removed
        keep = frozenset()
        errors.append({"matrix": str(matrix), "error": f"unreadable ({type(exc).__name__}): no image is removed without the stand-in list"})
    tags = all_tags(docker)
    decided = image_decisions(deps_images(docker, tags), recent, ids, recipes, now_s, in_progress, keep, named)
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
    cache_budget = _env_gb("LOCALCI_BUILDER_CACHE_GB", BUILDER_CACHE_GB)   # a budget, not an age (B8: until=24h kept 16.9 GB)
    if not dry:   # the build cache grows with every deps build, whether or not an image went
        builder_prune(docker, rec, cache_budget)
    rec["runs"] = trim_runs(runs, now_s, dry)
    rec["vm_free_gb"]["after"] = vm_free_gb(docker, state)
    floor = _env_gb("LOCALCI_VM_MIN_FREE_GB", VM_MIN_FREE_GB)   # B8: the VM's free space outranks the slots
    rec["vm_floor"] = {"floor_gb": floor, "removed": 0}
    if dry or errors:
        rec["vm_floor"]["skipped"] = "dry run" if dry else "an input is unreadable"
    elif rec["vm_free_gb"]["after"] is None:
        rec["vm_floor"]["skipped"] = "the VM's free space is unmeasured"
    else:   # under the floor the newest of a recipe is not protected: only the never-list and what the lease run names are
        # (a 60 GiB VM holds one image per recipe plus a build's scratch when three recipes are live: Pro, 2026-10-08T17:26Z)
        for im in sorted((d for d in decided if not d["remove"] and not d["live"] and not never(d["tag"], keep)),
                         key=lambda d: (d["refs"], d["created"] is None, d["created"] or 0, d["tag"])):
            if rec["vm_free_gb"]["after"] >= floor:
                break
            before = rec["vm_free_gb"]["after"]
            r = _docker(docker, "image", "rm", im["tag"])
            if r.returncode != 0:
                errors.append({"tag": im["tag"], "gb": im["gb"], "rule": "vm floor", "error": r.stderr.strip()[:200]})
                continue
            im["remove"] = True
            built = f"built {(now_s - im['created']) / 3600:.1f} h ago" if im["created"] is not None else "undated"
            removed.append({"tag": im["tag"], "gb": im["gb"],
                            "rule": f"vm floor: VM free {before:g} GB < {floor:g} GB after the cap; {im['refs']} plan(s) of the last 48 h "
                                    f"name it, {built}"})
            rec["vm_floor"]["removed"] += 1
            builder_prune(docker, rec, cache_budget)   # the cache entries tied to the image go with it, or the VM gains nothing
            rec["vm_free_gb"]["after"] = vm_free_gb(docker, state)
            if rec["vm_free_gb"]["after"] is None:
                break
        rec["vm_floor"]["met"] = rec["vm_free_gb"]["after"] is not None and rec["vm_free_gb"]["after"] >= floor
    if "builder_prune" in rec:
        rec["builder_prune"]["cache_gb"]["after"] = build_cache_gb(docker)
    rec["images"] = {"removed" if not dry else "would_remove": removed, "errors": errors,
                     "kept": [{"tag": d["tag"], "rule": d["rule"]} for d in decided if not d["remove"]] + never_kept}
    rec["host_free_gb"]["after"] = host_free_gb(host_path)
    if fstrim and not dry:   # every real prune ends with a trim: a run's own containers and layers free blocks every tick, which
        # stay allocated in the host's sparse disk until trimmed (B7, measured 2026-10-08T15:16Z: 11.4 GiB back with no removal)
        try:
            t = subprocess.run([colima, "ssh", "--", "sudo", "fstrim", "-av"], capture_output=True, text=True, timeout=900)
            rec["fstrim"] = {"rc": t.returncode, "tail": (t.stdout or t.stderr).strip()[-160:]}
        except (OSError, subprocess.TimeoutExpired) as e:
            rec["fstrim"] = {"rc": None, "tail": type(e).__name__}
        rec["host_free_gb"]["after_fstrim"] = host_free_gb(host_path)
    rec["failed"] = [k for k in ("builder_prune", "fstrim") if k in rec and rec[k]["rc"] != 0] + (["images"] if errors else [])
    return rec
