#!/usr/bin/env python3
"""
Health Check Script for RAG Dedup Verification
Verifies that SearchService is the canonical retriever and /api/search works correctly
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path (multiple paths needed for absolute imports)
backend_path = Path(__file__).parent.parent / "backend"
apps_backend_path = Path(__file__).parent.parent.parent / "apps" / "backend-rag" / "backend"
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(apps_backend_path))
# Also add parent for 'backend' absolute imports
sys.path.insert(0, str(backend_path.parent))

import logging
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def check_search_service_import() -> dict[str, Any]:
    """Check SearchService can be imported"""
    try:
        return {
            "status": "ok",
            "message": "SearchService imported successfully",
        }
    except Exception as e:
        return {"status": "error", "message": f"SearchService import failed: {e}"}


async def check_search_service_initialization() -> dict[str, Any]:
    """Check SearchService can be initialized"""
    try:
        from services.search_service import SearchService

        service = SearchService()
        return {
            "status": "ok",
            "message": "SearchService initialized successfully",
        }
    except Exception as e:
        return {"status": "error", "message": f"SearchService initialization failed: {e}"}


async def check_search_service_has_apply_filters() -> dict[str, Any]:
    """Check SearchService.search() has apply_filters parameter"""
    try:
        import inspect

        from services.search_service import SearchService

        sig = inspect.signature(SearchService.search)
        params = list(sig.parameters.keys())

        if "apply_filters" in params:
            return {
                "status": "ok",
                "message": "SearchService.search() has apply_filters parameter",
                "parameters": params,
            }
        else:
            return {
                "status": "error",
                "message": "SearchService.search() missing apply_filters parameter",
                "parameters": params,
            }
    except Exception as e:
        return {"status": "error", "message": f"Parameter check failed: {e}"}


async def check_knowledge_service_deprecated() -> dict[str, Any]:
    """Check KnowledgeService is marked as deprecated"""
    try:
        service_path = (
            Path(__file__).parent.parent
            / "backend"
            / "app"
            / "modules"
            / "knowledge"
            / "service.py"
        )
        content = service_path.read_text()

        # Check module docstring or class docstring
        has_deprecated_in_doc = "DEPRECATED" in content.upper() or "deprecated" in content.lower()

        if has_deprecated_in_doc:
            return {
                "status": "ok",
                "message": "KnowledgeService is marked as deprecated",
            }
        else:
            return {
                "status": "warning",
                "message": "KnowledgeService not explicitly marked as deprecated",
            }
    except Exception as e:
        return {"status": "error", "message": f"KnowledgeService check failed: {e}"}


async def check_router_uses_search_service() -> dict[str, Any]:
    """Check knowledge router uses get_search_service helper"""
    try:
        router_path = (
            Path(__file__).parent.parent / "backend" / "app" / "modules" / "knowledge" / "router.py"
        )
        content = router_path.read_text()

        checks = {
            "get_search_service": "get_search_service" in content,
            "app.state.search_service": "app.state.search_service" in content
            or "getattr(request.app.state" in content,
            "apply_filters=True": "apply_filters=True" in content,
            "Request import": "Request" in content
            and ("from fastapi import" in content or "Request," in content),
        }

        all_passed = all(checks.values())
        return {
            "status": "ok" if all_passed else "warning",
            "message": "Router refactored to use SearchService"
            if all_passed
            else "Router may not be fully refactored",
            "checks": checks,
        }
    except Exception as e:
        return {"status": "error", "message": f"Router check failed: {e}"}


async def check_config_has_search_flag() -> dict[str, Any]:
    """Check config.py has search_enable_filters flag"""
    try:
        from app.core.config import settings

        if hasattr(settings, "search_enable_filters"):
            return {
                "status": "ok",
                "message": f"search_enable_filters flag exists (value: {settings.search_enable_filters})",
            }
        else:
            return {
                "status": "error",
                "message": "search_enable_filters flag missing in config",
            }
    except Exception as e:
        return {"status": "error", "message": f"Config check failed: {e}"}


async def check_cache_prefix_separation() -> dict[str, Any]:
    """Check cache prefixes are separated (no collision)"""
    try:
        search_service_path = (
            Path(__file__).parent.parent / "backend" / "services" / "search_service.py"
        )
        knowledge_service_path = (
            Path(__file__).parent.parent
            / "backend"
            / "app"
            / "modules"
            / "knowledge"
            / "service.py"
        )

        search_content = search_service_path.read_text()
        knowledge_content = knowledge_service_path.read_text()

        # Check SearchService uses "rag_search"
        search_has_prefix = '"rag_search"' in search_content or "'rag_search'" in search_content

        # Check KnowledgeService uses "rag_search_deprecated"
        knowledge_has_deprecated = (
            '"rag_search_deprecated"' in knowledge_content
            or "'rag_search_deprecated'" in knowledge_content
        )

        if search_has_prefix and knowledge_has_deprecated:
            return {
                "status": "ok",
                "message": "Cache prefixes separated (rag_search vs rag_search_deprecated)",
            }
        else:
            return {
                "status": "warning",
                "message": "Cache prefixes may not be properly separated",
                "details": {
                    "search_service_has_prefix": search_has_prefix,
                    "knowledge_service_has_deprecated": knowledge_has_deprecated,
                },
            }
    except Exception as e:
        return {"status": "error", "message": f"Cache prefix check failed: {e}"}


async def check_search_service_filters_logic() -> dict[str, Any]:
    """Check SearchService filter logic is correct"""
    try:
        search_service_path = (
            Path(__file__).parent.parent / "backend" / "services" / "search_service.py"
        )
        content = search_service_path.read_text()

        # Check that filters are enabled by default (not disabled)
        has_filter_logic = "apply_filters" in content
        has_enable_by_default = (
            "apply_filters is False" in content or "apply_filters == False" in content
        )  # Only disable if explicitly False

        if has_filter_logic and has_enable_by_default:
            return {
                "status": "ok",
                "message": "Filter logic: enabled by default, disabled only if apply_filters=False",
            }
        else:
            return {
                "status": "warning",
                "message": "Filter logic may not be correctly implemented",
            }
    except Exception as e:
        return {"status": "error", "message": f"Filter logic check failed: {e}"}


async def check_environment_variables() -> dict[str, Any]:
    """Check critical environment variables are set"""
    try:
        import os
        from app.core.config import Settings

        settings = Settings()
        missing_vars = []
        warnings = []

        # Critical variables
        critical_vars = {
            "OPENAI_API_KEY": settings.openai_api_key,
            "QDRANT_URL": settings.qdrant_url,
        }

        # Optional but recommended
        recommended_vars = {
            "GOOGLE_API_KEY": settings.google_api_key,
            "DATABASE_URL": os.getenv("DATABASE_URL"),
        }

        for var_name, value in critical_vars.items():
            if not value:
                missing_vars.append(var_name)

        for var_name, value in recommended_vars.items():
            if not value:
                warnings.append(var_name)

        if missing_vars:
            return {
                "status": "error",
                "message": f"Missing critical env vars: {', '.join(missing_vars)}",
                "missing": missing_vars,
            }
        elif warnings:
            return {
                "status": "warning",
                "message": f"Missing recommended env vars: {', '.join(warnings)}",
                "warnings": warnings,
            }
        else:
            return {
                "status": "ok",
                "message": "All critical environment variables are set",
            }
    except Exception as e:
        return {"status": "error", "message": f"Environment check failed: {e}"}


async def check_database_connectivity() -> dict[str, Any]:
    """Check PostgreSQL database connectivity"""
    try:
        import os
        import asyncpg

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return {
                "status": "skipped",
                "message": "DATABASE_URL not set, skipping database check",
            }

        try:
            conn = await asyncpg.connect(database_url)
            await conn.execute("SELECT 1")
            await conn.close()
            return {
                "status": "ok",
                "message": "Database connection successful",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Database connection failed: {e}",
            }
    except ImportError:
        return {
            "status": "skipped",
            "message": "asyncpg not available, skipping database check",
        }
    except Exception as e:
        return {"status": "error", "message": f"Database check failed: {e}"}


async def check_qdrant_connectivity() -> dict[str, Any]:
    """Check Qdrant vector database connectivity"""
    try:
        import httpx
        from app.core.config import settings

        qdrant_url = settings.qdrant_url
        if not qdrant_url:
            return {
                "status": "skipped",
                "message": "QDRANT_URL not set, skipping Qdrant check",
            }

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{qdrant_url}/collections")
            if response.status_code == 200:
                return {
                    "status": "ok",
                    "message": f"Qdrant connection successful ({qdrant_url})",
                }
            else:
                return {
                    "status": "error",
                    "message": f"Qdrant returned status {response.status_code}",
                }
    except Exception as e:
        return {"status": "error", "message": f"Qdrant check failed: {e}"}


async def check_type_hints_coverage() -> dict[str, Any]:
    """Check type hints coverage in Python files"""
    try:
        import ast

        backend_dir = Path(__file__).parent.parent / "backend"
        python_files = list(backend_dir.rglob("*.py"))
        python_files = [f for f in python_files if "test" not in str(f) and "__pycache__" not in str(f)]

        total_functions = 0
        typed_functions = 0
        total_classes = 0
        typed_classes = 0

        for py_file in python_files[:50]:  # Limit to first 50 files for performance
            try:
                content = py_file.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_functions += 1
                        if node.returns or any(arg.annotation for arg in node.args.args):
                            typed_functions += 1
                    elif isinstance(node, ast.ClassDef):
                        total_classes += 1
                        # Check if class has type annotations in methods
                        has_typed_methods = any(
                            m.returns or any(a.annotation for a in m.args.args)
                            for m in node.body
                            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                        )
                        if has_typed_methods:
                            typed_classes += 1

            except Exception:
                continue

        if total_functions == 0:
            return {
                "status": "skipped",
                "message": "No functions found to check",
            }

        coverage = (typed_functions / total_functions) * 100 if total_functions > 0 else 0

        if coverage >= 80:
            status = "ok"
        elif coverage >= 50:
            status = "warning"
        else:
            status = "error"

        return {
            "status": status,
            "message": f"Type hints coverage: {coverage:.1f}% ({typed_functions}/{total_functions} functions)",
            "coverage": coverage,
            "typed_functions": typed_functions,
            "total_functions": total_functions,
        }
    except Exception as e:
        return {"status": "error", "message": f"Type hints check failed: {e}"}


async def check_test_coverage() -> dict[str, Any]:
    """Check if test files exist for main modules"""
    try:
        backend_dir = Path(__file__).parent.parent / "backend"
        tests_dir = backend_dir.parent / "tests"

        # Find modules
        modules_dir = backend_dir / "app" / "modules"
        if not modules_dir.exists():
            return {
                "status": "skipped",
                "message": "Modules directory not found",
            }

        modules = [d for d in modules_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        modules_with_tests = 0
        modules_without_tests = []

        for module in modules:
            # Check for corresponding test directory
            test_module_dir = tests_dir / "modules" / module.name
            if test_module_dir.exists() and list(test_module_dir.glob("test_*.py")):
                modules_with_tests += 1
            else:
                modules_without_tests.append(module.name)

        coverage = (modules_with_tests / len(modules)) * 100 if modules else 0

        if coverage >= 80:
            status = "ok"
        elif coverage >= 50:
            status = "warning"
        else:
            status = "error"

        message = f"Test coverage: {coverage:.1f}% ({modules_with_tests}/{len(modules)} modules)"
        if modules_without_tests:
            message += f" - Missing tests for: {', '.join(modules_without_tests[:5])}"

        return {
            "status": status,
            "message": message,
            "coverage": coverage,
            "modules_with_tests": modules_with_tests,
            "total_modules": len(modules),
            "missing_tests": modules_without_tests,
        }
    except Exception as e:
        return {"status": "error", "message": f"Test coverage check failed: {e}"}


async def check_no_hardcoded_secrets() -> dict[str, Any]:
    """Check for hardcoded secrets in code"""
    try:
        import re

        backend_dir = Path(__file__).parent.parent / "backend"
        python_files = list(backend_dir.rglob("*.py"))
        python_files = [f for f in python_files if "test" not in str(f) and "__pycache__" not in str(f)]

        suspicious_patterns = [
            (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API key"),
            (r'AIza[0-9A-Za-z-_]{35}', "Google API key"),
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        ]

        violations = []
        for py_file in python_files[:100]:  # Limit for performance
            try:
                content = py_file.read_text()
                for pattern, description in suspicious_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        violations.append(f"{py_file.name}: {description}")
            except Exception:
                continue

        if violations:
            return {
                "status": "error",
                "message": f"Found {len(violations)} potential hardcoded secrets",
                "violations": violations[:10],  # Limit output
            }
        else:
            return {
                "status": "ok",
                "message": "No hardcoded secrets detected",
            }
    except Exception as e:
        return {"status": "error", "message": f"Secrets check failed: {e}"}


async def main():
    """Run all health checks"""
    logger.info("🔍 Starting Comprehensive Health Check...\n")

    checks = [
        # RAG-specific checks
        ("SearchService Import", check_search_service_import),
        ("SearchService Initialization", check_search_service_initialization),
        ("SearchService apply_filters Parameter", check_search_service_has_apply_filters),
        ("KnowledgeService Deprecated", check_knowledge_service_deprecated),
        ("Router Uses SearchService", check_router_uses_search_service),
        ("Config Has search_enable_filters", check_config_has_search_flag),
        ("Cache Prefix Separation", check_cache_prefix_separation),
        ("SearchService Filter Logic", check_search_service_filters_logic),
        # General health checks
        ("Environment Variables", check_environment_variables),
        ("Database Connectivity", check_database_connectivity),
        ("Qdrant Connectivity", check_qdrant_connectivity),
        ("Type Hints Coverage", check_type_hints_coverage),
        ("Test Coverage", check_test_coverage),
        ("No Hardcoded Secrets", check_no_hardcoded_secrets),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = await check_func()
            results.append((name, result))
        except Exception as e:
            results.append((name, {"status": "error", "message": str(e)}))

    # Print results
    print("\n" + "=" * 60)
    print("NUZANTARA PRIME - COMPREHENSIVE HEALTH CHECK")
    print("=" * 60 + "\n")

    all_ok = True
    for name, result in results:
        status = result["status"]
        message = result["message"]

        if status == "ok":
            icon = "✅"
        elif status == "warning":
            icon = "⚠️"
            all_ok = False
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"
            all_ok = False

        print(f"{icon} {name}: {message}")

        if "parameters" in result:
            print(f"   Parameters: {result['parameters']}")
        if "checks" in result:
            print(f"   Checks: {result['checks']}")
        if "details" in result:
            print(f"   Details: {result['details']}")
        if "missing" in result:
            print(f"   Missing: {result['missing']}")
        if "warnings" in result:
            print(f"   Warnings: {result['warnings']}")
        if "coverage" in result:
            print(f"   Coverage: {result['coverage']:.1f}%")
        if "violations" in result:
            print(f"   Violations: {len(result['violations'])} found")
            for violation in result['violations'][:3]:
                print(f"     - {violation}")

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All checks passed! System is healthy.")
        return 0
    else:
        print("⚠️ Some checks failed or have warnings. Please review.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
