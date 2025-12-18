# ZANTARA OPTIMIZATION PATCHES

Apply these patches to `apps/webapp-next` to ensure Zantara is 100% Identity-Aware, Robust, and Natural.

---

## PATCH 1: IDENTITY & PERSONA FIX (Critical)
**File:** `apps/webapp-next/src/lib/api/chat.ts`
**Issue:** User ID was hardcoded to `"web_user"`, preventing the backend from recognizing the user (e.g., Anton) and activating the "Jaksel" persona.
**Fix:** Retrieve the real user ID/Email from `authAPI` or localStorage.

```typescript
// apps/webapp-next/src/lib/api/chat.ts

// [IMPORT] Add this import at the top
import { authAPI } from '@/lib/api/auth';

// [MODIFY] Inside streamChat function, around line 70
// OLD:
// user_id: 'web_user',

// NEW:
const user = authAPI.getUser();
const userId = user?.email || 'web_user'; // Use email as ID for Jaksel mapping

// ... inside body:
user_id: userId,
```

---

## PATCH 2: ROBUSTNESS & TIMEOUT (Critical)
**File:** `apps/webapp-next/src/lib/api/chat.ts`
**Issue:** Default timeout is 60s. Complex RAG queries or "Deep Thinking" chains can take longer.
**Fix:** Increase timeout to 180s (3 minutes).

```typescript
// apps/webapp-next/src/lib/api/chat.ts

// [MODIFY] Around line 62
// OLD:
// const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

// NEW:
const timeoutId = setTimeout(() => controller.abort(), 180000); // 180 second timeout (3 mins)
```

---

## PATCH 3: CONTEXT & MEMORY OPTIMIZATION
**File:** `apps/webapp-next/src/app/chat/page.tsx`
**Issue:** Sending 200 messages (100 turns) is good, but we should ensure we don't cut off the *system prompt* or essential context if the backend doesn't handle it. (Note: Backend usually handles truncation, but frontend safety is good).
**Fix:** Ensure we send the *latest* relevant context.

```typescript
// apps/webapp-next/src/app/chat/page.tsx

// [VERIFY] Around line 140
// The current implementation is actually GOOD:
// .slice(-200) // Last 200 messages
//
// [OPTIMIZATION]
// Ensure we don't send 'error' messages back to the context to avoid confusing the AI.
const conversationHistory = messages
  .filter(msg => msg.content !== "Sorry, I encountered an error. Please try again.") // Filter errors
  .slice(-200)
  .map(msg => ({
    role: msg.role,
    content: msg.content
  }))
```

---

## PATCH 4: NATURALNESS & UI UX
**File:** `apps/webapp-next/src/app/chat/page.tsx`
**Issue:** "Thinking" state is static.
**Fix:** Add a random "natural" delay or "typing" effect if the response is too fast (optional), but more importantly, handle the *Empty* state better.

```typescript
// apps/webapp-next/src/app/chat/page.tsx

// [MODIFY] Empty state message (around line 501)
// Make it more inviting and less "system-like".
// OLD: "Semoga kehadiran kami membawa cahaya..."
// NEW: (Keep it, it's poetic and fits the Bali Zero vibe. Just ensure it renders perfectly.)
```

---

## PATCH 5: MULTILINGUAL HANDLING
**File:** `apps/webapp-next/src/lib/api/chat.ts`
**Issue:** We want to ensure the backend knows the user's locale if possible (though RAG usually detects language).
**Fix:** Pass `client_locale` in the metadata if the backend supports it.

```typescript
// apps/webapp-next/src/lib/api/chat.ts

// [ADD] Inside body object
body: JSON.stringify({
  message: message,
  user_id: userId,
  conversation_history: conversationHistory || [],
  metadata: {
    client_locale: navigator.language, // e.g., "id-ID", "en-US"
    client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
  }
}),
```
