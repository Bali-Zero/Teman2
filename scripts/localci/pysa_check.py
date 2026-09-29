#!/usr/bin/env python3
"""Pysa (Meta, MIT) taint check for the FastAPI backend — the local stand-in for CodeQL's python security queries.

Self-contained (stdlib only) so the runner can execute it from a BASE-ref copy with `python -I`.

  setup --home DIR [--backend-venv DIR] [--rebuild]   one-off: venv + pyre-check, taint stubs (pinned), curated site-packages view,
                                                       then a sha256 manifest of everything the judge executes or reads from the home
  verify-home --home DIR [--expect-digest D]    rc 0 + digest when the home still matches its manifest, rc 2 otherwise
  scan  --home DIR --worktree WT --ref REF --out DIR
  judge --home DIR --worktree WT --base REF --candidate REF --out DIR [--expect-home-digest D]   -> rc 0 no new flow, 1 new flows, 2 tool error

Why a baseline: this backend already carries ~900 CodeQL log-injection flows; a blocking check can only demand
"no NEW flow versus the base ref". A flow is keyed by (family, source callable, sink callable, sink statement text),
so unrelated line shifts do not create "new" findings and a moved-but-identical statement is not one either.
Benchmark that justified the choice: ~/.nuzantara-pilots/local-ci-followup/benchmark/REPORT_BENCHMARK.md (2026-09-27).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PYRE_CHECK_VERSION = "0.10.0"
STUBS_REPO = "https://github.com/facebook/pyre-check.git"
STUBS_COMMIT = "d5614e0a75f539443225fce3c3c55a77cfbfb72c"  # pragma: allowlist secret — public git SHA of facebook/pyre-check stubs/taint as benchmarked 2026-09-27, not a credential
APP_REL = "apps/backend-rag"
PKG_REL = "backend"
PYTHON_VERSION = "3.11"
HERE = Path(__file__).resolve().parent
MODELS_SRC = HERE / "pysa"
FAMILIES = {9001: ("log_injection", {"Logging"}), 6302: ("stack_trace_exposure", {"ReturnedToUser"}),
            5011: ("path_injection", {"FileSystem_ReadWrite"}), 6060: ("path_injection", {"FileSystem_Other"}),
            5012: ("ssrf", {"HTTPClientRequest", "HTTPClientRequest_URI", "HTTPClientRequest_METADATA", "HTTPClientRequest_DATA"}),
            5018: ("redirect", {"Redirect"}), 5008: ("xss", {"XSS"})}
ROUTE = {"get", "post", "put", "delete", "patch", "options", "head", "trace", "api_route", "route", "websocket"}
REGISTER = {"add_api_route", "add_route", "add_websocket_route", "add_api_websocket_route"}   # imperative registration: router.add_api_route("/p", fn)
FRAMEWORK_TYPES = {"Request", "Response", "WebSocket", "BackgroundTasks", "StreamingResponse", "HTMLResponse", "JSONResponse"}
FRAMEWORK_MODULES = ("fastapi", "starlette")   # a type is "the framework's" only when this module imported it from there — a local class Response is a body
INJECTORS = {"Depends", "Security"}
EXCLUDED_PARTS = {"tests", "test", "__pycache__"}   # out of the analysis scope — so an import of them FROM in-scope code is itself a finding (scope_escape)
# No name-based exemption: FastAPI resolves Request/WebSocket/BackgroundTasks by TYPE ANNOTATION only — an unannotated
# parameter called `request` is a query parameter, i.e. user input (Codex refutation, 2026-09-27).


def sh(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int | None = None, log=None) -> int:
    if log is not None:
        log.write(f"$ {' '.join(map(str, cmd))}\n")
        log.flush()
        return subprocess.run(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout).returncode


# ------------------------------------------------------------------ models (from the tree being scanned)
def _call_name(node: ast.AST) -> str:
    f = node.func if isinstance(node, ast.Call) else node
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def _idents(node: ast.AST) -> set[str]:
    """Identifiers structurally present in an annotation — string constants (descriptions, forward refs) do not count."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def is_injected(default, annotation) -> bool:
    if isinstance(default, ast.Call) and _call_name(default) in INJECTORS:
        return True
    return annotation is not None and any(isinstance(n, ast.Call) and _call_name(n) in INJECTORS for n in ast.walk(annotation))


