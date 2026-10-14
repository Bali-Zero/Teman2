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
import fcntl
import gzip
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
VM_MIN_FREE_GB = 15.0       # B8: under it after the cap every deps image but the never-list and the lease run's goes, fewest 48 h
                            # plan references first, ties oldest, the newest included (env LOCALCI_VM_MIN_FREE_GB)
BUILDER_CACHE_GB = 4        # B8: the build cache is kept to this budget (env LOCALCI_BUILDER_CACHE_GB), not by age
FULL_DAYS, VERDICT_DAYS = 7, 30
RECIPE_LABEL = "org.nuzantara.localci.recipe"
TAG_RE = re.compile(r"localci-deps:[0-9a-f]{16}\b")
ID_RE = re.compile(r"sha256:[0-9a-f]{64}")
RUN_TS_RE = re.compile(r"-(\d{8}T\d{6}Z)$")
BULK = ("call-graph.json", "higher-order-call-graph.json")   # Pysa's, 77-114 MB each (Pro, 2026-10-08); taint-output.json is the verdict
TREE_PACK = ("tree.pack", "tree.pack.part", "tree.pack.json")   # B14's ~845 MB pack: the run's `finally` removes it, a SIGKILL or reboot does not
TREE_PACK_STALE_H = 24   # a live run can last hours; a pack older than a day belongs to a run that is gone
BULK_KEEP_H = TREE_PACK_STALE_H   # B26 U1': the same criterion for the Pysa call graphs, finished run or not (no status.json is asked)
COMPRESS = ("taint-output.json", "dependency-graph.json")   # B26 U5: kept, gzipped in place after TREE_PACK_STALE_H
VERDICT = ("status.json", "hosted_compare.json", "state/plan.json")
HOST_PATH = "/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/"
CANDIDATE_IMAGE = "localci-candidate:1"
VM_DOCKER_MOUNT = "/mnt/lima-colima"   # B8b: the Colima VM's data disk (/dev/vdb1), bind-mounted on /var/lib/docker; online discard is kept on it
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
    """Every value of every `service_images` map in the matrix (BASE image -> local stand-in) and the image of every `extra_services`
    entry (the matrix's own stand-ins, digest-pinned), read, never hardcoded."""
    import yaml   # the merger's venv carries PyYAML, as the runner's matrix reader needs it

    found, todo = set(), [yaml.safe_load(matrix.read_text())]
    while todo:
        node = todo.pop()
        if isinstance(node, dict):
            if isinstance(node.get("service_images"), dict):
                found.update(str(v) for v in node["service_images"].values())
            if isinstance(node.get("extra_services"), list):
                found.update(str(e["image"]) for e in node["extra_services"] if isinstance(e, dict) and e.get("image"))
            todo.extend(node.values())
        elif isinstance(node, list):
            todo.extend(node)
    return frozenset(found)


TS_RE = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?(?:Z|([+-])(\d\d):?(\d\d))?")


def _ts(text: str) -> float | None:
    """docker's Created as a UTC instant. RFC 3339 with nanoseconds (two builds in one second are still ordered) and a trailing
    `Z` or `±HH:MM` / `±HHMM` offset: Pro's docker prints local time with `+08:00`, and dropping it made every image 8 h younger
    than it is (B8a, measured 2026-10-09T02:49:24Z: "built -5.3 h ago"). No offset reads as UTC; anything else is None."""
    m = TS_RE.fullmatch((text or "").strip())
    if not m or (m.group(3) and (int(m.group(4)) > 23 or int(m.group(5)) > 59)):
        return None
    off_s = (1 if m.group(3) == "+" else -1) * (int(m.group(4)) * 3600 + int(m.group(5)) * 60) if m.group(3) else 0
    try:
        return calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) + float(m.group(2) or 0) - off_s
    except ValueError:
        return None


def run_age_h(run: Path, now_s: float) -> float | None:
    """A run's age from the timestamp the merger put in its name (removing files changes a directory's mtime, never its name)."""
    m = RUN_TS_RE.search(run.name)
    t = calendar.timegm(time.strptime(m.group(1), "%Y%m%dT%H%M%SZ")) if m else None
    return None if t is None else (now_s - t) / 3600


