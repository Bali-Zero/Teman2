# Code Cleanup Report

**Generated:** 2025-12-15
**Author:** Claude Opus 4.5
**Scope:** apps/mouth (Frontend) + apps/backend-rag (Backend)

---

## Executive Summary

Analisi completa del codebase per identificare bug, errori, codice duplicato/inutile.

| Category | Frontend | Backend | Total |
|----------|----------|---------|-------|
| Console statements to review | 58 | 30+ | 88+ |
| TypeScript `any` types | 3 | N/A | 3 |
| localStorage usages (security) | 14 | N/A | 14 |
| TODO/FIXME comments | 6 | 8 | 14 |
| Empty `pass` statements | N/A | 30+ | 30+ |
| Magic numbers | 20+ | N/A | 20+ |

---

## 1. Console Statements to Remove/Replace

### Frontend (apps/mouth/src)

**Critical - Remove in production:**

| File | Line | Type | Action |
|------|------|------|--------|
| `hooks/useConversations.ts` | 17, 31, 41 | `console.error` | Replace with error boundary |
| `hooks/useWebSocket.ts` | 76, 119, 124, 175 | Mixed | Replace with monitoring service |
| `hooks/useTeamStatus.ts` | 14, 39 | `console.error` | Replace with toast notification |
| `hooks/useChat.ts` | 116, 125, 214, 250, 263 | `console.error` | User feedback needed |
| `app/chat/page.tsx` | 108 | `console.error` | Silent fail OK |
| `app/agents/page.tsx` | 55, 104, 116, 163 | Mixed | Remove debug, keep errors |
| `app/admin/page.tsx` | 65, 74, 83, 129 | `console.error` | Replace with UI feedback |
| `lib/api.ts` | 471 | `console.warn` | OK to keep |

**Keep (Monitoring/Debug tools):**
- `lib/monitoring.ts` - Intended for dev monitoring
- `lib/monitoring-dashboard.ts` - Dev dashboard tool
- `components/MonitoringWidget.tsx` - Dev tool

### Backend (apps/backend-rag/backend)

**Critical - Replace with logging:**

| File | Line | Pattern | Action |
|------|------|---------|--------|
| `services/gemini_service.py` | 307-321 | `print()` in test | Move to __main__ guard |
| `services/deepseek_client.py` | 186-206 | `print()` in test | Move to __main__ guard |
| `services/openrouter_client.py` | 323-350 | `print()` in test | Move to __main__ guard |

---

## 2. TypeScript Type Issues

### `any` types found:

```typescript
// apps/mouth/src/types/pricing.ts:13
[key: string]: any;  // Should use specific type

// apps/mouth/src/components/chat/MessageBubble.test.tsx:13
CitationCard: ({ sources }: { sources: any[] }) => ...  // Test mock - OK

// apps/mouth/src/app/agents/__tests__/page.test.tsx:29
div: ({ children, ...props }: any) => ...  // Test mock - OK
```

**Action:** Fix `pricing.ts` - define proper interface.

---

## 3. localStorage Security Issues

All 14 usages need review per security strategy:

| File | Usage | Risk | Migration |
|------|-------|------|-----------|
| `lib/api.ts:148` | `auth_token` read | HIGH | httpOnly cookie |
| `lib/api.ts:149` | `user_profile` read | MEDIUM | Keep (non-sensitive) |
| `lib/api.ts:169` | `auth_token` write | HIGH | httpOnly cookie |
| `lib/api.ts:176` | `user_profile` write | MEDIUM | Keep (non-sensitive) |
| `lib/api.ts:184-185` | Token/profile clear | HIGH | Cookie clear |
| `app/chat/page.tsx:130,246` | `user_avatar` | HIGH | Upload to CDN |
| `FeedbackWidget.tsx:32,57,59,62,79` | Feedback state | LOW | OK to keep |
| `MonitoringWidget.tsx:26` | Widget toggle | LOW | OK to keep |

---

## 4. TODO/FIXME Comments

### Frontend:

```typescript
// apps/mouth/src/components/ui/button.test.tsx:8,12
// TODO: Add assertions
// TODO: Add more test cases

// apps/mouth/src/components/layout/Sidebar.test.tsx:24
// TODO: Add more test cases

// apps/mouth/src/components/chat/ThinkingIndicator.test.tsx:8,12
// TODO: Add assertions

// apps/mouth/src/app/agents/page.tsx:52
// TODO: Use actual backend response when API returns proper agent status
```

### Backend:

```python
# services/intelligent_router.py:37
web_search_client=None,  # TODO: Inject Web Search

# core/chunker.py:232
# TODO: Implement page-aware chunking

# services/collective_memory_workflow.py:61,88,147,157
# Multiple TODOs for NER and memory integration

# services/cross_oracle_synthesis_service.py:496
# TODO: Implement golden answer cache check

# app/routers/intel.py:184
# TODO: Implement Qdrant filter support
```

---

## 5. Magic Numbers to Extract

### Frontend Constants Needed:

