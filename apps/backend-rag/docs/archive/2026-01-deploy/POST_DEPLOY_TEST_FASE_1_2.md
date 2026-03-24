# Post-Deploy Testing Guide: FASE 1 + 2

**Date:** 2026-01-17
**Deploy:** Backend v1553, Frontend TBD
**Features:** WebApp fixes + WhatsApp/Telegram parity

---

## Test Summary

### ✅ Backend Deployed

- **App:** nuzantara-rag
- **Deployment:** Successful (2 machines healthy)
- **URL:** https://nuzantara-rag.fly.dev
- **Features:** FASE 2.1, 2.2, 2.3 deployed

### ⏳ Frontend Pending

- **App:** nuzantara-mouth (Vercel)
- **Status:** Local commit ready, push blocked by pre-existing test failures
- **Features:** FASE 1.2, 1.3 ready to deploy

---

## FASE 2 Backend Tests (Production Ready)

### 2.1: WhatsApp Status Updates (10s intervals)

**Test Steps:**

1. Send WhatsApp message to business number: `+62 XXX` (configured in Fly secrets)
2. **Expected behavior:**
   - User receives status update every ~10 seconds:
     - "🔍 Processing..."
     - "📚 Searching..."
     - "🧠 Analyzing..."
   - Final response arrives within 45 seconds
   - User sees progress throughout the wait

**Verification:**

```bash
# Check logs for status updates
fly logs -a nuzantara-rag | grep "FASE 2.1"

# Look for:
# ✅ [FASE 2.1] WhatsApp status update #1 sent: 🔍 Processing... (elapsed: 10.0s)
# ✅ [FASE 2.1] WhatsApp status update #2 sent: 📚 Searching... (elapsed: 20.1s)
```

**Success Criteria:**

- [ ] Status updates sent every 10± seconds
- [ ] Correct emoji for each phase
- [ ] User reports improved UX (knows system is working)

---

### 2.2: WhatsApp Timeout (45s)

**Test Steps:**

1. Trigger a complex query that takes >45 seconds (e.g., "Explain all Indonesia visa types in detail")
2. **Expected behavior:**
   - Status updates sent up to ~40 seconds
   - At 45 seconds, user receives: "⏱️ Mi dispiace, la richiesta sta richiedendo troppo tempo. Riprova o scrivi /human per parlare con Zero."
   - No infinite waiting

**Verification:**

```bash
# Check logs for timeout
fly logs -a nuzantara-rag | grep "FASE 2.2"

# Look for:
# ⏱️ [FASE 2.2] WhatsApp query TIMEOUT after 45.2s from +62XXX
# Extra fields: {"status_updates_sent": 4, "phases_seen": [...]}
```

**Success Criteria:**

- [ ] Query times out at exactly 45 seconds
- [ ] Timeout message sent to user
- [ ] Logs show timeout reason and elapsed time
- [ ] Timeout rate <5% (check metrics after 24h)

---

### 2.3: Telegram Markdown Fallback

**Test Steps:**

1. Send Telegram message with **problematic markdown** (special characters):
   - "What's the price? (USD $100.50 - 20% off!)"
   - "PT PMA requirements: Step 1 → Step 2 → Step 3"
2. **Expected behavior:**
   - Strategy 1 (MarkdownV2): May fail due to special chars
   - Strategy 2 (HTML): Fallback with `<b>`, `<i>`, `<a>` tags
   - Strategy 3 (Plain text): Always succeeds (no formatting)
   - Message ALWAYS delivered (no 400 errors)

**Verification:**

```bash
# Check logs for fallback strategy
fly logs -a nuzantara-rag | grep "Telegram message sent"

# Look for one of:
# ✅ Telegram message sent with MarkdownV2 to 123456
# ✅ Telegram message sent with HTML to 123456
# ✅ Telegram message sent with plain text to 123456
```

**Success Criteria:**

- [ ] All messages delivered (no 400 errors)
- [ ] Fallback strategy logged (MarkdownV2 → HTML → Plain)
- [ ] Formatting preserved when possible
- [ ] <1% all-strategies-fail rate (check after 24h)

---

## FASE 1 Frontend Tests (Pending Deploy)

### 1.2: ImageGenModal State Management

**Test Steps:**

1. Open webapp: https://www.balizero.com/chat
2. Login as `zero@balizero.com`
3. Click ✨ sparkles icon in chat input bar
4. **Expected behavior:**
   - Modal opens with "Genera Immagine" title
   - Can type prompt
   - Can close and reopen multiple times
   - State persists during conversation

**Success Criteria:**

- [ ] Modal opens on sparkles click
- [ ] Modal closes on X button
- [ ] Can generate images via modal
- [ ] No console errors about `imageModalOpen`

---

### 1.3: Session ID with UUID v4

**Test Steps:**

1. Open webapp in **incognito window**
2. Open browser DevTools → Console
3. Type: `localStorage.getItem('sessionId')`
4. **Expected format:** `session_XXXXXXXX-XXXX-4XXX-YXXX-XXXXXXXXXXXX` (UUID v4)
5. Refresh page
6. Check sessionId again → should be **different** (new session)

**Verification:**

```bash
# Check backend logs for session ID format
fly logs -a nuzantara-rag | grep "init_session"

# Look for:
# ℹ️ Session ID generated with UUID v4 [metadata: {"sessionIdFormat":"uuid_v4","length":44}]
```

**Success Criteria:**

- [ ] Session IDs follow UUID v4 format
- [ ] No collisions (run 100+ concurrent tests)
- [ ] Logs confirm UUID v4 generation
- [ ] Session IDs are unique across multiple tabs

---

