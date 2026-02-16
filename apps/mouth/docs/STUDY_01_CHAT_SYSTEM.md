# 💬 PARTE 1: Chat System

> Il sistema di chat AI di Nuzantara (ZANTARA)

---

## Overview

Il chat è il cuore dell'interazione utente-AI. Supporta:

- Messaggi di testo
- Voice notes (recording + TTS)
- File attachments
- RAG con citazioni
- Streaming responses
- Agentic RAG

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Chat Page                           │
│                    app/chat/page.tsx                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      useChatPage Hook                       │
│    Orchestrates: messages, streaming, TTS, conversations    │
└───────────┬─────────────┬─────────────┬─────────────────────┘
            │             │             │
            ▼             ▼             ▼
┌───────────────┐ ┌─────────────┐ ┌──────────────┐
│ useChatSend   │ │useChatStream│ │ useChatTTS   │
│ (send logic)  │ │ (SSE)       │ │ (audio)      │
└───────────────┘ └─────────────┘ └──────────────┘
            │             │             │
            └─────────────┼─────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       API Client                            │
│                    lib/api/chat/                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend RAG                            │
│                 /api/conversations/                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. ChatSidebar

**File:** `components/chat/ChatSidebar.tsx`

```typescript
interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete
}: ChatSidebarProps) {
  return (
    <aside className="w-64 border-r bg-background">
      <Button onClick={onNew}>
        <Plus /> New Chat
      </Button>

      <ScrollArea>
        {conversations.map(conv => (
          <ConversationItem
            key={conv.id}
            conversation={conv}
            isActive={conv.id === activeId}
            onClick={() => onSelect(conv.id)}
            onDelete={() => onDelete(conv.id)}
          />
        ))}
      </ScrollArea>
    </aside>
  );
}
```

### 2. ChatMessageList

**File:** `components/chat/ChatMessageList.tsx`

```typescript
interface ChatMessageListProps {
  messages: Message[];
  isLoading: boolean;
  onRetry: (messageId: string) => void;
}

export function ChatMessageList({
  messages,
  isLoading,
  onRetry
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map(message => (
        <MessageBubble
          key={message.id}
          message={message}
          onRetry={() => onRetry(message.id)}
        />
      ))}

      {isLoading && <ThinkingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}
```

### 3. MessageBubble

**File:** `components/chat/MessageBubble.tsx` (21KB)

```typescript
interface MessageBubbleProps {
  message: Message;
  onRetry?: () => void;
  onFeedback?: (rating: number) => void;
}

export function MessageBubble({
  message,
  onRetry,
  onFeedback
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;

  return (
    <div className={cn(
      "flex gap-3",
      isUser ? "flex-row-reverse" : "flex-row"
    )}>
      {/* Avatar */}
      <Avatar>
        {isUser ? <UserIcon /> : <BotIcon />}
      </Avatar>

      {/* Message content */}
      <div className={cn(
        "rounded-lg p-3 max-w-[80%]",
        isUser
          ? "bg-primary text-primary-foreground"
          : "bg-muted"
      )}>
        {/* Markdown rendering */}
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code: CodeBlock,
            a: ExternalLink,
          }}
        >
          {message.content}
        </ReactMarkdown>

        {/* Streaming indicator */}
        {isStreaming && <StreamingCursor />}

        {/* Sources (RAG citations) */}
        {message.sources?.length > 0 && (
          <SourcesList sources={message.sources} />
        )}

        {/* Actions */}
        {!isUser && (
          <MessageActions
            onCopy={() => copyToClipboard(message.content)}
            onSpeak={() => speakMessage(message.content)}
            onFeedback={onFeedback}
          />
        )}
      </div>
    </div>
  );
}
```

### 4. ChatInputBar

**File:** `components/chat/ChatInputBar.tsx` (8KB)

