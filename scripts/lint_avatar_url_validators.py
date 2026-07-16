#!/usr/bin/env python3
"""lint_avatar_url_validators.py — guards the `avatar_url` data:-URI invariant
(superscar #3 "Guard-over-match / -under-match" applied to a NEW-MODEL blind spot).

Prod invariant: `clients.avatar_url` must be a storage URL, never an inline
base64 `data:` URI. Inline base64 blew the clients list up to ~10MB and 422'd
every client edit (19/1744 rows still poisoned as of 2026-07-16, PR #2494).
`ClientUpdate` (app/routers/crm_clients.py) carries a `reject_data_uri_avatar`
field_validator; the same guard was later attached to the other write-path
Pydantic models that expose `avatar_url` (ClientCreate, ClientProfileUpdate,
ClientValidator). That fix protects the FOUR models known today. It does
nothing for a FIFTH model born tomorrow with an unguarded `avatar_url` field —
the exact "esiste != armato" shape this repo has been bitten by repeatedly
(cicatrix-superscar.md #2/#3).

This is a static, repo-scan-only AST lint — no DB, no network, no $HOME
dependency. It walks every `*.py` file under a root (default:
apps/backend-rag/backend/), finds every `ast.ClassDef` that (a) inherits
`BaseModel` and (b) declares a field named `avatar_url`, and classifies it:

  GUARDED      — has a `@field_validator("avatar_url")` (or legacy
                 `@validator("avatar_url")`) decorated method in the class
                 body, OR uses the shared-validator attach pattern
                 (`_x = field_validator("avatar_url")(checker)`), OR the
                 `avatar_url` field's own type is `Annotated[..., AfterValidator(...)]`
                 (or Before/Plain/WrapValidator), either inline, via a
                 module-level type alias in the SAME file, or via a type
                 alias defined in ANOTHER scanned file and imported by bare
                 name (e.g. `from backend.app.utils.crm_utils import
                 AvatarUrl` then `avatar_url: AvatarUrl`) — the real shape
                 this repo's shared avatar_url guard actually took.
  ALLOWLISTED  — an explicit, reviewed `file::ClassName` entry in ALLOWLIST
                 below, with a one-line reason. Used for models that
                 legitimately do NOT write `clients.avatar_url` (e.g. a
                 read-only response/serialization model, or a model bound to
                 a different table with its own avatar semantics).
  UNGUARDED    — neither of the above. FAIL.

Anti-blind-scan guard (scar W84 "green because it looked nowhere"): if the
walk visits ZERO .py files, OR visits files but finds ZERO avatar_url-bearing
Pydantic models at all, that is NOT "clean" — it means the scanner is
mis-pathed or broken, and exits 2 rather than reporting a false-clean 0.
Zero UNGUARDED findings among >=1 discovered model is a legitimate clean
result (exit 0/1 per --strict); zero models found at all is not.

Pure signaler — this script NEVER writes, edits, or mutates anything.

Usage:
    python3 scripts/lint_avatar_url_validators.py [--root PATH] [--json] [--strict]

Exit codes:
    0   clean (no UNGUARDED findings), OR any run without --strict
    1   with --strict: >=1 UNGUARDED model found
    2   scanner blind: zero files walked, or zero avatar_url models found
        at all (mis-pathed/broken — see anti-blind-scan guard above)
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Allowlist — deliberate, reviewable exemptions ONLY (superscar #3: an
# exemption is a guard with the sign flipped; it needs its own guilt+
# innocence discipline, which is why this is an explicit table with a reason
# per line rather than a heuristic like "skip anything under team_members.py").
#
# Key format: "<path relative to repo root>::<ClassName>".
#
# If a future Pydantic model binds to `team_members` (or any table other than
# `clients`) and legitimately owns its own `avatar_url` semantics, add it here
# with its own reason — do NOT special-case it by filename/table-name guess in
# the scanner logic itself.
# --------------------------------------------------------------------------

ALLOWLIST: Dict[str, str] = {
    "apps/backend-rag/backend/app/routers/crm_clients.py::ClientResponse": (
        "read-only response/serialization model — instantiated FROM already-"
        "stored DB rows for GET responses (id/created_at/updated_at present); "
        "it never accepts a client-supplied avatar_url on write, so there is "
        "no write path here for the data:-URI guard to protect."
    ),
}

# --------------------------------------------------------------------------
# AST detection
# --------------------------------------------------------------------------

FIELD_NAME = "avatar_url"
VALIDATOR_DECORATOR_NAMES = frozenset({"field_validator", "validator"})
ANNOTATED_WRAPPER_NAMES = frozenset(
    {"AfterValidator", "BeforeValidator", "PlainValidator", "WrapValidator"}
)


@dataclass(frozen=True)
class ModelFinding:
    """One Pydantic model class that declares an `avatar_url` field."""

    file: str  # posix path, relative to repo_root when possible
    class_name: str
    lineno: int
    guard_kind: str  # see _GUARD_KIND_* constants below, or "unguarded"

    @property
    def key(self) -> str:
        return f"{self.file}::{self.class_name}"

    @property
    def guarded(self) -> bool:
        return self.guard_kind != _GUARD_KIND_UNGUARDED


_GUARD_KIND_DECORATOR = "field_validator_decorator"
_GUARD_KIND_SHARED_ASSIGN = "shared_validator_assign"
_GUARD_KIND_ANNOTATED = "annotated_after_validator"
_GUARD_KIND_UNGUARDED = "unguarded"


def _name_of(node: ast.AST) -> Optional[str]:
    """Return the bare identifier of a Name or the .attr of an Attribute."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_pydantic_base_model(node: ast.ClassDef) -> bool:
    """True if any base class resolves (by name) to BaseModel.

    Name-only matching (not full import resolution) is deliberate: this is a
    repo-scan lint over a codebase that consistently writes
    `from pydantic import BaseModel` — liberal-by-name matches the "be
    liberal in what counts as guarded" instruction and avoids false-negatives
    from import aliasing, at the cost of (accepted) false-positives on an
    unrelated third-party `BaseModel` name, which is not a real risk here.
    """
    return any(_name_of(base) == "BaseModel" for base in node.bases)


