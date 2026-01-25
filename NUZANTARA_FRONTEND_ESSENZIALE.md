# ⚛️ NUZANTARA - FRONTEND ESSENTIAL CODE

**Generated:** 2026-01-25
**Stack:** Next.js 15, React 19, TypeScript, TailwindCSS

---

## 📁 STRUTTURA ESSENZIALE

```
apps/mouth/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # 🏠 Root layout
│   │   ├── chat/
│   │   │   └── page.tsx            # 💬 Main chat interface
│   │   ├── (workspace)/            # 🏢 Internal workspace
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── clients/page.tsx
│   │   │   └── intelligence/       # 📰 News/Intel center
│   │   ├── (portal)/               # 🌐 Client portal
│   │   └── (blog)/                 # 📝 Public blog
│   ├── components/
│   │   ├── chat/                   # 💬 Chat components
│   │   │   ├── ChatHeader.tsx
│   │   │   ├── ChatInputBar.tsx
│   │   │   ├── ChatMessageList.tsx
│   │   │   └── MessageBubble.tsx
│   │   ├── crm/                    # 👥 CRM components
│   │   └── ui/                     # 🎨 Base UI (shadcn)
│   ├── hooks/
│   │   ├── useChatPage.ts          # 🎯 Chat orchestration
│   │   ├── useChatSend.ts          # 📤 Message sending
│   │   └── useChatStreaming.ts     # 📡 SSE streaming
│   └── lib/
│       └── api/
│           └── chat/chat.api.ts    # 🔌 Backend API client
```

---

## 1️⃣ CHAT PAGE (`chat/page.tsx`)

Orchestratore lightweight che compone hooks e componenti.

```tsx
'use client';

import { useChatPage } from '@/hooks/useChatPage';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatMessageListVirtualized } from '@/components/chat/ChatMessageListVirtualized';
import { ChatInputBar } from '@/components/chat/ChatInputBar';

export default function ChatPage() {
  const {
    // State
    displayMessages,
    isPending,
    currentStatus,
    
    // Refs
    messagesEndRef,
    
    // Hooks
    chatInput,
    sidebar,
    conversations,
    
    // Handlers
    handleSend,
    handleNewChat,
    handleConversationClick,
  } = useChatPage();

  return (
    <div className="flex h-screen bg-[#202020] text-white">
      {/* Sidebar - Conversations list */}
      <ChatSidebar
        isOpen={sidebar.sidebarOpen}
        conversations={conversations.conversations}
        currentConversationId={conversations.currentConversationId}
        onNewChat={handleNewChat}
        onConversationClick={handleConversationClick}
      />

      <main className="flex-1 flex flex-col">
        {/* Header */}
        <ChatHeader
          isSidebarOpen={sidebar.sidebarOpen}
          onToggleSidebar={sidebar.toggleSidebar}
        />

        {/* Messages */}
        <ChatMessageListVirtualized
          messages={displayMessages}
          isLoading={isPending}
          messagesEndRef={messagesEndRef}
        />

        {/* Input */}
        <ChatInputBar
          input={chatInput.input}
          setInput={chatInput.setInput}
          isLoading={isPending}
          onSend={handleSend}
        />
      </main>
    </div>
  );
}
```

---

## 2️⃣ CHAT PAGE HOOK (`useChatPage.ts`)

Hook composito che orchestra tutta la logica chat.

