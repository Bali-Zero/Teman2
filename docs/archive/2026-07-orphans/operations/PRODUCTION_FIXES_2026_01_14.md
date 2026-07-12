# Production Fixes - 2026-01-14

## Summary

This document describes 4 production bugs identified and fixed on 2026-01-14.

| #   | Bug                                           | Severity | Status |
| --- | --------------------------------------------- | -------- | ------ |
| 1   | Clients page virtualization not rendering     | High     | Fixed  |
| 2   | WebSocket RealtimeService connection failures | High     | Fixed  |
| 3   | AUTO CRM UUID serialization error             | Medium   | Fixed  |
| 4   | Pollinations.ai watermarks on article images  | Low      | Fixed  |

---

## Fix 1: Clients Page Virtualization

### Problem

The clients page used `@tanstack/react-virtual` for performance with large lists, but the virtualized list showed 0 height and nothing rendered.

### Root Cause

The CSS property `contain: 'strict'` was applied to the scroll container. This layout isolation requires explicit dimensions, but the container had no explicit height, causing the virtualizer to calculate 0 as the total size.

### Solution

**File:** `apps/mouth/src/app/(workspace)/clients/page.tsx`

1. Removed `contain: 'strict'` CSS property
2. Added `min-h-[400px]` to ensure minimum height
3. Added `useEffect` to force re-measure when parent becomes available

```typescript
// Force re-measure when parent becomes available
useEffect(() => {
  if (parentRef.current) {
    virtualizer.measure();
  }
}, [virtualizer]);

// Container with minimum height
<div
  ref={parentRef}
  className="flex-1 overflow-auto pb-4 min-h-[400px]"
>
```

### Test Coverage

**File:** `apps/mouth/src/components/crm/__tests__/ClientKanban.virtualization.test.tsx`

---

## Fix 2: WebSocket RealtimeService Connection Failures

### Problem

Browser console showed repeated WebSocket errors:

```
WebSocket error
Max reconnection attempts reached
```

### Root Cause

The WebSocket client was attempting to authenticate by passing `userId` and `userName` as query parameters, but the backend expected JWT token authentication via subprotocol.

### Solution

**File:** `apps/mouth/src/lib/realtime.tsx`

1. Retrieve auth token from localStorage (fallback to sessionStorage)
2. Validate JWT token format (3 parts, >50 chars)
3. Pass token via WebSocket subprotocol: `bearer.{token}`
4. Add SSR protection in constructor
5. Prevent infinite reconnect loops when no token available

```typescript
// Get token from storage
const token =
  localStorage.getItem("auth_token") || sessionStorage.getItem("auth_token");

// Validate JWT format
const tokenParts = token.split(".");
if (tokenParts.length !== 3 || token.length < 50) {
  logger.warn("Invalid token format detected");
  return;
}

// Connect with token in subprotocol
this.ws = new WebSocket(wsUrl, [`bearer.${token}`]);
```

### Test Coverage

**File:** `apps/mouth/src/lib/realtime.test.ts`

---

## Fix 3: AUTO CRM UUID Serialization Error

### Problem

Backend error logs showed:

```
TypeError: Object of type UUID is not JSON serializable
```

This occurred when the AI CRM Extractor tried to include existing client data (with asyncpg UUID types) in the extraction prompt.

### Root Cause

`json.dumps()` cannot serialize `uuid.UUID` objects returned by asyncpg. The function was called without a custom encoder.

### Solution

**File:** `apps/backend-rag/backend/services/crm/ai_crm_extractor.py`

Added `AsyncpgJSONEncoder` class that handles:

- `uuid.UUID` → string
- `datetime` → ISO format
- `date` → ISO format

```python
class AsyncpgJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle asyncpg types"""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

# Usage
json.dumps(existing_client_data, indent=2, cls=AsyncpgJSONEncoder)
```

### Test Coverage

**File:** `apps/backend-rag/tests/unit/services/crm/test_ai_crm_extractor.py`

Tests include:

- `test_encode_uuid` - UUID to string conversion
- `test_encode_datetime` - datetime to ISO format
- `test_encode_date` - date to ISO format
- `test_encode_nested_uuids` - nested structures
- `test_encode_mixed_types` - all types together
- `test_extract_from_conversation_with_existing_client_uuid` - integration test

---

## Fix 4: Pollinations.ai Watermarks on Article Images

### Problem

Article images generated via Pollinations.ai API showed watermarks:

```
"NO RATE LIMITS! GET FREE DAILY CREDITS"
```

### Root Cause

The `?nologo=true` parameter on Pollinations.ai URLs was not effective, and the service was adding promotional watermarks.

### Solution

**File:** `apps/mouth/src/components/dashboard/FeaturedArticlesWidget.tsx`

Replaced Pollinations.ai URLs with local static images that already existed in the repository:

```typescript
// Before
imageUrl: 'https://image.pollinations.ai/prompt/...',

// After
imageUrl: '/static/news/dengue-alert.jpg',
imageUrl: '/static/news/perfect-storm-bali.jpg',
```

### Test Coverage

Visual verification only - UI component change.

---

## Deployment

Both frontend and backend were deployed after fixes:

| App      | Deploy Method      | Version |
| -------- | ------------------ | ------- |
| Backend  | `fly deploy --now` | v1576   |
| Frontend | Git push → Vercel  | auto    |

### Verification Commands

```bash
# Backend health
curl -s https://nuzantara-rag.fly.dev/health | jq .status

# Frontend
curl -sI https://balizero.com | head -1
```

---

## Related Files Changed

| File                                                             | Type     | Description                   |
| ---------------------------------------------------------------- | -------- | ----------------------------- |
| `apps/mouth/src/app/(workspace)/clients/page.tsx`                | MODIFIED | Virtualization fix            |
| `apps/mouth/src/lib/api/client.ts`                               | MODIFIED | getUserProfile sync + logging |
| `apps/mouth/src/lib/realtime.tsx`                                | MODIFIED | WebSocket auth                |
| `apps/backend-rag/backend/services/crm/ai_crm_extractor.py`      | MODIFIED | UUID encoder                  |
| `apps/mouth/src/components/dashboard/FeaturedArticlesWidget.tsx` | MODIFIED | Static images                 |

---

## Commit

```
a12f1b95 fix: resolve 4 production bugs
```