```typescript
interface ChatInputBarProps {
  onSend: (content: string, files?: File[]) => void;
  isLoading: boolean;
  placeholder?: string;
}

export function ChatInputBar({
  onSend,
  isLoading,
  placeholder = "Ask ZANTARA anything..."
}: ChatInputBarProps) {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        `${textareaRef.current.scrollHeight}px`;
    }
  }, [content]);

  const handleSubmit = () => {
    if (!content.trim() && files.length === 0) return;
    onSend(content, files);
    setContent('');
    setFiles([]);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t p-4">
      {/* File preview */}
      {files.length > 0 && (
        <FilePreviewList
          files={files}
          onRemove={(i) => setFiles(f => f.filter((_, j) => j !== i))}
        />
      )}

      <div className="flex items-end gap-2">
        {/* File upload */}
        <FileUploadButton onFiles={setFiles} />

        {/* Voice recording */}
        <VoiceRecordButton onRecording={handleVoice} />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1 resize-none"
          rows={1}
        />

        {/* Send button */}
        <Button
          onClick={handleSubmit}
          disabled={isLoading || (!content.trim() && files.length === 0)}
        >
          <Send />
        </Button>
      </div>
    </div>
  );
}
```

### 5. ThinkingIndicator

**File:** `components/chat/ThinkingIndicator.tsx` (25KB)

