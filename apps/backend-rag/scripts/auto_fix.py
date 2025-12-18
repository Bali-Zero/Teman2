#!/usr/bin/env python3
"""
NUZANTARA PRIME - Auto-Fix Script (24/7)
Automatically fixes common code quality issues.
"""

import ast
import logging
import re
import sys
from pathlib import Path
from typing import Any

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class AutoFixer:
    """Automatically fixes common code issues"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backend_path = backend_path
        self.fixes_applied = []

    def fix_imports(self, file_path: Path) -> bool:
        """Fix import organization"""
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            # Group imports
            imports = []
            other_lines = []
            in_imports = True

            for line in lines:
                if line.strip().startswith(("import ", "from ")):
                    imports.append(line)
                elif line.strip() == "" and in_imports:
                    imports.append(line)
                else:
                    in_imports = False
                    other_lines.append(line)

            # Sort imports: stdlib, third-party, local
            stdlib_imports = []
            third_party_imports = []
            local_imports = []

            for imp in imports:
                if not imp.strip():
                    continue
                if imp.startswith("from .") or imp.startswith("from app."):
                    local_imports.append(imp)
                elif any(pkg in imp for pkg in ["fastapi", "pydantic", "sqlmodel", "httpx", "pytest"]):
                    third_party_imports.append(imp)
                else:
                    stdlib_imports.append(imp)

            # Rebuild content
            new_imports = []
            if stdlib_imports:
                new_imports.extend(sorted(stdlib_imports))
                new_imports.append("")
            if third_party_imports:
                new_imports.extend(sorted(third_party_imports))
                new_imports.append("")
            if local_imports:
                new_imports.extend(sorted(local_imports))
                new_imports.append("")

            new_content = "\n".join(new_imports + other_lines)

            if new_content != content:
                if not self.dry_run:
                    file_path.write_text(new_content)
                self.fixes_applied.append(f"Fixed imports in {file_path.name}")
                return True
        except Exception as e:
            logger.debug(f"Error fixing imports in {file_path}: {e}")

        return False

    def fix_trailing_whitespace(self, file_path: Path) -> bool:
        """Remove trailing whitespace"""
        try:
            content = file_path.read_text()
            lines = content.split("\n")
            fixed_lines = [line.rstrip() for line in lines]
            new_content = "\n".join(fixed_lines)

            if new_content != content:
                if not self.dry_run:
                    file_path.write_text(new_content)
                self.fixes_applied.append(f"Fixed trailing whitespace in {file_path.name}")
                return True
        except Exception as e:
            logger.debug(f"Error fixing whitespace in {file_path}: {e}")

        return False

    def fix_missing_final_newline(self, file_path: Path) -> bool:
        """Ensure file ends with newline"""
        try:
            content = file_path.read_text()
            if content and not content.endswith("\n"):
                if not self.dry_run:
                    file_path.write_text(content + "\n")
                self.fixes_applied.append(f"Added final newline to {file_path.name}")
                return True
        except Exception as e:
            logger.debug(f"Error fixing newline in {file_path}: {e}")

        return False

    def fix_type_hints_basic(self, file_path: Path) -> bool:
        """Add basic type hints where obvious"""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            # Simple cases: function parameters with default None -> Optional
            modified = False
            lines = content.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if function has parameters with None defaults but no type hints
                    for arg in node.args.args:
                        if arg.annotation is None:
                            # Try to infer from default value
                            for default in node.args.defaults:
                                if isinstance(default, ast.Constant) and default.value is None:
                                    # Add Optional type hint
                                    arg_line = lines[node.lineno - 1]
                                    if f"{arg.arg}=" in arg_line and "Optional" not in content:
                                        # This is complex, skip for now
                                        pass

            if modified and not self.dry_run:
                file_path.write_text("\n".join(lines))
                self.fixes_applied.append(f"Added type hints to {file_path.name}")
                return True
        except Exception as e:
            logger.debug(f"Error fixing type hints in {file_path}: {e}")

        return False

    def process_file(self, file_path: Path) -> int:
        """Process a single file"""
        fixes = 0
        if self.fix_trailing_whitespace(file_path):
            fixes += 1
        if self.fix_missing_final_newline(file_path):
            fixes += 1
        if self.fix_imports(file_path):
            fixes += 1
        return fixes

    def process_directory(self, directory: Path) -> dict[str, Any]:
        """Process all Python files in directory"""
        python_files = list(directory.rglob("*.py"))
        python_files = [
            f for f in python_files
            if "test" not in str(f) and "__pycache__" not in str(f)
        ]

        total_fixes = 0
        files_processed = 0

        for py_file in python_files:
            fixes = self.process_file(py_file)
            if fixes > 0:
                files_processed += 1
                total_fixes += fixes

        return {
            "files_processed": files_processed,
            "total_fixes": total_fixes,
            "files_checked": len(python_files),
        }

    def run(self) -> None:
        """Run auto-fix"""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        logger.info(f"🔧 Starting Auto-Fix ({mode})")

        results = self.process_directory(self.backend_path)

        print("\n" + "=" * 70)
        print(f"NUZANTARA PRIME - AUTO-FIX RESULTS ({mode})")
        print("=" * 70)
        print(f"Files checked: {results['files_checked']}")
        print(f"Files modified: {results['files_processed']}")
        print(f"Total fixes: {results['total_fixes']}")

        if self.fixes_applied:
            print("\nFixes applied:")
            for fix in self.fixes_applied[:20]:  # Show first 20
                print(f"  ✅ {fix}")

        print("=" * 70)


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Auto-Fix common code issues")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed without making changes")

    args = parser.parse_args()

    fixer = AutoFixer(dry_run=args.dry_run)
    fixer.run()


if __name__ == "__main__":
    main()


