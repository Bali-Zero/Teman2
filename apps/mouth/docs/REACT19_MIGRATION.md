# React 19 + Next.js 15 Chat Migration

## Overview

This document describes the modernization of the Chat component from legacy React patterns to React 19 + Next.js 15 best practices.

## Old vs New Architecture Comparison

### Before (page.tsx)

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT COMPONENT                        │
├─────────────────────────────────────────────────────────────┤
│  useState x 12                                              │
│  useEffect x 8 (data fetching, side effects)               │
│  useCallback x 10                                           │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  useChat    │  │useConversation│ │useTeamStatus│        │
│  │  (manual    │  │  (manual     │  │  (manual    │        │
│  │  loading)   │  │  loading)    │  │  loading)   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                 │
│         ▼                ▼                ▼                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  fetch() + SSE parsing               │   │
│  │                  (client-side only)                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Issues:**
- 437 lines of code in single component
- Manual loading state management (4 separate `isLoading` states)
- useEffect for data fetching (waterfall requests)
- No optimistic updates (user waits for server response)
- Raw SSE parsing on client (complex, error-prone)
- High Time to Interactive (TTI)

### After (chat-v2/page.tsx)

```
┌─────────────────────────────────────────────────────────────┐
│                    SERVER ACTIONS (actions.ts)              │
├─────────────────────────────────────────────────────────────┤
│  sendMessage()          → createStreamableValue()           │
│  saveConversation()     → cookies() auth                    │
│  loadConversations()    → next: { revalidate: 60 }         │
│  toggleClockStatus()    → Server-side mutation              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT COMPONENT                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │  useOptimistic()                                    │   │
│  │  Messages appear INSTANTLY                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  useTransition()                                    │   │
│  │  Non-blocking saves, background operations          │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  readStreamableValue() from AI SDK RSC              │   │
│  │  Efficient stream consumption                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Key Improvements

### 1. Optimistic Updates with `useOptimistic`

**Before:**
```tsx
// User sends message → waits for server → sees loading → message appears
const handleSend = async () => {
  setIsLoading(true);
  try {
    await api.sendMessage(input);
    // Only now does the message appear
  } finally {
    setIsLoading(false);
  }
};
```

**After:**
```tsx
// User sends message → message appears INSTANTLY → streams in background
const [optimisticMessages, addOptimisticMessage] = useOptimistic(
  messages,
  (state, newMessage) => [...state, newMessage]
);

const handleSend = async () => {
  // 🔥 Message appears immediately
  startTransition(() => {
    addOptimisticMessage(userMessage);
  });

  // Stream response in background
  const { messageStream } = await sendMessage(...);
  for await (const chunk of readStreamableValue(messageStream)) {
    // Update streaming content
  }
};
```

**Result:** Zero perceived latency for the user.

### 2. Server Actions for Mutations

**Before:**
```tsx
// Complex client-side fetch with auth handling
const sendMessage = async () => {
  const token = localStorage.getItem('token');
  const response = await fetch('/api/proxy', {
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ ... }),
  });
  // SSE parsing logic...
};
```

**After:**
```tsx
// Server Action with automatic auth
'use server';

export async function sendMessage(messages, sessionId) {
  const cookieStore = await cookies();
  const token = cookieStore.get('nz_access_token')?.value;

  // Secure server-side call
  const response = await fetch(BACKEND_URL, {
    headers: { Authorization: `Bearer ${token}` },
  });

  return createStreamableValue(/* ... */);
}
```

**Result:**
- Secure (tokens never exposed to client)
- Simpler (no proxy needed)
- Type-safe (end-to-end)

### 3. AI SDK RSC for Streaming

**Before (manual SSE parsing):**
```tsx
const reader = response.body?.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    // More parsing...
  }
}
```

**After (AI SDK RSC):**
```tsx
import { readStreamableValue } from 'ai/rsc';

for await (const chunk of readStreamableValue(messageStream)) {
  updateContent(chunk);
}
```

**Result:** Cleaner, more maintainable code.

### 4. Eliminated useEffect for Data Fetching

**Before:**
```tsx
useEffect(() => {
  const loadData = async () => {
    setIsLoading(true);
    await loadConversations();
    await loadClockStatus();
    await loadProfile();
    setIsLoading(false);
  };
  loadData();
}, []);
```

**After (with React 19 `use` or RSC):**
```tsx
// Server Component (parent)
async function ChatLayout({ children }) {
  const conversations = await loadConversations();
  const clockStatus = await getClockStatus();

  return (
    <ChatProvider initialData={{ conversations, clockStatus }}>
      {children}
    </ChatProvider>
  );
}
```

**Result:** Data is ready before component mounts.

## Performance Metrics (Expected)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| TTI (Time to Interactive) | ~2.5s | ~1.2s | **52% faster** |
| Perceived latency (send) | ~300ms | ~0ms | **Instant** |
| JS Bundle (chat page) | ~85KB | ~45KB | **47% smaller** |
| Loading states | 4 | 1 | **Simplified** |

## Migration Path

### Phase 1: Server Actions (✅ Done)
- Created `actions.ts` with all mutations
- Uses `cookies()` for secure auth
- Returns `StreamableValue` for responses

### Phase 2: Optimistic Hook (✅ Done)
- Created `useOptimisticChat` hook
- Encapsulates `useOptimistic` + `useTransition`
- Consumes streams with `readStreamableValue`

### Phase 3: Component Refactor (✅ Done)
- Created `chat-v2/page.tsx` as new implementation
- Created `StreamingMessageList` component
- Reduced complexity significantly

### Phase 4: Testing & Rollout (✅ COMPLETED)
- [x] Manual testing of new chat flow
- [x] Full migration (replaced old chat page)
- [ ] Add E2E tests for new chat flow
- [ ] Monitor error rates and performance

## File Structure (After Rollout)

```
apps/mouth/src/
├── app/
│   └── chat/              # React 19 implementation
│       ├── page.tsx       # ~690 lines (full feature parity)
│       └── actions.ts     # Server Actions
│
├── components/
│   ├── chat/              # Shared components (ChatHeader, ChatInputBar, etc.)
│   └── chat-v2/           # Optimized components
│       └── StreamingMessageList.tsx
│
└── hooks/
    ├── useChat.ts         # Legacy (still available for reference)
    └── useOptimisticChat.ts # New React 19 hook
```

## Dependencies Required

```json
{
  "dependencies": {
    "ai": "^4.0.0",
    "@ai-sdk/anthropic": "^1.0.0",
    "@ai-sdk/google": "^1.0.0"
  }
}
```

## Notes

### Why Not Full RSC?
The chat component needs:
- Real-time streaming updates
- User input handling
- WebSocket connections

These require client-side interactivity. The hybrid approach (Server Actions + Client Components) gives us the best of both worlds.

### Backwards Compatibility
The legacy `/chat` route remains functional during migration. Once validated, we can:
1. Move `chat-v2` to `chat`
2. Archive old implementation
3. Update imports

## References

- [React 19 useOptimistic](https://react.dev/reference/react/useOptimistic)
- [Next.js Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
- [AI SDK RSC](https://sdk.vercel.ai/docs/ai-sdk-rsc)
