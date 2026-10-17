#!/usr/bin/env python3
"""localci runner v0.2.0 — durable coordinator for a local CI / release gate.

Commands: plan | run | review | status.

Statuses: QUEUED RUNNING PASS FAIL ERROR BLOCKED STALE INTERRUPTED NOT_APPLICABLE.
Overall verdicts: PASS | SUBSET_PASS | FAIL | BLOCKED. Missing evidence is never PASS.

Every receipt is bound to candidate sha, tree sha, base sha, plan hash and an
environment hash (python/pytest/git/uv versions, platform, host, runner sha256,
a lock hash of the venv contents and the identity of every tool a check runs).
The coordinator is single-host: `state/coordinator.lock` is an flock, a mutual
exclusion between processes on ONE machine, not a distributed fence.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import fnmatch
import hashlib
import html
import io
import json
import os
import platform
import shlex
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

RUNNER_VERSION = "0.6.0"
STATUSES = ("QUEUED", "RUNNING", "PASS", "FAIL", "ERROR", "BLOCKED", "STALE", "INTERRUPTED", "NOT_APPLICABLE")
BLOCKING = {"ERROR", "BLOCKED", "STALE", "RUNNING", "QUEUED", "INTERRUPTED"}
EXECUTABLE = ("pytest", "trusted_pytest", "cmd", "trusted_steps", "contained_steps", "contained_jobs")
# kinds in which CANDIDATE code executes (trusted_pytest: BASE test, candidate implementation; contained_steps: a required context's steps)
CANDIDATE_KINDS = ("pytest", "trusted_pytest", "contained_steps", "contained_jobs")
ISOLATIONS = ("container", "none")
DEFAULT_ISOLATION_IMAGE = "localci-candidate:1"   # scripts/localci/candidate.Dockerfile
SANDBOX_UID = 65534
JUNIT_MAX_BYTES = 32 << 20
COPY_TIMEOUT_S = 600
MAPPINGS = ("executed", "not_applicable_rule", "blocked", "not_implemented")
COVERAGES = ("full", "partial")   # what an executed context's verdict covers of its hosted twin; travels with every result
# The docker host ran out of disk (B3): the ERROR LINES the tools print when a write hits ENOSPC, matched line by line on their
# own shapes, never on a substring anywhere — a test named test_enospc_*, a fixture raising OSError("no space left on device") or an
# assertion quoting the phrase keeps its verdict. Such a line in a sandbox's output makes the context ERROR host_disk_full.
DISK_FULL_LINE = re.compile(
    r"ENOSPC: no space left on device"                         # libuv / node / npm (npm's TAR_ENTRY_ERROR lines)
    r"|^npm (?:ERR!|error) code ENOSPC\s*$"
    r"|\[Errno 28\] No space left on device"                   # CPython's OSError from a real write (pip, open, shutil)
    r"|\bDiskFull(?:Error)?(?:'>)?: \S"                         # asyncpg DiskFullError / psycopg DiskFull raised with its message
    r"|\bcould not (?:extend|write to) file \"[^\"\n]+\": \S"   # the postgres server's own message (SQLSTATE 53100)
    r"|^(?!.*\b\w*(?:Error|Exception)\b).*: [Nn]o space left on device\s*$")   # a C tool's strerror (tar, cp, git); no Python exception text
RECOVERY_LINE = re.compile(r"\bthe database system is in recovery mode\b")   # a service Postgres after it crashed; counted only after a line above
# a check reason the runner wrote itself: the host, not the candidate — the context has no verdict, and it is not a FAIL
HOST_NO_VERDICT = re.compile(r"^(?:host_disk_full|host_disk_below_floor \d+(?:\.\d+)?GB<\d+(?:\.\d+)?GB|host_disk_unmeasured|host_disk_floor_invalid)(?=:)")
# Free-space floor (B3): no service leg starts on a docker host with less free disk than this (GB, 10^9 bytes). One backend shard's
# sandbox wrote 7-10 GB on Pro's 58.8 GB Colima VM, which also holds ~47 GB of images (measured 2026-10-08). 0 disables the floor.
MIN_FREE_ENV, DEFAULT_MIN_FREE_GB = "LOCALCI_MIN_FREE_GB", 12.0
_HOST_FREE: dict = {}   # run dir -> (free GB or None, why): the docker host's free space, read once per `run`
RESERVED_CHECK_PREFIXES = ("policy.", "tests.", "review.", "trusted.")  # planned by the runner itself, never by --extra-check
RUNNER_OWNED_KEYS = frozenset({"extra", "isolation", "trusted_pythonpath", "trusted_dir_sha256", "trusted_files", "deps_image", "deps_note"})
EXTRA_CHECK_KINDS = ("cmd", "pytest")  # an extra check must EXECUTE something: a `record` extra would be a verdict without evidence
EXTRA_CHECK_NAME = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z0-9][a-z0-9_-]*)+$")  # no whitespace/case twins of a planned name ("security.pysa_python " is not a new check)
TRUSTED_PYSA_FILES = ["scripts/localci/pysa_check.py", "scripts/localci/pysa/taint.config", "scripts/localci/pysa/fastapi_sources_sinks.pysa",
                      "scripts/localci/pysa/site_packages.txt"]  # taken from BASE: a candidate cannot weaken the taint models that judge it
PYSA_SCOPE = "apps/backend-rag/backend/"
DEFAULT_PYSA_HOME = Path.home() / ".nuzantara-pilots" / "local-ci" / "pysa-home"
DEFAULT_GATE_LEDGER = Path.home() / ".nuzantara-pilots" / "local-ci-gate" / "verdicts.jsonl"
TRUSTED_CLASSIFIER_FILES = [
    "scripts/ci/change_map.py", "scripts/ci/test_change_map.py", "scripts/ci/security_gate_flags.py",
    "scripts/ci/hotzone_changed_files.sh", "scripts/ci/impact_map.py", "scripts/ci/test_impact_map.py", "scripts/ci/test_security_gate_flags.py",
]
BAN_TEST = "scripts/tests/test_ban_predicates.py"
SECRET_ENV = ("FLY_API_TOKEN", "VERCEL_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "DATABASE_URL",
              "CLAUDE_CODE_OAUTH_TOKEN", "REDIS_PASSWORD")
# Entity rule, not a spelling: any variable that looks like a credential is stripped from check
# environments — every ANTHROPIC_* variable (the paid per-token key lives there) and any name
# ending in a credential suffix. The ban guards forbid spelling the paid key's name in prose.
SECRET_ENV_PREFIXES = ("ANTHROPIC_",)
SECRET_ENV_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "PASSWORD", "_PASSWD")


def is_secret_env(name: str) -> bool:
    return name in SECRET_ENV or name.startswith(SECRET_ENV_PREFIXES) or name.endswith(SECRET_ENV_SUFFIXES)


# Interpreter start-up hooks a candidate tree could plant (sitecustomize/usercustomize/.pth are found
# through these variables) must never reach a TRUSTED interpreter: no PYTHONPATH, no user site.
_TRUSTED_ENV_DROP = ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTEST_ADDOPTS", "PYTEST_PLUGINS")


def change_map_status(cm: dict) -> str:
    """Mirror GitHub's `changes` job: an unclassified or empty diff passes there and runs every job (run_all),
    whose weight the BLOCKED test records already carry. Anything the classifier cannot vouch for is no
    signal (BLOCKED), never FAIL — a local FAIL tells the fleet not to arm a PR GitHub accepts."""
    if cm.get("mode") == "enforcing" and cm.get("reason") in ("classified", "unclassified_paths", "empty_changed_set"):
        return "PASS"
    return "BLOCKED"


def trusted_env(base: dict | None = None) -> dict:
    """Environment for a trusted (base-ref) check: secrets stripped, python injection variables removed."""
    env = {k: v for k, v in (os.environ if base is None else base).items() if not is_secret_env(k) and k not in _TRUSTED_ENV_DROP}
    # PYTHONNOUSERSITE is deliberately NOT set: it propagates to child interpreters and hides user-site tools
    # a trusted check legitimately shells out to (detect-secrets lives there on Pro -> the ban test went red).
    # The trusted interpreter itself is started with -I, which already ignores the user site.
    env.update(PYTHONSAFEPATH="1", PYTHONDONTWRITEBYTECODE="1")
    return env
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_DEADLINE_S = 3600


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj) -> str:
    return sha256_bytes(json.dumps(obj, sort_keys=True, default=str).encode())


def git(wt: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(wt), *args], text=True).strip()


def atomic_write(p: Path, data: str) -> None:
    """Write-temp + fsync + rename: a reader sees the old file or the new one, never a torn one."""
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Store:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.state_path = self.run_dir / "state" / "state.json"
        self.lock_path = self.run_dir / "state" / "coordinator.lock"
        (self.run_dir / "state").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "receipts").mkdir(exist_ok=True)
        (self.run_dir / "logs").mkdir(exist_ok=True)

    def load(self) -> dict:
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def save(self, st: dict) -> None:
        st["updated_at"] = now()
        atomic_write(self.state_path, json.dumps(st, indent=2, sort_keys=True))

    def lock(self, blocking: bool = True):
        """Exclusive flock on this host. Returns the open file (a context manager), or None if non-blocking and busy."""
        fh = open(self.lock_path, "a+")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError:
            fh.close()
            return None
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        return fh

    def journal(self, rec: dict) -> None:
        with open(self.run_dir / "state" / "journal.jsonl", "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")


def identity(wt: Path) -> dict:
    dirty = git(wt, "status", "--porcelain", "--untracked-files=all")
    return {
        "candidate_sha": git(wt, "rev-parse", "HEAD"),
        "tree_sha": git(wt, "rev-parse", "HEAD^{tree}"),
        "dirty": bool(dirty),
        "dirty_paths": dirty.splitlines()[:20],
    }


# ------------------------------------------------------------ environment evidence
def _try(cmd: list[str], timeout: int = 60) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=trusted_env())
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def deps_lock(venv_py: str) -> tuple[str, str]:
    """sha256 of the venv's frozen requirements — `<py> -m pip freeze`, else `uv pip freeze --python <py>`."""
    for source, cmd in (("pip", [venv_py, "-I", "-m", "pip", "freeze"]), ("uv", ["uv", "pip", "freeze", "--python", venv_py])):
        out = _try(cmd)
        if out is not None:
            return sha256_bytes(out.encode()), source
    return "unavailable", "none"


def tool_identity(exe: str, cwd: str | None = None) -> dict:
    """Resolved executable path + sha256 when it is a regular file, else 'not-a-file'."""
    cand = exe
    if os.sep in exe and not os.path.isabs(exe) and cwd:
        cand = str(Path(cwd) / exe)
    found = shutil.which(cand)
    if not found:
        return {"path": None, "sha256": "not-a-file"}
    real = os.path.realpath(found)
    return {"path": real, "sha256": sha256_file(Path(real)) if os.path.isfile(real) else "not-a-file"}


def env_fingerprint(venv_py: str, checks: dict | None = None) -> dict:
    probe = "import sys,platform,pytest;print(sys.version.split()[0]);print(pytest.__version__);print(platform.platform())"
    out = _try([venv_py, "-I", "-c", probe])
    py, pt, plat = (out.split("\n") + ["", "", ""])[:3] if out else ("unavailable", "unavailable", platform.platform())
    uv = _try(["uv", "--version"])
    gv = _try(["git", "--version"])
    lock_sha, lock_src = deps_lock(venv_py)
    tools = {}
    for name, spec in sorted((checks or {}).items()):
        kind = spec.get("kind")
        iso = spec.get("isolation") or {}
        if kind in CANDIDATE_KINDS and iso.get("mode") == "container":
            tools[name] = {"image_id": iso.get("image_id"), "docker": tool_identity(iso.get("docker") or "docker"), **({"deps_image": spec["deps_image"]} if spec.get("deps_image") else {})}
        elif kind == "cmd" and spec.get("cmd"):
            tools[name] = tool_identity(spec["cmd"][0], spec.get("cwd"))
        elif kind == "trusted_steps":
            tools[name] = {a: tool_identity(a) for a in sorted({s["argv"][0] for s in spec["steps"] if s.get("argv")})}
        elif kind in ("pytest", "trusted_pytest"):
            tools[name] = tool_identity(spec.get("python") or venv_py, spec.get("cwd"))
    return {"python": py, "pytest": pt, "platform": plat, "hostname": platform.node(), "runner_version": RUNNER_VERSION,
            "runner_sha256": sha256_file(Path(__file__)), "uv_version": uv.strip() if uv else None,
            "git_version": gv.strip() if gv else None, "deps_lock_sha256": lock_sha, "deps_lock_source": lock_src, "tools": tools}


def env_hash(env: dict) -> str:
    return sha256_json(env)


def proc_start(pid: int) -> str | None:
    return (_try(["ps", "-o", "lstart=", "-p", str(pid)], timeout=5) or "").strip() or None


