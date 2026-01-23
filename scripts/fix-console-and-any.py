#!/usr/bin/env python3
"""
Script to automatically replace console.* and any types in TypeScript files
This script performs safe, pattern-based replacements
"""

import re
import sys
from pathlib import Path
from typing import Tuple

# Patterns to replace
REPLACEMENTS = [
    # Console replacements
    (
        r"console\.log\(([^)]+)\)",
        r'logger.debug(\1, { component: "AUTO", action: "log" })',
    ),
    (
        r"console\.error\(([^)]+)\)",
        r'logger.error(\1, { component: "AUTO", action: "error" }, toError(\1))',
    ),
    (
        r"console\.warn\(([^)]+)\)",
        r'logger.warn(\1, { component: "AUTO", action: "warn" })',
    ),
    (
        r"console\.info\(([^)]+)\)",
        r'logger.info(\1, { component: "AUTO", action: "info" })',
    ),
    # Any type replacements
    (r":\s*any\s*([,\}\)])", r": unknown\1"),  # Replace : any with : unknown
    (r"as\s+any", r"as unknown"),  # Replace as any with as unknown
    (
        r"Record<string,\s*any>",
        r"Record<string, unknown>",
    ),  # Replace Record<string, any>
    (r"Record<string,\s*any\s*>", r"Record<string, unknown>"),
]

# Files to skip (already processed or special cases)
SKIP_FILES = [
    "logger.ts",
    "common.ts",
    ".test.ts",
    ".spec.ts",
]

# Directories to process
TARGET_DIRS = [
    "apps/mouth/src/lib",
    "apps/mouth/src/components",
    "apps/mouth/src/hooks",
    "apps/mouth/src/app",
]


def needs_import(content: str) -> Tuple[bool, bool]:
    """Check if file needs logger or toError imports"""
    has_logger = "logger" in content and (
        "from" in content and "logger" in content.split("from")[0]
        if "from" in content
        else False
    )
    has_to_error = "toError" in content
    needs_logger_import = "logger." in content and not (
        "import" in content and "logger" in content
    )
    needs_to_error_import = "toError(" in content and not (
        "import" in content and "toError" in content
    )

    return needs_logger_import, needs_to_error_import


def add_imports(content: str, needs_logger: bool, needs_to_error: bool) -> str:
    """Add necessary imports at the top of the file"""
    if not needs_logger and not needs_to_error:
        return content

    # Find last import statement
    lines = content.split("\n")
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i

    if last_import_idx == -1:
        # No imports, add at top
        imports = []
        if needs_logger:
            imports.append("import { logger } from '@/lib/logger';")
        if needs_to_error:
            imports.append("import { toError } from '@/lib/types/common';")
        return "\n".join(imports) + "\n" + content
    else:
        # Add after last import
        imports = []
        if needs_logger:
            imports.append("import { logger } from '@/lib/logger';")
        if needs_to_error:
            imports.append("import { toError } from '@/lib/types/common';")

        lines.insert(last_import_idx + 1, "\n".join(imports))
        return "\n".join(lines)


def process_file(file_path: Path) -> Tuple[bool, int]:
    """Process a single file and return (modified, replacements_count)"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        replacements = 0

        # Apply replacements
        for pattern, replacement in REPLACEMENTS:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                replacements += len(matches)

        # Check if we need to add imports
        needs_logger, needs_to_error = needs_import(content)
        if needs_logger or needs_to_error:
            content = add_imports(content, needs_logger, needs_to_error)

        # Only write if content changed
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, replacements

        return False, 0
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0


def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped"""
    name = file_path.name
    return any(skip in name for skip in SKIP_FILES)


def main():
    """Main function"""
    base_path = Path(__file__).parent.parent
    total_files = 0
    modified_files = 0
    total_replacements = 0

    for target_dir in TARGET_DIRS:
        dir_path = base_path / target_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*.ts"):
            if file_path.name.endswith(".d.ts"):
                continue

            if should_skip_file(file_path):
                continue

            total_files += 1
            modified, replacements = process_file(file_path)

            if modified:
                modified_files += 1
                total_replacements += replacements
                print(
                    f"✓ {file_path.relative_to(base_path)} ({replacements} replacements)"
                )

    print(f"\nProcessed {total_files} files")
    print(f"Modified {modified_files} files")
    print(f"Total replacements: {total_replacements}")


if __name__ == "__main__":
    main()
