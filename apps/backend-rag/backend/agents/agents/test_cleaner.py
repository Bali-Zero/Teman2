"""
🧹 TEST CLEANER AGENT

Identifies and removes obsolete, duplicate, and useless tests.
Keeps the test suite clean and maintainable.

Features:
- Orphaned test detection
- Semantic duplicate identification
- Useless test detection (always green, never executed)
- Safe archiving before deletion
- Comprehensive metrics and reporting
"""

import ast
import asyncio
import json
import logging
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Import Test Force services
try:
    from backend.agents.services.llm_adapter import LLMProvider, LLMRequest, get_llm_adapter
    from backend.agents.services.test_metrics import get_metrics_collector
    TEST_FORCE_AVAILABLE = True
except ImportError:
    TEST_FORCE_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestAnalyzer:
    """Analyzes test files for various quality issues."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        
    def analyze_test_file(self, test_file: Path) -> Dict[str, Any]:
        """Comprehensive analysis of a single test file."""
        try:
            content = test_file.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            analysis = {
                "file": str(test_file),
                "size": len(content),
                "lines": len(content.splitlines()),
                "imports": self._extract_imports(tree),
                "test_functions": self._extract_test_functions(tree),
                "test_classes": self._extract_test_classes(tree),
                "fixtures": self._extract_fixtures(tree),
                "mock_usage": self._analyze_mock_usage(content),
                "assertions": self._count_assertions(tree),
                "complexity": self._calculate_complexity(tree),
                "quality_issues": []
            }
            
            # Detect quality issues
            analysis["quality_issues"].extend(self._detect_quality_issues(analysis))
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing test file {test_file}: {e}")
            return {
                "file": str(test_file),
                "error": str(e),
                "quality_issues": ["parse_error"]
            }
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    imports.append(f"{module}.{name.name}")
        return imports
    
    def _extract_test_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract test functions with metadata."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                functions.append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                    "has_docstring": ast.get_docstring(node) is not None,
                    "line_count": node.end_lineno - node.lineno + 1 if hasattr(node, 'end_lineno') else 0
                })
        return functions
    
    def _extract_test_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract test classes."""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(name.startswith('test') for name in node.name.lower()):
                classes.append({
                    "name": node.name,
                    "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                    "base_classes": [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
                })
        return classes
    
    def _extract_fixtures(self, tree: ast.AST) -> List[str]:
        """Extract pytest fixtures."""
        fixtures = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Name) and decorator.id == 'fixture') or \
                       (isinstance(decorator, ast.Attribute) and decorator.attr == 'fixture'):
                        fixtures.append(node.name)
        return fixtures
    
    def _analyze_mock_usage(self, content: str) -> Dict[str, int]:
        """Analyze mock usage in tests."""
        return {
            "mock_calls": content.count('mock.') + content.count('Mock('),
            "patch_calls": content.count('@patch') + content.count('patch('),
            "magic_mock": content.count('MagicMock'),
            "async_mock": content.count('AsyncMock')
        }
    
    def _count_assertions(self, tree: ast.AST) -> int:
        """Count assertion statements."""
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                count += 1
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['assert_equal', 'assert_not_equal', 'assert_true', 'assert_false', 
                                         'assert_in', 'assert_not_in', 'assert_raises', 'assert_is_none',
                                         'assert_is_not_none', 'assert_greater', 'assert_less']:
                        count += 1
        return count
    
    def _calculate_complexity(self, tree: ast.AST) -> Dict[str, int]:
        """Calculate complexity metrics."""
        complexity = {
            "cyclomatic": 1,  # Base complexity
            "nested_loops": 0,
            "nested_conditions": 0,
            "try_except": 0
        }
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.With)):
                complexity["cyclomatic"] += 1
                if isinstance(node, (ast.While, ast.For)):
                    complexity["nested_loops"] += 1
                elif isinstance(node, ast.If):
                    complexity["nested_conditions"] += 1
            elif isinstance(node, ast.Try):
                complexity["try_except"] += 1
                complexity["cyclomatic"] += len(node.handlers)
        
        return complexity
    
    def _detect_quality_issues(self, analysis: Dict[str, Any]) -> List[str]:
        """Detect quality issues in test file."""
        issues = []
        
        # No test functions
        if not analysis.get("test_functions"):
            issues.append("no_test_functions")
        
        # No assertions
        if analysis.get("assertions", 0) == 0:
            issues.append("no_assertions")
        
        # No mocks for external dependencies
        if analysis.get("mock_usage", {}).get("mock_calls", 0) == 0 and \
           any("import" in imp for imp in analysis.get("imports", [])):
            issues.append("no_mocks_for_external_deps")
        
        # Too simple (always green)
        if analysis.get("assertions", 0) <= 1 and analysis.get("mock_usage", {}).get("mock_calls", 0) == 0:
            issues.append("too_simple")
        
        # Too complex
        if analysis.get("complexity", {}).get("cyclomatic", 0) > 10:
            issues.append("too_complex")
        
        # Empty test file
        if analysis.get("lines", 0) < 10:
            issues.append("empty_or_minimal")
        
        return issues


