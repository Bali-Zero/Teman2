"""
🔧 TEST MAINTAINER AGENT

Maintains and updates existing tests when source code changes.
Ensures tests stay synchronized with codebase evolution.

Features:
- Source-to-test mapping
- Change impact analysis
- Automatic test updates
- Validation and fixing
- Comprehensive metrics
"""

import ast
import asyncio
import json
import logging
import subprocess
import time
from datetime import datetime
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


class TestMapper:
    """Maps source files to their corresponding test files."""
    
    def __init__(self, repo_path: Path, tests_dir: Path):
        self.repo_path = repo_path
        self.tests_dir = tests_dir
        self._mapping_cache: Dict[str, List[str]] = {}
        
    def find_tests_for_source(self, source_file: Path) -> List[Path]:
        """Find test files that test the given source file."""
        cache_key = str(source_file.relative_to(self.repo_path))
        
        if cache_key in self._mapping_cache:
            return [Path(p) for p in self._mapping_cache[cache_key]]
        
        test_files = []
        
        # Strategy 1: Direct naming convention
        test_candidates = [
            self.tests_dir / f"test_{source_file.name}",
            self.tests_dir / source_file.with_name(f"test_{source_file.name}"),
            self.tests_dir / source_file.parent / f"test_{source_file.name}",
        ]
        
        for candidate in test_candidates:
            if candidate.exists():
                test_files.append(candidate)
        
        # Strategy 2: Search in test content
        if not test_files:
            test_files = self._search_test_content(source_file)
        
        # Strategy 3: Module-based mapping
        if not test_files:
            test_files = self._module_based_mapping(source_file)
        
        # Cache result
        self._mapping_cache[cache_key] = [str(f) for f in test_files]
        return test_files
    
    def _search_test_content(self, source_file: Path) -> List[Path]:
        """Search for test files that import or reference the source file."""
        test_files = []
        module_name = source_file.stem
        
        try:
            for test_file in self.tests_dir.rglob("test_*.py"):
                if not test_file.is_file():
                    continue
                
                try:
                    content = test_file.read_text(encoding='utf-8')
                    
                    # Check for imports or references
                    if (f"import {module_name}" in content or 
                        f"from {module_name}" in content or
                        module_name in content):
                        test_files.append(test_file)
                        
                except Exception:
                    continue  # Skip unreadable files
                    
        except Exception as e:
            logger.warning(f"Error searching test content: {e}")
        
        return test_files
    
    def _module_based_mapping(self, source_file: Path) -> List[Path]:
        """Map based on module structure."""
        test_files = []
        
        # Convert source path to module path
        relative_path = source_file.relative_to(self.repo_path)
        module_parts = list(relative_path.with_suffix('').parts)
        
        # Look for tests in corresponding test directories
        for depth in range(len(module_parts)):
            test_module_parts = ['tests'] + module_parts[depth:]
            test_pattern = self.repo_path / Path(*test_module_parts) / f"test_{module_parts[-1]}.py"
            
            if test_pattern.exists():
                test_files.append(test_pattern)
        
        return test_files
    
    def get_all_mappings(self) -> Dict[str, List[str]]:
        """Get all source-to-test mappings."""
        mappings = {}
        
        # Scan all Python files in repo
        for source_file in self.repo_path.rglob("*.py"):
            if self._is_source_file(source_file):
                test_files = self.find_tests_for_source(source_file)
                if test_files:
                    mappings[str(source_file.relative_to(self.repo_path))] = [str(f) for f in test_files]
        
        return mappings
    
    def _is_source_file(self, file_path: Path) -> bool:
        """Check if file is a source file (not test file)."""
        return (
            file_path.suffix == '.py' and
            'test_' not in file_path.name and
            'tests' not in file_path.parts and
            '__pycache__' not in file_path.parts
        )