def pid_alive(pid: int, started: str | None = None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except OSError:
        return False
    if started:
        cur = proc_start(pid)
        if cur is not None and cur != started:
            return False  # pid recycled by an unrelated process
    return True


# ------------------------------------------------------------------ contexts matrix
def load_contexts(path: str | None) -> dict:
    """Defensive read of the required-contexts matrix. status: missing | ok | invalid."""
    if not path:
        return {"status": "missing", "reason": "no --contexts-file given", "required": None, "map": {}}
    p = Path(path)
    if not p.exists():
        return {"status": "missing", "reason": f"{path} does not exist yet", "required": None, "map": {}}
    try:
        import yaml

        raw = p.read_bytes()
        doc = yaml.safe_load(raw)
    except Exception as e:  # noqa: BLE001 — any parse failure is "invalid", never "ok"
        return {"status": "invalid", "reason": f"unreadable contexts file: {type(e).__name__}: {e}", "required": None, "map": {}}
    items = doc.get("contexts") if isinstance(doc, dict) else None
    if not isinstance(items, list) or not items:
        return {"status": "invalid", "reason": "top-level `contexts:` must be a non-empty list", "required": None, "map": {}}
    cmap: dict = {}
    for i, it in enumerate(items):
        if not isinstance(it, dict) or not isinstance(it.get("name"), str) or not it["name"].strip():
            return {"status": "invalid", "reason": f"contexts[{i}] has no string `name`", "required": None, "map": {}}
        name = it["name"]
        if name in cmap:
            return {"status": "invalid", "reason": f"duplicate context name {name!r}", "required": None, "map": {}}
        mapping = it.get("mapping")
        note = None
        if mapping not in MAPPINGS:
            note, mapping = f"unknown mapping {mapping!r} treated as blocked", "blocked"
        local = it.get("local") if isinstance(it.get("local"), dict) else {}
        coverage = it.get("coverage", "full")   # an entry that declares nothing is full; a value it cannot read is never full
        if coverage not in COVERAGES:
            note, coverage = "; ".join(x for x in (note, f"unknown coverage {coverage!r} treated as partial") if x), "partial"
        cnote = it.get("coverage_note") if isinstance(it.get("coverage_note"), str) and it["coverage_note"].strip() else None
        cmap[name] = {"mapping": mapping, "local": local, "check": local.get("check") if isinstance(local.get("check"), str) else None, "note": note,
                      "workflow_file": it.get("workflow_file"), "job_id": it.get("job_id"), "coverage": coverage,
                      "coverage_note": (cnote or "declared partial without a coverage_note") if coverage == "partial" else None}
    return {"status": "ok", "reason": "", "required": list(cmap), "map": cmap, "sha256": sha256_bytes(raw)}


def resolve_context_check(name: str, ctx: dict, checks) -> str | None:
    for cand in (ctx.get("check"), name, f"ctx.{name}"):
        if cand and cand in checks:
            return cand
    return None


# ------------------------------------------------------------------------- plan
def _extract_base_file(wt: Path, base: str, rel: str) -> bytes | None:
    r = subprocess.run(["git", "-C", str(wt), "show", f"{base}:{rel}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


PLAN_HASH_EXCLUDE = ("created_at", "created_epoch", "deadline_at", "plan_hash")


def plan_hash_of(plan: dict) -> str:
    return sha256_json({k: v for k, v in plan.items() if k not in PLAN_HASH_EXCLUDE})


def load_plan_verified(run_dir: Path) -> dict:
    """Load plan.json and refuse it when its content no longer hashes to the plan_hash it carries."""
    plan = json.loads((Path(run_dir) / "state" / "plan.json").read_text())
    if plan.get("plan_hash") != plan_hash_of(plan):
        sys.exit(f"plan.json integrity check failed in {run_dir}: content does not match its plan_hash — the plan was edited after it was frozen")
    return plan


def pysa_check_spec(wt: Path, base: str, cand: str, trusted: Path, run_dir: Path, changed: list[str], home_arg: str | None) -> dict:
    """Pysa taint judge (no NEW flow vs BASE) — N/A when the diff has no backend python, BLOCKED when it cannot be trusted or run."""
    touched = [f for f in changed if f.startswith(PYSA_SCOPE) and "/tests/" not in f and "/test/" not in f]   # ANY file: .gitattributes, .pyi, configs can change what Pysa sees
    if not touched:
        return {"kind": "record", "status": "NOT_APPLICABLE", "reason": f"no non-test file under {PYSA_SCOPE} in the diff"}
    tdir = trusted / "pysa"
    (tdir / "pysa").mkdir(parents=True, exist_ok=True)
    for rel in TRUSTED_PYSA_FILES:
        blob = _extract_base_file(wt, base, rel)
        if blob is None:
            return {"kind": "record", "status": "BLOCKED", "reason": f"trusted pysa file {rel} missing at base {base[:12]} — the check cannot judge with candidate-supplied logic"}
        (tdir / ("pysa_check.py" if rel.endswith("pysa_check.py") else f"pysa/{Path(rel).name}")).write_bytes(blob)
    home = Path(home_arg) if home_arg else DEFAULT_PYSA_HOME
    if not (home / "venv" / "bin" / "pyre").exists():
        return {"kind": "record", "status": "BLOCKED", "reason": f"pysa home {home} not set up (python scripts/localci/pysa_check.py setup --home {home} --backend-venv apps/backend-rag/.venv)"}
    try:   # measured by the BASE judge: a home that no longer matches its setup manifest is refused before anything runs
        r = subprocess.run([sys.executable, "-I", str(tdir / "pysa_check.py"), "verify-home", "--home", str(home)], capture_output=True, text=True, timeout=600, env=trusted_env())
        vh = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as e:
        r, vh = None, {"reason": f"{type(e).__name__}: {e}"}
    if not vh.get("digest"):
        why = vh.get("reason") or (r.stdout.strip() or r.stderr.strip())[-300:] if r is not None else vh.get("reason")
        return {"kind": "record", "status": "BLOCKED", "reason": f"pysa home {home} is not a measured trusted identity: {why}"}
    shas = {str(f.relative_to(tdir)): sha256_file(f) for f in sorted(tdir.rglob("*")) if f.is_file()}
    return {"kind": "cmd", "cwd": str(wt), "trusted_pythonpath": str(tdir), "trusted_dir_sha256": shas, "error_rcs": [2], "pysa_home_digest": vh["digest"],
            "cmd": [sys.executable, "-I", str(tdir / "pysa_check.py"), "judge", "--home", str(home), "--worktree", str(wt), "--base", base, "--candidate", cand,
                    "--out", str(run_dir / "receipts" / "pysa"), "--expect-home-digest", vh["digest"]],
            "purpose": f"Pysa taint on {len(touched)} touched backend file(s): no NEW log-injection/stack-trace/path/SSRF/redirect flow vs BASE {base[:12]}; judge logic and models from BASE"}


# ------------------------------------------------------- required contexts the runner executes (v0.4.0)
CTX_CHECK_NAME = re.compile(r"^ctx\.[a-z0-9][a-z0-9-]*$")
SUPERSEDED_RECORDS = {"tests.backend_shards": "ctx.backend-tests", "tests.frontend_mouth": "ctx.frontend-tests-mouth"}
MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
IMPLICIT_USES = ("actions/checkout@", "actions/setup-python@")   # stood in for by the tree copy and the image/host interpreter
STEPS_DRIVER = Path(__file__).with_name("steps_driver.py")
PYTEST_INDEXED = Path(__file__).with_name("pytest_indexed.py")
HOSTED_SCRIPTS_PYTHON = "3.11"   # scripts-tests-sweep.yml's setup-python: the interpreter hosted runs scripts/tests with
# scripts-tests-sweep.yml's "Install dependencies" step, line by line (a test pins it to the workflow): (cwd under the tree, argv). They run offline inside
# the sandbox against the deps image's /opt/wheels, so the interpreter holds the lock + cell-core + the four test packages hosted's sweep has.
SWEEP_INSTALL = (("apps/backend-rag", ["pip", "install", "--upgrade", "pip", "uv"]),
                 ("apps/backend-rag", ["uv", "pip", "install", "--system", "-r", "requirements.lock.txt"]),
                 ("apps/backend-rag", ["uv", "pip", "install", "--system", "-e", "../../packages/cell-core"]),
                 ("apps/backend-rag", ["uv", "pip", "install", "--system", "pytest", "pytest-asyncio", "pytest-mock", "fakeredis"]))
SWEEP_DEPS_CONTEXT = "Backend Tests (Python)"   # its matrix deps recipe IS that closure: same recipe, same digest, same image, no second build
SWEEP_ENV = {"HOME": "/home/runner", "USER": "runner", "LOGNAME": "runner", "UV_OFFLINE": "1", "UV_FIND_LINKS": "/opt/wheels", "PIP_FIND_LINKS": "/opt/wheels", "PIP_NO_INDEX": "1",
             "PIP_DISABLE_PIP_VERSION_CHECK": "1", "JWT_SECRET_KEY": "test_jwt_secret_key_for_testing_only_min_32_chars_long",   # pragma: allowlist secret — the sweep's public constants
             "API_KEYS": "test_api_key_1,test_api_key_2"}   # pragma: allowlist secret — its DATABASE_URL/REDIS_URL are services this sandbox does not have, so not set
INSTALL_RC = 97   # pytest_indexed.py's exit when the env install failed: no verdict on the candidate (same literal there, pinned by a test)
# What a contained step sees of GitHub: the merge_group event (the build whose verdict lands on main), and an offline pip.
CONTAINED_STEP_ENV = {"CI": "true", "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "merge_group", "GITHUB_WORKSPACE": "/w",
                      "HOME": "/home/runner", "SHELL": "/bin/bash", "PIP_FIND_LINKS": "/opt/wheels",
                      "RUNNER_TEMP": "/tmp/runner-temp", "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}


def _blocked(reason: str) -> dict:
    return {"kind": "record", "status": "BLOCKED", "reason": reason}


SHELLS = {None: ["bash", "-e", "{0}"], "bash": ["bash", "--noprofile", "--norc", "-eo", "pipefail", "{0}"]}   # GitHub's own templates


def _step_cwd(ws: dict, run_defaults: dict) -> str:
    wd = ws.get("working-directory") or run_defaults.get("working-directory") or "."
    return "." if wd in (".", "./") else safe_tree_path(str(wd).rstrip("/"))


HOSTED_RUNNERS = ("ubuntu-latest", "ubuntu-24.04")   # what the host tools and candidate.Dockerfile stand in for


def written_reason(v) -> str | None:
    """A not-applicable reason is a string with something legible in it: a flag, a list or a blank (zero-width included) is not."""
    return v.strip() if isinstance(v, str) and any(ch.isalnum() for ch in v) else None


def resolve_steps(job: dict, local: dict, base: str, run_defaults: dict | None = None,
                  wf_env: dict | None = None, expressions: bool = False) -> tuple[list | None, str | None]:
    """Account for EVERY step of the BASE workflow job, in matrix order: a transcribed `argv`, the BASE `run:` body verbatim (written
    to a script file and run with GitHub's shell template), or `not_applicable` with a reason. A step the matrix does not name, a
    `not_run` step, duplicate step names, or an expression the runner does not evaluate makes the context BLOCKED — the local verdict
    never covers less than the job and still calls itself the job's. A step's `if:` is recorded, not evaluated: running a step
    GitHub might skip can only add red, never hide it. Env merges as GitHub does: workflow, job, step, then the matrix's overrides;
    a job that runs in its own `container:`, beside `services:`, or on another runner image is not emulated. `expressions` (service
    contexts): `${{ }}`, `if:`, `continue-on-error` and step `timeout-minutes` are kept for the driver to evaluate (gh_expr.py;
    plan_service_context validates them), artifact actions may be `emulate`d, and `services:` are plan_services' to judge."""
    runs_on = job.get("runs-on")
    runs_on = runs_on[0] if isinstance(runs_on, list) and len(runs_on) == 1 else runs_on   # `[ubuntu-latest]` is one label
    if (shape := [k for k in ("container", "services") if k in job and not (expressions and k == "services")]) or runs_on not in HOSTED_RUNNERS:
        return None, f"BASE job shape not emulated: {shape or ''} runs-on={job.get('runs-on')!r} (the sandbox stands in for {HOSTED_RUNNERS})"
    wsteps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
    names = [s["name"] for s in wsteps if isinstance(s.get("name"), str)]
    if (dups := sorted({n for n in names if names.count(n) > 1})):
        return None, f"BASE job has duplicate step names {dups}: its steps cannot be told apart"
    defaults = {**(run_defaults or {}), **(((job.get("defaults") or {}).get("run")) or {})}
    by_name = {s["name"]: s for s in wsteps if isinstance(s.get("name"), str)}
    out: list = []
    seen: set = set()
    not_run: list = []
    for i, st in enumerate(local.get("steps") or []):
        st = st if isinstance(st, dict) else {}
        wname = st.get("workflow_step")
        if isinstance(st.get("workflow_step_prefix"), str) and st["workflow_step_prefix"]:   # for a name that spells a banned shape
            hits = [n for n in by_name if n.startswith(st["workflow_step_prefix"])]
            wname = hits[0] if len(hits) == 1 else None
        if wname not in by_name or wname in seen:
            return None, f"matrix step {i} names workflow step {wname!r}: absent from the BASE job or mapped twice"
        seen.add(wname)
        ws = by_name[wname]
        if st.get("not_run"):
            not_run.append(f"{wname!r}: {st['not_run']}")
            continue
        if "not_applicable" in st:
            if (reason := written_reason(st["not_applicable"])) is None:
                return None, f"matrix step {wname!r}: not_applicable needs a written reason, got {st['not_applicable']!r}"
            out.append({"name": wname, "not_applicable": reason})
            continue
        if expressions and st.get("emulate"):
            act = next((v for k, v in EMULATED_USES.items() if str(ws.get("uses", "")).startswith(k)), None)
            w = ws.get("with") or {}
            if act is None or "\n" in str(w.get("path", "")).strip() or ws.get("continue-on-error"):
                return None, f"workflow step {wname!r}: only a single-path, fail-on-error upload/download-artifact is emulated"
            out.append({"name": wname, **({"if": str(ws["if"])} if ws.get("if") is not None else {}),
                        "emulate": {"action": act, **{k: str(w.get(k, "")) for k in ("path", "name", "pattern")}, "merge": w.get("merge-multiple") is True,
                                    "if_no_files_found": str(w.get("if-no-files-found", "warn"))}})
            continue
        env = {k: str(v) for k, v in {**(wf_env or {}), **(job.get("env") or {}), **(ws.get("env") or {})}.items()}
        env.update({k: base if v == "$BASE_SHA" else str(v) for k, v in (st.get("env") or {}).items()})
        step = {"name": wname}
        if st.get("argv"):
            step["argv"] = [base if x == "$BASE_SHA" else str(x) for x in st["argv"]]
        else:
            run, shell = ws.get("run"), ws.get("shell") or defaults.get("shell")
            if not isinstance(run, str) or ("${{" in run and not expressions) or shell not in SHELLS:
                return None, f"workflow step {wname!r} is not a bash run: body without expressions (shell={shell!r}) — transcribe it as argv or give a reason"
            step.update(argv=list(SHELLS[shell]), script=run)
        coe = ws.get("continue-on-error")
        if not expressions and ((expr := sorted(k for k, v in env.items() if "${{" in v)) or coe):
            return None, f"workflow step {wname!r}: env {expr} carry expressions the runner does not evaluate (override them) or the step is continue-on-error"
        try:
            step.update(env=env, cwd=_step_cwd(ws, defaults))
        except RuntimeError as e:
            return None, f"workflow step {wname!r}: working-directory {e}"
        if ws.get("if") is not None:
            step["if" if expressions else "if_not_evaluated"] = str(ws["if"])
        if expressions:
            tm = ws.get("timeout-minutes")
            if coe not in (None, False, True) or (tm is not None and (isinstance(tm, bool) or not isinstance(tm, (int, float)) or tm <= 0)):
                return None, f"workflow step {wname!r}: continue-on-error/timeout-minutes must be literals here"
            step.update({k: v for k, v in (("id", ws.get("id")), ("continue_on_error", coe is True), ("timeout_s", tm * 60 if tm else None)) if v})
        elif ws.get("timeout-minutes") is not None:   # hosted kills the step there; only the expression-mode driver does too
            return None, f"workflow step {wname!r}: a step timeout-minutes is emulated only in a service context (expressions: true)"
        if st.get("trusted_scan") is False:   # a path filter (`case` list, `git diff -- <paths>`) names surfaces, not judges
            step["trusted_scan"] = False
        out.append(step)
    unmapped = [s.get("name") or s.get("uses") or "<unnamed step>" for s in wsteps
                if s.get("name") not in seen and not str(s.get("uses", "")).startswith(IMPLICIT_USES)]
    why = "; ".join(([f"BASE workflow step(s) {unmapped} not mapped by the matrix"] if unmapped else []) + [f"not run locally: {n}" for n in not_run])
    return (None, why) if why else (out, None)


def named_scripts(wt: Path, base: str, steps: list) -> list:
    """Every .py/.sh file at BASE that a step names outright, and every .py/.sh under a directory it names with a trailing slash
    (`pytest infra/organ-conformance/`): the judges a context's own workflow runs, taken from BASE. Comment lines are not read, nor
    steps the matrix marks `trusted_scan: false` (path sentinels, whose path lists name the surfaces under test, not judges)."""
    listing = git(wt, "ls-tree", "-r", "--name-only", base).splitlines()
    return step_judges(steps, [f for f in listing if f.endswith((".py", ".sh"))])


def step_judges(steps: list, files: list) -> list:
    """The files of `files` the steps name outright or under a directory they name with a trailing slash; comment lines and
    `trusted_scan: false` steps are not read. Over one step it is the judges that step's own verdict was read with (B5)."""
    text = "\n".join(ln for s in steps if s.get("trusted_scan") is not False
                     for ln in ((s.get("script") or "") + "\n" + " ".join(s.get("argv") or [])).splitlines() if not ln.lstrip().startswith("#"))
    toks = set(re.findall(r"[A-Za-z0-9_][A-Za-z0-9_./-]*", text))
    named = {f for f in files if f in toks}
    for d in (t for t in toks if t.endswith("/") and t.count("/") >= 2):   # `infra/organ-conformance/`, never a bare `scripts/`
        named |= {f for f in files if f.startswith(d)}
    return sorted(named)


def select_python(job: dict, have: str | None, extra: dict | None = None) -> tuple[str | None, str | None]:
    """actions/setup-python is stood in for by the interpreter the steps run under: its pin must name the default one ("" = no PATH
    change) or one of the image's extra interpreters (`LOCALCI_PYTHONS`, full versions; its bin dir goes first on PATH, as
    setup-python does). A pin without a minor ("3", "3.x": hosted takes the newest), an absent pin (hosted reads a version file) or a
    second setup-python step (an interpreter switch mid-job) is not emulated. (prefix, None) or (None, why)."""
    pins = [s for s in job.get("steps") or [] if isinstance(s, dict) and str(s.get("uses", "")).startswith("actions/setup-python@")]
    if len(pins) > 1:
        return None, f"BASE job runs actions/setup-python {len(pins)} times: an interpreter switch mid-job is not emulated"
    if not pins:
        return "", None
    want = str(((pins[0].get("with") or {}).get("python-version")) or "")
    parts = [p for p in want.split(".") if p not in ("x", "*")]
    if len(parts) >= 2 and all(p.isdigit() for p in parts):
        if have and have.split(".")[:len(parts)] == parts:
            return "", None
        if (hit := next((d for v, d in sorted((extra or {}).items()) if v.split(".")[:len(parts)] == parts), None)):
            return hit, None
    return None, f"BASE setup-python pins python-version {want!r}, the interpreters here are {[have, *sorted(extra or {})]!r}"


HISTORY_MAX_FILES = 3000


def history_delta(wt: Path, base: str, cand: str) -> dict | str:
    """What the sandbox needs to rebuild BASE as a commit under the candidate's: the paths the candidate added, and the BASE mode and
    blob of every path it modified, deleted or retyped. Inside, `main` and `origin/main` are that BASE commit (see steps_driver)."""
    raw = subprocess.run(["git", "-C", str(wt), "diff", "--raw", "--no-abbrev", "--no-renames", "-z", base, cand], capture_output=True, check=True).stdout.decode()
    fields, added, olds = raw.split("\0"), [], []
    for meta, rel in zip(fields[0::2], fields[1::2]):
        old_mode, _new_mode, old_oid, _new_oid, status = meta.lstrip(":").split(" ")
        if "160000" in (old_mode, _new_mode):
            return f"the candidate changes the submodule pointer {rel!r}: the sandbox tree carries no gitlinks, BASE is not rebuilt"
        if "\n" in rel:
            return f"the changed path {rel!r} holds a newline: BASE is not rebuilt inside the sandbox"
        (added if status == "A" else olds).append(safe_tree_path(rel) if status == "A" else [safe_tree_path(rel), old_mode, old_oid])
    if len(added) + len(olds) > HISTORY_MAX_FILES:
        return f"the diff touches {len(added) + len(olds)} paths (> {HISTORY_MAX_FILES}): BASE is not rebuilt inside the sandbox"
    return {"added": added, "base": olds}


def plan_context_check(wt: Path, base: str, cand: str, trusted: Path, name: str, ctx: dict, trusted_sha: dict, changed: list,
                       pyv: dict) -> dict:
    """One planned check for one required context. `where: host` = BASE scripts (or a version-pinned tool) judging the candidate
    tree as data — a trusted, sealed check; `where: container` = the steps run inside the candidate sandbox with the BASE copies of
    `trusted_files` laid over the candidate's. Anything that cannot be planned honestly is a BLOCKED record naming why."""
    local, wf = ctx["local"], ctx.get("workflow_file")
    where = local.get("where")
    if where not in ("host", "container"):
        return _blocked(f"local.where must be host or container, got {where!r}")
    try:
        import yaml

        doc = yaml.safe_load(_extract_base_file(wt, base, str(wf)) or b"")
        job = doc["jobs"][ctx.get("job_id")]
        if not isinstance(job, dict):
            raise TypeError("job is not a mapping")
    except Exception as e:  # noqa: BLE001 — an unreadable BASE workflow is no plan, never a guess
        return _blocked(f"BASE workflow {wf} job {ctx.get('job_id')!r} unreadable at {base[:12]}: {type(e).__name__}")
    steps, why = resolve_steps(job, local, base if where == "host" else "main", ((doc.get("defaults") or {}).get("run")) or {}, doc.get("env") or {})
    prefix, why2 = select_python(job, pyv.get(where), pyv.get("container_extra") if where == "container" else None)
    if why or why2:
        return _blocked(why or why2)
    try:
        files = [safe_tree_path(str(f)) for f in local.get("trusted_files") or []]
    except RuntimeError as e:
        return _blocked(f"trusted_files: {e}")
    if local.get("trusted_from_steps"):
        files += [f for f in named_scripts(wt, base, steps) if f not in files]
    blobs = {f: _extract_base_file(wt, base, f) for f in files}
    if (missing := [f for f, b in blobs.items() if b is None]):
        return _blocked(f"trusted file(s) {missing} missing at base {base[:12]} — the candidate would supply its own judge")
    judged = [*files, str(wf)]   # mode and object: a judge turned into a symlink or an executable is a rewritten judge
    modified = [f for f, a, b in zip(judged, tree_entries(wt, base, judged), tree_entries(wt, cand, judged)) if a != b]
    if where == "container":   # the sandbox gets raw blobs: a changed .gitattributes can make GitHub's checkout materialize other bytes
        modified += [f for f in changed if f.rsplit("/", 1)[-1] == ".gitattributes"]
    for st in steps:   # the judges each step names: a red read with one the candidate rewrites is no verdict (steps_verdict)
        st["trusted"] = step_judges([st], files)
    spec = {"context": name, "cwd": str(wt), "steps": steps, "trusted_files": files, "judge_modified": modified}
    if isinstance(tm := job.get("timeout-minutes"), (int, float)) and not isinstance(tm, bool) and tm > 0:
        spec["timeout_s"] = int(tm * 60)   # hosted kills the job there: no local green may take longer
    if where == "container":
        for f, b in blobs.items():
            dest = trusted / "base_files" / f
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b)
            trusted_sha[f] = sha256_bytes(b)
        for s in steps:
            if s.get("argv"):
                s["argv"] = ["python" if x == "$PY" else x for x in s["argv"]]
        history = history_delta(wt, base, cand) if local.get("git_index") else None
        if isinstance(history, str):
            return _blocked(history)
        return {**spec, "kind": "contained_steps", "git_index": bool(local.get("git_index")), "history": history, "path_prefix": prefix,
                "venv": True,
                "env": CONTAINED_STEP_ENV,
                "driver_sha256": sha256_file(STEPS_DRIVER), "purpose": f"{name}: {len(steps)} workflow step(s) in the candidate sandbox, {files} from BASE"}
    tdir = trusted / "ctx" / ctx["check"]
    for f, b in blobs.items():
        (tdir / f).parent.mkdir(parents=True, exist_ok=True)
        (tdir / f).write_bytes(b)
    pins: dict = {}
    for tool, var in (local.get("tool_pins") or {}).items():
        found = shutil.which(str(tool))
        path = os.path.realpath(found) if found else None
        if path and (not os.path.isabs(found) or Path(path).is_relative_to(os.path.realpath(wt)) or not os.path.isfile(path)):
            return _blocked(f"{tool}: resolves to {found!r} — relative or inside the candidate worktree, never executed as a judge")
        want = str({**(doc.get("env") or {}), **(job.get("env") or {})}.get(var, ""))
        got = ((_try([path, "-version"]) or "").splitlines() or [""])[0].strip() if path else None
        if not want or got != want:
            return _blocked(f"{tool}: host binary {path or 'not on PATH'} reports version {got!r}, BASE {wf} pins {var}={want!r}")
        pins[tool] = path
    for mod in local.get("host_modules") or []:
        if not MODULE_NAME.match(str(mod)) or _try([sys.executable, "-I", "-c", f"import {mod}"]) is None:
            return _blocked(f"host interpreter {sys.executable} cannot import {mod!r}")
    for s in steps:
        a = s.get("argv")
        if a and "script" not in s and a[0] == "$PY" and len(a) > 1 and a[1] in blobs:
            s["argv"] = [sys.executable, "-I", str(tdir / a[1]), *a[2:]]
        elif a and "script" not in s and a[0] in pins:
            s["argv"] = [pins[a[0]], *a[1:]]
        elif a:
            return _blocked(f"host step {s['name']!r} runs {a[:2]}: only `$PY <trusted file>` or a version-pinned tool runs on the host")
    return {**spec, "kind": "trusted_steps", "trusted_dir": str(tdir), "trusted_dir_sha256": full_dir_map(tdir),
            "tool_sha256": {p: sha256_file(Path(p)) for p in pins.values()},
            "purpose": f"{name}: BASE {files} and pinned {sorted(pins)} judge the candidate tree on the host (no candidate code runs)"}


def tree_entries(wt: Path, rev: str, paths: list) -> list:
    """(mode, type, object) of each path at `rev`, None where absent; paths taken literally, never as pathspec patterns."""
    out = subprocess.run(["git", "--literal-pathspecs", "-C", str(wt), "ls-tree", "-z", "--full-tree", rev, "--", *paths],
                         capture_output=True, check=True).stdout.decode()
    got = {rec.split("\t", 1)[1]: tuple(rec.split("\t", 1)[0].split(" ")) for rec in out.split("\0") if "\t" in rec}
    return [got.get(p) for p in paths]


# ------------------------------------------------------- service contexts (v0.6.0): jobs, services, deps images, expressions
GH_EXPR = Path(__file__).with_name("gh_expr.py")
EMULATED_USES = {"actions/upload-artifact@": "upload", "actions/download-artifact@": "download"}
HEALTH_FLAGS = {"--health-cmd": "cmd", "--health-interval": "interval", "--health-timeout": "timeout", "--health-retries": "retries"}
SERVICE_STEP_ENV = {"UV_OFFLINE": "1", "UV_FIND_LINKS": "/opt/wheels"}   # uv's spelling of the offline wheelhouse pip already gets
RUNNER_CTX = {"os": "Linux", "arch": "ARM64", "temp": "/tmp/runner-temp", "name": "localci"}   # arm64 here, X64 hosted: a parity gap
ARTIFACT_MAX_BYTES = 256 << 20
DEPS_LABEL = "org.nuzantara.localci.deps"
DEPS_RECIPE_LABEL = "org.nuzantara.localci.recipe"   # the check that built it: merger.py prune keeps the newest per recipe
DEPS_BUILD_TIMEOUT_S = 7200   # a cold build: 3552 s measured for e2e-tests on Pro (2026-10-11); merger.PLAN_TIMEOUT_S stays above it
_MARKER_ATOM = r"""(?:[a-z_]+|"[^"]*"|'[^']*')\s*(?:===|==|!=|<=|>=|<|>|~=|not\s+in|in)\s*(?:[a-z_]+|"[^"]*"|'[^']*')"""
# `name[extras]==version`, optionally `; <PEP 508 marker>` — nothing else; and pip reads a space-separated token starting with `-`
# anywhere on the line as an option (`--no-binary` would lift --only-binary), so _pin_lines also drops any line with a `\s-`.
REQ_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9.+!_-]+"
                     rf"(\s*;\s*\(*\s*{_MARKER_ATOM}\s*\)*(?:\s+(?:and|or)\s+\(*\s*{_MARKER_ATOM}\s*\)*)*)?\s*\\?$")
# The deps image: the candidate image plus an offline wheelhouse of the closure a job's install steps ask for, so they re-run
# verbatim with no network (pip and uv read /opt/wheels), plus public files the job's code downloads at run time (fetched once,
# sha256-pinned in the matrix). Built at plan time with network, but nothing of the candidate executes: wheels only
# (--only-binary, no build backend runs), from requirement lines reduced to `name==version` pins (an -e path, a URL or an index
# option never reaches the network stage). The interpreter the job's setup-python pin names is handed to the sandbox user, as
# the hosted toolcache belongs to the runner user, so `pip install` / `uv pip install --system` write where they do hosted.
DEPS_DOCKERFILE = """\
ARG BASE
FROM ${BASE} AS wheels
ARG PY
USER root
COPY req.txt pkgs.txt fetch.json fetch.py install.txt /req/
RUN "$PY" -m pip download --no-cache-dir -q --disable-pip-version-check --only-binary=:all: -d /wheels -r /req/req.txt \\
 && "$PY" -m pip download --no-cache-dir -q --disable-pip-version-check --only-binary=:all: -d /wheels pip uv setuptools wheel $(cat /req/pkgs.txt) \\
 && "$PY" /req/fetch.py get /req/fetch.json /fetch
FROM ${BASE}
ARG PY
USER root
RUN chown -R 65534:65534 "$(dirname "$(dirname "$(readlink -f "$PY")")")"
COPY --from=wheels /wheels/ /opt/wheels/
COPY --from=wheels /req /req
RUN --network=none --mount=type=bind,from=wheels,source=/fetch,target=/mnt/fetch "$PY" /req/fetch.py put /req/fetch.json /mnt/fetch
USER 65534
RUN --network=none xargs -r "$PY" -m pip install -q --disable-pip-version-check --no-deps --no-index < /req/install.txt
USER root
"""
# A job with no Python closure (Frontend Tests: node only) starts from the candidate image as it is: no wheel stage, no interpreter
# handed to the sandbox user.
DEPS_BARE = """\
ARG BASE
FROM ${BASE}
USER root
"""
# Node, when the job calls it (ubuntu-latest carries one; setup-node pins one): the official image's binary and its npm.
DEPS_NODE = """\
COPY --from=node:{v}-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:{v}-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \\
 && node --version | grep -q "^v{v}\\."
ENV LOCALCI_NODE={v}
"""
# npm: the candidate's lockfile and package manifests (data) fill an npm cache in the official node image with network and no
# lifecycle script (`--ignore-scripts`: no package code runs there); the job's own `npm install` then runs verbatim, offline, from
# that cache, its scripts inside the sandbox. Every lock entry resolves to the public registry or is a workspace link (checked).
DEPS_NPM_STAGE = """\
FROM node:{v}-bookworm-slim AS npmcache
COPY npm/ /src/
RUN for lock in $(cd /src && find . -name package-lock.json | sort); do \\
      (cd "/src/${{lock%/package-lock.json}}" && npm ci --ignore-scripts --no-audit --no-fund --loglevel=error --cache /npm-cache) || exit 1; \\
    done && rm -rf /src
"""
DEPS_NPM = """\
COPY --from=npmcache --chown=65534:65534 /npm-cache /opt/npm-cache
"""
# Playwright: the lock's playwright-core, from the registry, installs its browser and the OS libraries it needs (apt) as root
# with network at build; the job's own browser-install step needs root and network, which the sandbox never has. A child that
# drops PLAYWRIGHT_BROWSERS_PATH (the visa smoke's sanitized env keeps HOME) finds it at the runner user's default cache path.
DEPS_PLAYWRIGHT = """\
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN for i in 1 2 3; do npm_config_cache=/tmp/npx-root timeout 1200 npx -y playwright-core@{pw} install --with-deps {browser} && break; \\
      [ $i = 3 ] && exit 1; sleep 5; done && rm -rf /tmp/npx-root \\
 && chmod -R a+rX /opt/ms-playwright \\
 && install -d -o 65534 -g 65534 /home/runner/.cache && ln -s /opt/ms-playwright /home/runner/.cache/ms-playwright
"""
DEPS_APT = """\
RUN A='-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::Languages=none' && \\
    for i in 1 2 3; do timeout 300 apt-get $A update -qq && break; [ $i = 3 ] && exit 1; sleep 5; done && \\
    DEBIAN_FRONTEND=noninteractive timeout 900 apt-get $A install -y -qq --no-install-recommends {pkgs} && rm -rf /var/lib/apt/lists/*
"""
DEPS_OFFLINE_NPM = """\
ENV npm_config_cache=/opt/npm-cache npm_config_offline=true npm_config_update_notifier=false
"""
DEPS_FETCH_PY = """\
import hashlib, json, os, shutil, sys, urllib.request
mode, spec, where = sys.argv[1:4]
os.makedirs(where, exist_ok=True)
for i, f in enumerate(json.load(open(spec))):
    if mode == "get":
        data = urllib.request.urlopen(f["url"], timeout=300).read()
        if hashlib.sha256(data).hexdigest() != f["sha256"]:
            sys.exit(f"{f['url']}: sha256 differs from the matrix pin")
        open(os.path.join(where, str(i)), "wb").write(data)
    else:
        os.makedirs(os.path.dirname(f["path"]), exist_ok=True)
        shutil.copyfile(os.path.join(where, str(i)), f["path"])
        d = f["path"]
        while d not in ("/", "/tmp", "/home"):
            os.chown(d, 65534, 65534)
            d = os.path.dirname(d)
"""


# CodeQL (the two CodeQL Analysis contexts): the CLI bundle, pinned in the matrix and extracted at build. The tarball (675 MB) is fetched by
# the builder with its sha256 checked (`ADD --checksum`) into a stage of its own and bind-mounted into the one RUN that extracts it: it is
# never read whole into memory here and never lands in a layer. The RUN also asserts `codeql version` equals the pin.
DEPS_CODEQL_STAGE = """\
FROM scratch AS codeqlbundle
ADD --checksum=sha256:{sha256} {url} /bundle.tgz
"""
DEPS_CODEQL = """\
RUN --mount=type=bind,from=codeqlbundle,source=/bundle.tgz,target=/mnt/bundle.tgz \\
    tar -xzf /mnt/bundle.tgz -C /opt && test "$(/opt/codeql/codeql version --format=terse)" = "{version}"
ENV PATH=/opt/codeql:${{PATH}}
"""
LEG_SCRIPT = "codeql_leg.sh"
LEG_INPUT_ENV = frozenset({"CODEQL_BIN", "CODEQL_SOURCE_ROOT", "LOCALCI_CODEQL_WORK", "CODEQL_BASE_CONFIG"})   # the leg's own tests set these, nothing else may
CODEQL_URL = re.compile(r"https://[A-Za-z0-9._~/%+-]+")
CODEQL_RESULTS = re.compile(r"^LOCALCI_CODEQL_RESULTS language=([a-z]+) results=(\d+) rules=(\d+)$", re.M)


def codeql_pin(raw) -> tuple[dict | None, str | None]:
    """deps.codeql as the matrix pins it: ({version, url, sha256}, None), (None, None) when absent, (None, why) when it cannot be pinned."""
    if raw is None:
        return None, None
    ok = isinstance(raw, dict) and set(raw) == {"version", "url", "sha256"} and all(isinstance(v, str) for v in raw.values())
    if not ok or not re.fullmatch(r"\d+\.\d+\.\d+", raw["version"]) or not CODEQL_URL.fullmatch(raw["url"]) \
            or not re.fullmatch(r"[0-9a-f]{64}", raw["sha256"]):
        return None, "deps.codeql needs exactly a plain version, an https url without a query and a lowercase sha256 pin"
    return dict(raw), None


def _gh_expr():
    """gh_expr.py by path: the same file the driver gets at /cfg, whether the runner runs as a script or as a module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("localci_gh_expr", GH_EXPR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def github_ctx(base: str, pr: int | None, repo: str) -> dict:
    """The merge_group event inside the sandbox, where `main` is the rebuilt BASE commit and `localci` the candidate's; the driver
    replaces these two names with their hex ids once it has built them (hosted hands hex ids, and judges check the shape)."""
    head_ref = f"refs/heads/gh-readonly-queue/main/pr-{pr}-{base}" if pr else ""
    return {"event_name": "merge_group", "repository": repo, "sha": "localci", "ref": head_ref or "refs/heads/localci", "actor": "localci",
            "event": {"action": "checks_requested",
                      "merge_group": {"base_sha": "main", "head_sha": "localci", "head_ref": head_ref, "base_ref": "refs/heads/main"}}}


def _seconds(v: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)?", v.strip())
    if not m:
        raise ValueError(v)
    return float(m.group(1)) * {"ms": 0.001, "s": 1, "m": 60, None: 1}[m.group(2)]


SERVICE_KEYS = {"image", "credentials", "env", "ports", "options"}   # what a hosted service may declare, but `volumes`: never mounted here


def plan_services(job: dict, images: dict, docker: str) -> tuple[list | None, str | None]:
    """A job's `services:` as BASE declares them. The image must have an operator-pinned local stand-in (a BASE tag the operator never
    vetted is BLOCKED, not guessed), its id is pinned now; env is BASE's literal map and nothing else (no host variable can reach it);
    only health flags are honoured, and only identity port maps, which the shared loopback reaches as the hosted job reaches localhost."""
    out = []
    for sname, svc in (job.get("services") or {}).items():
        svc = svc if isinstance(svc, dict) else {}
        if (extra := sorted(set(svc) - SERVICE_KEYS)):
            return None, f"service {sname}: {extra} not emulated (a volume is never mounted into a service here; only {sorted(SERVICE_KEYS)} are read)"
        ref = str(svc.get("image") or "")
        if not images.get(ref):
            return None, f"service {sname}: BASE image {ref!r} has no operator-pinned stand-in in local.service_images"
        env = {str(k): str(v) for k, v in (svc.get("env") or {}).items()}
        if (expr := sorted(k for k, v in env.items() if "${{" in v)):
            return None, f"service {sname}: env {expr} carry expressions (a secret or a context the run does not hold; names only)"
        ports = [str(p) for p in svc.get("ports") or []]
        if not ports or any(not re.fullmatch(r"(\d+):\1", p) for p in ports):
            return None, f"service {sname}: ports {ports} — only identity maps (N:N) are reachable on the shared loopback"
        try:
            toks, health = shlex.split(str(svc.get("options") or "")), {}
            while toks:
                flag = toks.pop(0)
                if flag not in HEALTH_FLAGS or not toks:
                    return None, f"service {sname}: option {flag!r} is not emulated (only {sorted(HEALTH_FLAGS)})"
                health[HEALTH_FLAGS[flag]] = toks.pop(0)
            budget = (int(health["retries"]) + 1) * (_seconds(health["interval"]) + _seconds(health["timeout"]))
        except (ValueError, KeyError) as e:
            return None, f"service {sname}: health options incomplete or unreadable ({type(e).__name__}: {e})"
        iid = (_try([docker, "image", "inspect", "--format", "{{.Id}}", images[ref]]) or "").strip()
        if not iid.startswith("sha256:"):
            return None, f"service {sname}: stand-in image {images[ref]!r} for {ref} is not present (docker pull it, then plan again)"
        out.append({"name": str(sname), "image": ref, "local_image": images[ref], "image_id": iid, "env": env, "ports": ports, "health": health,
                    "health_budget_s": budget + 60})
    return out, None


GEN_RE = re.compile(r"\$LOCALCI_GEN\.([a-z][a-z0-9_]*)")   # a value the run makes up, named: the same name is the same value in every container of the leg
EXTRA_SERVICE_KEYS = {"name", "image", "env", "health", "seed", "reached"}
REACHED_KEYS = {"request", "min", "api_key_env"}
SEED_KEYS = {"file", "class", "name_field", "size_field", "distance", "api_key_env"}
DIGEST_IMAGE = re.compile(r"[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}")


def fill_generated(env: dict, store: dict) -> dict:
    """`$LOCALCI_GEN.<name>` in an env value becomes 48 random hex characters, made now, once per name per leg and kept only in `store`
    (this process's memory): the stand-in services and the steps of one leg agree on them, and no run, host or disk ever holds the same."""
    return {k: GEN_RE.sub(lambda m: store.setdefault(m.group(1), os.urandom(24).hex()), str(v)) for k, v in env.items()}


def read_seed(seed: object, read_base) -> tuple[dict | None, str | None]:
    """The one collection a Qdrant stand-in is seeded with, EMPTY, so the code that walks collections runs here as it does hosted (it
    holds 14 there). Its name and vector size are the defaults the backend's own Settings class declares at BASE (read with ast from
    the BASE blob at plan time and frozen in the plan, never typed into the matrix); the distance is the one every collection
    migration of the backend creates (`Cosine`)."""
    if not isinstance(seed, dict) or set(seed) != SEED_KEYS:
        return None, f"seed needs exactly {sorted(SEED_KEYS)}"
    blob = read_base(str(seed["file"]))
    if blob is None:
        return None, f"seed: {seed['file']} is absent from BASE"
    import ast
    try:
        cls = next(n for n in ast.parse(blob).body if isinstance(n, ast.ClassDef) and n.name == seed["class"])
        got = {n.target.id: n.value.value for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
               and isinstance(n.value, ast.Constant)}
    except (SyntaxError, ValueError, StopIteration):
        return None, f"seed: class {seed['class']} unreadable in BASE {seed['file']}"
    name, size = got.get(seed["name_field"]), got.get(seed["size_field"])
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) or type(size) is not int or not 0 < size <= 65536:
        return None, f"seed: BASE declares no plain {seed['name_field']} / {seed['size_field']} constant"
    if seed["distance"] not in ("Cosine", "Dot", "Euclid") or not re.fullmatch(r"[A-Z0-9_]+", str(seed["api_key_env"])):
        return None, "seed: distance or api_key_env unreadable"
    return {"collection": name, "size": size, "distance": seed["distance"], "api_key_env": str(seed["api_key_env"])}, None


SEED_SCRIPT = """exec 3<>/dev/tcp/127.0.0.1/6333
B='{"vectors":{"size":%d,"distance":"%s"}}'
printf 'PUT /collections/%s HTTP/1.0\\r\\napi-key: %%s\\r\\nContent-Type: application/json\\r\\nContent-Length: %%d\\r\\n\\r\\n%%s' "$%s" ${#B} "$B" >&3
head -1 <&3 | grep -q ' 200 '"""


TELEMETRY_SCRIPT = """exec 3<>/dev/tcp/127.0.0.1/6333
printf 'GET /telemetry?details_level=3 HTTP/1.0\\r\\napi-key: %%s\\r\\n\\r\\n' "$%s" >&3
tail -n 1 <&3"""


def requests_seen(docker: str, ctr: str, reached: dict) -> int | None:
    """How many 2xx answers the stand-in gave to `reached["request"]` (Qdrant's own telemetry counts them per route), read from inside
    the container with its key. None when it cannot be read. The seed makes a PUT, the container's health check opens a socket: a
    `GET /collections` is the backend's own boot probe or /health, so zero means the backend never reached the stand-in."""
    out = _try([docker, "exec", ctr, "bash", "-c", TELEMETRY_SCRIPT % reached["api_key_env"]], 60)
    try:
        by_status = json.loads(out or "")["result"]["requests"]["rest"]["responses"].get(reached["request"], {})
        return sum(int(v["count"]) for k, v in by_status.items() if str(k).startswith("2"))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def step_summary(log_text: str, step_name: str) -> dict | None:
    """{'passed': n, 'skipped': n} from the LAST Playwright summary lines inside one driver step's output (the segment between its
    `##[localci] step N: <name>` marker and its `step N rc=` line); None when the step or its summary is absent."""
    m = re.search(r"^##\[localci\] step (\d+): " + re.escape(step_name) + r"$", log_text, re.M)
    if not m:
        return None
    end = re.search(rf"^##\[localci\] step {m.group(1)} rc=", log_text[m.end():], re.M)
    seg = log_text[m.end():m.end() + end.start()] if end else log_text[m.end():]
    passed = re.findall(r"^\s+(\d+) passed(?: \([^)]*\))?\s*$", seg, re.M)
    skipped = re.findall(r"^\s+(\d+) skipped\s*$", seg, re.M)
    return {"passed": int(passed[-1]), "skipped": int(skipped[-1]) if skipped else 0} if passed else None


