"""Package-wide arming of the extensions-presence invariant (see
`synthesis.py`'s module docstring, the "INVARIANT" paragraph).

`test_action_item_adapter.py::test_extensions_is_always_explicitly_set_never_omitted`
checks ONE adapter's real OUTPUT -- it only catches a regression in
`action_item_adapter.py` itself, and does nothing for a future sibling
adapter (e.g. the not-yet-opened ActionIntent/OperationalReceipt slices)
that copies the `build_with_object_hash(...)` pattern but forgets to pass
`extensions=`. That gap is exactly what a per-adapter behavioural test
depends on someone remembering to write for their own new adapter.

This test closes it structurally instead: it parses (via `ast`, not string
grep -- a reformatted or aliased-import call site could dodge a grep) every
`.py` file in `backend.services.research_os` for calls to
`build_with_object_hash(...)` and asserts each one passes `extensions=`
explicitly. It runs against the SOURCE, so it catches the omission the
moment a new adapter file is added to this package -- before anyone writes
(or forgets to write) a test for that adapter's own output.
"""

from __future__ import annotations

import ast
from pathlib import Path

import backend.services.research_os as _research_os_pkg

_TARGET_CALL_NAME = "build_with_object_hash"


def _calls_in_file(source_path: Path) -> list[tuple[int, bool]]:
    """Return (line_number, passes_extensions_explicitly) for every
    `build_with_object_hash(...)` call found in one source file.
    """

    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    results: list[tuple[int, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != _TARGET_CALL_NAME:
            continue
        has_extensions_kwarg = any(kw.arg == "extensions" for kw in node.keywords)
        # A bare `**kwargs` splat (kw.arg is None) could also be carrying
        # `extensions` -- this test's job is to catch an OMITTED extensions,
        # not to forbid a legitimate forwarding pattern it cannot see inside.
        has_splat = any(kw.arg is None for kw in node.keywords)
        results.append((node.lineno, has_extensions_kwarg or has_splat))
    return results


def test_every_build_with_object_hash_call_passes_extensions_explicitly():
    """Per `research_os.hashing`'s presence-preserving null semantics (module
    docstring lines 3-5) and its framing of `object_hash` as "canonical
    object identity" (line 28): omitting `extensions=` from a
    `build_with_object_hash` call produces a DIFFERENT canonical identity
    than passing `extensions={}`, for the same logical object -- a
    difference of authoring style a future adapter added to this package
    could introduce without anyone noticing. Structurally scans every `.py`
    file in the package (AST, not grep) for such calls and fails the moment
    ANY of them -- today's adapter or a future one -- omits the keyword.
    """

    package_dir = Path(_research_os_pkg.__file__).resolve().parent
    violations: list[str] = []
    total_calls = 0

    for source_path in sorted(package_dir.glob("*.py")):
        for lineno, has_extensions in _calls_in_file(source_path):
            total_calls += 1
            if not has_extensions:
                violations.append(f"{source_path.name}:{lineno}")

    assert total_calls > 0, (
        "expected at least one build_with_object_hash(...) call in "
        f"{package_dir} to scan -- if this is 0, the glob or the target "
        "package moved and this test is silently checking nothing"
    )
    assert not violations, (
        "build_with_object_hash call(s) omit extensions=, changing this "
        f"adapter's canonical object identity by accident: {violations}"
    )
