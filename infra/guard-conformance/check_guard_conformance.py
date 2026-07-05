#!/usr/bin/env python3
"""check_guard_conformance.py — superscar #3 enforcement (over/under-match).

THE RULE THIS EXECUTES (cicatrix-superscar.md #3, verbatim antidote):
  "nessuna guardia mergiata senza un test di innocenza (NON scatta su un caso
   legittimo limitrofo) E di colpevolezza"
Until today that rule was prose. This checker makes it structure: a guard that
exists in code without BOTH proofs registered fails CI — the #3 family
(W68→W72→W73→W77→W82→W83→W84→W85, the most recursive disease in the corpus)
can no longer grow a new member silently.

WHAT IT CHECKS, against infra/guard-conformance/registry.json:

  C1 CENSUS — code and registry agree on WHAT EXISTS:
     - bridge: every `def _guard_*` in scripts/openclaw_whatsapp_bridge.py
       (AST parse, comments can't fool it) has a registry entry, and every
       registry entry still exists in code (stale entries fail too);
     - command hooks: every *.py/*.sh in the hooks dirs is either registered
       (with tests / vaccine coverage) or explicitly exempted WITH a reason;
     - registered symbols (regexes, classifiers) still exist in their source.

  C2 PROOFS — every bridge guard has >=1 GUILT and >=1 INNOCENCE test ref;
     every hook entry has >=1 test ref or explicit vaccine coverage.

  C3 ANTI-PHANTOM (W65: even the refuter hallucinates) — every referenced
     test function exists as `def <name>` in the declared test file; every
     referenced test file exists on disk and mentions its hook by name.

  C4 ARMED (W81: esiste != armato) — every referenced test file is reachable
     by at least one .github/workflows/*.yml (direct path or ancestor-dir
     pytest invocation). A test that exists but never runs is theater.
     Known limit (accepted, documented): substring matching over workflow
     text can false-positive if a workflow names a path it never executes —
     the census+phantom checks bound the damage; do not "fix" this by
     parsing YAML into a second execution model.

DIVISION OF LABOR (deliberate, red-team-reviewed): this checker proves
LINKAGE (census parity, both proofs registered, refs real, tests reachable);
EXECUTION of the proofs belongs to CI (tests.yml runs the bridge suite dir;
hook-innocence-gate.yml + guard-conformance.yml execute the hook suites —
incl. W83/W84, which no workflow executed before this suite existed). Known
accepted limits: existence checks are regex-based (a symbol surviving only
in a comment passes C1 — census+CI-execution bound the damage); the bridge
census contract is the `_guard_` def prefix (a guard written outside that
convention is invisible — the convention IS the org contract, registry._doc
says so); vaccine coverage asserts the hook appears in the vaccine's CASES,
whose corpus carries both innocence AND guilt cases per hook by design.

Exit 0 = conformant. Exit 1 = violations (each printed with its rule id).
Runs anywhere (CI, any machine): pure stdlib, read-only, no network.

    python3 infra/guard-conformance/check_guard_conformance.py [--json]

Reference: IMMUNE FORGE mandate 2026-07-05 · infra/scar-gates/ (the W-gate
pattern this generalizes) · infra/claude-hooks/test_hook_innocence.py (the
vaccine this makes non-optional).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent          # infra/guard-conformance
REPO_ROOT = HERE.parent.parent                  # repo root
REGISTRY_PATH = HERE / "registry.json"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

HOOK_FILE_SUFFIXES = (".py", ".sh")
HOOK_SKIP_PREFIXES = ("test_", "install_", "__")
HOOK_SKIP_NAMES = {"README.md"}


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ helpers


def ast_guard_defs(source_path: Path, prefix: str) -> set[str]:
    """Function names starting with `prefix` — AST, not grep, so strings and
    comments cannot create phantom guards or hide real ones."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith(prefix)
    }


def def_exists(test_file: Path, func_name: str) -> bool:
    if not test_file.exists():
        return False
    pattern = re.compile(
        r"^\s*(?:async\s+)?def\s+" + re.escape(func_name) + r"\b", re.MULTILINE
    )
    return bool(pattern.search(test_file.read_text(encoding="utf-8")))


def symbol_exists(source_file: Path, symbol: str) -> bool:
    if not source_file.exists():
        return False
    return bool(
        re.search(r"\b" + re.escape(symbol) + r"\b", source_file.read_text(encoding="utf-8"))
    )


