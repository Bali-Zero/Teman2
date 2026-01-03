# Circular Imports Prevention Guide

## Background

On 2026-01-03, a production crash was caused by circular imports in `services/routing/__init__.py` and `services/oracle/__init__.py`. This document provides guidelines to prevent similar issues.

## Root Cause

Python evaluates `__init__.py` files at import time. If `ModuleA` imports from `ModuleB` while `ModuleB.__init__` is still being evaluated (because it's importing `ModuleA`), you get:

```
ImportError: cannot import name 'X' from partially initialized module 'Y'
(most likely due to a circular import)
```

## Prevention Patterns

### Pattern 1: Import Order (Most Common Fix)

In `__init__.py` files, always import **sub-services FIRST**, then main services:

```python
# services/routing/__init__.py

# ✅ CORRECT: Sub-services first
from .confidence_calculator import ConfidenceCalculatorService  # sub-service
from .routing_stats import RoutingStatsService                  # sub-service

# Main services AFTER all sub-services are loaded
from .query_router import QueryRouter  # main (may import from sub-services)
```

```python
# ❌ WRONG: Main service imports before sub-services are defined
from .query_router import QueryRouter  # This will fail if it imports RoutingStatsService
from .routing_stats import RoutingStatsService
```

### Pattern 2: Lazy Imports (For Complex Dependencies)

Use `__getattr__` for modules that cause circular imports:

```python
# services/memory/__init__.py

# Eager imports - no circular dependencies
from .models import MemoryFact, MemoryContext
from .episodic_memory_service import EpisodicMemoryService

# Lazy imports - orchestrator imports agents which causes circular imports
_LAZY_IMPORTS = {
    "MemoryOrchestrator": ".orchestrator",
}

_loaded_lazy = {}

def __getattr__(name: str):
    """Lazy import handler."""
    if name in _LAZY_IMPORTS:
        if name not in _loaded_lazy:
            import importlib
            module = importlib.import_module(_LAZY_IMPORTS[name], package=__name__)
            _loaded_lazy[name] = getattr(module, name)
        return _loaded_lazy[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Pattern 3: Local Imports (Inside Functions)

For rarely-used imports that cause cycles:

```python
def some_function():
    # Import only when needed
    from services.heavy_module import HeavyClass
    return HeavyClass()
```

## Modules Using Each Pattern

### Pattern 1 (Import Order)
- `services/routing/__init__.py`
- `services/oracle/__init__.py`
- `services/analytics/__init__.py`

### Pattern 2 (Lazy Imports)
- `services/memory/__init__.py` - `MemoryOrchestrator`
- `services/misc/__init__.py` - `FollowupService`, `GoldenAnswerService`, etc.

## Testing for Circular Imports

Before committing changes to `__init__.py` files, test the import:

```bash
cd apps/backend-rag
python -c "from services.YOUR_MODULE import *"
```

If it fails with `ImportError: cannot import name...partially initialized`, you have a circular import.

## Quick Diagnostic

```bash
# Find all __init__.py files in services
find backend/services -name "__init__.py" -exec grep -l "from \." {} \;

# Check import order in a specific module
python -c "import ast; print([n.module for n in ast.parse(open('backend/services/routing/__init__.py').read()).body if isinstance(n, ast.ImportFrom)])"
```

## Fixes Applied (2026-01-03)

| File | Issue | Fix |
|------|-------|-----|
| `services/routing/__init__.py` | `QueryRouter` imported before `RoutingStatsService` | Reordered imports |
| `services/oracle/__init__.py` | `OracleService` imported before `ReasoningEngineService` | Reordered imports |

---

Last updated: 2026-01-03