def framework_bindings(tree: ast.AST) -> tuple[set[str], set[str]]:
    """(local names bound to a framework type, local aliases of a framework module) from this module's imports."""
    locals_, roots = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] in FRAMEWORK_MODULES:
            for al in n.names:
                if al.name in FRAMEWORK_TYPES:
                    locals_.add(al.asname or al.name)
                elif al.name in {"requests", "responses", "websockets", "background"}:   # from starlette import responses; responses.Response
                    roots.add(al.asname or al.name)
        elif isinstance(n, ast.Import):
            for al in n.names:
                if al.name.split(".")[0] in FRAMEWORK_MODULES:
                    roots.add((al.asname or al.name).split(".")[0])
    return locals_, roots


def is_framework_type(annotation: ast.AST, fw_locals: set[str], fw_roots: set[str]) -> bool:
    for n in ast.walk(annotation):
        if isinstance(n, ast.Name) and n.id in fw_locals:
            return True
        if isinstance(n, ast.Attribute) and n.attr in FRAMEWORK_TYPES:
            root = n.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in fw_roots:
                return True
    return False


def handler_params(fn: ast.AST, fw_locals: set[str] = frozenset(), fw_roots: set[str] = frozenset()) -> list[str]:
    a = fn.args
    pos = a.posonlyargs + a.args
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    keep = []
    for arg, dflt in list(zip(pos, defaults)) + list(zip(a.kwonlyargs, a.kw_defaults)):
        if arg.arg in {"self", "cls"}:
            continue
        if arg.annotation is not None and is_framework_type(arg.annotation, fw_locals, fw_roots):
            continue
        if is_injected(dflt, arg.annotation):
            continue
        keep.append(arg.arg)
    return keep


def route_decorator(fn: ast.AST) -> str | None:
    for d in fn.decorator_list:
        f = d.func if isinstance(d, ast.Call) else d
        name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)   # `get = router.get; @get(...)` counts too
        if name in ROUTE:
            return name
    return None


def defs(prefix: str, body: list) -> list[tuple[str, ast.AST]]:
    """Every function at any depth with its Pyre-style qualified name — handlers built inside factories or classes are handlers too."""
    out = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            q = f"{prefix}.{node.name}"
            out.append((q, node))
            out += defs(q, node.body)
        elif isinstance(node, ast.ClassDef):
            out += defs(f"{prefix}.{node.name}", node.body)
        elif hasattr(node, "body") and isinstance(getattr(node, "body"), list):   # if / try / with at module or function level
            out += defs(prefix, node.body)
            for extra in ("orelse", "finalbody"):
                out += defs(prefix, getattr(node, extra, []) or [])
            for h in getattr(node, "handlers", []) or []:
                out += defs(prefix, h.body)
    return out


def registered_endpoints(tree: ast.AST) -> dict[str, str]:
    """{function name: kind} for handlers registered imperatively — router.add_api_route("/p", fn) instead of a decorator."""
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in REGISTER:
            args = [a for a in n.args[1:2]] + [k.value for k in n.keywords if k.arg == "endpoint"]
            for a in args:
                if isinstance(a, ast.Name):
                    out[a.id] = "websocket" if "websocket" in n.func.attr else n.func.attr
    return out


def gen_handler_models(app_dir: Path) -> tuple[str, int]:
    """One explicit Pysa model per route handler (ModelQuery is inert on the Pyrefly backend)."""
    lines, seen = [], set()
    for p in sorted((app_dir / PKG_REL).rglob("*.py")):
        rel = p.relative_to(app_dir)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        module = ".".join(rel.with_suffix("").parts)
        registered = registered_endpoints(tree)
        fw_locals, fw_roots = framework_bindings(tree)
        for full, fn in defs(module, tree.body):
            deco = route_decorator(fn) or registered.get(fn.name)
            if deco is None or full in seen:
                continue
            seen.add(full)
            kw = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
            sig = ", ".join(f"{x}: TaintSource[UserControlled]" for x in handler_params(fn, fw_locals, fw_roots))
            ret = "" if deco == "websocket" else " -> TaintSink[ReturnedToUser]"
            lines.append(f"{kw} {full}({sig}){ret}: ...")
    return "# generated from the scanned tree — FastAPI route handlers as sources/sinks\n" + "\n".join(lines) + "\n", len(lines)


