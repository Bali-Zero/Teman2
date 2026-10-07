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
import fcntl
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

RUNNER_VERSION = "0.5.0"
STATUSES = ("QUEUED", "RUNNING", "PASS", "FAIL", "ERROR", "BLOCKED", "STALE", "INTERRUPTED", "NOT_APPLICABLE")
BLOCKING = {"ERROR", "BLOCKED", "STALE", "RUNNING", "QUEUED", "INTERRUPTED"}
EXECUTABLE = ("pytest", "trusted_pytest", "cmd", "trusted_steps", "contained_steps")
# kinds in which CANDIDATE code executes (trusted_pytest: BASE test, candidate implementation; contained_steps: a required context's steps)
CANDIDATE_KINDS = ("pytest", "trusted_pytest", "contained_steps")
ISOLATIONS = ("container", "none")
DEFAULT_ISOLATION_IMAGE = "localci-candidate:1"   # scripts/localci/candidate.Dockerfile
SANDBOX_UID = 65534
JUNIT_MAX_BYTES = 32 << 20
COPY_TIMEOUT_S = 600
MAPPINGS = ("executed", "not_applicable_rule", "blocked", "not_implemented")
RESERVED_CHECK_PREFIXES = ("policy.", "tests.", "review.", "trusted.")  # planned by the runner itself, never by --extra-check
RUNNER_OWNED_KEYS = frozenset({"extra", "isolation", "trusted_pythonpath", "trusted_dir_sha256", "trusted_files"})
EXTRA_CHECK_KINDS = ("cmd", "pytest")  # an extra check must EXECUTE something: a `record` extra would be a verdict without evidence
EXTRA_CHECK_NAME = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z0-9][a-z0-9_-]*)+$")  # no whitespace/case twins of a planned name ("security.pysa_python " is not a new check)
TRUSTED_PYSA_FILES = ["scripts/localci/pysa_check.py", "scripts/localci/pysa/taint.config", "scripts/localci/pysa/fastapi_sources_sinks.pysa",
                      "scripts/localci/pysa/site_packages.txt"]  # taken from BASE: a candidate cannot weaken the taint models that judge it
