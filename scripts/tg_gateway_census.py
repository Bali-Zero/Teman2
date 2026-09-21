#!/usr/bin/env python3
"""tg_gateway_census.py — which tg_notify.py each active crontab entry actually resolves.

Read-only. PWC-7033 C1: the producers reaching the non-routing HOME fork
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
          os.environ is empty but for HOME: TG_NOTIFY_BIN is set nowhere on Pro.

Children are followed the way the producer reaches them: script paths on code
lines, variables holding a script path, `source` (which keeps the caller's $0),
sibling-module imports, script paths passed to subprocess. Anything else that
names the gateway is UNRESOLVED, never guessed: the counts are then a floor, and
the exit code says so. `routes` = the resolved file contains `gateway_routed`,
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
SH_PATH_RE = re.compile(r"""(?<![\w}$./-])(?:~|\$HOME|\$\{HOME\}|\$\(dirname "\$0"\))?/[\w./-]+\.(?:sh|py)\b""")
SH_VARPATH_RE = re.compile(r"\$\{?([A-Za-z_]\w*)\}?(/[\w./-]+\.(?:sh|py))\b")
SH_ASSIGN_RE = re.compile(r"^\s*(?:export\s+|local\s+|readonly\s+|declare(?:\s+-\w+)*\s+)?([A-Za-z_]\w*)=(.*?)\s*$")
SH_FALLBACK_RE = re.compile(r'^\s*\[\[? -f "\$\{?([A-Za-z_]\w*)\}?" \]\]? \|\| \1=(.*?)\s*$')
SH_SOURCE_RE = re.compile(r"^\s*(?:source|\.)\s+(\S+)")
SUBST_OK = (
    '$(cd "$(dirname "$0")" && pwd)',
    '$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)',
    '$(dirname "$0")',
    '$(dirname "${BASH_SOURCE[0]}")',
)
PY_CALLS_OK = {
    "Path", "str", "get", "getenv", "expanduser", "resolve", "absolute", "is_file", "isfile",
    "exists", "home", "joinpath", "dirname", "abspath", "realpath", "join",
}
PY_SPAWN = {"run", "Popen", "call", "check_call", "check_output", "system", "execv", "execvp"}


def _expand(word: str, home: str) -> str:
    return HOME_PREFIX_RE.sub(home, word)


def _safe_rhs(rhs: str) -> bool:
    """True if bash can evaluate this assignment's right side without running a command."""
    for s in SUBST_OK:
        rhs = rhs.replace(s, "")
    if "`" in rhs or "$(" in rhs:
        return False
    if len(rhs) >= 2 and rhs[0] == rhs[-1] == '"':
        return '"' not in rhs[1:-1]
    return re.fullmatch(r"[\w./~${}:+=@%-]*", rhs) is not None


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def _calls_ok(nodes: list) -> bool:
    return all(_call_name(c) in PY_CALLS_OK for n in nodes for c in ast.walk(n) if isinstance(c, ast.Call))


class Result:
    def __init__(self, lineno: int):
        self.lineno = lineno
        self.invoked: list[str] = []
        self.gateways: dict[str, set[str]] = {}
        self.reasons: list[str] = []
        self.not_runnable = False
        self.seen: set[tuple[str, str]] = set()

    def gateway(self, path: str, via: str) -> None:
        key = os.path.realpath(path) if path and os.path.isfile(path) else f"MISSING:{path or '-'}"
        self.gateways.setdefault(key, set()).add(via)

    def unresolved(self, why: str) -> None:
        if why not in self.reasons:
            self.reasons.append(why)