def run_alive(run: Path) -> bool:
    """B16: a run with no status.json is live only while its coordinator holds `state/coordinator.lock` — runner.py's flock,
    held for the whole `run` and dropped by the kernel when the process dies. An evicted, killed or crashed run leaves no
    status.json and a free lock: read as live, it kept its images for 48 h (Pro, 2026-10-12: four B15 evictions held two second-slot
    deps images, about 6.35 GB, through host pressure, so every next run started short and was evicted too). No lock
    file means no coordinator ever ran. A lock that cannot be opened or probed counts as held: unknown keeps the image."""
    lock = run / "state" / "coordinator.lock"
    try:
        fh = open(lock, "rb")
    except FileNotFoundError:
        return False
    except OSError:
        return True
    with fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError:   # BlockingIOError: the coordinator holds it; anything else is unknown, so held too
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False


def plan_deps(doc):
    """(recipe, tag) for every deps image a parsed plan's jobs name: the check `ctx.backend-tests` is the recipe `backend-tests`."""
    for name, spec in (doc.get("checks") or {}).items() if isinstance(doc, dict) else []:
        for job in (spec.get("jobs") or []) if isinstance(spec, dict) else []:
            for tag in TAG_RE.findall(str((job or {}).get("deps") or "")):
                yield (name[4:] if name.startswith("ctx.") else name), tag


MATRIX_REL = "scripts/localci/contexts_matrix.yaml"


def main_keeper(state: Path, docker: str) -> dict:
    """B22 K1 v3: per recipe, main's deps tag RECOMPUTED: runner.py's pure `deps_recipe` on the mirror at refs/merger/base, with the
    current candidate image id, for every context of the BASE matrix that has a `deps` block. The tree is read as data (git show),
    nothing of it runs. Any error is unknown (`tags` None, `reason`) or, for one recipe, a None tag with its reason: today's rule."""
    def unknown(why: str) -> dict:
        return {"tags": None, "evidence": None, "reason": why}
    try:
        import yaml
        runner, repo = _runner(), str(state / "repo.git")
        git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=30)  # noqa: E731
        base = git("rev-parse", "--verify", "--quiet", "refs/merger/base^{commit}")
        if base.returncode != 0:
            return unknown("the mirror has no refs/merger/base")
        base = base.stdout.strip()
        shown = git("show", f"{base}:{MATRIX_REL}")
        if shown.returncode != 0:
            return unknown("the BASE matrix is unreadable in the mirror")
        insp = _docker(docker, "image", "inspect", "--format", "{{.Id}}\n{{range .Config.Env}}{{println .}}{{end}}", CANDIDATE_IMAGE)
        lines = insp.stdout.strip().splitlines()
        if insp.returncode != 0 or not lines or not lines[0].startswith("sha256:"):
            return unknown(f"the candidate image {CANDIDATE_IMAGE} is not inspectable")
        iso = runner.isolation_of_inspect(CANDIDATE_IMAGE, lines, docker)
        tags, evidence, todo = {}, {}, [yaml.safe_load(shown.stdout)]
        while todo:
            node = todo.pop()
            if isinstance(node, dict):
                loc = node.get("local")
                if isinstance(loc, dict) and isinstance(loc.get("check"), str) and loc.get("deps"):
                    recipe = loc["check"][4:] if loc["check"].startswith("ctx.") else loc["check"]
                    try:
                        job = yaml.safe_load(runner._extract_base_file(Path(repo), base, str(node.get("workflow_file"))) or b"")["jobs"][node.get("job_id")]
                        prefix, why = runner.select_python(job, iso.get("python_version"), iso.get("pythons") or {})
                        info, why = (None, why) if prefix is None else runner.deps_recipe(Path(repo), base, iso, loc["deps"], prefix)
                        tags[recipe] = f"{DEPS_PREFIX}{info['digest'][:16]}" if info else None
                        evidence[recipe] = {"recomputed_at": base, "digest": info["digest"]} if info else {"reason": why}
                    except Exception as exc:  # noqa: BLE001 — one recipe that cannot be recomputed is unknown, the others stand
                        tags[recipe], evidence[recipe] = None, {"reason": f"{type(exc).__name__}: {str(exc)[:120]}"}
                todo.extend(node.values())
            elif isinstance(node, list):
                todo.extend(node)
        return {"tags": tags, "evidence": evidence, "reason": None} if tags else unknown("the BASE matrix has no deps block")
    except Exception as exc:  # noqa: BLE001 — the keeper never takes the prune down: unknown means today's rule
        return unknown(f"keeper failed ({type(exc).__name__}: {str(exc)[:120]})")


