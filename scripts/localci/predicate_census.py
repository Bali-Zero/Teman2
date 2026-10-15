"""B31-prime: the predicate census is GENERATED from the source, never hand-counted.

Every conditional of the files named in SCOPE is extracted by a parser and keyed by (file, normalized condition text,
occurrence). `scripts/localci/predicate_census.jsonl` must hold exactly one row per extracted conditional, and each row names
either mutants of the b31 table that turn it (and sit on its text) or an argued equivalence. See docs/specs/localci-sovereign-2026-10-07.md
"B31-prime".

Python: every ast.If / IfExp / While test, every comprehension `if`, every BoolOp (and each of its operands), every Compare.
Bash: every `if`/`elif`/`while`/`until` condition, every `for ((;cond;))` condition, every case-arm pattern alternative, every
operand of a `&&`/`||` chain, every operand of a compound condition, every `${VAR:-default}` and `${VAR:+alt}`.
A line that looks conditional to a keyword scan and yields no row is an error, not a silence.
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
# (file, start marker, end marker, only-regex). None = no bound. docs_guardian.sh: the consumer part of the helper only —
# the arm gate and the call (marker .. "Return to main branch") and every later conditional that reads INTENT_FAILED.
SCOPE = (
    ("scripts/signal_merge_intent.sh", None, None, None),
    ("scripts/localci/label_census.py", None, None, None),
    ("scripts/docs_guardian.sh", "# Enable auto-merge only if", "# Return to main branch", None),
    ("scripts/docs_guardian.sh", "# Return to main branch", None, r"INTENT"),
)


@dataclass(frozen=True)
class Cond:
    file: str
    text: str
    occ: int
    kind: str
    start: int
    end: int

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.file, self.text, self.occ)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ----------------------------------------------------------------------------------------------------------- python
def _offsets(src: str) -> list[int]:
    out, pos = [], 0
    for line in src.splitlines(keepends=True):
        out.append(pos)
        pos += len(line)
    return out


def _span(src_lines: list[str], offs: list[int], node: ast.AST) -> tuple[int, int]:
    def at(lineno: int, col: int) -> int:
        line = src_lines[lineno - 1]
        return offs[lineno - 1] + len(line.encode()[:col].decode(errors="ignore"))
    return at(node.lineno, node.col_offset), at(node.end_lineno, node.end_col_offset)


def extract_python(src: str) -> list[tuple[str, int, int, str]]:
    tree = ast.parse(src)
    lines, offs = src.splitlines(keepends=True), _offsets(src)
    found: dict[tuple[int, int], tuple[str, int, int, str]] = {}

    def add(node: ast.AST, kind: str) -> None:
        s, e = _span(lines, offs, node)
        found.setdefault((s, e), (norm(src[s:e]), s, e, kind))

    for n in ast.walk(tree):
        if isinstance(n, (ast.If, ast.While)):
            add(n.test, "if" if isinstance(n, ast.If) else "while")
        elif isinstance(n, ast.IfExp):
            add(n.test, "ifexp")
        elif isinstance(n, ast.comprehension):
            for t in n.ifs:
                add(t, "comp-if")
        elif isinstance(n, ast.BoolOp):
            add(n, "boolop")
            for v in n.values:
                if not (isinstance(v, ast.Constant) or (isinstance(v, (ast.Dict, ast.List, ast.Tuple, ast.Set)) and not getattr(v, "elts", getattr(v, "keys", [1])))):
                    add(v, "operand")
        elif isinstance(n, ast.Compare):
            add(n, "compare")
    return sorted(found.values(), key=lambda t: (t[1], t[2]))


# ------------------------------------------------------------------------------------------------------------ bash
def _mask_comments(text: str) -> str:
    """Blank every comment (a `#` that starts a word, outside quotes) keeping offsets."""
    out = []
    for line in text.split("\n"):
        q, i, cut = None, 0, None
        while i < len(line):
            c = line[i]
            if q:
                if c == "\\" and q == '"':
                    i += 1
                elif c == q:
                    q = None
            elif c in "'\"":
                q = c
            elif c == "\\":
                i += 1
            elif c == "#" and (i == 0 or line[i - 1] in " \t;("):
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut] + " " * (len(line) - cut))
    return "\n".join(out)


def _top_split(s: str, base: int, seps: tuple[str, ...]) -> list[tuple[str, int, int, str]]:
    """Split s at top-level separators (outside quotes, $(..), ${..}, (( )), [[ ]], [ ]); returns (piece, start, end, sep-before)."""
    pieces, depth, q, i, last, sep_before = [], 0, None, 0, 0, ""
    stack: list[str] = []
    n = len(s)
    while i < n:
        c = s[i]
        if q == "'":
            if c == "'":
                q = None
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if q == '"':
            if c == '"':
                q = None
            elif s.startswith("$(", i) or s.startswith("${", i):
                stack.append(")" if s[i + 1] == "(" else "}")
                i += 2
                continue
            elif stack and c == stack[-1]:
                stack.pop()
            i += 1
            continue
        if c == "'":
            q = "'"
        elif c == '"':
            q = '"'
        elif s.startswith("$((", i):
            stack.append("))")
            i += 3
            continue
        elif s.startswith("$(", i) or s.startswith("${", i):
            stack.append(")" if s[i + 1] == "(" else "}")
            i += 2
            continue
        elif s.startswith("((", i) and (i == 0 or s[i - 1] in " \t;"):
            stack.append("))")
            i += 2
            continue
        elif c == "(" and not stack and (i == 0 or s[i - 1] in " \t;"):
            stack.append(")")
        elif s.startswith("[[", i) and (i == 0 or s[i - 1] in " \t;!") and i + 2 < n and s[i + 2] in " \t":
            stack.append("]]")
            i += 2
            continue
        elif c == "[" and (i == 0 or s[i - 1] in " \t;!(") and i + 1 < n and s[i + 1] in " \t" and not stack:
            stack.append("]")
        elif stack and s.startswith(stack[-1], i) and (stack[-1] in (")", "}", "))") or i == 0 or s[i - 1] in " \t"):
            i += len(stack.pop())
            continue
        elif not stack:
            for sp in seps:
                if s.startswith(sp, i) and not (sp == ";" and s.startswith(";;", i)):
                    pieces.append((s[last:i], base + last, base + i, sep_before))
                    sep_before, i = sp, i + len(sp)
                    last = i
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    pieces.append((s[last:], base + last, base + n, sep_before))
    return [(p, a, b, sp) for p, a, b, sp in pieces]


def _trim(text: str, a: int) -> tuple[str, int, int]:
    lead = len(text) - len(text.lstrip())
    t = text.strip()
    return t, a + lead, a + lead + len(t)


_KEYWORDS = ("then", "else", "do", "{", "}", "fi", "done", "esac")
_FUNC = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\(\)\s*\{?\s*")


def extract_bash(src: str) -> list[tuple[str, int, int, str]]:
    text = _mask_comments(src)
    rows: list[tuple[str, int, int, str]] = []
    covered_lines: set[int] = set()
    pos, in_case = 0, False

    def row(t: str, a: int, b: int, kind: str, line_no: int, span: tuple[int, int] | None = None) -> None:
        t, a, b = _trim(t, a)
        if t:
            rows.append((norm(t), span[0] if span else a, span[1] if span else b, kind))
            covered_lines.add(line_no)

    def operands(cond: str, a: int, kind: str, line_no: int) -> None:
        lead = len(cond) - len(cond.lstrip())
        body = cond.strip()
        if body.startswith("[[ ") and body.endswith(" ]]"):   # a `[[ x && y ]]` is a compound condition too: its operands are rows
            cond, a = body[3:-3], a + lead + 3
        parts = _top_split(cond, a, ("&&", "||"))
        if len(parts) > 1:
            for k, (p, s, e, sep) in enumerate(parts):
                nxt = parts[k + 1][3] if k + 1 < len(parts) else ""
                row(p, s, e, kind + "-operand", line_no, (s, e + len(nxt)))

    def statement(st: str, a: int, line_no: int) -> None:
        nonlocal in_case
        while True:
            m = re.match(r"\s*(then|else|do)\b\s*", st) or re.match(r"\s*[{}]\s*", st) or _FUNC.match(st)
            if not m or not m.group(0).strip():
                break
            st, a = st[m.end():], a + m.end()
        if not st.strip():
            return
        m = re.match(r"\s*(if|elif|while|until)\s+", st)
        if m:
            cond = st[m.end():]
            row(cond, a + m.end(), a + len(st), m.group(1), line_no)
            operands(cond, a + m.end(), m.group(1), line_no)
            return
        m = re.match(r"\s*for\s*\(\(([^;]*);([^;]*);([^)]*)\)\)", st)
        if m:
            row(m.group(2), a + m.start(2), a + m.end(2), "for", line_no)
            return
        m = re.match(r"\s*case\s+(.*?)\s+in\b", st)
        if m:
            in_case = (norm(m.group(1)), True)
            covered_lines.add(line_no)
            rest = st[m.end():]
            if rest.strip():
                case_arms(rest, a + m.end(), line_no)
            return
        if re.match(r"\s*(fi|done|esac)\b", st):
            return
        parts = _top_split(st, a, ("&&", "||"))
        if len(parts) > 1:
            for k, (p, s, e, sep) in enumerate(parts):
                nxt = parts[k + 1][3] if k + 1 < len(parts) else ""
                row(p, s, e, "chain", line_no, (s, e + len(nxt)))
                inner = p.strip()
                im = re.match(r"(if|while)\s+", inner)
                if im:
                    row(inner[im.end():], s + (len(p) - len(p.lstrip())) + im.end(), e, im.group(1), line_no)

    def case_arms(seg: str, a: int, line_no: int) -> None:
        nonlocal in_case
        for arm, s, e, _ in _split_dsemi(seg, a):
            if re.match(r"\s*esac\b", arm):
                in_case = False
                continue
            m = re.match(r"\s*([^()\s][^()]*?)\)\s*(.*)$", arm, re.S)
            if not m:
                continue
            pat, body = m.group(1), m.group(2)
            subj = in_case[0] if in_case else "?"
            for alt, s2, e2, _ in _top_split(pat, s + m.start(1), ("|",)):
                t, x, y = _trim(alt, s2)
                rows.append((norm(f"case {subj} in {t}"), x, e, "case-arm"))   # the span runs to the end of the arm: its body is what the pattern selects
                covered_lines.add(line_no)
            body_start = s + m.start(2)
            for st, s3, _e3, _ in _top_split(body, body_start, (";",)):
                if re.match(r"\s*esac\b", st):
                    in_case = False
                else:
                    statement(st, s3, line_no)

    lines = text.split("\n")
    for line_no, line in enumerate(lines):
        base = pos
        pos += len(line) + 1
        if not line.strip():
            continue
        if line.rstrip().endswith("\\"):
            raise ValueError(f"line {line_no + 1}: a continuation line hides a conditional from the extractor; write it on one line")
        if in_case and not re.match(r"\s*esac\b", line):
            case_arms(line, base, line_no)
        else:
            for st, s, _e, _ in _top_split(line, base, (";",)):
                if in_case and re.match(r"\s*esac\b", st):
                    in_case = False
                elif in_case:
                    case_arms(st, s, line_no)
                else:
                    statement(st, s, line_no)
        for m in re.finditer(r"\$\{(\w+)(:[-+])([^}]*)\}", line):
            rows.append((norm(m.group(0)), base + m.start(), base + m.end(), "default"))
            covered_lines.add(line_no)
        if re.search(r"(^|[\s;(])(if|elif|while|until|case)\s|&&|\|\||\[\[ ", line) and line_no not in covered_lines:
            raise ValueError(f"line {line_no + 1} looks conditional but the extractor found nothing: {line.strip()[:100]}")
    seen: set[tuple[int, int, str]] = set()
    out = []
    for r in sorted(rows, key=lambda t: (t[1], t[2], t[3])):
        k = (r[1], r[2], r[0])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _split_dsemi(seg: str, a: int) -> list[tuple[str, int, int, str]]:
    return _top_split(seg, a, (";;",))


def extract(rootdir: Path = ROOT) -> list[Cond]:
    out: list[Cond] = []
    counts: dict[tuple[str, str], int] = {}
    for rel, lo_m, hi_m, only in SCOPE:
        src = (rootdir / rel).read_text()
        lo = src.index(lo_m) if lo_m else 0
        hi = src.index(hi_m, lo) if hi_m else len(src)
        body = src[lo:hi]
        raw = extract_python(body) if rel.endswith(".py") else extract_bash(body)
        for t, s, e, kind in raw:
            if only and not re.search(only, t):
                continue
            counts[(rel, t)] = counts.get((rel, t), 0) + 1
            out.append(Cond(rel, t, counts[(rel, t)], kind, s + lo, e + lo))
    return out


def mutant_spans(mutants: dict, rootdir: Path = ROOT) -> dict[str, tuple[str, int, int]]:
    """name -> (file, start, end) of the text each b31 mutant replaces; the text must occur exactly once."""
    out = {}
    for name, (rel, old, new, _tests) in mutants.items():
        if not name.startswith("b31-"):
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
        out[name] = (rel, i + pre, i + len(old) - suf)   # only the text the mutant really changes; empty = an insertion point
    return out


def rows_hit_by(conds: list[Cond], spans: dict[str, tuple[str, int, int]]) -> dict[tuple[str, str, int], list[str]]:
    hit: dict[tuple[str, str, int], list[str]] = {c.key: [] for c in conds}
    for name, (rel, s, e) in spans.items():
        for c in conds:
            if c.file == rel and ((c.start < e and s < c.end) or (s == e and c.start <= s <= c.end)):
                hit[c.key].append(name)
    return hit


def draft(mutants: dict) -> list[dict]:
    """The table as the sources and the b31 mutants say it today; rows nobody touches come out with an empty mutant list to be argued or killed."""
    conds = extract()
    hit = rows_hit_by(conds, mutant_spans(mutants))
    return [{"file": c.file, "cond": c.text, "occ": c.occ, "mutants": sorted(hit[c.key])} for c in conds]


def load_table() -> list[dict]:
    return [json.loads(line) for line in TABLE.read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    conds = extract()
    if "--draft" in sys.argv:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mm", ROOT / "scripts/localci/tests/mutants/merger_mutants.py")
        mm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mm)
        old = {(r["file"], r["cond"], r["occ"]): r for r in (load_table() if TABLE.exists() else [])}
        out = []
        for r in draft(mm.MUTANTS):
            prev = old.get((r["file"], r["cond"], r["occ"]), {})
            for k in ("equivalent", "note"):
                if prev.get(k):
                    r[k] = prev[k]
            out.append(r)
        TABLE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
        print(len(out), "rows written to", TABLE.relative_to(ROOT))
    elif "--json" in sys.argv:
        print(json.dumps([{"file": c.file, "cond": c.text, "occ": c.occ, "kind": c.kind} for c in conds], indent=1))
    else:
        for c in conds:
            print(f"{c.file}:{c.occ}\t{c.kind}\t{c.text}")
        print(len(conds), "conditionals", file=sys.stderr)
