# 🎨 FRONTEND NUZANTARA (MOUTH) - Studio Approfondito

> Analisi completa del frontend Next.js 14+ suddiviso in aree logiche

---

## 📊 Overview

| Metrica        | Valore                   |
| -------------- | ------------------------ |
| **Framework**  | Next.js 14+ (App Router) |
| **Linguaggio** | TypeScript               |
| **Styling**    | Tailwind CSS             |
| **Components** | 127 file TSX             |
| **Hooks**      | 28 custom hooks          |
| **API Client** | 30+ moduli               |
| **Test E2E**   | Playwright               |

---

## 🗺️ Mappa del Frontend

```
mouth/src/
├── 1️⃣ APP (Routes)         → Pages, layouts, API routes
├── 2️⃣ COMPONENTS           → 127 UI components
├── 3️⃣ HOOKS                → 28 custom React hooks
├── 4️⃣ LIB                  → API client, utilities
├── 5️⃣ PROVIDERS            → Context providers
└── 6️⃣ TYPES                → TypeScript definitions
```

---

## 1️⃣ APP - Routes & Pages

**Location:** `src/app/`

### Route Groups (Next.js 14+)

```
app/
├── (blog)/              # 🌐 Public blog/website
│   ├── [category]/      # Blog categories
│   │   └── [slug]/      # Individual articles
│   ├── contact/         # Contact page
│   ├── news/            # News section
│   ├── services/        # Services pages
│   │   └── [slug]/      # Service detail
│   └── team/            # Team page
│
├── (portal)/            # 🔒 Client portal
│   └── portal/
│       ├── company/     # Company info
│       ├── documents/   # Client documents
│       ├── messages/    # Client messages
│       ├── settings/    # Portal settings
│       ├── taxes/       # Tax documents
│       └── visa/        # Visa status
│
├── (workspace)/         # 🏢 Team workspace (main app)
│   ├── admin/           # Admin panel
│   ├── analytics/       # Analytics dashboard
│   ├── clients/         # CRM clients
│   ├── dashboard/       # Main dashboard
│   ├── documents/       # Google Drive-like docs
│   ├── email/           # Email management
│   ├── intelligence/    # AI Intelligence center
│   ├── knowledge/       # Knowledge base
│   ├── omnichannel/     # Multi-channel comms
│   ├── process/         # Process management
│   ├── settings/        # App settings
│   ├── team-management/ # Team admin
│   └── whatsapp/        # WhatsApp integration
│
├── api/                 # 🔌 API routes (proxy to backend)
│   ├── [...path]/       # Catch-all proxy
│   └── blog/            # Blog-specific APIs
│
├── chat/                # 💬 Chat interface
├── login/               # 🔐 Authentication
└── portal/              # Portal entry point
```

### Layout Hierarchy

```
app/layout.tsx (root)
├── (blog)/layout.tsx      # Public site layout
├── (portal)/layout.tsx    # Client portal layout
└── (workspace)/layout.tsx # Team workspace layout
```

---

## 2️⃣ COMPONENTS - UI Library

**Location:** `src/components/`

### Component Categories

| Folder       | Components | Description               |
| ------------ | ---------- | ------------------------- |
| `ui/`        | 23         | Base UI (shadcn/ui based) |
| `chat/`      | 19         | Chat interface components |
| `dashboard/` | 14         | Dashboard widgets         |
| `crm/`       | 5          | CRM components            |
| `documents/` | 8          | Google Drive-like UI      |
| `blog/`      | 10         | Blog/article components   |
| `admin/`     | 3          | Admin panel               |
| `agents/`    | 4          | AI agents UI              |
| `workspace/` | 3          | Sidebar, header           |
| `memory/`    | 5          | Memory visualization      |
| `email/`     | 6          | Email components          |
| `search/`    | 4          | Search UI                 |
| `seo/`       | 4          | SEO components            |
| `pricing/`   | 2          | Pricing tables            |
| `voice/`     | 2          | Voice recording           |
| `whatsapp/`  | 3          | WhatsApp integration      |
| `telegram/`  | 3          | Telegram integration      |
| `instagram/` | 3          | Instagram integration     |
| `twitter/`   | 3          | Twitter integration       |

### Key Components

#### Chat System

```
components/chat/
├── ChatHeader.tsx           # Conversation header
├── ChatInputBar.tsx         # Message input (8KB)
├── ChatMessageList.tsx      # Message list
├── ChatMessageListVirtualized.tsx  # Virtualized for perf
├── ChatSidebar.tsx          # Conversation list
├── MessageBubble.tsx        # Single message (21KB) ⭐
├── ThinkingIndicator.tsx    # AI thinking animation (25KB)
├── ChatSourcesPanel.tsx     # RAG sources display
├── FeedbackWidget.tsx       # User feedback
├── PricingTable.tsx         # Inline pricing
└── ImageGenModal.tsx        # Image generation
```

#### Dashboard Widgets