class ChangeImpactAnalyzer:
    """Analyzes the impact of code changes on tests."""
    
    def __init__(self):
        pass
    
    def analyze_changes(self, source_file: Path, old_content: str, new_content: str) -> Dict[str, Any]:
        """Analyze changes and determine impact on tests."""
        try:
            old_tree = ast.parse(old_content) if old_content.strip() else None
            new_tree = ast.parse(new_content) if new_content.strip() else None
            
            impact = {
                "breaking_changes": [],
                "additive_changes": [],
                "deprecated_items": [],
                "signature_changes": [],
                "test_update_required": False
            }
            
            if old_tree and new_tree:
                impact = self._compare_ast(old_tree, new_tree)
            elif new_tree and not old_tree:
                # New file
                impact["additive_changes"] = self._extract_definitions(new_tree)
                impact["test_update_required"] = True
            elif old_tree and not new_tree:
                # File deleted
                impact["deprecated_items"] = self._extract_definitions(old_tree)
                impact["test_update_required"] = True
            
            return impact
            
        except Exception as e:
            logger.error(f"Error analyzing changes for {source_file}: {e}")
            return {
                "breaking_changes": [],
                "additive_changes": [],
                "deprecated_items": [],
                "signature_changes": [],
                "test_update_required": True,  # Conservative: assume update needed
                "error": str(e)
            }
    
    def _compare_ast(self, old_tree: ast.AST, new_tree: ast.AST) -> Dict[str, Any]:
        """Compare two AST trees and identify changes."""
        old_defs = self._extract_definitions(old_tree)
        new_defs = self._extract_definitions(new_tree)
        
        impact = {
            "breaking_changes": [],
            "additive_changes": [],
            "deprecated_items": [],
            "signature_changes": [],
            "test_update_required": False
        }
        
        # Find deprecated items
        for item_type, items in old_defs.items():
            for item in items:
                if item not in new_defs.get(item_type, []):
                    impact["deprecated_items"].append(f"{item_type}:{item}")
                    impact["test_update_required"] = True
        
        # Find new items
        for item_type, items in new_defs.items():
            for item in items:
                if item not in old_defs.get(item_type, []):
                    impact["additive_changes"].append(f"{item_type}:{item}")
                    impact["test_update_required"] = True
        
        # TODO: Detect signature changes (more complex AST comparison)
        
        return impact
    
    def _extract_definitions(self, tree: ast.AST) -> Dict[str, List[str]]:
        """Extract class and function definitions from AST."""
        definitions = {
            "classes": [],
            "functions": [],
            "methods": []
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                definitions["classes"].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                if hasattr(node, 'parent_class'):
                    definitions["methods"].append(f"{node.parent_class}.{node.name}")
                else:
                    definitions["functions"].append(node.name)
        
        return definitions


class TestMaintainerAgent:
    """
    Test Maintainer Agent - Keeps tests synchronized with source code.
    
    Workflow:
    1. Monitor source code changes
    2. Map affected test files
    3. Analyze change impact
    4. Update tests automatically
    5. Validate updated tests
    6. Report on maintenance activities
    """
    
    def __init__(
        self,
        repo_path: Path = Path("apps/backend-rag"),
        tests_dir: Path = Path("tests"),
        llm_provider: str = "local"
    ):
        self.repo_path = repo_path
        self.tests_dir = tests_dir
        self.llm_provider = llm_provider
        
        # Initialize services
        if TEST_FORCE_AVAILABLE:
            self.llm_adapter = get_llm_adapter()
            self.metrics_collector = get_metrics_collector()
            self.agent_metrics = self.metrics_collector.register_agent("TestMaintainer")
        else:
            self.llm_adapter = None
            self.metrics_collector = None
            self.agent_metrics = None
        
        # Initialize components
        self.test_mapper = TestMapper(repo_path, tests_dir)
        self.impact_analyzer = ChangeImpactAnalyzer()
        
        # Statistics
        self.stats = {
            "files_analyzed": 0,
            "tests_updated": 0,
            "tests_fixed": 0,
            "breaking_changes": 0,
            "additive_changes": 0
        }
        
        logger.info(f"🔧 TestMaintainerAgent initialized for {repo_path}")
    
    async def scan_and_maintain(self, check_git: bool = True) -> Dict[str, Any]:
        """
        Scan for changes and maintain tests.
        
        Args:
            check_git: Whether to check git for changes
            
        Returns:
            Summary of maintenance activities
        """
        start_time = time.time()
        logger.info("🔍 Starting test maintenance scan...")
        
        try:
            changed_files = []
            
            if check_git:
                changed_files = self._get_changed_files()
            else:
                # Scan all files for comprehensive maintenance
                changed_files = list(self.repo_path.rglob("*.py"))
                changed_files = [f for f in changed_files if self._is_source_file(f)]
            
            logger.info(f"📁 Found {len(changed_files)} files to analyze")
            
            results = []
            for source_file in changed_files[:20]:  # Limit to prevent overwhelming
                try:
                    result = await self.maintain_file_tests(source_file)
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ Failed to maintain tests for {source_file}: {e}")
                    results.append({
                        "source_file": str(source_file),
                        "success": False,
                        "error": str(e)
                    })
            
            # Generate summary
            duration = time.time() - start_time
            summary = {
                "duration": duration,
                "files_analyzed": len(changed_files),
                "results": results,
                "stats": self.stats.copy()
            }
            
            # Log summary
            successful = sum(1 for r in results if r.get("success", False))
            logger.info(f"✅ Maintenance completed in {duration:.2f}s:")
            logger.info(f"   Files analyzed: {successful}/{len(changed_files)}")
            logger.info(f"   Tests updated: {self.stats['tests_updated']}")
            logger.info(f"   Tests fixed: {self.stats['tests_fixed']}")
            logger.info(f"   Breaking changes: {self.stats['breaking_changes']}")
            
            return summary
            
        except Exception as e:
            error_msg = f"Maintenance scan failed: {e}"
            logger.error(f"❌ {error_msg}")
            if self.agent_metrics:
                self.agent_metrics.record_operation(
                    time.time() - start_time,
                    success=False,
                    error=error_msg
                )
            return {"success": False, "error": error_msg}
    
    async def maintain_file_tests(self, source_file: Path) -> Dict[str, Any]:
        """
        Maintain tests for a specific source file.
        
        Args:
            source_file: Path to the source file
            
        Returns:
            Maintenance result
        """
        start_time = time.time()
        logger.info(f"🔄 Maintaining tests for: {source_file}")
        
        try:
            # Find related test files
            test_files = self.test_mapper.find_tests_for_source(source_file)
            
            if not test_files:
                logger.debug(f"⏭️ No tests found for {source_file}")
                return {
                    "source_file": str(source_file),
                    "success": True,
                    "action": "no_tests_found"
                }
            
            # Analyze changes (if git available)
            impact = await self._analyze_file_changes(source_file)
            
            if not impact["test_update_required"]:
                logger.debug(f"⏭️ No test updates required for {source_file}")
                return {
                    "source_file": str(source_file),
                    "success": True,
                    "action": "no_updates_needed",
                    "test_files": [str(f) for f in test_files]
                }
            
            # Update each test file
            update_results = []
            for test_file in test_files:
                try:
                    result = await self._update_test_file(test_file, source_file, impact)
                    update_results.append(result)
                except Exception as e:
                    logger.error(f"❌ Failed to update {test_file}: {e}")
                    update_results.append({
                        "test_file": str(test_file),
                        "success": False,
                        "error": str(e)
                    })
            
            # Update statistics
            self.stats["files_analyzed"] += 1
            successful_updates = sum(1 for r in update_results if r.get("success", False))
            self.stats["tests_updated"] += successful_updates
            
            if impact["breaking_changes"]:
                self.stats["breaking_changes"] += len(impact["breaking_changes"])
            if impact["additive_changes"]:
                self.stats["additive_changes"] += len(impact["additive_changes"])
            
            # Record metrics
            duration = time.time() - start_time
            if self.agent_metrics:
                self.agent_metrics.record_operation(duration, successful_updates > 0)
            
            return {
                "source_file": str(source_file),
                "success": successful_updates > 0,
                "test_files": [str(f) for f in test_files],
                "update_results": update_results,
                "impact": impact,
                "duration": duration
            }
            
        except Exception as e:
            error_msg = f"Error maintaining tests for {source_file}: {e}"
            logger.error(f"❌ {error_msg}")
            if self.agent_metrics:
                self.agent_metrics.record_operation(
                    time.time() - start_time,
                    success=False,
                    error=error_msg
                )
            return {"source_file": str(source_file), "success": False, "error": error_msg}
    
    def _get_changed_files(self) -> List[Path]:
        """Get list of changed files from git."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD", "*.py"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30.0
            )
            
            if result.returncode == 0:
                files = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        file_path = self.repo_path / line.strip()
                        if file_path.exists() and self._is_source_file(file_path):
                            files.append(file_path)
                return files
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting git changes: {e}")
            return []
    
    def _is_source_file(self, file_path: Path) -> bool:
        """Check if file is a source file."""
        return (
            file_path.suffix == '.py' and
            'test_' not in file_path.name and
            'tests' not in file_path.parts and
            '__pycache__' not in file_path.parts
        )
    
    async def _analyze_file_changes(self, source_file: Path) -> Dict[str, Any]:
        """Analyze changes to determine test impact."""
        try:
            # Get current content
            current_content = source_file.read_text(encoding='utf-8')
            
            # Get previous content from git
            try:
                result = subprocess.run(
                    ["git", "show", "HEAD~1:" + str(source_file.relative_to(self.repo_path))],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30.0
                )
                
                if result.returncode == 0:
                    previous_content = result.stdout
                else:
                    previous_content = ""  # File is new
                    
            except Exception:
                previous_content = ""  # File is new or error
            
            # Analyze impact
            impact = self.impact_analyzer.analyze_changes(
                source_file, previous_content, current_content
            )
            
            logger.debug(f"📊 Impact analysis for {source_file}: {impact}")
            return impact
            
        except Exception as e:
            logger.error(f"Error analyzing changes for {source_file}: {e}")
            return {
                "breaking_changes": [],
                "additive_changes": [],
                "deprecated_items": [],
                "signature_changes": [],
                "test_update_required": True,  # Conservative
                "error": str(e)
            }
    
    async def _update_test_file(
        self, 
        test_file: Path, 
        source_file: Path, 
        impact: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a specific test file based on changes."""
        try:
            # Read current test content
            current_test_content = test_file.read_text(encoding='utf-8')
            
            # Generate updated test using LLM
            updated_content = await self._generate_test_update(
                test_file, source_file, current_test_content, impact
            )
            
            # Validate and save
            validation_result = await self._validate_and_save_test(test_file, updated_content)
            
            if validation_result["valid"]:
                # Run tests to verify
                test_result = await self._run_tests(test_file)
                
                if test_result["success"]:
                    logger.info(f"✅ Updated and validated tests: {test_file}")
                    return {
                        "test_file": str(test_file),
                        "success": True,
                        "action": "updated",
                        "test_result": test_result
                    }
                else:
                    logger.warning(f"⚠️ Updated tests failed: {test_file}")
                    return {
                        "test_file": str(test_file),
                        "success": False,
                        "action": "updated_but_failed",
                        "error": test_result.get("error", "Tests failed")
                    }
            else:
                logger.warning(f"⚠️ Test update validation failed: {test_file}")
                return {
                    "test_file": str(test_file),
                    "success": False,
                    "action": "validation_failed",
                    "error": validation_result["error"]
                }
                
        except Exception as e:
            error_msg = f"Error updating test file {test_file}: {e}"
            logger.error(f"❌ {error_msg}")
            return {"test_file": str(test_file), "success": False, "error": error_msg}
    
    async def _generate_test_update(
        self,
        test_file: Path,
        source_file: Path,
        current_test_content: str,
        impact: Dict[str, Any]
    ) -> str:
        """Generate updated test content using LLM."""
        
        # Read source file content
        try:
            source_content = source_file.read_text(encoding='utf-8')
        except Exception:
            source_content = "# Could not read source file"
        
        prompt = f"""You are an Expert Python Test Engineer specializing in test maintenance.

TASK: Update existing tests to reflect changes in the source code.

SOURCE FILE: {source_file.relative_to(self.repo_path)}
TEST FILE: {test_file.relative_to(self.repo_path)}

CHANGES DETECTED:
- Breaking changes: {impact['breaking_changes']}
- Additive changes: {impact['additive_changes']}
- Deprecated items: {impact['deprecated_items']}

CURRENT SOURCE CODE:
```python
{source_content}
```

CURRENT TEST CODE:
```python
{current_test_content}
```

REQUIREMENTS:
1. Update tests to handle breaking changes
2. Add tests for new functions/classes
3. Remove or mock deprecated items
4. Maintain existing test structure and patterns
5. Keep all working tests unchanged
6. Add comprehensive tests for new functionality
7. Ensure 100% compatibility with updated source code
8. Preserve test fixtures and setup code

UPDATE STRATEGY:
- If functions were removed: remove or mock related tests
- If functions were added: add comprehensive tests
- If signatures changed: update test calls
- If classes were modified: update test instances

Return ONLY the complete updated Python test code. No explanations, no markdown formatting.
"""
        
        try:
            if self.llm_adapter:
                provider_map = {
                    "local": LLMProvider.OLLAMA,
                    "gemini": LLMProvider.GEMINI,
                    "mock": LLMProvider.MOCK
                }
                
                request = LLMRequest(
                    prompt=prompt,
                    max_tokens=8000,  # Larger for comprehensive updates
                    temperature=0.1,
                    provider=provider_map.get(self.llm_provider, LLMProvider.OLLAMA)
                )
                
                response = await self.llm_adapter.generate(request)
                logger.info(f"🤖 Generated test update: {len(response.text)} chars")
                return response.text
                
            else:
                logger.warning("⚠️ LLM adapter not available, returning original tests")
                return current_test_content
                
        except Exception as e:
            logger.error(f"❌ Test update generation failed: {e}")
            return current_test_content
    
    async def _validate_and_save_test(self, test_file: Path, test_content: str) -> Dict[str, Any]:
        """Validate test syntax and save to file."""
        try:
            # Check syntax
            ast.parse(test_content)
            
            # Create backup
            backup_file = test_file.with_suffix(f".backup.{int(time.time())}")
            if test_file.exists():
                test_file.rename(backup_file)
            
            # Save updated test
            test_file.write_text(test_content, encoding='utf-8')
            logger.info(f"💾 Updated test saved to {test_file}")
            
            return {"valid": True, "test_file": str(test_file), "backup": str(backup_file)}
            
        except SyntaxError as e:
            error_msg = f"Syntax error in updated test: {e}"
            logger.error(f"❌ {error_msg}")
            return {"valid": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Error saving updated test: {e}"
            logger.error(f"❌ {error_msg}")
            return {"valid": False, "error": error_msg}
    
    async def _run_tests(self, test_file: Path) -> Dict[str, Any]:
        """Run tests to verify updates."""
        try:
            cmd = ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"]
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60.0
            )
            
            success = result.returncode == 0
            
            return {
                "success": success,
                "output": result.stdout,
                "error": result.stderr if not success else None
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Test execution timed out"}
        except Exception as e:
            return {"success": False, "error": f"Error running tests: {e}"}
    
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
        logger.info("🧹 TestMaintainerAgent cleaned up")


# CLI interface
async def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Maintainer Agent")
    parser.add_argument("--repo", default="apps/backend-rag", help="Repository path")
    parser.add_argument("--no-git", action="store_true", help="Don't check git, scan all files")
    parser.add_argument("--provider", default="local", choices=["local", "gemini", "mock"])
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] 🔧 TestMaintainer: %(message)s"
    )
    
    # Create and run agent
    agent = TestMaintainerAgent(
        repo_path=Path(args.repo),
        llm_provider=args.provider
    )
    
    try:
        result = await agent.scan_and_maintain(check_git=not args.no_git)
        
        # Print summary
        print("\n🔧 Test Maintenance Summary:")
        print(f"Files analyzed: {result['files_analyzed']}")
        print(f"Tests updated: {agent.stats['tests_updated']}")
        print(f"Tests fixed: {agent.stats['tests_fixed']}")
        print(f"Breaking changes: {agent.stats['breaking_changes']}")
        print(f"Duration: {result['duration']:.2f}s")
        
        # Save metrics if available
        if agent.metrics_collector:
            agent.metrics_collector.save_snapshot()
            
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
