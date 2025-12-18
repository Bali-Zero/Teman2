#!/usr/bin/env python3
"""
🤖 TESTBOT - Zantara Test Automation Agent

Automatically manages tests for code changes using AI.

Features:
1. Analyzes code changes (git diff)
2. Determines which tests are needed
3. Generates/updates tests automatically
4. Fixes broken tests
5. Removes obsolete tests

Uses AI (Gemini/Zantara) to understand code context and generate appropriate tests.

Agent Name: TESTBOT (Test Automation Bot)
Part of: Nuzantara Prime Test Automation System
"""

import ast
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("testbot.agent")

try:
    from llm.zantara_ai_client import ZantaraAIClient
except ImportError:
    # Fallback if not available
    ZantaraAIClient = None


class AITestAgent:
    """
    🤖 TESTBOT - AI-powered test management agent
    
    Part of the Nuzantara Prime Test Automation System.
    Automatically analyzes code changes and manages test lifecycle.
    """

    def __init__(self, backend_dir: Path, test_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.test_dir = Path(test_dir)
        self.ai_client = None
        
        # Initialize AI client if available
        if ZantaraAIClient:
            try:
                self.ai_client = ZantaraAIClient()
            except Exception as e:
                print(f"⚠️  Could not initialize AI client: {e}")
                print("   Continuing without AI assistance...")

    def get_changed_files(self) -> List[Path]:
        """Get list of Python files changed in git"""
        try:
            # Get staged and unstaged changes
            result = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True,
                text=True,
                cwd=self.backend_dir.parent.parent,
            )
            staged_files = result.stdout.strip().split("\n") if result.stdout.strip() else []
            
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.backend_dir.parent.parent,
            )
            all_changed = result.stdout.strip().split("\n") if result.stdout.strip() else []
            
            # Combine and filter Python files in backend
            changed = set(staged_files + all_changed)
            python_files = [
                Path(f) for f in changed
                if f.endswith(".py") and "apps/backend-rag/backend" in f
            ]
            
            return python_files
        except Exception as e:
            print(f"⚠️  Error getting changed files: {e}")
            return []

    def analyze_code_changes(self, file_path: Path) -> Dict:
        """Analyze code changes to understand what needs testing"""
        try:
            # Get git diff for the file
            result = subprocess.run(
                ["git", "diff", "HEAD", str(file_path)],
                capture_output=True,
                text=True,
                cwd=self.backend_dir.parent.parent,
            )
            diff = result.stdout
            
            # Read current file
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_code = f.read()
            else:
                current_code = ""
            
            # Parse AST to understand structure
            try:
                tree = ast.parse(current_code)
                classes = []
                functions = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        classes.append({"name": node.name, "methods": methods})
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            functions.append(node.name)
                
                return {
                    "file": str(file_path),
                    "diff": diff,
                    "classes": classes,
                    "functions": functions,
                    "is_new_file": not diff or "new file" in diff.lower(),
                    "has_changes": bool(diff),
                }
            except SyntaxError:
                return {
                    "file": str(file_path),
                    "diff": diff,
                    "classes": [],
                    "functions": [],
                    "is_new_file": True,
                    "has_changes": bool(diff),
                }
        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")
            return {"file": str(file_path), "error": str(e)}

    def determine_test_needs(self, analysis: Dict) -> Dict:
        """Use AI to determine what tests are needed"""
        if not self.ai_client:
            # Fallback: simple heuristic-based approach
            return self._determine_test_needs_heuristic(analysis)
        
        try:
            prompt = f"""
Analyze this code change and determine what tests are needed:

File: {analysis['file']}
Is New File: {analysis.get('is_new_file', False)}
Classes: {analysis.get('classes', [])}
Functions: {analysis.get('functions', [])}

Diff:
{analysis.get('diff', '')[:2000]}

Please provide:
1. What type of tests are needed (unit, integration, API)?
2. Which functions/methods need tests?
3. What edge cases should be tested?
4. Are there any existing tests that need updating?

Respond in JSON format:
{{
    "test_type": "unit|integration|api",
    "functions_to_test": ["function1", "function2"],
    "edge_cases": ["case1", "case2"],
    "update_existing": true/false,
    "test_file_path": "tests/unit/test_module.py"
}}
"""
            response = self.ai_client.generate(prompt, max_tokens=1000)
            
            # Try to parse JSON from response
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.find("```", json_start)
                    response = response[json_start:json_end].strip()
                elif "```" in response:
                    json_start = response.find("```") + 3
                    json_end = response.find("```", json_start)
                    response = response[json_start:json_end].strip()
                
                return json.loads(response)
            except json.JSONDecodeError:
                # Fallback to heuristic
                return self._determine_test_needs_heuristic(analysis)
        except Exception as e:
            print(f"⚠️  AI analysis failed: {e}, using heuristic")
            return self._determine_test_needs_heuristic(analysis)

    def _determine_test_needs_heuristic(self, analysis: Dict) -> Dict:
        """Heuristic-based test needs determination"""
        file_path = Path(analysis['file'])
        rel_path = file_path.relative_to(self.backend_dir)
        
        # Determine test type based on path
        if "routers" in str(rel_path):
            test_type = "api"
            test_dir = self.test_dir / "api"
        elif "services" in str(rel_path):
            test_type = "integration"
            test_dir = self.test_dir / "integration"
        else:
            test_type = "unit"
            test_dir = self.test_dir / "unit"
        
        # Determine test file path
        test_file_name = f"test_{file_path.stem}.py"
        test_file_path = test_dir / test_file_name
        
        return {
            "test_type": test_type,
            "functions_to_test": analysis.get("functions", []),
            "classes_to_test": [c["name"] for c in analysis.get("classes", [])],
            "edge_cases": [],
            "update_existing": test_file_path.exists(),
            "test_file_path": str(test_file_path),
        }

    def generate_test_code(self, analysis: Dict, test_needs: Dict) -> str:
        """Generate test code using AI"""
        if not self.ai_client:
            return self._generate_test_code_template(analysis, test_needs)
        
        # Check if this is a frontend file
        file_path = Path(analysis.get("file", ""))
        if "apps/mouth" in str(file_path) or "frontend" in str(file_path):
            # Delegate to frontend generator
            try:
                from frontend_test_generator import FrontendTestGenerator
                config = {"ai": {"model": "gemini-2.5-flash", "max_tests_per_run": 10}}
                frontend_gen = FrontendTestGenerator(config)
                if file_path.suffix in [".tsx", ".ts"]:
                    if "component" in str(file_path).lower() or file_path.suffix == ".tsx":
                        return frontend_gen._generate_component_test(file_path) or self._generate_test_code_template(analysis, test_needs)
                    else:
                        return frontend_gen._generate_e2e_test(file_path) or self._generate_test_code_template(analysis, test_needs)
            except Exception as e:
                logger.warning(f"Frontend generator failed, using template: {e}")
                return self._generate_test_code_template(analysis, test_needs)
        
        try:
            prompt = f"""
Generate comprehensive pytest test code for:

File: {analysis['file']}
Test Type: {test_needs['test_type']}
Functions to Test: {test_needs.get('functions_to_test', [])}
Classes to Test: {test_needs.get('classes_to_test', [])}

Current Code:
{self._read_file_safely(Path(analysis['file']))[:3000]}

Requirements:
1. Use pytest fixtures from conftest.py
2. Follow AAA pattern (Arrange, Act, Assert)
3. Include edge cases and error handling
4. Mock external dependencies
5. Use proper async/await for async functions
6. Include docstrings

Generate complete, runnable test code:
"""
            response = self.ai_client.generate(prompt, max_tokens=4000)
            
            # Extract code from markdown if present
            if "```python" in response:
                code_start = response.find("```python") + 9
                code_end = response.find("```", code_start)
                return response[code_start:code_end].strip()
            elif "```" in response:
                code_start = response.find("```") + 3
                code_end = response.find("```", code_start)
                return response[code_start:code_end].strip()
            
            return response
        except Exception as e:
            print(f"⚠️  AI generation failed: {e}, using template")
            return self._generate_test_code_template(analysis, test_needs)

    def _generate_test_code_template(self, analysis: Dict, test_needs: Dict) -> str:
        """Generate basic test template"""
        file_path = Path(analysis['file'])
        module_name = file_path.stem
        
        lines = [
            '"""',
            f'Tests for {module_name}',
            'Auto-generated - PLEASE REVIEW AND COMPLETE',
            '"""',
            '',
            'import pytest',
            'from unittest.mock import MagicMock, AsyncMock, patch',
            '',
        ]
        
        # Add imports based on test type
        if test_needs['test_type'] == 'api':
            lines.append('from fastapi.testclient import TestClient')
            lines.append('')
        
        # Add test classes
        for class_name in test_needs.get('classes_to_test', []):
            lines.append(f'class Test{class_name}:')
            lines.append(f'    """Test suite for {class_name}"""')
            lines.append('')
            lines.append('    def test_placeholder(self):')
            lines.append('        """TODO: Implement test"""')
            lines.append('        assert True')
            lines.append('')
        
        # Add test functions
        for func_name in test_needs.get('functions_to_test', []):
            lines.append(f'def test_{func_name}(self):')
            lines.append(f'    """Test {func_name} function"""')
            lines.append('    # Arrange')
            lines.append('    # Act')
            lines.append('    # Assert')
            lines.append('    assert True')
            lines.append('')
        
        return '\n'.join(lines)

    def _read_file_safely(self, file_path: Path, max_lines: int = 100) -> str:
        """Safely read file with line limit"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:max_lines]
                return ''.join(lines)
        except Exception:
            return ""

    def find_obsolete_tests(self) -> List[Path]:
        """Find test files for code that no longer exists"""
        obsolete = []
        
        # Map test files to source files
        for test_file in self.test_dir.rglob("test_*.py"):
            # Extract module name from test file
            module_name = test_file.stem.replace("test_", "")
            
            # Try to find corresponding source file
            found = False
            for pattern in [
                f"{module_name}.py",
                f"{module_name.replace('_', '')}.py",
            ]:
                if (self.backend_dir / pattern).exists():
                    found = True
                    break
                
                # Check in subdirectories
                for source_file in self.backend_dir.rglob(pattern):
                    found = True
                    break
            
            if not found:
                obsolete.append(test_file)
        
        return obsolete

    def fix_broken_tests(self, test_file: Path) -> bool:
        """Try to fix broken tests"""
        try:
            # Run tests to see what's broken
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=self.backend_dir.parent,
            )
            
            if result.returncode == 0:
                return True  # Tests pass
            
            # Analyze errors and try to fix
            errors = result.stderr + result.stdout
            
            if self.ai_client:
                prompt = f"""