## Integration Tests (Cross-Channel)

### Unified Session Test

**Test Steps:**

1. User registers on webapp with phone number verification
2. User sends message on **webapp**
3. User sends message on **WhatsApp** (same phone)
4. User sends message on **Telegram** (linked account)
5. Check webapp conversation history

**Expected Behavior:**

- All 3 messages appear in **one unified conversation**
- Session ID format: `unified_session_{user_id}` (not channel-specific)
- Conversation context preserved across channels

**Success Criteria:**

- [ ] Webapp shows messages from all 3 channels
- [ ] Session ID shared across channels
- [ ] Conversation context flows correctly
- [ ] No duplicate messages

---

## Logging Verification

### Check Structured Logs (FASE 1)

```bash
# Frontend logging (browser console)
# Open DevTools → Console → Filter for "Session ID generated"
# Should see:
# ℹ️ 07:20:00 [INFO] Session ID generated with UUID v4
#   [component: "useChatPage", action: "init_session", metadata: {...}]

# Backend logging (Fly.io)
fly logs -a nuzantara-rag | grep "FASE"

# Should see:
# 🚀 [FASE 2.1] Processing business query with status updates
# ✅ [FASE 2.1] WhatsApp status update #1 sent: 🔍 Processing...
# ⏱️ [FASE 2.2] WhatsApp query TIMEOUT after 45.2s
# ✅ [FASE 2] WhatsApp RAG response completed (duration: 35.0s, updates: 3)
```

---

## Metrics Queries (After 24h)

### Query 1: WhatsApp Performance

```sql
SELECT
    AVG(total_duration_seconds) as avg_duration,
    AVG(status_updates_sent) as avg_updates,
    COUNT(*) as total_queries
FROM logs
WHERE feature = 'whatsapp_complete'
AND created_at > NOW() - INTERVAL '24 hours';
```

**Expected:**

- avg_duration: 25-35 seconds
- avg_updates: 2-4 updates per query
- timeout_rate: <5%

---

### Query 2: Timeout Rate

```sql
SELECT
    COUNT(*) FILTER (WHERE timed_out = true) as timeouts,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE timed_out = true) / COUNT(*), 2) as timeout_rate_percent
FROM logs
WHERE feature IN ('whatsapp_complete', 'whatsapp_timeout_handling')
AND created_at > NOW() - INTERVAL '7 days';
```

**Target:** <5% timeout rate

---

### Query 3: Telegram Fallback Strategy

```sql
SELECT
    COUNT(*) FILTER (WHERE message LIKE '%MarkdownV2%') as markdownv2_success,
    COUNT(*) FILTER (WHERE message LIKE '%HTML%') as html_fallback,
    COUNT(*) FILTER (WHERE message LIKE '%plain text%') as plain_fallback,
    COUNT(*) FILTER (WHERE message LIKE '%failed%') as all_failed
FROM logs
WHERE component = 'telegram'
AND created_at > NOW() - INTERVAL '24 hours';
```

**Expected:**

- markdownv2_success: 70-80%
- html_fallback: 15-25%
- plain_fallback: 1-5%
- all_failed: <1%

---

## Deployment Checklist

### Backend (✅ COMPLETED)

- [x] FASE 2.1 code deployed (status updates)
- [x] FASE 2.2 code deployed (timeout handling)
- [x] FASE 2.3 code deployed (markdown fallback)
- [x] Logging added to all critical paths
- [x] Backend healthy (2/2 machines)
- [ ] Verify logs in production (run tests above)

### Frontend (⏳ PENDING)

- [x] FASE 1.2 code committed locally (ImageGenModal)
- [x] FASE 1.3 code committed locally (UUID v4)
- [x] Logging added to frontend
- [ ] Push to GitHub (blocked by pre-existing test failures)
- [ ] Deploy to Vercel (automatic after push)
- [ ] Verify in production

---

## Known Issues

### Local Test Failures (Not Blocking)

**Issue:** 22 pre-existing test failures in unrelated components:

- `useChatTTS.test.ts` - 4 failures (TTS error handling)
- `useChatInput.test.ts` - 3 failures (toast callbacks)
- `StatsCard.memo.test.tsx` - 1 failure (React.memo)

**Impact:** Blocks git push due to Husky pre-push hook

**Workaround Options:**

1. Fix 22 failing tests (unrelated to FASE 1+2)
2. Push frontend with `--no-verify` (bypass hook)
3. Manually deploy frontend to Vercel

**Status:** Backend deployed successfully, frontend commit ready locally

---

## Next Steps

1. **Deploy Frontend:**
   - Option A: Fix pre-existing test failures
   - Option B: Push with `--no-verify` flag
   - Option C: Manual Vercel deployment

2. **Run End-to-End Tests:**
   - WhatsApp status updates (real phone)
   - Telegram markdown fallback (real messages)
   - WebApp image generation modal
   - UUID v4 session IDs

3. **Monitor Metrics (24h):**
   - WhatsApp timeout rate (<5% target)
   - Telegram fallback strategy distribution
   - Frontend session ID collisions (should be 0)

4. **Update Documentation:**
   - Mark checklist items as complete
   - Document any issues found
   - Update FASE_1_2_LOGGING_METRICS.md

---

## Rollback Plan

If critical issues found in production:

**Backend Rollback:**

```bash
# Revert to previous release
fly releases -a nuzantara-rag
fly deploy --image registry.fly.io/nuzantara-rag:deployment-PREVIOUS_ID
```

**Frontend Rollback:**

```bash
# Vercel automatic rollback via dashboard
# Or git revert + push
git revert HEAD
git push origin main
```

---

**End of Post-Deploy Test Guide**