def plan_extra_services(extra: object, taken: set, docker: str, read_base=lambda rel: None) -> tuple[list | None, str | None]:
    """Stand-ins the MATRIX adds beside BASE's `services:` (hosted points a secret at a cloud endpoint no container here can be): each is
    pinned by DIGEST in the matrix (a tag is a moving target), present locally (never pulled by a run), and gets the same shape and the
    same start, health budget and teardown as a BASE service. Its env is the matrix's literal map; only `$LOCALCI_GEN.<name>` is made up."""
    out = []
    for i, svc in enumerate(extra if isinstance(extra, list) else [] if extra is None else [None]):
        if not isinstance(svc, dict) or (bad := sorted(set(svc) - EXTRA_SERVICE_KEYS)):
            return None, f"extra_services[{i}]: a mapping of {sorted(EXTRA_SERVICE_KEYS)} only (got {None if not isinstance(svc, dict) else bad})"
        name, ref, h = str(svc.get("name") or ""), str(svc.get("image") or ""), svc.get("health")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or name in taken:
            return None, f"extra_services[{i}]: name {name!r} is not a plain name, or is already a service of the job"
        if not DIGEST_IMAGE.fullmatch(ref):
            return None, f"service {name}: image {ref!r} is not pinned by digest (repo@sha256:<64 hex>)"
        env = {str(k): str(v) for k, v in (svc.get("env") or {}).items()}
        if (expr := sorted(k for k, v in env.items() if "${{" in v)):
            return None, f"service {name}: env {expr} carry expressions"
        if not isinstance(h, dict) or set(h) != {"cmd", "interval", "timeout", "retries"} or not h["cmd"]:
            return None, f"service {name}: health needs exactly cmd, interval, timeout and retries"
        try:
            health = {k: str(v) for k, v in h.items()}
            budget = (int(health["retries"]) + 1) * (_seconds(health["interval"]) + _seconds(health["timeout"]))
        except (ValueError, KeyError) as e:
            return None, f"service {name}: health unreadable ({type(e).__name__}: {e})"
        seed = None
        if svc.get("seed") is not None:
            seed, why = read_seed(svc["seed"], read_base)
            if why or seed["api_key_env"] not in env:
                return None, f"service {name}: {why or 'seed api_key_env is not in the service env'}"
        reached = svc.get("reached")
        if reached is not None and (not isinstance(reached, dict) or set(reached) != REACHED_KEYS
                                    or not re.fullmatch(r"(GET|PUT|POST) /[A-Za-z0-9/_-]*", str(reached["request"]))
                                    or type(reached["min"]) is not int or reached["min"] < 1 or str(reached["api_key_env"]) not in env):
            return None, f"service {name}: reached needs exactly {sorted(REACHED_KEYS)}: a plain `GET /path`, a count >= 1, a key env of the service"
        iid = (_try([docker, "image", "inspect", "--format", "{{.Id}}", ref]) or "").strip()
        if not iid.startswith("sha256:"):
            return None, f"service {name}: image {ref} is not present locally (docker pull it, then plan again)"
        taken = taken | {name}
        out.append({"name": name, "image": ref, "local_image": ref, "image_id": iid, "env": env, "ports": [], "health": health,
                    "health_budget_s": budget + 60, **({"seed": seed} if seed else {}),
                    **({"reached": {k: reached[k] for k in sorted(REACHED_KEYS)}} if reached else {})})
    return out, None


def matrix_legs(job: dict) -> tuple[list | None, str | None]:
    m = (job.get("strategy") or {}).get("matrix")
    if m is None:
        return [{}], None
    if isinstance(m, dict) and list(m) == ["include"] and isinstance(m["include"], list) and m["include"] \
            and all(isinstance(x, dict) and x for x in m["include"]):
        return [dict(x) for x in m["include"]], None   # include alone: each entry is one job, as hosted expands it
    if not isinstance(m, dict) or any(k in m for k in ("include", "exclude")) or any(not isinstance(v, list) or not v for v in m.values()):
        return None, "strategy.matrix with include/exclude beside axes, or non-list axes, is not emulated"
    legs = [{}]
    for k, vals in m.items():
        legs = [{**leg, k: v} for leg in legs for v in vals]
    return legs, None


def _pin_lines(blob: bytes) -> tuple[list, list]:
    keep, dropped = [], []
    for ln in blob.decode(errors="replace").splitlines():
        t = ln.strip()
        if not t or t.startswith("#") or re.fullmatch(r"--hash=sha256:[0-9a-f]{64}\s*\\?", t):
            continue
        (keep if REQ_PIN.match(t) and not re.search(r"\s-", t) else dropped).append(t.rstrip("\\").strip())
    return keep, dropped


def deps_recipe(wt: Path, cand: str, iso: dict, deps: dict, prefix: str) -> tuple[dict | None, str]:
    """The pure part of `plan_deps_image`: (info, "") or (None, why). `info` holds the recipe, its digest (the image tag is
    `localci-deps:{digest[:16]}`), the Dockerfile text and the inputs the build needs. It reads the tree at `cand` as data and calls
    no docker; B22's prune recomputes main's tag with it."""
    reqs, dropped = [], []
    for rel in deps.get("requirements") or []:
        blob = _extract_base_file(wt, cand, safe_tree_path(str(rel)))   # the CANDIDATE's requirement file, read as data
        if blob is None:
            return None, f"deps: {rel} absent from the candidate"
        k, d = _pin_lines(blob)
        reqs, dropped = reqs + k, dropped + d
    pkgs = sorted(str(p) for p in deps.get("packages") or [])
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", p) for p in pkgs):
        return None, "deps.packages must be bare distribution names"
    fetch = [{"url": str(f.get("url")), "sha256": str(f.get("sha256")), "path": str(f.get("path")), "install": f.get("install") is True}
             for f in deps.get("fetch") or []]
    if any(not f["url"].startswith("https://") or not re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) or not f["path"].startswith("/")
           or ".." in f["path"].split("/") or f["path"].startswith("/w/") for f in fetch):
        return None, "deps.fetch entries need an https url, a sha256 pin and an absolute path outside the tree"
    cq, cq_why = codeql_pin(deps.get("codeql"))
    if cq_why:
        return None, cq_why
    py = f"{prefix.rstrip('/')}/python3" if prefix else "python3"
    node = str(deps.get("node") or "")
    if node and not node.isdigit():
        return None, "deps.node must be a major version"
    npm_files, pw, why = {}, "", None
    for lock in [deps["npm"]] if isinstance(deps.get("npm"), str) else deps.get("npm") or []:
        files, pw1, why = npm_inputs(wt, cand, {"npm": lock})
        if why:
            break
        pre = lock.rsplit("/", 1)[0] + "/" if "/" in lock else ""
        npm_files.update({pre + k: v for k, v in files.items()})
        pw = pw or pw1
    apt = sorted(str(a) for a in deps.get("apt") or [])
    browser = str(deps.get("playwright") or "")
    if why or ((deps.get("npm") or browser) and not node) or any(not re.fullmatch(r"[a-z0-9][a-z0-9.+-]*", a) for a in apt) \
            or browser not in ("", "chromium", "firefox", "webkit") or (browser and not pw):
        return None, f"deps: {why or 'npm/playwright need deps.node and an npm lock naming playwright-core; apt names are package names'}"
    dockerfile = (DEPS_DOCKERFILE if reqs or pkgs or fetch else DEPS_BARE) + (DEPS_NODE.format(v=node) if node else "")
    if npm_files:
        dockerfile = dockerfile.replace("\nFROM ${BASE}\n", "\n" + DEPS_NPM_STAGE.format(v=node) + "FROM ${BASE}\n", 1)
    if cq:
        dockerfile = dockerfile.replace("\nFROM ${BASE}\n", "\n" + DEPS_CODEQL_STAGE.format(**cq) + "FROM ${BASE}\n", 1)
    dockerfile += (DEPS_APT.format(pkgs=" ".join(apt)) if apt else "") + (DEPS_PLAYWRIGHT.format(pw=pw, browser=browser) if browser else "") \
        + (DEPS_NPM + DEPS_OFFLINE_NPM if npm_files else "") + (DEPS_CODEQL.format(version=cq["version"]) if cq else "")
    recipe = {"base": iso["image_id"], "python": py, "requirements": sorted(set(reqs)), "packages": pkgs, "fetch": fetch, "node": node,
              "dockerfile": sha256_bytes((dockerfile + DEPS_FETCH_PY).encode())}
    if npm_files or apt or browser:   # absent keys keep a recipe built before them (and its image) as it was
        recipe.update(npm={k: sha256_bytes(v) for k, v in sorted(npm_files.items())}, playwright=[browser, pw], apt=apt)
    if cq:   # the pin is part of the recipe: a bump is a new digest, hence a new image, and the prune keeps the newest per recipe as it does
        recipe["codeql"] = cq
    digest = sha256_json(recipe)
    return {"recipe": recipe, "digest": digest, "dockerfile": dockerfile, "reqs": reqs, "pkgs": pkgs, "fetch": fetch, "npm_files": npm_files,
            "py": py, "dropped": dropped}, ""


def plan_deps_image(wt: Path, cand: str, iso: dict, deps: dict, prefix: str, run_dir: Path, slug: str) -> tuple[str | None, str]:
    """(image id, note) or (None, why). Cached by recipe digest: the same lock on the same candidate image reuses its image."""
    info, why = deps_recipe(wt, cand, iso, deps, prefix)
    if info is None:
        return None, why
    recipe, digest, dockerfile, pkgs, fetch, npm_files, py, dropped = (info[k] for k in ("recipe", "digest", "dockerfile", "pkgs", "fetch", "npm_files", "py", "dropped"))
    tag, docker = f"localci-deps:{digest[:16]}", iso["docker"]
    note = f"deps {tag} ({len(recipe['requirements'])} pins + {pkgs}, {len(fetch)} fetched file(s)); not reaching the network stage: {dropped}"
    have = (_try([docker, "image", "inspect", "--format", "{{.Id}} {{index .Config.Labels \"" + DEPS_LABEL + "\"}}", tag]) or "").split()
    if have[1:] != [digest]:
        ctxd = run_dir / "state" / "deps" / slug
        ctxd.mkdir(parents=True, exist_ok=True)
        (ctxd / "req.txt").write_text("\n".join(recipe["requirements"]) + "\n")
        (ctxd / "pkgs.txt").write_text(" ".join(pkgs) + "\n")
        (ctxd / "fetch.json").write_text(json.dumps(fetch))
        (ctxd / "install.txt").write_text("".join(f"{f['path']}\n" for f in fetch if f["install"]))
        (ctxd / "fetch.py").write_text(DEPS_FETCH_PY)
        (ctxd / "Dockerfile").write_text(dockerfile)
        for rel, blob in npm_files.items():
            (ctxd / "npm" / rel).parent.mkdir(parents=True, exist_ok=True)
            (ctxd / "npm" / rel).write_bytes(blob)
        base_tag = f"localci-deps-base:{iso['image_id'].split(':')[-1][:16]}"
        denv = trusted_env()
        with open(run_dir / "logs" / f"deps-{slug}.log", "w") as fh:
            ok = subprocess.run([docker, "tag", iso["image_id"], base_tag], stdout=fh, stderr=subprocess.STDOUT, env=denv, timeout=60).returncode == 0
            try:
                ok = ok and subprocess.run([docker, "build", "--progress=plain", "--label", f"{DEPS_LABEL}={digest}",
                                            "--label", f"{DEPS_RECIPE_LABEL}={slug}", "--build-arg", f"BASE={base_tag}",   # the prune's recipe (B6)
                                            "--build-arg", f"PY={py}", "-t", tag, str(ctxd)], stdout=fh, stderr=subprocess.STDOUT, env=denv,
                                           timeout=DEPS_BUILD_TIMEOUT_S).returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
        if not ok:
            return None, f"deps image build failed (logs/deps-{slug}.log): the job's install closure is not available offline"
        have = (_try([docker, "image", "inspect", "--format", "{{.Id}} {{index .Config.Labels \"" + DEPS_LABEL + "\"}}", tag]) or "").split()
    layers = lambda ref: (_try([docker, "image", "inspect", "--format", "{{json .RootFS.Layers}}", ref]) or "null")   # noqa: E731
    base_l, deps_l = json.loads(layers(iso["image_id"])) or [], json.loads(layers(have[0] if have else tag)) or []
    if have[1:] != [digest] or not base_l or deps_l[:len(base_l)] != base_l:
        return None, f"deps image {tag} is not built on the pinned candidate image {iso['image_id'][:19]} (label or layer chain differs)"
    return have[0], note


MERGE_GROUP_EVENT_KEYS = {"merge_group", "repository", "organization", "installation", "sender", "enterprise"}   # `action` is modelled


REBUILT_IDS = {("github", "sha"), ("github", "event", "merge_group", "base_sha"), ("github", "event", "merge_group", "head_sha")}
QUEUE_REF = {("github", "ref"), ("github", "event", "merge_group", "head_ref")}   # the queue's ref names the PR: pr-<N>-<base>
ENV_EVALUATED_HERE = "which the workflow declares: the runner evaluates that text itself, where env is empty, so it would read '' silently"


def path_read(texts, wanted: set) -> str | None:
    """The first context path `texts` read that is one of `wanted`, or an object that holds one (`${{ github.event.merge_group }}`).
    What does not parse is refused where that text is evaluated."""
    X = _gh_expr()
    for t in texts:
        try:
            found = X.paths(str(t or ""))
        except X.ExprError:
            continue
        for path in found:
            if any(ids[:len(path)] == tuple(str(p).lower() for p in path) for ids in wanted):
                return ".".join(path)
    return None


def rebuilt_id(texts) -> str | None:
    """The first commit id the sandbox rebuilds that `texts` reads: only the driver knows those ids, once it has built the commits, so a text
    the runner evaluates itself (an artifact name or path, a host or egress step) cannot read them (Codex, B1 delta review)."""
    return path_read(texts, REBUILT_IDS)


def declared_env_read(texts, declared) -> str | None:
    """The first `env.X` that `texts` read where X is an env the workflow declares in that scope (or the whole `env` object, when it
    declares any). A text the runner evaluates itself (an artifact name or path, a host reader's argv, a checkout ref) holds no env, so
    that read would be '' where hosted reads the declared value; an undeclared X is null hosted too."""
    X, names = _gh_expr(), {str(d).lower() for d in declared}
    for t in texts:
        try:
            found = X.paths(str(t or ""))
        except X.ExprError:
            continue
        for path in found:
            if path[0].lower() == "env" and (path[1].lower() in names if len(path) > 1 else bool(names)):
                return ".".join(path)
    return None


def unmodelled_path(path: list, gh: dict, needs: list, stood_in: dict) -> str | None:
    """Why a path the BASE job reads holds a value hosted that this run does not (refused), or None. `steps`, `env`, `matrix` and
    `vars` are the run's own (vars as the matrix declares them); a key absent from a merge_group event is null hosted as here."""
    low = [p.lower() for p in path]
    root, k1 = low[0], (low[1] if len(low) > 1 else None)
    if root == "github":
        if k1 != "event":
            return None if k1 in {k.lower() for k in gh} else "is a github property this run does not model"
        if len(low) > 2 and low[2] == "merge_group":
            return None if len(low) == 3 or low[3] in gh["event"]["merge_group"] else "is a merge_group field this run does not model"
        return "is part of the merge_group payload this run does not model" if len(low) > 2 and low[2] in MERGE_GROUP_EVENT_KEYS else None
    if root == "runner":
        return None if k1 in RUNNER_CTX else "is a runner property this run does not model"
    if root == "job":
        return None if low[1:] == ["status"] else "is a job property this run does not model (only job.status is)"
    if root == "strategy":
        return "strategy is not modelled"
    if root == "needs" and k1 is not None:
        if k1 not in [n.lower() for n in needs]:
            return None
        rest, si = low[2:], next((v for k, v in stood_in.items() if k.lower() == k1), None)
        if rest[:1] == ["result"] or not rest:
            return None
        if rest[:1] == ["outputs"] and si is not None and (len(rest) == 1 or rest[1] in {k.lower() for k in si.get("outputs") or {}}):
            return None
        return "is an upstream output this run does not carry"
    return None


def npm_inputs(wt: Path, cand: str, deps: dict) -> tuple[dict, str, str | None]:
    """The candidate's npm lock and the manifests it installs (root + each workspace), read as data -> (files, playwright-core
    version, why-not). A lock entry that resolves anywhere but the public registry (a tarball URL, git, a file path that is not a
    declared workspace) is refused: the networked stage fetches only what the registry serves under the lock's integrity."""
    lock_rel = safe_tree_path(str(deps["npm"]))
    root = lock_rel.rsplit("/", 1)[0] + "/" if "/" in lock_rel else ""
    files: dict = {}
    for rel in (lock_rel, f"{root}package.json"):
        if (blob := _extract_base_file(wt, cand, rel)) is None:
            return {}, "", f"{rel} absent from the candidate"
        files[rel[len(root):]] = blob
    try:
        lock, manifest = json.loads(files["package-lock.json"]), json.loads(files["package.json"])
    except (KeyError, ValueError) as e:
        return {}, "", f"npm lock/manifest unreadable: {type(e).__name__}"
    ws = manifest.get("workspaces") or []
    ws = ws.get("packages") or [] if isinstance(ws, dict) else ws
    if any(not isinstance(w, str) or any(c in w for c in "*?[") for w in ws):
        return {}, "", "npm workspaces must be plain paths (no globs)"
    for w in ws:
        rel = f"{root}{safe_tree_path(w.rstrip('/'))}/package.json"
        if (blob := _extract_base_file(wt, cand, rel)) is None:
            return {}, "", f"workspace manifest {rel} absent from the candidate"
        files[rel[len(root):]] = blob
    pkgs = lock.get("packages") if isinstance(lock.get("packages"), dict) else None
    if pkgs is None:
        return {}, "", "npm lock has no `packages` map (lockfileVersion >= 2 required)"
    for key, ent in pkgs.items():
        res = ent.get("resolved") if isinstance(ent, dict) else None
        if res is None:
            continue
        if ent.get("link") is True and res.rstrip("/") in [w.rstrip("/") for w in ws]:
            continue
        if re.fullmatch(r"git\+(?:ssh://git@|https://)github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git#[0-9a-f]{40}", str(res)):
            continue   # pinned to a full commit id: npm fetches github's https tarball of that commit (no git, no credentials)
        if not (str(res).startswith("https://registry.npmjs.org/") and str(ent.get("integrity", "")).startswith("sha512-")):
            return {}, "", (f"npm lock entry {key!r} resolves to {str(res)[:80]!r}: only the public registry with an integrity, "
                            "or a github repository at a full commit id, is fetched")
    pw = str((pkgs.get("node_modules/playwright-core") or {}).get("version") or "")
    return files, pw if re.fullmatch(r"\d+\.\d+\.\d+", pw) else "", None


READER_RETRY_WAITS = (0, 10, 30)


def run_host_reader(argv: list, cwd: Path, timeout: int | None, no_verdict: str | None = None, pending: str | None = None) -> dict:
    """A BASE reader of GitHub state (the harness gate verdict) at plan time, before any candidate code: python -I on the BASE copy,
    secrets stripped from its environment (gh answers with its stored login, a read). Its rc is frozen into the plan, so the seal
    covers it, and the driver folds it in at the step's position, where the step's own `if:` decides whether it counts."""
    for wait in READER_RETRY_WAITS:   # a reader that says it could not read GitHub (`no_verdict`, the matrix's) is asked again, then no verdict
        time.sleep(wait)
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout or 300, env=trusted_env(), cwd=str(cwd))
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"rc": None, "reason": f"host reader could not run: {type(e).__name__}"}
        out = r.stdout + r.stderr   # the reader's own error line, on stderr, line-anchored: a description it echoes (stdout) cannot fake it
        if pending and r.returncode != 0 and any(ln.startswith(pending) for ln in r.stderr.splitlines()):   # B12: not posted yet, and a posting session takes minutes: no retry
            return {"rc": None, "reason": f"gate_pending: host, at plan: BASE {Path(argv[2]).name} — no harness/fable-gate verdict posted on the head yet; "
                    "asked again once it is", "log": out[-4000:], "gate_pending": True}   # the flag, frozen in the plan, marks the context: never the text
        if not (no_verdict and r.returncode != 0 and any(ln.startswith(no_verdict) for ln in r.stderr.splitlines())):
            return {"rc": r.returncode, "reason": f"host, at plan: BASE {Path(argv[2]).name} rc={r.returncode}", "log": out[-4000:]}
    return {"rc": None, "reason": f"host, at plan: BASE {Path(argv[2]).name} could not read GitHub ({no_verdict!r}, {len(READER_RETRY_WAITS)} tries): "
            "no verdict on the candidate, re-run", "log": out[-4000:]}


def classifier_needs(trusted: Path, cm: dict, changed: list, spec) -> tuple[dict | None, str | None]:
    """`needs.<job>` as the hosted `changes` job hands it to a job that reads its flags: the BASE classifier (already extracted to `trusted/`)
    run on the plan's changed files and the trusted change map, the way the hosted step runs it. (needs, note), or (None, why) when the
    matrix names a classifier the plan did not take from BASE. A classifier that fails, or answers an output the matrix declared
    with anything but true/false, is hosted's fail-open: the job's result is not `success` and every output reads true, so the leg runs."""
    job = str(spec.get("job") or "") if isinstance(spec, dict) else ""
    script = str(spec.get("script") or "") if isinstance(spec, dict) else ""
    names = [str(n) for n in spec.get("outputs") or []] if isinstance(spec, dict) else []
    if not job or not names or script not in TRUSTED_CLASSIFIER_FILES or not (trusted / Path(script).name).is_file():
        return None, f"local.classifier must name a job, its outputs and a BASE classifier file of {TRUSTED_CLASSIFIER_FILES}"
    try:
        r = subprocess.run([sys.executable, "-I", str(trusted / Path(script).name)], input="\n".join(changed) + "\n", capture_output=True, text=True,
                           timeout=60, env={**trusted_env(), "MAP_JSON": json.dumps(cm)})
        got = dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)
        err = None if r.returncode == 0 and all(got.get(n) in ("true", "false") for n in names) else f"rc={r.returncode}, outputs {sorted(got)}"
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        got, err = {}, type(e).__name__
    if err:
        return {"result": "failure", "outputs": {n: "true" for n in names}}, f"BASE {Path(script).name} gave no flags ({err}): fail-open, the job runs"
    return {"result": "success", "outputs": {n: got[n] for n in names}}, f"BASE {Path(script).name}: " + " ".join(f"{n}={got[n]}" for n in names)


RING_OVERRIDE_VAR, RING_OVERRIDE_SH = "MERGEOS_RING_GATING_DISABLED", "scripts/ci/ring_gating_override.sh"


def _gh_variables(env: dict, path: str, get=None) -> list | None:
    """Every variable a `gh api` list endpoint holds (per_page=100, paged), or None when the read cannot be trusted: any non-200 status (gh
    exits non-zero on it, a 404 included: a list that is missing is a read that failed, not an empty one), a body that is not JSON, one
    without a `variables` array of objects and an integer `total_count`, or a count that disagrees with the rows collected."""
    rows, total = [], None
    for page in range(1, 51):
        q = f"{path}?per_page=100&page={page}"
        r = (subprocess.CompletedProcess([], 0, json.dumps(get(q)), "") if get is not None
             else subprocess.run(["gh", "api", q], capture_output=True, text=True, timeout=60, env=env))
        if r.returncode != 0:
            return None
        body = json.loads(r.stdout)
        got = body.get("variables") if isinstance(body, dict) else None
        count = body.get("total_count") if isinstance(body, dict) else None
        if not isinstance(got, list) or not all(isinstance(v, dict) for v in got) or type(count) is not int or total not in (None, count):
            return None
        rows, total = rows + got, count
        if len(rows) >= total or not got:
            return rows if len(rows) == total else None
    return None


def ring_gating_override(wt: Path, base: str, trusted: Path, repo: str, jobs: dict | None = None, get=None) -> dict:
    """The manual override security.yml's `changes` job honours (`vars.MERGEOS_RING_GATING_DISABLED`), read now with the operator's gh and
    judged by BASE's own truth table (scripts/ci/ring_gating_override.sh, run, not re-implemented). Hosted resolves `vars.X` as a repository
    variable first, then an organization variable visible to the repository (an environment variable too, when the job names an
    `environment:`): the repository list is read, then the organization list when the repository's owner is an Organization. {read: ok|error,
    active: bool}: a name in neither list is ok and inactive; a read, a BASE file or a truth-table answer that cannot be had, and a BASE job
    that names an `environment:` (its variables are invisible to this read), are `error` and ACTIVE, the same fail-open as a classifier
    error, so a doubt can only run more, never less."""
    fail = {"read": "error", "active": True}
    blob = _extract_base_file(wt, base, RING_OVERRIDE_SH)
    if blob is None or any(isinstance(j, dict) and "environment" in j for j in (jobs or {}).values()):
        return fail
    if getattr(get, "__name__", None) == "gh_get":
        get = None
    env = trusted_env()
    try:
        owner = (subprocess.CompletedProcess([], 0, json.dumps(get(f"repos/{repo}")), "") if get is not None
                 else subprocess.run(["gh", "api", f"repos/{repo}"], capture_output=True, text=True, timeout=60, env=env))
        owner_type = (json.loads(owner.stdout).get("owner") or {}).get("type") if owner.returncode == 0 else None
        if owner_type not in ("Organization", "User"):
            return fail
        value = None
        for path in (f"repos/{repo}/actions/variables", *((f"repos/{repo}/actions/organization-variables",) if owner_type == "Organization" else ())):
            rows = _gh_variables(env, path, get=get)
            if rows is None:
                return fail
            hit = [v for v in rows if str(v.get("name", "")).upper() == RING_OVERRIDE_VAR]   # variable names are case-insensitive
            if hit:
                value = hit[0].get("value")
                if len(hit) != 1 or not isinstance(value, str):
                    return fail
                break   # the repository variable wins over the organization's
        script = trusted / "ctx" / Path(RING_OVERRIDE_SH).name
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_bytes(blob)
        out = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=30,
                             env={**env, **({RING_OVERRIDE_VAR: value} if value is not None else {})})
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return fail
    answer = out.stdout.strip()
    if out.returncode != 0 or answer not in ("active=true", "active=false"):
        return fail
    return {"read": "ok", "active": answer == "active=true"}


def version_sentinel(trusted: Path, wt: Path, base: str, check: str, spec, language: str, pin: str, repo: str) -> str | None:
    """None when the newest hosted analysis of `language` on main reports the pinned CLI, else why there is no verdict (BLOCKED, never
    green): another version, no such analysis, or a read that failed. BASE's reader runs on the host at plan time with the operator's gh,
    through the same host-reader path as the harness floor's (retried on its CANNOT-VERIFY line, then no verdict)."""
    rel = str(spec.get("reader") or "") if isinstance(spec, dict) else ""
    try:
        rel = safe_tree_path(rel)
    except RuntimeError:
        rel = ""
    blob = _extract_base_file(wt, base, rel) if rel else None
    if blob is None:
        return f"version sentinel: reader {spec.get('reader') if isinstance(spec, dict) else spec!r} is not a file at BASE {base[:12]}"
    dest = trusted / "ctx" / check / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    got = run_host_reader([sys.executable, "-I", str(dest), "--repo", repo, "--language", language, "--pin", pin], dest.parent, 300,
                          no_verdict="::error::codeql_version_read: CANNOT-VERIFY")
    if got["rc"] == 0:
        return None
    return f"version sentinel: {got['reason']}: {(got.get('log') or '').strip()[-300:]}"


def _squashed(d) -> dict:
    return {str(k): " ".join(str(v).split()) for k, v in (d or {}).items()}


PIN_REF = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def candidate_pin_follow(wt: Path, base: str, cand: str, wf: str, local: dict, ctx_job: str | None) -> str | None:
    """The plan reads BASE's workflow and matrix, so a bump merged without its matrix pin leaves main with a workflow the matrix does not
    follow and every later PR BLOCKED, the fix included (it is judged by that BASE matrix). Here the candidate's own workflow and matrix are read
    as data: for every step BASE's matrix pins, the candidate's matrix must still pin it and agree with the candidate's workflow, and a pin the
    candidate changes must be an immutable `<action>@<40 hex>`. Nothing of the candidate runs; the plan stays BASE's. None when they agree, when
    BASE pins nothing, or when neither file differs from BASE; else the reason."""
    mrel = "scripts/localci/contexts_matrix.yaml"
    base_pins = {(jl.get("job_id"), ms.get("workflow_step")): ms for jl in [*(local.get("jobs") or []), {**local, "job_id": ctx_job}]
                 for ms in jl.get("steps") or [] if isinstance(ms.get("uses_pin"), str) or isinstance(ms.get("with_pin"), dict)}
    blobs = {r: (_extract_base_file(wt, base, r), _extract_base_file(wt, cand, r)) for r in (wf, mrel)}
    if not base_pins or all(a == b for a, b in blobs.values()):
        return None
    try:
        import yaml

        wdoc, mdoc = (yaml.safe_load(blobs[r][1] or b"") for r in (wf, mrel))
        cl = next(c["local"] for c in mdoc["contexts"] if (c.get("local") or {}).get("check") == local.get("check"))
        cms = {(jl.get("job_id"), ms.get("workflow_step")): ms for jl in [*(cl.get("jobs") or []), {**cl, "job_id": ctx_job}] for ms in jl.get("steps") or []}
        for (jid, step), bms in base_pins.items():
            ms, lab = cms.get((jid, step)) or {}, f"job {jid}: step {step!r}"
            ws = next((x for x in ((wdoc["jobs"].get(jid) or {}).get("steps") or []) if isinstance(x, dict) and x.get("name") == step), {})
            if isinstance(bms.get("uses_pin"), str):
                if not isinstance(ms.get("uses_pin"), str):
                    return f"{lab}: the candidate matrix no longer pins the action"
                if ws.get("uses") != ms["uses_pin"]:
                    return f"{lab}: the candidate workflow uses {ws.get('uses')!r} but the candidate matrix transcribes {ms['uses_pin']!r} — a bump carries its matrix pin"
                if ms["uses_pin"] != bms["uses_pin"] and not PIN_REF.match(ms["uses_pin"]):
                    return f"{lab}: the candidate's new pin {ms['uses_pin']!r} is not an immutable <action>@<40 hex sha> ref"
            if isinstance(bms.get("with_pin"), dict):
                if not isinstance(ms.get("with_pin"), dict):
                    return f"{lab}: the candidate matrix no longer pins the action inputs"
                if _squashed(ws.get("with")) != _squashed(ms["with_pin"]):
                    return f"{lab}: the candidate workflow's inputs differ from the candidate matrix's with_pin — a changed input carries its matrix pin"
    except Exception as e:  # noqa: BLE001
        return f"candidate workflow/matrix unreadable as data ({type(e).__name__}): its pins cannot be compared"
    return None