PYSA_SCOPE = "apps/backend-rag/backend/"
DEFAULT_PYSA_HOME = Path.home() / ".nuzantara-pilots" / "local-ci" / "pysa-home"
TRUSTED_CLASSIFIER_FILES = [
    "scripts/ci/change_map.py", "scripts/ci/test_change_map.py", "scripts/ci/security_gate_flags.py",
    "scripts/ci/hotzone_changed_files.sh", "scripts/ci/impact_map.py", "scripts/ci/test_impact_map.py",
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
            tools[name] = {"image_id": iso.get("image_id"), "docker": tool_identity(iso.get("docker") or "docker")}
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
        cmap[name] = {"mapping": mapping, "local": local, "check": local.get("check") if isinstance(local.get("check"), str) else None, "note": note,
                      "workflow_file": it.get("workflow_file"), "job_id": it.get("job_id")}
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
MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
IMPLICIT_USES = ("actions/checkout@", "actions/setup-python@")   # stood in for by the tree copy and the image/host interpreter
STEPS_DRIVER = Path(__file__).with_name("steps_driver.py")
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


def resolve_steps(job: dict, local: dict, base: str, run_defaults: dict | None = None,
                  wf_env: dict | None = None) -> tuple[list | None, str | None]:
    """Account for EVERY step of the BASE workflow job, in matrix order: a transcribed `argv`, the BASE `run:` body verbatim (written
    to a script file and run with GitHub's shell template), or `not_applicable` with a reason. A step the matrix does not name, a
    `not_run` step, duplicate step names, or an expression the runner does not evaluate makes the context BLOCKED — the local verdict
    never covers less than the job and still calls itself the job's. A step's `if:` is recorded, not evaluated: running a step
    GitHub might skip can only add red, never hide it. Env merges as GitHub does: workflow, job, step, then the matrix's overrides;
    a job that runs in its own `container:`, beside `services:`, or on another runner image is not emulated."""
    if (shape := [k for k in ("container", "services") if job.get(k)]) or job.get("runs-on") not in HOSTED_RUNNERS:
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
            if not isinstance(st["not_applicable"], str) or not st["not_applicable"].strip():
                return None, f"matrix step {wname!r}: not_applicable needs a written reason, got {st['not_applicable']!r}"
            out.append({"name": wname, "not_applicable": st["not_applicable"].strip()})
            continue
        env = {k: str(v) for k, v in {**(wf_env or {}), **(job.get("env") or {}), **(ws.get("env") or {})}.items()}
        env.update({k: base if v == "$BASE_SHA" else str(v) for k, v in (st.get("env") or {}).items()})
        step = {"name": wname}
        if st.get("argv"):
            step["argv"] = [base if x == "$BASE_SHA" else str(x) for x in st["argv"]]
        else:
            run, shell = ws.get("run"), ws.get("shell") or defaults.get("shell")
            if not isinstance(run, str) or "${{" in run or shell not in SHELLS:
                return None, f"workflow step {wname!r} is not a bash run: body without expressions (shell={shell!r}) — transcribe it as argv or give a reason"
            step.update(argv=list(SHELLS[shell]), script=run)
        if (expr := sorted(k for k, v in env.items() if "${{" in v)) or ws.get("continue-on-error"):
            return None, f"workflow step {wname!r}: env {expr} carry expressions the runner does not evaluate (override them) or the step is continue-on-error"
        try:
            step.update(env=env, cwd=_step_cwd(ws, defaults))
        except RuntimeError as e:
            return None, f"workflow step {wname!r}: working-directory {e}"
        if ws.get("if") is not None:
            step["if_not_evaluated"] = str(ws["if"])
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
    text = "\n".join(ln for s in steps if s.get("trusted_scan") is not False
                     for ln in ((s.get("script") or "") + "\n" + " ".join(s.get("argv") or [])).splitlines() if not ln.lstrip().startswith("#"))
    toks = set(re.findall(r"[A-Za-z0-9_][A-Za-z0-9_./-]*", text))
    scripts = [f for f in listing if f.endswith((".py", ".sh"))]
    named = {f for f in scripts if f in toks}
    for d in (t for t in toks if t.endswith("/") and t.count("/") >= 2):   # `infra/organ-conformance/`, never a bare `scripts/`
        named |= {f for f in scripts if f.startswith(d)}
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
        want = str((job.get("env") or {}).get(var, ""))
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


def full_dir_map(td: Path) -> dict:
    return {str(f.relative_to(td)): sha256_file(f) for f in sorted(td.rglob("*")) if f.is_file()} if td.is_dir() else {}


def cmd_plan(a):
    run_dir, wt = Path(a.run_dir).resolve(), Path(a.worktree).resolve()
    store = Store(run_dir)
    ident = identity(wt)
    if a.candidate and ident["candidate_sha"] != a.candidate:
        sys.exit(f"worktree HEAD {ident['candidate_sha']} != requested candidate {a.candidate}")
    base = git(wt, "rev-parse", a.base + "^{commit}")
    trusted = run_dir / "state" / "trusted"
    trusted.mkdir(parents=True, exist_ok=True)
    for f in TRUSTED_CLASSIFIER_FILES:
        blob = _extract_base_file(wt, base, f)
        if blob is None:
            sys.exit(f"trusted classifier file {f} missing at base {base[:12]} — refusing to plan without the trusted classifier")
        (trusted / Path(f).name).write_bytes(blob)
    changed = git(wt, "diff", "--name-only", f"{base}..{ident['candidate_sha']}").splitlines()
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
        "policy.trusted_classifier_corpus": {"kind": "cmd", "cwd": str(trusted), "cmd": [sys.executable, "test_change_map.py"], "trusted_pythonpath": str(trusted),
            "purpose": "the classifier that decides which jobs run is proven on its own guilt+innocence corpus, from the BASE ref (candidate cannot self-approve)"},
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
        checks[chk] = plan_context_check(wt, base, ident["candidate_sha"], trusted, cname, ctx, trusted_sha, changed, pyv)
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
        elif spec["kind"] == "contained_steps" and iso["mode"] != "container":
            checks[name] = _blocked("a required context's steps run only under --isolation container: they execute candidate code and mutate "
                                    "their tree (guilt controls)")
        else:
            spec["isolation"] = iso
            if iso["mode"] == "container":
                spec.pop("python", None)   # the interpreter is the pinned image's, not a host venv
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
    env = dict(ln.split("=", 1) for ln in lines[1:] if "=" in ln)
    pyv = env.get("PYTHON_VERSION")   # set by the official python images; LOCALCI_PYTHONS="<major.minor>=<bin dir> ..." by candidate.Dockerfile
    extra = dict(x.split("=", 1) for x in env.get("LOCALCI_PYTHONS", "").split() if "=" in x)
    return {"mode": "container", "image": image, "image_id": lines[0], "docker": os.path.realpath(docker), "network": "none",
            "mounts": [], "user": f"{SANDBOX_UID}:{SANDBOX_UID}", "init": True, "python_version": pyv, "pythons": extra}


def isolation_of(plan: dict) -> dict:
    """A plan frozen before v0.3.0 carries no isolation evidence: it is uncontained, never silently upgraded."""
    return plan.get("isolation") or {"mode": "none", "reason": "plan predates isolation evidence (runner < 0.3.0)"}


def _tar_add(tf: tarfile.TarFile, name: str, data: bytes | None = None, mode: int = 0o644, link: str | None = None) -> None:
    ti = tarfile.TarInfo(name)
    ti.uid = ti.gid = SANDBOX_UID
    ti.mtime = int(time.time())   # a checkout writes its files now; mtime 0 made every file 56 years old to an age-reading test
    if data is None and link is None:
        ti.type, ti.mode = tarfile.DIRTYPE, 0o755
        tf.addfile(ti)
    elif link is not None:
        ti.type, ti.linkname, ti.mode = tarfile.SYMTYPE, link, 0o777
        tf.addfile(ti)
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
                    timeout: float | None = None) -> int:
    """Tar `commit`'s tree from the OBJECT STORE into `sink` under w/ — never the checkout (ignored files such as .env or a venv stay
    out) and never `git archive` (it honours the candidate's export-ignore). `overrides` replace blobs (BASE test files); `extra` lands
    outside w/. Owned by the sandbox uid so candidate tests can write where they could in a checkout."""
    listing = subprocess.run(["git", "-C", str(wt), "ls-tree", "-r", "-z", "--full-tree", commit], capture_output=True, check=True, timeout=timeout).stdout.decode()
    entries = []
    for rec in listing.split("\0"):
        if rec:
            meta, rel = rec.split("\t", 1)
            mode, kind, oid = meta.split(" ")
            if kind == "blob":
                entries.append((mode, oid, safe_tree_path(rel)))
    parents = lambda paths, top: {f"{top}{q}" for n in paths for q in Path(n).parents if str(q) != "."}   # noqa: E731
    dirs = sorted({"w", "out"} | parents({rel for _, _, rel in entries} | set(overrides), "w/") | parents(extra, ""))
    tf = tarfile.open(fileobj=sink, mode="w|")
    for d in dirs:
        _tar_add(tf, d)
    for x in sorted(extra):
        _tar_add(tf, x, extra[x])
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


