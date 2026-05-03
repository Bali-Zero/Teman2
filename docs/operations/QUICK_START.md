# Quick Start: Deploy Conversation Persistence

**Ready to deploy in 3 steps** 🚀

---

## Step 1: Deploy Backend (5 minutes)

```bash
cd apps/backend-rag

# Deploy to Fly.io
flyctl deploy --app nuzantara-rag --region sin

# Verify deployment
curl https://nuzantara-rag.fly.dev/api/health
```

**Expected**: Health check returns `{"status": "healthy"}`

---

## Step 2: Update Frontend (10 minutes)

### A. Add the new files (already created):

- ✅ `apps/mouth/src/lib/api/chat/webhook-chat.api.ts`
- ✅ `apps/mouth/src/hooks/useConversationPersistence.ts`

### B. Update your chat component:

```typescript
// In your chat page/component
import { useConversationPersistence } from '@/hooks/useConversationPersistence';
import { WebhookChatApi } from '@/lib/api/chat/webhook-chat.api';

export function ChatComponent() {
  const { sessionId, isLoading } = useConversationPersistence();
  const webhookChatApi = new WebhookChatApi(apiClient);

  const sendMessage = async (message: string) => {
    const response = await webhookChatApi.sendMessage(
      message,
      sessionId,
      { source: 'webapp' }
    );

    // Use response.answer for UI
    // response.persisted tells you if it saved
    // response.conversation_id is the DB record
  };

  return <div>{/* Your chat UI */}</div>;
}
```

### C. Deploy frontend:

```bash
cd apps/mouth

# Build and test locally
pnpm build
pnpm dev  # Test at http://localhost:3000

# Deploy to Vercel
vercel --prod
```

---

## Step 3: Verify (2 minutes)

### Test the full flow:

1. **Open webapp** → Send message: "What is the capital of France?"
2. **Check console** → Should see: `Message persisted: true`
3. **Refresh page** (F5)
4. **Send follow-up** → "What about Germany?"
5. **Verify** → AI should remember France question ✅

### Check database:

```bash
flyctl ssh console -a nuzantara-rag
psql $DATABASE_URL -c "SELECT COUNT(*) FROM conversations;"
```

**Expected**: Count increases with each conversation

---

## ✅ Success!

Your webapp now has full conversation persistence:

- ✅ Messages saved automatically
- ✅ Context maintained after refresh
- ✅ Cleanup runs daily
- ✅ Performance < 50ms

---

## Troubleshooting

**Messages not persisting?**

```bash
# Check backend logs
flyctl logs -a nuzantara-rag | grep "persisted"
```

**Context not working?**

```typescript
// Add debug logging
console.log("Session ID:", sessionId);
console.log("Persisted:", response.persisted);
```

**Need help?**

- Full guide: `docs/operations/DEPLOYMENT_GUIDE.md`
- Documentation: `apps/backend-rag/backend/docs/CONVERSATION_PERSISTENCE.md`
- Tests: `apps/backend-rag/backend/tests/test_conversation_persistence.py`
