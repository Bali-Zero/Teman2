#!/usr/bin/env python3
"""tg_gateway_census.py — which tg_notify.py each active crontab entry actually resolves.

Read-only, and not by promise: every evaluation below runs under sandbox-exec (no write,
no network, no exec but its own interpreter), and without it the census refuses to run.
PWC-7033 C1: the producers reaching the non-routing HOME fork
`~/scripts/tg_notify.py` were counted twice by WRAPPER NAME and were wrong twice
(#7039: 24, #7047: 52, the #7047 gate: at least 74). This census counts by the
gateway each entry RESOLVES, running the producer's own resolution code:

  shell   the file's plain assignments and its `[ -f "$V" ] || V=...` fallbacks
          are executed verbatim by bash, with $0 set to the path the file was
          INVOKED by (a file symlink keeps `dirname "$0"` at the link's dir) and
          the entry's own arguments as $1.. (so `run.sh <job>` dispatch resolves).
  python  a function holding a 'tg_notify.py' literal is called if every call in
          it is a path/env lookup; otherwise only the assignment and the `if`
          fallbacks right after it run. Module-level names they need, likewise.
          os.environ holds HOME and the crontab's TG_*/NUZANTARA_* variables only.

What a command runs is followed, not every word on it: the word in command position,
the script an interpreter is given, the arguments of a script it runs (wrappers run
them), `bash -c STR ARG0` with ARG0 as $0. Inside a script: script paths on code
lines, variables holding one, relative ones placed by the script's own `cd`, and
`source` (which keeps the caller's $0 and arguments); in Python, sibling modules and
packages from the script's dir and from any `sys.path` entry the file adds, and
script paths passed to subprocess. A file is followed if it ends .sh/.py or starts
with `#!`. Crontab `TG_*`/`NUZANTARA_*` variables reach the resolvers' env.

A resolver counts if the entry LOADS it, called on this run's path or not: `reach` is
what the entry's code can resolve. Anything named that this census cannot run —
a gateway in an unmodelled shape, an unplaceable relative script, `python -m`, a
chain deeper than MAX_DEPTH — is UNRESOLVED, never guessed, and the exit says so.
Not modelled, and therefore stated where a number is quoted: env set by files the
job sources at run time. `routes` = the resolved file contains `gateway_routed`,
the measure of docs/specs/seat-board-drain-v1.md §1.

Exit: 0 = every entry resolved · 3 = at least one UNRESOLVED · 2 = usage error.
Usage: python3 scripts/tg_gateway_census.py [--crontab FILE] [--json]
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

GATEWAY = "tg_notify.py"
MAX_DEPTH = 6
SCHEDULE_RE = re.compile(r"^\s*(@\w+|[0-9*])")
ENV_LINE_RE = re.compile(r"^\s*[A-Za-z_]\w*=")
OPERATOR_RE = re.compile(r"^[|;&<>()]+$")
HOME_PREFIX_RE = re.compile(r"^(~|\$HOME|\$\{HOME\})(?=/)")
SCRIPT_WORD_RE = re.compile(r"\.(sh|py)$")
MESSAGE_LINE_RE = re.compile(r"^\s*(echo|log\w*|printf|warn|die|err)\b")
SH_PATH_RE = re.compile(r"""(?<![\w}$./-])(?:~|\$HOME|\$\{HOME\}|\$\(dirname "\$0"\))?/[\w./-]*\w""")
SH_VARPATH_RE = re.compile(r"\$\{?([A-Za-z_]\w*)\}?(/[\w./-]+\.(?:sh|py))\b")
SH_ASSIGN_RE = re.compile(r"^\s*(?:export\s+|local\s+|readonly\s+|declare(?:\s+-\w+)*\s+)?([A-Za-z_]\w*)=(.*?)\s*$")
SH_FALLBACK_RE = re.compile(r'^\s*\[\[? -f "\$\{?([A-Za-z_]\w*)\}?" \]\]? \|\| \1=(.*?)\s*$')
SH_SOURCE_RE = re.compile(r"^\s*(?:source|\.)\s+(\S+)")
SH_CD_RE = re.compile(r"^\s*cd\s+(.+?)\s*(?:\|\||&&|;|$)")
SH_REL_RE = re.compile(
    r"""(?:^\s*|[;&|(]\s*|\b(?:exec|bash|sh|zsh|python3?|source|nohup)\s+|"\$\{?\w+\}?"\s+|\$\{?\w+\}?\s+)"""
    r"""((?:\./)?[\w-][\w.-]*(?:/[\w.-]+)*\.(?:sh|py))(?![\w/])"""
)
SUBST_OK_RE = re.compile(  # the only command substitutions run: dirname, and cd+pwd into a plain path
    r'\$\(cd "(?:[\w./~-]|\$\{?\w+\}?|\$\(dirname "\$(?:0|\{?\w+\}?)"\))*" && pwd(?: -P)?\)'
    r'|\$\(dirname "\$(?:0|\{?\w+\}?)"\)'
)
CASE_ARM_RE = re.compile(r"^\s*[\w*|.@-]+\)\s+(.*?)\s*;;\s*$")
PY_NAME_CALLS = {"Path", "str"}
PY_ATTR_CALLS = {
    "get", "getenv", "expanduser", "resolve", "absolute", "is_file", "isfile",
    "exists", "home", "joinpath", "dirname", "abspath", "realpath", "join",
}
PY_BANNED = (ast.While, ast.Lambda, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom, ast.ClassDef,
             ast.With, ast.AsyncWith, ast.Await)
INTERPRETER_RE = re.compile(r"^(?:bash|sh|zsh|dash|python[\d.]*|exec|nohup|env|nice|caffeinate|time|timeout)$")
ENV_PASS_RE = re.compile(r"^(?:TG|NUZANTARA)_\w+$")  # the only env the resolvers on Pro read, besides HOME
SH_SPECIAL_RE = re.compile(r"^(?:PATH|IFS|ENV|CDPATH|GLOBIGNORE|PS4|PROMPT_COMMAND|SHELLOPTS|FUNCNEST|BASH\w*)$")
SANDBOX = "/usr/bin/sandbox-exec"
# Every evaluation runs in a macOS sandbox: no write but /dev/null, no network, no signal to another
# process, and no exec but the interpreter it was started for (and dirname for bash). The allow-lists
# above decide what is WORTH running; this decides what CAN happen if one of them is wrong.
SANDBOX_PROFILE = (
    '(version 1)(allow default)(deny file-write*)(allow file-write-data (literal "/dev/null"))'
    "(deny network*)(deny signal (target others))(deny process-exec)(allow process-exec {allow})"
)
PY_CHILD = r"""
import json, os, sys
from pathlib import Path
req = json.load(sys.stdin)
class _Path:  # os.path without a way back to the real os module
    join, dirname, basename = staticmethod(os.path.join), staticmethod(os.path.dirname), staticmethod(os.path.basename)
    abspath, realpath = staticmethod(os.path.abspath), staticmethod(os.path.realpath)
    isfile, exists, expanduser = staticmethod(os.path.isfile), staticmethod(os.path.exists), staticmethod(os.path.expanduser)
class _Os:
    path = _Path
    environ = req["env"]
    @staticmethod
    def getenv(k, d=None):
        return _Os.environ.get(k, d)
ns = {"__builtins__": {"list": list, "str": str, "len": len}, "Path": Path, "os": _Os, "__file__": req["file"]}
for src in req["deps"]:
    try:
        exec(src, ns)
    except Exception:
        pass
try:
    exec(req["code"], ns)
    out = ns[req["call"]]() if req["call"] else ns[req["var"]]
    print(json.dumps({"out": str(out) if out else ""}))
except Exception:
    print(json.dumps({"out": None}))
"""


def _jail(argv: list[str], literals: list[str], subpaths: list[str] = ()) -> list[str]:
    allow = " ".join([*(f'(literal "{x}")' for x in literals), *(f'(subpath "{x}")' for x in subpaths)])
    return [SANDBOX, "-p", SANDBOX_PROFILE.format(allow=allow), *argv]
PY_SPAWN = {"run", "Popen", "call", "check_call", "check_output", "system", "execv", "execvp"}


def _expand(word: str, home: str) -> str:
    return HOME_PREFIX_RE.sub(home, word)


def _safe_rhs(rhs: str) -> bool:
    """True if bash can evaluate this assignment's right side without running a command."""
    rhs = SUBST_OK_RE.sub("", rhs)
    if any(t in rhs for t in ("`", "$(", "$[", "\\", "${!", "${ ", "${|", "${\t", "${\n")):
        return False
    for inner in re.findall(r"\$\{([^}]*)\}", rhs):  # no subscript, transform or arithmetic offset
        if "[" in inner or "@" in inner or re.match(r"\w+:(?![-=?+])", inner):
            return False
    if len(rhs) >= 2 and rhs[0] == rhs[-1] == '"':
        return '"' not in rhs[1:-1]
    return re.fullmatch(r"[\w./~${}:+=@%-]*", rhs) is not None


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def _calls_ok(nodes: list) -> bool:
    """True if running these nodes can only look paths and env up: no other call, no rebinding."""
    for c in (c for n in nodes for c in ast.walk(n)):
        if isinstance(c, PY_BANNED) or (isinstance(c, ast.Attribute) and c.attr.startswith("_")):
            return False
        if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)) and c not in nodes:
            return False
        if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Store) and c.id in PY_NAME_CALLS | {"os"}:
            return False
        if isinstance(c, (ast.Attribute, ast.Subscript, ast.Starred)) and isinstance(c.ctx, (ast.Store, ast.Del)):
            return False
        if isinstance(c, ast.Delete):
            return False
        if isinstance(c, ast.Call) and not (
            (isinstance(c.func, ast.Name) and c.func.id in PY_NAME_CALLS)
            or (isinstance(c.func, ast.Attribute) and c.func.attr in PY_ATTR_CALLS)
        ):
            return False
    return True