def execute_contained(name: str, spec: dict, run_dir: Path, plan: dict, inner: list[str], overrides: dict[str, bytes], extra: dict[str, bytes],
                      env: dict, log: Path, junit: Path, timeout: int, workdir: str = "/w") -> tuple[int | None, str | None]:
    """Run candidate code in a fresh container: no bind mount, no network, no capability, non-root, no host environment.
    The tree goes in as a tar stream and only the junit comes out; the host run dir, receipts, credentials and the Pysa
    home are not reachable from inside. Returns (rc, error)."""
    iso = spec["isolation"]
    docker = iso["docker"]
    ctr = re.sub(r"[^a-zA-Z0-9_.-]", "-", f"localci-{plan['run_id']}-{name}")[:100] + "-" + os.urandom(4).hex()
    denv = trusted_env()
    create = [docker, "create", "--name", ctr, "--label", "org.nuzantara.localci=candidate", "--label", f"org.nuzantara.localci.run={run_label(run_dir)}",
              "--network", "none", "--cap-drop", "ALL", "--init",   # an init reaps orphans, as the hosted runner's does
              "--security-opt", "no-new-privileges", "--user", iso["user"], "--pids-limit", "1024", "--memory", "4g", "--workdir", workdir,
              *[f"--env={k}={v}" for k, v in sorted(env.items())], iso["image_id"], *inner]
    try:
        r = subprocess.run(create, capture_output=True, text=True, timeout=120, env=denv)
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
            t_end = time.monotonic() + COPY_TIMEOUT_S
            try:
                watchdog.start()
                n = stream_tree_tar(Path(plan["worktree"]), plan["candidate_sha"], cp.stdin, overrides, extra, group, COPY_TIMEOUT_S)
                cp.stdin.close()
                cp.wait(timeout=max(1.0, t_end - time.monotonic()))
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as e:
                for proc in group:
                    proc.kill()
                    proc.wait()
                return None, f"candidate tree copy-in failed{' (budget ' + str(COPY_TIMEOUT_S) + 's expired)' if expired.is_set() else ''}: {type(e).__name__}"
            finally:
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
            fh.write(f"# isolation=container image={iso['image_id']} network=none user={iso['user']} mounts=none tree={plan['candidate_sha']} blobs={n}\n")
            fh.flush()
            try:
                rc = subprocess.run([docker, "start", "-a", ctr], stdout=fh, stderr=subprocess.STDOUT, timeout=timeout, env=denv).returncode
            except subprocess.TimeoutExpired:
                subprocess.run([docker, "kill", ctr], capture_output=True, timeout=60, env=denv)
                return None, f"timeout after {timeout}s (container killed; removal verified below or the run aborts)"
        why = _read_junit_out(docker, ctr, junit)
        if why:
            with open(log, "a") as fh:
                fh.write(f"# junit: {why}\n")
        return rc, None
    finally:
        _remove_verified(docker, ctr, denv)