def scope_escapes(app_dir: Path) -> list[dict]:
    """In-scope modules importing from an excluded (tests/) path: the excluded code becomes reachable, so it is a finding, not a blind spot."""
    out = []
    for p in sorted((app_dir / PKG_REL).rglob("*.py")):
        rel = p.relative_to(app_dir)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        module = ".".join(rel.with_suffix("").parts)
        for n in ast.walk(tree):
            targets = []
            if isinstance(n, ast.ImportFrom):
                base = ".".join(module.split(".")[:-n.level] if n.level else []) if n.level else ""
                targets = [".".join(x for x in (base, n.module or "", al.name) if x) for al in n.names]
            elif isinstance(n, ast.Import):
                targets = [al.name for al in n.names]
            for t in targets:
                if any(part in EXCLUDED_PARTS for part in t.split(".")):
                    text = ast.unparse(n)
                    key = hashlib.sha1("|".join(["scope_escape", module, text]).encode()).hexdigest()[:16]
                    out.append({"key": key, "family": "scope_escape", "code": 0, "source_callable": module, "issue": f"{rel}:{n.lineno}", "sink": f"{rel}:{n.lineno}",
                                "sink_callable": "<import>", "sink_statement": text[:200], "sink_localised": True})
                    break
    return out


# ------------------------------------------------------------------ measured home
MANIFEST = "manifest.json"
MEASURED = ("venv", "pyre-check/stubs/taint", "site")   # what `pyre analyze` executes or reads from the home (typeshed lives in venv/)


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _measure_tree(root: Path, label: str, out: dict) -> None:
    """Every regular file under root by sha256 — source-less .pyc included, Python imports those — every symlink by its target (and,
    for a target outside, that target's content). Only __pycache__ is skipped: pyre runs with PYTHONPYCACHEPREFIX, so cached bytecode
    there is never looked up. A linked site package is type input only (never executed): its bytecode is not measured."""
    if root.is_symlink():
        tgt = os.path.realpath(root)
        out[label] = f"link:{os.readlink(root)}"
        if os.path.isdir(tgt):
            _measure_tree(Path(tgt), f"{label}=>", out)
        elif os.path.isfile(tgt):
            out[f"{label}=>"] = _sha(Path(tgt))
        return
    if root.is_file():
        out[label] = _sha(root)
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for d in list(dirnames):
            if os.path.islink(os.path.join(dirpath, d)):
                dirnames.remove(d)
                _measure_tree(Path(dirpath) / d, f"{label}/{os.path.relpath(os.path.join(dirpath, d), root)}", out)
        for f in sorted(filenames):
            fp = Path(dirpath) / f
            if f.endswith(".pyc") and label.startswith("site/"):
                continue
            if fp.is_symlink():
                _measure_tree(fp, f"{label}/{os.path.relpath(fp, root)}", out)
            else:
                out[f"{label}/{os.path.relpath(fp, root)}"] = _sha(fp)


def measure_home(home: Path) -> dict:
    out: dict = {}
    for rel in MEASURED:
        if (home / rel).exists() or (home / rel).is_symlink():
            _measure_tree(home / rel, rel, out)
    py = home / "venv" / "bin" / "python"   # the venv interpreter is a link to a base install outside the home: its binary and stdlib count too
    if py.exists():
        base = Path(os.path.realpath(py))
        out["interpreter"] = str(base)
        out["interpreter=>"] = _sha(base)
        stdlib = base.parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}"
        for cand in sorted((base.parent.parent / "lib").glob("python3.*")):
            stdlib = cand
        if stdlib.is_dir():
            sub: dict = {}
            for dirpath, dirnames, filenames in os.walk(stdlib):
                dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", "site-packages", "test", "idlelib", "tkinter"))
                for f in sorted(filenames):
                    if f.endswith((".py", ".so", ".pyc", ".pth")):
                        sub[os.path.relpath(os.path.join(dirpath, f), stdlib)] = _sha(Path(dirpath) / f)
            out["interpreter-stdlib"] = hashlib.sha256(json.dumps(sub, sort_keys=True).encode()).hexdigest()
    return out