These tests are failing. Fix them:

Test File: {test_file}
Errors:
{errors[:2000]}

Provide fixed test code:
"""
                fixed_code = self.ai_client.generate(prompt, max_tokens=4000)
                
                # Extract code and write
                if "```python" in fixed_code:
                    code_start = fixed_code.find("```python") + 9
                    code_end = fixed_code.find("```", code_start)
                    fixed_code = fixed_code[code_start:code_end].strip()
                
                with open(test_file, 'w') as f:
                    f.write(fixed_code)
                
                return True
            
            return False
        except Exception as e:
            print(f"⚠️  Error fixing tests: {e}")
            return False

    def run(self, dry_run: bool = False) -> Dict:
        """Main execution: analyze changes and manage tests"""
        print("🤖 TESTBOT - Zantara Test Automation Agent")
        print("=" * 60)
        print("Analyzing code changes...")
        
        changed_files = self.get_changed_files()
        if not changed_files:
            print("✅ No Python files changed")
            return {"status": "no_changes"}
        
        print(f"📝 Found {len(changed_files)} changed file(s)")
        
        results = {
            "files_analyzed": [],
            "tests_generated": [],
            "tests_updated": [],
            "tests_fixed": [],
            "obsolete_tests": [],
        }
        
        for file_path in changed_files:
            print(f"\n📄 Analyzing: {file_path}")
            
            # Analyze code
            analysis = self.analyze_code_changes(file_path)
            results["files_analyzed"].append(analysis)
            
            # Determine test needs
            test_needs = self.determine_test_needs(analysis)
            print(f"   Test type: {test_needs['test_type']}")
            print(f"   Test file: {test_needs['test_file_path']}")
            
            # Generate/update tests
            test_file_path = Path(test_needs['test_file_path'])
            test_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if test_needs.get('update_existing') and test_file_path.exists():
                print(f"   ⚠️  Test file exists - updating...")
                if not dry_run:
                    # Read existing and merge
                    with open(test_file_path, 'r') as f:
                        existing = f.read()
                    
                    new_code = self.generate_test_code(analysis, test_needs)
                    # Simple merge: append if not duplicate
                    if new_code not in existing:
                        with open(test_file_path, 'a') as f:
                            f.write('\n\n# Auto-generated additions\n')
                            f.write(new_code)
                    
                    results["tests_updated"].append(str(test_file_path))
            else:
                print(f"   ✨ Generating new test file...")
                if not dry_run:
                    test_code = self.generate_test_code(analysis, test_needs)
                    with open(test_file_path, 'w') as f:
                        f.write(test_code)
                    results["tests_generated"].append(str(test_file_path))
        
        # Find obsolete tests
        print("\n🔍 Checking for obsolete tests...")
        obsolete = self.find_obsolete_tests()
        if obsolete:
            print(f"   Found {len(obsolete)} potentially obsolete test(s)")
            results["obsolete_tests"] = [str(t) for t in obsolete]
            if not dry_run:
                print("   ⚠️  Review manually before deleting")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Summary:")
        print(f"   Files analyzed: {len(results['files_analyzed'])}")
        print(f"   Tests generated: {len(results['tests_generated'])}")
        print(f"   Tests updated: {len(results['tests_updated'])}")
        print(f"   Obsolete tests: {len(results['obsolete_tests'])}")
        
        return results


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🤖 TESTBOT - Zantara Test Automation Agent",
        epilog="Part of Nuzantara Prime Test Automation System"
    )
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    parser.add_argument("--backend-dir", default="apps/backend-rag/backend", help="Backend directory")
    parser.add_argument("--test-dir", default="apps/backend-rag/tests", help="Test directory")
    
    args = parser.parse_args()
    
    backend_dir = Path(args.backend_dir)
    test_dir = Path(args.test_dir)
    
    if not backend_dir.exists():
        print(f"❌ Backend directory not found: {backend_dir}")
        sys.exit(1)
    
    agent = AITestAgent(backend_dir, test_dir)
    results = agent.run(dry_run=args.dry_run)
    
    if results.get("status") == "no_changes":
        sys.exit(0)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