class ContainerCleanupError(RuntimeError):
    """A candidate container may still exist: the run must not start another check next to it."""


def _remove_verified(docker: str, ctr: str, denv: dict) -> None:
    try:
        subprocess.run([docker, "rm", "-f", ctr], capture_output=True, timeout=120, env=denv)
        gone = subprocess.run([docker, "container", "inspect", "--format", "{{.Id}}", ctr], capture_output=True, text=True, timeout=60, env=denv)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ContainerCleanupError(f"removal of candidate container {ctr} not verifiable: {type(e).__name__}") from e
    if gone.returncode == 0 or "no such" not in (gone.stderr or "").lower():
        raise ContainerCleanupError(f"candidate container {ctr} still present or its absence unverifiable after docker rm -f (inspect rc={gone.returncode})")


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
    for rel in spec.get("trusted_files") or []:
        bp = run_dir / "state" / "trusted" / "base_files" / rel
        blob = bp.read_bytes() if bp.exists() else None   # an empty __init__.py is a blob too
        if blob is None or sha256_bytes(blob) != plan.get("trusted_files_sha256", {}).get(rel):
            return {"status": "ERROR", "reason": f"trusted blob {rel} missing or differs from the plan's sha256", "rc": None, "counts": None}
        overrides[rel] = blob
    if kind == "pytest":
        if not spec.get("modules"):
            return {"status": "ERROR", "reason": "zero test modules selected — missing evidence is not PASS", "rc": None, "counts": {"collected": 0, "executed": 0}}
        inner = ["python", "-m", "pytest", "-p", "no:cacheprovider", "-q", "--junitxml=/out/junit.xml", *spec["modules"]]
        env["PYTHONPATH"] = workdir
    elif kind == "contained_steps":
        drv = STEPS_DRIVER.read_bytes()
        if sha256_bytes(drv) != spec.get("driver_sha256"):
            return {"status": "ERROR", "reason": "steps driver changed since the plan pinned it", "rc": None, "counts": None}
        extra["cfg/steps_driver.py"] = drv
        hist = spec.get("history") or {"added": [], "base": []}
        for (rel, _mode, oid), blob in zip(hist["base"], read_blobs(Path(plan["worktree"]), [o for _, _, o in hist["base"]])):
            extra[f"cfg/base/{rel}"] = blob
        extra["cfg/steps.json"] = json.dumps({"context": spec["context"], "root": workdir, "git_index": spec.get("git_index"), "history": spec.get("history"),
                                              "path_prefix": spec.get("path_prefix") or "", "venv": bool(spec.get("venv")), "env": spec["env"],
                                              "steps": spec["steps"]}).encode()
        inner = ["python", "-I", "/cfg/steps_driver.py", "/cfg/steps.json", "/out/junit.xml"]
    else:
        extra["cfg/pytest-trusted.ini"] = b"[pytest]\npythonpath = /w\n"
        inner = ["python", "-I", "-m", "pytest", "-p", "no:cacheprovider", "--noconftest", "-c", "/cfg/pytest-trusted.ini", "--rootdir", "/w", "-q",
                 "--junitxml=/out/junit.xml", *[f"/w/{r}" for r in overrides]]
    with open(log, "w") as fh:
        fh.write(f"# {now()} container cmd={' '.join(inner)}\n")
    t0 = time.monotonic()
    try:
        rc, err = execute_contained(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, timeout, workdir)
    except ContainerCleanupError:
        raise
    except (OSError, subprocess.SubprocessError, RuntimeError) as e:
        rc, err = None, f"container execution failed: {type(e).__name__}: {e}"
    dur = round(time.monotonic() - t0, 3)
    if err:
        return {"status": "ERROR", "reason": err, "rc": None, "duration_s": dur, "counts": None, "log": str(log), "isolation": "container"}
    if kind == "contained_steps":
        steps = parse_step_junit(junit)
        status, reason = classify_contained_steps(rc, steps, spec)
        return {"status": status, "reason": reason + " [contained: candidate-produced junit]", "rc": rc, "duration_s": dur, "counts": None, "steps": steps,
                "log": str(log), "isolation": "container"}
    counts = parse_junit(junit)
    status, reason = classify_pytest(rc, counts)
    return {"status": status, "reason": reason + " [contained: candidate-produced junit]", "rc": rc, "duration_s": dur, "counts": counts, "log": str(log),
            "isolation": "container"}


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