class Result:
    def __init__(self, lineno: int):
        self.lineno = lineno
        self.invoked: list[str] = []
        self.gateways: dict[str, set[str]] = {}
        self.reasons: list[str] = []
        self.not_runnable = False
        self.seen: set[tuple[str, str]] = set()
        self.pyroots: set[str] = set()
        self.env: dict[str, str] = {}

    def gateway(self, path: str, via: str) -> None:
        key = os.path.realpath(path) if path and os.path.isfile(path) else f"MISSING:{path or '-'}"
        self.gateways.setdefault(key, set()).add(via)

    def unresolved(self, why: str) -> None:
        if why not in self.reasons:
            self.reasons.append(why)


class Census:
    def __init__(self, home: str):
        self.home = home
        self._env: dict[str, str] = {}

    # ---- shell -------------------------------------------------------------
    def _sh_eval(self, lines: list[str], zero: str, src: str, args: list[str] | None, res: Result):
        body = ["__src=" + shlex.quote(src)]
        gw_vars: set[str] = set()
        for n, ln in enumerate(lines, 1):
            if ln.lstrip().startswith("#"):
                continue
            ln = ln.replace("${BASH_SOURCE[0]}", "${__src}")
            arm = CASE_ARM_RE.match(ln)
            ln = arm.group(1) if arm else ln
            cd = SH_CD_RE.match(ln)
            if cd and _safe_rhs(cd.group(1)):
                # a `cd "$V"` is run once per value V takes anywhere in the file: branches are not guessed
                step = f"cd {cd.group(1)} 2>/dev/null && printf 'C {n}=%s\\n' \"$PWD\""
                refs = sorted(set(re.findall(r"\$\{?([A-Za-z_]\w*)\}?", cd.group(1))) - {"HOME", "__src"})
                body.append(f'for __v in "${{__all_{refs[0]}[@]}}"; do ( {refs[0]}="$__v"; {step} ); done'
                            if len(refs) == 1 else f"( {step} )")
                continue
            m = SH_ASSIGN_RE.match(ln)
            if m and _safe_rhs(m.group(2)) and not SH_SPECIAL_RE.match(m.group(1)):
                name = m.group(1)
                body += [f"{name}={m.group(2)}", f'__all_{name}+=("${name}")',
                         f"printf 'V %s=%s\\n' {name} \"${name}\""]
                if GATEWAY in m.group(2):
                    if args is None and re.search(r"\$\{?[1-9@*]", m.group(2)):
                        res.unresolved(f"{src}:{n} builds the gateway from arguments this census cannot see")
                    gw_vars.add(name)
                    body.append(f"printf 'G %s=%s\\n' {name} \"${name}\"")
                continue
            f = SH_FALLBACK_RE.match(ln)
            if f and f.group(1) in gw_vars and _safe_rhs(f.group(2)):
                name = f.group(1)
                body += [f'[ -f "${name}" ] || {name}={f.group(2)}', f"printf 'G %s=%s\\n' {name} \"${name}\""]
        proc = subprocess.run(
            _jail(["/bin/bash", "--noprofile", "--norc", "-c", "\n".join(body), zero, *(args or [])],
                  ["/bin/bash", "/usr/bin/dirname"]),
            capture_output=True, text=True, timeout=15, cwd=self.home,
            env={**res.env, "HOME": self.home, "PATH": "/usr/bin:/bin"},
        )
        values: dict[str, list[str]] = {}
        final: dict[str, str] = {}
        cds: list[tuple[int, str]] = []
        for out in proc.stdout.splitlines():
            kind, _, kv = out.partition(" ")
            name, _, val = kv.partition("=")
            if kind == "V" and name not in gw_vars:
                values.setdefault(name, []).append(val)
            elif kind == "G":
                final[name] = val
            elif kind == "C":
                cds.append((int(name), val))
        return values, final, cds

    def _walk_sh(self, text: str, p: str, zero: str, args: list[str], depth: int, res: Result) -> None:
        lines = text.splitlines()
        values, final, cds = self._sh_eval(lines, zero, p, args, res)
        for g in final.values():
            res.gateway(g, p)
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("#") or not ln.strip():
                continue
            m = SH_ASSIGN_RE.match(ln)
            resolver = bool(SH_FALLBACK_RE.match(ln) or (m and m.group(1) in final))
            message = bool(MESSAGE_LINE_RE.match(ln))
            src = SH_SOURCE_RE.match(ln)
            paths = [_expand(w.replace('$(dirname "$0")', os.path.dirname(zero)), self.home)
                     for w in SH_PATH_RE.findall(ln)]
            paths += [v + vm.group(2) for vm in SH_VARPATH_RE.finditer(ln) if vm.group(1) != "HOME"
                      for v in values.get(vm.group(1), [])]
            for path in paths:
                if resolver or message or not path.startswith("/"):
                    continue
                if os.path.basename(path) == GATEWAY:
                    res.gateway(path, p)
                else:
                    self._walk(path, args if src else None, zero if src else path, depth + 1, res)
            placed = False
            for rel in ([] if message else SH_REL_RE.findall(ln.split(" #")[0])):
                found = {os.path.realpath(c): c for c in (os.path.normpath(os.path.join(d, rel))
                                                          for n, d in cds if n < i + 1) if os.path.isfile(c)}
                if len(found) == 1:
                    placed = True
                    path = next(iter(found.values()))
                    self._walk(path, args if src else None, zero if src else path, depth + 1, res)
                elif os.path.basename(rel) != os.path.basename(zero):
                    where = f"is ambiguous: {sorted(found)}" if found else "has no directory this census can place"
                    res.unresolved(f"{p}:{i + 1} runs {rel}, which {where}")
            if GATEWAY in ln and not (resolver or message or paths or placed):
                res.unresolved(f"{p}:{i + 1} names {GATEWAY} in a shape this census does not run")
            if m or message:
                continue
            for name, vals in values.items():
                if re.search(rf"\$(?:\{{{name}\}}|{name}(?!\w))", ln):
                    for v in vals:
                        if v.startswith("/"):
                            self._walk(v, args if src else None, zero if src else v, depth + 1, res)

    # ---- python ------------------------------------------------------------
    @staticmethod
    def _scope(node: ast.AST, parents: dict) -> ast.AST | None:
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                return node
        return None

    def _py_exec(self, tree: ast.Module, code: list, call: str | None, var: str | None, p: str,
                 res_env: dict | None = None, scope: ast.AST | None = None) -> str | None:
        res_env = res_env or {}
        ns = {"Path", "os", "__file__", "list", "str", "len"}
        line = min(getattr(c, "lineno", 0) for c in code)
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        defs: dict[str, list] = {}  # every simple (annotated) assignment with the scope it binds in
        for st in ast.walk(tree):
            tgt = st.targets[0] if isinstance(st, ast.Assign) and len(st.targets) == 1 else \
                st.target if isinstance(st, ast.AnnAssign) and st.value is not None else None
            if isinstance(tgt, ast.Name):
                defs.setdefault(tgt.id, []).append((self._scope(st, parents), st))
        pick: dict[str, ast.stmt] = {}
        todo = [(n.id, scope) for c in code for n in ast.walk(c) if isinstance(n, ast.Name)]
        while todo:  # Python scoping: the name's own function first, then the module; never a sibling's local
            name, sc = todo.pop()
            if name in pick or name in ns:
                continue
            local = sorted((st for w, st in defs.get(name, []) if sc is not None and w is sc and st.lineno < line),
                           key=lambda st: st.lineno)
            glob = sorted((st for w, st in defs.get(name, []) if w is None), key=lambda st: st.lineno)
            if not glob and not local:
                continue
            if local:
                pick[name] = local[-1]
            elif sc is not None:
                pick[name] = glob[-1]  # a function runs after the module has loaded: its last binding
            else:
                pick[name] = next((st for st in reversed(glob) if st.lineno < line), glob[0])
            todo += [(n.id, self._scope(pick[name], parents)) for n in ast.walk(pick[name].value)
                     if isinstance(n, ast.Name)]
        req = {
            "deps": [ast.unparse(st) for st in sorted(pick.values(), key=lambda st: st.lineno) if _calls_ok([st])],
            "code": ast.unparse(ast.fix_missing_locations(ast.Module(body=code, type_ignores=[]))),
            "call": call, "var": var, "file": p, "env": {**res_env, "HOME": self.home},
        }
        exe = sys.executable
        proc = subprocess.run(
            _jail([exe, "-I", "-S", "-c", PY_CHILD], [exe, os.path.realpath(exe)], [sys.base_prefix]),
            input=json.dumps(req), capture_output=True, text=True, timeout=15, cwd="/", env={"HOME": self.home},
        )
        try:
            return json.loads(proc.stdout.strip().splitlines()[-1])["out"]
        except (ValueError, IndexError, KeyError):
            return None

    def _py_slice(self, tree: ast.Module, node: ast.AST, parents: dict):
        """(code, call, var) that computes the gateway this literal belongs to, or None."""
        fn, stmt, cur = None, None, node
        while cur in parents:
            cur = parents[cur]
            if stmt is None and isinstance(cur, ast.stmt):
                stmt = cur
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = cur
                break
        pure = copy.copy(fn)
        if pure is not None:
            pure.decorator_list, pure.returns = [], None
        if pure is not None and _calls_ok([pure]) and not fn.args.args and stmt is not fn:
            return [pure], fn.name, None, None
        if not (isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)):
            return None
        block = next((v for _, v in ast.iter_fields(parents[stmt]) if isinstance(v, list) and stmt in v), [stmt])
        var = stmt.targets[0].id
        code: list = [stmt]
        for s in block[block.index(stmt) + 1:]:
            names = {n.id for n in ast.walk(s.test) if isinstance(n, ast.Name)} if isinstance(s, ast.If) else set()
            if var not in names or not all(isinstance(b, ast.Assign) for b in s.body):
                break
            code.append(s)
        return (code, None, var, fn) if _calls_ok(code) else None

    def _py_value(self, tree: ast.Module, expr: ast.expr, p: str, scope: ast.AST | None) -> str | None:
        assign = ast.copy_location(ast.Assign(targets=[ast.Name(id="_v", ctx=ast.Store())], value=expr), expr)
        return self._py_exec(tree, [assign], None, "_v", p, self._env, scope) if _calls_ok([assign]) else None

    def _walk_py(self, text: str, p: str, depth: int, res: Result, imported: bool) -> None:
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            res.unresolved(f"{p}: unparseable ({e.msg})")
            return
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        here = os.path.dirname(os.path.realpath(p))
        if not imported:
            res.pyroots.add(here)  # sys.path[0] of a script run by path
        nodes = sorted(ast.walk(tree), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
        for node in nodes:  # sys.path extensions first, evaluated by the file's own expression
            if isinstance(node, ast.Call) and _call_name(node) in ("insert", "append") and node.args \
                    and isinstance(node.func, ast.Attribute) and ast.unparse(node.func.value) == "sys.path":
                root = self._py_value(tree, node.args[-1], p, self._scope(node, parents))
                if root:
                    res.pyroots.add(root)
                else:
                    res.unresolved(f"{p}:{node.lineno} extends sys.path by an expression this census cannot run")
        hits = []
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    mods, roots = [a.name for a in node.names], [here, *sorted(res.pyroots)]
                else:
                    base = node.module or ""
                    mods = [base, *(f"{base}.{a.name}".lstrip(".") for a in node.names)]
                    up = here
                    for _ in range(node.level - 1):
                        up = os.path.dirname(up)
                    roots = [up] if node.level else [here, *sorted(res.pyroots)]
                for mod in filter(None, mods):
                    if mod.split(".")[0] == "tg_notify":
                        res.unresolved(f"{p}:{node.lineno} imports tg_notify (resolution by sys.path)")
                        continue
                    rel = mod.replace(".", "/")
                    for cand in (os.path.join(r, rel + ext) for r in roots for ext in (".py", "/__init__.py")):
                        if os.path.isfile(cand):
                            self._walk(cand, [], cand, depth + 1, res, imported=True)
                            break
            elif isinstance(node, ast.Call) and _call_name(node) in PY_SPAWN:
                for arg in (e for a in node.args for e in (a.elts if isinstance(a, (ast.List, ast.Tuple)) else [a])):
                    val = arg.value if isinstance(arg, ast.Constant) else \
                        self._py_value(tree, arg, p, self._scope(node, parents))
                    child = os.path.expanduser(val) if isinstance(val, str) else ""
                    if SCRIPT_WORD_RE.search(child) and os.path.isabs(child) and os.path.basename(child) != GATEWAY:
                        self._walk(child, [], child, depth + 1, res)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and GATEWAY in node.value \
                    and not isinstance(parents.get(node), ast.Expr) and not re.search(r"\s", node.value) \
                    and not self._in_test(node, parents):
                hits.append(node)
        covered: set = set()
        for node in hits:
            if node in covered:
                continue
            sl = self._py_slice(tree, node, parents)
            if sl is None:
                if node.value.startswith(("/", "~/")):
                    res.gateway(os.path.expanduser(node.value), p)
                else:
                    res.unresolved(f"{p}:{node.lineno} names {GATEWAY} in a shape this census does not run")
                continue
            covered |= {n for c in sl[0] for n in ast.walk(c)}
            gw = self._py_exec(tree, sl[0], sl[1], sl[2], p, res.env, sl[3])
            if gw is None:
                res.unresolved(f"{p}:{node.lineno} gateway resolver raised when run in isolation")
            else:
                res.gateway(gw, p)

    @staticmethod
    def _in_test(node: ast.AST, parents: dict) -> bool:
        """A literal inside an `if`/`assert` test only probes that the gateway exists; it sends nothing."""
        cur = node
        while cur in parents and not isinstance(cur, ast.stmt):
            par = parents[cur]
            if isinstance(par, (ast.If, ast.While, ast.Assert, ast.IfExp)) and par.test is cur:
                return True
            cur = par
        return False

    # ---- walk --------------------------------------------------------------
    def _walk(self, p: str, args: list[str] | None, zero: str, depth: int, res: Result,
              imported: bool = False) -> None:
        real = os.path.realpath(p)
        if (real, zero) in res.seen or not os.path.isfile(real):
            return
        if GATEWAY in (os.path.basename(p), os.path.basename(real)):
            res.gateway(p, p)
            return
        try:
            with open(real, "rb") as fh:
                if not (SCRIPT_WORD_RE.search(real) or fh.read(2) == b"#!"):
                    return  # data, a log, a binary: nothing this census can follow runs from it
            if depth > MAX_DEPTH:
                res.unresolved(f"{p}: a chain deeper than {MAX_DEPTH} is not followed")
                return
            res.seen.add((real, zero))
            text = Path(real).read_text(errors="replace")
        except OSError as e:
            res.unresolved(f"{p}: unreadable ({e.strerror})")
            return
        self._env = res.env
        if real.endswith(".py") or text.startswith("#!") and "python" in text.split("\n", 1)[0]:
            self._walk_py(text, p, depth, res, imported)
        else:
            self._walk_sh(text, p, zero, args, depth, res)

    def _command(self, cmd: str, res: Result, top: bool, zero: str | None = None) -> None:
        """Follow what a command line RUNS: the word in command position, the script an interpreter
        is given, and the arguments of a script it runs (wrappers run their arguments)."""
        try:
            lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            toks = list(lex)
        except ValueError as e:
            res.unresolved(f"command not tokenizable ({e})")
            return
        cwd, cmdpos, wrapped, first = None, True, False, top
        for i, tok in enumerate(toks):
            prev = toks[i - 1] if i else ""
            if OPERATOR_RE.match(tok):
                if not any(c in tok for c in "<>"):
                    cmdpos, wrapped = True, False
                continue
            if OPERATOR_RE.match(prev) and any(c in prev for c in "<>"):
                continue  # a redirect target
            if " " in tok:
                flag_c = prev.startswith("-") and "c" in prev
                nxt = toks[i + 1] if flag_c and i + 1 < len(toks) and not OPERATOR_RE.match(toks[i + 1]) else None
                self._command(tok, res, False, _expand(nxt, self.home) if nxt else None)
                continue
            if not (cmdpos or wrapped):
                continue
            if cmdpos and ENV_LINE_RE.match(tok):
                name, _, val = tok.partition("=")
                if ENV_PASS_RE.match(name):
                    res.env[name] = val
                continue
            if tok.startswith("-"):
                if tok == "-m" and i + 1 < len(toks):
                    res.unresolved(f"python -m {toks[i + 1]} is not followed")
                continue
            base = os.path.basename(tok)
            if tok == "cd" and i + 1 < len(toks):
                cwd = _expand(toks[i + 1], self.home) if _expand(toks[i + 1], self.home).startswith("/") else cwd
                cmdpos = False
                continue
            if INTERPRETER_RE.match(base) or base in ("source", "."):
                continue
            path = _expand(tok, self.home)
            if not path.startswith(("/", "./")) and not SCRIPT_WORD_RE.search(path):
                cmdpos = False  # a command found on PATH (echo, curl, git): its arguments are not run
                continue
            if not path.startswith("/"):
                if not cwd:
                    res.unresolved(f"relative invocation {tok} with no `cd` before it is not followed")
                    continue
                path = os.path.normpath(os.path.join(cwd, path))
            res.invoked.append(path)
            if first and not os.path.isfile(os.path.realpath(path)):
                res.not_runnable = True
            first = False
            sourced = prev in ("source", ".")
            args = []
            for t in toks[i + 1:]:
                if OPERATOR_RE.match(t):
                    break
                args.append(t)
            self._walk(path, args, (zero or "sh") if sourced else path, 0, res)
            cmdpos, wrapped = False, True

    def entry(self, lineno: int, line: str, env: dict[str, str]) -> Result:
        res = Result(lineno)
        res.env = dict(env)
        fields = line.split()
        self._command(" ".join(fields[1:] if fields[0].startswith("@") else fields[5:]), res, True)
        return res


def routes(gateway: str) -> bool:
    try:
        return "gateway_routed" in Path(gateway).read_text(errors="replace")
    except OSError:
        return False


def census(crontab: str, home: str) -> dict:
    c = Census(home)
    rows, env = [], {}
    for n, line in enumerate(crontab.splitlines(), 1):
        s = line.strip()
        if ENV_LINE_RE.match(s):  # crontab env applies to every entry below it
            name, _, val = s.partition("=")
            if ENV_PASS_RE.match(name.strip()):
                env[name.strip()] = val.strip().strip("\"'")
            continue
        if not s or s.startswith("#") or not SCHEDULE_RE.match(s):
            continue
        r = c.entry(n, s, env)
        rows.append({
            "line": n,
            "invoked": r.invoked,
            "not_runnable": r.not_runnable,
            "gateways": [{"path": g, "routes": routes(g), "via": sorted(v)} for g, v in sorted(r.gateways.items())],
            "unresolved": r.reasons,
        })
    run = [r for r in rows if not r["not_runnable"]]
    summary = {
        "active": len(rows),
        "not_runnable": len(rows) - len(run),
        "unresolved": sum(1 for r in rows if r["unresolved"]),
        "reach_nonrouting": sum(1 for r in run if any(not g["routes"] and not g["path"].startswith("MISSING:")
                                                      for g in r["gateways"])),
        "reach_routing_only": sum(1 for r in run if r["gateways"] and all(g["routes"] for g in r["gateways"])),
        "reach_missing": sum(1 for r in run if any(g["path"].startswith("MISSING:") for g in r["gateways"])),
        "reach_none": sum(1 for r in run if not r["gateways"]),
    }
    by_gw: dict[str, dict] = {}
    for r in run:
        for g in r["gateways"]:
            e = by_gw.setdefault(g["path"], {"routes": g["routes"], "entries": 0, "via": {}})
            e["entries"] += 1
            for v in g["via"]:
                e["via"][v] = e["via"].get(v, 0) + 1
    return {"home": home, "entries": rows, "by_gateway": by_gw, "summary": summary}


def _short(p: str, home: str) -> str:
    return p.replace(home + "/", "~/")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--crontab", help="read this file instead of `crontab -l`")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    home = str(Path.home())
    if not os.path.exists(SANDBOX):
        print(f"{SANDBOX} not found: this census evaluates producer code only inside it", file=sys.stderr)
        return 2
    if a.crontab:
        text = Path(a.crontab).read_text()
    else:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"crontab -l failed: {proc.stderr.strip()}", file=sys.stderr)
            return 2
        text = proc.stdout
    out = census(text, home)
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for r in out["entries"]:
            state = "NOT-RUNNABLE" if r["not_runnable"] else ",".join(
                ("routing:" if g["routes"] else "NONROUTING:") + _short(g["path"], home) for g in r["gateways"]
            ) or "none"
            print(f"L{r['line']}\t{state}\t{' '.join(_short(p, home) for p in r['invoked'])}")
            for why in r["unresolved"]:
                print(f"\tUNRESOLVED {_short(why, home)}")
        print("## by gateway: entries, routes, and the resolving file AS INVOKED with its entry count")
        for g, e in sorted(out["by_gateway"].items()):
            via = ", ".join(f"{_short(v, home)}={n}" for v, n in sorted(e["via"].items()))
            print(f"{e['entries']}\t{_short(g, home)}\troutes={'yes' if e['routes'] else 'no'}\t{via}")
        print("## summary\n" + " ".join(f"{k}={v}" for k, v in out["summary"].items()))
    return 3 if out["summary"]["unresolved"] else 0


if __name__ == "__main__":
    sys.exit(main())