class DuplicateDetector:
    """Detects semantic duplicates in test files."""
    
    def __init__(self, llm_adapter=None):
        self.llm_adapter = llm_adapter
        
    def find_duplicates(self, test_files: List[Path]) -> List[Dict[str, Any]]:
        """Find duplicate or similar test files."""
        duplicates = []
        
        # Simple heuristic-based duplicate detection
        similarity_groups = self._group_by_similarity(test_files)
        
        for group_id, group in similarity_groups.items():
            if len(group) > 1:
                duplicates.append({
                    "group_id": group_id,
                    "files": [str(f) for f in group],
                    "similarity_type": "heuristic",
                    "reason": "Similar structure and assertions"
                })
        
        # LLM-based semantic duplicate detection (if available)
        if self.llm_adapter and len(test_files) <= 20:  # Limit to prevent API overload
            semantic_duplicates = asyncio.run(self._find_semantic_duplicates(test_files))
            duplicates.extend(semantic_duplicates)
        
        return duplicates
    
    def _group_by_similarity(self, test_files: List[Path]) -> Dict[str, List[Path]]:
        """Group files by heuristic similarity."""
        groups = defaultdict(list)
        
        for test_file in test_files:
            try:
                content = test_file.read_text(encoding='utf-8')
                
                # Create similarity signature
                signature = self._create_similarity_signature(content)
                groups[signature].append(test_file)
                
            except Exception as e:
                logger.warning(f"Error processing {test_file}: {e}")
                continue
        
        return dict(groups)
    
    def _create_similarity_signature(self, content: str) -> str:
        """Create a signature for similarity matching."""
        # Normalize content
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        
        # Extract key patterns
        patterns = []
        for line in lines:
            # Test function names
            if line.startswith('def test_'):
                patterns.append('test_func')
            # Common assertions
            elif any(x in line for x in ['assert', 'assertEquals', 'assertTrue']):
                patterns.append('assertion')
            # Mock usage
            elif any(x in line for x in ['mock', 'Mock', 'patch']):
                patterns.append('mock')
            # Fixtures
            elif line.startswith('@pytest.fixture') or line.startswith('@fixture'):
                patterns.append('fixture')
        
        return '|'.join(sorted(set(patterns)))
    
    async def _find_semantic_duplicates(self, test_files: List[Path]) -> List[Dict[str, Any]]:
        """Find semantic duplicates using LLM."""
        duplicates = []
        
        # Compare each pair of files
        for i, file1 in enumerate(test_files):
            for file2 in test_files[i+1:]:
                try:
                    similarity = await self._compare_files_semantically(file1, file2)
                    
                    if similarity > 0.8:  # High similarity threshold
                        duplicates.append({
                            "group_id": f"semantic_{i}_{test_files.index(file2)}",
                            "files": [str(file1), str(file2)],
                            "similarity_type": "semantic",
                            "similarity_score": similarity,
                            "reason": f"Semantic similarity: {similarity:.2f}"
                        })
                        
                except Exception as e:
                    logger.warning(f"Error comparing {file1} and {file2}: {e}")
                    continue
        
        return duplicates
    
    async def _compare_files_semantically(self, file1: Path, file2: Path) -> float:
        """Compare two files semantically using LLM."""
        try:
            content1 = file1.read_text(encoding='utf-8')[:2000]  # Limit content
            content2 = file2.read_text(encoding='utf-8')[:2000]
            
            prompt = f"""Compare these two test files and return a similarity score between 0.0 and 1.0.

Test 1:
```python
{content1}
```

Test 2:
```python
{content2}
```

Return ONLY a number between 0.0 and 1.0 representing semantic similarity.
Consider: test purpose, assertions, structure, and functionality.
"""
            
            request = LLMRequest(
                prompt=prompt,
                max_tokens=50,
                temperature=0.1,
                provider=LLMProvider.OLLAMA
            )
            
            response = await self.llm_adapter.generate(request)
            
            # Extract similarity score
            try:
                score = float(response.text.strip())
                return max(0.0, min(1.0, score))  # Clamp to [0, 1]
            except ValueError:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error in semantic comparison: {e}")
            return 0.0


