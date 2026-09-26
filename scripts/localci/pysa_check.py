#!/usr/bin/env python3
"""Pysa (Meta, MIT) taint check for the FastAPI backend — the local stand-in for CodeQL's python security queries.

Self-contained (stdlib only) so the runner can execute it from a BASE-ref copy with `python -I`.

  setup --home DIR [--backend-venv DIR]      one-off: venv + pyre-check, taint stubs (pinned), curated site-packages view
  scan  --home DIR --worktree WT --ref REF --out DIR
  judge --home DIR --worktree WT --base REF --candidate REF --out DIR   -> rc 0 no new flow, 1 new flows, 2 tool error

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
ROUTE = {"get", "post", "put", "delete", "patch", "options", "head", "api_route", "websocket"}
FRAMEWORK = re.compile(r"(^|[^\w.])(fastapi\.|starlette\.\w+\.)?(Request|Response|WebSocket|BackgroundTasks|StreamingResponse|HTMLResponse|JSONResponse)($|[^\w])")
INJECT = re.compile(r"\b(Depends|Security)\s*\(")
FRAMEWORK_NAMES = {"request", "req", "response", "websocket", "ws", "background_tasks"}


def sh(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int | None = None, log=None) -> int:
    if log is not None:
        log.write(f"$ {' '.join(map(str, cmd))}\n")
        log.flush()
        return subprocess.run(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout).returncode


# ------------------------------------------------------------------ models (from the tree being scanned)
def is_injected(default, annotation) -> bool:
    if isinstance(default, ast.Call):
        f = default.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name in {"Depends", "Security"}:
            return True
    return annotation is not None and bool(INJECT.search(ast.unparse(annotation)))


def handler_params(fn: ast.AST) -> list[str]:
    a = fn.args
    pos = a.posonlyargs + a.args
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    keep = []
    for arg, dflt in list(zip(pos, defaults)) + list(zip(a.kwonlyargs, a.kw_defaults)):
        if arg.arg in {"self", "cls"}:
            continue
        if arg.annotation is None and arg.arg in FRAMEWORK_NAMES:   # unannotated `request` / `websocket` are still the framework objects
            continue
        if arg.annotation is not None and FRAMEWORK.search(ast.unparse(arg.annotation)):
            continue
        if is_injected(dflt, arg.annotation):
            continue
        keep.append(arg.arg)
    return keep


def route_decorator(fn: ast.AST) -> str | None:
    for d in fn.decorator_list:
        f = d.func if isinstance(d, ast.Call) else d
        if isinstance(f, ast.Attribute) and f.attr in ROUTE:
            return f.attr
    return None


def gen_handler_models(app_dir: Path) -> tuple[str, int]:
    """One explicit Pysa model per route handler (ModelQuery is inert on the Pyrefly backend)."""
    lines, seen = [], set()
    for p in sorted((app_dir / PKG_REL).rglob("*.py")):
        rel = p.relative_to(app_dir)
        if any(part in {"tests", "test", "__pycache__"} for part in rel.parts):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        module = ".".join(rel.with_suffix("").parts)
        scopes = [(module, tree.body)] + [(f"{module}.{c.name}", c.body) for c in tree.body if isinstance(c, ast.ClassDef)]
        for prefix, body in scopes:
            for fn in body:
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                deco = route_decorator(fn)
                if deco is None:
                    continue
                full = f"{prefix}.{fn.name}"
                if full in seen:
                    continue
                seen.add(full)
                kw = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
                sig = ", ".join(f"{x}: TaintSource[UserControlled]" for x in handler_params(fn))
                ret = "" if deco == "websocket" else " -> TaintSink[ReturnedToUser]"
                lines.append(f"{kw} {full}({sig}){ret}: ...")
    return "# generated from the scanned tree — FastAPI route handlers as sources/sinks\n" + "\n".join(lines) + "\n", len(lines)


# ------------------------------------------------------------------ setup
def cmd_setup(a) -> int:
    home = Path(a.home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    log = open(home / "setup.log", "a")
    venv = home / "venv"
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
    (home / "setup.json").write_text(json.dumps({"pyre_check": PYRE_CHECK_VERSION, "stubs_commit": STUBS_COMMIT, "backend_site_packages": str(sp),
                                                 "linked": linked, "missing": missing, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))
    print(json.dumps({"home": str(home), "linked": linked, "missing": missing}))
    return 0


def home_ready(home: Path) -> str | None:
    for rel in ("venv/bin/pyre", "venv/bin/pyrefly", "pyre-check/stubs/taint", "site", "venv/lib/pyre_check/typeshed"):
        if not (home / rel).exists():
            return f"pysa home {home} is not set up: missing {rel} (run `pysa_check.py setup --home {home} --backend-venv <apps/backend-rag/.venv>`)"
    return None


# ------------------------------------------------------------------ scan
def export_tree(wt: Path, ref: str, dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    tree = subprocess.run(["git", "-C", str(wt), "rev-parse", f"{ref}:{APP_REL}/{PKG_REL}"], capture_output=True, text=True, check=True).stdout.strip()
    ar = subprocess.Popen(["git", "-C", str(wt), "archive", ref, f"{APP_REL}/{PKG_REL}"], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=ar.stdout, check=True)
    ar.wait()
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
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.append((n.lineno, n.end_lineno, n.name))
                elif isinstance(n, ast.stmt) and not isinstance(n, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ClassDef, ast.AsyncWith, ast.AsyncFor)):
                    idx.append((n.lineno, n.end_lineno, " ".join(x.strip() for x in src[n.lineno - 1:n.end_lineno])))
        except (SyntaxError, FileNotFoundError):
            pass
        _stmt_cache[ck] = (idx, funcs)
    idx, funcs = _stmt_cache[ck]
    best = min((s for s in idx if s[0] <= line <= s[1]), key=lambda s: s[1] - s[0], default=None)
    fn = min((f for f in funcs if f[0] <= line <= f[1]), key=lambda f: f[1] - f[0], default=None)
    return (fn[2] if fn else "<module>", re.sub(r"\s+", " ", best[2]) if best else f"<line {line}>")


def extract_findings(taint_output: Path, app_dir: Path) -> list[dict]:
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
    lv, out, seen = Leaves(models), [], set()
    for d in issues:
        fam = FAMILIES.get(d["code"])
        if not fam:
            continue
        family, kinds = fam
        leaves: set = set()
        for t in d["traces"]:
            if t["name"] != "backward":
                continue
            for r in t["roots"]:
                if lv.kinds_ok(r, kinds) or "origin" in r:
                    leaves |= lv.hop(d["filename"], r, kinds, 0)
        for lf, ll, localised in (leaves or {(d["filename"], d["line"], True)}):
            fn, text = stmt_of(app_dir, lf, ll)
            key = hashlib.sha1("|".join([family, d["callable"], lf, fn, text]).encode()).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            out.append({"key": key, "family": family, "code": d["code"], "source_callable": d["callable"], "issue": f"{d['filename']}:{d['line']}",
                        "sink": f"{lf}:{ll}", "sink_callable": fn, "sink_statement": text[:200], "sink_localised": localised})
    return out


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
    (models_dir / "fastapi_handlers_generated.pysa").write_text(text)
    write_configs(app_dir, home, models_dir)
    t0 = time.monotonic()
    rc = run_pysa(home, app_dir, out / "results", timeout, log)
    taint = out / "results" / "taint-output.json"
    if rc != 0 or not taint.exists():
        return {"ok": False, "rc": rc, "tree": tree, "reason": f"pyre analyze rc={rc}, taint-output present={taint.exists()}", "duration_s": round(time.monotonic() - t0, 1)}
    findings = extract_findings(taint, app_dir)
    res = {"ok": True, "rc": 0, "ref": ref, "tree": tree, "handlers_modelled": n, "duration_s": round(time.monotonic() - t0, 1), "findings": findings,
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
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "pysa.log", "w")
    base_tree = subprocess.run(["git", "-C", str(wt), "rev-parse", f"{a.base}:{APP_REL}/{PKG_REL}"], capture_output=True, text=True, check=True).stdout.strip()
    cache = home / "baselines" / f"{base_tree}.json"
    if cache.exists():
        base_res = json.loads(cache.read_text())
        base_res["cached"] = True
    else:
        base_res = scan(home, wt, a.base, out / "base", a.timeout, log)
        if base_res["ok"]:
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(json.dumps(base_res))
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
              "candidate_tree": cand_res["tree"], "handlers_modelled": cand_res["handlers_modelled"],
              "base_findings": len(base_res["findings"]), "candidate_findings": len(cand_res["findings"]), "new": d["new"], "fixed": len(d["fixed"]),
              "unchanged": d["unchanged"], "durations_s": {"base": base_res["duration_s"], "candidate": cand_res["duration_s"]}}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    md = [f"# pysa judge — {verdict}", "", f"base `{a.base}` ({len(base_res['findings'])} flows, cached={report['base_cached']}) → candidate `{a.candidate}` ({len(cand_res['findings'])} flows): "
          f"**{len(d['new'])} new**, {len(d['fixed'])} fixed, {d['unchanged']} unchanged", ""]
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
    s.set_defaults(fn=cmd_setup)
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
        q.set_defaults(fn=fn)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