def plan_service_context(wt: Path, base: str, cand: str, trusted: Path, name: str, ctx: dict, changed: list, pyv: dict, iso: dict, cm: dict,
                         run_dir: Path, pr_number: int | None, trusted_sha: dict | None = None,
                         gate_ledger: Path | str | None = DEFAULT_GATE_LEDGER, head_sha: str | None = None) -> dict:
    """A required context whose job `needs:` other jobs, runs beside `services:`, installs a lock, or decides steps with expressions:
    every job of the chain is planned from BASE, each matrix leg runs in its own fresh sandbox with its own services, and the context's
    own job sees its upstreams' artifacts and results. Anything the runner cannot reproduce is BLOCKED naming why."""
    local, wf = ctx["local"], str(ctx.get("workflow_file"))
    flag = local.get("runs_when")
    if flag and change_map_status(cm) == "PASS" and not cm.get("run_all") and flag not in (cm.get("suggested_jobs") or []):
        return {"kind": "record", "status": "NOT_APPLICABLE", "skipped": "change_map",   # a skip, compared as one (B5), never an execution
                "reason": f"trusted change_map does not select {flag} (suggested={cm.get('suggested_jobs')}): "
                "the hosted job skips, and a skipped required context is satisfied"}
    if local.get("where") != "container" or iso.get("mode") != "container" or iso.get("error"):
        return _blocked(f"a service context runs only under --isolation container ({iso.get('error') or iso.get('mode')})")
    X = _gh_expr()
    try:
        import yaml

        doc = yaml.safe_load(_extract_base_file(wt, base, wf) or b"")
        jobs_doc = doc["jobs"]
    except Exception as e:  # noqa: BLE001
        return _blocked(f"BASE workflow {wf} unreadable at {base[:12]}: {type(e).__name__}")
    repo = str(local.get("repository") or "Bali-Zero/Teman2")
    gh = github_ctx(base, pr_number, repo)
    static = {"github": gh, "vars": dict(local.get("vars") or {}), "runner": RUNNER_CTX, "matrix": {}, "needs": {}, "env": {}, "steps": {}}
    stood_in, flags_note, ov, classifier_off = dict(local.get("needs") or {}), None, None, False
    if local.get("classifier"):   # a job whose `needs:` outputs the BASE classifier decides (CodeQL's per-language flags), not the matrix
        got, flags_note = classifier_needs(trusted, cm, changed, local["classifier"])
        if got is None:
            return _blocked(flags_note)
        holders = {j: jobs_doc.get(j) for j in (local["classifier"]["job"], ctx.get("job_id"))}   # the `changes` job holds the override step; the leg's job reads its flags
        ov = ring_gating_override(wt, base, trusted, repo, holders)   # hosted's classify steps are skipped when it is active: every flag defaults true
        if ov["active"]:
            got = {"result": "success" if ov["read"] == "ok" else "failure", "outputs": {n: "true" for n in got["outputs"]}}
            flags_note = f"{flags_note}; ring-gating override " + ("ACTIVE (vars.MERGEOS_RING_GATING_DISABLED=true): both flags true" if ov["read"] == "ok"
                                                                  else "unreadable: fail-open, both flags true")
        stood_in[str(local["classifier"]["job"])] = got
        classifier_off = got["result"] == "success" and all(v == "false" for v in (got.get("outputs") or {}).values())
    if (why := candidate_pin_follow(wt, base, cand, wf, local, ctx.get("job_id"))):
        return _blocked(why)
    upstream, planned = set(stood_in), []
    for jl in [*(local.get("jobs") or []), {**local, "job_id": ctx.get("job_id")}]:
        jid, job = jl.get("job_id"), jobs_doc.get(jl.get("job_id"))
        if not isinstance(job, dict):
            return _blocked(f"job {jid!r} absent from BASE {wf}")
        needs = job.get("needs") or []
        needs = [needs] if isinstance(needs, str) else list(needs)
        if (unknown := [n for n in needs if n not in upstream]):
            return _blocked(f"job {jid}: needs {unknown}, neither run here nor declared in local.needs")
        jenv = {str(k): str(v) for k, v in {**(doc.get("env") or {}), **(job.get("env") or {}), **(jl.get("env") or {})}.items()}
        steps, why = resolve_steps({**job, "env": jenv}, jl, "main", ((doc.get("defaults") or {}).get("run")) or {}, expressions=True)
        if why:
            return _blocked(f"job {jid}: {why}")
        for ms in jl.get("steps") or []:   # an action step the matrix transcribes as a command: its inputs, and the action itself, are part of what was transcribed
            ws = next((x for x in job.get("steps") or [] if isinstance(x, dict) and x.get("name") == ms.get("workflow_step")), {})
            if isinstance(ms.get("uses_pin"), str) and ws.get("uses") != ms["uses_pin"]:
                return _blocked(f"job {jid}: step {ms.get('workflow_step')!r} uses {ws.get('uses')!r}, not the action {ms['uses_pin']!r} the matrix transcribed "
                                "— an action bump is not emulated until the matrix follows it")
            if isinstance(ms.get("with_pin"), dict):
                have = {str(k): " ".join(str(v).split()) for k, v in (ws.get("with") or {}).items()}
                if have != {str(k): " ".join(str(v).split()) for k, v in ms["with_pin"].items()}:
                    return _blocked(f"job {jid}: step {ms.get('workflow_step')!r} inputs {have} are not the ones the matrix transcribed "
                                    f"{ms['with_pin']} — a changed action input is not emulated until the matrix follows it")
        order = [s.get("name") for s in job.get("steps") or [] if isinstance(s, dict)]
        if [st["name"] for st in steps] != [n for n in order if n in {st["name"] for st in steps}]:
            return _blocked(f"job {jid}: the matrix lists its steps out of BASE order; outputs and job status flow in that order")
        prefix, why = select_python(job, pyv.get("container"), pyv.get("container_extra"))
        legs, why2 = matrix_legs(job)
        if legs and (want := jl.get("leg")) is not None:   # a required context that is one leg's check run: "Frontend Tests (Next.js) (mouth, true)"
            legs = [g for g in legs if set(g) == set(want) and all(type(g[k]) is type(v) and g[k] == v for k, v in want.items())]   # 1 is not true
            shown = "(" + ", ".join(str(v).lower() if isinstance(v, bool) else str(v) for v in legs[0].values()) + ")" if len(legs) == 1 else None
            why2 = why2 or (None if shown and jid == ctx.get("job_id") and name.endswith(shown) else
                            f"leg {want!r} is not exactly one leg of the context's own job, the one whose check run is {name!r}")
        svcs, why3 = plan_services(job, local.get("service_images") or {}, iso["docker"])
        if svcs is not None:
            extra_svcs, why3 = plan_extra_services(jl.get("extra_services"), {s["name"] for s in svcs}, iso["docker"],
                                                          lambda rel: _extract_base_file(wt, base, safe_tree_path(rel)))
            svcs = svcs + extra_svcs if extra_svcs is not None else None
        if why or why2 or why3:
            return _blocked(f"job {jid}: {why or why2 or why3}")
        nodes = {str((s.get("with") or {}).get("node-version", "")) for s in job.get("steps") or [] if str(s.get("uses", "")).startswith("actions/setup-node@")}
        if nodes and nodes != {str((local.get("deps") or {}).get("node") or "")}:
            return _blocked(f"job {jid}: setup-node pins {sorted(nodes)}, the deps image carries node {(local.get('deps') or {}).get('node')!r}")
        checkout = None
        for s in job.get("steps") or []:
            w = (s.get("with") or {}) if str(s.get("uses", "")).startswith("actions/checkout@") else {}
            if set(w) - {"fetch-depth", "ref", "filter"}:
                return _blocked(f"job {jid}: checkout with {sorted(set(w) - {'fetch-depth', 'ref', 'filter'})} is not emulated")
            if "ref" in w:
                if (q := declared_env_read([w["ref"]], {*jenv, *(s.get("env") or {})})):
                    return _blocked(f"job {jid}: checkout ref reads `{q}`, {ENV_EVALUATED_HERE}")
                try:
                    if X.substitute(str(w["ref"]), static) != "main":
                        return _blocked(f"job {jid}: checkout ref {w['ref']!r} is neither the candidate nor its BASE")
                except X.ExprError as e:
                    return _blocked(f"job {jid}: checkout ref: {e}")
                checkout = "base"
        try:   # each text carries where it sits, so a refusal names the step and the variable (a name, never a value)
            texts = [*((f"job env {k}", str(v)) for k, v in jenv.items()),
                     *((f"step {s.get('name') or s.get('uses')!r} with.ref", str((s.get("with") or {}).get("ref", ""))) for s in job.get("steps") or [])]
            base_env = {s["name"]: s.get("env") or {} for s in job.get("steps") or [] if isinstance(s, dict) and isinstance(s.get("name"), str)}
            for st in steps:
                lab = f"step {st['name']!r}"
                if st.get("script") and re.search(r"GITHUB_(ENV|PATH|STATE)\b", st["script"]):
                    raise X.ExprError(f"{lab} writes GITHUB_ENV/PATH/STATE, which the driver does not read back")
                texts += [(f"{lab} run body", str(st.get("script") or "")), *((f"{lab} env {k}", str(v)) for k, v in (st.get("env") or {}).items()),
                          *((f"{lab} with.{k}", str(v or "")) for k, v in (st.get("emulate") or {}).items())]
                texts += [(f"{lab} if", "${{ " + X.unwrap(str(st["if"])) + " }}")] if "if" in st else []
                if any(Path(str(a)).name == LEG_SCRIPT for a in st.get("argv") or []) and (seam := sorted(LEG_INPUT_ENV & {*jenv, *(st.get("env") or {})})):
                    raise X.ExprError(f"{lab} runs {LEG_SCRIPT} with {seam} in its composed env: those are the leg's own test seams, and a BASE workflow or "
                                      "matrix that sets them would point the BASE-trusted commands at another CLI, tree or config")
                if st.get("emulate") and (q := declared_env_read(st["emulate"].values(), {*jenv, *base_env.get(st["name"], {})})):
                    raise X.ExprError(f"{lab} artifact name or path reads `{q}`, {ENV_EVALUATED_HERE}")
            for lab, t in texts:
                try:
                    found = X.paths(t)
                except X.ExprError as e:
                    raise X.ExprError(f"{lab}: {e}") from None
                for path in found:
                    if (why := unmodelled_path(path, gh, needs, stood_in)):
                        raise X.ExprError(f"{lab}: `{'.'.join(path)}` {why}")
            if pr_number is None:   # hosted, the queue's ref is refs/heads/gh-readonly-queue/main/pr-<N>-<base>; here '' or made up
                for lab, t in [*texts, *((f"step {st['name']!r} argv", str(a)) for st in steps for a in st.get("argv") or [])]:
                    if (q := path_read([t], QUEUE_REF)):
                        raise X.ExprError(f"{lab} reads `{q}`, the merge queue's ref that names the PR: the runner was given no --pr-number, "
                                          "so the step would run on an empty or made-up ref (plan again with --pr-number)")
            if (rid := rebuilt_id(v for st in steps for v in (st.get("emulate") or {}).values())):
                raise X.ExprError(f"an artifact name or path reads `{rid}`, a commit id only the driver knows")
        except X.ExprError as e:
            return _blocked(f"job {jid}: {e}")
        tm = job.get("timeout-minutes", 360)
        if isinstance(tm, bool) or not isinstance(tm, (int, float)) or tm <= 0:
            return _blocked(f"job {jid}: timeout-minutes {tm!r} is not a plain number of minutes")
        by_name = {str(ms.get("workflow_step") or ms.get("workflow_step_prefix")): ms for ms in jl.get("steps") or [] if ms.get("side")}
        for st in steps:
            ms = next((m for k, m in by_name.items() if st["name"] == k or st["name"].startswith(k) and by_name[k].get("workflow_step_prefix")), None)
            if ms and (rid := rebuilt_id([st.get("script"), *(st.get("env") or {}).values(), *(ms.get("argv") or [])])):
                return _blocked(f"job {jid}: side step {st['name']!r} reads `{rid}`, a commit id only the driver knows (it runs outside it)")
            if (ms or {}).get("side") == "egress":   # run in its own sandbox WITH network: only the files it names, only tools BASE pins
                for a, b in (ms.get("rewrite") or []):
                    if st.get("script", "").count(a) != 1:
                        return _blocked(f"job {jid}: rewrite {a!r} must match the BASE body of {st['name']!r} exactly once")
                    st["script"] = st["script"].replace(a, b)
                st["side"] = {"where": "egress", "inputs": [safe_tree_path(str(p)) for p in ms.get("inputs") or []], "rewrite": ms.get("rewrite") or []}
            elif (ms or {}).get("side") == "host":   # a BASE reader of host/GitHub state, run NOW on the host: its answer is frozen in the plan
                if (q := declared_env_read(st.get("argv") or [], st.get("env") or {})):
                    return _blocked(f"job {jid}: host step {st['name']!r} argv reads `{q}`, {ENV_EVALUATED_HERE}")
                try:
                    argv = [X.substitute(str(x), static) for x in st.get("argv") or []]
                except X.ExprError as e:
                    return _blocked(f"job {jid}: host step {st['name']!r}: {e}")
                ledger_arg = str(Path(gate_ledger).expanduser()) if gate_ledger else ""
                head_arg = str(head_sha or cand)
                if "$GATE_LEDGER" in argv and not ledger_arg:
                    return _blocked(f"job {jid}: host step {st['name']!r} reads $GATE_LEDGER with no --gate-ledger")
                if "$HEAD" in argv and not re.fullmatch(r"[0-9a-f]{40}", head_arg):
                    return _blocked(f"job {jid}: host step {st['name']!r} reads $HEAD with invalid --head {head_arg!r}")
                argv = [ledger_arg if x == "$GATE_LEDGER" else (head_arg if x == "$HEAD" else x) for x in argv]
                try:
                    tfiles = [safe_tree_path(str(f)) for f in local.get("trusted_files") or []]
                except RuntimeError as e:
                    return _blocked(f"job {jid}: trusted_files: {e}")
                if not (len(argv) > 1 and argv[0] == "$PY" and argv[1] in tfiles):
                    return _blocked(f"job {jid}: host step {st['name']!r} must run `$PY <a trusted file present at BASE>`")
                blobs = {tf: _extract_base_file(wt, base, tf) for tf in tfiles}
                if any(b is None for b in blobs.values()):
                    return _blocked(f"job {jid}: host step {st['name']!r} must run `$PY <a trusted file present at BASE>`")
                tdir = trusted / "ctx" / str(ctx["check"])
                for tf, tb in blobs.items():
                    (tdir / tf).parent.mkdir(parents=True, exist_ok=True)
                    (tdir / tf).write_bytes(tb)
                blob = blobs[argv[1]]
                st["side"] = {"where": "host", "argv": [sys.executable, "-I", str(tdir / argv[1]), *argv[2:]], "base_sha256": sha256_bytes(blob)}
                st["precomputed"] = run_host_reader(st["side"]["argv"], tdir, st.get("timeout_s"), ms.get("no_verdict_when"), ms.get("pending_when"))
        image_id, deps_note = iso["image_id"], ""
        if local.get("deps"):
            if classifier_off:   # B39: every classifier output is false, so the leg skips its steps: validate the recipe without building the deps image
                info, why_d = deps_recipe(wt, cand, iso, local["deps"], prefix)
                if info is None:
                    return _blocked(f"job {jid}: {why_d}")
                deps_note = f"deps localci-deps:{info['digest'][:16]} skipped at plan (classifier flags all false)"
            else:
                image_id, deps_note = plan_deps_image(wt, cand, iso, local["deps"], prefix, run_dir,   # deps_recipe: contexts sharing one image share its prune recipe
                                                      re.sub(r"[^a-z0-9-]", "-", str(local.get("deps_recipe") or str(ctx["check"])[4:])))
                if image_id is None:
                    return _blocked(f"job {jid}: {deps_note}")
        pw = jl.get("playwright_skips")
        if pw is not None and (not isinstance(pw, dict) or set(pw) != {"step", "skipped"} or type(pw["skipped"]) is not int or pw["skipped"] < 0
                               or pw["step"] not in {st["name"] for st in steps}):
            return _blocked(f"job {jid}: playwright_skips needs exactly {{step: <a step of the job>, skipped: <int >= 0>}}")
        planned.append({"job_id": jid, "needs": needs, "legs": legs, "steps": steps, "job_env": jenv, "services": svcs, "path_prefix": prefix,
                        **({"playwright_skips": {"step": pw["step"], "skipped": pw["skipped"]}} if pw else {}),
                        "checkout": checkout, "image_id": image_id, "deps": deps_note, "venv": local.get("bare_venv", True) is not False,
                        "git_index": jl.get("git_index", True) is not False, "timeout_s": tm * 60})
        upstream.add(jid)
    for f in local.get("egress_trusted") or []:   # a tool an egress step runs is BASE's pin, or the step does not run at all
        if _extract_base_file(wt, base, f) != _extract_base_file(wt, cand, f):
            return _blocked(f"{f} differs from BASE: an egress step would run tools the candidate chose, with network")
    overlay: list = []
    if local.get("trusted_overlay"):   # BASE's copy of these files is laid over the candidate's inside the sandbox, and a candidate that changes one is a rewritten judge
        try:
            overlay = [safe_tree_path(str(f)) for f in local.get("trusted_files") or []]
        except RuntimeError as e:
            return _blocked(f"trusted_files: {e}")
        blobs = {f: _extract_base_file(wt, base, f) for f in overlay}
        if (missing := [f for f, b in blobs.items() if b is None]):
            return _blocked(f"trusted file(s) {missing} missing at base {base[:12]} — the candidate would supply its own judge")
        for f, b in blobs.items():
            dest = trusted / "base_files" / f
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b)
            if trusted_sha is not None:
                trusted_sha[f] = sha256_bytes(b)
    notes = [n for n in (flags_note,) if n]
    if local.get("version_sentinel"):   # the hosted CLI is chosen per run by GitHub: a local analysis on another one is not the hosted check
        lang = str((local.get("leg") or {}).get("language") or "")
        pin = str(((local.get("deps") or {}).get("codeql") or {}).get("version") or "")
        if not lang or not pin:
            return _blocked("version_sentinel needs local.leg.language and local.deps.codeql.version")
        if (why := version_sentinel(trusted, wt, base, str(ctx["check"]), local["version_sentinel"], lang, pin, repo)):
            return _blocked(why)
        notes.append(f"hosted {lang} CodeQL CLI == the pin {pin} at plan time")
    history = history_delta(wt, base, cand)
    if isinstance(history, str):
        return _blocked(history)
    judged = [wf, *overlay]
    modified = [f for f, a, b in zip(judged, tree_entries(wt, base, judged), tree_entries(wt, cand, judged)) if a != b]
    modified += [f for f in changed if f.rsplit("/", 1)[-1] == ".gitattributes"]
    return {"kind": "contained_jobs", "context": name, "cwd": str(wt), "jobs": planned, "judge_modified": modified, "trusted_files": [], "overlay": overlay,
            "skip_is_pass": local.get("skip_is_pass") is True, "plan_notes": notes, **({"ring_gating_override": ov} if ov else {}),
            "history": history, "expr": static, "needs": stood_in, "memory": str(local.get("memory") or "4g"),
            "driver_sha256": sha256_file(STEPS_DRIVER), "expr_sha256": sha256_file(GH_EXPR),
            "timeout_s": sum(j["timeout_s"] * len(j["legs"]) for j in planned),
            "purpose": f"{name}: jobs {[j['job_id'] for j in planned]} from BASE {wf}, each leg in a fresh sandbox"
                       f"{' with services ' + str(sorted({s['name'] for j in planned for s in j['services']})) if any(j['services'] for j in planned) else ''}"}


def full_dir_map(td: Path) -> dict:
    return {str(f.relative_to(td)): sha256_file(f) for f in sorted(td.rglob("*")) if f.is_file()} if td.is_dir() else {}


MATRIX_REL = "scripts/localci/contexts_matrix.yaml"


PARITY_MAX_BYTES = 2 << 20   # a candidate file read for parity: the largest real one is tests.yml, 160 KB; past this it is a finding, not a parse
PARITY_MAX_NODES = 500_000   # YAML aliases share objects at load, so a bomb is cheap to parse and ruinous to str()/walk: expanded size is capped


def expanded_nodes_within(obj, cap: int) -> bool:
    """True when `obj` has at most `cap` nodes counted as a TREE (a shared alias counts every time it is reached); stops at the cap."""
    stack, n = [obj], 0
    while stack:
        cur = stack.pop()
        n += 1
        if n > cap:
            return False
        if isinstance(cur, dict):
            stack.extend(cur.keys())
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)
    return True


def parity_yaml(blob: bytes, what: str):
    """Candidate YAML as data under a size cap and an expansion cap; ValueError names why (a finding about the candidate)."""
    import yaml

    if len(blob) > PARITY_MAX_BYTES:
        raise ValueError(f"{what} is {len(blob)} bytes, over the {PARITY_MAX_BYTES} byte cap read for parity")
    doc = yaml.safe_load(blob or b"")
    if not expanded_nodes_within(doc, PARITY_MAX_NODES):
        raise ValueError(f"{what} expands (YAML aliases) past {PARITY_MAX_NODES} nodes")
    return doc


def matrix_accounting(wt: Path, rev: str, scratch: Path) -> list[str]:
    """What the matrix at `rev` leaves unaccounted among the workflows at `rev`, both read from the object store as DATA: one problem
    string per executed context whose job `resolve_steps` cannot account for (a workflow step the matrix does not name, a matrix step
    the workflow no longer has, a shape it cannot emulate) — the runner's own computation, so what BLOCKS a context at plan time is
    exactly what this reports. An unreadable matrix or workflow is a problem too. Empty = every step of every executed context is accounted for."""
    blob = _extract_base_file(wt, rev, MATRIX_REL)
    if blob is None:
        return [f"{MATRIX_REL} is absent"]
    try:
        parity_yaml(blob, MATRIX_REL)
    except Exception as e:  # noqa: BLE001 — the candidate's own data: a finding, never our crash
        return [f"{MATRIX_REL}: {type(e).__name__}: {e}"[:300]]
    scratch.mkdir(parents=True, exist_ok=True)
    mp = scratch / f"matrix-{rev[:12]}.yaml"
    mp.write_bytes(blob)
    ctxs = load_contexts(str(mp))
    if ctxs["status"] != "ok":
        return [f"{MATRIX_REL}: {ctxs['reason']}"]
    problems: list[str] = []
    docs: dict = {}
    for cname, ctx in ctxs["map"].items():
        if ctx["mapping"] != "executed" or not ctx["local"].get("steps"):
            continue
        try:   # whatever the candidate's data does to our reading of it is a problem with the candidate's data, so a NEW one is FAIL, not BLOCKED
            problems.extend(_context_accounting(wt, rev, cname, ctx, docs))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{cname}: its matrix data cannot be read ({type(e).__name__})")
    return problems


def _context_accounting(wt: Path, rev: str, cname: str, ctx: dict, docs: dict) -> list[str]:
    problems: list[str] = []
    wf, local = str(ctx.get("workflow_file")), ctx["local"]
    if wf not in docs:
        try:
            docs[wf] = parity_yaml(_extract_base_file(wt, rev, wf) or b"", wf)
        except Exception:  # noqa: BLE001 — an unparseable, oversized or bomb workflow is a finding, never a crash
            docs[wf] = None
    doc = docs[wf]
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        return [f"{cname}: workflow {wf} is unreadable (unparseable, oversized or over the expansion cap)"]
    legs = [*(local.get("jobs") or []), {**local, "job_id": ctx.get("job_id")}] if local.get("expressions") else [{**local, "job_id": ctx.get("job_id")}]
    defaults = ((doc.get("defaults") or {}).get("run")) or {}
    for jl in legs:   # a service context chains jobs: each has its own matrix steps, as plan_service_context reads them
        job = doc["jobs"].get(jl.get("job_id"))
        if not isinstance(job, dict):
            problems.append(f"{cname}: job {jl.get('job_id')!r} is absent from {wf}")
            continue
        if local.get("expressions"):
            jenv = {str(k): str(v) for k, v in {**(doc.get("env") or {}), **(job.get("env") or {}), **(jl.get("env") or {})}.items()}
            _, why = resolve_steps({**job, "env": jenv}, jl, "main", defaults, expressions=True)
        else:
            _, why = resolve_steps(job, jl, rev, defaults, doc.get("env") or {})
        if why:
            problems.append(f"{cname}: job {jl.get('job_id')}: {why}")
    return problems


def matrix_parity_check(wt: Path, base: str, cand: str, scratch: Path) -> dict:
    """policy.matrix_parity: the PR that adds or changes a step of a workflow the matrix executes must carry its matrix row.

    Candidate files are read as data (never executed); the code is BASE's. FAIL names every problem the candidate has that BASE does
    not (a drift the candidate introduces, or fails to cure while touching it). A problem BASE already has is not the candidate's:
    NOT_APPLICABLE names it (an innocent PR on a drifted base is never blocked by someone else's drift). PASS when nothing is unaccounted."""
    try:
        was, now_ = matrix_accounting(wt, base, scratch), matrix_accounting(wt, cand, scratch)
    except Exception as e:  # noqa: BLE001 — our own failure is no verdict on the candidate: BLOCKED, never FAIL
        return _blocked(f"matrix parity could not be computed: {type(e).__name__}: {e}")
    new = [p for p in now_ if p not in was]
    if new:
        return {"kind": "record", "status": "FAIL",
                "reason": "the candidate leaves the matrix out of step with the workflows it executes (add the row in the SAME PR): " + " | ".join(new)}
    if now_:
        return {"kind": "record", "status": "NOT_APPLICABLE",
                "reason": f"{len(now_)} problem(s) already present at BASE, none introduced by the candidate: " + " | ".join(now_)}
    return {"kind": "record", "status": "PASS", "reason": "every step of every executed context is accounted for by the candidate's matrix and workflows"}