def steps_verdict(steps: list, spec: dict) -> tuple[str, str]:
    """A context is PASS only when every step it runs returned 0 and every other step is NOT_APPLICABLE with a reason. A red step
    dominates (FAIL > ERROR > BLOCKED); a green won with the BASE judge while the candidate rewrites that judge is not claimed."""
    for status in ("FAIL", "ERROR", "BLOCKED"):
        bad = [s for s in steps if s["status"] == status]
        if bad:
            return status, f"{len(bad)} step(s) {status}: " + "; ".join(f"{s['name']} ({s['reason']})" for s in bad)[:600]
    ran = [s for s in steps if s["status"] == "PASS"]
    na = [s for s in steps if s["status"] == "NOT_APPLICABLE"]
    if not ran or len(ran) + len(na) != len(steps) or any(not (s.get("reason") or "").strip() for s in na):
        return "ERROR", f"{len(ran)} step(s) ran, {len(na)} not applicable of {len(steps)} — no executed step or an unexplained one is not PASS"
    if spec.get("judge_modified"):
        return "BLOCKED", (f"{len(ran)} step(s) rc=0 with the BASE judge, but the candidate rewrites {spec['judge_modified']}: hosted judges with "
                           "the candidate's copy, which this run did not execute — no green claimed")
    return "PASS", f"{len(ran)} step(s) rc=0" + ("; not applicable: " + "; ".join(f"{s['name']} ({s['reason']})" for s in na) if na else "")


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
    """A coordinator killed with -9 never reached its `docker rm -f`: remove THIS run dir's leftover candidate containers before
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
            subprocess.run([iso["docker"], "rm", "-f", *ids], capture_output=True, timeout=120, env=trusted_env())
            left = subprocess.run([iso["docker"], "ps", "-aq", *flt], capture_output=True, text=True, timeout=60, env=trusted_env())
            if left.returncode != 0 or left.stdout.split():
                return f"{len(left.stdout.split())} orphan candidate container(s) survived docker rm -f"
            store.journal({"event": "orphan_containers_removed", "count": len(ids), "at": now()})
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{type(e).__name__}: {e}"
    return None


def execute(name: str, spec: dict, run_dir: Path, plan: dict, timeout: int) -> dict:
    timeout = spec.get("timeout_s") or timeout   # a context's budget is its hosted job's timeout-minutes, else the run-wide default
    log = run_dir / "logs" / f"{name}.log"
    junit = run_dir / "receipts" / f"{name}.junit.xml"
    junit.unlink(missing_ok=True)   # a junit left by an earlier attempt is never this attempt's evidence
    kind = spec["kind"]
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
                    store.save(st)
                    continue
                attempt = c.get("attempts", 0) + 1
                started = now()
                c.update(status="RUNNING", reason="executing", at=started, pid=os.getpid(), pid_started=proc_start(os.getpid()), started_at=started, attempts=attempt)
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
                         steps=res.get("steps"))
                c.pop("pid", None)
                c.pop("pid_started", None)
                store.save(st)
                print(f"{name}: {res['status']} — {res['reason']} ({res.get('duration_s')}s)")
            if names:
                seal_now("end of run")
    finally:
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
        if mapping in ("blocked", "not_implemented"):
            out["results"][name] = {"mapping": mapping, "check": chk, "verdict": "BLOCKED"}
            out["blocked"].append(name)
            continue
        if chk is None:
            out["results"][name] = {"mapping": mapping, "check": None, "verdict": "UNCOVERED"}
            out["uncovered"].append(name)
            continue
        s, reason = view[chk]["status"], view[chk].get("reason") or ""
        ok = s == "PASS" or (s == "NOT_APPLICABLE" and reason.strip() != "")
        out["results"][name] = {"mapping": mapping, "check": chk, "verdict": "OK" if ok else s}
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
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