```typescript
export function useChatPage(): UseChatPageReturn {
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Compose sub-hooks
  const chatInput = useChatInput();
  const chatTTS = useChatTTS();
  const sidebar = useChatSidebar();
  const conversations = useConversations();
  const teamStatus = useTeamStatus();
  const audioRecorder = useAudioRecorder();
  
  // Messages state with optimistic updates
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);
  const [isPending, startTransition] = useTransition();
  const [currentStatus, setCurrentStatus] = useState('');
  
  // Optimistic UI for instant feedback
  const [optimisticMessages, addOptimisticMessage] = useOptimistic(
    messages,
    (state, newMessage: OptimisticMessage) => [...state, newMessage]
  );

  const handleSend = useCallback(async () => {
    if (!chatInput.input.trim() || isPending) return;
    
    const userMessage: OptimisticMessage = {
      id: generateId(),
      role: 'user',
      content: chatInput.input,
      timestamp: new Date().toISOString(),
      isPending: false,
    };
    
    // Optimistic: show user message immediately
    addOptimisticMessage(userMessage);
    chatInput.setInput('');
    
    // Add placeholder for AI response
    const aiPlaceholder: OptimisticMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      isPending: true,
      isStreaming: true,
    };
    addOptimisticMessage(aiPlaceholder);
    
    // Stream response from backend
    await api.chat.sendMessageStreaming(
      userMessage.content,
      sessionId,
      (chunk) => {
        // Update AI message with streaming content
        setMessages(prev => 
          prev.map(m => 
            m.id === aiPlaceholder.id 
              ? { ...m, content: chunk }
              : m
          )
        );
      },
      (fullResponse, sources, metadata) => {
        // Finalize message
        setMessages(prev =>
          prev.map(m =>
            m.id === aiPlaceholder.id
              ? { ...m, content: fullResponse, sources, isPending: false, isStreaming: false }
              : m
          )
        );
      },
      (error) => {
        showToast(error.message, 'error');
      },
      (step) => {
        // Handle reasoning steps, tool calls
        setCurrentStatus(step.type);
      }
    );
  }, [chatInput.input, isPending, sessionId]);

  return {
    displayMessages: optimisticMessages,
    isPending,
    currentStatus,
    messagesEndRef,
    chatInput,
    sidebar,
    conversations,
    handleSend,
    // ... other handlers
  };
}
```

---

## 3️⃣ CHAT API CLIENT (`chat.api.ts`)

Client per comunicare con il backend RAG.

```typescript
export class ChatApi {
  constructor(private client: IApiClient) {}

  /**
   * SSE streaming via backend `/api/agentic-rag/stream`
   * 
   * Event types handled:
   * - token: Partial response text
   * - sources: Retrieved documents
   * - tool_call/tool_end: Tool execution
   * - thinking: Reasoning steps
   * - done: Stream complete
   * - error: Error occurred
   */
  async sendMessageStreaming(
    message: string,
    conversationId: string,
    onChunk: (chunk: string) => void,
    onDone: (full: string, sources: Source[], metadata: any) => void,
    onError: (error: Error) => void,
    onStep?: (step: AgentStep) => void,
    timeoutMs = 120_000,
    conversationHistory: Message[] = [],
    abortSignal?: AbortSignal,
  ): Promise<void> {
    const url = `${API_BASE}/api/agentic-rag/stream`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': crypto.randomUUID(),
      },
      body: JSON.stringify({
        query: message,
        session_id: conversationId,
        conversation_history: conversationHistory.slice(-200), // Max 200 msgs
        stream: true,
      }),
      signal: abortSignal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let accumulated = '';
    let sources: Source[] = [];
    let metadata: any = {};

    while (true) {
      const { done, value } = await reader!.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          const eventType = line.slice(7);
          // Next line should be data
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          
          switch (data.type) {
            case 'token':
              accumulated += data.content;
              onChunk(accumulated);
              break;
            case 'sources':
              sources = data.sources;
              break;
            case 'thinking':
            case 'tool_call':
            case 'tool_end':
              onStep?.({
                type: data.type,
                data: data.content,
                timestamp: Date.now(),
              });
              break;
            case 'done':
              onDone(accumulated, sources, metadata);
              return;
            case 'error':
              onError(new Error(data.message));
              return;
          }
        }
      }
    }
  }

  /**
   * Non-streaming query (rarely used)
   */
  async sendMessage(message: string, userId?: string) {
    const response = await this.client.request<QueryResponse>(
      '/api/agentic-rag/query',
      {
        method: 'POST',
        body: JSON.stringify({
          query: message,
          user_id: userId || 'anonymous',
        }),
      }
    );
    return {
      response: response.answer,
      sources: response.sources,
    };
  }
}
```

---

## 4️⃣ MESSAGE BUBBLE (`MessageBubble.tsx`)

Rendering di un singolo messaggio.

