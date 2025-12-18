# 🤖 NUZANTARA PRIME - Automation Scripts

This directory contains automation scripts for code quality, testing, and development workflows.

## 📋 Available Scripts

### 1. `test_generator.py` - Automated Test Generation

Generates pytest-compatible test files for Python functions and API endpoints.

**Usage:**
```bash
# Generate tests for a specific file
python apps/backend-rag/scripts/test_generator.py apps/backend-rag/backend/app/modules/knowledge/service.py

# Specify output directory
python apps/backend-rag/scripts/test_generator.py apps/backend-rag/backend/app/routers/health.py --output tests/unit/
```

**Features:**
- Automatically detects functions and classes
- Identifies async functions and API endpoints
- Generates test structure mirroring source code
- Creates TODO comments for manual completion
- Follows project testing standards

**Example Output:**
```python
"""
Auto-generated test file for service.py
"""

import pytest
from app.modules.knowledge.service import *

class TestKnowledgeService:
    def test_search_success(self):
        """Test search success case"""
        # TODO: Implement test
        pass
```

---

### 2. `refactor_helper.py` - Refactoring Assistant

Analyzes code for refactoring opportunities and code quality issues.

**Usage:**
```bash
# Analyze a file
python apps/backend-rag/scripts/refactor_helper.py apps/backend-rag/backend/app/modules/knowledge/service.py

# Analyze a directory
python apps/backend-rag/scripts/refactor_helper.py apps/backend-rag/backend/app/modules/

# Save report to file
python apps/backend-rag/scripts/refactor_helper.py apps/backend-rag/backend/app/modules/ --output refactoring_report.txt
```

**Features:**
- Finds duplicate code patterns
- Identifies missing type hints
- Detects inconsistent error handling
- Finds hardcoded values (URLs, magic numbers)
- Locates print() statements that should use logger

**Example Output:**
```
======================================================================
NUZANTARA PRIME - REFACTORING ANALYSIS REPORT
======================================================================

🔍 DUPLICATE CODE (3 found):
  - service.py:45 - process_data
    Duplicate of: utils.py:120 - process_data

📝 MISSING TYPE HINTS (12 found):
  - service.py:23 - search (missing: return type, parameter types)

⚠️  INCONSISTENT ERROR HANDLING (5 found):
  - service.py:67 - fetch_data: Missing error handling
```

---

### 3. `health_check.py` - Comprehensive Health Check

Performs comprehensive system health checks including connectivity, code quality, and configuration.

**Usage:**
```bash
# Run all health checks
python apps/backend-rag/scripts/health_check.py
```

**Checks Performed:**
- ✅ Environment variables validation
- ✅ Database connectivity (PostgreSQL)
- ✅ Qdrant vector database connectivity
- ✅ Type hints coverage
- ✅ Test coverage analysis
- ✅ Hardcoded secrets detection
- ✅ RAG-specific checks (SearchService, filters, etc.)

**Example Output:**
```
============================================================
NUZANTARA PRIME - COMPREHENSIVE HEALTH CHECK
============================================================

✅ Environment Variables: All critical environment variables are set
✅ Database Connectivity: Database connection successful
✅ Qdrant Connectivity: Qdrant connection successful (https://qdrant.cloud)
⚠️  Type Hints Coverage: Type hints coverage: 65.2% (234/359 functions)
✅ Test Coverage: Test coverage: 85.0% (17/20 modules)
✅ No Hardcoded Secrets: No hardcoded secrets detected
```

---

### 4. `create_module.py` - Module Template Generator

Creates a new module with complete structure following project standards.

**Usage:**
```bash
# Create a new module
python apps/backend-rag/scripts/create_module.py mymodule
```

**Generated Structure:**
```
apps/backend-rag/backend/app/modules/mymodule/
├── __init__.py          # Module exports
├── models.py            # SQLModel models
├── service.py           # Business logic
└── router.py            # FastAPI endpoints

tests/modules/mymodule/
├── test_models.py       # Model tests
├── test_service.py      # Service tests
└── test_router.py       # API endpoint tests
```

**Features:**
- Complete CRUD operations template
- Type hints everywhere
- Error handling with logging
- Docstrings for all functions
- Test files with pytest fixtures
- FastAPI router with dependency injection

**Next Steps After Generation:**
1. Review and customize `models.py`
2. Implement service methods
3. Complete test implementations
4. Register router in `main_cloud.py`
5. Run tests: `pytest tests/modules/mymodule/`

---

## 🔄 Integration with `.cursorrules`

All scripts are designed to work with the automated TDD protocol defined in `.cursorrules`:

- **Test Generation**: Automatically called when creating new functions/endpoints
- **Code Review**: `refactor_helper.py` findings are checked before marking tasks complete
- **Health Checks**: Run before deployment to ensure system health
- **Module Creation**: Ensures new modules follow project standards

---

## 📚 Best Practices

### Test Generation
1. Always review generated tests
2. Complete TODO sections
3. Add edge cases and error scenarios
4. Run tests: `pytest tests/modules/<module>/`

### Refactoring
1. Run `refactor_helper.py` before major changes
2. Address high-priority issues first (security, error handling)
3. Use incremental refactoring approach
4. Run tests after each refactoring step

### Health Checks
1. Run before committing code
2. Fix critical issues immediately
3. Address warnings in next sprint
4. Use in CI/CD pipeline

### Module Creation
1. Use descriptive module names (lowercase, no spaces)
2. Follow the generated structure
3. Implement all CRUD operations
4. Write comprehensive tests

---

## 🚀 Quick Start

```bash
# 1. Generate tests for a new service
python apps/backend-rag/scripts/test_generator.py apps/backend-rag/backend/app/modules/knowledge/service.py

# 2. Check code quality
python apps/backend-rag/scripts/refactor_helper.py apps/backend-rag/backend/app/modules/

# 3. Run health checks
python apps/backend-rag/scripts/health_check.py

# 4. Create a new module
python apps/backend-rag/scripts/create_module.py analytics
```

---

## 📝 Notes

- All scripts require Python 3.11+
- Scripts automatically add backend to Python path
- Output is formatted for easy reading
- Scripts follow project coding standards (type hints, error handling, logging)

