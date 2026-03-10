# Deployment Guide: Conversation Persistence System

**Date**: 2026-02-09  
**Priority**: P0 🔴  
**Status**: Ready for Deployment

---

## 🎯 Overview

This guide covers deploying the conversation persistence system to production, including:

- Backend deployment (Fly.io)
- Frontend integration (Vercel)
- Monitoring setup
- Verification steps

---

## 📋 Pre-Deployment Checklist

### Backend

- [x] ConversationRepository created
- [x] Webhook chat router implemented
- [x] Cleanup cron job integrated
- [x] Router registered in app
- [x] Tests created
- [ ] Environment variables verified
- [ ] Database indexes confirmed

### Frontend

- [ ] WebhookChatApi client created
- [ ] useConversationPersistence hook created
- [ ] Chat component updated
- [ ] Session management implemented
- [ ] Error handling added

---

## 🚀 Step 1: Deploy Backend

### Option A: Automated Deployment

```bash
cd apps/backend-rag/backend
./scripts/deploy_backend.sh
```

### Option B: Manual Deployment

```bash
cd apps/backend-rag

# Deploy to Fly.io
flyctl deploy --app nuzantara-rag --region sin

# Wait for deployment
flyctl status -a nuzantara-rag

# Check health
curl https://nuzantara-rag.fly.dev/api/health
```

### Verify Backend Deployment

```bash
# Test webhook/chat endpoint
curl -X POST https://nuzantara-rag.fly.dev/webhook/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "query": "Test message",
    "session_id": "test-session-123",
    "metadata": {"test": true}
  }'

# Expected response:
# {
#   "answer": "...",
#   "session_id": "test-session-123",
#   "conversation_id": 123,
#   "persisted": true,
#   ...
# }
```

---

## 🎨 Step 2: Update Frontend

### 2.1 Install Dependencies (if needed)

```bash
cd apps/mouth
pnpm install
```

### 2.2 Update Chat Component

Create or update your chat component to use the new system:

```typescript
// Example: src/app/chat/page.tsx or similar
import { useConversationPersistence } from '@/hooks/useConversationPersistence';
import { WebhookChatApi } from '@/lib/api/chat/webhook-chat.api';
import { useApiClient } from '@/hooks/useApiClient';

export function ChatPage() {
  const { sessionId, isLoading, resetSession } = useConversationPersistence();
  const apiClient = useApiClient();
  const webhookChatApi = new WebhookChatApi(apiClient);

  const handleSendMessage = async (message: string) => {
    if (!sessionId) return;

    try {
      const response = await webhookChatApi.sendMessage(
        message,
        sessionId,
        { source: 'webapp' }
      );

      console.log('Conversation ID:', response.conversation_id);
      console.log('Persisted:', response.persisted);

      // Update UI with response.answer
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  // Load conversation history on mount
  useEffect(() => {
    if (!sessionId || isLoading) return;

    webhookChatApi.getHistory(sessionId, 20)
      .then(history => {
        // Restore conversation in UI
        console.log('Loaded history:', history.messages);
      })
      .catch(error => {
        console.error('Failed to load history:', error);
      });
  }, [sessionId, isLoading]);

  return (
    <div>
      {/* Chat UI */}
      <button onClick={resetSession}>New Conversation</button>
    </div>
  );
}
```

### 2.3 Update API Client

Add WebhookChatApi to your API client exports:

```typescript
// src/lib/api/api-client.ts or similar
import { WebhookChatApi } from "./chat/webhook-chat.api";

export class ApiClient {
  // ... existing code ...

  get webhookChat() {
    return new WebhookChatApi(this);
  }
}
```

### 2.4 Build and Test Locally

```bash
cd apps/mouth

# Build
pnpm build

# Test locally
pnpm dev

# Open http://localhost:3000 and test chat
```

---

## 🌐 Step 3: Deploy Frontend

### Option A: Vercel (Recommended)

```bash
cd apps/mouth

# Deploy to Vercel
vercel --prod

# Or push to main branch for auto-deploy
git add .
git commit -m "feat: add conversation persistence system"
git push origin main
```

### Option B: Manual Build

```bash
cd apps/mouth

# Build for production
pnpm build

# Deploy build output to your hosting provider
```

---

## 📊 Step 4: Monitoring & Verification

### 4.1 Backend Monitoring

```bash
# Watch logs in real-time
flyctl logs -a nuzantara-rag

# Check for persistence logs
flyctl logs -a nuzantara-rag | grep "Conversation persisted"

# Check database
flyctl ssh console -a nuzantara-rag
psql $DATABASE_URL -c "SELECT COUNT(*) FROM conversations;"
```

### 4.2 Frontend Monitoring

