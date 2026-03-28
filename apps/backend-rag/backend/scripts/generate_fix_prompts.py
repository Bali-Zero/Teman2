#!/usr/bin/env python3
"""
Fix Prompt Generator for Autonomous Test-Fix Loop.

Reads the classified failure queue and generates LLM fix prompts,
grouped by root cause for efficient batch fixing.

Each prompt includes:
- The failing test code (extracted via AST or line reading)
- The error traceback
- The source file under test (relevant functions only)
- Rules and constraints for the fix

Usage:
    python3 -m backend.scripts.generate_fix_prompts /tmp/nuz-failure-queue.json
    python3 -m backend.scripts.generate_fix_prompts /tmp/nuz-failure-queue.json --max-fixes 30 --output-dir /tmp/nuz-fix-prompts/
"""

import ast
import json
import sys
from pathlib import Path

# Base directory for backend code
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent  # apps/backend-rag/

SAFETY_RAILS = {
    "readonly_files": [
        "backend/main.py",
        "backend/main_cloud.py",
        "backend/core/config.py",
        "backend/core/dependencies.py",
        "backend/prompts/",
        "alembic/",
        "fly.toml",
        "fly.staging.toml",
        "requirements.txt",
    ],
    "banned_diff_patterns": [
        "# type: ignore",
        "# noqa",
        "# pragma: no cover",
        "# pylint: disable",
        "pytest.skip(",
        "pytest.mark.skip",
        "@unittest.skip",
    ],
    "max_diff_lines": 50,
    "max_files_changed": 3,
}


def read_file_safe(filepath: Path, max_lines: int = 200) -> str:
    """Read a file safely, returning empty string if not found."""
    try:
        lines = filepath.read_text().splitlines()
        if len(lines) > max_lines:
            return (
                "\n".join(lines[:max_lines])
                + f"\n\n... [{len(lines) - max_lines} more lines truncated]"
            )
        return "\n".join(lines)
    except (FileNotFoundError, PermissionError):
        return ""


def extract_test_function(test_file: Path, test_name: str) -> str:
    """Extract just the failing test function from the test file using AST."""
    try:
        source = test_file.read_text()
        tree = ast.parse(source)
    except (FileNotFoundError, SyntaxError):
        return ""

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == test_name:
                lines = source.splitlines()
                start = node.lineno - 1
                end = (
                    node.end_lineno
                    if hasattr(node, "end_lineno") and node.end_lineno
                    else start + 20
                )
                return "\n".join(lines[start:end])

    return ""


def extract_relevant_source(source_file: Path, max_lines: int = 150) -> str:
    """Extract source code, truncating if too large.

    For large files, tries to extract just the classes/functions
    rather than the entire file.
    """
    try:
        source = source_file.read_text()
    except FileNotFoundError:
        return f"[File not found: {source_file}]"

    lines = source.splitlines()
    if len(lines) <= max_lines:
        return source

    # File is too large — extract function/class signatures + imports
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "\n".join(lines[:max_lines]) + f"\n\n... [{len(lines) - max_lines} lines truncated]"

    parts: list[str] = []

    # Always include imports (first ~30 lines usually)
    import_end = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_end = max(import_end, node.end_lineno or node.lineno)
    if import_end > 0:
        parts.append("\n".join(lines[:import_end]))

    # Include class and function definitions (first 20 lines of each)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = min(
                node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 20,
                start + 30,
            )
            parts.append(f"\n# Line {node.lineno}:")
            parts.append("\n".join(lines[start:end]))
            if end < (node.end_lineno or end):
                parts.append("    ... [truncated]")

    result = "\n".join(parts)
    if len(result.splitlines()) > max_lines:
        return "\n".join(result.splitlines()[:max_lines]) + "\n... [truncated]"
    return result


def is_protected_file(filepath: str) -> bool:
    """Check if file is in safety rails readonly list."""
    for protected in SAFETY_RAILS["readonly_files"]:
        if filepath.startswith(protected) or filepath.endswith(protected):
            return True
    return False