def plan_refs(runs: Path, now_s: float) -> tuple[dict, dict, dict, list, set]:
    """Tags and image ids named by a plan of the last 48 h (tag -> youngest age in hours), each tag's recipe as the plans
    read it (the check whose job names it: `ctx.backend-tests` -> `backend-tests`), and the plans that could not be read —
    any of which may name an image, so none is removed while one exists — and what the run in progress names (a run of the
    last 48 h with no status.json yet whose coordinator still holds its lock, B16). A half-written plan still names what its text names."""
    recent, ids, recipes, unreadable, in_progress = {}, {}, {}, [], set()
    named = {}   # tag or image id -> the plans of the last 48 h that name it (B8: an image's count is the union, tag or id)
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
        for recipe, tag in plan_deps(doc):
            recipes.setdefault(tag, set()).add(recipe)
        if age_h <= REF_WINDOW_H:
            for tag in TAG_RE.findall(raw):
                recent[tag] = min(recent.get(tag, age_h), age_h)
            for iid in ID_RE.findall(raw):
                ids[iid] = min(ids.get(iid, age_h), age_h)
            for ref in set(TAG_RE.findall(raw)) | set(ID_RE.findall(raw)):
                named.setdefault(ref, set()).add(str(plan))
            if not (plan.parent.parent / "status.json").exists() and run_alive(plan.parent.parent):
                in_progress |= set(TAG_RE.findall(raw)) | set(ID_RE.findall(raw))
    return recent, ids, {t: sorted(r)[0] for t, r in recipes.items()}, unreadable, in_progress, named


def _docker(docker: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([docker, *args], capture_output=True, text=True, timeout=timeout)


def shed_order(d: dict) -> tuple:   # the order the VM floor and the host pressure both shed in: fewest plan references first, undated before dated, oldest first
    return (d["refs"], d["created"] is None, d["created"] or 0, d["tag"])


def rm_image(docker: str, tag: str) -> subprocess.CompletedProcess:   # never -f: an image a container still uses is refused, not torn out
    return _docker(docker, "image", "rm", tag)


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
                    stand_ins: frozenset = frozenset(), named: dict | None = None, main: frozenset = frozenset()) -> list[dict]:
    """Every deps image with `remove`, `slot` and the rule that decided it. Per recipe, MAX_IMAGES_PER_RECIPE slots held by
    distinct images: the newest holds the first; the others go to the images most plans of the last 48 h name (ties: the
    youngest reference, then the newest image). Beyond the slots an image stays only when the run in progress names it (a run
    of the last 48 h with no status.json whose coordinator holds its lock; the prune never runs beside the lease holder) — no clock grace (B8). An image no
    plan of the window names takes no slot and goes. B22: main's tags (`main`) hold slot 1 in place of the newest and are never beyond the cap. The never-list is always kept. A recipe nothing records is its own."""
    named = named or {}
    for im in images:
        im["recipe"] = im.get("label_recipe") or recipes.get(im["tag"]) or f"unknown:{im['tag']}"
    newest, by_recipe = {}, {}
    for im in images:
        by_recipe.setdefault(im["recipe"], []).append(im)
        if im["created"] is not None and (im["recipe"] not in newest or im["created"] > newest[im["recipe"]]["created"]):
            newest[im["recipe"]] = im
    ref_of = lambda im: min([h for h in (recent.get(im["tag"]), ids.get(im["id"])) if h is not None], default=None)  # noqa: E731
    count_of = lambda im: len(set(named.get(im["tag"], ())) | set(named.get(im["id"], ())))  # noqa: E731  distinct plans, tag OR id
    out = {}
    for r, ims in by_recipe.items():
        top, slots = newest.get(r), {}   # image id -> slot number
        mains = [im for im in ims if im["tag"] in main and not never(im["tag"], stand_ins)]
        if mains:
            top = max(mains, key=lambda im: im["created"] or 0)   # B22: main's image is the keeper, whatever the clock says
        used = {1} if top is not None else set()   # slot 1 is the newest's, even when the run in progress holds it
        rest = []
        for im in ims:
            if never(im["tag"], stand_ins):
                out[im["tag"]] = (False, never_rule(im["tag"], stand_ins), None)
            elif im["tag"] in in_progress or im["id"] in in_progress:
                out[im["tag"]] = (False, "named by the run in progress (no status.json yet, its coordinator holds the lock)", None)
            elif top is None or im["created"] is None or im["created"] == top["created"] or im["tag"] in main:
                slots[im["id"]] = 1   # an image built at the same instant, or undated, ranks with the newest
                out[im["tag"]] = (False, f"main's image of recipe {r} (named by the newest judged commit on main)" if im["tag"] in main
                                  else f"the newest image of recipe {r}", 1)
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