def _field_target_name(item: ast.stmt) -> Optional[str]:
    """Return the assigned field name if `item` is a class-body field decl."""
    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
        return item.target.id
    if isinstance(item, ast.Assign) and len(item.targets) == 1:
        target = item.targets[0]
        if isinstance(target, ast.Name):
            return target.id
    return None


def _has_avatar_url_field(node: ast.ClassDef) -> bool:
    return any(_field_target_name(item) == FIELD_NAME for item in node.body)


def _decorator_guards_avatar_url(dec: ast.expr) -> bool:
    """True if `dec` is `@field_validator("avatar_url", ...)` (or `@validator(...)`)."""
    if not isinstance(dec, ast.Call):
        return False
    func_name = _name_of(dec.func)
    if func_name not in VALIDATOR_DECORATOR_NAMES:
        return False
    return any(
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and arg.value == FIELD_NAME
        for arg in dec.args
    )


def _unwrap_classmethod(value: ast.expr) -> ast.expr:
    """Unwrap a single outer `classmethod(...)` call, if present."""
    if (
        isinstance(value, ast.Call)
        and _name_of(value.func) == "classmethod"
        and len(value.args) == 1
    ):
        return value.args[0]
    return value


def _assign_is_shared_validator_attach(item: ast.stmt) -> bool:
    """True for `_x = field_validator("avatar_url")(checker)` in a class body.

    This is the documented Pydantic v2 pattern for reusing one validator
    function across multiple models without re-decorating a method on each
    class (the "shared checker" shape this task's spec calls out by name).
    """
    if not isinstance(item, ast.Assign):
        return False
    value = _unwrap_classmethod(item.value)
    if not isinstance(value, ast.Call):
        return False
    inner_func = value.func
    return _decorator_guards_avatar_url(inner_func) if isinstance(inner_func, ast.Call) else False


