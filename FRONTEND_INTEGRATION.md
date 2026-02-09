# Frontend Integration - Conversation Persistence

**Status**: ✅ Backend testato e funzionante in produzione  
**Next**: Integra nel frontend

---

## 🎯 Obiettivo

Aggiornare il chat component per usare il nuovo sistema di persistenza che:
- Salva automaticamente ogni messaggio
- Mantiene la conversazione dopo page refresh
- Carica history all'avvio

---

## 📝 Step-by-Step

### 1. Trova il Chat Component

Cerca il file principale del chat (probabilmente uno di questi):
```
apps/mouth/src/app/chat/page.tsx
apps/mouth/src/app/(workspace)/chat/page.tsx
apps/mouth/src/components/chat/ChatInterface.tsx
```

### 2. Aggiungi gli Import

```typescript
import { useConversationPersistence } from '@/hooks/useConversationPersistence';
import { WebhookChatApi } from '@/lib/api/chat/webhook-chat.api';
import { useApiClient } from '@/hooks/useApiClient'; // o il tuo hook per API client
```

### 3. Inizializza nel Component

```typescript
export function ChatPage() {
  // Session management (auto-genera e persiste session_id)
  const { sessionId, isLoading, resetSession } = useConversationPersistence();
  
  // API client
  const apiClient = useApiClient();
  const webhookApi = new WebhookChatApi(apiClient);
  
  // State per messaggi
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  // ... resto del component
}
```

### 4. Carica History all'Avvio

```typescript
useEffect(() => {
  if (!sessionId || isLoading) return;

  // Carica conversation history
  const loadHistory = async () => {
    try {
      setIsLoadingHistory(true);
      const history = await webhookApi.getHistory(sessionId, 20);
      
      if (history.success && history.messages.length > 0) {
        setMessages(history.messages);
        console.log(`✅ Loaded ${history.total_messages} messages from history`);
      }
    } catch (error) {
      console.error('Failed to load history:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  loadHistory();
}, [sessionId, isLoading]);
```

### 5. Modifica Send Message

```typescript
const handleSendMessage = async (userMessage: string) => {
  if (!sessionId) return;

  try {
    // Aggiungi messaggio utente alla UI
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Invia al backend con persistence
    const response = await webhookApi.sendMessage(
      userMessage,
      sessionId,
      { 
        source: 'webapp',
        timestamp: new Date().toISOString()
      }
    );

    // Aggiungi risposta AI alla UI
    setMessages(prev => [...prev, { 
      role: 'assistant', 
      content: response.answer 
    }]);

    // Log persistence status
    console.log('✅ Message persisted:', response.persisted);
    console.log('📊 Conversation ID:', response.conversation_id);

  } catch (error) {
    console.error('Failed to send message:', error);
    // Handle error (mostra toast, etc.)
  }
};
```

### 6. Aggiungi Pulsante "New Conversation"

```typescript
<button 
  onClick={() => {
    resetSession();
    setMessages([]);
  }}
  className="..."
>
  🔄 New Conversation
</button>
```

---

## 📋 Esempio Completo

```typescript
'use client';

import { useState, useEffect } from 'react';
import { useConversationPersistence } from '@/hooks/useConversationPersistence';
import { WebhookChatApi } from '@/lib/api/chat/webhook-chat.api';
import { useApiClient } from '@/hooks/useApiClient';

export function ChatPage() {
  // Hooks
  const { sessionId, isLoading: isSessionLoading, resetSession } = useConversationPersistence();
  const apiClient = useApiClient();
  const webhookApi = new WebhookChatApi(apiClient);

  // State
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSending, setIsSending] = useState(false);

  // Load history on mount
  useEffect(() => {
    if (!sessionId || isSessionLoading) return;

    const loadHistory = async () => {
      try {
        setIsLoadingHistory(true);
        const history = await webhookApi.getHistory(sessionId, 20);
        
        if (history.success && history.messages.length > 0) {
          setMessages(history.messages);
        }
      } catch (error) {
        console.error('Failed to load history:', error);
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadHistory();
  }, [sessionId, isSessionLoading]);

  // Send message
  const handleSend = async (userMessage: string) => {
    if (!sessionId || !userMessage.trim()) return;

    try {
      setIsSending(true);
      
      // Add user message to UI
      setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

      // Send to backend
      const response = await webhookApi.sendMessage(
        userMessage,
        sessionId,
        { source: 'webapp' }
      );

      // Add AI response to UI
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: response.answer 
      }]);

    } catch (error) {
      console.error('Send failed:', error);
    } finally {
      setIsSending(false);
    }
  };

  // New conversation
  const handleNewConversation = () => {
    resetSession();
    setMessages([]);
  };

  if (isSessionLoading || isLoadingHistory) {
    return <div>Loading conversation...</div>;
  }

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <h1>Chat</h1>
        <button onClick={handleNewConversation}>
          New Conversation
        </button>
      </div>

      {/* Messages */}
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="chat-input">
        <input
          type="text"
          onKeyPress={(e) => {
            if (e.key === 'Enter' && !isSending) {
              handleSend(e.currentTarget.value);
              e.currentTarget.value = '';
            }
          }}
          disabled={isSending}
          placeholder="Type a message..."
        />
      </div>
    </div>
  );
}
```

---

## 🧪 Test dopo Integrazione

1. **Invia messaggio** → Verifica console: `persisted: true`
2. **Refresh pagina (F5)** → Messaggi devono riapparire
3. **Invia follow-up** → AI deve ricordare contesto
4. **Click "New Conversation"** → Messaggi si azzerano, nuovo session_id

---

## 🚀 Deploy

```bash
cd apps/mouth

# Build
pnpm build

# Test locale
pnpm dev

# Deploy a Vercel
vercel --prod
```

---

## 📊 Monitoring

Dopo il deploy, monitora:

```javascript
// In DevTools Console
localStorage.getItem('zantara_session_id')  // Verifica session_id
```

```bash
# Backend logs
flyctl logs -a nuzantara-rag | grep "persisted"
```

---

## ✅ Checklist

- [ ] Import aggiunti
- [ ] `useConversationPersistence` hook usato
- [ ] History caricata all'avvio
- [ ] `sendMessage` usa `webhookApi`
- [ ] Pulsante "New Conversation" aggiunto
- [ ] Build locale OK
- [ ] Test refresh page OK
- [ ] Deploy a Vercel
- [ ] Test produzione OK

---

**Pronto per integrare!** Modifica il chat component e testa. 🎯