class _Count:
    """A write-only sink that counts: a dry run measures the gzip without writing it."""

    def __init__(self):
        self.n = 0

    def write(self, b):
        self.n += len(b)
        return len(b)

    def flush(self):
        pass


def compress_receipts(run: Path, skip: set, dry: bool) -> tuple[int, bool]:
    """B26 U5: gzip COMPRESS under `receipts/pysa/*/results/` in place, atomically (`.gz.part`, fsync, rename, then the original goes).
    Returns (bytes freed, whether a receipt was compressed). A `.gz.part` is never valid: it is removed. A file with its `.gz` beside it
    only loses its original; no symlink is followed (a linked directory is not entered, a linked file is not read); `skip` is what the
    trim already doomed. An OSError on one file leaves that file whole."""
    freed, hit = 0, False
    base = run / "receipts" / "pysa"
    if run.is_symlink() or (run / "receipts").is_symlink() or base.is_symlink() or not base.is_dir():
        return 0, False
    for side in sorted(base.iterdir()):
        res = side / "results"
        if side.is_symlink() or res.is_symlink() or not res.is_dir():
            continue
        for stale in sorted(res.glob("*.gz.part")):
            freed += stale.lstat().st_size
            if not dry:
                stale.unlink()
        for name in COMPRESS:
            src, gz, part = res / name, res / f"{name}.gz", res / f"{name}.gz.part"
            if src in skip or src.is_symlink() or not src.is_file() or gz.is_symlink():
                continue
            try:
                before = src.lstat().st_size
                if gz.is_file():   # a rename that landed and an unlink that did not: the .gz is whole by construction
                    after = 0
                elif dry:
                    sink = _Count()
                    with open(src, "rb") as fi, gzip.GzipFile(filename=name, fileobj=sink, mode="wb", mtime=0, compresslevel=3) as g:
                        shutil.copyfileobj(fi, g, 1 << 20)
                    after = sink.n
                else:
                    with open(src, "rb") as fi, open(part, "wb") as fo:
                        with gzip.GzipFile(filename=name, fileobj=fo, mode="wb", mtime=0, compresslevel=3) as g:
                            shutil.copyfileobj(fi, g, 1 << 20)
                        fo.flush()
                        os.fsync(fo.fileno())
                    os.replace(part, gz)
                    after = gz.lstat().st_size
                if not dry:
                    src.unlink()
                freed += before - after
                hit = True
            except OSError:
                continue
    return freed, hit


def trim_runs(runs: Path, now_s: float, dry: bool) -> dict:
    """7 days full; then `logs/` and the Pysa call graphs go; after 30 days only VERDICT stays. A run older than TREE_PACK_STALE_H
    loses a tree pack its `finally` never removed, whatever its age. B26: from BULK_KEEP_H on a run loses the Pysa call graphs
    (`trimmed_bulk`) and has COMPRESS gzipped in place (`compressed`); the verdict and the rest keep their retention. Symlinks are
    removed as links."""
    out = {"trimmed_7d": [], "trimmed_30d": [], "trimmed_pack": [], "trimmed_bulk": [], "compressed": [], "freed_gb": 0.0}
    if runs.is_symlink():   # the prune never leaves the merger's state dir: a linked runs/ is someone else's tree
        return {**out, "refused": f"{runs} is a symlink"}
    freed = 0
    for run in sorted(p for p in runs.iterdir() if p.is_dir() and not p.is_symlink()) if runs.is_dir() else []:
        age_h = run_age_h(run, now_s)
        if age_h is None or age_h < TREE_PACK_STALE_H:
            continue
        full = age_h < FULL_DAYS * 24
        bulk_now = age_h >= BULK_KEEP_H
        doomed, pack_hit, bulk_hit = [], False, False
        for root, dirs, files in os.walk(run):
            rel_root = Path(root).relative_to(run)
            for f in files + [d for d in dirs if (Path(root) / d).is_symlink()]:
                rel = (rel_root / f).as_posix()
                pack = rel_root.as_posix() == "state" and f in TREE_PACK
                bulk = full and bulk_now and f in BULK
                pack_hit, bulk_hit = pack_hit or pack, bulk_hit or bulk
                if pack or bulk or (not full and ((age_h >= VERDICT_DAYS * 24 and rel not in VERDICT) or (age_h < VERDICT_DAYS * 24 and (rel == "logs" or rel.startswith("logs/") or f in BULK)))):
                    doomed.append(Path(root) / f)
        if doomed:
            for p in doomed:
                freed += p.lstat().st_size
                if not dry:
                    p.unlink()
            if not dry and not full:   # a young run keeps its layout: only the pack goes
                for root, dirs, _ in sorted(os.walk(run, topdown=False), key=lambda w: -len(w[0])):
                    if root != str(run) and not os.listdir(root):
                        os.rmdir(root)
            if full:
                if pack_hit:
                    out["trimmed_pack"].append(run.name)
                if bulk_hit:
                    out["trimmed_bulk"].append(run.name)
            else:
                out["trimmed_30d" if age_h >= VERDICT_DAYS * 24 else "trimmed_7d"].append(run.name)
        saved, hit = compress_receipts(run, set(doomed), dry)
        freed += saved
        if hit:
            out["compressed"].append(run.name)
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