def _annotated_metadata_has_validator_wrapper(annotated_slice: ast.expr) -> bool:
    """True if any metadata element of an `Annotated[...]` slice is a call to
    AfterValidator/BeforeValidator/PlainValidator/WrapValidator."""
    elements: Sequence[ast.expr]
    if isinstance(annotated_slice, ast.Tuple):
        elements = annotated_slice.elts
    else:
        elements = [annotated_slice]
    for elem in elements:
        if isinstance(elem, ast.Call) and _name_of(elem.func) in ANNOTATED_WRAPPER_NAMES:
            return True
    return False


def _annotation_is_annotated_with_validator(
    annotation: ast.expr, type_alias_guarded: Mapping[str, bool]
) -> bool:
    """True if `annotation` is `Annotated[..., AfterValidator(...)]` (inline),
    or a bare Name that resolves to a module-level type alias built that way.
    """
    if isinstance(annotation, ast.Subscript) and _name_of(annotation.value) == "Annotated":
        return _annotated_metadata_has_validator_wrapper(annotation.slice)
    if isinstance(annotation, ast.Name):
        return type_alias_guarded.get(annotation.id, False)
    return False


def _module_type_alias_guards(tree: ast.Module) -> Dict[str, bool]:
    """Module-level `Foo = Annotated[str | None, AfterValidator(check)]` aliases.

    Lets a field write `avatar_url: AvatarUrl = None` and still be recognized
    as guarded via indirection through the alias, rather than only inline
    `Annotated[...]` on the field itself.
    """
    aliases: Dict[str, bool] = {}
    for node in tree.body:
        target_name: Optional[str] = None
        value: Optional[ast.expr] = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name):
                target_name = t.id
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value = node.value
        if target_name is None or value is None:
            continue
        if isinstance(value, ast.Subscript) and _name_of(value.value) == "Annotated":
            aliases[target_name] = _annotated_metadata_has_validator_wrapper(value.slice)
    return aliases


def _guard_kind_for_class(node: ast.ClassDef, type_alias_guarded: Mapping[str, bool]) -> str:
    """Classify one avatar_url-bearing model class. Liberal by design — the
    goal is catching a model with NOTHING, not policing which shape wins."""
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(_decorator_guards_avatar_url(dec) for dec in item.decorator_list):
                return _GUARD_KIND_DECORATOR
        if _assign_is_shared_validator_attach(item):
            return _GUARD_KIND_SHARED_ASSIGN
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            if item.target.id == FIELD_NAME and item.annotation is not None:
                if _annotation_is_annotated_with_validator(item.annotation, type_alias_guarded):
                    return _GUARD_KIND_ANNOTATED
    return _GUARD_KIND_UNGUARDED