```tsx
interface MessageBubbleProps {
  message: Message;
  userAvatar?: string | null;
  onFollowUpClick?: (question: string) => void;
}

export function MessageBubble({ message, userAvatar, onFollowUpClick }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;

  return (
    <div className={cn(
      'flex gap-3 p-4',
      isUser ? 'justify-end' : 'justify-start'
    )}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <span className="text-white text-sm">Z</span>
        </div>
      )}

      {/* Message content */}
      <div className={cn(
        'max-w-[80%] rounded-2xl px-4 py-2',
        isUser 
          ? 'bg-blue-600 text-white' 
          : 'bg-gray-800 text-gray-100'
      )}>
        {/* Streaming indicator */}
        {isStreaming && (
          <ThinkingIndicator status={message.currentStatus} />
        )}
        
        {/* Content with markdown */}
        <MarkdownRenderer content={message.content} />
        
        {/* Sources */}
        {message.sources?.length > 0 && (
          <SourcesList sources={message.sources} />
        )}
        
        {/* Follow-up suggestions */}
        {message.metadata?.followUps && (
          <FollowUpButtons 
            questions={message.metadata.followUps}
            onClick={onFollowUpClick}
          />
        )}
      </div>

      {/* User avatar */}
      {isUser && userAvatar && (
        <img src={userAvatar} className="w-8 h-8 rounded-full" />
      )}
    </div>
  );
}
```

---

## 5️⃣ CRM CLIENT CARD (`ClientCard.tsx`)

Card per visualizzare un cliente nel CRM.

```tsx
interface ClientCardProps {
  client: Client;
  onEdit: (id: number) => void;
  onViewFolder: (folderId: string) => void;
}

export function ClientCard({ client, onEdit, onViewFolder }: ClientCardProps) {
  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle>{client.company_name || client.name}</CardTitle>
            <Badge variant={getStatusVariant(client.status)}>
              {client.status}
            </Badge>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => onEdit(client.id)}>
                Edit
              </DropdownMenuItem>
              {client.gdrive_folder_id && (
                <DropdownMenuItem onClick={() => onViewFolder(client.gdrive_folder_id)}>
                  View Documents
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>📧 {client.email}</p>
          <p>📱 {client.phone}</p>
          {client.visa_type && <p>🛂 {client.visa_type}</p>}
          {client.expiry_date && (
            <p className={isExpiringSoon(client.expiry_date) ? 'text-red-500' : ''}>
              📅 Expires: {formatDate(client.expiry_date)}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

---

## 📊 API CLIENT STRUCTURE

```typescript
// lib/api/index.ts
export const api = {
  chat: new ChatApi(apiClient),
  crm: new CrmApi(apiClient),
  conversations: new ConversationsApi(apiClient),
  drive: new DriveApi(apiClient),
  team: new TeamApi(apiClient),
  intelligence: new IntelligenceApi(apiClient),
};

// Usage
await api.chat.sendMessageStreaming(...);
await api.crm.getClients({ status: 'active' });
await api.conversations.list();
```

---

## 🎨 UI COMPONENTS (shadcn/ui)

```
components/ui/
├── button.tsx
├── card.tsx
├── dialog.tsx
├── input.tsx
├── select.tsx
├── tabs.tsx
├── toast.tsx
└── skeleton.tsx
```

---

## 🛠️ KEY DEPENDENCIES

```json
{
  "next": "^15.0",
  "react": "^19.0",
  "typescript": "^5.7",
  "@tanstack/react-query": "^5.62",
  "tailwindcss": "^3.4",
  "lucide-react": "^0.468",
  "framer-motion": "^11.15",
  "@radix-ui/react-*": "latest",
  "uuid": "^11.0"
}
```

---

## 🔄 DATA FLOW

```
User Input
    │
    ▼
[ChatInputBar] → useChatInput
    │
    ▼
[useChatPage.handleSend]
    │
    ├── Optimistic UI update
    ▼
[ChatApi.sendMessageStreaming]
    │
    ▼
SSE Stream from Backend
    │
    ├── onChunk → Update message content
    ├── onStep → Show thinking/tools
    └── onDone → Finalize message
    │
    ▼
[ChatMessageList] re-renders
```