```typescript
// apps/mouth/src/constants/config.ts (NEW FILE)
export const CONFIG = {
  // Timeouts
  TOAST_DURATION_MS: 3000,
  AUTO_REFRESH_INTERVAL_MS: 30000,
  AGENT_REFRESH_DELAY_MS: 2000,

  // Limits
  MAX_IMAGE_SIZE_BYTES: 2 * 1024 * 1024,  // 2MB
  MAX_IMAGE_DIMENSION: 2048,
  MOBILE_BREAKPOINT_PX: 768,

  // UI
  Z_INDEX_TOAST: 100,
  Z_INDEX_DROPDOWN: 50,
  ANIMATION_DURATION_MS: 300,
  LOGO_SIZE_PX: 120,
} as const;
```

**Current locations:**
- `page.tsx:159` - 3000 (toast duration)
- `page.tsx:185` - 2 * 1024 * 1024 (image size)
- `page.tsx:233` - 2048 (max dimension)
- `page.tsx:270` - 768 (mobile breakpoint)
- `agents/page.tsx:133` - 30000 (refresh interval)
- `agents/page.tsx:160` - 2000 (reload delay)

---

## 6. Duplicate Code Patterns

### Click-Outside Handler (Duplicate):

```typescript
// apps/mouth/src/app/chat/page.tsx:143-154
// Pattern repeated for attachMenu and userMenu

// SOLUTION: Extract to hook
// apps/mouth/src/hooks/useClickOutside.ts
export function useClickOutside(
  ref: RefObject<HTMLElement>,
  handler: () => void
) {
  useEffect(() => {
    const listener = (event: MouseEvent | TouchEvent) => {
      if (!ref.current || ref.current.contains(event.target as Node)) return;
      handler();
    };
    document.addEventListener('mousedown', listener);
    document.addEventListener('touchstart', listener);
    return () => {
      document.removeEventListener('mousedown', listener);
      document.removeEventListener('touchstart', listener);
    };
  }, [ref, handler]);
}
```

### Error Handling Pattern (Duplicate):

```typescript
// Multiple hooks have same pattern:
try {
  // ... operation
} catch (error) {
  console.error('Failed to X:', error);
}

// SOLUTION: Create error handling utility
// apps/mouth/src/lib/errorHandler.ts
export function handleError(error: unknown, context: string): void {
  const message = error instanceof Error ? error.message : 'Unknown error';
  // Log to monitoring service
  monitoring.trackError(context, message);
  // Show user feedback if appropriate
}
```

---

## 7. Empty Exception Handlers (Backend)

**Files with `pass` in except blocks:**

| File | Count | Risk |
|------|-------|------|
| `services/tools/definitions.py` | 4 | LOW (abstract methods) |
| `core/legal/structure_parser.py` | 1 | MEDIUM |
| `services/oracle_service.py` | 3 | HIGH |
| `services/autonomous_scheduler.py` | 2 | MEDIUM |
| `services/session_service.py` | 1 | MEDIUM |
| `services/emotional_attunement.py` | 1 | LOW |
| `core/plugins/plugin.py` | 5 | LOW (abstract) |

**Action:** Review `oracle_service.py` - silent failures may hide bugs.

---

## 8. Async/Await Issues

### Fire-and-Forget Pattern:

```typescript
// apps/mouth/src/hooks/useChat.ts:116
api.saveConversation(messagesToSave, sessionId!, metadata).catch(console.error);

// Issue: If save fails, local and remote state diverge
// SOLUTION: Add retry logic or queue for offline support
```

### Missing Error Boundaries:

```typescript
// apps/mouth/src/app/chat/page.tsx:121
await Promise.all([loadConversationList(), loadClockStatus(), loadUserProfile()]);

// Issue: One failure breaks all
// SOLUTION: Use Promise.allSettled (already in strategy doc)
```

---

## 9. Unused Imports Check

Run `npx eslint --rule '@typescript-eslint/no-unused-vars: error'` on:
- `apps/mouth/src/app/chat/page.tsx` - Large component, likely has unused imports
- `apps/mouth/src/components/chat/MessageBubble.tsx` - Many lucide imports

---

## 10. Recommended Cleanup Actions

### Priority 1 (Security):
- [ ] Migrate auth token to httpOnly cookies
- [ ] Remove avatar from localStorage
- [ ] Add CSP headers

### Priority 2 (Code Quality):
- [ ] Extract `useClickOutside` hook
- [ ] Create `constants/config.ts`
- [ ] Replace console.error with proper error handling
- [ ] Fix `pricing.ts` any type

### Priority 3 (Maintenance):
- [ ] Address TODO comments or convert to project issues
- [ ] Add tests for empty test files
- [ ] Review backend `pass` statements in exception handlers

---

## Test Coverage Requirements

### New Tests Needed:

```typescript
// apps/mouth/src/hooks/useClickOutside.test.ts
// apps/mouth/src/lib/errorHandler.test.ts
// apps/mouth/src/constants/config.test.ts (validate values)
```

### Existing Tests to Complete:

```typescript
// apps/mouth/src/components/ui/button.test.tsx - Add assertions
// apps/mouth/src/components/layout/Sidebar.test.tsx - Add cases
// apps/mouth/src/components/chat/ThinkingIndicator.test.tsx - Add assertions
```

---

*Report generated by Claude Opus 4.5 - 2025-12-15*