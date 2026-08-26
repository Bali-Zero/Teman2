"""Structural arming for "this package's prose cites a module that does not exist".

THE DEFECT THIS CLOSES (PENDING-ARMS row opened 2026-08-24, D3 dispatch-vs-shipped
audit). D3's dispatch defined the deliverable as "adapters + shadow dual-write
behind a flag, default OFF + parity probe". The adapters shipped; the flag and the
probe never existed. But two prose sites cited them anyway -- `__init__.py`'s
package docstring and `action_item_adapter.py`'s "inert while the shadow dual-write
flag defaults off (see shadow.py)". That second one was not a TODO: it was the
adapter's stated REASON that leaving `risk_class`/`sensitivity` defaulted was safe.
The adapter is indeed inert today -- but because nothing calls it, not because a
flag gates it. Those are structurally different guarantees, and the first caller to
wire it into a real read path would have found no gate where the docstring promised
an off-by-default one.

PR #4993 took the corrective path the ledger row allowed ("if D3 ships partial,
correct both `shadow.py` citations so they stop promising a gate that does not
exist"). This file is that row's `proof-of-armed`: it makes the CLASS
non-re-derivable instead of hand-fixing two strings and leaving the pattern free to
recur a third time. It does NOT build the dual-write plan -- that is D8, an OPEN
condition on `contract-pass-001.md` §9, owned by another lane.

WHY THE RESOLUTION SCOPE IS NARROW, AND WHY THAT IS THE WHOLE POINT.
`shadow.py` DOES exist in this repo -- `apps/backend-rag/backend/services/visa_engine/
shadow.py`, an unrelated subsystem. A repo-wide "does a file with this basename
exist?" check would therefore have resolved the citation and passed green on the
exact defect it was built to catch. Worse, that is precisely the failure the row
described from the READER's side: "a P05/P06 builder who follows either citation
lands in the visa-engine's unrelated `shadow.py`". So resolution is scoped to the
roots a reader of THIS package could plausibly mean, and nothing else.

WHY `ast` PLUS `tokenize` RATHER THAN A GREP. The claim can live in a docstring or
in a `#` comment, and both carry the same false promise to the next reader; `ast`
alone cannot see comments, and a bare grep over the file would also match live code
(an import, a `Path("shadow.py")`), which is a different thing entirely and would
make this test fire on real references. Parsing separates the three.

WHY AN EXPLICIT ALLOWLIST RATHER THAN A "DOES THE SENTENCE DISCLAIM IT?" HEURISTIC.
The corrected prose still NAMES `shadow.py` -- it has to, in order to say the file
never existed. Deciding "is this mention a promise or a disclaimer?" from the
surrounding text is substring-guarding (cicatrix family #3, over/under-match), and
the guard would be one rephrasing away from silence. Instead the disclaimer is
carried MACHINE-READABLY here, with a reason, and `test_known_absent_registry_has_
not_rotted` fails if an entry ever starts resolving -- so the allowlist cannot
quietly outlive its own justification.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import backend.services.research_os as _research_os_pkg

_PACKAGE_DIR = Path(_research_os_pkg.__file__).resolve().parent

# A citation like `foo.py`. Deliberately basename-only: the prose in this package
# cites siblings by bare filename, which is exactly what makes a phantom one so
# easy to write and so hard to notice.
_CITATION = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*\.py)\b")

# Filenames a reader of THIS package's prose could reasonably be pointed at. A
# citation resolves only if its basename exists somewhere under one of these.
# See the module docstring for why this is not the whole repo.
_SEARCH_ROOT_SUFFIXES = (
    ("apps", "backend-rag", "backend", "services", "research_os"),
    ("packages", "research-os-core"),
    ("apps", "backend-rag", "backend", "tests", "services", "research_os"),
    ("apps", "backend-rag", "backend", "tests", "unit", "research_os"),
)

# Citations this package is ALLOWED to make to something that does not exist,
# each with the reason it is named at all. Anything not listed here must resolve.
_KNOWN_ABSENT: dict[str, str] = {
    "shadow.py": (
        "Named only to state that it has never existed in this package. The phased "
        "dual-write/read plan that would introduce it is D8, an OPEN condition on "
        "contract-pass-001.md §9, owned by the lane covering Packets 05-15 -- not "
        "by this package. Any prose here that reads as safe BECAUSE a dual-write "
        "switch defaults off is describing a switch nobody built."
    ),
}


def _repo_root() -> Path:
    for candidate in _PACKAGE_DIR.parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from the research_os package path")


def _resolvable_basenames() -> set[str]:
    """Every `.py` basename reachable under the scoped search roots."""

    root = _repo_root()
    names: set[str] = set()
    for suffix in _SEARCH_ROOT_SUFFIXES:
        search_dir = root.joinpath(*suffix)
        if not search_dir.is_dir():
            continue
        names.update(path.name for path in search_dir.rglob("*.py"))
    return names


def _prose_of(source: str, filename: str) -> list[tuple[int, str]]:
    """Every docstring and every `#` comment in one source file, as
    (line_number, text). Live code is deliberately excluded -- an import or a
    `Path("shadow.py")` is a real reference, not a claim about the world.
    """

    prose: list[tuple[int, str]] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        doc = ast.get_docstring(node, clean=False)
        if doc is None:
            continue
        # ast.Module has no lineno; its docstring starts at the first statement.
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            lineno = node.body[0].lineno if node.body else 1
        prose.append((lineno, doc))
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            prose.append((token.start[0], token.string))
    return prose


def _citations() -> list[tuple[str, int, str]]:
    """(source_file_name, line_number, cited_basename) for the whole package."""

    found: list[tuple[str, int, str]] = []
    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        for lineno, text in _prose_of(source, str(source_path)):
            for cited in _CITATION.findall(text):
                found.append((source_path.name, lineno, cited))
    return found


def test_every_module_cited_in_prose_resolves_or_is_declared_absent() -> None:
    """No docstring or comment in this package may name a `.py` file that a reader
    cannot find, unless it is declared in `_KNOWN_ABSENT` with a reason.
    """

    resolvable = _resolvable_basenames()
    phantoms = [
        (source, lineno, cited)
        for source, lineno, cited in _citations()
        if cited not in resolvable and cited not in _KNOWN_ABSENT
    ]
    assert not phantoms, (
        "prose in backend.services.research_os cites module(s) that do not exist "
        "under the scoped search roots and are not declared in _KNOWN_ABSENT: "
        + "; ".join(f"{source}:{lineno} -> {cited}" for source, lineno, cited in phantoms)
        + ". Either the file should exist, or the sentence should stop promising it "
        "does -- and if it is named deliberately in order to DENY that it exists, add "
        "it to _KNOWN_ABSENT with the reason."
    )


def test_known_absent_registry_has_not_rotted() -> None:
    """An allowlist entry that starts resolving is an allowlist lying about the
    world -- the same disease one layer up. Fail rather than silently over-permit.
    """

    resolvable = _resolvable_basenames()
    stale = sorted(name for name in _KNOWN_ABSENT if name in resolvable)
    assert not stale, (
        f"_KNOWN_ABSENT declares {stale} absent, but they now resolve under the "
        "scoped search roots. Remove them from the registry -- the citations they "
        "cover are no longer phantom."
    )


def test_known_absent_entries_carry_a_reason() -> None:
    """A bare allowlist is a permission slip with no argument attached."""

    thin = sorted(name for name, reason in _KNOWN_ABSENT.items() if len(reason.strip()) < 40)
    assert not thin, f"_KNOWN_ABSENT entries without a substantive reason: {thin}"


def test_the_scan_is_not_vacuous() -> None:
    """A scan that finds nothing to scan is not 'clean' (W84 discipline). Assert
    positively on what was read, never on the absence of a complaint.
    """

    source_files = sorted(_PACKAGE_DIR.glob("*.py"))
    assert len(source_files) >= 8, (
        f"expected the research_os package to hold at least 8 modules, scanned "
        f"{len(source_files)}: {[p.name for p in source_files]}"
    )
    citations = _citations()
    assert len(citations) >= 10, (
        f"expected the package's prose to cite at least 10 module references, "
        f"found {len(citations)} -- a citation scan that finds almost nothing is "
        "more likely broken than it is evidence of clean prose"
    )
    assert any(cited == "shadow.py" for _, _, cited in citations), (
        "the package no longer names shadow.py anywhere in prose. If the "
        "disclaiming sentences were removed, drop the _KNOWN_ABSENT entry too "
        "rather than leaving an allowlist that covers nothing"
    )


def test_a_phantom_citation_is_actually_detected() -> None:
    """GUILT half of the guard-conformance pair: prove the detector fires."""

    resolvable = _resolvable_basenames()
    prose = _prose_of(
        '"""Wires up the never_built_helper.py bridge."""\n', "<synthetic>"
    )
    cited = [name for _, text in prose for name in _CITATION.findall(text)]
    assert cited == ["never_built_helper.py"]
    assert cited[0] not in resolvable and cited[0] not in _KNOWN_ABSENT


def test_a_citation_that_resolves_only_outside_the_scope_is_still_a_phantom() -> None:
    """The shadow.py trap, asserted directly: a basename that exists ELSEWHERE in
    the repo but not under this package's search roots must still be flagged. A
    repo-wide existence check would pass here -- and would have passed on the
    original defect, since visa_engine/shadow.py is a real file.
    """

    root = _repo_root()
    outsider = root / "apps" / "backend-rag" / "backend" / "services" / "visa_engine" / "shadow.py"
    assert outsider.is_file(), (
        "this test's premise moved: it needs a real .py file that lives outside the "
        f"scoped search roots, and {outsider} is gone. Point it at another one."
    )
    assert outsider.name not in _resolvable_basenames(), (
        f"{outsider.name} resolved under the scoped search roots -- the scope has "
        "widened far enough to swallow an unrelated subsystem, which is exactly the "
        "failure this narrowness exists to prevent"
    )


def test_a_real_sibling_citation_is_not_flagged() -> None:
    """INNOCENCE half: a citation of a module that really is a sibling passes."""

    resolvable = _resolvable_basenames()
    for real_sibling in ("synthesis.py", "loss_report.py", "action_item_adapter.py"):
        assert (_PACKAGE_DIR / real_sibling).is_file(), f"{real_sibling} vanished"
        assert real_sibling in resolvable