class OrphanDetector:
    """Detects orphaned tests (tests for deleted source code)."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        
    def find_orphans(self, test_files: List[Path]) -> List[Dict[str, Any]]:
        """Find test files that test non-existent source code."""
        orphans = []
        
        for test_file in test_files:
            try:
                orphan_info = self._check_if_orphaned(test_file)
                if orphan_info["is_orphaned"]:
                    orphans.append(orphan_info)
                    
            except Exception as e:
                logger.warning(f"Error checking {test_file}: {e}")
                continue
        
        return orphans
    
    def _check_if_orphaned(self, test_file: Path) -> Dict[str, Any]:
        """Check if a test file is orphaned."""
        try:
            content = test_file.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            # Extract potential source module references
            imports = self._extract_imports(tree)
            referenced_modules = self._extract_referenced_modules(content, tree)
            
            missing_modules = []
            for module in referenced_modules:
                if not self._module_exists(module):
                    missing_modules.append(module)
            
            is_orphaned = len(missing_modules) > 0 and len(referenced_modules) > 0
            
            return {
                "test_file": str(test_file),
                "is_orphaned": is_orphaned,
                "referenced_modules": referenced_modules,
                "missing_modules": missing_modules,
                "orphan_reason": f"Missing modules: {missing_modules}" if missing_modules else None
            }
            
        except Exception as e:
            return {
                "test_file": str(test_file),
                "is_orphaned": False,
                "error": str(e)
            }
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports
    
    def _extract_referenced_modules(self, content: str, tree: ast.AST) -> List[str]:
        """Extract modules that are being tested."""
        modules = set()
        
        # From imports
        for imp in self._extract_imports(tree):
            if not imp.startswith(('test_', 'pytest', 'unittest', 'mock', 'conftest')):
                modules.add(imp.split('.')[0])
        
        # From function/class names (heuristic)
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('def test_'):
                # Extract module from function name
                func_name = line[5:].split('(')[0]
                if '_' in func_name:
                    potential_module = func_name.split('_')[0]
                    if potential_module not in ['test', 'mock', 'setup']:
                        modules.add(potential_module)
        
        return list(modules)
    
    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists in the codebase."""
        # Check as file
        module_file = self.repo_path / f"{module_name}.py"
        if module_file.exists():
            return True
        
        # Check as package
        module_dir = self.repo_path / module_name
        if module_dir.is_dir() and (module_dir / "__init__.py").exists():
            return True
        
        # Check in subdirectories
        for pattern in [f"*/{module_name}.py", f"*/{module_name}/__init__.py"]:
            if list(self.repo_path.glob(pattern)):
                return True
        
        return False