```bash
# Check Vercel logs
vercel logs

# Monitor browser console for:
# - "Created new session"
# - "Restored session"
# - "Message persisted"
```

### 4.3 End-to-End Test

1. **Open webapp** in browser
2. **Send message**: "What is the capital of France?"
3. **Check console**: Should see "Message persisted: true"
4. **Refresh page** (F5)
5. **Send follow-up**: "What about Germany?"
6. **Verify context**: AI should remember previous question
7. **Check persistence**: Both messages should be in history

### 4.4 Database Verification

```sql
-- Connect to database
psql $DATABASE_URL

-- Check recent conversations
SELECT
    id,
    session_id,
    user_id,
    jsonb_array_length(messages) as message_count,
    created_at
FROM conversations
ORDER BY created_at DESC
LIMIT 10;

-- Check specific session
SELECT
    messages,
    metadata
FROM conversations
WHERE session_id = 'your-session-id';
```

---

## 🔧 Step 5: Configuration

### Backend Environment Variables

Verify these are set in Fly.io:

```bash
# Check secrets
flyctl secrets list -a nuzantara-rag

# Required:
# - DATABASE_URL (PostgreSQL connection string)
# - JWT_SECRET_KEY (for authentication)
# - REDIS_URL (optional, for caching)
```

### Frontend Environment Variables

Verify in Vercel dashboard or `.env.production`:

```bash
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
```

---

## 🐛 Troubleshooting

### Issue: "Message not persisted"

**Check:**

1. Database connection available
2. JWT token valid
3. session_id provided in request

**Debug:**

```bash
# Check backend logs
flyctl logs -a nuzantara-rag | grep "Failed to save conversation"

# Test database connection
flyctl ssh console -a nuzantara-rag
psql $DATABASE_URL -c "SELECT 1"
```

### Issue: "Context not maintained"

**Check:**

1. Same session_id used across requests
2. Conversation history retrieved (check logs)
3. RAG orchestrator receiving history

**Debug:**

```typescript
// Add logging in frontend
console.log("Session ID:", sessionId);
console.log("History loaded:", history.messages.length);
```

### Issue: "Cleanup job not running"

**Check:**

1. AutonomousScheduler started
2. conversation_cleanup_enabled=True
3. Database pool available

**Debug:**

```bash
# Check scheduler logs
flyctl logs -a nuzantara-rag | grep "Conversation cleanup"

# Run manually
flyctl ssh console -a nuzantara-rag
cd /app
python -m backend.jobs.conversation_cleanup
```

---

## 📈 Performance Monitoring

### Key Metrics

Monitor these in production:

1. **Persistence Rate**: Should be ~100%

   ```sql
   SELECT
       COUNT(*) as total_requests,
       COUNT(DISTINCT conversation_id) as persisted
   FROM conversations
   WHERE created_at > NOW() - INTERVAL '1 hour';
   ```

2. **Query Performance**: Should be < 50ms

   ```sql
   EXPLAIN ANALYZE
   SELECT messages FROM conversations
   WHERE session_id = 'test-session'
   ORDER BY created_at DESC LIMIT 1;
   ```

3. **Storage Growth**: Monitor table size
   ```sql
   SELECT pg_size_pretty(pg_total_relation_size('conversations'));
   ```

### Alerts

Set up alerts for:

- Persistence rate drops below 95%
- Query time exceeds 100ms
- Table size exceeds 10GB
- Cleanup job failures

---

## ✅ Post-Deployment Checklist

- [ ] Backend deployed and healthy
- [ ] Frontend deployed and accessible
- [ ] End-to-end test passed
- [ ] Conversation persists after refresh
- [ ] Context maintained across sessions
- [ ] Cleanup job running daily
- [ ] Monitoring dashboards updated
- [ ] Team notified of deployment
- [ ] Documentation updated

---

## 🎉 Success Criteria

✅ **Deployment successful when:**

1. Client sends message → receives response
2. Client refreshes page → conversation persists
3. Client sends follow-up → AI remembers context
4. Database shows conversation records
5. Cleanup job runs without errors
6. Performance metrics within targets

---

## 📞 Support

**Issues?**

- Check logs: `flyctl logs -a nuzantara-rag`
- Run tests: `pytest tests/test_conversation_persistence.py`
- Manual cleanup: `python -m backend.jobs.conversation_cleanup`

**Documentation:**

- Backend: `apps/backend-rag/backend/docs/CONVERSATION_PERSISTENCE.md`
- Implementation: `apps/backend-rag/IMPLEMENTATION_SUMMARY.md`

---

**Deployment Date**: **\*\***\_**\*\***  
**Deployed By**: **\*\***\_**\*\***  
**Verified By**: **\*\***\_**\*\***
