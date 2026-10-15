"""B31'': the predicate census of the label helper, generated from the Python source with `ast`.

Since B31'' no decision lives in bash (`scripts/signal_merge_intent.sh` is `exec python3 scripts/localci/label_intent.py`), so the census is Python only.
Every conditional of the files in SCOPE is extracted and keyed by (file, normalized condition text, occurrence); `scripts/localci/predicate_census.jsonl`
holds exactly one row per extracted conditional, naming the `b31-*` mutants whose changed text lies on it. The mutants of every row are GENERATED from the
same extraction (`auto_mutants`: the condition negated), so a conditional cannot appear without its mutant.

Rows: If/IfExp/While tests, comprehension `if`, every BoolOp and each non-literal operand, every Compare, every `not`, every ExceptHandler, and a call to a
predicate (`isinstance`, `bool`, `any`, `all`, `filter`, `startswith`, `endswith`, `isdigit`, `isascii`, `fullmatch`, ...).
Fail-loud DENYLIST: a node type this module does not model (`match`, `assert`, `with`, `lambda`, walrus, `global`/`nonlocal`, `async`, `await`) raises
`ValueError` instead of passing; so does a file that does not parse.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "scripts/localci/predicate_census.jsonl"
SCOPE = ("scripts/localci/label_intent.py", "scripts/localci/label_census.py")
PURE_FUNCTIONS = {"plan", "_pause", "_first_read", "_write", "_readback", "parse_config", "has_label", "arm_is_benign", "_tail", "_note", "_number"}
PREDICATE_CALLS = {"isinstance", "issubclass", "bool", "any", "all", "filter", "hasattr", "callable", "startswith", "endswith", "isdigit", "isalpha",
                   "isascii", "isalnum", "isspace", "fullmatch", "match", "search", "exists", "is_file", "is_dir"}
DENIED = (ast.Match, ast.Assert, ast.With, ast.AsyncWith, ast.Lambda, ast.NamedExpr, ast.Global, ast.Nonlocal, ast.AsyncFor, ast.AsyncFunctionDef,
          ast.Await, ast.TryStar)


@dataclass(frozen=True)
class Cond:
    file: str
    text: str
    occ: int
    kind: str
    start: int
    end: int
    func: str

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.file, self.text, self.occ)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _offsets(src: str) -> list[int]:
    out, pos = [], 0
    for line in src.splitlines(keepends=True):
        out.append(pos)
        pos += len(line)
    return out


def _span(lines: list[str], offs: list[int], node: ast.AST) -> tuple[int, int]:
    def at(lineno: int, col: int) -> int:
        return offs[lineno - 1] + len(lines[lineno - 1].encode()[:col].decode(errors="ignore"))
    return at(node.lineno, node.col_offset), at(node.end_lineno, node.end_col_offset)


def _call_name(node: ast.Call) -> str:
    f = node.func
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")


def _is_literal(v: ast.AST) -> bool:
    return isinstance(v, ast.Constant) or (isinstance(v, (ast.Dict, ast.List, ast.Tuple, ast.Set)) and not getattr(v, "elts", getattr(v, "keys", [1])))


def extract_python(src: str) -> list[tuple[str, int, int, str, str]]:
    """-> [(text, start, end, kind, enclosing function)] sorted by position; raises ValueError on a denied node or a syntax error."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise ValueError(f"does not parse: {exc}") from exc
    lines, offs = src.splitlines(keepends=True), _offsets(src)
    found: dict[tuple[int, int], tuple[str, int, int, str, str]] = {}
    owner: dict[int, str] = {}
    for fn in ast.walk(tree):   # outer functions first, so the innermost enclosing one wins
        if isinstance(fn, ast.FunctionDef):
            for sub in ast.walk(fn):
                owner[id(sub)] = fn.name

    def add(node: ast.AST, kind: str, origin: ast.AST) -> None:
        s, e = _span(lines, offs, node)
        found.setdefault((s, e), (norm(src[s:e]), s, e, kind, owner.get(id(origin), "")))

    for n in ast.walk(tree):
        if isinstance(n, DENIED):
            raise ValueError(f"line {n.lineno}: {type(n).__name__} is a construct the census does not model: write it as an if/boolean or extend the extractor")
        if isinstance(n, (ast.If, ast.While)):
            add(n.test, "if" if isinstance(n, ast.If) else "while", n)
        elif isinstance(n, ast.IfExp):
            add(n.test, "ifexp", n)
        elif isinstance(n, ast.comprehension):
            for t in n.ifs:
                add(t, "comp-if", n)
        elif isinstance(n, ast.BoolOp):
            add(n, "boolop", n)
            for v in n.values:
                if not _is_literal(v):
                    add(v, "operand", n)
        elif isinstance(n, ast.Compare):
            add(n, "compare", n)
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            add(n, "not", n)
        elif isinstance(n, ast.ExceptHandler):
            if n.type is None:
                raise ValueError(f"line {n.lineno}: a bare `except:` hides which failure is a decision: name the exception")
            add(n.type, "except", n)
        elif isinstance(n, ast.Call) and _call_name(n) in PREDICATE_CALLS:
            add(n, "predicate-call", n)
            for arg in n.args:
                if isinstance(arg, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
                    add(arg.elt, "predicate-element", n)
    return sorted(found.values(), key=lambda t: (t[1], t[2]))


def extract(rootdir: Path = ROOT) -> list[Cond]:
    out: list[Cond] = []
    for rel in SCOPE:
        counts: dict[str, int] = {}
        for t, s, e, kind, func in extract_python((rootdir / rel).read_text()):
            counts[t] = counts.get(t, 0) + 1
            out.append(Cond(rel, t, counts[t], kind, s, e, func))
    return out


def auto_mutants(rootdir: Path = ROOT) -> dict[str, tuple[str, str, str, tuple[str, ...]]]:
    """One mutant per extracted conditional: its text negated (an `except` clause: a type that never matches). `old` carries context until it is unique."""
    out = {}
    conds = extract(rootdir)
    for rel in SCOPE:
        src = (rootdir / rel).read_text()
        for c in (c for c in conds if c.file == rel):
            text = src[c.start:c.end]
            new = "ZeroDivisionError" if c.kind == "except" else f"(not ({text}))"
            lo, hi = c.start, c.end
            while src.count(src[lo:hi]) > 1:
                lo, hi = max(0, lo - 12), min(len(src), hi + 12)
            old = src[lo:hi]
            name = f"b31-ast-{Path(rel).stem}-{c.func or 'module'}-{c.kind}-{c.start}-{c.end}"
            tests = ("scripts/localci/tests/test_label_intent.py",) if c.func in PURE_FUNCTIONS else ("scripts/localci/tests/test_label_census.py",)
            out[name] = (rel, old, old[: c.start - lo] + new + old[c.end - lo:], tests)
    return out


def mutant_spans(mutants: dict, rootdir: Path = ROOT) -> dict[str, tuple[str, int, int]]:
    """name -> (file, start, end) of the text each b31 mutant really changes (common prefix and suffix stripped); `old` must occur once."""
    out = {}
    for name, (rel, old, new, _tests) in mutants.items():
        if not name.startswith("b31-"):
            continue
        if name.startswith("b31-ast-"):   # generated: it names the exact span of its own conditional
            s, e = name.rsplit("-", 2)[-2:]
            out[name] = (rel, int(s), int(e))
            continue
        src = (rootdir / rel).read_text()
        if src.count(old) != 1:
            raise ValueError(f"{name}: its text occurs {src.count(old)} times in {rel}")
        i = src.index(old)
        pre = 0
        while pre < min(len(old), len(new)) and old[pre] == new[pre]:
            pre += 1
        suf = 0
        while suf < min(len(old), len(new)) - pre and old[len(old) - 1 - suf] == new[len(new) - 1 - suf]:
            suf += 1
        out[name] = (rel, i + pre, i + len(old) - suf)
    return out


def rows_hit_by(conds: list[Cond], spans: dict[str, tuple[str, int, int]]) -> dict[tuple[str, str, int], list[str]]:
    hit: dict[tuple[str, str, int], list[str]] = {c.key: [] for c in conds}
    for name, (rel, s, e) in spans.items():
        for c in conds:
            exact = name.startswith("b31-ast-")
            if c.file == rel and (((c.start, c.end) == (s, e)) if exact else ((c.start < e and s < c.end) or (s == e and c.start <= s <= c.end))):
                hit[c.key].append(name)
    return hit


def draft(mutants: dict) -> list[dict]:
    conds = extract()
    hit = rows_hit_by(conds, mutant_spans(mutants))
    return [{"file": c.file, "cond": c.text, "occ": c.occ, "mutants": sorted(hit[c.key])} for c in conds]


def load_table() -> list[dict]:
    return [json.loads(line) for line in TABLE.read_text().splitlines() if line.strip()]


def _mutants_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mm", ROOT / "scripts/localci/tests/mutants/merger_mutants.py")
    mm = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mm
    spec.loader.exec_module(mm)
    return mm


if __name__ == "__main__":
    if "--draft" in sys.argv:
        old = {(r["file"], r["cond"], r["occ"]): r for r in (load_table() if TABLE.exists() else [])}
        out = []
        for r in draft(_mutants_module().MUTANTS):
            prev = old.get((r["file"], r["cond"], r["occ"]), {})
            for k in ("equivalent", "note"):
                if prev.get(k):
                    r[k] = prev[k]
            out.append(r)
        TABLE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
        print(len(out), "rows written to", TABLE.relative_to(ROOT))
    else:
        conds = extract()
        for c in conds:
            print(f"{c.file}:{c.occ}\t{c.kind}\t{c.func}\t{c.text}")
        print(len(conds), "conditionals", file=sys.stderr)