class TestCleanerAgent:
    """
    Test Cleaner Agent - Identifies and removes problematic tests.
    
    Workflow:
    1. Scan all test files
    2. Analyze quality and detect issues
    3. Find duplicates and orphans
    4. Generate cleanup recommendations
    5. Archive and remove problematic tests
    6. Generate comprehensive reports
    """
    
    def __init__(
        self,
        repo_path: Path = Path("apps/backend-rag"),
        tests_dir: Path = Path("tests"),
        llm_provider: str = "local",
        dry_run: bool = True
    ):
        self.repo_path = repo_path
        self.tests_dir = tests_dir
        self.llm_provider = llm_provider
        self.dry_run = dry_run
        
        # Initialize services
        if TEST_FORCE_AVAILABLE:
            self.llm_adapter = get_llm_adapter()
            self.metrics_collector = get_metrics_collector()
            self.agent_metrics = self.metrics_collector.register_agent("TestCleaner")
        else:
            self.llm_adapter = None
            self.metrics_collector = None
            self.agent_metrics = None
        
        # Initialize components
        self.analyzer = TestAnalyzer(repo_path)
        self.duplicate_detector = DuplicateDetector(self.llm_adapter)
        self.orphan_detector = OrphanDetector(repo_path)
        
        # Archive directory
        self.archive_dir = tests_dir / ".archive" / datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Statistics
        self.stats = {
            "files_analyzed": 0,
            "orphans_found": 0,
            "duplicates_found": 0,
            "useless_tests_found": 0,
            "files_archived": 0,
            "space_freed": 0
        }
        
        logger.info(f"🧹 TestCleanerAgent initialized for {repo_path}")
    
    async def scan_and_clean(self, aggressive: bool = False) -> Dict[str, Any]:
        """
        Scan for test issues and clean them up.
        
        Args:
            aggressive: Use more aggressive cleanup criteria
            
        Returns:
            Summary of cleaning activities
        """
        start_time = time.time()
        logger.info("🔍 Starting test cleanup scan...")
        
        try:
            # Find all test files
            test_files = list(self.tests_dir.rglob("test_*.py"))
            test_files = [f for f in test_files if f.is_file()]
            logger.info(f"📁 Found {len(test_files)} test files")
            
            # Analyze all test files
            logger.info("🔍 Analyzing test files...")
            analyses = []
            for test_file in test_files:
                analysis = self.analyzer.analyze_test_file(test_file)
                analyses.append(analysis)
                self.stats["files_analyzed"] += 1
            
            # Detect issues
            logger.info("🔍 Detecting test issues...")
            orphans = self.orphan_detector.find_orphans(test_files)
            duplicates = self.duplicate_detector.find_duplicates(test_files)
            useless_tests = self._identify_useless_tests(analyses, aggressive)
            
            # Update statistics
            self.stats["orphans_found"] = len(orphans)
            self.stats["duplicates_found"] = len(duplicates)
            self.stats["useless_tests_found"] = len(useless_tests)
            
            # Generate cleanup recommendations
            recommendations = self._generate_recommendations(
                analyses, orphans, duplicates, useless_tests
            )
            
            # Perform cleanup (if not dry run)
            cleanup_results = []
            if not self.dry_run:
                logger.info("🧹 Performing cleanup...")
                for recommendation in recommendations:
                    result = await self._cleanup_item(recommendation)
                    cleanup_results.append(result)
            
            # Generate summary
            duration = time.time() - start_time
            summary = {
                "duration": duration,
                "files_analyzed": len(test_files),
                "orphans_found": len(orphans),
                "duplicates_found": len(duplicates),
                "useless_tests_found": len(useless_tests),
                "recommendations": recommendations,
                "cleanup_results": cleanup_results if not self.dry_run else [],
                "stats": self.stats.copy(),
                "dry_run": self.dry_run
            }
            
            # Log summary
            logger.info(f"✅ Cleanup scan completed in {duration:.2f}s:")
            logger.info(f"   Files analyzed: {len(test_files)}")
            logger.info(f"   Orphans found: {len(orphans)}")
            logger.info(f"   Duplicates found: {len(duplicates)}")
            logger.info(f"   Useless tests found: {len(useless_tests)}")
            logger.info(f"   Recommendations: {len(recommendations)}")
            
            if self.dry_run:
                logger.info("🔍 DRY RUN MODE - No files were deleted")
                logger.info("   Run with --no-dry-run to perform actual cleanup")
            
            return summary
            
        except Exception as e:
            error_msg = f"Cleanup scan failed: {e}"
            logger.error(f"❌ {error_msg}")
            if self.agent_metrics:
                self.agent_metrics.record_operation(
                    time.time() - start_time,
                    success=False,
                    error=error_msg
                )
            return {"success": False, "error": error_msg}
    
    def _identify_useless_tests(self, analyses: List[Dict[str, Any]], aggressive: bool) -> List[Dict[str, Any]]:
        """Identify useless or low-value tests."""
        useless = []
        
        for analysis in analyses:
            if "error" in analysis:
                continue
            
            issues = analysis.get("quality_issues", [])
            
            # Define useless criteria
            is_useless = False
            reason = []
            
            # Always check for basic issues
            if "no_test_functions" in issues:
                is_useless = True
                reason.append("no test functions")
            
            if "no_assertions" in issues:
                is_useless = True
                reason.append("no assertions")
            
            if "empty_or_minimal" in issues:
                is_useless = True
                reason.append("empty or minimal")
            
            # Aggressive mode criteria
            if aggressive:
                if "too_simple" in issues:
                    is_useless = True
                    reason.append("too simple")
                
                if analysis.get("lines", 0) < 5:
                    is_useless = True
                    reason.append("too short")
            
            if is_useless:
                useless.append({
                    "file": analysis["file"],
                    "reason": ", ".join(reason),
                    "issues": issues,
                    "analysis": analysis
                })
        
        return useless
    
    def _generate_recommendations(
        self,
        analyses: List[Dict[str, Any]],
        orphans: List[Dict[str, Any]],
        duplicates: List[Dict[str, Any]],
        useless_tests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate cleanup recommendations."""
        recommendations = []
        
        # Orphaned tests - high priority removal
        for orphan in orphans:
            recommendations.append({
                "action": "remove",
                "priority": "high",
                "file": orphan["test_file"],
                "reason": f"Orphaned test: {orphan['orphan_reason']}",
                "category": "orphan"
            })
        
        # Useless tests - medium priority removal
        for useless in useless_tests:
            recommendations.append({
                "action": "remove",
                "priority": "medium",
                "file": useless["file"],
                "reason": f"Useless test: {useless['reason']}",
                "category": "useless"
            })
        
        # Duplicates - keep one, remove others
        for duplicate_group in duplicates:
            files = duplicate_group["files"]
            if len(files) > 1:
                # Keep the first/largest file, remove others
                files_to_remove = files[1:]  # Keep first one
                for file_to_remove in files_to_remove:
                    recommendations.append({
                        "action": "remove",
                        "priority": "low",
                        "file": file_to_remove,
                        "reason": f"Duplicate of {files[0]}",
                        "category": "duplicate",
                        "duplicate_group": duplicate_group["group_id"]
                    })
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        return recommendations
    
    async def _cleanup_item(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """Perform cleanup for a single recommendation."""
        file_path = Path(recommendation["file"])
        
        try:
            if not file_path.exists():
                return {
                    "file": str(file_path),
                    "success": False,
                    "error": "File does not exist"
                }
            
            # Create archive
            if not self.archive_dir.exists():
                self.archive_dir.mkdir(parents=True, exist_ok=True)
            
            # Archive file
            archive_path = self.archive_dir / file_path.name
            shutil.move(str(file_path), str(archive_path))
            
            # Update statistics
            self.stats["files_archived"] += 1
            self.stats["space_freed"] += file_path.stat().st_size
            
            logger.info(f"🗑️ Archived: {file_path} -> {archive_path}")
            
            return {
                "file": str(file_path),
                "success": True,
                "action": "archived",
                "archive_path": str(archive_path),
                "size_freed": file_path.stat().st_size
            }
            
        except Exception as e:
            error_msg = f"Error archiving {file_path}: {e}"
            logger.error(f"❌ {error_msg}")
            return {
                "file": str(file_path),
                "success": False,
                "error": error_msg
            }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive cleanup report."""
        if self.metrics_collector:
            return self.metrics_collector.generate_report("markdown")
        else:
            return self._generate_simple_report(results)
    
    def _generate_simple_report(self, results: Dict[str, Any]) -> str:
        """Generate simple markdown report."""
        md = f"""# 🧹 Test Cleanup Report

**Generated:** {datetime.now().isoformat()}
**Mode:** {'DRY RUN' if results.get('dry_run', True) else 'LIVE'}

## Summary
- **Files analyzed:** {results.get('files_analyzed', 0)}
- **Orphans found:** {results.get('orphans_found', 0)}
- **Duplicates found:** {results.get('duplicates_found', 0)}
- **Useless tests found:** {results.get('useless_tests_found', 0)}
- **Recommendations:** {len(results.get('recommendations', []))}
- **Files archived:** {results.get('stats', {}).get('files_archived', 0)}
- **Space freed:** {results.get('stats', {}).get('space_freed', 0)} bytes

## Recommendations
"""
        
        for rec in results.get('recommendations', []):
            md += f"- **{rec['priority'].upper()}** {rec['action']}: {rec['file']} - {rec['reason']}\n"
        
        if results.get('dry_run', True):
            md += "\n> **Note:** This was a dry run. No files were actually deleted.\n"
            md += "> Run with `--no-dry-run` to perform actual cleanup.\n"
        
        return md
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        stats = self.stats.copy()
        if self.agent_metrics:
            stats.update({
                "agent_success_rate": self.agent_metrics.success_rate,
                "avg_operation_time": self.agent_metrics.avg_operation_time,
                "total_operations": self.agent_metrics.operations_completed + self.agent_metrics.operations_failed
            })
        return stats
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.llm_adapter:
            await self.llm_adapter.close()
        logger.info("🧹 TestCleanerAgent cleaned up")


# CLI interface
async def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Cleaner Agent")
    parser.add_argument("--repo", default="apps/backend-rag", help="Repository path")
    parser.add_argument("--no-dry-run", action="store_true", help="Perform actual cleanup")
    parser.add_argument("--aggressive", action="store_true", help="Use aggressive cleanup criteria")
    parser.add_argument("--provider", default="local", choices=["local", "gemini", "mock"])
    parser.add_argument("--report", help="Save report to file")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] 🧹 TestCleaner: %(message)s"
    )
    
    # Create and run agent
    agent = TestCleanerAgent(
        repo_path=Path(args.repo),
        llm_provider=args.provider,
        dry_run=not args.no_dry_run
    )
    
    try:
        result = await agent.scan_and_clean(aggressive=args.aggressive)
        
        # Generate and save report
        report = agent.generate_report(result)
        if args.report:
            with open(args.report, 'w') as f:
                f.write(report)
            print(f"📄 Report saved to: {args.report}")
        else:
            print("\n" + report)
        
        # Print summary
        print(f"\n🧹 Test Cleanup Summary:")
        print(f"Files analyzed: {result['files_analyzed']}")
        print(f"Orphans found: {result['orphans_found']}")
        print(f"Duplicates found: {result['duplicates_found']}")
        print(f"Useless tests: {result['useless_tests_found']}")
        print(f"Recommendations: {len(result['recommendations'])}")
        if not args.no_dry_run:
            print(f"Files archived: {agent.stats['files_archived']}")
            print(f"Space freed: {agent.stats['space_freed']} bytes")
        
        # Save metrics if available
        if agent.metrics_collector:
            agent.metrics_collector.save_snapshot()
            
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
