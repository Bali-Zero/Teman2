"""Structural arming for "this package's text cites a module that does not exist".

THE DEFECT THIS CLOSES (PENDING-ARMS row opened 2026-08-24, D3 dispatch-vs-shipped
audit). D3's dispatch defined the deliverable as "adapters + shadow dual-write
behind a flag, default OFF + parity probe". The adapters shipped; the flag and the
probe never existed. But the shipped code cited them anyway -- and not as a TODO:
`action_item_adapter.py` gave the flag as its stated REASON that leaving
`risk_class`/`sensitivity` defaulted was safe. The adapter is inert today, but
because nothing calls it, not because a gate holds it. Those are different
guarantees, and the first caller to wire it into a real read path would have found
no gate where the prose promised an off-by-default one.

PR #4993 took the corrective path the ledger row allowed -- correct the citations
rather than build the flag, since the phased dual-write/read plan that would own it
is D8, an OPEN condition on `contract-pass-001.md` §9 belonging to another lane.
This file is that row's `proof-of-armed`: it makes the CLASS non-re-derivable
instead of hand-fixing two strings.

WHY THIS SCANS EVERY STRING, NOT JUST DOCSTRINGS AND COMMENTS. The first version of
this test read only docstrings (`ast`) and comments (`tokenize`). A cross-family
refuter attacked it and was right: **the historical defect site is neither.** The
`shadow.py` sentence lives in a plain string literal inside a `warnings.extend([...])`
list at `action_item_adapter.py:390` -- which is this package's dominant idiom for
stating claims (`LegacyFieldReport.warnings`, disclosure strings). So the original
test was blind to the class in exactly the form it occurred, and its own
non-vacuity check was satisfied by an unrelated `__init__.py` docstring mention,
which made the blindness look like coverage. Measured before widening: scanning
every string constant adds exactly one unresolved citation to this package --
`shadow.py`, the declared one -- and zero false positives.

The widening also needs no prose-vs-path heuristic, which is the point. A
`Path("shadow.py")` in live code that names a module this package does not have is
not an innocent exception to be filtered out; it is the same defect wearing
different clothes. Deciding "is this string a claim or a path?" would be
substring-guarding (cicatrix family #3), one rephrasing away from silence.

WHY THE RESOLUTION SCOPE IS NARROW, AND WHY THAT IS THE WHOLE POINT.
`shadow.py` DOES exist in this repo -- `apps/backend-rag/backend/services/visa_engine/
shadow.py`, an unrelated subsystem. A repo-wide "does a file with this basename
exist?" check would therefore have resolved the citation and passed green on the
exact defect it was built to catch. That is also the failure the row described from
the READER's side: "a P05/P06 builder who follows either citation lands in the
visa-engine's unrelated `shadow.py`". So resolution is scoped, and
`test_no_search_root_reaches_an_unrelated_subsystem` asserts the property
structurally rather than by naming one example.

WHY AN EXPLICIT ALLOWLIST RATHER THAN A "DOES THE SENTENCE DISCLAIM IT?" HEURISTIC.
The corrected text still NAMES `shadow.py` -- it has to, in order to say the file
never existed. So absence is declared machine-readably in `_KNOWN_ABSENT`, with a
reason, and cannot quietly outlive its justification.

The anti-rot check for that registry is deliberately PACKAGE-LOCAL, which is the
second thing the refuter caught. Checking it against every search root would mean a
future `tests/.../shadow.py` fixture forces the entry's removal -- after which the
package's citations resolve against that unrelated fixture and the main check goes
green on the visa-engine trap one root over. An allowlist entry is stale only when
the module actually appears in the package (or its core distribution), which is the
only place a citation in this package's own text could honestly mean.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import backend.services.research_os as _research_os_pkg

_PACKAGE_DIR = Path(_research_os_pkg.__file__).resolve().parent

# A citation like `foo.py`. Deliberately basename-only: this package's text cites
# siblings by bare filename, which is what makes a phantom one easy to write and
# hard to notice.
_CITATION = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*\.py)\b")

_PACKAGE_ROOT_SUFFIX = ("apps", "backend-rag", "backend", "services", "research_os")
_CORE_ROOT_SUFFIX = ("packages", "research-os-core")

# Filenames a reader of THIS package's text could reasonably be pointed at. A
# citation resolves only if its basename exists under one of these.
_SEARCH_ROOT_SUFFIXES = (
    _PACKAGE_ROOT_SUFFIX,
    _CORE_ROOT_SUFFIX,
    ("apps", "backend-rag", "backend", "tests", "services", "research_os"),
    ("apps", "backend-rag", "backend", "tests", "unit", "research_os"),
)

# Roots where a module named in this package's own text could honestly LIVE.
# Narrower than the resolution set on purpose -- see the module docstring.
_PACKAGE_LOCAL_ROOT_SUFFIXES = (_PACKAGE_ROOT_SUFFIX, _CORE_ROOT_SUFFIX)

# An unrelated subsystem that owns a colliding basename. Named here so the scope
# test can assert no search root ever reaches it.
_UNRELATED_SUBSYSTEM_SUFFIX = ("apps", "backend-rag", "backend", "services", "visa_engine")

_KNOWN_ABSENT: dict[str, str] = {
    "shadow.py": (
        "Named only to state that it has never existed in this package. The phased "
        "dual-write/read plan that would introduce it is D8, an OPEN condition on "
        "contract-pass-001.md §9, owned by the lane covering Packets 05-15 -- not "
        "by this package. Any text here that reads as safe BECAUSE a dual-write "
        "switch defaults off is describing a switch nobody built."
    ),
}


def _repo_root() -> Path:
    for candidate in _PACKAGE_DIR.parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from the research_os package path")


def _basenames_under(suffixes: tuple[tuple[str, ...], ...]) -> set[str]:
    root = _repo_root()
    names: set[str] = set()
    for suffix in suffixes:
        search_dir = root.joinpath(*suffix)
        assert search_dir.is_dir(), (
            f"declared search root {search_dir} does not exist -- a silently skipped "
            "root is an unmonitored scope shrink, so this fails loudly instead"
        )
        names.update(path.name for path in search_dir.rglob("*.py"))
    return names


def _resolvable_basenames() -> set[str]:
    return _basenames_under(_SEARCH_ROOT_SUFFIXES)


def _package_source_files() -> list[Path]:
    """Every module in the package, subpackages included (`rglob`, not `glob`: a
    future `research_os/adapters/` must not be able to carry unscanned text).
    """

    return sorted(_PACKAGE_DIR.rglob("*.py"))


def _texts_of(source: str, filename: str) -> list[tuple[int, str, str]]:
    """(line_number, kind, text) for every string and comment in one source file.

    `kind` is one of "docstring", "string", "comment" -- carried so a failure can
    say WHERE the claim lives, which is the difference between a fixable report and
    a puzzle. Every string is included, not a prose-looking subset: see the module
    docstring for why no heuristic is applied here.
    """

    texts: list[tuple[int, str, str]] = []
    tree = ast.parse(source, filename=filename)

    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstring_nodes.add(id(first.value))
            texts.append((first.value.lineno, "docstring", first.value.value))

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_nodes
        ):
            texts.append((node.lineno, "string", node.value))

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            texts.append((token.start[0], "comment", token.string))

    return texts


def _citations() -> list[tuple[str, int, str, str]]:
    """(source_file, line_number, kind, cited_basename) for the whole package."""

    found: list[tuple[str, int, str, str]] = []
    for source_path in _package_source_files():
        source = source_path.read_text(encoding="utf-8")
        rel = source_path.relative_to(_PACKAGE_DIR).as_posix()
        for lineno, kind, text in _texts_of(source, str(source_path)):
            for cited in _CITATION.findall(text):
                found.append((rel, lineno, kind, cited))
    return found


def test_every_module_cited_anywhere_resolves_or_is_declared_absent() -> None:
    """No docstring, string literal or comment in this package may name a `.py`
    file a reader cannot find, unless declared in `_KNOWN_ABSENT` with a reason.
    """

    resolvable = _resolvable_basenames()
    phantoms = [
        entry
        for entry in _citations()
        if entry[3] not in resolvable and entry[3] not in _KNOWN_ABSENT
    ]
    assert not phantoms, (
        "text in backend.services.research_os cites module(s) that do not exist "
        "under the scoped search roots and are not declared in _KNOWN_ABSENT: "
        + "; ".join(f"{src}:{line} ({kind}) -> {cited}" for src, line, kind, cited in phantoms)
        + ". Either the file should exist, or the sentence should stop promising it "
        "does -- and if it is named deliberately in order to DENY that it exists, "
        "add it to _KNOWN_ABSENT with the reason."
    )


def test_the_historical_defect_site_is_actually_scanned() -> None:
    """Regression guard for this test's own first version, which read only
    docstrings and comments and was therefore blind to the one site that mattered:
    the `shadow.py` disclaimer lives in a plain string literal inside a
    `warnings.extend([...])` list, not in a docstring. If a future refactor narrows
    the scanner back, this fails before the blindness can be mistaken for coverage.
    """

    in_strings = [
        (src, line)
        for src, line, kind, cited in _citations()
        if cited == "shadow.py" and kind == "string"
    ]
    assert in_strings, (
        "no string literal in this package names shadow.py any more. If the "
        "disclaimer moved into a docstring that is fine -- but confirm the scanner "
        "still reads string literals at all, because that is the surface this "
        "package actually keeps its claims on"
    )
    assert any(src == "action_item_adapter.py" for src, _ in in_strings), (
        f"shadow.py is named in string literals {in_strings}, but no longer in "
        "action_item_adapter.py, which is where the original false safety claim "
        "lived. If that disclosure was deleted, drop the _KNOWN_ABSENT entry too"
    )


def test_known_absent_registry_has_not_rotted() -> None:
    """An allowlist entry that starts resolving is an allowlist lying about the
    world. Checked PACKAGE-LOCALLY on purpose: a test fixture that happens to share
    the basename must not be able to force this entry's removal, because removing it
    would then let the package's own citations resolve against that fixture.
    """

    local = _basenames_under(_PACKAGE_LOCAL_ROOT_SUFFIXES)
    stale = sorted(name for name in _KNOWN_ABSENT if name in local)
    assert not stale, (
        f"_KNOWN_ABSENT declares {stale} absent, but they now exist in the package "
        "or its core distribution. Remove them from the registry -- the citations "
        "they cover are no longer phantom."
    )


def test_known_absent_entries_carry_a_reason() -> None:
    """A bare allowlist is a permission slip with no argument attached."""

    assert _KNOWN_ABSENT, (
        "_KNOWN_ABSENT is empty. That is legitimate only if this package no longer "
        "names any absent module -- verify against "
        "test_the_historical_defect_site_is_actually_scanned before accepting it"
    )
    thin = sorted(name for name, reason in _KNOWN_ABSENT.items() if len(reason.strip()) < 40)
    assert not thin, f"_KNOWN_ABSENT entries without a substantive reason: {thin}"


def test_no_search_root_reaches_an_unrelated_subsystem() -> None:
    """The scope invariant, asserted structurally rather than by naming one example:
    no declared search root may contain a subsystem outside research_os. Stated the
    other way -- if widening a root would make `visa_engine/shadow.py` resolvable,
    the narrowness that this whole test rests on is gone.
    """

    root = _repo_root()
    unrelated = root.joinpath(*_UNRELATED_SUBSYSTEM_SUFFIX)
    assert unrelated.is_dir(), (
        f"this test's premise moved: {unrelated} is gone. It needs a real sibling "
        "subsystem outside the search roots; point it at another one."
    )
    reaching = [
        "/".join(suffix)
        for suffix in _SEARCH_ROOT_SUFFIXES
        if unrelated == root.joinpath(*suffix) or root.joinpath(*suffix) in unrelated.parents
    ]
    assert not reaching, (
        f"search root(s) {reaching} contain the unrelated subsystem {unrelated} -- "
        "the scope has widened far enough to swallow a foreign package, which is "
        "exactly the failure this narrowness exists to prevent"
    )
    assert "shadow.py" not in _resolvable_basenames(), (
        "shadow.py resolved under the scoped search roots; the citation this test "
        "exists for would now silently pass"
    )


def test_the_scan_is_not_vacuous() -> None:
    """A scan that finds nothing to scan is not 'clean' (W84). Assert positively on
    what was read. The thresholds are deliberately structural rather than tuned to
    the current file count -- a count pinned at today's exact value turns red on an
    innocent file deletion, which is the pressure that gets guards weakened.
    """

    source_files = _package_source_files()
    assert source_files, "scanned zero modules in the research_os package"
    kinds = {kind for _, _, kind, _ in _citations()}
    assert kinds >= {"docstring", "string", "comment"}, (
        f"the scanner produced citations of kinds {sorted(kinds)} -- all three "
        "surfaces (docstring, string literal, comment) should be exercised by this "
        "package's own text; a missing kind means that reader is broken, not that "
        "the package is clean"
    )


def test_a_phantom_citation_is_detected_in_every_surface() -> None:
    """GUILT half of the guard-conformance pair, one case per surface the scanner
    claims to read. The first version only proved the docstring path -- and the
    surface it did not prove was the one the real defect used.
    """

    resolvable = _resolvable_basenames()
    samples = {
        "docstring": '"""Wires up the never_built_helper.py bridge."""\n',
        "string": 'WARNINGS = ["safe while never_built_helper.py is off"]\n',
        "comment": "# gated by never_built_helper.py until D8 lands\n",
    }
    for expected_kind, source in samples.items():
        found = [
            (kind, name)
            for _, kind, text in ((ln, k, t) for ln, k, t in _texts_of(source, "<synthetic>"))
            for name in _CITATION.findall(text)
        ]
        assert found, f"the {expected_kind} surface produced no citation at all"
        kinds = {kind for kind, _ in found}
        assert expected_kind in kinds, (
            f"expected a citation of kind {expected_kind!r}, got {sorted(kinds)}"
        )
        for _, name in found:
            assert name == "never_built_helper.py"
            assert name not in resolvable and name not in _KNOWN_ABSENT


def test_a_real_sibling_citation_is_not_flagged() -> None:
    """INNOCENCE half: a citation of a module that really is a sibling passes."""

    resolvable = _resolvable_basenames()
    for real_sibling in ("synthesis.py", "loss_report.py", "action_item_adapter.py"):
        assert (_PACKAGE_DIR / real_sibling).is_file(), f"{real_sibling} vanished"
        assert real_sibling in resolvable