```
components/dashboard/
├── AiPulseWidget.tsx        # AI activity
├── AutoCRMWidget.tsx        # CRM automation (15KB)
├── ComplianceWidget.tsx     # Compliance status
├── EmailPreview.tsx         # Email preview (10KB)
├── FeaturedArticlesWidget.tsx  # Featured content
├── FinancialRealityWidget.tsx  # Financial data
├── GrafanaWidget.tsx        # Grafana embed
├── MonitoringWidget.tsx     # System monitoring
├── NusantaraHealthWidget.tsx   # Backend health (16KB)
├── PratichePreview.tsx      # Cases preview
├── StatsCard.tsx            # Stats display
└── WhatsAppPreview.tsx      # WhatsApp preview
```

#### UI Components (shadcn/ui based)

```
components/ui/
├── button.tsx       # Variants: default, outline, ghost, etc.
├── card.tsx         # Card container
├── dialog.tsx       # Modal dialogs
├── input.tsx        # Text input
├── label.tsx        # Form labels
├── select.tsx       # Select dropdowns
├── table.tsx        # Data tables
├── tabs.tsx         # Tab navigation
├── toast.tsx        # Toast notifications
├── skeleton.tsx     # Loading skeletons
├── progress.tsx     # Progress bars
├── scroll-area.tsx  # Custom scrollbars
└── confetti.tsx     # Celebration effects
```

---

## 3️⃣ HOOKS - Custom React Hooks

**Location:** `src/hooks/`

### 28 Custom Hooks

| Hook                       | LOC | Purpose                   |
| -------------------------- | --- | ------------------------- |
| `useChatPage.ts`           | 650 | Main chat orchestrator ⭐ |
| `useChatTTS.ts`            | 260 | Text-to-speech            |
| `useChat.ts`               | 225 | Chat state management     |
| `useOptimisticChat.ts`     | 220 | Optimistic updates        |
| `useChatMessages.ts`       | 135 | Message handling          |
| `useChatInput.ts`          | 200 | Input handling            |
| `useChatSend.ts`           | 220 | Message sending           |
| `useChatStreaming.ts`      | 155 | SSE streaming             |
| `useChatSidebar.ts`        | 70  | Sidebar state             |
| `useWebSocket.ts`          | 195 | WebSocket connection      |
| `useConversations.ts`      | 120 | Conversation list         |
| `useDashboardData.ts`      | 150 | Dashboard data            |
| `useDrive.ts`              | 190 | Google Drive operations   |
| `useAgenticRAGStream.ts`   | 155 | Agentic RAG streaming     |
| `useAudioRecorder.ts`      | 110 | Voice recording           |
| `useGeminiNano.ts`         | 155 | Chrome Gemini Nano        |
| `useKeyboardShortcuts.ts`  | 135 | Keyboard shortcuts        |
| `useKeyboardNavigation.ts` | 190 | Grid navigation           |
| `useInfiniteScroll.ts`     | 50  | Infinite scrolling        |
| `useEdgeSanitizer.ts`      | 50  | Input sanitization        |
| `useTeamStatus.ts`         | 45  | Team online status        |
| `useSystemSound.ts`        | 45  | System sounds             |
| `useClickOutside.ts`       | 70  | Click outside detection   |
| `useDebounce.ts`           | 25  | Debounced values          |
| `useIsMounted.ts`          | 30  | Mount detection           |
| `useAutoAnimate.ts`        | 15  | Auto-animate              |
| `useData.ts`               | 30  | Generic data fetching     |

### Key Hook: useChatPage

```typescript
// hooks/useChatPage.ts (650 LOC)
export function useChatPage() {
  // State
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sub-hooks composition
  const { sendMessage } = useChatSend();
  const { startStreaming } = useChatStreaming();
  const { conversations, loadConversations } = useConversations();
  const { playTTS } = useChatTTS();

  // Main send handler
  const handleSend = async (content: string, files?: File[]) => {
    // Optimistic update
    const tempMessage = createTempMessage(content);
    setMessages((prev) => [...prev, tempMessage]);

    // Send to backend
    const response = await sendMessage(content, files);

    // Handle streaming response
    if (response.stream) {
      await handleStreaming(response.stream);
    }

    // Update with real message
    setMessages((prev) => prev.map((m) => (m.id === tempMessage.id ? response : m)));
  };

  return {
    messages,
    isLoading,
    isStreaming,
    error,
    handleSend,
    conversations,
    // ... more
  };
}
```

---

## 4️⃣ LIB - API & Utilities

**Location:** `src/lib/`

### Structure