def home_digest(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def verify_home(home: Path, expect: str | None = None) -> tuple[str | None, str | None]:
    """(digest, None) when the home matches the manifest setup wrote (and `expect`, when given); (None, why) otherwise."""
    mp = home / MANIFEST
    if not mp.is_file():
        return None, f"pysa home {home} carries no {MANIFEST}: it predates measured setup and may hold anything — run `pysa_check.py setup --home {home} --rebuild`"
    try:
        man = json.loads(mp.read_text())
        files, recorded = man["files"], man["digest"]
    except (ValueError, KeyError, TypeError) as e:
        return None, f"{MANIFEST} unreadable: {e}"
    if home_digest(files) != recorded:
        return None, f"{MANIFEST} is internally inconsistent (its file map does not hash to its digest)"
    if expect and recorded != expect:
        return None, f"pysa home digest {recorded[:16]} != {expect[:16]} measured when this run was planned: the home was replaced"
    now_files = measure_home(home)
    if now_files != files:
        diff = sorted(k for k in set(files) | set(now_files) if files.get(k) != now_files.get(k))
        return None, f"pysa home tampered: {len(diff)} measured entr{'y' if len(diff) == 1 else 'ies'} changed since setup (first: {diff[:3]}) — run setup --rebuild"
    return recorded, None


def write_manifest(home: Path) -> tuple[str, dict]:
    files = measure_home(home)
    digest = home_digest(files)
    (home / MANIFEST).write_text(json.dumps({"digest": digest, "pyre_check": PYRE_CHECK_VERSION, "stubs_commit": STUBS_COMMIT, "files": files,
                                             "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=0, sort_keys=True))
    return digest, files


def cmd_verify_home(a) -> int:
    digest, why = verify_home(Path(a.home).resolve(), a.expect_digest)
    print(json.dumps({"ok": digest is not None, "digest": digest, "reason": why}))
    return 0 if digest else 2


# ------------------------------------------------------------------ setup
def cmd_setup(a) -> int:
    home = Path(a.home).resolve()
    venv = home / "venv"
    installed = any((home / r).exists() for r in ("venv", "pyre-check", "site"))
    if installed and not a.rebuild:
        digest, why = verify_home(home)
        if digest is None:   # the old setup REUSED whatever venv/stubs it found: a replaced pyre would have survived a "re-setup"
            print(f"setup: refusing to reuse an existing installation: {why}")
            return 2
    home.mkdir(parents=True, exist_ok=True)
    log = open(home / "setup.log", "a")
    if a.rebuild:
        for r in ("venv", "pyre-check", "site", "baselines", MANIFEST):
            t = home / r
            t.unlink() if t.is_file() or t.is_symlink() else shutil.rmtree(t, ignore_errors=True)
    if not (venv / "bin" / "pyre").exists():
        if sh(["uv", "venv", "-q", "-p", "3.12", str(venv)], log=log) or sh(["uv", "pip", "install", "-q", "--python", str(venv / "bin" / "python"), f"pyre-check=={PYRE_CHECK_VERSION}"], log=log):
            print("setup: pyre-check install failed (see setup.log)")
            return 2
    stubs = home / "pyre-check"
    if not (stubs / "stubs" / "taint").exists():
        shutil.rmtree(stubs, ignore_errors=True)
        if sh(["git", "clone", "-q", "--filter=blob:none", "--sparse", STUBS_REPO, str(stubs)], log=log) or \
           sh(["git", "-C", str(stubs), "sparse-checkout", "set", "stubs/taint"], log=log) or \
           sh(["git", "-C", str(stubs), "checkout", "-q", STUBS_COMMIT], log=log):
            print("setup: stubs clone failed (see setup.log)")
            return 2
    sp = Path(a.backend_venv).resolve() / "lib" / f"python{PYTHON_VERSION}" / "site-packages"
    if not sp.is_dir():
        print(f"setup: backend site-packages not found at {sp}")
        return 2
    site = home / "site"
    site.mkdir(exist_ok=True)
    wanted = [x.strip() for x in (MODELS_SRC / "site_packages.txt").read_text().splitlines() if x.strip()]
    linked, missing = 0, []
    for n in wanted:
        src = sp / n if (sp / n).exists() else sp / f"{n}.py"
        if not src.exists():
            missing.append(n)
            continue
        dst = site / src.name
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        os.symlink(src, dst)
        linked += 1
    frozen = subprocess.run(["uv", "pip", "freeze", "--python", str(venv / "bin" / "python")], capture_output=True, text=True).stdout
    head = subprocess.run(["git", "-C", str(stubs), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(stubs), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if f"pyre-check=={PYRE_CHECK_VERSION}" not in frozen.split() or head != STUBS_COMMIT or dirty:
        print(f"setup: installed identity is not the pinned one (pyre-check=={PYRE_CHECK_VERSION} in venv: {f'pyre-check=={PYRE_CHECK_VERSION}' in frozen.split()}, "
              f"stubs HEAD {head[:12]} vs {STUBS_COMMIT[:12]}, stubs dirty: {bool(dirty)}) — refusing to measure it; rerun with --rebuild")
        return 2
    digest, files = write_manifest(home)
    (home / "setup.json").write_text(json.dumps({"pyre_check": PYRE_CHECK_VERSION, "stubs_commit": STUBS_COMMIT, "backend_site_packages": str(sp),
                                                 "linked": linked, "missing": missing, "home_digest": digest, "measured_entries": len(files),
                                                 "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))
    print(json.dumps({"home": str(home), "linked": linked, "missing": missing, "home_digest": digest, "measured_entries": len(files)}))
    return 0


def home_ready(home: Path) -> str | None:
    for rel in ("venv/bin/pyre", "venv/bin/pyrefly", "pyre-check/stubs/taint", "site", "venv/lib/pyre_check/typeshed"):
        if not (home / rel).exists():
            return f"pysa home {home} is not set up: missing {rel} (run `pysa_check.py setup --home {home} --backend-venv <apps/backend-rag/.venv>`)"
    return None


# ------------------------------------------------------------------ scan
def export_tree(wt: Path, ref: str, dest: Path) -> str:
    """Materialise <ref>:apps/backend-rag/backend from the object store — never `git archive`, which honours the candidate's
    own `.gitattributes export-ignore` and would let a PR hide files from the judge (fresh-gate BLOCK, 2026-09-27)."""
    dest.mkdir(parents=True, exist_ok=True)
    sub = f"{APP_REL}/{PKG_REL}"
    tree = subprocess.run(["git", "-C", str(wt), "rev-parse", f"{ref}:{sub}"], capture_output=True, text=True, check=True).stdout.strip()
    listing = subprocess.run(["git", "-C", str(wt), "ls-tree", "-r", "-z", tree], capture_output=True, check=True).stdout.decode()
    entries = []
    for rec in listing.split("\0"):
        if not rec:
            continue
        meta, rel = rec.split("\t", 1)
        mode, kind, oid = meta.split(" ")
        if kind == "blob" and mode != "120000":          # symlinks are not followed and not analysed
            entries.append((oid, rel))
    batch = subprocess.run(["git", "-C", str(wt), "cat-file", "--batch"], input="".join(f"{o}\n" for o, _ in entries).encode(), capture_output=True, check=True).stdout
    pos, written = 0, 0
    for oid, rel in entries:
        nl = batch.index(b"\n", pos)
        hdr = batch[pos:nl].decode().split(" ")
        if hdr[0] != oid or hdr[1] != "blob":
            raise RuntimeError(f"cat-file stream desync at {rel}: {hdr}")
        size = int(hdr[2])
        body = batch[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        target = dest / sub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        written += 1
    exported = sum(1 for _ in (dest / sub).rglob("*") if _.is_file()) if entries else 0
    if written != len(entries) or exported != written:
        raise RuntimeError(f"export incomplete for {ref}: {len(entries)} blobs listed, {written} written, {exported} on disk")
    return tree


def write_configs(app_dir: Path, home: Path, models_dir: Path) -> None:
    (app_dir / "pyrefly.toml").write_text(
        f'project-includes = ["{PKG_REL}/**/*.py"]\nproject-excludes = ["**/__pycache__/**", "**/node_modules/**", "**/tests/**", "**/test/**"]\n'
        f'search-path = ["{app_dir}"]\nsite-package-path = ["{home / "site"}"]\npython-version = "{PYTHON_VERSION}"\n')
    (app_dir / ".pyre_configuration").write_text(json.dumps({
        "source_directories": [PKG_REL], "taint_models_path": [str(home / "pyre-check" / "stubs" / "taint"), str(models_dir)],
        "typeshed": str(home / "venv" / "lib" / "pyre_check" / "typeshed"), "python_version": PYTHON_VERSION}, indent=1))


def run_pysa(home: Path, app_dir: Path, results: Path, timeout: int, log) -> int:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONSAFEPATH")}
    env["PATH"] = f"{home / 'venv' / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONPYCACHEPREFIX"] = str(results.parent / "pycache")   # never load bytecode cached inside the (measured) home
    shutil.rmtree(app_dir / ".pyre", ignore_errors=True)
    return sh([str(home / "venv" / "bin" / "pyre"), "--noninteractive", "analyze", "--no-verify", "--save-results-to", str(results)],
              cwd=str(app_dir), env=env, timeout=timeout, log=log)


class Leaves:
    """Follow Pysa backward traces through callee models down to the sink statement (memoised, cycle-safe)."""

    def __init__(self, models: dict):
        self.models, self.memo, self.busy = models, {}, set()

    @staticmethod
    def param(port: str) -> str | None:
        return port[7:].split(")")[0].split(",")[0].strip() if port.startswith("formal(") else None

    @staticmethod
    def kinds_ok(t: dict, kinds: set) -> bool:
        return any(k.get("kind") in kinds for k in t.get("kinds", []))

    def follow(self, callable_: str, param: str | None, kinds: set, depth: int) -> set:
        key = (callable_, param, tuple(sorted(kinds)))
        if key in self.memo:
            return self.memo[key]
        m = self.models.get(callable_)
        if not m or depth > 25 or key in self.busy:
            return set()
        self.busy.add(key)
        out: set = set()
        for s in m.get("sinks", []):
            if self.param(s["port"]) != param:
                continue
            for t in s["taint"]:
                if self.kinds_ok(t, kinds):
                    out |= self.hop(m["filename"], t, kinds, depth)
        self.busy.discard(key)
        self.memo[key] = out
        return out

    def hop(self, filename: str, t: dict, kinds: set, depth: int) -> set:
        if "origin" in t:
            return {(filename, t["origin"]["line"], True)}
        if "call" in t:
            c = t["call"]
            targets = [x for x in c.get("resolves_to", []) if x.startswith(PKG_REL + ".") and x in self.models]
            out: set = set()
            for tgt in targets:
                out |= self.follow(tgt, self.param(c["port"]), kinds, depth + 1)
            if out:
                return out
            return {(filename, c["position"]["line"], not targets)}  # external callee: the call site is the sink; project callee: unlocalised
        return set()


_stmt_cache: dict = {}


def stmt_of(app_dir: Path, rel: str, line: int) -> tuple[str, str]:
    """(enclosing function name, normalised statement text) for a line — the line-shift-proof part of the key."""
    ck = (str(app_dir), rel)                 # keyed by TREE too: base and candidate scans share this process
    if ck not in _stmt_cache:
        idx, funcs = [], []
        try:
            tree = ast.parse((app_dir / rel).read_text(encoding="utf-8", errors="replace"))
            src = (app_dir / rel).read_text(encoding="utf-8", errors="replace").splitlines()

            def walk(node, prefix):   # qualified names: Class.method — two same-named methods in one file are two callables
                for n in ast.iter_child_nodes(node):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        q = f"{prefix}{n.name}"
                        funcs.append((n.lineno, n.end_lineno, q))
                        walk(n, q + ".")
                    elif isinstance(n, ast.ClassDef):
                        walk(n, f"{prefix}{n.name}.")
                    else:
                        if isinstance(n, ast.stmt) and not isinstance(n, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncWith, ast.AsyncFor)):
                            idx.append((n.lineno, n.end_lineno, " ".join(x.strip() for x in src[n.lineno - 1:n.end_lineno])))
                        walk(n, prefix)
            walk(tree, "")
        except (SyntaxError, FileNotFoundError):
            pass
        _stmt_cache[ck] = (idx, funcs)
    idx, funcs = _stmt_cache[ck]
    best = min((s for s in idx if s[0] <= line <= s[1]), key=lambda s: s[1] - s[0], default=None)
    fn = min((f for f in funcs if f[0] <= line <= f[1]), key=lambda f: f[1] - f[0], default=None)
    return (fn[2] if fn else "<module>", re.sub(r"\s+", " ", best[2]) if best else f"<line {line}>")


def extract_findings(taint_output: Path, app_dir: Path) -> tuple[list[dict], int]:
    """(findings, number of model records) — zero model records means Pysa analysed nothing, not that the tree is clean."""
    models, issues = {}, []
    for line in taint_output.read_text().splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("kind") == "model":
            models[o["data"]["callable"]] = o["data"]
        elif o.get("kind") == "issue":
            issues.append(o["data"])
    lv, out, seen = Leaves(models), [], {}
    for d in issues:
        family, kinds = FAMILIES.get(d["code"], (f"pysa_{d['code']}", set()))   # an unlisted rule (RCE 5001, SQLi 5005, ...) is still a flow, never dropped
        leaves: set = set()
        for t in d["traces"]:
            if t["name"] != "backward":
                continue
            for r in t["roots"]:
                if lv.kinds_ok(r, kinds) or "origin" in r:
                    leaves |= lv.hop(d["filename"], r, kinds, 0)
        for lf, ll, localised in sorted(leaves or {(d["filename"], d["line"], True)}):
            fn, text = stmt_of(app_dir, lf, ll)
            ident = "|".join([family, d["callable"], lf, fn, text])
            n_th = seen.get(ident, 0) + 1                      # multiset: a SECOND identical sink statement fed by a new flow is a new flow
            seen[ident] = n_th
            key = hashlib.sha1(f"{ident}|#{n_th}".encode()).hexdigest()[:16]
            out.append({"key": key, "family": family, "code": d["code"], "source_callable": d["callable"], "issue": f"{d['filename']}:{d['line']}",
                        "sink": f"{lf}:{ll}", "sink_callable": fn, "sink_statement": text[:200], "sink_localised": localised})
    return out, len(models)


def scan(home: Path, wt: Path, ref: str, out: Path, timeout: int, log) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    app_dir = out / "tree" / APP_REL
    shutil.rmtree(out / "tree", ignore_errors=True)
    tree = export_tree(wt, ref, out / "tree")
    models_dir = out / "models"
    models_dir.mkdir(exist_ok=True)
    for f in MODELS_SRC.glob("*"):
        if f.suffix in (".pysa", ".config"):
            shutil.copy(f, models_dir / f.name)
    text, n = gen_handler_models(app_dir)
    if n == 0:   # fail closed: an unmodelled tree has no sources, so it would always look clean
        return {"ok": False, "rc": None, "tree": tree, "reason": f"no FastAPI route handler found under {APP_REL}/{PKG_REL} — nothing to model, refusing to call an unmodelled tree clean", "duration_s": 0.0}
    (models_dir / "fastapi_handlers_generated.pysa").write_text(text)
    write_configs(app_dir, home, models_dir)
    t0 = time.monotonic()
    rc = run_pysa(home, app_dir, out / "results", timeout, log)
    taint = out / "results" / "taint-output.json"
    if rc != 0 or not taint.exists():
        return {"ok": False, "rc": rc, "tree": tree, "reason": f"pyre analyze rc={rc}, taint-output present={taint.exists()}", "duration_s": round(time.monotonic() - t0, 1)}
    findings, n_models = extract_findings(taint, app_dir)
    findings += scope_escapes(app_dir)
    if n_models == 0:   # fail closed: rc 0 with an empty/malformed taint-output is a tool failure, not a clean tree
        return {"ok": False, "rc": rc, "tree": tree, "reason": "taint-output.json carries no model record — Pysa analysed nothing (empty or malformed output is not a verdict)",
                "duration_s": round(time.monotonic() - t0, 1)}
    res = {"ok": True, "rc": 0, "ref": ref, "tree": tree, "handlers_modelled": n, "models": n_models, "duration_s": round(time.monotonic() - t0, 1), "findings": findings,
           "by_family": {f: sum(1 for x in findings if x["family"] == f) for f in sorted({x["family"] for x in findings})}}
    (out / "findings.json").write_text(json.dumps(res, indent=1))
    shutil.rmtree(out / "tree", ignore_errors=True)
    return res


def cmd_scan(a) -> int:
    home, wt, out = Path(a.home).resolve(), Path(a.worktree).resolve(), Path(a.out).resolve()
    if (why := home_ready(home)):
        print(why)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "pysa.log", "w") as log:
        res = scan(home, wt, a.ref, out, a.timeout, log)
    print(json.dumps({k: v for k, v in res.items() if k != "findings"}, indent=1))
    return 0 if res["ok"] else 2


def diff_findings(base: list[dict], cand: list[dict]) -> dict:
    bk, ck = {x["key"]: x for x in base}, {x["key"]: x for x in cand}
    new = [ck[k] for k in ck if k not in bk]
    fixed = [bk[k] for k in bk if k not in ck]
    return {"new": new, "fixed": fixed, "unchanged": len(set(bk) & set(ck))}


def cmd_judge(a) -> int:
    home, wt, out = Path(a.home).resolve(), Path(a.worktree).resolve(), Path(a.out).resolve()
    if (why := home_ready(home)):
        print(why)
        return 2
    digest, why = verify_home(home, a.expect_home_digest)
    if digest is None:   # a replaced pyre, stub, typeshed or site package is not the judge that was measured: no verdict
        print(json.dumps({"verdict": "ERROR", "stage": "home", "reason": why}))
        return 2
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "pysa.log", "w")
    base_tree = subprocess.run(["git", "-C", str(wt), "rev-parse", f"{a.base}:{APP_REL}/{PKG_REL}"], capture_output=True, text=True, check=True).stdout.strip()
    judge_id = hashlib.sha256(b"".join(f.read_bytes() for f in sorted([Path(__file__)] + list(MODELS_SRC.glob("*")))) ).hexdigest()[:16]
    # BASE is scanned on every judge run. A cross-run cache lived in the home, where an earlier uncontained (--isolation none or
    # pre-0.3.0) candidate could rewrite a baseline AND any index vouching for it; nothing the same OS user can write authenticates
    # it, so the ~70 s it saved is not worth a forgeable "unchanged" (independent review R3, 2026-09-29).
    base_res = scan(home, wt, a.base, out / "base", a.timeout, log)
    if not base_res["ok"]:
        print(json.dumps({"verdict": "ERROR", "stage": "base", **{k: v for k, v in base_res.items() if k != "findings"}}))
        return 2
    cand_res = scan(home, wt, a.candidate, out / "candidate", a.timeout, log)
    if not cand_res["ok"]:
        print(json.dumps({"verdict": "ERROR", "stage": "candidate", **{k: v for k, v in cand_res.items() if k != "findings"}}))
        return 2
    d = diff_findings(base_res["findings"], cand_res["findings"])
    verdict = "FAIL" if d["new"] else "PASS"
    report = {"verdict": verdict, "base": a.base, "base_tree": base_tree, "base_cached": base_res.get("cached", False), "candidate": a.candidate,
              "candidate_tree": cand_res["tree"], "handlers_modelled": cand_res["handlers_modelled"], "handlers_modelled_base": base_res["handlers_modelled"],
              "handlers_dropped": max(0, base_res["handlers_modelled"] - cand_res["handlers_modelled"]), "judge_id": judge_id,
              "base_findings": len(base_res["findings"]), "candidate_findings": len(cand_res["findings"]), "new": d["new"], "fixed": len(d["fixed"]),
              "unchanged": d["unchanged"], "durations_s": {"base": base_res["duration_s"], "candidate": cand_res["duration_s"]}, "home_digest": digest}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    md = [f"# pysa judge — {verdict}", "", f"base `{a.base}` ({len(base_res['findings'])} flows, cached={report['base_cached']}) → candidate `{a.candidate}` ({len(cand_res['findings'])} flows): "
          f"**{len(d['new'])} new**, {len(d['fixed'])} fixed, {d['unchanged']} unchanged — handlers modelled {base_res['handlers_modelled']} → {cand_res['handlers_modelled']}"
          + (f" (**{report['handlers_dropped']} fewer**: a handler that lost its decorator also lost its sources — read the diff)" if report["handlers_dropped"] else ""), ""]
    for x in d["new"]:
        md.append(f"- `{x['family']}` {x['source_callable']} → `{x['sink']}` in `{x['sink_callable']}`: `{x['sink_statement'][:120]}`")
    (out / "report.md").write_text("\n".join(md) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "new"} | {"new": [f"{x['family']} {x['sink']}" for x in d["new"]]}, indent=1))
    return 1 if d["new"] else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pysa_check")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--home", required=True)
    s.add_argument("--backend-venv", default=str(Path.cwd() / APP_REL / ".venv"))
    s.add_argument("--rebuild", action="store_true", help="wipe venv, stubs, site view and baselines, reinstall the pinned versions, re-measure")
    s.set_defaults(fn=cmd_setup)
    v = sub.add_parser("verify-home")
    v.add_argument("--home", required=True)
    v.add_argument("--expect-digest")
    v.set_defaults(fn=cmd_verify_home)
    for name, fn in (("scan", cmd_scan), ("judge", cmd_judge)):
        q = sub.add_parser(name)
        q.add_argument("--home", required=True)
        q.add_argument("--worktree", required=True)
        q.add_argument("--out", required=True)
        q.add_argument("--timeout", type=int, default=1500)
        if name == "scan":
            q.add_argument("--ref", default="HEAD")
        else:
            q.add_argument("--base", required=True)
            q.add_argument("--candidate", default="HEAD")
            q.add_argument("--expect-home-digest", help="the home digest measured at plan time: a different home is refused")
        q.set_defaults(fn=fn)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except Exception as e:  # noqa: BLE001 — an unexpected crash is a tool error (rc 2), never a FAIL (rc 1) and never a PASS
        print(json.dumps({"verdict": "ERROR", "stage": a.cmd, "reason": f"{type(e).__name__}: {e}"[:400]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