def cmd_plan(a):
    run_dir, wt = Path(a.run_dir).resolve(), Path(a.worktree).resolve()
    store = Store(run_dir)
    ident = identity(wt)
    if a.candidate and ident["candidate_sha"] != a.candidate:
        sys.exit(f"worktree HEAD {ident['candidate_sha']} != requested candidate {a.candidate}")
    head_sha = getattr(a, "head", None) or ident["candidate_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", str(head_sha)):
        sys.exit(f"--head must be a 40-char lowercase hex sha, got {head_sha!r}")
    gate_ledger = getattr(a, "gate_ledger", None)
    if gate_ledger is None:
        gate_ledger = str(DEFAULT_GATE_LEDGER)
    base = git(wt, "rev-parse", a.base + "^{commit}")
    trusted = run_dir / "state" / "trusted"
    trusted.mkdir(parents=True, exist_ok=True)
    for f in TRUSTED_CLASSIFIER_FILES:
        blob = _extract_base_file(wt, base, f)
        if blob is None:
            sys.exit(f"trusted classifier file {f} missing at base {base[:12]} — refusing to plan without the trusted classifier")
        (trusted / Path(f).name).write_bytes(blob)
    changed = git(wt, "diff", "--no-renames", "--name-only", f"{base}..{ident['candidate_sha']}").splitlines()   # hotzone_changed_files.sh: a rename lists BOTH paths
    cm = json.loads(subprocess.run([sys.executable, "-I", str(trusted / "change_map.py")], input="\n".join(changed) + "\n",
                                   capture_output=True, text=True, check=True, env=trusted_env()).stdout)
    test_mods = sorted(f for f in changed if f.startswith("scripts/tests/test_") and f.endswith(".py") and (wt / f).exists())
    optin = [m for m in test_mods if "real_pg" in m]
    pure = [m for m in test_mods if m not in optin]
    venv_py = a.python or str(run_dir / "venv" / "bin" / "python")
    if not a.python and not Path(venv_py).exists():
        venv_py = sys.executable
    trusted_sha: dict[str, str] = {}
    checks = {
        "policy.trusted_classifier_corpus": {"kind": "cmd", "cwd": str(trusted), "cmd": [sys.executable, "-m", "unittest", "test_change_map", "test_security_gate_flags"],
            "trusted_pythonpath": str(trusted),
            "purpose": "the classifiers that decide which jobs and scanners run are proven on their own guilt+innocence corpora (change map and gate flags, as security.yml runs both), from the BASE ref (candidate cannot self-approve)"},
        "policy.change_map": {"kind": "record", "status": change_map_status(cm),
            "reason": f"trusted change_map: reason={cm.get('reason')} run_all={cm.get('run_all')} suggested={cm.get('suggested_jobs')}", "data": cm},
        "tests.scripts_impacted": ({"kind": "pytest", "cwd": str(wt), "modules": pure, "python": venv_py,
            "purpose": "impacted backstage tests, blocking locally (GitHub runs scripts/tests only as a report-only sweep)"} if pure else
            {"kind": "record", "status": "NOT_APPLICABLE", "reason": "no scripts/tests/test_*.py module changed in the diff (trusted classification of the diff)"}),
        "tests.scripts_optin_real_pg": {"kind": "record", "status": "NOT_APPLICABLE",
            "reason": (f"opt-in modules {optin} require WA_TEAM_PROMISES_REAL_PG=1 + pg_ctl/initdb; not enabled, recorded not skipped" if optin else "no opt-in module in diff")},
        "tests.backend_shards": {"kind": "record", "status": "BLOCKED" if ("backend-tests" in cm.get("suggested_jobs", []) or cm.get("run_all")) else "NOT_APPLICABLE",
            "reason": ("backend-tests selected by the trusted classifier but no local backend runner exists" if ("backend-tests" in cm.get("suggested_jobs", []) or cm.get("run_all"))
                       else f"trusted change_map suggested_jobs={cm.get('suggested_jobs')}: backend shards not selected")},
        "tests.frontend_mouth": {"kind": "record", "status": "BLOCKED" if ("frontend-tests" in cm.get("suggested_jobs", []) or cm.get("run_all")) else "NOT_APPLICABLE",
            "reason": ("frontend-tests selected by the trusted classifier but no local frontend runner exists" if ("frontend-tests" in cm.get("suggested_jobs", []) or cm.get("run_all"))
                       else "mouth domain not touched per trusted change_map")},
        "review.independent": {"kind": "review", "purpose": "a seat != builder signs the reviewed candidate identity; BLOCKED until a matching review is imported"},
    }
    checks["policy.matrix_parity"] = matrix_parity_check(wt, base, ident["candidate_sha"], run_dir / "state" / "parity")
    checks["security.pysa_python"] = pysa_check_spec(wt, base, ident["candidate_sha"], trusted, run_dir, changed, a.pysa_home)
    tp_files = [BAN_TEST] + [f for f in (a.trusted_pytest or []) if f != BAN_TEST]
    for rel in tp_files:
        blob = _extract_base_file(wt, base, rel)
        name = "policy.paid_anthropic_ban" if rel == BAN_TEST else f"trusted.{Path(rel).stem}"
        if blob is None:
            checks[name] = {"kind": "record", "status": "BLOCKED", "reason": f"trusted test {rel} is missing at base {base[:12]}"}
            continue
        dest = trusted / "base_files" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        trusted_sha[rel] = sha256_bytes(blob)
        checks[name] = {"kind": "trusted_pytest", "cwd": str(wt), "python": venv_py, "trusted_files": [rel],
                        "purpose": f"{rel} extracted from BASE {base[:12]} and run against the candidate tree (candidate cannot rewrite its own guard)"}
    iso = isolation_spec(a.isolation, a.isolation_image)
    pyv = {"host": platform.python_version(), "container": iso.get("python_version"), "container_extra": iso.get("pythons") or {}}
    ctxs = load_contexts(a.contexts_file)   # operator input, like the runner itself: never read from the candidate's tree
    for cname, ctx in ctxs["map"].items():
        if ctx["mapping"] != "executed" or not ctx["local"].get("steps"):
            continue
        chk = ctx.get("check")
        if not isinstance(chk, str) or not CTX_CHECK_NAME.match(chk) or chk in checks:
            sys.exit(f"context {cname!r}: an executed context with steps needs a unique local.check matching {CTX_CHECK_NAME.pattern}, got {chk!r}")
        if ctx["local"].get("expressions"):   # service contexts (v0.6.0): job chains, services, deps images, evaluated expressions
            checks[chk] = plan_service_context(wt, base, ident["candidate_sha"], trusted, cname, ctx, changed, pyv, iso, cm, run_dir, a.pr_number, trusted_sha,
                                               gate_ledger=gate_ledger, head_sha=head_sha)
        else:
            checks[chk] = plan_context_check(wt, base, ident["candidate_sha"], trusted, cname, ctx, trusted_sha, changed, pyv)
    for legacy, chk in SUPERSEDED_RECORDS.items():   # "no local runner exists" stops being true once the context is planned
        if chk in checks:
            checks[legacy] = {"kind": "record", "status": "NOT_APPLICABLE", "reason": f"superseded by {chk}: that check carries the job's verdict"}
    for extra in (a.extra_check or []):
        name, eq, spec_s = extra.partition("=")
        if not eq or not EXTRA_CHECK_NAME.match(name):
            sys.exit(f"--extra-check must be NAME=JSON with NAME matching {EXTRA_CHECK_NAME.pattern}, got {extra!r}")
        if name.startswith(RESERVED_CHECK_PREFIXES) or name in checks:
            sys.exit(f"--extra-check {name!r} collides with a planned or reserved check name ({', '.join(RESERVED_CHECK_PREFIXES)} are reserved): "
                     "an extra check cannot overwrite a policy or forge a trusted verdict")
        try:
            spec = json.loads(spec_s)
        except json.JSONDecodeError as e:
            sys.exit(f"--extra-check {name!r}: invalid JSON spec: {e}")
        if not isinstance(spec, dict) or spec.get("kind") not in EXTRA_CHECK_KINDS:
            sys.exit(f"--extra-check {name!r}: kind must be one of {EXTRA_CHECK_KINDS}")
        if (bad := sorted(set(spec) & RUNNER_OWNED_KEYS)):
            sys.exit(f"--extra-check {name!r}: {bad} are set by the runner, never by an extra (trust, isolation and pinning are not the operator's to claim)")
        checks[name] = {**spec, "extra": True}   # operator-chosen: a `cmd` extra runs on the host and may execute candidate code
    if iso.get("mode") != "container" or any(s.get("kind") == "cmd" and s.get("extra") for s in checks.values()):
        print("WARNING: this plan runs candidate code on the host as your user: it can rewrite any Pysa home together with its manifest "
              "and baseline index, so treat every home this user can write as untrusted afterwards — "
              "`pysa_check.py setup --home <home> --rebuild` before the next contained plan relies on it", file=sys.stderr)
    for name, spec in list(checks.items()):   # candidate code never runs uncontained unless the operator said --isolation none
        if spec.get("kind") not in CANDIDATE_KINDS:
            continue
        if iso.get("error"):
            checks[name] = {"kind": "record", "status": "BLOCKED", "reason": f"isolation=container unavailable at plan time: {iso['error']} — candidate code is not "
                            "run uncontained unless the plan says --isolation none"}
        elif spec["kind"] in ("contained_steps", "contained_jobs") and iso["mode"] != "container":
            checks[name] = _blocked("a required context's steps run only under --isolation container: they execute candidate code and mutate "
                                    "their tree (guilt controls)")
        else:
            spec["isolation"] = iso
            if iso["mode"] == "container":
                spec.pop("python", None)   # the interpreter is the pinned image's, not a host venv
    sc = checks.get("tests.scripts_impacted")
    if sc and sc["kind"] == "pytest" and iso.get("mode") == "container" and ctxs["status"] == "ok":   # hosted's sweep env: the Backend Tests deps image
        deps = ((ctxs["map"].get(SWEEP_DEPS_CONTEXT) or {}).get("local") or {}).get("deps")
        image, note = plan_deps_image(wt, ident["candidate_sha"], iso, deps, os.path.dirname(hosted_python(iso)), run_dir, "backend-tests") if deps \
            else (None, f"the contexts matrix has no deps recipe for {SWEEP_DEPS_CONTEXT!r}")
        checks["tests.scripts_impacted"] = {**sc, "deps_image": image, "deps_note": note} if image else \
            _blocked(f"tests.scripts_impacted: hosted's sweep env (lock + cell-core + test packages) is not available offline: {note}")
    for spec in checks.values():   # every trusted dir is sha-mapped at plan time and re-verified before it runs (classifier dir included)
        if spec.get("kind") == "cmd" and spec.get("trusted_pythonpath") and "trusted_dir_sha256" not in spec:
            spec["trusted_dir_sha256"] = trusted_dir_map(Path(spec["trusted_pythonpath"]))
    seats = [s.strip() for s in ([a.builder_seat] if a.builder_seat else []) + (a.builder_seats.split(",") if a.builder_seats else []) if s and s.strip()]
    created_epoch = time.time()
    plan = {"run_id": run_dir.name, "created_at": now(), "created_epoch": created_epoch, "worktree": str(wt), "base_sha": base,
            "candidate_sha": ident["candidate_sha"], "tree_sha": ident["tree_sha"], "changed_files": changed,
            "trusted_classifier_sha256": sha256_file(trusted / "change_map.py"), "trusted_files_sha256": trusted_sha,
            "builder_seat": a.builder_seat or None, "builder_seats": sorted(set(seats)),
            "max_attempts": a.max_attempts, "deadline_s": a.deadline_s, "deadline_at": created_epoch + a.deadline_s,
            "contexts_file": a.contexts_file, "contexts_status": ctxs["status"], "contexts_reason": ctxs["reason"],
            "contexts_sha256": ctxs.get("sha256"), "required_contexts": ctxs["required"], "contexts_map": ctxs["map"], "checks": checks,
            "isolation": iso, "runner_version": RUNNER_VERSION}
    plan["plan_hash"] = plan_hash_of(plan)
    atomic_write(run_dir / "state" / "plan.json", json.dumps(plan, indent=2, sort_keys=True))
    env = env_fingerprint(venv_py, checks)
    st = {"run_id": run_dir.name, "plan_hash": plan["plan_hash"],
          "binding": {"candidate_sha": ident["candidate_sha"], "tree_sha": ident["tree_sha"], "base_sha": base, "dirty_at_plan": ident["dirty"]},
          "env": env, "env_hash": env_hash(env), "checks": {}}
    for name, spec in checks.items():
        if spec["kind"] == "record":
            st["checks"][name] = {"status": spec["status"], "reason": spec["reason"], "at": now(), "receipt": None, "attempts": 0, "history": []}
        else:
            st["checks"][name] = {"status": "QUEUED", "reason": "not executed yet", "at": now(), "receipt": None, "attempts": 0, "history": []}
    if ident["dirty"]:
        for c in st["checks"].values():
            c.update(status="BLOCKED", reason="worktree dirty at plan time: " + ",".join(ident["dirty_paths"]))
    store.save(st)
    print(json.dumps({"run_id": run_dir.name, "candidate": ident["candidate_sha"], "base": base, "plan_hash": plan["plan_hash"],
                      "contexts": ctxs["status"], "isolation": {k: iso.get(k) for k in ("mode", "image", "image_id", "error")},
                      "checks": {k: v["status"] for k, v in st["checks"].items()}}, indent=1))


# -------------------------------------------------------------------------- run
def parse_junit(p: Path) -> dict:
    empty = {"collected": 0, "executed": 0, "failures": None, "errors": None, "skipped": None}
    if not p.exists():
        return {**empty, "junit": "missing"}
    try:
        root = ET.parse(p).getroot()
    except ET.ParseError:
        return {**empty, "junit": "unparseable"}
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    t = sum(int(s.get("tests", 0)) for s in suites)
    f = sum(int(s.get("failures", 0)) for s in suites)
    e = sum(int(s.get("errors", 0)) for s in suites)
    k = sum(int(s.get("skipped", 0)) for s in suites)
    return {"collected": t, "executed": t - k, "failures": f, "errors": e, "skipped": k, "junit": str(p)}


def classify_pytest(rc: int | None, counts: dict) -> tuple[str, str]:
    """rc 1 -> FAIL; crash / rc 2-4 / rc 5 / zero tests / all skipped -> ERROR; PASS only with executed tests and rc 0."""
    if rc is None:
        return "ERROR", "no exit code — not a verdict on the candidate"
    if rc < 0:
        return "ERROR", f"pytest crashed (signal {-rc}) — not a verdict on the candidate"
    if rc == INSTALL_RC:
        return "ERROR", "the sandbox's offline env install failed (see the log) — not a verdict on the candidate"
    if rc == 5 or counts["collected"] == 0:
        return "ERROR", f"pytest rc={rc}: zero tests collected (junit={counts.get('junit')}) — not PASS"
    if rc in (2, 3, 4):
        return "ERROR", f"pytest rc={rc} (collection/internal/usage error): failures={counts['failures']} errors={counts['errors']} — not a verdict on the candidate"
    if rc == 1:
        return "FAIL", f"pytest rc=1: failures={counts['failures']} errors={counts['errors']}"
    if rc == 0:
        if counts["failures"] or counts["errors"]:
            return "ERROR", f"rc=0 contradicts junit failures={counts['failures']} errors={counts['errors']}"
        if counts["executed"] <= 0:
            return "ERROR", "rc=0 but no executed test (all skipped) — not PASS"
        return "PASS", f"{counts['executed']} executed, {counts['skipped']} skipped, 0 failed"
    return "ERROR", f"unexpected pytest rc={rc}"


def build_overlay(wt: Path, overlay: Path, overrides: dict[str, bytes], prefix: str = "") -> None:
    """Mirror `wt` with symlinks, except `overrides` (rel path -> bytes) which are real files.

    A base-ref test that computes REPO_ROOT from its own __file__ then sees the candidate tree
    (through the symlinks) while the test file itself is the BASE ref's copy.
    """
    src = wt / prefix if prefix else wt
    overlay.mkdir(parents=True, exist_ok=True)
    rel = {o[len(prefix):] for o in overrides if o.startswith(prefix)}
    dirs = {r.split("/", 1)[0] for r in rel if "/" in r}
    files = {r for r in rel if "/" not in r}
    if src.is_dir():
        for entry in os.scandir(src):
            if entry.name in dirs or entry.name in files:
                continue
            os.symlink(entry.path, overlay / entry.name)
    for d in dirs:
        build_overlay(wt, overlay / d, overrides, prefix + d + "/")
    for f in files:
        (overlay / f).write_bytes(overrides[prefix + f])


def isolation_spec(mode: str, image: str) -> dict:
    """Plan-time measurement of the candidate sandbox: the image is pinned by ID (a retag cannot substitute it)."""
    if mode == "none":
        return {"mode": "none", "reason": "operator chose --isolation none: candidate code runs as the operator's OS user (advisory only)"}
    docker = shutil.which("docker")
    if not docker:
        return {"mode": "container", "image": image, "error": "docker CLI not found"}
    try:
        r = subprocess.run([docker, "image", "inspect", "--format", "{{.Id}}\n{{range .Config.Env}}{{println .}}{{end}}", image], capture_output=True,
                           text=True, timeout=60, env=trusted_env())
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"mode": "container", "image": image, "error": f"docker unreachable: {e}"}
    lines = r.stdout.strip().splitlines()
    if r.returncode != 0 or not lines or not lines[0].startswith("sha256:"):
        return {"mode": "container", "image": image, "error": f"image {image!r} not inspectable (rc={r.returncode}): {r.stderr.strip()[:200]}"}
    return isolation_of_inspect(image, lines, docker)


def isolation_of_inspect(image: str, lines: list, docker: str) -> dict:
    """The sandbox spec from `docker image inspect --format '{{.Id}}\\n{{range .Config.Env}}{{println .}}{{end}}'` lines (B22's prune reads the same)."""
    env = dict(ln.split("=", 1) for ln in lines[1:] if "=" in ln)
    pyv = env.get("PYTHON_VERSION")   # set by the official python images; LOCALCI_PYTHONS="<major.minor>=<bin dir> ..." by candidate.Dockerfile
    extra = dict(x.split("=", 1) for x in env.get("LOCALCI_PYTHONS", "").split() if "=" in x)
    return {"mode": "container", "image": image, "image_id": lines[0], "docker": os.path.realpath(docker), "network": "none",
            "mounts": [], "user": f"{SANDBOX_UID}:{SANDBOX_UID}", "init": True, "python_version": pyv, "pythons": extra}


def isolation_of(plan: dict) -> dict:
    """A plan frozen before v0.3.0 carries no isolation evidence: it is uncontained, never silently upgraded."""
    return plan.get("isolation") or {"mode": "none", "reason": "plan predates isolation evidence (runner < 0.3.0)"}


def _tar_add(tf: tarfile.TarFile, name: str, data: bytes | None = None, mode: int = 0o644, link: str | None = None, src: Path | None = None) -> None:
    ti = tarfile.TarInfo(name)
    ti.uid = ti.gid = SANDBOX_UID
    ti.mtime = int(time.time())   # a checkout writes its files now; mtime 0 made every file 56 years old to an age-reading test
    if data is None and link is None and src is None:
        ti.type, ti.mode = tarfile.DIRTYPE, 0o755
        tf.addfile(ti)
    elif link is not None:
        ti.type, ti.linkname, ti.mode = tarfile.SYMTYPE, link, 0o777
        tf.addfile(ti)
    elif src is not None:   # a host file streamed from disk, never read whole into memory (the tree pack is hundreds of MB)
        with open(src, "rb") as fh:
            ti.size, ti.mode = os.fstat(fh.fileno()).st_size, mode
            tf.addfile(ti, fh)
    else:
        ti.size, ti.mode = len(data), mode
        tf.addfile(ti, io.BytesIO(data))


def safe_tree_path(rel: str) -> str:
    """A tree entry path from `git ls-tree`: a crafted tree object can carry `..` or an absolute name — never written outside the root."""
    parts = rel.split("/")
    if not rel or rel.startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise RuntimeError(f"unsafe tree entry path {rel!r}")
    return rel