MAX_USED_RE = re.compile(r"--max-used-space\b")
KEEP_STORAGE_RE = re.compile(r"--keep-storage\b")
TOTAL_RE = re.compile(r"^Total:\s*([0-9]+(?:\.[0-9]+)?)\s*(B|kB|KB|MB|GB|TB)\s*$", re.M)
DEPRECATED_RE = re.compile(r"deprecated|has been changed to", re.I)
DU_LINE_RE = re.compile(r"^(Shared|Private|Reclaimable|Total):\s*([0-9]+(?:\.[0-9]+)?)\s*(B|kB|KB|MB|GB|TB)\s*$", re.M)


def builder_prune_flag(docker: str) -> str:
    """The flag that means "keep at most this much cache", read from the installed buildx's own help. buildx >= 0.34 deprecated
    `--keep-storage` into `--reserved-space` (a floor, not a cap), so it exits 0 having freed nothing; `--max-used-space` is the
    old meaning. Old buildx lists only `--keep-storage`; a help that cannot be read says nothing, and rc then decides."""
    try:
        h = _docker(docker, "builder", "prune", "--help", timeout=30)
        text = f"{h.stdout or ''}\n{h.stderr or ''}" if h.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        text = ""
    return "keep-storage" if KEEP_STORAGE_RE.search(text) and not MAX_USED_RE.search(text) else "max-used-space"


def prune_total_gb(output: str) -> float | None:
    """buildx's own `Total:` line (`Total:\t3.867GB`, `Total:\t0B`) in GB; None when the output has none."""
    m = TOTAL_RE.search(output or "")
    return round(float(m.group(1)) * SIZE_UNITS[m.group(2)] / 1e9, 3) if m else None


def flag_deprecated(output: str, flag: str) -> bool:
    """Whether a line of the call's output NAMES the flag we passed and says it is deprecated or changed (buildx 0.34: `Flag
    --keep-storage has been deprecated, keep-storage flag has been changed to reserved-space`). Another flag's warning, or the
    word `deprecated` on a line that does not name ours, is not this."""
    named = re.compile(rf"--{re.escape(flag)}(?![\w-])")
    return any(named.search(ln) and DEPRECATED_RE.search(ln) for ln in (output or "").splitlines())


