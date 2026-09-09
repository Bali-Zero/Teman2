# Code style, patterns and common pitfalls

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

## 9. Code Style & Patterns

### Python (Backend)

```python
# Good: Async, typed, clean logging, persistent client
from typing import Optional
from backend.core.logging import logger

async def fetch_kbli_data(code: str) -> Optional[dict]:
    """Fetch KBLI data from Qdrant."""
    try:
        result = await qdrant.search(
            collection_name="kbli",
            query_vector=embedding,
            limit=1
        )
        logger.info(f"KBLI search successful: {code}")
        return result[0] if result else None
    except Exception as e:
        logger.error(f"KBLI search failed: {code}", exc_info=True)
        raise
```

### TypeScript (Frontend)

```typescript
// Good: Type-safe, error handling
interface KBLIResponse {
  code: string;
  title_en: string;
  description: string;
}

async function fetchKBLI(code: string): Promise<KBLIResponse | null> {
  try {
    const response = await fetch(`/api/kbli/${code}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("KBLI fetch failed:", error);
    return null;
  }
}
```

## 10. Common Pitfalls

❌ **AVOID:**

- Running Python without virtualenv
- Using `requests` instead of `httpx`
- Nested payload structures in Qdrant
- Hardcoded prices or visa info
- `print()` debugging in production code
- Relative imports
- Blocking I/O operations
- Missing type hints

✅ **DO:**

- Always activate venv first
- Use `httpx` for all HTTP calls
- Flat payloads in Qdrant
- `PricingTool` for all pricing
- `logger` for all logging
- Absolute imports
- Async/await everywhere
- Full type annotations
