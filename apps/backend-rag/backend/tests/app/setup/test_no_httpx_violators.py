"""Regression test for Golden Rule #10 (CLAUDE.md §4).

Replicates the classifier used in `scripts/audit_httpx_violations.sh`
(P0-5 phase 1 audit) and asserts that no `httpx.AsyncClient(`
instantiation falls into the **violation** buckets:

* ``CRITICAL_LOOP_BODY``
* ``VIOLATION_FUNCTION_BODY`` — bare instantiation in a function body
  with NO ``is_closed`` guard within the preceding 5 lines.
* ``VIOLATION_INSTANCE_INIT`` — assignment to ``self.<attr>`` inside an
  ``__init__`` method.

Allowed (``OK_*``) patterns:

* Files ending in ``_http.py`` — canonical lazy-singleton location
  (e.g. ``services/notifications/email_http.py``).
* Files under ``backend/scripts/`` — one-shot CLI tools.
* ``async with httpx.AsyncClient(...) as ...:`` — deterministic close
  via context manager.
* Assignment guarded by an ``is_closed`` check within the preceding 5
  lines (the canonical lazy-singleton getter idiom).
* Test files (``tests/``, ``test_*.py``, ``*_test.py``).
* Lines tagged with ``# golden-rule-10-exempt`` (must include a brief
  reason, by convention).

The same logic is enforced at PR-check time by
``.github/workflows/lint-golden-rule-10.yml`` (which runs this test
file directly). Keeping the regex / lookback in sync between the
audit script, this test, and the CI workflow is the single source of
truth for Golden Rule #10.

Cost: <500ms locally — pure file reads, no module imports, no DB.
"""

from __future__ import annotations

import re
from pathlib import Path

# tests/app/setup/test_no_httpx_violators.py
#   parents[0] = setup
#   parents[1] = app
#   parents[2] = tests
#   parents[3] = backend
BACKEND_DIR = Path(__file__).resolve().parents[3]

_LOOKBACK = 5  # lines — same window as the audit classifier
_INSTANTIATION_RE = re.compile(r"\bhttpx\.AsyncClient\s*\(")
_INIT_DEF_RE = re.compile(r"^\s*(async\s+)?def\s+__init__\s*\(")
_LOOP_RE = re.compile(r"^\s*(for|while)\s+")
_IS_CLOSED_RE = re.compile(r"\bis_closed\b")


def _is_skipped_path(path: Path) -> bool:
    rel = path.relative_to(BACKEND_DIR).as_posix()
    if rel.endswith("_http.py"):
        return True
    if rel.startswith("scripts/"):
        return True
    if rel.startswith("tests/") or "/tests/" in rel:
        return True
    name = path.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


def _classify(lines: list[str], idx: int) -> str | None:
    """Return a violation tag if the line at ``idx`` is bad, else None."""
    line = lines[idx]
    stripped = line.lstrip()
    if stripped.startswith(("#", '"', "'")):
        return None  # comment or docstring
    if "# golden-rule-10-exempt" in line:
        return None
    if "async with httpx.AsyncClient" in line or "async with _httpx.AsyncClient" in line:
        return None
    if not _INSTANTIATION_RE.search(line):
        return None

    # Lookback for is_closed guard
    start = max(0, idx - _LOOKBACK)
    window = lines[start:idx]
    if any(_IS_CLOSED_RE.search(w) for w in window):
        return None  # OK_LAZY_SINGLETON_GETTER

    # Loop body? walk back up to 8 lines (same as audit) but only
    # within the same indentation-or-deeper context.
    base_indent = len(line) - len(line.lstrip(" "))
    for back in range(idx - 1, max(-1, idx - 9), -1):
        prev = lines[back]
        if not prev.strip():
            continue
        prev_indent = len(prev) - len(prev.lstrip(" "))
        if prev_indent > base_indent:
            continue  # nested block, skip
        if _LOOP_RE.match(prev):
            return "CRITICAL_LOOP_BODY"
        # Stop at function/class def — different scope.
        if re.match(r"^\s*(async\s+)?def\s+", prev) or re.match(r"^\s*class\s+", prev):
            break

    # Instance-init? walk back to find the enclosing def.
    for back in range(idx - 1, -1, -1):
        prev = lines[back]
        m = re.match(r"^(\s*)(async\s+)?def\s+(\w+)", prev)
        if not m:
            continue
        prev_indent = len(m.group(1))
        if prev_indent < base_indent:
            if m.group(3) == "__init__":
                return "VIOLATION_INSTANCE_INIT"
            break

    return "VIOLATION_FUNCTION_BODY"


def _strip_multiline_strings(lines: list[str]) -> set[int]:
    """Return the set of 0-based line indices that fall inside triple-quoted strings.

    Crude but effective: tracks `\"\"\"` and `'''` toggles on a single
    pass. Misses adversarial cases (mixed quoting, escaped triple-quotes
    inside another string), but works for our codebase where docstrings
    follow PEP 257 conventions.
    """
    inside_indices: set[int] = set()
    state: str | None = None  # the active triple-quote, or None
    for idx, line in enumerate(lines):
        i = 0
        while i < len(line):
            if state is None:
                ts = line.find('"""', i)
                ss = line.find("'''", i)
                # Pick the earliest opener.
                cands = [(p, q) for p, q in ((ts, '"""'), (ss, "'''")) if p != -1]
                if not cands:
                    break
                start, q = min(cands, key=lambda x: x[0])
                # Found opener — does the string also close on this line?
                close = line.find(q, start + 3)
                if close != -1:
                    i = close + 3
                    continue
                state = q
                inside_indices.add(idx)
                break
            else:
                close = line.find(state, i)
                if close == -1:
                    inside_indices.add(idx)
                    break
                state = None
                i = close + 3
        if state is not None:
            inside_indices.add(idx)
    return inside_indices


def _gather_violations() -> list[tuple[str, int, str, str]]:
    out: list[tuple[str, int, str, str]] = []
    for py in BACKEND_DIR.rglob("*.py"):
        if _is_skipped_path(py):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "httpx.AsyncClient(" not in text:
            continue
        lines = text.splitlines()
        in_string = _strip_multiline_strings(lines)
        for idx, _line in enumerate(lines):
            if idx in in_string:
                continue
            tag = _classify(lines, idx)
            if tag is None:
                continue
            rel = py.relative_to(BACKEND_DIR).as_posix()
            out.append((rel, idx + 1, tag, lines[idx].strip()))
    return out


def test_no_httpx_violators_outside_http_files() -> None:
    """Fail the build if a Golden Rule #10 violation regrows."""
    violations = _gather_violations()
    if not violations:
        return
    msg_lines = [
        f"Golden Rule #10: {len(violations)} httpx.AsyncClient violation(s).",
        "Fix: hoist to a module-level lazy singleton in `*_http.py`",
        "(see backend/services/notifications/email_http.py).",
        "Or use `async with httpx.AsyncClient(...) as ...:`.",
        "Or annotate `# golden-rule-10-exempt: <reason>` if provably safe.",
        "",
    ]
    for rel, lineno, tag, snippet in violations:
        msg_lines.append(f"  [{tag}] {rel}:{lineno}  {snippet}")
    raise AssertionError("\n".join(msg_lines))