def buildx_du_gb(docker: str) -> dict | None:
    """The summary of `docker buildx du` in GB: {shared, private, reclaimable, total}. buildx prints no `Shared:` (and no
    `Private:`) when nothing is shared, and then everything is private. A measurement: unreadable or unparsed is None."""
    try:
        r = _docker(docker, "buildx", "du", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    return du_summary_gb(r.stdout or "") if r.returncode == 0 else None


def du_summary_gb(output: str) -> dict | None:
    got = {k: round(float(n) * SIZE_UNITS[u] / 1e9, 3) for k, n, u in DU_LINE_RE.findall(output or "")}
    if "Total" not in got or "Reclaimable" not in got:
        return None
    shared = got.get("Shared", 0.0)
    return {"shared": shared, "private": got.get("Private", round(got["Total"] - shared, 3)), "reclaimable": got["Reclaimable"], "total": got["Total"]}


def builder_prune(docker: str, rec: dict, budget_gb: float) -> None:
    """`docker builder prune -af --max-used-space`: `-a` because the entries are the layers of images that exist, which are not
    dangling — without it nothing went (Pro, 2026-10-08T17:26Z: 0 B of a 21.8 GB cache). Run after image removals, so the entries
    tied to them go. The flag is chosen once per prune run (B13). rc and tail are the last call's, `runs` the count, `freed_gb` the sum
    of buildx's `Total:` over the calls; `deprecated_flag` is true when any call said the flag we passed is deprecated or changed;
    the cache size is journalled before the first and after the last."""
    if "builder_prune" not in rec:
        rec["builder_prune"] = {"rc": 0, "keep_storage_gb": budget_gb, "flag": builder_prune_flag(docker),
                                "freed_gb": None, "deprecated_flag": False, "cache_gb": {"before": build_cache_gb(docker)}, "runs": 0}
    bp = rec["builder_prune"]
    try:
        b = _docker(docker, "builder", "prune", "-af", f"--{bp['flag']}", f"{budget_gb:g}GB", timeout=600)
        out = f"{b.stdout}\n{b.stderr}"
        rc, tail, freed = b.returncode, (b.stdout or b.stderr).strip()[-120:], prune_total_gb(out)
        bp["deprecated_flag"] = bp["deprecated_flag"] or flag_deprecated(out, bp["flag"])
    except (OSError, subprocess.SubprocessError) as e:
        rc, tail, freed = None, type(e).__name__, None
    bp["runs"] += 1
    bp["tail"] = tail
    if freed is not None:
        bp["freed_gb"] = round((bp["freed_gb"] or 0.0) + freed, 3)
    bp["rc"] = rc   # the last call's, as ruled; `runs` says how many there were


def _vm_discard_on(colima: str) -> tuple[bool | None, str | None]:
    """Whether the VM's data disk is mounted with `discard`: (True|False, None), or (None, why) when it cannot be read. The mount
    point is matched as the second FIELD of a /proc/mounts line and `discard` as one of the comma-split options, never as text."""
    try:
        t = subprocess.run([colima, "ssh", "--", "cat", "/proc/mounts"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, type(e).__name__
    if t.returncode != 0:
        return None, f"rc {t.returncode}"
    found = None
    for line in t.stdout.splitlines():
        f = line.split()
        if len(f) >= 4 and f[1] == VM_DOCKER_MOUNT:
            found = "discard" in f[3].split(",")   # the LAST line for a mount point is the one in force (a stacked mount)
    return (found, None) if found is not None else (None, "mount point not found")


def keep_vm_discard(colima: str) -> dict:
    """B8b: the VM's data disk keeps online discard, so a finished leg's blocks return to the host as they are freed, not at the tick's
    end. Mount options do not survive a VM restart; this puts the option back. Never raises: a measurement problem stops nothing."""
    if os.environ.get("LOCALCI_VM_DISCARD") == "0":
        return {"skipped": "LOCALCI_VM_DISCARD=0"}
    out = {"before": None, "after": None, "remounted": False, "rc": None, "error": None}
    out["before"], out["error"] = _vm_discard_on(colima)
    out["after"] = out["before"]
    if out["before"] is not False:
        return out
    out["remounted"] = True
    try:
        r = subprocess.run([colima, "ssh", "--", "sudo", "mount", "-o", "remount,discard", VM_DOCKER_MOUNT], capture_output=True, text=True, timeout=60)
        out["rc"] = r.returncode
        if r.returncode != 0:
            out["error"] = (r.stderr or r.stdout).strip()[-160:] or f"rc {r.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:
        out["error"] = type(e).__name__
    out["after"], why = _vm_discard_on(colima)
    out["error"] = out["error"] or why
    return out


def prune(state: Path, docker: str, dry: bool = False, fstrim: bool = False, colima: str = "colima", host_path: str = HOST_PATH,
          now_s: float | None = None, matrix: Path = MATRIX, pressure_gb: float | None = None) -> dict:
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
    mk = main_keeper(state, docker)   # B22: read-only; unknown means today's rule (the newest is slot 1)
    rec["main_tags"], rec["main_evidence"] = mk["tags"], mk["evidence"]
    if mk["tags"] is None:
        rec["main_reason"] = mk["reason"]
    main = frozenset(t for t in (mk["tags"] or {}).values() if t)
    decided = image_decisions(deps_images(docker, tags), recent, ids, recipes, now_s, in_progress, keep, named, main)
    blind = bool(errors)   # an unreadable plan or matrix; a refused removal below is an error too, but it blinds nothing
    for d in decided if blind else []:
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
    if dry or blind:
        rec["vm_floor"]["skipped"] = "dry run" if dry else "an input is unreadable"
    elif rec["vm_free_gb"]["after"] is None:
        rec["vm_floor"]["skipped"] = "the VM's free space is unmeasured"
    else:   # under the floor the newest of a recipe is not protected: only the never-list and what the lease run names are
        # (a 60 GiB VM holds one image per recipe plus a build's scratch when three recipes are live: Pro, 2026-10-08T17:26Z)
        for im in sorted((d for d in decided if not d["remove"] and not d["live"] and not never(d["tag"], keep)),
                         key=shed_order):
            if rec["vm_free_gb"]["after"] >= floor:
                break
            before = rec["vm_free_gb"]["after"]
            r = rm_image(docker, im["tag"])
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
    # B15: the host under the pressure threshold (start floor + run headroom) is pressure too: every deps image beyond the newest of its recipe
    # goes, fewest 48 h plan references first (the VM order), never the never-list and never the run in progress's; the trim follows
    free_before = rec["host_free_gb"]["before"]
    rec["pressure_gb"] = pressure_gb
    rec["host_pressure"] = pressure_gb is not None and free_before < pressure_gb
    if rec["host_pressure"] and not (dry or blind):
        dropped = False
        for im in sorted((d for d in decided if not d["remove"] and not d["live"] and d["slot"] != 1 and not never(d["tag"], keep)),
                         key=shed_order):
            r = rm_image(docker, im["tag"])
            if r.returncode != 0:
                errors.append({"tag": im["tag"], "gb": im["gb"], "rule": "host pressure", "error": r.stderr.strip()[:200]})
                continue
            im["remove"] = True
            removed.append({"tag": im["tag"], "gb": im["gb"], "rule": f"host pressure: host free {free_before:g} GB < {pressure_gb:g} GB; "
                                                                      f"slot {im['slot']} of its recipe, {im['refs']} plan(s) of the last 48 h name it; "
                                                                      f"dropping a second-slot image means a cold rebuild of that recipe"})
            dropped = True
        if dropped:
            builder_prune(docker, rec, cache_budget)   # after the removals, as the VM-floor branch: the cache entries tied to the images go with them
    if "builder_prune" in rec:
        rec["builder_prune"]["cache_gb"]["after"] = build_cache_gb(docker)
        rec["builder_prune"]["du_gb"] = buildx_du_gb(docker)   # a measurement, never a verdict: BuildKit's cap accounting is opaque
    rec["images"] = {"removed" if not dry else "would_remove": removed, "errors": errors,
                     "kept": [{"tag": d["tag"], "rule": d["rule"]} for d in decided if not d["remove"]] + never_kept}
    rec["host_free_gb"]["after"] = host_free_gb(host_path)
    if fstrim and not dry:   # every real prune ends with a trim: a run's own containers and layers free blocks every tick, which
        # stay allocated in the host's sparse disk until trimmed (B7, measured 2026-10-08T15:16Z: 11.4 GiB back with no removal)
        rec["vm_discard"] = keep_vm_discard(colima)   # before the trim: the trim then finds only what discard has not returned
        try:
            t = subprocess.run([colima, "ssh", "--", "sudo", "fstrim", "-av"], capture_output=True, text=True, timeout=900)
            rec["fstrim"] = {"rc": t.returncode, "tail": (t.stdout or t.stderr).strip()[-160:]}
        except (OSError, subprocess.TimeoutExpired) as e:
            rec["fstrim"] = {"rc": None, "tail": type(e).__name__}
        rec["host_free_gb"]["after_fstrim"] = host_free_gb(host_path)
    rec["failed"] = [k for k in ("builder_prune", "fstrim") if k in rec and (rec[k]["rc"] != 0 or rec[k].get("deprecated_flag"))] + (["images"] if errors else [])
    if rec.get("vm_discard", {}).get("remounted") and rec["vm_discard"]["after"] is not True:
        rec["failed"].append("vm_discard")
    return rec