class Census:
    def __init__(self, home: str):
        self.home = home

    # ---- shell -------------------------------------------------------------
    def _sh_eval(self, lines: list[str], zero: str, src: str, args: list[str]):
        body = ["__src=" + shlex.quote(src)]
        gw_vars: set[str] = set()
        for ln in lines:
            if ln.lstrip().startswith("#"):
                continue
            ln = ln.replace("${BASH_SOURCE[0]}", "${__src}")
            m = SH_ASSIGN_RE.match(ln)
            if m and _safe_rhs(m.group(2)):
                name = m.group(1)
                body += [f"{name}={m.group(2)}", f"printf 'V %s=%s\\n' {name} \"${name}\""]
                if GATEWAY in m.group(2):
                    gw_vars.add(name)
                    body.append(f"printf 'G %s=%s\\n' {name} \"${name}\"")
                continue
            f = SH_FALLBACK_RE.match(ln)
            if f and f.group(1) in gw_vars and _safe_rhs(f.group(2)):
                name = f.group(1)
                body += [f'[ -f "${name}" ] || {name}={f.group(2)}', f"printf 'G %s=%s\\n' {name} \"${name}\""]
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", "\n".join(body), zero, *args],
            capture_output=True, text=True, timeout=15, cwd="/",
            env={"HOME": self.home, "PATH": "/usr/bin:/bin"},
        )
        values: dict[str, list[str]] = {}
        final: dict[str, str] = {}
        for out in proc.stdout.splitlines():
            kind, _, kv = out.partition(" ")
            name, _, val = kv.partition("=")
            if kind == "V" and name not in gw_vars:
                values.setdefault(name, []).append(val)
            elif kind == "G":
                final[name] = val
        return values, final

    def _walk_sh(self, text: str, p: str, zero: str, args: list[str], depth: int, res: Result) -> None:
        lines = text.splitlines()
        values, final = self._sh_eval(lines, zero, p, args)
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
                    self._walk(path, [], zero if src else path, depth + 1, res)
            if GATEWAY in ln and not (resolver or message or paths):
                res.unresolved(f"{p}:{i + 1} names {GATEWAY} in a shape this census does not run")
            if m or message:
                continue
            for name, vals in values.items():
                if re.search(rf"\$(?:\{{{name}\}}|{name}(?!\w))", ln):
                    for v in vals:
                        if v.startswith("/") and SCRIPT_WORD_RE.search(v):
                            self._walk(v, [], zero if src else v, depth + 1, res)

    # ---- python ------------------------------------------------------------
    def _py_exec(self, tree: ast.Module, code: list, call: str | None, var: str | None, p: str) -> str | None:
        class _Os:
            path = os.path
            environ = {"HOME": self.home}

            @staticmethod
            def getenv(k, d=None):
                return _Os.environ.get(k, d)

        ns: dict = {"__builtins__": {"list": list, "str": str, "len": len}, "Path": Path, "os": _Os, "__file__": p}
        top = {t.id: st for st in tree.body if isinstance(st, ast.Assign)
               for t in st.targets if isinstance(t, ast.Name)}
        need = {n.id for c in code for n in ast.walk(c) if isinstance(n, ast.Name)}
        grew = True
        while grew:
            extra = {n.id for k in need if k in top for n in ast.walk(top[k].value) if isinstance(n, ast.Name)}
            grew = not extra <= need
            need |= extra
        for st in tree.body:
            if st in top.values() and any(isinstance(t, ast.Name) and t.id in need for t in st.targets) \
                    and _calls_ok([st.value]):
                try:
                    exec(compile(ast.Module(body=[st], type_ignores=[]), p, "exec"), ns)
                except Exception:
                    pass
        try:
            exec(compile(ast.fix_missing_locations(ast.Module(body=code, type_ignores=[])), p, "exec"), ns)
            out = ns[call]() if call else ns[var]
        except Exception:
            return None
        return str(out) if out else ""

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
        if fn is not None and _calls_ok([fn]) and not fn.args.args and not stmt is fn:
            pure = copy.copy(fn)
            pure.decorator_list, pure.returns = [], None
            return [pure], fn.name, None
        body = fn.body if fn is not None else tree.body
        while stmt is not None and stmt not in body:
            stmt = parents.get(stmt)
        if not (isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)):
            return None
        var = stmt.targets[0].id
        code: list = [stmt]
        for s in body[body.index(stmt) + 1:]:
            names = {n.id for n in ast.walk(s.test) if isinstance(n, ast.Name)} if isinstance(s, ast.If) else set()
            if var not in names or not all(isinstance(b, ast.Assign) for b in s.body):
                break
            code.append(s)
        return (code, None, var) if _calls_ok(code) else None

    def _walk_py(self, text: str, p: str, depth: int, res: Result) -> None:
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            res.unresolved(f"{p}: unparseable ({e.msg})")
            return
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        here = os.path.dirname(os.path.realpath(p))
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for mod in (m.split(".")[0] for m in mods):
                    if mod == "tg_notify":
                        res.unresolved(f"{p}:{node.lineno} imports tg_notify (resolution by sys.path)")
                    elif mod and os.path.isfile(os.path.join(here, mod + ".py")):
                        sib = os.path.join(here, mod + ".py")
                        self._walk(sib, [], sib, depth + 1, res)
            elif isinstance(node, ast.Call) and _call_name(node) in PY_SPAWN:
                for c in ast.walk(node):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and SCRIPT_WORD_RE.search(c.value) \
                            and c.value.startswith(("/", "~/")) and os.path.basename(c.value) != GATEWAY:
                        child = os.path.expanduser(c.value)
                        self._walk(child, [], child, depth + 1, res)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and GATEWAY in node.value \
                    and not isinstance(parents.get(node), ast.Expr) and not re.search(r"\s", node.value):
                hits.append(node)
        covered: set = set()
        for node in sorted(hits, key=lambda n: (n.lineno, n.col_offset)):
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
            gw = self._py_exec(tree, *sl, p)
            if gw is None:
                res.unresolved(f"{p}:{node.lineno} gateway resolver raised when run in isolation")
            else:
                res.gateway(gw, p)

    # ---- walk --------------------------------------------------------------
    def _walk(self, p: str, args: list[str], zero: str, depth: int, res: Result) -> None:
        real = os.path.realpath(p)
        if depth > MAX_DEPTH or (real, zero) in res.seen or not os.path.isfile(real):
            return
        res.seen.add((real, zero))
        if os.path.basename(real) == GATEWAY:
            res.gateway(p, p)
            return
        try:
            text = Path(real).read_text(errors="replace")
        except OSError as e:
            res.unresolved(f"{p}: unreadable ({e.strerror})")
            return
        if real.endswith(".py") or text.startswith("#!") and "python" in text.split("\n", 1)[0]:
            self._walk_py(text, p, depth, res)
        else:
            self._walk_sh(text, p, zero, args, depth, res)

    def _command(self, cmd: str, res: Result, top: bool) -> None:
        cwd = None  # the entry's own `cd <abs>` anchors the relative script words after it
        try:
            lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            toks = list(lex)
        except ValueError as e:
            res.unresolved(f"command not tokenizable ({e})")
            return
        first = top
        for i, tok in enumerate(toks):
            prev = toks[i - 1] if i else ""
            if " " in tok:
                self._command(tok, res, False)
                continue
            if tok == "-m" and "python" in os.path.basename(prev) and i + 1 < len(toks):
                res.unresolved(f"python -m {toks[i + 1]} is not followed")
            if prev == "cd" and _expand(tok, self.home).startswith("/"):
                cwd = _expand(tok, self.home)
            if not SCRIPT_WORD_RE.search(tok) or (OPERATOR_RE.match(prev) and ">" in prev):
                continue
            path = _expand(tok, self.home)
            if not path.startswith("/") and cwd:
                path = os.path.normpath(os.path.join(cwd, path))
            if not path.startswith("/"):
                res.unresolved(f"relative invocation {tok} with no `cd` before it is not followed")
                continue
            res.invoked.append(path)
            if first and not os.path.isfile(os.path.realpath(path)):
                res.not_runnable = True
            first = False
            args = []
            for t in toks[i + 1:]:
                if OPERATOR_RE.match(t):
                    break
                args.append(t)
            self._walk(path, args, path, 0, res)

    def entry(self, lineno: int, line: str) -> Result:
        res = Result(lineno)
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
    rows = []
    for n, line in enumerate(crontab.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or ENV_LINE_RE.match(s) or not SCHEDULE_RE.match(s):
            continue
        r = c.entry(n, s)
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