def _is_test_mock_import_error(error_type: str, error_message: str, test_file: str) -> bool:
    """Detect if an IMPORT error is caused by incomplete test mocks in sys.modules.

    Pattern: test fixture creates types.ModuleType mock and injects into sys.modules
    but forgets to add certain attributes that the real module exports.
    Signature: "(unknown location)" in the error message.
    """
    if error_type != "IMPORT":
        return False
    return "(unknown location)" in error_message or "cannot import name" in error_message


def build_fix_prompt(
    group_key: str,
    failures: list[dict],
    error_type: str,
) -> str:
    """Build a fix prompt for a group of related failures."""
    # Gather context for the first failure (representative)
    first = failures[0]
    test_file_path = BACKEND_ROOT / first["test_file"]
    source_file_path = BACKEND_ROOT / first["file_path"]

    # Detect if this is a test-mock import error (fix goes in test file, not source)
    is_mock_fix = _is_test_mock_import_error(
        error_type, first.get("error_message", ""), first["test_file"],
    )

    # Extract test function name from nodeid
    test_name = first["test_id"].split("::")[-1] if "::" in first["test_id"] else ""
    test_code = extract_test_function(test_file_path, test_name) if test_name else ""
    if not test_code:
        test_code = read_file_safe(test_file_path, max_lines=100)

    source_code = extract_relevant_source(source_file_path)

    # For mock-fix errors, also show the test file's fixture/setup code
    test_fixture_code = ""
    if is_mock_fix:
        test_fixture_code = read_file_safe(test_file_path, max_lines=250)

    # Build the list of all affected tests in this group
    affected_tests = "\n".join(f"- {f['test_id']}" for f in failures[:10])
    if len(failures) > 10:
        affected_tests += f"\n- ... and {len(failures) - 10} more"

    # Safety check (only for source fixes, not test-mock fixes)
    if not is_mock_fix:
        source_rel = (
            str(source_file_path.relative_to(BACKEND_ROOT))
            if source_file_path.exists()
            else first["file_path"]
        )
        if is_protected_file(source_rel):
            return ""  # Skip protected files

    # Choose fix target based on error type
    if is_mock_fix:
        first["test_file"]
        fix_instructions = f"""## Instructions (TEST MOCK FIX)
1. Read the error carefully. The root cause is an INCOMPLETE MOCK in the test fixture.
2. The test file has a fixture (often `autouse=True`) that replaces real modules in
   `sys.modules` with `types.ModuleType` mocks. The mock is MISSING an attribute
   that the real module exports.
3. Fix the TEST FILE (`{first["test_file"]}`) by adding the missing attribute to the mock.
   Look for `types.ModuleType(...)` + `monkeypatch.setitem(sys.modules, ...)` patterns.
4. Compare what the REAL source module exports vs what the mock provides.
   Add the missing attribute (use `MagicMock()` or `AsyncMock()` as appropriate).
5. After fixing, verify:
   ```bash
   cd {BACKEND_ROOT} && source .venv/bin/activate && PYTHONPATH=. pytest {first["test_id"]} -x -q --tb=short
   ```
6. If it passes, run the full test file:
   ```bash
   PYTHONPATH=. pytest {first["test_file"]} -q --tb=short
   ```
7. Commit:
   ```bash
   git add {first["test_file"]} && git commit -m "fix(auto): mock - {group_key}"
   ```"""
    else:
        first["file_path"]
        fix_instructions = f"""## Instructions
1. Read the error carefully. Identify the ROOT CAUSE.
2. Fix the SOURCE code (in `{first["file_path"]}`), NOT the test file.
3. After fixing, run ONLY the affected test to verify:
   ```bash
   cd {BACKEND_ROOT} && source .venv/bin/activate && PYTHONPATH=. pytest {first["test_id"]} -x -q --tb=short
   ```
4. If the fix passes, also run the full test file to check for regressions:
   ```bash
   PYTHONPATH=. pytest {first["test_file"]} -q --tb=short
   ```
5. If both pass, commit the fix with a descriptive message:
   ```bash
   git add {first["file_path"]} && git commit -m "fix(auto): {error_type.lower()} - {group_key}"
   ```"""

    # Build the prompt
    prompt_parts = [
        f"""You are fixing failing tests in the Nuzantara backend (Python FastAPI).
Work in directory: {BACKEND_ROOT}

## Error Classification: {error_type}{"  (TEST MOCK FIX)" if is_mock_fix else ""}
## Group: {group_key}
## Affected Tests ({len(failures)} total):
{affected_tests}

## Primary Failing Test
File: {first["test_file"]}
Test: {first["test_id"]}
```python
{test_code}
```

## Error Output
```
{first["root_exception"]}

{first["error_message"][:400]}
```""",
    ]

    if is_mock_fix and test_fixture_code:
        prompt_parts.append(f"""
## Test File (contains the mock fixture to fix)
File: {first["test_file"]}
```python
{test_fixture_code}
```""")

    prompt_parts.append(f"""
## Source Code Under Test (reference — shows what the real module exports)
File: {first["file_path"]}
```python
{source_code}
```

{fix_instructions}

## STRICT RULES (violations = immediate rejection)
- NEVER add `# type: ignore`, `# noqa`, `# pragma: no cover`
- NEVER suppress errors — fix the root cause
- NEVER weaken assertions or change expected values
- Keep changes MINIMAL — smallest diff that fixes the test
- Maximum {SAFETY_RAILS["max_diff_lines"]} lines changed
- Maximum {SAFETY_RAILS["max_files_changed"]} files changed
- If you cannot fix it without more context, respond: ESCALATE: <reason>

## COMMIT RULE (CRITICAL)
You MUST `git commit` each successful fix INDIVIDUALLY before moving to the next.
This enables precise bisect-and-revert if a fix causes regressions later.""")

    return "\n".join(prompt_parts).strip()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate fix prompts from failure queue")
    parser.add_argument("queue", help="Path to classified failure queue JSON")
    parser.add_argument(
        "--max-fixes", type=int, default=30, help="Max number of fix prompts to generate",
    )
    parser.add_argument(
        "--output-dir", default="/tmp/nuz-fix-prompts", help="Output directory for prompt files",
    )
    parser.add_argument(
        "--types",
        nargs="*",
        default=None,
        help="Only generate for these error types (e.g., IMPORT FIXTURE)",
    )
    args = parser.parse_args()

    if not Path(args.queue).exists():
        print(f"ERROR: Queue file not found: {args.queue}", file=sys.stderr)
        sys.exit(1)

    with open(args.queue) as f:
        data = json.load(f)

    queue = data.get("queue", [])

    # Filter by type if specified
    if args.types:
        allowed_types = {t.upper() for t in args.types}
        queue = [f for f in queue if f["error_type"] in allowed_types]

    # Group by group_key
    groups: dict[str, list[dict]] = {}
    for failure in queue:
        key = failure.get("group_key", failure["test_id"])
        if key not in groups:
            groups[key] = []
        groups[key].append(failure)

    # Sort groups by: total failures in group (most impactful first)
    sorted_groups = sorted(groups.items(), key=lambda x: (-len(x[1]), x[0]))

    # Generate prompts
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    manifest: list[dict] = []

    for group_key, failures in sorted_groups:
        if generated >= args.max_fixes:
            break

        error_type = failures[0]["error_type"]
        prompt = build_fix_prompt(group_key, failures, error_type)

        if not prompt:
            skipped += 1
            continue

        filename = f"fix-{generated + 1:03d}.txt"
        (output_dir / filename).write_text(prompt)

        manifest.append(
            {
                "file": filename,
                "group_key": group_key,
                "error_type": error_type,
                "failure_count": len(failures),
                "primary_test": failures[0]["test_id"],
                "source_file": failures[0]["file_path"],
            },
        )

        generated += 1

    # Write manifest
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print("=== Fix Prompt Generation ===")
    print(f"Total failure groups: {len(groups)}")
    print(f"Prompts generated: {generated}")
    print(f"Skipped (protected files): {skipped}")
    print(f"Output directory: {output_dir}")
    print("\nGenerated prompts:")
    for item in manifest:
        print(
            f"  {item['file']}  [{item['error_type']}]  {item['failure_count']}x  {item['group_key']}",
        )


if __name__ == "__main__":
    main()