def _relative_key(path: Path, repo_root: Path) -> str:
    """Posix-style path for the finding key, relative to repo_root when
    possible (so ALLOWLIST entries are stable regardless of --root)."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_file(path: Path) -> Optional[ast.Module]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError:
        return None


def _classes_with_avatar_url(
    tree: ast.Module, rel_path: str, type_alias_guarded: Mapping[str, bool]
) -> List[ModelFinding]:
    findings: List[ModelFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_pydantic_base_model(node):
            continue
        if not _has_avatar_url_field(node):
            continue
        guard_kind = _guard_kind_for_class(node, type_alias_guarded)
        findings.append(
            ModelFinding(
                file=rel_path,
                class_name=node.name,
                lineno=node.lineno,
                guard_kind=guard_kind,
            )
        )
    return findings


def scan_file(
    path: Path, repo_root: Path, extra_type_aliases: Mapping[str, bool] = {}  # noqa: B006
) -> List[ModelFinding]:
    """Parse one file and return every avatar_url-bearing Pydantic model in it.

    `extra_type_aliases` lets a caller supply guard verdicts for bare type
    names that resolve via an IMPORT from another file (see `scan_tree`,
    which is the whole-tree path that actually resolves this cross-file case
    for real runs). Single-file callers — e.g. targeted tests — get only the
    aliases defined in this same file unless they pass more explicitly.
    """
    tree = _parse_file(path)
    if tree is None:
        return []
    local_aliases = _module_type_alias_guards(tree)
    merged = {**extra_type_aliases, **local_aliases}
    return _classes_with_avatar_url(tree, _relative_key(path, repo_root), merged)


# --------------------------------------------------------------------------
# Tree walk
# --------------------------------------------------------------------------

PRUNE_DIR_NAMES = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
)


def _iter_py_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for dirpath, dirnames, filenames in __import__("os").walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIR_NAMES]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


@dataclass
class ScanResult:
    files_scanned: int
    findings: List[ModelFinding]


def scan_tree(root: Path, repo_root: Path) -> ScanResult:
    """Whole-tree scan, two passes.

    Pass 1 builds a GLOBAL registry of guarded module-level type aliases
    (bare name -> guarded bool), unioned across every file the walk visits.
    This is what lets `AvatarUrl` — defined once in crm_utils.py as
    `Annotated[str | None, AfterValidator(reject_data_uri_avatar)]` — be
    recognized as a guard when it is IMPORTED and used bare
    (`avatar_url: AvatarUrl = None`) in a completely different file
    (crm_clients.py, crm_enhanced.py, client_core.py), without this script
    having to resolve Python import paths back to files. Matching is by bare
    alias name (not import-qualified): fine for this narrow surface — the
    only names that matter are annotations literally used on a field
    literally named `avatar_url` inside a Pydantic BaseModel, so a same-name
    collision with an unrelated alias would have to be a deliberate,
    self-defeating act. A same-name alias marked guarded ANYWHERE in the
    scanned tree is treated as guarded everywhere it's referenced bare
    (OR-merge) — liberal by design, see module docstring.

    Pass 2 re-walks each parsed tree's classes using {global registry} merged
    with that file's own local aliases (local definitions win on conflict).
    """
    py_files = list(_iter_py_files(root))
    parsed: List[Tuple[Path, ast.Module]] = []
    for py_file in py_files:
        tree = _parse_file(py_file)
        if tree is not None:
            parsed.append((py_file, tree))

    global_aliases: Dict[str, bool] = {}
    for _, tree in parsed:
        for name, guarded in _module_type_alias_guards(tree).items():
            global_aliases[name] = global_aliases.get(name, False) or guarded

    findings: List[ModelFinding] = []
    for py_file, tree in parsed:
        rel = _relative_key(py_file, repo_root)
        local_aliases = _module_type_alias_guards(tree)
        merged_aliases = {**global_aliases, **local_aliases}
        findings.extend(_classes_with_avatar_url(tree, rel, merged_aliases))

    findings.sort(key=lambda f: (f.file, f.lineno))
    return ScanResult(files_scanned=len(py_files), findings=findings)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def classify(
    findings: Sequence[ModelFinding], allowlist: Mapping[str, str]
) -> Tuple[List[ModelFinding], List[Tuple[ModelFinding, str]], List[ModelFinding]]:
    """Split findings into (guarded, allowlisted-with-reason, unguarded)."""
    guarded: List[ModelFinding] = []
    allowlisted: List[Tuple[ModelFinding, str]] = []
    unguarded: List[ModelFinding] = []
    for finding in findings:
        if finding.guarded:
            guarded.append(finding)
        elif finding.key in allowlist:
            allowlisted.append((finding, allowlist[finding.key]))
        else:
            unguarded.append(finding)
    return guarded, allowlisted, unguarded


def render_report(
    root: Path,
    result: ScanResult,
    guarded: Sequence[ModelFinding],
    allowlisted: Sequence[Tuple[ModelFinding, str]],
    unguarded: Sequence[ModelFinding],
    blind: bool,
) -> str:
    lines: List[str] = []
    lines.append("# avatar_url validator lint report")
    lines.append("")
    lines.append(f"- root: `{root}`")
    lines.append(f"- files scanned: {result.files_scanned}")
    lines.append(
        f"- avatar_url-bearing Pydantic models found: {len(result.findings)} "
        f"(guarded={len(guarded)} allowlisted={len(allowlisted)} unguarded={len(unguarded)})"
    )
    lines.append("")

    if blind:
        lines.append(
            "## BLIND SCAN\n\n"
            "The walk visited zero files or found zero avatar_url-bearing "
            "Pydantic models. That is NOT a clean result — it means this "
            "scanner is mis-pathed or broken (scar W84: a guard that passes "
            "because it looked nowhere is a false-clean). Fix `--root` before "
            "trusting this report.\n"
        )
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## UNGUARDED (FAIL)")
    if not unguarded:
        lines.append("none")
    else:
        for f in unguarded:
            lines.append(
                f"- {f.file}:{f.lineno} `{f.class_name}` — declares `avatar_url` "
                "with no field_validator, shared-validator attach, or Annotated "
                "AfterValidator, and is not in ALLOWLIST"
            )
    lines.append("")

    lines.append("## Allowlisted (deliberate exemption)")
    if not allowlisted:
        lines.append("none")
    else:
        for f, reason in allowlisted:
            lines.append(f"- {f.file}:{f.lineno} `{f.class_name}` — {reason}")
    lines.append("")

    lines.append("## Guarded")
    if not guarded:
        lines.append("none")
    else:
        for f in guarded:
            lines.append(f"- {f.file}:{f.lineno} `{f.class_name}` — {f.guard_kind}")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_json(
    root: Path,
    result: ScanResult,
    guarded: Sequence[ModelFinding],
    allowlisted: Sequence[Tuple[ModelFinding, str]],
    unguarded: Sequence[ModelFinding],
    blind: bool,
) -> dict:
    def _f(finding: ModelFinding, extra: Optional[dict] = None) -> dict:
        d = {
            "file": finding.file,
            "class_name": finding.class_name,
            "lineno": finding.lineno,
            "guard_kind": finding.guard_kind,
        }
        if extra:
            d.update(extra)
        return d

    return {
        "schema": 1,
        "root": str(root),
        "files_scanned": result.files_scanned,
        "models_found": len(result.findings),
        "blind": blind,
        "guarded": [_f(f) for f in guarded],
        "allowlisted": [_f(f, {"reason": reason}) for f, reason in allowlisted],
        "unguarded": [_f(f) for f in unguarded],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _default_root() -> Path:
    # scripts/lint_avatar_url_validators.py -> parent = scripts/, parent.parent = repo root.
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "apps" / "backend-rag" / "backend"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lint_avatar_url_validators.py",
        description=(
            "Static AST lint: every Pydantic BaseModel with an avatar_url field "
            "must be guarded against inline data: URIs (field_validator, shared "
            "validator attach, or Annotated AfterValidator), or explicitly "
            "allowlisted with a reason. Pure signaler — never mutates."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Root to scan (default: <repo-root>/apps/backend-rag/backend).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help=(
            "Repo root used to compute relative ALLOWLIST keys (default: this "
            "script's own repo root). Override for isolated/test runs where "
            "--root points outside the real repo, so relative-path keys still "
            "resolve instead of falling back to absolute paths."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the markdown report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any UNGUARDED avatar_url model is found (otherwise always exit 0).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    root: Path = args.root if args.root is not None else _default_root()
    repo_root: Path = args.repo_root if args.repo_root is not None else _repo_root()

    if not root.exists():
        print(f"lint_avatar_url_validators: root not found: {root}", file=sys.stderr)
        return 2

    result = scan_tree(root, repo_root)
    guarded, allowlisted, unguarded = classify(result.findings, ALLOWLIST)

    # Anti-blind-scan guard (W84): zero files walked, or zero avatar_url
    # models found at all, is a broken/mis-pathed scanner — never "clean".
    blind = result.files_scanned == 0 or len(result.findings) == 0

    if args.json:
        print(json.dumps(build_json(root, result, guarded, allowlisted, unguarded, blind)))
    else:
        print(
            render_report(root, result, guarded, allowlisted, unguarded, blind),
            end="",
        )

    if blind:
        return 2
    if args.strict and unguarded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