```
lib/
├── api/                 # API client modules
│   ├── client.ts        # Base HTTP client (11KB) ⭐
│   ├── api-client.ts    # Extended client (16KB)
│   ├── chat/            # Chat API
│   ├── crm/             # CRM API
│   ├── drive/           # Google Drive API
│   ├── intelligence.api.ts  # Intel API (11KB)
│   ├── auth/            # Auth API
│   ├── conversations/   # Conversations API
│   ├── knowledge/       # Knowledge API
│   ├── media/           # Media API
│   ├── portal/          # Portal API
│   ├── team/            # Team API
│   ├── websocket/       # WebSocket client
│   └── zantara-sdk/     # Backend SDK
│
├── utils/               # Utility functions
│   ├── date.ts          # Date formatting
│   ├── format.ts        # String formatting
│   └── validation.ts    # Input validation
│
├── types/               # Type definitions
│   ├── api.ts           # API types
│   ├── chat.ts          # Chat types
│   └── user.ts          # User types
│
├── blog/                # Blog utilities
├── seo/                 # SEO utilities
├── edge/                # Edge runtime utils
├── metrics/             # Performance metrics
├── logging/             # Structured logging
│
├── analytics.ts         # Analytics tracking
├── logger.ts            # Logger (6KB)
├── metrics.ts           # Web vitals (6KB)
├── monitoring.ts        # Monitoring (7KB)
├── realtime.tsx         # Real-time updates (14KB)
├── ai-insights.tsx      # AI insights (19KB)
├── funnel-analytics.tsx # Funnel tracking (16KB)
└── mobile-optimization.tsx  # Mobile perf (12KB)
```

### API Client

```typescript
// lib/api/client.ts
export class APIClient {
  private baseURL: string;
  private token: string | null;

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_URL;
    this.token = this.getToken();
  }

  // Base methods
  async get<T>(path: string): Promise<T>;
  async post<T>(path: string, data?: unknown): Promise<T>;
  async put<T>(path: string, data?: unknown): Promise<T>;
  async delete<T>(path: string): Promise<T>;

  // Streaming
  async stream(path: string, data?: unknown): AsyncGenerator<string>;

  // Auth
  login(email: string, password: string): Promise<AuthResponse>;
  logout(): Promise<void>;
  getToken(): string | null;

  // Profile
  getProfile(): Promise<UserProfile>;
  getUserProfile(): UserProfile | null;
}

export const api = new APIClient();
```

---

## 5️⃣ PROVIDERS - Context

**Location:** `src/providers/`

```typescript
// providers/index.tsx
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <AnalyticsProvider>
            {children}
          </AnalyticsProvider>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
```

---

## 6️⃣ Testing

### E2E Tests (Playwright)

**Location:** `e2e/`

```
e2e/
├── admin/          # Admin tests
├── auth/           # Auth flow tests
├── chat/           # Chat tests
├── crm/            # CRM tests
├── knowledge/      # Knowledge base tests
├── login/          # Login tests
├── smoke/          # Smoke tests
├── websocket/      # WebSocket tests
├── zantara/        # Integration tests
├── fixtures/       # Test fixtures
└── utils/          # Test utilities
```

### Unit Tests

- Location: `src/**/__tests__/`
- Framework: Vitest
- Coverage: `coverage/`

---

## 📁 Key Files Summary

| File                                             | Size | Purpose                |
| ------------------------------------------------ | ---- | ---------------------- |
| `hooks/useChatPage.ts`                           | 23KB | Main chat orchestrator |
| `components/chat/ThinkingIndicator.tsx`          | 25KB | AI thinking UI         |
| `components/chat/MessageBubble.tsx`              | 21KB | Message display        |
| `lib/api/api-client.ts`                          | 16KB | Extended API client    |
| `lib/ai-insights.tsx`                            | 19KB | AI insights            |
| `lib/funnel-analytics.tsx`                       | 16KB | Analytics funnel       |
| `components/dashboard/NusantaraHealthWidget.tsx` | 16KB | Health dashboard       |
| `components/dashboard/AutoCRMWidget.tsx`         | 15KB | CRM widget             |

---

## 🎨 Design System

### Colors (Tailwind)

```css
/* Dark theme (default) */
--background: #2a2a2a --foreground: #fafafa --accent: #10b981 (emerald) --muted: #6b7280
  /* Google Drive theme (documents) */ --drive-primary: #1a73e8 --drive-selected: #e8f0fe
  --drive-hover: #f5f5f5;
```

### Spacing

- Sidebar: 240px (`md:ml-60`)
- Header: 64px
- Page padding: `p-4 md:p-6 lg:p-8`

---

## 🔄 Data Flow

```
User Action
    │
    ▼
┌──────────────┐
│   Component  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Custom Hook │ (useChatPage, useDrive, etc.)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  API Client  │ (lib/api/)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Backend    │ (Nuzantara RAG)
└──────────────┘
```

---

## 🚀 Development

```bash
# Install
npm install

# Dev server
npm run dev

# Build
npm run build

# Tests
npm run test        # Unit tests
npm run e2e         # E2E tests

# Lint
npm run lint
```

---

## 📚 Related Docs

- `DOCUMENTATION.md` - Full documentation (48KB)
- `CLAUDE.md` - AI context
- `README.md` - Project overview
- `docs/DRIVE_SYSTEM.md` - Documents page docs

---

_"Beautiful interfaces, powerful functionality" 🎨_
