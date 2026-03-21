#!/usr/bin/env python3
"""
Script to add one-line docstrings to undocumented public methods.
Processes backend/services/ directory systematically.
"""

import re
from pathlib import Path


def analyze_method_signature(line: str) -> dict:
    """Extract method name and parameters from a def line."""
    match = re.match(r"^\s+def ([a-z][a-z0-9_]*)\s*\((.*?)\)\s*(?:->.*?)?:", line)
    if not match:
        return None

    method_name = match.group(1)
    params = match.group(2).strip()

    # Skip __init__ and private methods
    if method_name.startswith("_"):
        return None

    return {"name": method_name, "params": params, "indent": len(line) - len(line.lstrip())}


def generate_docstring(method_name: str, params: str) -> str:
    """Generate a concise one-line docstring based on method name."""
    # Common patterns
    if method_name.startswith("get_"):
        obj = method_name[4:].replace("_", " ")
        return f'"""Get {obj}."""'
    elif method_name.startswith("set_"):
        obj = method_name[4:].replace("_", " ")
        return f'"""Set {obj}."""'
    elif method_name.startswith("create_"):
        obj = method_name[7:].replace("_", " ")
        return f'"""Create {obj}."""'
    elif method_name.startswith("update_"):
        obj = method_name[7:].replace("_", " ")
        return f'"""Update {obj}."""'
    elif method_name.startswith("delete_"):
        obj = method_name[7:].replace("_", " ")
        return f'"""Delete {obj}."""'
    elif method_name.startswith("list_"):
        obj = method_name[5:].replace("_", " ")
        return f'"""List {obj}."""'
    elif method_name.startswith("search_"):
        obj = method_name[7:].replace("_", " ")
        return f'"""Search {obj}."""'
    elif method_name.startswith("find_"):
        obj = method_name[5:].replace("_", " ")
        return f'"""Find {obj}."""'
    elif method_name.startswith("load_"):
        obj = method_name[5:].replace("_", " ")
        return f'"""Load {obj}."""'
    elif method_name.startswith("save_"):
        obj = method_name[5:].replace("_", " ")
        return f'"""Save {obj}."""'
    elif method_name.startswith("validate_"):
        obj = method_name[9:].replace("_", " ")
        return f'"""Validate {obj}."""'
    elif method_name.startswith("check_"):
        obj = method_name[6:].replace("_", " ")
        return f'"""Check {obj}."""'
    elif method_name.startswith("build_"):
        obj = method_name[6:].replace("_", " ")
        return f'"""Build {obj}."""'
    elif method_name.startswith("generate_"):
        obj = method_name[9:].replace("_", " ")
        return f'"""Generate {obj}."""'
    elif method_name.startswith("calculate_"):
        obj = method_name[10:].replace("_", " ")
        return f'"""Calculate {obj}."""'
    elif method_name.startswith("process_"):
        obj = method_name[8:].replace("_", " ")
        return f'"""Process {obj}."""'
    elif method_name.startswith("execute_"):
        obj = method_name[8:].replace("_", " ")
        return f'"""Execute {obj}."""'
    elif method_name.startswith("run_"):
        obj = method_name[4:].replace("_", " ")
        return f'"""Run {obj}."""'
    elif method_name.startswith("start_"):
        obj = method_name[6:].replace("_", " ")
        return f'"""Start {obj}."""'
    elif method_name.startswith("stop_"):
        obj = method_name[5:].replace("_", " ")
        return f'"""Stop {obj}."""'
    elif method_name.startswith("is_"):
        obj = method_name[3:].replace("_", " ")
        return f'"""Check if {obj}."""'
    elif method_name.startswith("has_"):
        obj = method_name[4:].replace("_", " ")
        return f'"""Check if has {obj}."""'
    elif method_name.startswith("add_"):
        obj = method_name[4:].replace("_", " ")
        return f'"""Add {obj}."""'
    elif method_name.startswith("remove_"):
        obj = method_name[7:].replace("_", " ")
        return f'"""Remove {obj}."""'
    elif method_name.startswith("register_"):
        obj = method_name[9:].replace("_", " ")
        return f'"""Register {obj}."""'
    elif method_name.startswith("enable_"):
        obj = method_name[7:].replace("_", " ")
        return f'"""Enable {obj}."""'
    elif method_name.startswith("disable_"):
        obj = method_name[8:].replace("_", " ")
        return f'"""Disable {obj}."""'
    elif "status" in method_name:
        return '"""Return status information."""'
    elif "stats" in method_name:
        return '"""Return statistics."""'
    elif "count" in method_name:
        return '"""Count items."""'
    elif "metrics" in method_name:
        return '"""Return metrics."""'
    else:
        # Generic fallback
        readable = method_name.replace("_", " ").capitalize()
        return f'"""{readable}."""'


def process_file(file_path: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Process a single Python file and add missing docstrings."""
    try:
        with open(file_path) as f:
            lines = f.readlines()
    except Exception as e:
        return 0, [f"Error reading {file_path}: {e}"]

    modified_lines = []
    changes = []
    i = 0
    added_count = 0

    while i < len(lines):
        line = lines[i]
        modified_lines.append(line)

        # Check if this is a public method definition
        method_info = analyze_method_signature(line)

        if method_info:
            # Check if next non-empty line is a docstring
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                modified_lines.append(lines[j])
                j += 1

            if j < len(lines):
                next_line = lines[j].strip()
                if not (next_line.startswith('"""') or next_line.startswith("'''")):
                    # No docstring found - add one
                    indent = " " * (method_info["indent"] + 4)
                    docstring = generate_docstring(method_info["name"], method_info["params"])
                    modified_lines.append(f"{indent}{docstring}\n")
                    added_count += 1
                    changes.append(f"  L{i + 1}: Added docstring to {method_info['name']}()")

            i = j
            continue

        i += 1

    # Write back if changes were made
    if added_count > 0 and not dry_run:
        try:
            with open(file_path, "w") as f:
                f.writelines(modified_lines)
        except Exception as e:
            return 0, [f"Error writing {file_path}: {e}"]

    return added_count, changes


def main():
    """Main entry point."""
    import sys

    dry_run = "--dry-run" in sys.argv
    base_dir = Path("backend/services")

    if not base_dir.exists():
        print(f"Error: {base_dir} not found")
        return 1

    total_added = 0
    total_files = 0

    print(f"{'DRY RUN - ' if dry_run else ''}Processing backend/services/...\n")

    for py_file in sorted(base_dir.rglob("*.py")):
        if "__pycache__" in str(py_file) or "__init__" in py_file.name:
            continue

        added, changes = process_file(py_file, dry_run=dry_run)

        if added > 0:
            total_files += 1
            total_added += added
            rel_path = py_file.relative_to(base_dir.parent)
            print(f"\n{rel_path} ({added} docstrings added)")
            for change in changes[:5]:  # Show first 5
                print(change)
            if len(changes) > 5:
                print(f"  ... and {len(changes) - 5} more")

    print(
        f"\n{'Would add' if dry_run else 'Added'} {total_added} docstrings across {total_files} files"
    )

    if dry_run:
        print("\nRun without --dry-run to apply changes")

    return 0


if __name__ == "__main__":
    exit(main())