def stream_tree_tar(wt: Path, commit: str, sink, overrides: dict[str, bytes], extra: dict[str, bytes], group: list | None = None,
                    timeout: float | None = None, paths: set | None = None, files: dict[str, Path] | None = None) -> int:
    """Tar `commit`'s tree from the OBJECT STORE into `sink` under w/ — never the checkout (ignored files such as .env or a venv stay
    out) and never `git archive` (it honours the candidate's export-ignore). `overrides` replace blobs (BASE test files); `extra` lands
    outside w/; `files` (name -> host path) land outside w/ streamed from disk (B14: the tree pack). Owned by the sandbox uid so
    candidate tests can write where they could in a checkout."""
    listing = subprocess.run(["git", "-C", str(wt), "ls-tree", "-r", "-z", "--full-tree", commit], capture_output=True, check=True, timeout=timeout).stdout.decode()
    entries = []
    for rec in listing.split("\0"):
        if rec:
            meta, rel = rec.split("\t", 1)
            mode, kind, oid = meta.split(" ")
            if kind == "blob" and (paths is None or rel in paths):   # `paths`: an egress side step gets only the files it reads
                entries.append((mode, oid, safe_tree_path(rel)))
    parents = lambda paths, top: {f"{top}{q}" for n in paths for q in Path(n).parents if str(q) != "."}   # noqa: E731
    files = files or {}
    dirs = sorted({"w", "out"} | parents({rel for _, _, rel in entries} | set(overrides), "w/") | parents(set(extra) | set(files), ""))
    tf = tarfile.open(fileobj=sink, mode="w|")
    for d in dirs:
        _tar_add(tf, d)
    for x in sorted(extra):
        _tar_add(tf, x, extra[x])
    for x in sorted(files):
        _tar_add(tf, x, src=files[x])
    cat = subprocess.Popen(["git", "-C", str(wt), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if group is not None:
        group.append(cat)   # the caller's watchdog kills it with the copy process: a blocked read ends at EOF
    try:
        for mode, oid, rel in entries:
            cat.stdin.write(f"{oid}\n".encode())
            cat.stdin.flush()
            hdr = cat.stdout.readline().decode().split()
            if len(hdr) != 3 or hdr[0] != oid or hdr[1] != "blob":
                raise RuntimeError(f"cat-file stream desync at {rel}: {hdr}")
            body = cat.stdout.read(int(hdr[2]))
            cat.stdout.read(1)
            if rel in overrides:
                continue
            if mode == "120000":
                _tar_add(tf, f"w/{rel}", link=body.decode("utf-8", "surrogateescape"))
            else:
                _tar_add(tf, f"w/{rel}", body, 0o755 if mode == "100755" else 0o644)
    finally:
        try:
            cat.stdin.close()
        except OSError:
            pass
        try:
            cat.wait(timeout=30)
        except subprocess.TimeoutExpired:
            cat.kill()
            cat.wait()
    for rel, blob in sorted(overrides.items()):
        _tar_add(tf, f"w/{rel}", blob)
    tf.close()
    return len(entries)


TREE_PACK_TIMEOUT_S = 300
_TREE_PACK_LOCK = threading.Lock()
_TREE_PACK_FAILED: dict[tuple[str, str], str] = {}   # (run dir, commit) -> why: a failed build is not retried by every later container of the run


def build_tree_pack(wt: Path, commit: str, dest: Path, timeout: float) -> dict:
    """B14: one pack of `commit`'s tree objects (every blob and subtree, plus the root tree) for the sandboxes to index from, so no
    container re-hashes and re-packs the whole tree itself. Same entity set `stream_tree_tar` ships (a gitlink is skipped). pack-objects
    streams straight into `dest`: the pack is never held in memory. Any failure removes the partial file and raises."""
    part = dest.with_name(dest.name + ".part")
    try:
        root = subprocess.run(["git", "-C", str(wt), "rev-parse", f"{commit}^{{tree}}"], capture_output=True, text=True, check=True, timeout=timeout).stdout.strip()
        listing = subprocess.run(["git", "-C", str(wt), "ls-tree", "-r", "-t", "-z", "--full-tree", commit], capture_output=True, check=True,
                                 timeout=timeout).stdout.decode("utf-8", "surrogateescape")
        oids = {root}
        for rec in listing.split("\0"):
            if rec:
                _mode, kind, oid = rec.split("\t", 1)[0].split(" ")
                if kind in ("blob", "tree"):
                    oids.add(oid)
        with open(part, "wb") as fh:
            subprocess.run(["git", "-C", str(wt), "pack-objects", "--stdout", "-q"], input="".join(f"{o}\n" for o in sorted(oids)).encode(), stdout=fh,
                           stderr=subprocess.PIPE, check=True, timeout=timeout)
        h = hashlib.sha256()
        with open(part, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        os.replace(part, dest)
        return {"tree": root, "objects": len(oids), "bytes": dest.stat().st_size, "sha256": h.hexdigest()}
    except BaseException:
        part.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise


def tree_pack_for(run_dir: Path, plan: dict) -> tuple[Path | None, dict | None, str | None]:
    """The run's tree pack, built lazily by the first git_index container and reused by every later one (state/tree.pack beside a json
    sidecar). A reused pack is re-checked against its sidecar by commit and SIZE (not sha256: hashing hundreds of MB per container
    costs more than the container saves; the pack lives in the run's private state, which no sandbox mounts; the sandbox's own
    `index-pack` verifies every object's hash and the tree it names). -> (pack, sidecar, None) or (None, None, why): a pack that cannot
    be built only costs the speed, never a verdict."""
    pack, side, sha = run_dir / "state" / "tree.pack", run_dir / "state" / "tree.pack.json", plan.get("candidate_sha")
    key = (str(run_dir), sha)
    with _TREE_PACK_LOCK:
        if key in _TREE_PACK_FAILED:
            return None, None, _TREE_PACK_FAILED[key]
        try:
            if not sha:
                raise ValueError("the plan names no candidate commit")
            meta = json.loads(side.read_text()) if side.exists() and pack.exists() else None
            if meta and meta.get("commit") == sha and pack.stat().st_size == meta.get("bytes"):
                return pack, meta, None
            meta = {**build_tree_pack(Path(plan["worktree"]), sha, pack, TREE_PACK_TIMEOUT_S), "commit": sha}
            atomic_write(side, json.dumps(meta))
            return pack, meta, None
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, AttributeError, KeyError, TypeError) as e:   # a sidecar that is not a dict, or lacks a key
            pack.unlink(missing_ok=True)
            side.unlink(missing_ok=True)
            why = f"{type(e).__name__}: {str(e).strip()[:160]}"
            _TREE_PACK_FAILED[key] = why
            return None, None, why


def tree_pack_ship(run_dir: Path, plan: dict) -> tuple[dict | None, dict[str, Path], str | None]:
    """-> (the steps.json `tree_pack` entry, the host files to tar into the sandbox, the log line saying the pack is unavailable)."""
    pack, meta, why = tree_pack_for(run_dir, plan)
    if pack is None:
        return None, {}, f"# tree pack: unavailable ({why}) — the sandbox indexes the tree itself\n"
    return {"path": "/cfg/tree.pack", "tree": meta["tree"]}, {"cfg/tree.pack": pack}, None


def tree_pack_ship_safe(run_dir: Path, plan: dict) -> tuple[dict | None, dict[str, Path], str | None]:
    """The pack is a speed-up: whatever its machinery raises, the leg falls back to indexing the tree itself and says so."""
    try:
        return tree_pack_ship(run_dir, plan)
    except Exception as e:   # noqa: BLE001
        return None, {}, f"# tree pack: unavailable ({type(e).__name__}: {str(e).strip()[:160]}) \u2014 the sandbox indexes the tree itself\n"


def remove_tree_pack(run_dir: Path) -> None:
    """The pack is hundreds of MB and run dirs are kept as evidence: it goes when the run ends, whatever the verdicts were."""
    for name in ("tree.pack", "tree.pack.part", "tree.pack.json"):
        (run_dir / "state" / name).unlink(missing_ok=True)
    with _TREE_PACK_LOCK:
        for k in [k for k in _TREE_PACK_FAILED if k[0] == str(run_dir)]:
            del _TREE_PACK_FAILED[k]


def _gb(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _probe_free_gb(docker: str, image_id: str, run_dir: Path) -> tuple[float | None, str | None]:
    """The docker host's free space under its container root: `df -Pk /` in a throwaway, network-less, unprivileged container of
    the pinned candidate image (BASE-built, no candidate content), which sits on the same filesystem every sandbox writes to."""
    argv = [docker, "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user",
            f"{SANDBOX_UID}:{SANDBOX_UID}", "--label", "org.nuzantara.localci=probe", "--label", f"org.nuzantara.localci.run={run_label(run_dir)}",
            "--entrypoint", "df", image_id, "-Pk", "/"]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=120, env=trusted_env())
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"df probe did not run: {type(e).__name__}"
    lines = (r.stdout or "").strip().splitlines()
    if r.returncode != 0 or len(lines) < 2 or not re.search(r"\b(?:1024|1K)-blocks\b", lines[0]):
        return None, f"df probe rc={r.returncode}: {((r.stderr or '') + (r.stdout or '')).strip()[:160]!r}"
    fields = lines[-1].split()
    if len(fields) < 6 or not fields[3].isdigit():
        return None, f"df probe output unreadable: {lines[-1][:120]!r}"
    return int(fields[3]) * 1024 / 1e9, None


def disk_floor_refusal(docker: str, image_id: str, run_dir: Path) -> str | None:
    """Why a service leg must not start on this host (BLOCKED: no verdict, never a FAIL), else None. Floor 0 reads nothing."""
    raw = os.environ.get(MIN_FREE_ENV, "")
    try:
        floor = float(raw) if raw.strip() else DEFAULT_MIN_FREE_GB
    except ValueError:
        floor = float("nan")
    if not (0 <= floor < float("inf")):
        return f"host_disk_floor_invalid: {MIN_FREE_ENV}={raw[:40]!r} is not a number of GB >= 0 — no service leg starts on an unread floor"
    if floor == 0:
        return None
    key = str(run_dir)
    if key not in _HOST_FREE:
        _HOST_FREE[key] = _probe_free_gb(docker, image_id, run_dir)
    free, why = _HOST_FREE[key]
    if free is None:
        return f"host_disk_unmeasured: {why} — the {_gb(floor)} GB floor cannot be checked, so no service leg starts"
    if free < floor:
        return (f"host_disk_below_floor {_gb(free)}GB<{_gb(floor)}GB: the docker host has {_gb(free)} GB free, under {MIN_FREE_ENV}="
                f"{_gb(floor)}; the leg was not started — no verdict on the candidate, never a FAIL; free space and run again")
    return None


def run_label(run_dir: Path) -> str:
    """Container label value: the resolved run dir, hashed — two run dirs sharing a basename never reap each other's containers."""
    return sha256_bytes(str(Path(run_dir).resolve()).encode())[:24]


def _read_junit_out(docker: str, ctr: str, junit: Path) -> str | None:
    """Copy /out/junit.xml out of the stopped container: one regular file, size-capped — a symlink or an oversized file is no junit."""
    p = subprocess.Popen([docker, "cp", f"{ctr}:/out/junit.xml", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=trusted_env())
    watchdog = threading.Timer(COPY_TIMEOUT_S, p.kill)
    try:
        watchdog.start()
        with tarfile.open(fileobj=p.stdout, mode="r|") as t:
            m = t.next()
            if m is None or m.name != "junit.xml" or not m.isfile():
                return "no regular /out/junit.xml in the container"
            if m.size > JUNIT_MAX_BYTES:
                return f"junit.xml is {m.size} bytes (> {JUNIT_MAX_BYTES})"
            junit.write_bytes(t.extractfile(m).read())
            return None
    except (tarfile.TarError, OSError) as e:
        return f"junit copy-out failed: {e}"
    finally:
        watchdog.cancel()
        p.kill()
        p.wait()


# pytest-xdist's own words (3.x dsession.py) when a worker dies under the controller: an OOM-killed worker reads like this
XDIST_DEAD_WORKER = re.compile(r"\[gw\d+\] node down: Not properly terminated|\bworker '?gw\d+'? crashed")


def xdist_dead_worker(log: Path) -> tuple[str, int] | None:
    """The first line of a leg log where xdist reports a dead worker: (its words, 1-based line number as `grep -n` counts)."""
    try:
        with open(log, "rb") as fh:
            for n, raw in enumerate(fh, 1):
                if (m := XDIST_DEAD_WORKER.search(raw.decode(errors="replace"))):
                    return m.group(0), n
    except OSError:
        return None
    return None


SANDBOX_SAMPLER_ENV = "LOCALCI_SANDBOX_SAMPLER"   # "0": no `docker stats` / `docker ps -s` (B33 S2); the host-side phase times stay
SANDBOX_SAMPLE_EVERY_S = 2.0
SANDBOX_STATS_TIMEOUT_S, SANDBOX_PS_TIMEOUT_S = 20, 60
_SIZE_UNITS = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12, "KIB": 2**10, "MIB": 2**20, "GIB": 2**30, "TIB": 2**40}


def new_probe(name: str) -> dict:
    """B33 S2: the trusted side's numbers about one candidate container. DATA for the receipt — no verdict function reads a key of it."""
    sampler = "off" if os.environ.get(SANDBOX_SAMPLER_ENV) == "0" else "on"
    return {"name": name, "sampler": sampler, "t_create": None, "t_copy_in": None, "t_start_to_exit": None, "t_junit": None, "t_remove": None,
            "mem_peak_bytes": None, "disk_rw_bytes": None, "sampler_error": None}


def parse_size_bytes(text: str | None) -> int | None:
    """Docker's human size ('12.3MB', '1.5GiB', '0B') to bytes; None for anything else."""
    m = re.match(r"\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]+)\s*$", text or "")
    unit = _SIZE_UNITS.get(m.group(2).upper()) if m else None
    return int(float(m.group(1)) * unit) if m and unit else None


def _probe_error(probe: dict, what: str) -> None:
    seen = probe["sampler_error"] or ""
    if what not in seen and len(seen) < 200:
        probe["sampler_error"] = f"{seen}; {what}"[:200].lstrip("; ")


@contextlib.contextmanager
def _timed(probe: dict | None, key: str):
    t0 = time.monotonic()
    try:
        yield
    finally:
        if probe is not None:
            probe[key] = round(time.monotonic() - t0, 3)


class _MemSampler:
    """`docker stats --no-stream` of the container every SANDBOX_SAMPLE_EVERY_S while it runs; the maximum used memory is kept. Any failure
    is written to the probe and swallowed: this thread can never change what the run concludes."""

    def __init__(self, docker: str, ctr: str, denv: dict, probe: dict | None):
        self.docker, self.ctr, self.denv, self.probe = docker, ctr, denv, probe
        self._stop, self._t = threading.Event(), None

    def _once(self) -> None:
        try:
            r = subprocess.run([self.docker, "stats", "--no-stream", "--format", "{{.MemUsage}}", self.ctr], capture_output=True, text=True,
                               timeout=SANDBOX_STATS_TIMEOUT_S, env=self.denv)
            used = parse_size_bytes(r.stdout.split("/")[0]) if r.returncode == 0 else None
            if used is None:
                _probe_error(self.probe, f"docker stats rc={r.returncode} unparsable")
            elif used > 0 and (self.probe["mem_peak_bytes"] is None or used > self.probe["mem_peak_bytes"]):   # 0B: not running yet
                self.probe["mem_peak_bytes"] = used
        except Exception as e:   # noqa: BLE001 — a sampler failure is data in the receipt, never a verdict
            _probe_error(self.probe, f"docker stats {type(e).__name__}")

    def _loop(self) -> None:
        while True:
            self._once()
            if self._stop.wait(SANDBOX_SAMPLE_EVERY_S):
                return

    def __enter__(self):
        if self.probe is not None and self.probe["sampler"] == "on":
            self._t = threading.Thread(target=self._loop, name="localci-mem-sampler", daemon=True)
            self._t.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._t is not None:
            self._t.join(30)


def _probe_layer(docker: str, ctr: str, denv: dict, probe: dict | None) -> None:
    """The container's writable layer (`docker ps -s` SIZE, the part before '(virtual'), read before the container is removed."""
    if probe is None or probe["sampler"] != "on":
        return
    try:
        r = subprocess.run([docker, "ps", "-a", "-s", "--filter", f"name=^{ctr}$", "--format", "{{.Size}}"], capture_output=True, text=True,
                           timeout=SANDBOX_PS_TIMEOUT_S, env=denv)
        size = parse_size_bytes(r.stdout.split("(")[0]) if r.returncode == 0 else None
        if size is None:
            _probe_error(probe, f"docker ps -s rc={r.returncode} unparsable")
        else:
            probe["disk_rw_bytes"] = size
    except Exception as e:   # noqa: BLE001 — as the memory sampler: data, never a verdict
        _probe_error(probe, f"docker ps -s {type(e).__name__}")


def execute_contained(name: str, spec: dict, run_dir: Path, plan: dict, inner: list[str], overrides: dict[str, bytes], extra: dict[str, bytes],
                      env: dict, log: Path, junit: Path, timeout: int, workdir: str = "/w", network: str = "none", image_id: str | None = None,
                      memory: str = "4g", collect=None, paths: set | None = None, files: dict[str, Path] | None = None,
                      probe: dict | None = None) -> tuple[int | None, str | None]:
    """Run candidate code in a fresh container: no bind mount, no network, no capability, non-root, no host environment.
    The tree goes in as a tar stream and only the junit comes out; the host run dir, receipts, credentials and the Pysa
    home are not reachable from inside. Returns (rc, error). `probe` (new_probe) is filled in place with the trusted side's phase times,
    peak memory and layer size (B33 S2): data for the receipt, read by no verdict."""
    iso = spec["isolation"]
    docker = iso["docker"]
    ctr = re.sub(r"[^a-zA-Z0-9_.-]", "-", f"localci-{plan['run_id']}-{name}")[:100] + "-" + os.urandom(4).hex()
    denv = trusted_env()
    create = [docker, "create", "--name", ctr, "--label", "org.nuzantara.localci=candidate", "--label", f"org.nuzantara.localci.run={run_label(run_dir)}",
              "--network", network, "--cap-drop", "ALL", "--init",   # an init reaps orphans, as the hosted runner's does
              "--security-opt", "no-new-privileges", "--user", iso["user"], "--pids-limit", "1024", "--memory", memory, "--workdir", workdir,
              *[f"--env={k}={v}" for k, v in sorted(env.items())], image_id or iso["image_id"], *inner]
    made = False
    try:
        with _timed(probe, "t_create"):
            r = subprocess.run(create, capture_output=True, text=True, timeout=120, env=denv)
        made = r.returncode == 0
        if r.returncode != 0:
            return None, f"container create failed (image {iso['image_id'][:19]} pinned at plan time): {r.stderr.strip()[:300]}"
        with tempfile.TemporaryFile() as errf:   # stderr to a file (no pipe to fill) and a watchdog: a stalled copy-in cannot hang the run
            cp = subprocess.Popen([docker, "cp", "-a", "-", f"{ctr}:/"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errf, env=denv)
            group = [cp]   # ONE budget for the producer (git ls-tree / cat-file) and the consumer (docker cp)
            expired = threading.Event()

            def _expire():
                expired.set()
                for proc in list(group):
                    proc.kill()
            watchdog = threading.Timer(COPY_TIMEOUT_S, _expire)
            t_cp = t_end = time.monotonic()
            t_end += COPY_TIMEOUT_S
            try:
                watchdog.start()
                n = stream_tree_tar(Path(plan["worktree"]), plan["candidate_sha"], cp.stdin, overrides, extra, group, COPY_TIMEOUT_S, paths, files)
                cp.stdin.close()
                cp.wait(timeout=max(1.0, t_end - time.monotonic()))
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as e:
                for proc in group:
                    proc.kill()
                    proc.wait()
                return None, f"candidate tree copy-in failed{' (budget ' + str(COPY_TIMEOUT_S) + 's expired)' if expired.is_set() else ''}: {type(e).__name__}"
            finally:
                if probe is not None:
                    probe["t_copy_in"] = round(time.monotonic() - t_cp, 3)
                watchdog.cancel()
                for proc in group:   # a signal (KeyboardInterrupt) skips the except above: never leave the copy group running
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
            if expired.is_set():
                return None, f"candidate tree copy-in exceeded its {COPY_TIMEOUT_S}s budget"
            errf.seek(0)
            err = errf.read()
        if cp.returncode != 0:
            return None, f"candidate tree copy-in failed (rc={cp.returncode}): {err.decode(errors='replace').strip()[:300]}"
        with open(log, "a") as fh:
            fh.write(f"# isolation=container image={image_id or iso['image_id']} network={network} user={iso['user']} mounts=none tree={plan['candidate_sha']} blobs={n}\n")
            fh.flush()
            try:
                with _MemSampler(docker, ctr, denv, probe), _timed(probe, "t_start_to_exit"):   # the sampler's join is after the clock stops
                    rc = subprocess.run([docker, "start", "-a", ctr], stdout=fh, stderr=subprocess.STDOUT, timeout=timeout, env=denv).returncode
            except subprocess.TimeoutExpired:
                subprocess.run([docker, "kill", ctr], capture_output=True, timeout=60, env=denv)
                tail = "(container killed; removal verified below or the run aborts)"
                if (dead := xdist_dead_worker(log)):   # still no verdict: the reason only names what the log shows died first
                    return None, (f"timeout after {timeout}s — an xdist worker died mid-run ('{dead[0]}', log line {dead[1]}) and the controller "
                                  f"never finished: a memory-cgroup OOM-kill is the measured cause on Pro (2026-10-07/08); no verdict {tail}")
                return None, f"timeout after {timeout}s {tail}"
        with _timed(probe, "t_junit"):
            why = _read_junit_out(docker, ctr, junit)
            if collect is not None:   # artifacts a later job downloads, copied out of the stopped container before it is removed
                why = "; ".join(x for x in (why, collect(docker, ctr)) if x) or None
        if why:
            with open(log, "a") as fh:
                fh.write(f"# junit: {why}\n")
        return rc, None
    finally:
        try:
            if made:
                _probe_layer(docker, ctr, denv, probe)
        finally:   # a signal inside the layer read must still reach the removal
            with _timed(probe, "t_remove"):
                _remove_verified(docker, ctr, denv)


class ContainerCleanupError(RuntimeError):
    """A candidate container may still exist: the run must not start another check next to it."""


def _remove_verified(docker: str, ctr: str, denv: dict) -> None:
    try:
        subprocess.run([docker, "rm", "-f", "-v", ctr], capture_output=True, timeout=120, env=denv)   # -v: its anonymous volumes die with it
        gone = subprocess.run([docker, "container", "inspect", "--format", "{{.Id}}", ctr], capture_output=True, text=True, timeout=60, env=denv)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ContainerCleanupError(f"removal of candidate container {ctr} not verifiable: {type(e).__name__}") from e
    if gone.returncode == 0 or "no such" not in (gone.stderr or "").lower():
        raise ContainerCleanupError(f"candidate container {ctr} still present or its absence unverifiable after docker rm -f -v (inspect rc={gone.returncode})")


def hosted_python(iso: dict) -> str:
    """The interpreter of hosted's scripts/tests run, from the image's extra interpreters; the image default when it carries none."""
    for ver, bindir in sorted((iso.get("pythons") or {}).items()):
        if ver == HOSTED_SCRIPTS_PYTHON or ver.startswith(HOSTED_SCRIPTS_PYTHON + "."):
            return f"{bindir}/python3"
    return "python"


def _execute_candidate_contained(name: str, spec: dict, run_dir: Path, plan: dict, timeout: int, log: Path, junit: Path) -> dict:
    kind = spec["kind"]
    env = {"HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}
    try:   # the spec's cwd, mapped into the frozen tree; a cwd outside the candidate worktree has no contained equivalent
        rel = Path(os.path.realpath(spec.get("cwd") or plan["worktree"])).relative_to(os.path.realpath(plan["worktree"]))
    except ValueError:
        return {"status": "ERROR", "reason": f"cwd {spec.get('cwd')!r} is outside the candidate worktree — not runnable contained", "rc": None, "counts": None}
    workdir = "/w" if str(rel) == "." else f"/w/{rel.as_posix()}"
    overrides: dict[str, bytes] = {}
    extra: dict[str, bytes] = {}
    files: dict[str, Path] = {}
    pack_note, tp = None, None
    for rel in spec.get("trusted_files") or []:
        bp = run_dir / "state" / "trusted" / "base_files" / rel
        blob = bp.read_bytes() if bp.exists() else None   # an empty __init__.py is a blob too
        if blob is None or sha256_bytes(blob) != plan.get("trusted_files_sha256", {}).get(rel):
            return {"status": "ERROR", "reason": f"trusted blob {rel} missing or differs from the plan's sha256", "rc": None, "counts": None}
        overrides[rel] = blob
    if kind == "pytest":
        if not spec.get("modules"):
            return {"status": "ERROR", "reason": "zero test modules selected — missing evidence is not PASS", "rc": None, "counts": {"collected": 0, "executed": 0}}
        py = hosted_python(spec["isolation"])
        notes = []
        if py == "python":
            notes.append(f"# python: the image carries no {HOSTED_SCRIPTS_PYTHON} interpreter — pytest runs on the image default, which is not hosted's\n")
        argv = [py, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--junitxml=/out/junit.xml", *spec["modules"]]
        env["PYTHONPATH"] = workdir
        sweep = spec.get("deps_image")   # hosted's sweep env: its HOME, the offline install of its three lines, ~/logs as collecting the whole directory leaves it
        if sweep:
            env.update(SWEEP_ENV)
            notes.append(f"# env: deps image {sweep[:19]} ({spec.get('deps_note')}); offline install of the sweep's lines, HOME={SWEEP_ENV['HOME']}\n")
        hist = history_delta(Path(plan["worktree"]), plan["base_sha"], plan["candidate_sha"])   # hosted checks the tree out as a repository: so does the sandbox
        if isinstance(hist, str):   # hosted's checkout is depth 1: the indexed tree alone is what it has, so a BASE that cannot be rebuilt is no verdict-changer
            notes.append(f"# history: BASE not rebuilt as a commit ({hist[:160]}) — the tree is indexed alone, as hosted's depth-1 checkout is\n")
            hist = None
        extra["cfg/steps_driver.py"] = STEPS_DRIVER.read_bytes()
        extra["cfg/pytest_indexed.py"] = PYTEST_INDEXED.read_bytes()
        for (rel, _mode, oid), blob in zip((hist or {"base": []})["base"], read_blobs(Path(plan["worktree"]), [o for _, _, o in (hist or {"base": []})["base"]])):
            extra[f"cfg/base/{rel}"] = blob
        tp, files, pack_note = tree_pack_ship_safe(run_dir, plan)
        pack_note = "".join(notes) + (pack_note or "")
        extra["cfg/pytest_indexed.json"] = json.dumps({"root": workdir, "history": hist, "argv": argv, **({"path_prefix": str(Path(py).parent)} if py != "python" else {}),
                                                       **({"install": SWEEP_INSTALL, "home_dirs": ["logs"]} if sweep else {}), **({"tree_pack": tp} if tp else {})}).encode()
        inner = ["python", "-I", "/cfg/pytest_indexed.py", "/cfg/pytest_indexed.json"]
    elif kind == "contained_steps":
        drv = STEPS_DRIVER.read_bytes()
        if sha256_bytes(drv) != spec.get("driver_sha256"):
            return {"status": "ERROR", "reason": "steps driver changed since the plan pinned it", "rc": None, "counts": None}
        extra["cfg/steps_driver.py"] = drv
        hist = spec.get("history") or {"added": [], "base": []}
        for (rel, _mode, oid), blob in zip(hist["base"], read_blobs(Path(plan["worktree"]), [o for _, _, o in hist["base"]])):
            extra[f"cfg/base/{rel}"] = blob
        if spec.get("git_index"):
            tp, files, pack_note = tree_pack_ship_safe(run_dir, plan)
        extra["cfg/steps.json"] = json.dumps({"context": spec["context"], "root": workdir, "git_index": spec.get("git_index"), "history": spec.get("history"),
                                              "path_prefix": spec.get("path_prefix") or "", "venv": bool(spec.get("venv")), "env": spec["env"],
                                              "steps": spec["steps"], **({"tree_pack": tp} if tp else {})}).encode()
        inner = ["python", "-I", "/cfg/steps_driver.py", "/cfg/steps.json", "/out/junit.xml"]
    else:
        extra["cfg/pytest-trusted.ini"] = b"[pytest]\npythonpath = /w\n"
        inner = ["python", "-I", "-m", "pytest", "-p", "no:cacheprovider", "--noconftest", "-c", "/cfg/pytest-trusted.ini", "--rootdir", "/w", "-q",
                 "--junitxml=/out/junit.xml", *[f"/w/{r}" for r in overrides]]
    with open(log, "w") as fh:
        fh.write(f"# {now()} container cmd={' '.join(inner)}\n")
        fh.write(pack_note or "")
    t0, probe = time.monotonic(), new_probe(name)
    try:
        rc, err = execute_contained(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, timeout, workdir, files=files, probe=probe,
                                    image_id=spec.get("deps_image") if kind == "pytest" else None)
    except ContainerCleanupError:
        raise
    except (OSError, subprocess.SubprocessError, RuntimeError) as e:
        rc, err = None, f"container execution failed: {type(e).__name__}: {e}"
    dur = round(time.monotonic() - t0, 3)
    if (full := host_disk_full([log], name)):   # before any verdict: a full disk makes this run no evidence either way
        return {"status": "ERROR", "reason": full, "rc": rc, "duration_s": dur, "counts": None, "log": str(log), "isolation": "container", "sandbox": [probe]}
    if err:
        return {"status": "ERROR", "reason": err, "rc": None, "duration_s": dur, "counts": None, "log": str(log), "isolation": "container", "sandbox": [probe]}
    if kind == "contained_steps":
        steps = parse_step_junit(junit)
        status, reason = classify_contained_steps(rc, steps, spec)
        return {"status": status, "reason": reason + " [contained: candidate-produced junit]", "rc": rc, "duration_s": dur, "counts": None, "steps": steps,
                "log": str(log), "isolation": "container", "sandbox": [probe]}
    counts = parse_junit(junit)
    status, reason = classify_pytest(rc, counts)
    return {"status": status, "reason": reason + " [contained: candidate-produced junit]", "rc": rc, "duration_s": dur, "counts": counts, "log": str(log),
            "isolation": "container", "sandbox": [probe]}


def read_blobs(wt: Path, oids: list) -> list:
    if not oids:
        return []
    r = subprocess.run(["git", "-C", str(wt), "cat-file", "--batch"], input="".join(f"{o}\n" for o in oids).encode(), capture_output=True, check=True,
                       timeout=COPY_TIMEOUT_S)
    out, buf = [], io.BytesIO(r.stdout)
    for o in oids:
        hdr = buf.readline().decode().split()
        if len(hdr) != 3 or hdr[0] != o or hdr[1] != "blob":
            raise RuntimeError(f"BASE blob {o} unreadable: {hdr}")
        out.append(buf.read(int(hdr[2])))
        buf.read(1)
    return out


JUDGE_REWRITTEN_TAIL = "; hosted judges with the candidate's copy, which this run did not execute — no verdict (never FAIL, never OK)"


def judge_rewritten(step: str, spec: dict) -> tuple[list, str]:
    """The rewritten judges one step's verdict was read with, and the scope note. A step reads the trusted files it names
    (`trusted` in its plan); a rewritten file no step names (the workflow itself, a .gitattributes) is read by every step, and so is
    every rewritten file for a step the plan did not attribute (a service context's job step): context scope, said."""
    mod = [str(f) for f in spec.get("judge_modified") or []]
    planned = {s.get("name"): s.get("trusted") for s in spec.get("steps") or [] if isinstance(s, dict)}
    if not isinstance(planned.get(step), list):
        return mod, " (context scope: the plan attributes no judge to this step)"
    named = {f for t in planned.values() if isinstance(t, list) for f in t}
    everyone = [f for f in mod if f not in named]
    return [f for f in mod if f in planned[step]] + everyone, f" (context scope: {everyone} named by no step)" if everyone else ""


IF_FALSE = re.compile(r"^if: .* -> false( \(status [a-z]+\))?$")   # the driver's wording for a step its own `if:` skipped


def _step_key(job, name) -> tuple:
    """A step is named by its job AND its name: two jobs may share a step name, and the N/A one of the first excuses nothing in the second."""
    return (job, name)


def skipped_by_own_if(na: list, spec: dict) -> bool:
    """Whether an all-skipped leg is the gate's skip and nothing else: every NOT_APPLICABLE step is an `if:` the driver evaluated false or a
    step the matrix declares not applicable (the plan's own `not_applicable`), and at least one is an `if:` false: a step that carries an `if:`
    in BASE and was skipped any other way is in neither group. A leg that mixes a gate skip with an unexplained skip is no evidence, so it is not PASS."""
    planned = {_step_key(j.get("job_id"), s.get("name")): s for j in spec.get("jobs") or [] for s in j.get("steps") or [] if isinstance(s, dict)}
    planned.update({_step_key(None, s.get("name")): s for s in spec.get("steps") or [] if isinstance(s, dict)})

    def key_of(n) -> tuple:   # a leg's steps carry their label: "codeql[python] › Initialize CodeQL" is the step of job `codeql`
        label, sep, step = str(n).partition(" › ")
        return _step_key(label.split("[", 1)[0], step) if sep else _step_key(None, label)
    gated = [s for s in na if IF_FALSE.match(str(s.get("reason", "")))]
    rest = [s for s in na if s not in gated]
    return bool(gated) and all("not_applicable" in planned.get(key_of(s["name"]), {}) for s in rest)   # a matrix N/A step carries no `if:` in the plan


def judge_rc0_of(status: str, steps: list | None, spec: dict) -> str | None:
    """B25: the structured answer for a context that ran every step rc=0 with the BASE judge while the candidate rewrites a judge, read from
    the steps' statuses and the plan's ``judge_modified`` and never from any reason text (the junit's strings are the candidate's). BLOCKED, no
    FAIL/ERROR/BLOCKED step, at least one PASS: ``judge_rewritten_base_ok`` for ANY file the BASE judge reads that the candidate rewrote (a judge
    test, a workflow, .gitattributes: the owner's ruling of 2026-10-15). A RED read is ``judge_rewritten`` (steps_verdict), never this. None otherwise."""
    mod = [str(f) for f in spec.get("judge_modified") or []]
    sts = [s.get("status") for s in steps or [] if isinstance(s, dict)]
    if status != "BLOCKED" or not mod or not sts or not isinstance(steps, list) or len(sts) != len(steps) or "PASS" not in sts or any(x not in ("PASS", "NOT_APPLICABLE") for x in sts):
        return None
    return "judge_rewritten_base_ok"


def steps_verdict(steps: list, spec: dict) -> tuple[str, str]:
    """A context is PASS only when every step it runs returned 0 and every other step is NOT_APPLICABLE with a reason. A red step
    dominates (FAIL > ERROR > BLOCKED); a verdict read with a BASE judge the candidate rewrites is claimed in neither direction:
    a green is BLOCKED as before, and from B5 a red step whose own judge is rewritten is BLOCKED judge_rewritten, never FAIL."""
    rewritten = {s["name"]: hit for s in steps if spec.get("judge_modified") and s["status"] in ("FAIL", "ERROR")
                 and (hit := judge_rewritten(s["name"], spec))[0]}
    for status in ("FAIL", "ERROR", "BLOCKED"):
        bad = [s for s in steps if s["status"] == status and s["name"] not in rewritten]
        if status == "BLOCKED" and rewritten:
            return "BLOCKED", ("judge_rewritten: " + "; ".join(f"{n} read red with the BASE judge while the candidate rewrites {f}{scope}"
                                                               for n, (f, scope) in rewritten.items())[:600] + JUDGE_REWRITTEN_TAIL
                               + (f"; {len(bad)} step(s) BLOCKED: " + "; ".join(f"{s['name']} ({s['reason']})" for s in bad)[:300] if bad else ""))
        if bad:
            return status, f"{len(bad)} step(s) {status}: " + "; ".join(f"{s['name']} ({s['reason']})" for s in bad)[:600]
    ran = [s for s in steps if s["status"] == "PASS"]
    na = [s for s in steps if s["status"] == "NOT_APPLICABLE"]
    # a job whose per-leg gate skips every step still reports success hosted (CodeQL's RUN_THIS_LANGUAGE): the plan declares it, and only an
    # `if:` evaluated false here may stand for it (the driver words such a skip "if: ... -> false"), never a step the matrix marks N/A
    if not ran and spec.get("skip_is_pass") and na and len(na) == len(steps) and skipped_by_own_if(na, spec) \
            and all(written_reason(s.get("reason")) is not None for s in na):
        if spec.get("judge_modified"):
            return "BLOCKED", f"every step skipped by the job's own `if:`, but the candidate rewrites {spec['judge_modified']}: no green claimed"
        return "PASS", f"0 step(s) ran: the job's own `if:` skipped them, as hosted ({len(na)} not applicable): " + "; ".join(f"{s['name']} ({s['reason']})" for s in na)[:400]
    if not ran or len(ran) + len(na) != len(steps) or any(written_reason(s.get("reason")) is None for s in na):
        return "ERROR", f"{len(ran)} step(s) ran, {len(na)} not applicable of {len(steps)} — no executed step or an unexplained one is not PASS"
    if spec.get("judge_modified"):
        return "BLOCKED", (f"{len(ran)} step(s) rc=0 with the BASE judge, but the candidate rewrites {spec['judge_modified']}: hosted judges with "
                           "the candidate's copy, which this run did not execute — no green claimed")
    return "PASS", f"{len(ran)} step(s) rc=0" + ("; not applicable: " + "; ".join(f"{s['name']} ({s['reason']})" for s in na) if na else "")


def host_disk_full(logs, label: str) -> str | None:
    """The no-verdict reason when a sandbox's output carries a disk-full error line, else None. Read line by line in order; a
    postgres `recovery mode` line is counted only after such a line (alone it is the candidate's or the service's own failure)."""
    first, n, recovery = None, 0, 0
    for log in logs:
        if not log or not Path(log).is_file():
            continue
        with open(log, errors="replace") as fh:
            for line in fh:
                if DISK_FULL_LINE.search(line):
                    first, n = first or line.strip(), n + 1
                elif first and RECOVERY_LINE.search(line):
                    recovery += 1
    if first is None:
        return None
    return (f"host_disk_full: {label}: {first[:200]!r} ({n} disk-full line(s), {recovery} postgres recovery-mode line(s) after it) — "
            "the docker host ran out of disk: no verdict on the candidate (never FAIL, never OK); free space and run again")


def parse_step_junit(p: Path) -> list | None:
    try:
        root = ET.parse(p).getroot()
    except (OSError, ET.ParseError):
        return None
    out = []
    for tc in root.iter("testcase"):
        f, e, k = tc.find("failure"), tc.find("error"), tc.find("skipped")
        err = "ERROR" if e is not None and e.get("type") == "signal" else "BLOCKED"   # killed by a signal: no verdict; never started: BLOCKED
        node, status = next(((n, s) for n, s in ((f, "FAIL"), (e, err), (k, "NOT_APPLICABLE")) if n is not None), (None, "PASS"))
        out.append({"name": tc.get("name"), "status": status, "reason": node.get("message", "") if node is not None else "rc=0",
                    "seconds": float(tc.get("time") or 0)})
    return out


def classify_contained_steps(rc: int | None, steps: list | None, spec: dict) -> tuple[str, str]:
    """The driver's exit code and its junit must tell the same story about the planned steps, or there is no verdict."""
    if rc is None or rc < 0 or rc == 2:
        return "ERROR", f"steps driver rc={rc} — not a verdict on the candidate"
    if steps is None:
        return "ERROR", "no readable step junit — missing evidence is not PASS"
    planned = [(s["name"], "not_applicable" in s) for s in spec["steps"]]
    if [(s["name"], s["status"] == "NOT_APPLICABLE") for s in steps] != planned:
        return "ERROR", f"the junit lists {len(steps)} step(s) that are not the {len(planned)} planned ones in order"
    have = {s["status"] for s in steps}
    want = 1 if "FAIL" in have else 4 if "ERROR" in have else 3 if "BLOCKED" in have else 0
    if rc != want:
        return "ERROR", f"steps driver rc={rc} contradicts its junit (expected {want})"
    return steps_verdict(steps, spec)


def _execute_trusted_steps(spec: dict, timeout: int, log: Path) -> dict:
    tdir = Path(spec["trusted_dir"])
    if full_dir_map(tdir) != spec.get("trusted_dir_sha256"):   # rewritten judge, added or missing file: not the BASE evidence
        return {"status": "ERROR", "reason": "trusted dir tampered: its files differ from the sha256 map recorded at plan time", "rc": None, "counts": None}
    if (gone := [p for p in (spec.get("tool_sha256") or {}) if not os.path.isfile(p)]):
        return {"status": "BLOCKED", "reason": f"pinned tool(s) {gone} could not start: gone since the plan measured them", "rc": None, "counts": None}
    if (moved := [p for p, h in (spec.get("tool_sha256") or {}).items() if sha256_file(Path(p)) != h]):
        return {"status": "ERROR", "reason": f"pinned tool(s) {moved} changed since the plan measured them", "rc": None, "counts": None}
    base_env = {k: v for k, v in os.environ.items() if not is_secret_env(k)}
    results = []
    t0 = time.monotonic()
    with open(log, "w") as fh:
        for s in spec["steps"]:
            if "not_applicable" in s:
                results.append({"name": s["name"], "status": "NOT_APPLICABLE", "reason": s["not_applicable"], "seconds": 0.0})
                continue
            cwd = os.path.join(spec["cwd"], s.get("cwd") or ".")
            fh.write(f"# {now()} step {s['name']!r} cwd={cwd} cmd={' '.join(s['argv'])}\n")
            fh.flush()
            s0, rc = time.monotonic(), None
            try:
                rc = subprocess.run(s["argv"], cwd=cwd, env=trusted_env({**base_env, **s.get("env", {})}), stdout=fh, stderr=subprocess.STDOUT,
                                    timeout=max(1.0, t0 + timeout - time.monotonic())).returncode
                status, reason = ("PASS", "rc=0") if rc == 0 else ("ERROR", f"crashed (signal {-rc})") if rc < 0 else ("FAIL", f"rc={rc}")
            except OSError as e:
                status, reason = "BLOCKED", f"could not start: {e}"
            except subprocess.TimeoutExpired:
                status, reason = "ERROR", f"timeout ({timeout}s budget for the context)"
            results.append({"name": s["name"], "status": status, "reason": reason, "rc": rc, "seconds": round(time.monotonic() - s0, 3)})
    status, reason = steps_verdict(results, spec)
    return {"status": status, "reason": reason, "rc": next((r["rc"] for r in results if r.get("rc")), 0 if status == "PASS" else None),
            "duration_s": round(time.monotonic() - t0, 3), "counts": None, "steps": results, "log": str(log)}


def reap_containers(plan: dict, store: Store) -> str | None:
    """A coordinator killed with -9 never reached its `docker rm -f -v`: remove THIS run dir's leftover candidate containers before
    resuming. Returns why that could not be verified (the caller refuses to run candidate code next to an unknown survivor)."""
    iso = isolation_of(plan)
    if iso.get("mode") != "container" or not iso.get("docker"):
        return None
    flt = ["--filter", f"label=org.nuzantara.localci.run={run_label(store.run_dir)}"]
    try:
        ls = subprocess.run([iso["docker"], "ps", "-aq", *flt], capture_output=True, text=True, timeout=60, env=trusted_env())
        if ls.returncode != 0:
            return f"docker ps rc={ls.returncode}: {ls.stderr.strip()[:200]}"
        ids = ls.stdout.split()
        if ids:
            subprocess.run([iso["docker"], "rm", "-f", "-v", *ids], capture_output=True, timeout=120, env=trusted_env())
            left = subprocess.run([iso["docker"], "ps", "-aq", *flt], capture_output=True, text=True, timeout=60, env=trusted_env())
            if left.returncode != 0 or left.stdout.split():
                return f"{len(left.stdout.split())} orphan candidate container(s) survived docker rm -f -v"
            store.journal({"event": "orphan_containers_removed", "count": len(ids), "at": now()})
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{type(e).__name__}: {e}"
    return None


def start_services(docker: str, svcs: list, prefix: str, label: str, denv: dict, log: Path) -> tuple[list, str | None, str | None]:
    """(containers, netns owner, why-not). The first service owns a loopback-only network namespace (`--network none`); the other
    services and then the job join it, so `localhost:<port>` reaches them exactly as the hosted job reaches its mapped ports, and no
    container of the run has an interface to anything else. Healthy within the BASE health budget, or the job does not start."""
    names, owner = [], None
    for s in svcs:
        ctr = re.sub(r"[^a-zA-Z0-9_.-]", "-", f"{prefix}-svc-{s['name']}")[:110] + "-" + os.urandom(3).hex()
        h = s["health"]
        argv = [docker, "run", "-d", "--name", ctr, "--label", "org.nuzantara.localci=service", "--label", f"org.nuzantara.localci.run={label}",
                "--network", f"container:{owner}" if owner else "none", "--health-cmd", h["cmd"], "--health-interval", h["interval"],
                "--health-timeout", h["timeout"], "--health-retries", h["retries"], *[f"--env={k}={v}" for k, v in sorted(s["env"].items())], s["image_id"]]
        names.append(ctr)   # before docker is asked: a run that times out may still have created it, and the caller removes it
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=120, env=denv)
        except (OSError, subprocess.TimeoutExpired) as e:
            return names, owner, f"service {s['name']} did not start: {type(e).__name__}"
        if r.returncode != 0:
            return names, owner, f"service {s['name']} did not start (image {s['image_id'][:19]}): {r.stderr.strip()[:200]}"
        owner = owner or ctr
    for s, ctr in zip(svcs, names):
        t0, state = time.monotonic(), "starting"
        while state == "starting" and time.monotonic() - t0 < s["health_budget_s"]:
            time.sleep(0.5)
            state = (_try([docker, "inspect", "--format", "{{.State.Health.Status}}", ctr]) or "gone").strip()
        with open(log, "a") as fh:
            fh.write(f"# service {s['name']} ({s['local_image']} {s['image_id'][:19]} for {s['image']}): {state} after {time.monotonic() - t0:.1f}s\n")
        if state != "healthy":
            return names, owner, f"service {s['name']} is {state!r} after {time.monotonic() - t0:.0f}s (BASE health check, budget {s['health_budget_s']:.0f}s)"
        if (sd := s.get("seed")):   # the matrix's stand-in, once healthy: its one empty collection, made by the container itself (its own key, no host variable)
            script = SEED_SCRIPT % (sd["size"], sd["distance"], sd["collection"], sd["api_key_env"])
            r = _try([docker, "exec", ctr, "bash", "-c", script + " && echo seeded"], 60)
            with open(log, "a") as fh:
                fh.write(f"# service {s['name']}: seeded empty collection {sd['collection']} ({sd['size']}, {sd['distance']}): {'ok' if r and 'seeded' in r else 'FAILED'}\n")
            if not r or "seeded" not in r:
                return names, owner, f"service {s['name']} could not be seeded with collection {sd['collection']}: no verdict"
    return names, owner, None


def _collect_dir(docker: str, ctr: str, src: str) -> tuple[dict, str | None]:
    """Regular files under `src` in the stopped container, by relative path, size-capped — what upload-artifact would have kept."""
    p = subprocess.Popen([docker, "cp", f"{ctr}:{src.rstrip('/')}/.", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=trusted_env())
    watchdog, files, total = threading.Timer(COPY_TIMEOUT_S, p.kill), {}, 0
    try:
        watchdog.start()
        with tarfile.open(fileobj=p.stdout, mode="r|") as t:
            for m in t:
                rel = "/".join(x for x in m.name.split("/") if x not in ("", "."))
                if not m.isfile() or not rel:
                    continue
                total += m.size
                if total > ARTIFACT_MAX_BYTES:
                    return files, f"artifact {src} exceeds {ARTIFACT_MAX_BYTES} bytes"
                files[safe_tree_path(rel)] = t.extractfile(m).read()
    except (tarfile.TarError, OSError, RuntimeError) as e:
        return files, f"artifact copy-out of {src} failed: {type(e).__name__}"
    finally:
        watchdog.cancel()
        p.kill()
        p.wait()
    return files, None


def parse_expr_junit(p: Path) -> list | None:
    """The driver's junit in expression mode: a skipped case is NOT_APPLICABLE (with the condition that skipped it), a passed case
    marked outcome=failure is a continue-on-error step (its job did not fail), `cpu` is the step's CPU seconds."""
    steps = parse_step_junit(p)
    if steps is None:
        return None
    for s, tc in zip(steps, ET.parse(p).getroot().iter("testcase")):
        s["cpu"] = float(tc.get("cpu") or 0)
        if tc.get("outcome") == "failure":
            s["reason"] = "continue-on-error: " + ((tc.findtext("system-out") or "").strip() or "outcome failure")
    return steps


def _run_leg(name: str, spec: dict, job: dict, leg: dict, run_dir: Path, plan: dict, needs: dict, arts: dict, X) -> dict:
    """One job (one matrix leg) in a fresh sandbox with fresh services: rc, steps, artifacts; `infra` set when there is no verdict."""
    label = job["job_id"] + (f"[{','.join(str(v) for v in leg.values())}]" if leg else "")
    slug = re.sub(r"[^A-Za-z0-9_.-]", "-", label)
    log, junit = run_dir / "logs" / f"{name}.{slug}.log", run_dir / "receipts" / f"{name}.{slug}.junit.xml"
    junit.unlink(missing_ok=True)
    iso, denv, t0 = spec["isolation"], trusted_env(), time.monotonic()
    ctx = {**spec["expr"], "matrix": dict(leg), "needs": {j: needs[j] for j in job["needs"]}}
    drv, exs = STEPS_DRIVER.read_bytes(), GH_EXPR.read_bytes()
    out = {"label": label, "rc": None, "steps": [], "seconds": 0.0, "cpu": 0.0, "infra": None, "log": str(log), "logs": [str(log)], "sandbox": []}
    if sha256_bytes(drv) != spec["driver_sha256"] or sha256_bytes(exs) != spec["expr_sha256"]:
        out["infra"] = ("ERROR", "steps driver or gh_expr changed since the plan pinned them")
        return out
    base_extra: dict[str, bytes] = {"cfg/steps_driver.py": drv, "cfg/gh_expr.py": exs}
    hist = spec.get("history") or {"added": [], "base": []}
    for (rel, _mode, _oid), blob in zip(hist["base"], read_blobs(Path(plan["worktree"]), [o for _, _, o in hist["base"]])):
        base_extra[f"cfg/base/{rel}"] = blob
    env = {"HOME": "/tmp", "LANG": "C.UTF-8"}
    inner = ["python", "-I", "/cfg/steps_driver.py", "/cfg/steps.json", "/out/junit.xml"]
    cfg_base = {"root": "/w", "path_prefix": job["path_prefix"], "venv": job["venv"], "env": {**CONTAINED_STEP_ENV, **SERVICE_STEP_ENV},
                "job_env": job["job_env"], "expr": ctx}
    steps, gen = [], {}
    for st in job["steps"]:
        st = dict(st)
        if st.get("env"):
            st["env"] = fill_generated(st["env"], gen)
        if (st.get("side") or {}).get("where") == "egress":
            st["precomputed"] = _run_egress(name, spec, job, st, slug, cfg_base, base_extra, env, inner, run_dir, plan, out["sandbox"])
            out["logs"].append(str(run_dir / "logs" / f"{name}.{slug}.egress.log"))   # written by this leg: read for a full disk too
        st.pop("side", None)   # B25-prime P4: host-side metadata (incl. $GATE_LEDGER path) stays in plan.json, never shipped into /cfg/steps.json
        steps.append(st)
    extra = dict(base_extra)
    for st in steps:
        em = st.get("emulate") or {}
        if em.get("action") == "download":
            dest = safe_tree_path(X.substitute(em["path"], ctx))
            for aname, files in sorted(arts.items()):
                if fnmatch.fnmatchcase(aname, X.substitute(em["pattern"] or em["name"], ctx)):
                    extra.update({f"w/{dest}/{'' if em['merge'] else aname + '/'}{rel}": b for rel, b in files.items()})
    overrides: dict[str, bytes] = {}
    for rel in spec.get("overlay") or []:   # BASE's copy of a judge, laid over the candidate's: the plan froze its sha256
        bp = run_dir / "state" / "trusted" / "base_files" / rel
        blob = bp.read_bytes() if bp.exists() else None
        if blob is None or sha256_bytes(blob) != plan.get("trusted_files_sha256", {}).get(rel):
            out["infra"] = ("ERROR", f"trusted blob {rel} missing or differs from the plan's sha256")
            return out
        overrides[rel] = blob
    indexed = job.get("git_index", True)   # a job that reads no git history (CodeQL) gets the bare tree, as `git archive` hands the probe
    tp, files, pack_note = tree_pack_ship_safe(run_dir, plan) if indexed else (None, {}, "")
    extra["cfg/steps.json"] = json.dumps({**cfg_base, "context": f"{spec['context']} / {label}", "git_index": indexed, "history": spec.get("history"),
                                          "checkout": job.get("checkout"), "steps": steps, **({"tree_pack": tp} if tp else {})}).encode()
    uploads = [(X.substitute(em["name"], ctx), X.substitute(em["path"], ctx)) for em in (s.get("emulate") or {} for s in steps) if em.get("action") == "upload"]

    def collect(docker: str, ctr: str) -> str | None:
        why = []
        for aname, path in uploads:
            files, err = _collect_dir(docker, ctr, path if path.startswith("/") else f"/w/{path}")
            arts[aname] = files
            why += [err] if err else []
        return "; ".join(why) or None

    ctrs, owner, unreached = [], None, None
    try:
        with open(log, "w") as fh:
            fh.write(f"# {now()} {label}: image {job['image_id'][:19]} services {[s['name'] for s in job['services']]}\n")
            fh.write(pack_note or "")
        if (floor := disk_floor_refusal(iso["docker"], iso["image_id"], run_dir)):   # before any container of this leg exists
            with open(log, "a") as fh:
                fh.write(f"# not started: {floor}\n")
            out["infra"] = ("BLOCKED", floor)
            return out
        ctrs, owner, why = start_services(iso["docker"], [{**sv, "env": fill_generated(sv["env"], gen)} for sv in job["services"]], f"localci-{plan['run_id']}-{name}-{slug}", run_label(run_dir), denv, log)
        if why:
            out["infra"] = ("BLOCKED", f"{label}: {why}")
            return out
        out["sandbox"].append(probe := new_probe(f"{name}.{slug}"))
        rc, err = execute_contained(f"{name}.{slug}", spec, run_dir, plan, inner, overrides, extra, env, log, junit, job["timeout_s"], "/w",
                                    network=f"container:{owner}" if owner else "none", image_id=job["image_id"], memory=spec.get("memory", "4g"),
                                    collect=collect if uploads else None, files=files, probe=probe)
        for sv, c in zip(job["services"], ctrs):   # before teardown: what the stand-in was asked, counted by the stand-in
            if sv.get("reached"):
                seen = requests_seen(iso["docker"], c, sv["reached"])
                with open(log, "a") as fh:
                    fh.write(f"# service {sv['name']}: answered {seen} x {sv['reached']['request']} (2xx), needs >= {sv['reached']['min']}\n")
                if seen is None or seen < sv["reached"]["min"]:
                    unreached = f"service {sv['name']} answered {'an unreadable count of' if seen is None else seen} {sv['reached']['request']} (needs >= {sv['reached']['min']}): the backend never reached it"
    finally:
        for c in ctrs:
            try:
                _remove_verified(iso["docker"], c, denv)
            except Exception as e:   # noqa: BLE001 — one stuck service must not keep the others alive; the run reaper sweeps by label
                with open(log, "a") as fh:
                    fh.write(f"# service {c} not removed: {type(e).__name__}\n")
    out["seconds"] = round(time.monotonic() - t0, 3)
    if err:
        out["infra"] = ("ERROR", f"{label}: {err}")
        return out
    got = parse_expr_junit(junit)
    want = 1 if got and any(s["status"] == "FAIL" for s in got) else 4 if got and any(s["status"] == "ERROR" for s in got) else \
        3 if got and any(s["status"] == "BLOCKED" for s in got) else 0
    if rc is None or rc < 0 or rc == 2 or got is None or [s["name"] for s in got] != [s["name"] for s in steps] or rc != want:
        out["infra"] = ("ERROR", f"{label}: driver rc={rc}, junit {'unreadable' if got is None else f'{len(got)} case(s), expected rc {want}'} — no verdict")
        return out
    for s, planned in zip(got, steps):   # B12: the flag the plan froze, carried to the step it answered — never read from the junit's text
        if s["status"] == "BLOCKED" and (planned.get("precomputed") or {}).get("gate_pending") is True:
            s["gate_pending"] = True
    out.update(rc=rc, steps=got, cpu=round(sum(s["cpu"] for s in got), 3))
    if want == 0 and (pw := job.get("playwright_skips")):   # a pass whose skips are not exactly BASE's selection's is not hosted's work
        sm = step_summary(Path(log).read_text(errors="replace"), pw["step"])
        if sm is None or sm["skipped"] != pw["skipped"]:
            out["infra"] = ("BLOCKED", f"{label}: {pw['step']} " + ("printed no Playwright summary" if sm is None else f"expected {pw['skipped']} skipped (BASE's selection), saw {sm['skipped']}")
                            + " — more skips than BASE's (a credential-gated test.skip runs hosted) or fewer (BASE changed: update `playwright_skips` with it) is no verdict, never PASS")
            return out
    if want == 0 and unreached:   # the claim of a hermetic run is that the SET paths ran: a stand-in nobody asked is the old path under a new name
        out["infra"] = ("BLOCKED", f"{label}: {unreached}")
    return out


def gate_pending_of(status: str, steps: list) -> bool:
    """B12: a context is gate_pending only when it is BLOCKED and EVERY step that did not pass is a reader whose plan-frozen answer was
    "no verdict posted yet": another BLOCKED step (or a red one) stays BLOCKED after the post, so deciding again would change nothing."""
    bad = [s for s in steps if s["status"] not in ("PASS", "NOT_APPLICABLE")]
    return status == "BLOCKED" and bool(bad) and all(s.get("gate_pending") is True for s in bad)


def _run_egress(name: str, spec: dict, job: dict, st: dict, slug: str, cfg_base: dict, base_extra: dict, env: dict, inner: list,
                run_dir: Path, plan: dict, probes: list | None = None) -> dict:
    """A step that needs the network (pip-audit asks a vulnerability service) runs alone in a sandbox on the default bridge: no
    service, no git history, only the candidate files it names (data), and tools the plan proved are BASE's pins. Its rc is folded
    into the job's own run at its position, under the step's own `if:`."""
    one = {k: v for k, v in st.items() if k not in ("side", "if")}
    junit = run_dir / "receipts" / f"{name}.{slug}.egress.junit.xml"
    log = run_dir / "logs" / f"{name}.{slug}.egress.log"
    junit.unlink(missing_ok=True)
    extra = {k: v for k, v in base_extra.items() if not k.startswith("cfg/base/")}
    extra["cfg/steps.json"] = json.dumps({**cfg_base, "context": f"{spec['context']} / {slug} / egress", "steps": [one]}).encode()
    with open(log, "w") as fh:
        fh.write(f"# {now()} egress step {st['name']!r}: inputs {st['side']['inputs']}, rewrites {st['side']['rewrite']}\n")
    probe = new_probe(f"{name}.{slug}.egress")
    if probes is not None:
        probes.append(probe)
    rc, err = execute_contained(f"{name}.{slug}.egress", spec, run_dir, plan, inner, {}, extra, env, log, junit, st.get("timeout_s") or job["timeout_s"],
                                "/w", network="bridge", image_id=job["image_id"], probe=probe, memory=spec.get("memory", "4g"), paths=set(st["side"]["inputs"]))
    got = parse_expr_junit(junit) if not err else None
    tail = log.read_text(errors="replace")[-4000:] if log.exists() else ""
    if err or not got or len(got) != 1 or got[0]["name"] != st["name"] or (rc, got[0]["status"]) not in ((0, "PASS"), (1, "FAIL")):
        return {"rc": None, "reason": f"egress sandbox gave no consistent verdict: {err or f'rc={rc}, junit {got}'}", "log": tail}
    full = log.read_text(errors="replace") if log.exists() else ""
    if rc == 1 and not re.search(r"^Found [1-9][0-9]* known vulnerabilit|^Name +Version +ID", full, re.M) and (  # a finding is a verdict, network or not; the clean line is not one
            net := re.search(r"(ReadTimeoutError|ConnectTimeoutError|NewConnectionError|Max retries exceeded|Temporary failure in name "
                             r"resolution)[^\n]{0,120}", full)):
        return {"rc": None, "reason": f"the network failed the egress step, not the candidate ({net.group(0)[:100]}): no verdict (never green), re-run", "log": tail}
    return {"rc": rc, "reason": f"egress sandbox: {got[0]['reason']}", "log": tail}


def _job_rows(legs: list) -> list:
    return [{**{k: x[k] for k in ("label", "rc", "seconds", "cpu")}, "sandbox": x.get("sandbox") or []} for x in legs]


def _execute_jobs(name: str, spec: dict, run_dir: Path, plan: dict, log: Path) -> dict:
    """The context's jobs in BASE `needs:` order, legs one after another (parallelism 1: the measured capacity of this host), each
    in its own sandbox; the context's own job last, with its upstreams' results and artifacts. An upstream with no verdict (a service
    that never got healthy, a sandbox that broke) stops the chain: the context is ERROR/BLOCKED, never red on the candidate's account."""
    X = _gh_expr()
    needs, arts, legs, t0 = {k: dict(v) for k, v in (spec.get("needs") or {}).items()}, {}, [], time.monotonic()
    for job in spec["jobs"]:
        mine = []
        for leg in job["legs"]:
            r = _run_leg(name, spec, job, leg, run_dir, plan, needs, arts, X)
            legs.append(r)
            if (full := host_disk_full(r.get("logs") or [r.get("log")], r["label"])):   # the chain stops: nothing after it is evidence
                return {"status": "ERROR", "reason": full, "rc": None, "duration_s": round(time.monotonic() - t0, 3), "counts": None, "log": r["log"],
                        "jobs": _job_rows(legs), "isolation": "container"}
            if r["infra"]:
                st, why = r["infra"]
                return {"status": st, "reason": why, "rc": None, "duration_s": round(time.monotonic() - t0, 3), "counts": None, "log": r["log"],
                        "jobs": _job_rows(legs), "isolation": "container"}
            mine.append(r)
        needs[job["job_id"]] = {"result": "success" if all(r["rc"] == 0 for r in mine) else "failure", "outputs": {}}
    combined = [{**s, "name": f"{r['label']} › {s['name']}"} for r in legs for s in r["steps"]]
    status, reason = steps_verdict(combined, spec)
    if (coe := [s["name"] for s in combined if s["status"] == "PASS" and s["reason"].startswith("continue-on-error")]):
        reason += f"; continue-on-error, failed without failing the job (as hosted): {coe}"
    with open(log, "w") as fh:
        fh.writelines(f"# {r['label']}: rc={r['rc']} {r['seconds']}s cpu={r['cpu']}s log={r['log']}\n" for r in legs)
    found = {m.group(1): {"results": int(m.group(2)), "rules": int(m.group(3))} for r in legs if r.get("log") and Path(r["log"]).is_file()
             for m in CODEQL_RESULTS.finditer(Path(r["log"]).read_text(errors="replace"))}   # data for the receipt, never part of the verdict
    return {"status": status, "reason": reason + " [contained: candidate-produced junit]", "rc": max(r["rc"] for r in legs),
            "duration_s": round(time.monotonic() - t0, 3), "counts": None, "steps": combined, "log": str(log), "isolation": "container",
            **({"codeql": found} if found else {}),
            "jobs": _job_rows(legs), **({"gate_pending": True} if gate_pending_of(status, combined) else {})}


def execute(name: str, spec: dict, run_dir: Path, plan: dict, timeout: int) -> dict:
    timeout = spec.get("timeout_s") or timeout   # a context's budget is its hosted job's timeout-minutes, else the run-wide default
    log = run_dir / "logs" / f"{name}.log"
    junit = run_dir / "receipts" / f"{name}.junit.xml"
    junit.unlink(missing_ok=True)   # a junit left by an earlier attempt is never this attempt's evidence
    kind = spec["kind"]
    if kind == "contained_jobs":
        if (spec.get("isolation") or {}).get("mode") != "container":
            return {"status": "ERROR", "reason": "contained jobs planned without a container", "rc": None, "counts": None}
        return _execute_jobs(name, spec, run_dir, plan, log)
    if kind in CANDIDATE_KINDS and (spec.get("isolation") or {}).get("mode") == "container":
        return _execute_candidate_contained(name, spec, run_dir, plan, timeout, log, junit)
    if kind == "trusted_steps":
        return _execute_trusted_steps(spec, timeout, log)
    if kind == "contained_steps":
        return {"status": "ERROR", "reason": "contained steps planned without a container", "rc": None, "counts": None}
    envx = {k: v for k, v in os.environ.items() if not is_secret_env(k)}
    envx["PYTHONDONTWRITEBYTECODE"] = "1"  # kind "pytest" runs CANDIDATE tests (PYTHONPATH=cwd on purpose): they are not a trusted check
    cwd = spec.get("cwd") or plan["worktree"]
    if kind == "pytest":
        if not spec.get("modules"):
            return {"status": "ERROR", "reason": "zero test modules selected — missing evidence is not PASS", "rc": None, "counts": {"collected": 0, "executed": 0}}
        cmd = [spec["python"], "-m", "pytest", "-p", "no:cacheprovider", "-q", f"--junitxml={junit}", *spec["modules"]]
        envx["PYTHONPATH"] = cwd
    elif kind == "trusted_pytest":
        blobs: dict[str, bytes] = {}
        for rel in spec["trusted_files"]:
            bp = run_dir / "state" / "trusted" / "base_files" / rel
            blob = bp.read_bytes() if bp.exists() else None
            if blob is None or sha256_bytes(blob) != plan.get("trusted_files_sha256", {}).get(rel):
                return {"status": "ERROR", "reason": f"trusted blob {rel} missing or differs from the plan's sha256", "rc": None, "counts": None}
            blobs[rel] = blob
        overlay = run_dir / "state" / "trusted" / "overlay" / name
        shutil.rmtree(overlay, ignore_errors=True)
        build_overlay(Path(cwd), overlay, blobs)
        ini = run_dir / "state" / "trusted" / "pytest-trusted.ini"
        ini.write_text(f"[pytest]\npythonpath = {shlex.quote(cwd)}\n")
        cmd = [spec["python"], "-I", "-m", "pytest", "-p", "no:cacheprovider", "--noconftest", "-c", str(ini), "--rootdir", cwd, "-q",
               f"--junitxml={junit}", *[str(overlay / r) for r in blobs]]
        envx = trusted_env(envx)
    elif kind == "cmd":
        cmd = spec["cmd"]
        envx = trusted_env(envx)
        if spec.get("trusted_pythonpath"):  # a directory of BASE-ref files only (PYTHONSAFEPATH drops the script dir)
            tdir = Path(spec["trusted_pythonpath"])
            have = trusted_dir_map(tdir, spec.get("trusted_dir_sha256") or {})
            if have != (spec.get("trusted_dir_sha256") or {}):   # rewritten judge, added shadow module (json.py) or missing file: not the BASE evidence
                return {"status": "ERROR", "reason": "trusted dir tampered: its files differ from the sha256 map recorded at plan time", "rc": None, "counts": None}
            envx["PYTHONPATH"] = str(tdir)
    else:
        return {"status": "ERROR", "reason": f"unknown check kind {kind!r}", "rc": None, "counts": None}
    t0 = time.monotonic()
    try:
        with open(log, "w") as fh:
            fh.write(f"# {now()} cwd={cwd} cmd={' '.join(cmd)}\n")
            fh.flush()
            rc = subprocess.run(cmd, cwd=cwd, env=envx, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout).returncode
    except OSError as e:
        return {"status": "ERROR", "reason": f"unexecutable: {e}", "rc": None, "duration_s": round(time.monotonic() - t0, 3), "counts": None, "log": str(log)}
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "reason": f"timeout after {timeout}s", "rc": None, "duration_s": round(time.monotonic() - t0, 3), "counts": None, "log": str(log)}
    dur = round(time.monotonic() - t0, 3)
    if kind in ("pytest", "trusted_pytest"):
        counts = parse_junit(junit)
        status, reason = classify_pytest(rc, counts)
    else:
        counts = None
        if rc == 0:
            status, reason = "PASS", "rc=0"
        elif rc < 0:
            status, reason = "ERROR", f"crashed (signal {-rc})"
        elif rc in (spec.get("error_rcs") or []):
            status, reason = "ERROR", f"tool error rc={rc} (declared error_rcs={spec['error_rcs']}) — missing evidence is not a verdict"
        else:
            status, reason = "FAIL", f"rc={rc}"
    return {"status": status, "reason": reason, "rc": rc, "duration_s": dur, "counts": counts, "log": str(log)}


def mark_interrupted(name: str, c: dict, why: str | None = None) -> None:
    pid, started = c.get("pid"), c.get("started_at")
    reason = why or f"coordinator interrupted while RUNNING (pid {pid} dead, started_at {started}) — never PASS"
    c.setdefault("history", []).append({"attempt": c.get("attempts", 0), "status": "INTERRUPTED", "reason": reason, "started_at": started, "pid": pid, "ended_at": now()})
    c.update(status="INTERRUPTED", reason=reason, at=now(), last_pid=pid)
    c.pop("pid", None)
    c.pop("pid_started", None)


def reap_interrupted(st: dict, store: Store | None = None) -> list[str]:
    """Any RUNNING check whose recorded pid is dead becomes INTERRUPTED. Persists when a store is given."""
    hit = []
    for name, c in st["checks"].items():
        if c["status"] == "RUNNING" and not pid_alive(int(c.get("pid") or 0), c.get("pid_started")):
            mark_interrupted(name, c)
            hit.append(name)
            if store:
                store.journal({"event": "interrupted_check_detected", "check": name, "attempts": c.get("attempts", 0), "at": now()})
    if hit and store:
        store.save(st)
    return hit


def _verify_receipt(run_dir: Path, name: str, c: dict, st: dict, cur_hash: str) -> str | None:
    """Return None when the PASS of an executable check is backed by a valid receipt, else the reason it is not."""
    rp = c.get("receipt")
    if not rp or not Path(rp).exists():
        return "PASS without a receipt file"
    try:
        r = json.loads(Path(rp).read_text())
    except ValueError:
        return "receipt unreadable"
    claimed = r.pop("receipt_sha256", None)
    if claimed != sha256_json(r):
        return "receipt sha256 does not match its content"
    b = r.get("binding", {})
    for k in ("candidate_sha", "tree_sha", "base_sha"):
        if b.get(k) != st["binding"][k]:
            return f"receipt {k} differs from the run binding"
    if b.get("plan_hash") != st["plan_hash"]:
        return "receipt plan_hash differs from the run plan"
    if r.get("result", {}).get("status") != "PASS":
        return "receipt does not record PASS"
    if r.get("env_hash") != cur_hash:
        return f"env drift (receipt env_hash {str(r.get('env_hash'))[:12]} != current {cur_hash[:12]})"
    return None


IMPORTABLE = {".py", ".pyc", ".so", ".pyd", ".dylib"}


def trusted_dir_map(td: Path, recorded: dict | None = None) -> dict:
    """What can decide a trusted interpreter's imports from `td`: every recorded file (any depth), plus every top-level importable
    file and every package (dir with __init__.py). Scratch the runner itself writes there (overlay/, *.ini) is not import material."""
    out = {rel: (sha256_file(td / rel) if (td / rel).is_file() else "<missing>") for rel in (recorded or {})}
    if not td.is_dir():
        return out
    for f in sorted(td.iterdir()):
        if f.is_file() and f.name not in out and (recorded is None or f.suffix in IMPORTABLE):
            out[f.name] = sha256_file(f)
        elif f.is_dir() and (f / "__init__.py").exists():
            for g in sorted(f.rglob("*")):
                if g.is_file() and str(g.relative_to(td)) not in out:
                    out[str(g.relative_to(td))] = sha256_file(g)
    return out


TRUSTED_KINDS = ("cmd", "trusted_steps")   # the kinds whose verdict no candidate code can touch: BASE judge/classifier (or a version-pinned
# tool) under -I on a sha-mapped dir, reading the candidate tree as data.
# `trusted_pytest` takes its TEST from BASE but exercises the CANDIDATE's implementation (the ban test exec_module()s the candidate's
# scripts/check_ban_predicates.py) — candidate code runs inside it, so it executes AFTER the seal, like `pytest` (fresh gate #3, 2026-09-27).
SEALED_KINDS = ("cmd", "record", "trusted_steps")   # record = plan-time policy verdicts (change_map, N/A and BLOCKED reasons): sealed too
SEAL_MIN_PREFIX = 12


def trusted_seal(run_dir: Path, plan: dict, st: dict) -> str:
    """sha256 over plan.json + every `cmd` and `record` check's state entry and receipt bytes. Printed by `run` BEFORE candidate code executes; the
    operator keeps it outside run_dir and `status --seal` re-derives it — candidate code that rewrites state/receipts after the flock is
    released cannot rewrite what the operator already read."""
    h = hashlib.sha256((run_dir / "state" / "plan.json").read_bytes())
    for name in sorted(plan["checks"]):
        if plan["checks"][name]["kind"] not in SEALED_KINDS:
            continue
        c = st["checks"].get(name, {})
        h.update(json.dumps({"n": name, "s": c.get("status"), "r": c.get("reason"), "rc": c.get("rc")}, sort_keys=True).encode())
        rp = c.get("receipt")
        h.update(Path(rp).read_bytes() if rp and Path(rp).exists() else b"<no receipt>")
    return h.hexdigest()


def coordinator_python(plan: dict) -> str:
    """The interpreter the coordinator itself executes (env fingerprint, pip freeze): from a runner-planned check, never an extra."""
    return next((s["python"] for s in plan["checks"].values() if s.get("python") and not s.get("extra")), sys.executable)


def is_trusted_check(spec: dict) -> bool:
    """A runner-planned `cmd` (BASE judge/classifier). An `--extra-check` cmd is the operator's and may run candidate code on the host."""
    return spec.get("kind") in TRUSTED_KINDS and not spec.get("extra")


def runs_candidate_code(spec: dict) -> bool:
    return spec.get("kind") in CANDIDATE_KINDS or (spec.get("kind") == "cmd" and bool(spec.get("extra")))


def seal_unsupported(plan: dict) -> str | None:
    """Why no seal can vouch for this plan (None = it can). Uncontained candidate code — an --isolation none/legacy plan, or an
    extra `cmd` run on the host — can reset the run dir to a state no marker distinguishes from a fresh one (spec §8)."""
    mode = isolation_of(plan).get("mode")
    if mode != "container":
        return f"uncontained plan (isolation={mode})"
    extras = sorted(n for n, s in plan["checks"].items() if s.get("kind") == "cmd" and s.get("extra"))
    if extras:
        return f"extra host command(s) {', '.join(extras)} run uncontained"
    return None


def candidate_exposure(plan: dict, st: dict) -> dict | None:
    """Has candidate code executed against this run dir? The state marker is written BEFORE the first candidate check starts; any
    candidate check with an attempt, history or receipt counts too (an uncontained candidate could have erased the marker, not all
    of them). `mode` is the weakest isolation any candidate check ran under: one uncontained check makes the whole run dir uncontained."""
    exp = dict(st["candidate_exposure"]) if isinstance(st.get("candidate_exposure"), dict) else None
    for name, spec in plan["checks"].items():
        if not runs_candidate_code(spec):
            continue
        c = st["checks"].get(name, {})
        if c.get("attempts") or c.get("history") or c.get("receipt"):
            exp = exp or {"at": c.get("at"), "check": name, "mode": "none", "inferred": True}
            if (spec.get("isolation") or {}).get("mode") != "container":
                exp["mode"] = "none"
    if exp and seal_unsupported(plan):
        exp["mode"] = "none"
    return exp


def cmd_run(a):
    run_dir = Path(a.run_dir).resolve()
    store = Store(run_dir)
    plan = load_plan_verified(run_dir)

    def _term(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    old = {s: signal.signal(s, _term) for s in (signal.SIGTERM, signal.SIGINT)} if _main_thread() else {}
    try:
        with store.lock():
            st = store.load()
            reap_interrupted(st, store)
            if (why := reap_containers(plan, store)):
                sys.exit(f"refusing to run: cannot verify that no candidate container of this run dir survives ({why})")
            wt = Path(plan["worktree"])
            deadline_at = plan["created_epoch"] + a.deadline_s if a.deadline_s is not None else plan["deadline_at"]
            if a.deadline_s is not None:
                st["deadline_override_s"] = a.deadline_s
            max_attempts = plan.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
            if a.only:
                if a.only not in plan["checks"]:
                    sys.exit(f"unknown check {a.only!r}")
                names = [a.only]
            else:
                names = [n for n, c in st["checks"].items() if c["status"] in ("QUEUED", "INTERRUPTED")]
            names = sorted(names, key=lambda n: (not is_trusted_check(plan["checks"][n]), plan["checks"][n]["kind"] != "trusted_pytest"))  # cmd → seal → trusted_pytest → pytest
            venv_py = coordinator_python(plan)
            cur_env = env_fingerprint(venv_py, plan["checks"])
            cur_hash = env_hash(cur_env)
            sealed = False

            def seal_now(why: str) -> None:
                nonlocal sealed
                sealed = True
                if (unsup := seal_unsupported(plan)):
                    # uncontained/legacy: a lingering same-user process can reset this run dir to a state no marker distinguishes from a
                    # fresh plan (review round 2), so no seal minted here could vouch for it — none is (docs/specs/localci-completion §8)
                    store.journal({"event": "seal_withheld", "why": why, "at": now()})
                    print(f"seal WITHHELD  # {why}: {unsup} — no trusted seal is minted; "
                          "plan with --isolation container for one", flush=True)
                    return
                seal = trusted_seal(run_dir, plan, st)
                exp, first = candidate_exposure(plan, st), st.get("seal_first")
                if exp is None:   # no candidate code has run against this run dir: minting (or re-minting) is legitimate
                    st["seal"] = seal
                    st["seal_first"] = {"seal": seal, "at": now(), "why": why}
                    store.journal({"event": "seal", "seal": seal, "why": why, "at": now()})
                    store.save(st)
                    print(f"seal={seal}  # {why}: record this outside the run dir; `status --seal {seal[:12]}…` re-derives it", flush=True)   # before candidate code runs: a kill -9 must not eat it in a pipe buffer
                    return
                if exp.get("mode") == "container" and first and first.get("seal") == seal:
                    store.journal({"event": "seal_verified", "seal": seal, "why": why, "first_at": first.get("at"), "at": now()})
                    print(f"seal={seal}  # {why}: UNCHANGED since {first.get('at')} — candidate code ran only in containers, nothing new minted", flush=True)
                    return
                why_not = "the trusted evidence no longer re-derives the seal minted before candidate code ran"
                st["seal_refused"] = {"at": now(), "why": why, "reason": why_not}
                store.journal({"event": "seal_refused", "why": why, "reason": why_not, "exposure": exp, "at": now()})
                store.save(st)
                print(f"seal REFUSED  # {why}: {why_not} (exposed {exp.get('at')}); the only valid seal is the one printed before that — "
                      "check it with `status --seal <it>`, or plan a fresh run dir", flush=True)

            for name in names:
                spec, c = plan["checks"][name], st["checks"][name]
                if spec["kind"] not in EXECUTABLE:
                    continue
                if is_trusted_check(spec) and (exp := candidate_exposure(plan, st)) is not None:
                    # a trusted verdict produced after candidate code ran would be covered by no seal: never mint one, never re-run one
                    why_not = f"trusted check not run: candidate code already executed in this run dir ({exp.get('mode')}, {exp.get('at')}) — plan a fresh run dir"
                    if c["status"] in ("QUEUED", "INTERRUPTED"):
                        c.update(status="BLOCKED", reason=why_not, at=now())
                        store.save(st)
                    store.journal({"event": "trusted_rerun_refused", "check": name, "at": now()})
                    print(f"{name}: REFUSED — {why_not}")
                    continue
                if not is_trusted_check(spec) and not sealed:
                    seal_now("trusted checks done, candidate code about to run")
                if runs_candidate_code(spec) and candidate_exposure(plan, st) is None:
                    st["candidate_exposure"] = {"at": now(), "check": name, "mode": ((spec.get("isolation") or {}).get("mode") or "none")}
                    store.journal({"event": "candidate_exposure", **st["candidate_exposure"]})
                    store.save(st)
                if c["status"] == "RUNNING":
                    continue
                if c["status"] == "INTERRUPTED":
                    over_attempts = c.get("attempts", 0) >= max_attempts
                    over_deadline = time.time() > deadline_at
                    if over_attempts or over_deadline:
                        c.update(status="ERROR", at=now(), reason=f"retry budget exhausted: attempts={c.get('attempts', 0)}/{max_attempts} deadline_exceeded={over_deadline}; stays blocking")
                        store.journal({"event": "retry_budget_exhausted", "check": name, "at": now()})
                        store.save(st)
                        print(f"{name}: ERROR — {c['reason']}")
                        continue
                    c.update(status="QUEUED", reason="re-queued after interruption (within retry budget)", at=now())
                ident = identity(wt)
                b = st["binding"]
                if ident["candidate_sha"] != b["candidate_sha"] or ident["tree_sha"] != b["tree_sha"] or ident["dirty"]:
                    c.update(status="BLOCKED", reason=f"worktree moved: HEAD={ident['candidate_sha'][:12]} tree={ident['tree_sha'][:12]} dirty={ident['dirty']}", at=now())
                    c.pop("judge_no_verdict", None)
                    c.pop("gate_pending", None)
                    store.save(st)
                    continue
                attempt = c.get("attempts", 0) + 1
                started = now()
                c.update(status="RUNNING", reason="executing", at=started, pid=os.getpid(), pid_started=proc_start(os.getpid()), started_at=started, attempts=attempt)
                c.pop("gate_pending", None)   # B12: a flag is this attempt's answer, never an earlier one's
                c.pop("judge_no_verdict", None)
                store.save(st)
                try:
                    res = execute(name, spec, run_dir, plan, a.timeout)
                except KeyboardInterrupt as e:
                    mark_interrupted(name, c, f"coordinator received {e} while RUNNING (attempt {attempt}, started_at {started})")
                    store.journal({"event": "interrupted_by_signal", "check": name, "at": now()})
                    store.save(st)
                    raise
                except ContainerCleanupError as e:
                    c.update(status="ERROR", reason=f"{e} — run aborted before any further check", at=now())
                    c.pop("pid", None)
                    c.pop("pid_started", None)
                    store.journal({"event": "cleanup_unverified_abort", "check": name, "at": now()})
                    store.save(st)
                    sys.exit(f"{name}: ERROR — {e}; aborting the run (no further check starts next to a possibly surviving container)")
                except Exception as e:  # noqa: BLE001 — a crashing executor is ERROR, never a silent skip
                    res = {"status": "ERROR", "reason": f"executor crashed: {type(e).__name__}: {e}", "rc": None, "counts": None}
                receipt = {"check": name, "run_id": st["run_id"], "binding": {**b, "plan_hash": st["plan_hash"], "trusted_classifier_sha256": plan["trusted_classifier_sha256"]},
                           "env": cur_env, "env_hash": cur_hash, "attempt": attempt, "result": res, "finished_at": now(), "spec": spec}
                receipt["receipt_sha256"] = sha256_json(receipt)
                rp = run_dir / "receipts" / f"{name}.json"
                atomic_write(rp, json.dumps(receipt, indent=2, sort_keys=True))
                c.setdefault("history", []).append({"attempt": attempt, "status": res["status"], "reason": res["reason"], "started_at": started, "ended_at": now(), "pid": os.getpid()})
                c.update(status=res["status"], reason=res["reason"], at=now(), receipt=str(rp), rc=res.get("rc"), duration_s=res.get("duration_s"), counts=res.get("counts"), log=res.get("log"),
                         **({"judge_no_verdict": jv} if (jv := judge_rc0_of(res["status"], res.get("steps"), spec)) else {}),
                         steps=res.get("steps"), **({"gate_pending": True} if res.get("gate_pending") is True else {}))
                c.pop("pid", None)
                c.pop("pid_started", None)
                store.save(st)
                print(f"{name}: {res['status']} — {res['reason']} ({res.get('duration_s')}s)")
            if names:
                seal_now("end of run")
    finally:
        remove_tree_pack(run_dir)
        for s, h in old.items():
            signal.signal(s, h)


def _main_thread() -> bool:
    import threading

    return threading.current_thread() is threading.main_thread()


# ------------------------------------------------------------------ review import
def cmd_review(a):
    run_dir = Path(a.run_dir).resolve()
    store = Store(run_dir)
    plan = load_plan_verified(run_dir)
    raw = Path(a.file).read_bytes()
    file_sha = sha256_bytes(raw)
    with store.lock():
        st = store.load()
        c = st["checks"]["review.independent"]
        b = st["binding"]
        copy = run_dir / "receipts" / "review.independent.json"
        atomic_write(copy, raw.decode("utf-8", "replace"))

        def done(status: str, reason: str):
            c.setdefault("history", []).append({"status": status, "reason": reason, "review_sha256": file_sha, "ended_at": now()})
            c.update(status=status, reason=reason, at=now(), receipt=str(copy), review_sha256=file_sha)
            store.save(st)
            print(f"review.independent: {status} — {reason}")

        try:
            rev = json.loads(raw)
            if not isinstance(rev, dict):
                raise ValueError("top level is not an object")
        except ValueError as e:
            return done("BLOCKED", f"review file is not a JSON object: {e}")
        want = {"reviewed_candidate_sha": b["candidate_sha"], "reviewed_tree_sha": b["tree_sha"], "reviewed_base_sha": b["base_sha"]}
        bad = [f"{k}={str(rev.get(k))[:12]!r} != {v[:12]}" for k, v in want.items() if rev.get(k) != v]
        if bad:
            return done("BLOCKED", "review is not bound to this candidate identity: " + "; ".join(bad))
        seat = rev.get("reviewer_seat")
        if not isinstance(seat, str) or not seat.strip():
            return done("BLOCKED", "reviewer_seat missing or empty")
        builders = {s.strip().lower() for s in ([plan.get("builder_seat")] if plan.get("builder_seat") else []) + list(plan.get("builder_seats") or [])}
        if rev.get("builder_seat"):
            builders.add(str(rev["builder_seat"]).strip().lower())
        if not plan.get("builder_seat"):
            return done("BLOCKED", "plan recorded no builder_seat — reviewer != builder cannot be proven (plan --builder-seat)")
        if seat.strip().lower() in builders or seat.strip().lower() == "builder":
            return done("BLOCKED", f"reviewer seat {seat!r} is a builder seat — generator is never grader")
        verdict = rev.get("verdict")
        summary = str(rev.get("summary", ""))[:160]
        if verdict == "PASS":
            return done("PASS", f"reviewed by {seat}: {summary}")
        if verdict == "FAIL":
            return done("FAIL", f"reviewer {seat} verdict=FAIL: {summary}")
        return done("BLOCKED", f"verdict must be exactly 'PASS' or 'FAIL', got {verdict!r}")


# ----------------------------------------------------------------------- status
def freshness(st: dict, plan: dict, run_dir: Path, cur_hash: str) -> tuple[dict, dict]:
    ident = identity(Path(plan["worktree"]))
    b = st["binding"]
    stale_reason = None
    if ident["candidate_sha"] != b["candidate_sha"]:
        stale_reason = f"candidate moved {b['candidate_sha'][:12]} -> {ident['candidate_sha'][:12]}"
    elif ident["tree_sha"] != b["tree_sha"]:
        stale_reason = f"tree moved {b['tree_sha'][:12]} -> {ident['tree_sha'][:12]}"
    elif ident["dirty"]:
        stale_reason = "worktree dirty: " + ",".join(ident["dirty_paths"][:5])
    view = {}
    for name, c in st["checks"].items():
        v = dict(c)
        kind = plan["checks"].get(name, {}).get("kind")
        if stale_reason and c["status"] in ("PASS", "FAIL", "NOT_APPLICABLE"):
            v["status"], v["reason"] = "STALE", f"{stale_reason}; previous={c['status']}: {c['reason']}"
        elif c["status"] == "PASS" and kind in EXECUTABLE:
            why = _verify_receipt(run_dir, name, c, st, cur_hash)
            if why and why.startswith("env drift"):
                v["status"], v["reason"] = "STALE", f"{why}; previous=PASS: {c['reason']}"
            elif why:
                v["status"], v["reason"] = "ERROR", f"{why} — a PASS without a valid receipt is not PASS"
        elif c["status"] == "PASS" and kind == "review":
            cp = Path(c.get("receipt") or "")
            if not cp.exists() or sha256_file(cp) != c.get("review_sha256"):
                v["status"], v["reason"] = "BLOCKED", "review copy missing or changed since import"
        view[name] = v
    return view, {"worktree_now": ident, "stale_reason": stale_reason}


def evaluate_contexts(view: dict, plan: dict) -> dict:
    status = plan.get("contexts_status", "missing")
    out = {"status": status, "reason": plan.get("contexts_reason", ""), "required": plan.get("required_contexts"), "results": {}, "uncovered": [], "blocked": [], "red": []}
    if status != "ok":
        return out
    for name, ctx in plan["contexts_map"].items():
        chk = resolve_context_check(name, ctx, view)
        mapping = ctx["mapping"]
        # the BASE matrix's coverage rides on the verdict: a partial OK is an OK on a subset, never counted as a full one
        cov = {"coverage": ctx.get("coverage") or "unrecorded", **({"coverage_note": ctx["coverage_note"]} if ctx.get("coverage_note") else {})}
        if mapping in ("blocked", "not_implemented"):
            out["results"][name] = {"mapping": mapping, "check": chk, "verdict": "BLOCKED", **cov}
            out["blocked"].append(name)
            continue
        if chk is None:
            out["results"][name] = {"mapping": mapping, "check": None, "verdict": "UNCOVERED", **cov}
            out["uncovered"].append(name)
            continue
        s, reason = view[chk]["status"], view[chk].get("reason") or ""
        ok = s == "PASS" or (s == "NOT_APPLICABLE" and reason.strip() != "")
        out["results"][name] = {"mapping": mapping, "check": chk, "verdict": "OK" if ok else s, **cov}
        if s == "NOT_APPLICABLE" and isinstance(skip := ((plan.get("checks") or {}).get(chk) or {}).get("skipped"), str):
            out["results"][name]["skipped"] = skip   # satisfied as on GitHub, and said: the classifier decided, nothing ran
        if s in ("ERROR", "BLOCKED") and (host := HOST_NO_VERDICT.match(reason)):   # the host failed, not the candidate: named, no verdict
            out["results"][name]["no_verdict"] = host.group(0)
        elif s == "BLOCKED" and reason.startswith("judge_rewritten: "):   # a red read with a BASE judge the candidate rewrites (B5)
            out["results"][name]["no_verdict"] = "judge_rewritten"
        elif s == "BLOCKED" and view[chk].get("judge_no_verdict") in ("judge_rewritten_base_ok", "judge_rewritten"):   # B25: the structured flag, never the text
            out["results"][name]["no_verdict"] = view[chk]["judge_no_verdict"]
        elif s == "BLOCKED" and view[chk].get("gate_pending") is True:   # B12: the structured flag of the context's result, never its text
            out["results"][name]["no_verdict"] = "gate_pending"
        if not ok:
            (out["red"] if s == "FAIL" else out["blocked"]).append(name)
    return out


def overall(view: dict, plan: dict | None = None) -> str:
    s = {v["status"] for v in view.values()}
    if not s:
        return "BLOCKED"
    if "FAIL" in s:
        return "FAIL"
    if s & BLOCKING:
        return "BLOCKED"
    if any(v["status"] == "NOT_APPLICABLE" and not (v.get("reason") or "").strip() for v in view.values()):
        return "BLOCKED"
    if plan is None:
        return "PASS" if s <= {"PASS", "NOT_APPLICABLE"} else "BLOCKED"
    ctx = evaluate_contexts(view, plan)
    if ctx["status"] == "invalid":
        return "BLOCKED"
    if ctx["status"] == "missing":
        return "SUBSET_PASS"
    if ctx["red"]:
        return "FAIL"
    if ctx["blocked"]:
        return "BLOCKED"
    if ctx["uncovered"]:
        return "SUBSET_PASS"
    return "PASS"


def compute_status(run_dir: Path, write: bool = True) -> dict:
    run_dir = Path(run_dir).resolve()
    store = Store(run_dir)
    plan = load_plan_verified(run_dir)
    lk = store.lock(blocking=False)
    try:
        st = store.load()
        reap_interrupted(st, store if lk else None)
    finally:
        if lk:
            lk.close()
    venv_py = coordinator_python(plan)
    cur_env = env_fingerprint(venv_py, plan["checks"])
    cur_hash = env_hash(cur_env)
    view, fr = freshness(st, plan, run_dir, cur_hash)
    ctx = evaluate_contexts(view, plan)
    out = {"run_id": st["run_id"], "generated_at": now(), "overall": overall(view, plan), "candidate_sha": st["binding"]["candidate_sha"],
           "base_sha": st["binding"]["base_sha"], "tree_sha": st["binding"]["tree_sha"], "plan_hash": st["plan_hash"], "env": cur_env,
           "env_hash": cur_hash, "env_hash_plan": st.get("env_hash"), "builder_seat": plan.get("builder_seat"), "freshness": fr, "contexts": ctx,
           "checks": {n: {k: v.get(k) for k in ("status", "reason", "rc", "duration_s", "counts", "steps", "receipt", "log", "at", "attempts",
                                                     "review_sha256")} for n, v in view.items()}}
    if write:
        atomic_write(run_dir / "status.json", json.dumps(out, indent=2, sort_keys=True))
        atomic_write(run_dir / "status.html", render_html(out))
    return out


def cmd_status(a):
    out = compute_status(Path(a.run_dir))
    run_dir = Path(a.run_dir).resolve()
    plan, st = load_plan_verified(run_dir), Store(run_dir).load()
    recomputed = trusted_seal(run_dir, plan, st)
    unsup = seal_unsupported(plan)
    supported = unsup is None
    exp = candidate_exposure(plan, st)
    out["seal"] = recomputed if supported else None
    out["seal_diagnostic"] = None if supported else recomputed
    out["isolation"] = {k: isolation_of(plan).get(k) for k in ("mode", "image", "image_id", "reason")}
    out["candidate_exposure"] = exp
    out["seal_note"] = ("recomputed now; compare it with the seal `run` printed" if supported else
                        f"{unsup}: seal evidence is unsupported (docs/specs/localci-completion §8); the value is diagnostic only")
    atomic_write(run_dir / "status.json", json.dumps(out, indent=2, sort_keys=True))
    if a.seal and len(a.seal.strip()) < SEAL_MIN_PREFIX:
        sys.exit(f"--seal needs at least {SEAL_MIN_PREFIX} hex characters (a short prefix would match almost anything)")
    if a.seal and not supported:   # a seal-dependent verdict on an uncontained plan fails closed, match or not
        out["overall"] = "BLOCKED"
        out["freshness"]["stale_reason"] = (f"seal evidence unsupported for an uncontained plan ({unsup}); "
                                            f"diagnostic: recomputed {'matches' if recomputed.startswith(a.seal.strip()) else 'differs from'} the value given")
        atomic_write(run_dir / "status.json", json.dumps(out, indent=2, sort_keys=True))
    elif a.seal and not recomputed.startswith(a.seal.strip()):
        out["overall"] = "BLOCKED"
        out["freshness"]["stale_reason"] = f"seal mismatch: trusted evidence changed after the seal you recorded ({a.seal.strip()[:12]}… vs {out['seal'][:12]}…)"
        atomic_write(run_dir / "status.json", json.dumps(out, indent=2, sort_keys=True))
    if a.quiet:
        print(out["overall"])
    else:
        print(json.dumps({"overall": out["overall"], "stale_reason": out["freshness"]["stale_reason"], "seal": out["seal"], "seal_diagnostic": out["seal_diagnostic"],
                          "seal_note": out["seal_note"],
                          "isolation": out["isolation"]["mode"], "candidate_exposure": exp, "contexts": out["contexts"]["status"],
                          "checks": {n: v["status"] for n, v in out["checks"].items()}}, indent=1))
    return 0 if (not a.strict or out["overall"] == "PASS") else 1


COLORS = {"PASS": "#1a7f37", "SUBSET_PASS": "#9a6700", "FAIL": "#cf222e", "ERROR": "#cf222e", "BLOCKED": "#9a6700", "STALE": "#9a6700",
          "INTERRUPTED": "#bc4c00", "NOT_APPLICABLE": "#57606a", "QUEUED": "#57606a", "RUNNING": "#0969da"}


def render_html(out: dict) -> str:
    e = html.escape
    rows = []
    for n, v in sorted(out["checks"].items()):
        c = v.get("counts") or {}
        rows.append(f"<tr><td><code>{e(n)}</code></td><td style='color:{COLORS.get(v['status'], '#000')};font-weight:700'>{e(v['status'])}</td>"
                    f"<td>{e(v.get('reason') or '')}</td><td>{v.get('rc') if v.get('rc') is not None else ''}</td>"
                    f"<td>{c.get('collected', '')}/{c.get('executed', '')}/{c.get('failures', '')}/{c.get('skipped', '')}</td>"
                    f"<td>{v.get('attempts') or ''}</td><td>{v.get('duration_s') or ''}</td></tr>")
    ctx = out["contexts"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>local-ci {e(out['run_id'])}</title>
<style>body{{font:14px system-ui;margin:24px;max-width:1200px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}}th{{background:#f6f8fa}}code{{font-size:12px}}</style></head>
<body><h1>local-ci — <span style="color:{COLORS.get(out['overall'], '#000')}">{e(out['overall'])}</span></h1>
<p>run <code>{e(out['run_id'])}</code> · {e(out['generated_at'])} · host {e(str(out['env']['hostname']))} · runner v{e(out['env']['runner_version'])}</p>
<p>candidate <code>{out['candidate_sha']}</code><br>base <code>{out['base_sha']}</code><br>tree <code>{out['tree_sha']}</code><br>plan <code>{out['plan_hash'][:16]}</code> · env <code>{out['env_hash'][:16]}</code></p>
<p>freshness: {e(out['freshness']['stale_reason'] or 'bound identity matches worktree')}<br>contexts: {e(ctx['status'])} · uncovered {len(ctx['uncovered'])} · blocked {len(ctx['blocked'])}</p>
<table><tr><th>check</th><th>status</th><th>reason</th><th>rc</th><th>collected/executed/failed/skipped</th><th>attempts</th><th>s</th></tr>{''.join(rows)}</table>
<p style="color:#57606a">PASS needs every check PASS or NOT_APPLICABLE-with-reason AND every required context covered. SUBSET_PASS is not PASS.</p></body></html>"""


PARENT_PID_ENV = "LOCALCI_PARENT_PID"
PARENT_POLL_S = 5


def parent_gone(pid: int) -> bool:
    """B15: the merger that started this runner is gone (a bootout or `kickstart -k` kills the job's group, not the runner's
    own session): ESRCH is gone, EPERM is a live process of someone else."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def watch_parent(poll_s: float = PARENT_POLL_S, environ=None) -> threading.Thread | None:
    """B15: when the merger's pid (``LOCALCI_PARENT_PID``) disappears, SIGTERM this runner's own process group — the runner then
    marks its checks INTERRUPTED and removes its container in its `finally`. No env var, no watcher: an older merger changes nothing."""
    raw = (os.environ if environ is None else environ).get(PARENT_PID_ENV, "")
    if not raw.isdigit() or int(raw) <= 1:
        return None
    pid = int(raw)

    def loop():
        while not parent_gone(pid):
            time.sleep(poll_s)
        try:
            os.killpg(os.getpgrp(), signal.SIGTERM) if os.getpgrp() == os.getpid() else os.kill(os.getpid(), signal.SIGTERM)
        except OSError:
            pass

    t = threading.Thread(target=loop, name="localci-parent-watch", daemon=True)
    t.start()
    return t


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="localci")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--candidate")
    p.add_argument("--python")
    p.add_argument("--builder-seat")
    p.add_argument("--builder-seats", help="comma-separated extra builder/contributor seats")
    p.add_argument("--contexts-file")
    p.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    p.add_argument("--deadline-s", type=float, default=DEFAULT_DEADLINE_S)
    p.add_argument("--trusted-pytest", action="append", help="extra base-ref test file to run against the candidate tree")
    p.add_argument("--extra-check", action="append")
    p.add_argument("--pysa-home", help=f"Pysa home built by pysa_check.py setup (default {DEFAULT_PYSA_HOME})")
    p.add_argument("--isolation", choices=ISOLATIONS, default="container",
                   help="where candidate code (pytest, trusted_pytest) runs: a mount-less, network-less container (default) or, explicitly, as the operator")
    p.add_argument("--isolation-image", default=DEFAULT_ISOLATION_IMAGE, help="docker image for --isolation container; pinned by ID at plan time")
    p.add_argument("--pr-number", type=int, help="the pull request the candidate merges (merge_group.head_ref names it, as the queue does)")
    p.add_argument("--gate-ledger", default=str(DEFAULT_GATE_LEDGER), help="Pro gate-verdict ledger path for host readers ($GATE_LEDGER)")
    p.add_argument("--head", help="the decided PR head sha for host readers ($HEAD; defaults to the candidate sha)")
    p.set_defaults(fn=cmd_plan)
    r = sub.add_parser("run")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--only")
    r.add_argument("--timeout", type=int, default=900)
    r.add_argument("--deadline-s", type=float, default=None, help="override the plan's total run deadline (seconds after plan creation)")
    r.set_defaults(fn=cmd_run)
    v = sub.add_parser("review")
    v.add_argument("--run-dir", required=True)
    v.add_argument("--file", required=True)
    v.set_defaults(fn=cmd_review)
    s = sub.add_parser("status")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--quiet", action="store_true")
    s.add_argument("--strict", action="store_true", help="exit 1 unless overall is PASS")
    s.add_argument("--seal", help=f"the seal `run` printed (prefix of >= {SEAL_MIN_PREFIX} chars ok): overall becomes BLOCKED when the trusted evidence no longer re-derives it")
    s.set_defaults(fn=cmd_status)
    a = ap.parse_args(argv)
    if a.cmd in ("plan", "run"):
        watch_parent()
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