def workflows_text() -> str:
    chunks: list[str] = []
    if WORKFLOWS_DIR.exists():
        for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
            try:
                chunks.append(wf.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "\n".join(chunks)


def is_armed(test_rel_path: str, wf_text: str) -> bool:
    """C4: the test file (or an ancestor dir of it) appears in some workflow."""
    if test_rel_path in wf_text:
        return True
    parts = Path(test_rel_path).parts[:-1]
    # progressively shorter ancestor suffixes: "a/b/c/", "b/c/", "c/"
    for start in range(len(parts)):
        ancestor = "/".join(parts[start:]) + "/"
        if len(ancestor) > 1 and ancestor in wf_text:
            return True
    return False


# ------------------------------------------------------------------ checks


def check_bridge(surface: dict[str, Any], wf_text: str) -> list[str]:
    violations: list[str] = []
    source = REPO_ROOT / surface["source"]
    test_file = REPO_ROOT / surface["test_file"]
    prefix = surface["census"]["prefix"]

    if not source.exists():
        return [f"C1[bridge] source missing on disk: {surface['source']}"]

    in_code = ast_guard_defs(source, prefix)
    in_registry = set(surface["guards"].keys())

    for missing in sorted(in_code - in_registry):
        violations.append(
            f"C1[bridge] guard `{missing}` exists in code but is NOT registered "
            f"— write its guilt+innocence tests, then add it to registry.json"
        )
    for stale in sorted(in_registry - in_code):
        violations.append(
            f"C1[bridge] registry entry `{stale}` no longer exists in code — remove or rename"
        )

    for guard, entry in sorted(surface["guards"].items()):
        if guard not in in_code:
            continue  # already reported as stale
        for kind in ("guilt", "innocence"):
            refs = entry.get(kind, [])
            if not refs:
                violations.append(
                    f"C2[bridge] `{guard}` has NO {kind} test — the #3 antidote requires both"
                )
            for ref in refs:
                if not def_exists(test_file, ref):
                    violations.append(
                        f"C3[bridge] `{guard}` {kind} ref `{ref}` not found as a def in "
                        f"{surface['test_file']} — phantom reference (W65)"
                    )
    if not is_armed(surface["test_file"], wf_text):
        violations.append(
            f"C4[bridge] test file {surface['test_file']} is not reachable by any "
            f".github/workflows/*.yml — a test that never runs is theater (W81)"
        )
    return violations


def check_hooks(surface: dict[str, Any], wf_text: str) -> list[str]:
    violations: list[str] = []
    entries: dict[str, Any] = surface.get("entries", {})
    exempt: dict[str, str] = surface.get("exempt", {})
    vaccine_rel = surface.get("vaccine", "")
    vaccine = REPO_ROOT / vaccine_rel
    vaccine_text = vaccine.read_text(encoding="utf-8") if vaccine.exists() else ""

    # C1: every hook file on disk is registered or exempted-with-reason
    for dir_rel in surface.get("hooks_dirs", []):
        hooks_dir = REPO_ROOT / dir_rel
        if not hooks_dir.exists():
            violations.append(f"C1[hooks] hooks dir missing: {dir_rel}")
            continue
        for f in sorted(hooks_dir.iterdir()):
            if not f.is_file() or f.suffix not in HOOK_FILE_SUFFIXES:
                continue
            if f.name.startswith(HOOK_SKIP_PREFIXES) or f.name in HOOK_SKIP_NAMES:
                continue
            rel = f"{dir_rel}/{f.name}"
            if rel in entries:
                continue
            if rel in exempt and str(exempt[rel]).strip():
                continue
            violations.append(
                f"C1[hooks] `{rel}` is neither registered nor exempted-with-reason — "
                f"a new command hook must ship with vaccine cases or its own guilt+innocence tests"
            )

    # entries: source exists, symbols exist, tests exist+armed / vaccine coverage real
    for rel, entry in sorted(entries.items()):
        source = REPO_ROOT / rel
        if not source.exists():
            violations.append(f"C1[hooks] registered hook missing on disk: {rel}")
            continue
        for symbol, sym_entry in entry.get("symbols", {}).items():
            if not symbol_exists(source, symbol):
                violations.append(
                    f"C1[hooks] symbol `{symbol}` registered for {rel} not found in source"
                )
            sym_tests = sym_entry.get("tests", [])
            if not sym_tests:
                violations.append(f"C2[hooks] symbol `{symbol}` of {rel} has no test refs")
            for t in sym_tests:
                tp = REPO_ROOT / t
                if not tp.exists():
                    violations.append(f"C3[hooks] test file missing: {t} (ref by {rel}:{symbol})")
                elif not symbol_exists(tp, symbol):
                    violations.append(
                        f"C3[hooks] test {t} never mentions symbol `{symbol}` — phantom link"
                    )
                elif not is_armed(t, wf_text):
                    violations.append(f"C4[hooks] test {t} not reachable by any workflow (W81)")

        file_tests = entry.get("tests", [])
        covered_by_vaccine = "vaccine" in entry.get("also_covered_by", [])
        if covered_by_vaccine and Path(rel).name not in vaccine_text:
            violations.append(
                f"C3[hooks] {rel} claims vaccine coverage but {vaccine_rel} never names it"
            )
        if not file_tests and not entry.get("symbols") and not covered_by_vaccine:
            violations.append(
                f"C2[hooks] {rel} has neither tests, symbols-with-tests, nor vaccine coverage"
            )
        for t in file_tests:
            tp = REPO_ROOT / t
            if not tp.exists():
                violations.append(f"C3[hooks] test file missing: {t} (ref by {rel})")
            elif not is_armed(t, wf_text):
                violations.append(f"C4[hooks] test {t} not reachable by any workflow (W81)")

    # exempt hygiene: an exempted file that vanished = stale registry
    for rel in sorted(exempt.keys()):
        if not (REPO_ROOT / rel).exists():
            violations.append(f"C1[hooks] exempted file no longer exists (stale registry): {rel}")

    return violations


def check_simple_surfaces(registry: dict[str, Any], wf_text: str) -> list[str]:
    violations: list[str] = []

    gs = registry["surfaces"].get("guardrails_static")
    if gs:
        if not (REPO_ROOT / gs["source"]).exists():
            violations.append(f"C1[guardrails] source missing: {gs['source']}")
        for t in gs.get("tests", []):
            if not (REPO_ROOT / t).exists():
                violations.append(f"C3[guardrails] test file missing: {t}")
            elif not is_armed(t, wf_text):
                violations.append(f"C4[guardrails] test {t} not reachable by any workflow")

    for name, entry in registry["surfaces"].get("under_match_sentinels", {}).items():
        gate = entry.get("delegated_to", "")
        gate_path = REPO_ROOT / gate
        if not gate_path.exists():
            violations.append(f"C3[under-match] `{name}` delegated gate missing: {gate}")
            continue
        # C4 for delegated scar-gates: execution is TRANSITIVE — the meta-
        # verifier (scripts/verify_the_verifiers.py, run by its own workflow)
        # executes every MANIFEST gate with prose_only:false. Armed therefore
        # means: MANIFEST lists this gate un-prose, and the meta-verifier
        # workflow exists.
        manifest_path = REPO_ROOT / "infra" / "scar-gates" / "MANIFEST.json"
        armed = False
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                armed = any(
                    g.get("target") == gate_path.name and not g.get("prose_only", True)
                    for g in manifest.get("gates", [])
                )
            except (OSError, json.JSONDecodeError):
                armed = False
        if not armed or not (WORKFLOWS_DIR / "verify-the-verifiers.yml").exists():
            violations.append(
                f"C4[under-match] `{name}` gate {gate} is not armed via scar-gates "
                f"MANIFEST (prose_only must be false) + verify-the-verifiers workflow (W81)"
            )

    for key in registry["surfaces"].get("exempt_matchers", {}):
        src, _, symbol = key.partition("::")
        src_path = REPO_ROOT / src
        if not src_path.exists():
            violations.append(f"C1[exempt] exempted matcher source vanished (stale): {src}")
        elif symbol and not symbol_exists(src_path, symbol):
            violations.append(
                f"C1[exempt] exempted symbol `{symbol}` no longer exists in {src} (stale registry)"
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    as_json = "--json" in (argv or sys.argv[1:])
    registry = load_registry()
    wf_text = workflows_text()

    violations: list[str] = []
    violations += check_bridge(registry["surfaces"]["bridge_reply_guards"], wf_text)
    violations += check_hooks(registry["surfaces"]["command_hooks"], wf_text)
    violations += check_simple_surfaces(registry, wf_text)

    bridge_count = len(registry["surfaces"]["bridge_reply_guards"]["guards"])
    hook_count = len(registry["surfaces"]["command_hooks"]["entries"])

    if as_json:
        print(json.dumps({
            "schema": 1,
            "bridge_guards": bridge_count,
            "hook_entries": hook_count,
            "violations": violations,
            "conformant": not violations,
        }, indent=2))
    else:
        print(
            f"guard-conformance: {bridge_count} bridge guards, {hook_count} hook entries, "
            f"{len(violations)} violation(s)"
        )
        for v in violations:
            print(f"  ✗ {v}")
        if not violations:
            print("  ✓ every censused guard has guilt+innocence proofs, no phantoms, all armed in CI")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