```typescript
interface ThinkingIndicatorProps {
  stage?: 'thinking' | 'searching' | 'generating';
  searchQuery?: string;
  sourcesFound?: number;
}

export function ThinkingIndicator({
  stage = 'thinking',
  searchQuery,
  sourcesFound
}: ThinkingIndicatorProps) {
  return (
    <div className="flex gap-3 animate-pulse">
      <Avatar>
        <BotIcon className="animate-bounce" />
      </Avatar>

      <div className="bg-muted rounded-lg p-3">
        {/* Stage indicator */}
        <div className="flex items-center gap-2">
          <Loader2 className="animate-spin" />
          <span className="text-sm text-muted-foreground">
            {stage === 'thinking' && 'ZANTARA is thinking...'}
            {stage === 'searching' && `Searching: "${searchQuery}"`}
            {stage === 'generating' && `Found ${sourcesFound} sources, generating response...`}
          </span>
        </div>

        {/* Animated dots */}
        <div className="flex gap-1 mt-2">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="w-2 h-2 bg-primary rounded-full"
              style={{
                animation: `bounce 1s infinite ${i * 0.2}s`
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## Hooks

### useChatPage (Main Orchestrator)

**File:** `hooks/useChatPage.ts` (23KB)

```typescript
export function useChatPage() {
  // Core state
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Sub-hooks
  const { sendMessage, sendWithFiles } = useChatSend();
  const { startStream, stopStream } = useChatStreaming();
  const { playTTS, stopTTS, isSpeaking } = useChatTTS();
  const { conversations, refreshConversations } = useConversations();

  // Load conversation
  const loadConversation = useCallback(async (id: string) => {
    setIsLoading(true);
    try {
      const data = await api.getConversation(id);
      setMessages(data.messages);
      setConversationId(id);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Send message handler
  const handleSend = useCallback(
    async (content: string, files?: File[]) => {
      // Create optimistic message
      const tempId = `temp-${Date.now()}`;
      const userMessage: Message = {
        id: tempId,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };

      // Optimistic update
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        // Send to backend
        const response = await sendMessage({
          conversationId,
          content,
          files,
        });

        // Handle streaming response
        if (response.stream) {
          setIsStreaming(true);

          // Add placeholder for assistant
          const assistantMessage: Message = {
            id: response.messageId,
            role: "assistant",
            content: "",
            isStreaming: true,
          };
          setMessages((prev) => [...prev, assistantMessage]);

          // Stream chunks
          for await (const chunk of response.stream) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === response.messageId
                  ? { ...m, content: m.content + chunk }
                  : m,
              ),
            );
          }

          // Mark as complete
          setMessages((prev) =>
            prev.map((m) =>
              m.id === response.messageId ? { ...m, isStreaming: false } : m,
            ),
          );

          setIsStreaming(false);
        }

        // Auto-play TTS if enabled
        if (settings.autoTTS) {
          playTTS(response.content);
        }
      } catch (error) {
        // Mark message as failed
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...m, error: true } : m)),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId, sendMessage, playTTS],
  );

  // New conversation
  const handleNewConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
  }, []);

  // Delete conversation
  const handleDeleteConversation = useCallback(
    async (id: string) => {
      await api.deleteConversation(id);
      await refreshConversations();
      if (conversationId === id) {
        handleNewConversation();
      }
    },
    [conversationId, refreshConversations, handleNewConversation],
  );

  return {
    // State
    messages,
    isLoading,
    isStreaming,
    conversationId,
    conversations,
    isSpeaking,

    // Actions
    handleSend,
    loadConversation,
    handleNewConversation,
    handleDeleteConversation,
    playTTS,
    stopTTS,
  };
}
```

### useChatStreaming

**File:** `hooks/useChatStreaming.ts`

```typescript
export function useChatStreaming() {
  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(async function* (
    conversationId: string,
    content: string,
  ): AsyncGenerator<string> {
    // Create abort controller
    abortControllerRef.current = new AbortController();

    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, content }),
      signal: abortControllerRef.current.signal,
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      // Parse SSE format
      const lines = chunk.split("\n");
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = JSON.parse(line.slice(6));
          yield data.content;
        }
      }
    }
  }, []);

  const stopStream = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  return { startStream, stopStream };
}
```

### useChatTTS

**File:** `hooks/useChatTTS.ts`

```typescript
export function useChatTTS() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [queue, setQueue] = useState<string[]>([]);

  const playTTS = useCallback(
    async (text: string) => {
      setIsSpeaking(true);

      try {
        // Request TTS from backend
        const response = await api.generateTTS(text);
        const audioUrl = response.audioUrl;

        // Play audio
        audioRef.current = new Audio(audioUrl);
        audioRef.current.onended = () => {
          setIsSpeaking(false);
          // Play next in queue
          if (queue.length > 0) {
            const [next, ...rest] = queue;
            setQueue(rest);
            playTTS(next);
          }
        };
        await audioRef.current.play();
      } catch (error) {
        setIsSpeaking(false);
      }
    },
    [queue],
  );

  const stopTTS = useCallback(() => {
    audioRef.current?.pause();
    setIsSpeaking(false);
    setQueue([]);
  }, []);

  const queueTTS = useCallback(
    (text: string) => {
      if (isSpeaking) {
        setQueue((prev) => [...prev, text]);
      } else {
        playTTS(text);
      }
    },
    [isSpeaking, playTTS],
  );

  return { playTTS, stopTTS, queueTTS, isSpeaking };
}
```

---

## API Integration

### Chat API Client

**File:** `lib/api/chat/index.ts`

```typescript
export const chatApi = {
  // Send message
  async send(data: SendMessageRequest): Promise<SendMessageResponse> {
    return api.post("/api/chat/send", data);
  },

  // Stream message
  stream(data: SendMessageRequest): EventSource {
    return api.stream("/api/chat/stream", data);
  },

  // Get conversation
  async getConversation(id: string): Promise<Conversation> {
    return api.get(`/api/conversations/${id}`);
  },

  // List conversations
  async listConversations(): Promise<Conversation[]> {
    return api.get("/api/conversations");
  },

  // Delete conversation
  async deleteConversation(id: string): Promise<void> {
    return api.delete(`/api/conversations/${id}`);
  },

  // Generate TTS
  async generateTTS(text: string): Promise<TTSResponse> {
    return api.post("/api/tts/generate", { text });
  },

  // Transcribe audio
  async transcribe(audio: Blob): Promise<TranscribeResponse> {
    const formData = new FormData();
    formData.append("audio", audio);
    return api.post("/api/transcribe", formData);
  },
};
```

---

## Message Types

```typescript
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;

  // Optional
  isStreaming?: boolean;
  error?: boolean;
  sources?: Source[];
  images?: string[];
  audio?: string;
  metadata?: {
    model?: string;
    tokens?: number;
    latency?: number;
  };
}

interface Source {
  title: string;
  url?: string;
  snippet: string;
  score: number;
}

interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  preview?: string;
}
```

---

## Keyboard Shortcuts

| Shortcut      | Action           |
| ------------- | ---------------- |
| `Enter`       | Send message     |
| `Shift+Enter` | New line         |
| `Cmd+K`       | New conversation |
| `Cmd+/`       | Toggle sidebar   |
| `Escape`      | Stop streaming   |
| `Cmd+.`       | Stop TTS         |

---

_"Conversation is intelligence" 💬_
