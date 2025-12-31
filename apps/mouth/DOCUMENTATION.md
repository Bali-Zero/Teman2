# Nuzantara Mouth - Documentazione Tecnica Completa

> **Versione:** 1.0.0
> **Ultimo aggiornamento:** 31 Dicembre 2024
> **Autore:** Zantara AI
> **Stack:** Next.js 16 + React 19 + TypeScript + TailwindCSS 4

---

## Indice

1. [Overview](#1-overview)
2. [Architettura di Sistema](#2-architettura-di-sistema)
3. [Struttura del Progetto](#3-struttura-del-progetto)
4. [Configurazione](#4-configurazione)
5. [Routing e Pagine](#5-routing-e-pagine)
6. [Sistema di Componenti](#6-sistema-di-componenti)
7. [API Architecture](#7-api-architecture)
8. [State Management](#8-state-management)
9. [Sistema Blog (MDX)](#9-sistema-blog-mdx)
10. [Design System](#10-design-system)
11. [Integrazioni](#11-integrazioni)
12. [Autenticazione e Sicurezza](#12-autenticazione-e-sicurezza)
13. [Testing](#13-testing)
14. [Deployment](#14-deployment)
15. [Performance](#15-performance)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Overview

### Cos'è Mouth?

**Mouth** è il frontend dell'ecosistema Nuzantara - un sistema operativo AI per business in Indonesia. Serve come interfaccia principale per:

- **Chat AI (Zantara)** - Assistente RAG conversazionale
- **CRM Workspace** - Gestione clienti, casi, team
- **Blog Insights** - 100+ articoli MDX su visa, business, tax
- **Client Portal** - Portale self-service per clienti
- **Integrazioni** - WhatsApp, Email (Zoho), Knowledge Base

### Stack Tecnologico

| Layer | Tecnologia | Versione |
|-------|------------|----------|
| Framework | Next.js | 16.1.1 |
| Runtime | React | 19.2.1 |
| Language | TypeScript | 5.x |
| Styling | TailwindCSS | 4.x |
| Animations | Framer Motion | 12.x |
| AI SDK | Vercel AI SDK | 6.x |
| MDX | next-mdx-remote | 5.x |
| Testing | Vitest + Playwright | Latest |
| Deployment | Fly.io | Docker |

### Connessioni Esterne

```
┌─────────────────────────────────────────────────────────────────┐
│                         MOUTH (Frontend)                         │
│                    https://nuzantara-mouth.fly.dev               │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTP/WebSocket
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND-RAG (Python FastAPI)                  │
│                    https://nuzantara-rag.fly.dev                 │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Agentic RAG │  │   Qdrant     │  │  PostgreSQL  │          │
│  │   Pipeline   │  │  (Vectors)   │  │  (Database)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Claude    │  │    OpenAI    │  │    Gemini    │          │
│  │   (Primary)  │  │ (Embeddings) │  │   (Backup)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Sentry    │  │    Zoho      │  │  Pollinations │         │
│  │   (Errors)   │  │    (CRM)     │  │  (Image Gen)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Architettura di Sistema

### Pattern Architetturali

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    Pages    │  │  Components │  │   Layouts   │             │
│  │  (App Dir)  │  │  (Feature)  │  │  (Shared)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         STATE LAYER                              │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Hooks     │  │  Providers  │  │   Context   │             │
│  │  (Custom)   │  │  (React)    │  │  (Global)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                             │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  API Client │  │  WebSocket  │  │   Zantara   │             │
│  │   (Base)    │  │  Provider   │  │    SDK      │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    Types    │  │  Constants  │  │  Utilities  │             │
│  │ (TypeScript)│  │  (Config)   │  │  (Helpers)  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Flusso Dati (Chat)

```
User Input → ChatInputBar → useChat Hook → ChatApi.sendMessageStreaming()
                                                      │
                                                      ▼
                                            API Proxy (/api/[...path])
                                                      │
                                                      ▼
                                            Backend (SSE Stream)
                                                      │
                                                      ▼
                                            Parse Stream Events
                                                      │
                                                      ▼
          MessageBubble ← useChatMessages ← Update State
```

---

## 3. Struttura del Progetto

```
apps/mouth/
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── (blog)/                   # Route Group: Blog
│   │   │   └── insights/             # Blog pages
│   │   │       ├── [category]/       # Category page
│   │   │       │   └── [slug]/       # Article page
│   │   │       └── page.tsx          # Blog home
│   │   ├── (workspace)/              # Route Group: Workspace
│   │   │   ├── dashboard/            # Dashboard
│   │   │   ├── chat/                 # Chat interface
│   │   │   ├── clients/              # Client management
│   │   │   ├── cases/                # Case management
│   │   │   ├── email/                # Email (Zoho)
│   │   │   ├── knowledge/            # Knowledge base
│   │   │   ├── team/                 # Team management
│   │   │   ├── whatsapp/             # WhatsApp
│   │   │   ├── portal/               # Client portal
│   │   │   └── settings/             # Settings
│   │   ├── admin/                    # Admin pages
│   │   ├── agents/                   # Agent management
│   │   ├── api/                      # API Routes
│   │   │   ├── [...path]/            # Universal proxy
│   │   │   └── blog/                 # Blog API
│   │   ├── login/                    # Auth page
│   │   ├── globals.css               # Global styles
│   │   ├── layout.tsx                # Root layout
│   │   └── page.tsx                  # Root redirect
│   │
│   ├── components/                   # React Components
│   │   ├── admin/                    # Admin UI
│   │   ├── blog/                     # Blog components
│   │   │   ├── interactive/          # Interactive MDX components
│   │   │   ├── ArticleCard.tsx
│   │   │   ├── ArticleGrid.tsx
│   │   │   ├── CategoryNav.tsx
│   │   │   ├── MDXContent.tsx
│   │   │   ├── NewsletterForm.tsx
│   │   │   ├── SearchBar.tsx
│   │   │   └── TableOfContents.tsx
│   │   ├── chat/                     # Chat UI
│   │   │   ├── ChatHeader.tsx
│   │   │   ├── ChatInputBar.tsx
│   │   │   ├── ChatMessageList.tsx
│   │   │   ├── ChatSourcesPanel.tsx
│   │   │   ├── FeedbackWidget.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── ThinkingIndicator.tsx
│   │   ├── dashboard/                # Dashboard widgets
│   │   ├── email/                    # Email components
│   │   ├── memory/                   # Memory display
│   │   ├── pricing/                  # Pricing calculator
│   │   ├── search/                   # Search modal
│   │   ├── ui/                       # Base UI components
│   │   └── workspace/                # Workspace layout
│   │
│   ├── content/                      # MDX Content
│   │   └── articles/                 # Blog articles
│   │       ├── business/             # 27 articles
│   │       ├── immigration/          # 26 articles
│   │       ├── tax/                  # 15 articles
│   │       ├── property/             # 12 articles
│   │       ├── lifestyle/            # 14 articles
│   │       └── digital-nomad/        # 5 articles
│   │
│   ├── hooks/                        # Custom React Hooks
│   │   ├── useChat.ts
│   │   ├── useChatMessages.ts
│   │   ├── useChatStreaming.ts
│   │   ├── useConversations.ts
│   │   ├── useMemoryContext.ts
│   │   ├── useWebSocket.ts
│   │   └── ...
│   │
│   ├── lib/                          # Libraries & Utilities
│   │   ├── api/                      # API Clients
│   │   │   ├── chat/                 # Chat API
│   │   │   ├── zantara-sdk/          # Zantara SDK
│   │   │   ├── client.ts             # Base client
│   │   │   └── index.ts              # Exports
│   │   ├── blog/                     # Blog utilities
│   │   │   ├── articles.ts           # MDX reader
│   │   │   └── types.ts              # Blog types
│   │   └── utils.ts                  # Helpers
│   │
│   ├── providers/                    # Context Providers
│   │   └── WebSocketProvider.tsx
│   │
│   ├── constants/                    # Configuration
│   │   └── config.ts
│   │
│   └── types/                        # TypeScript Types
│       ├── index.ts                  # Core types
│       └── navigation.ts             # Nav types
│
├── public/                           # Static Assets
│   └── images/
│       ├── blog/                     # Blog images
│       │   ├── immigration/
│       │   ├── business/
│       │   ├── tax/
│       │   ├── property/
│       │   ├── lifestyle/
│       │   └── digital-nomad/
│       └── ...
│
├── e2e/                              # E2E Tests
├── Dockerfile                        # Docker build
├── fly.toml                          # Fly.io config
├── next.config.ts                    # Next.js config
├── tailwind.config.ts                # Tailwind config
├── vitest.config.ts                  # Test config
├── package.json                      # Dependencies
└── tsconfig.json                     # TypeScript config
```

---

## 4. Configurazione

### Environment Variables

```bash
# .env.local

# Backend API
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
NUZANTARA_API_URL=https://nuzantara-rag.fly.dev

# WebSocket
NEXT_PUBLIC_WS_URL=wss://nuzantara-rag.fly.dev/ws

# Error Tracking (Sentry)
NEXT_PUBLIC_SENTRY_DSN=https://xxx@sentry.io/xxx
SENTRY_DSN=https://xxx@sentry.io/xxx

# Build Info
NEXT_PUBLIC_BUILD_ID=local
```

### next.config.ts

```typescript
const nextConfig: NextConfig = {
  output: 'standalone',  // Per Docker deployment

  images: {
    remotePatterns: [
      { hostname: '*.fly.dev' },
      { hostname: 'oaidalleapiprodscus.blob.core.windows.net' },  // DALL-E
      { hostname: 'image.pollinations.ai' },  // Image gen
      { hostname: 'placehold.co' },  // Placeholders
    ],
  },

  // Sentry integration (conditional)
  sentry: {
    hideSourceMaps: true,
  },
};
```

### fly.toml (Deployment)

```toml
app = 'nuzantara-mouth'
primary_region = 'sin'  # Singapore

[build]

[env]
NODE_ENV = 'production'
NEXT_TELEMETRY_DISABLED = '1'

[http_service]
internal_port = 3000
force_https = true
auto_stop_machines = 'stop'
auto_start_machines = true
min_machines_running = 1
processes = ['app']

[[http_service.checks]]
grace_period = "30s"
interval = "30s"
method = "GET"
timeout = "10s"
path = "/"

[http_service.concurrency]
type = "requests"
soft_limit = 150
hard_limit = 200

[[vm]]
memory = '1024mb'
cpu_kind = 'shared'
cpus = 2
```

### Dockerfile

```dockerfile
# Multi-stage build per ottimizzazione

# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY package.json ./
RUN npm install --legacy-peer-deps --ignore-scripts

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# Stage 3: Runner
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Security: non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/src/content ./src/content

# Permissions
RUN mkdir -p .next/cache
RUN chown -R nextjs:nodejs ./src/content ./.next

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js", "-H", "0.0.0.0"]
```

---

## 5. Routing e Pagine

### Route Groups

| Group | Prefix | Layout | Scopo |
|-------|--------|--------|-------|
| `(blog)` | `/insights` | Blog layout | Articoli pubblici |
| `(workspace)` | `/` | Workspace layout | Area protetta |
| `api` | `/api` | N/A | API Routes |

### Mappa Routes

```
/                           → Redirect a /dashboard o /login
├── /login                  → Pagina autenticazione
├── /admin                  → Admin dashboard
│   └── /admin/system       → System monitoring
├── /agents                 → Gestione agenti
│
├── /dashboard              → Dashboard principale
│   └── /analytics          → Analytics view
├── /chat                   → Chat Zantara
├── /whatsapp               → Integrazione WhatsApp
├── /email                  → Email (Zoho)
├── /clients                → Lista clienti
│   └── /new                → Nuovo cliente
├── /cases                  → Gestione casi
│   └── /new                → Nuovo caso
├── /knowledge              → Knowledge base
├── /team                   → Team management
├── /settings               → Impostazioni
│   └── /auto-crm           → Auto-CRM config
├── /portal                 → Client portal
│   ├── /company            → Info azienda
│   ├── /documents          → Documenti
│   ├── /messages           → Messaggi
│   ├── /settings           → Impostazioni
│   ├── /taxes              → Info fiscali
│   ├── /visa               → Info visa
│   └── /register           → Registrazione
│
└── /insights               → Blog home
    ├── /[category]         → Categoria (6 categorie)
    └── /[category]/[slug]  → Articolo singolo

API Routes:
├── /api/[...path]          → Proxy universale al backend
├── /api/blog/articles      → Lista articoli
├── /api/blog/articles/[category]/[slug]  → Articolo singolo
├── /api/blog/articles/[category]/[slug]/views  → Track views
├── /api/blog/ai-generate   → Genera articolo AI
├── /api/blog/newsletter    → Subscribe newsletter
└── /api/blog/newsletter/confirm  → Conferma email
```

### Dynamic Routes Parameters

| Route | Params | Valori |
|-------|--------|--------|
| `/insights/[category]` | category | `immigration`, `business`, `tax`, `property`, `lifestyle`, `digital-nomad` |
| `/insights/[category]/[slug]` | slug | Qualsiasi slug articolo valido |
| `/api/[...path]` | path | Array di segmenti URL |

---

## 6. Sistema di Componenti

### Gerarchia Componenti

```
App
├── RootLayout
│   ├── Providers (WebSocket, Theme, etc.)
│   └── Children
│       ├── WorkspaceLayout
│       │   ├── AppSidebar
│       │   ├── Header
│       │   └── PageContent
│       │       ├── DashboardPage
│       │       │   ├── StatsCard[]
│       │       │   ├── AiPulseWidget
│       │       │   ├── WhatsAppPreview
│       │       │   └── ComplianceWidget
│       │       ├── ChatPage
│       │       │   ├── ChatHeader
│       │       │   ├── ChatMessageList
│       │       │   │   └── MessageBubble[]
│       │       │   ├── ChatSourcesPanel
│       │       │   └── ChatInputBar
│       │       └── ...
│       └── BlogLayout
│           └── InsightsPage
│               ├── SearchBar
│               ├── CategoryNav
│               ├── ArticleGrid
│               │   └── ArticleCard[]
│               └── NewsletterForm
```

### Componenti Chat

| Componente | File | Props | Descrizione |
|------------|------|-------|-------------|
| `ChatHeader` | `chat/ChatHeader.tsx` | sessionId, onNewChat | Header con info sessione |
| `ChatInputBar` | `chat/ChatInputBar.tsx` | input, isLoading, onSend, onImageGenerate | Input multimodale |
| `ChatMessageList` | `chat/ChatMessageList.tsx` | messages, onFollowUp | Lista messaggi scrollabile |
| `MessageBubble` | `chat/MessageBubble.tsx` | message, isLast, onFollowUp | Singolo messaggio |
| `ChatSourcesPanel` | `chat/ChatSourcesPanel.tsx` | sources, isOpen | Panel sorgenti laterale |
| `ThinkingIndicator` | `chat/ThinkingIndicator.tsx` | status | Indicatore elaborazione |
| `FeedbackWidget` | `chat/FeedbackWidget.tsx` | messageId, onSubmit | Feedback thumbs |

### Componenti Blog

| Componente | File | Props | Descrizione |
|------------|------|-------|-------------|
| `ArticleCard` | `blog/ArticleCard.tsx` | article, index, variant | Card articolo |
| `ArticleGrid` | `blog/ArticleGrid.tsx` | articles, variant | Griglia articoli |
| `CategoryNav` | `blog/CategoryNav.tsx` | current, onChange | Filtri categoria |
| `MDXContent` | `blog/MDXContent.tsx` | source | Renderer MDX |
| `SearchBar` | `blog/SearchBar.tsx` | onSearch, placeholder | Ricerca articoli |
| `TableOfContents` | `blog/TableOfContents.tsx` | content | TOC auto-generato |
| `NewsletterForm` | `blog/NewsletterForm.tsx` | defaultCategories | Form iscrizione |

### Componenti Interattivi Blog

| Componente | Props | Uso in MDX |
|------------|-------|------------|
| `DecisionTree` | nodes, title, startNodeId | `<DecisionTree nodes={[...]} />` |
| `Calculator` | fields, title, formula | `<Calculator fields={[...]} />` |
| `ComparisonTable` | items, title | `<ComparisonTable items={[...]} />` |
| `JourneyMap` | steps, title | `<JourneyMap steps={[...]} />` |
| `InfoCard` | variant, title, children | `<InfoCard variant="warning">...</InfoCard>` |
| `Checklist` | items, title | `<Checklist items={[...]} />` |
| `ConfidenceMeter` | level, source, lastUpdated | `<ConfidenceMeter level="high" />` |
| `LegalDecoder` | sections, title | `<LegalDecoder sections={[...]} />` |
| `AskZantara` | context, placeholder | `<AskZantara context="visa" />` |
| `GlossaryTerm` | term, definition | `<GlossaryTerm term="KITAS">...</GlossaryTerm>` |

### Componenti UI Base

```typescript
// Importazione standard
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem } from '@/components/ui/select';
import { Table, TableHeader, TableBody, TableRow, TableCell } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Toast } from '@/components/ui/toast';
```

---

## 7. API Architecture

### API Client Base

```typescript
// /lib/api/client.ts

class ApiClientBase {
  protected baseUrl: string;
  protected token: string | null;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.NEXT_PUBLIC_API_URL;
    this.token = localStorage.getItem('auth_token');
  }

  protected async fetch<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': this.token ? `Bearer ${this.token}` : '',
        'X-Correlation-ID': generateCorrelationId(),
        ...options?.headers,
      },
      credentials: 'include',  // Per cookies
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }

    return response.json();
  }
}
```

### Domain APIs

| API Class | Endpoint Base | Metodi Principali |
|-----------|---------------|-------------------|
| `ChatApi` | `/api/agentic-rag` | `sendMessage()`, `sendMessageStreaming()` |
| `ConversationsApi` | `/api/bali-zero/conversations` | `list()`, `get()`, `save()`, `delete()` |
| `AuthApi` | `/api/auth` | `login()`, `logout()`, `register()` |
| `CrmApi` | `/api/crm` | `getClients()`, `createClient()`, `getCases()` |
| `KnowledgeApi` | `/api/knowledge` | `search()`, `getDocuments()`, `upload()` |
| `EmailApi` | `/api/email` | `getEmails()`, `sendEmail()`, `attachZoho()` |
| `TeamApi` | `/api/team` | `getMembers()`, `clockIn()`, `clockOut()` |
| `PortalApi` | `/api/portal` | `getData()`, `inviteClient()` |

### API Proxy Route

```typescript
// /app/api/[...path]/route.ts

export async function GET(request: NextRequest, { params }: RouteParams) {
  const path = (await params).path.join('/');
  const backendUrl = `${BACKEND_URL}/api/${path}`;

  // Forward request to backend
  const response = await fetch(backendUrl, {
    method: 'GET',
    headers: forwardHeaders(request),
    credentials: 'include',
  });

  // Handle streaming (SSE)
  if (response.headers.get('content-type')?.includes('text/event-stream')) {
    return new Response(response.body, {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  }

  return NextResponse.json(await response.json());
}
```

### Streaming Protocol (Chat)

```typescript
// Event types nel stream SSE
type StreamEvent =
  | { type: 'status'; data: string }
  | { type: 'tool_start'; data: { name: string; args: object } }
  | { type: 'tool_end'; data: { result: string } }
  | { type: 'reasoning_step'; data: { phase: string; message: string } }
  | { type: 'sources'; data: Source[] }
  | { type: 'metadata'; data: MessageMetadata }
  | { type: 'image'; data: { url: string } }
  | { type: 'content'; data: string }  // Chunk di risposta
  | { type: 'error'; data: string }
  | { type: 'done'; data: null };
```

---

## 8. State Management

### Custom Hooks

```typescript
// useChat - Main chat logic
const {
  input,
  setInput,
  messages,
  isLoading,
  handleSend,
  generateSessionId,
} = useChat();

// useChatMessages - Message state
const {
  messages,
  setMessages,
  addMessage,
  updateMessage,
  appendContent,
} = useChatMessages();

// useChatStreaming - Stream handling
const {
  isStreaming,
  currentSteps,
  sendStreamingMessage,
} = useChatStreaming();

// useConversations - History
const {
  conversations,
  currentConversation,
  loadConversations,
  saveConversation,
  deleteConversation,
} = useConversations();

// useMemoryContext - User memory
const {
  profileFacts,
  summary,
  counters,
  refresh,
} = useMemoryContext(userId);

// useWebSocket - Real-time
const {
  isConnected,
  connect,
  disconnect,
  send,
  subscribe,
} = useWebSocket();
```

### Providers

```typescript
// WebSocket Provider
<WebSocketProvider url={wsUrl}>
  <App />
</WebSocketProvider>

// Usage in components
const { send, subscribe } = useWebSocketContext();
```

### Local Storage Keys

| Key | Tipo | Descrizione |
|-----|------|-------------|
| `auth_token` | string | JWT token |
| `user_profile` | object | Cached user info |
| `chat_preferences` | object | Chat settings |
| `recent_conversations` | array | Recent chat IDs |

---

## 9. Sistema Blog (MDX)

### Struttura Articolo MDX

```mdx
---
id: "unique-id"
slug: "article-slug"
title: "Article Title"
subtitle: "Optional Subtitle"
excerpt: "200 character summary..."
coverImage: "/images/blog/category/slug.jpg"
coverImageAlt: "Image description"
category: "immigration"
tags: ["visa", "KITAS", "work-permit"]
author:
  id: "zantara-ai"
  name: "Zantara AI"
  avatar: "/images/zantara-avatar.png"
  role: "AI Research Assistant"
  isAI: true
publishedAt: "2025-01-01T00:00:00Z"
updatedAt: "2025-01-01T00:00:00Z"
status: "published"
featured: true
trending: false
readingTime: 12
viewCount: 1500
aiGenerated: true
aiConfidenceScore: 0.92
seoTitle: "SEO Title (60 chars max)"
seoDescription: "SEO Description (160 chars max)"
locale: "en"
---

import { InfoCard, DecisionTree, Calculator } from '@/components/blog/interactive';

# Main Title

<InfoCard variant="info" title="Important Note">
This is highlighted information.
</InfoCard>

## Section 1

Regular markdown content with **bold** and *italic*.

<DecisionTree
  title="Which Option?"
  nodes={[
    { id: "start", question: "Question?", options: [...] }
  ]}
/>

## Section 2

| Column 1 | Column 2 |
|----------|----------|
| Data     | Data     |

<Calculator
  title="Cost Calculator"
  fields={[
    { name: "amount", label: "Amount", type: "number" }
  ]}
  formula="amount * 1.1"
/>
```

### Categorie e Articoli

| Categoria | Slug | Articoli | Topics |
|-----------|------|----------|--------|
| Immigration | `immigration` | 26 | Visa, KITAS, work permits |
| Business | `business` | 27 | PT PMA, NIB, OSS, licensing |
| Tax | `tax` | 15 | NPWP, PPh, VAT, treaties |
| Property | `property` | 12 | Land, ownership, rental |
| Lifestyle | `lifestyle` | 14 | Banking, healthcare, living |
| Digital Nomad | `digital-nomad` | 5 | Remote work, coworking |

### MDX Processing Pipeline

```
MDX File → gray-matter (frontmatter) → next-mdx-remote/serialize → MDXContent render
                                              ↓
                                    Strip import statements
                                              ↓
                                    remarkGfm plugin (tables, etc.)
                                              ↓
                                    Custom component mapping
```

### API Endpoints Blog

| Endpoint | Method | Descrizione |
|----------|--------|-------------|
| `/api/blog/articles` | GET | Lista articoli con filtri |
| `/api/blog/articles?category=X` | GET | Filtra per categoria |
| `/api/blog/articles?featured=true` | GET | Solo featured |
| `/api/blog/articles?q=search` | GET | Cerca articoli |
| `/api/blog/articles/[cat]/[slug]` | GET | Singolo articolo |
| `/api/blog/articles/[cat]/[slug]/views` | POST | Track view |
| `/api/blog/newsletter` | POST | Subscribe |
| `/api/blog/ai-generate` | POST | Genera con AI |

---

## 10. Design System

### Color Palette

```css
:root {
  /* Background */
  --background: #141414;
  --background-secondary: #1a1a1a;
  --background-tertiary: #242424;

  /* Foreground */
  --foreground: #f5f5f5;
  --foreground-secondary: rgba(255, 255, 255, 0.7);
  --foreground-muted: rgba(255, 255, 255, 0.5);

  /* Brand */
  --accent: #2251ff;         /* Primary blue */
  --accent-hover: #4d73ff;
  --accent-light: rgba(34, 81, 255, 0.1);

  /* Semantic */
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;
  --info: #3b82f6;

  /* Borders */
  --border: rgba(255, 255, 255, 0.1);
  --border-hover: rgba(255, 255, 255, 0.2);
}
```

### Typography

```css
/* Fonts */
--font-sans: 'Geist', system-ui, sans-serif;
--font-mono: 'Geist Mono', monospace;
--font-serif: 'Georgia', serif;  /* Per headings blog */

/* Sizes */
--text-xs: 0.75rem;    /* 12px */
--text-sm: 0.875rem;   /* 14px */
--text-base: 1rem;     /* 16px */
--text-lg: 1.125rem;   /* 18px */
--text-xl: 1.25rem;    /* 20px */
--text-2xl: 1.5rem;    /* 24px */
--text-3xl: 1.875rem;  /* 30px */
--text-4xl: 2.25rem;   /* 36px */
```

### Spacing

```css
/* 4px grid */
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
--space-12: 3rem;     /* 48px */
--space-16: 4rem;     /* 64px */
```

### Component Variants

```typescript
// Button variants (CVA pattern)
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-lg font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-accent text-white hover:bg-accent-hover",
        secondary: "bg-white/10 text-white hover:bg-white/20",
        ghost: "hover:bg-white/5",
        destructive: "bg-error text-white hover:bg-error/90",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-lg",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  }
);
```

### Utility Classes

```css
/* Glass effect */
.glass {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Gradient text */
.text-gradient {
  background: linear-gradient(to right, var(--accent), #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Glow effect */
.glow {
  box-shadow: 0 0 20px rgba(34, 81, 255, 0.3);
}

/* Skeleton loading */
.skeleton {
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.05) 0%,
    rgba(255,255,255,0.1) 50%,
    rgba(255,255,255,0.05) 100%
  );
  animation: shimmer 2s infinite;
}
```

---

## 11. Integrazioni

### Backend RAG (Python)

```typescript
// Connessione
const BACKEND_URL = process.env.NUZANTARA_API_URL || 'https://nuzantara-rag.fly.dev';

// Endpoints principali
POST /api/agentic-rag/stream    // Chat streaming
POST /api/agentic-rag/query     // Chat sync
GET  /api/bali-zero/conversations/:user_id  // History
POST /api/bali-zero/conversations/:user_id  // Save
GET  /api/bali-zero/memory/context/:user_id // Memory
```

### WebSocket

```typescript
// Connessione
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'wss://nuzantara-rag.fly.dev/ws';

// Event handling
ws.on('open', () => console.log('Connected'));
ws.on('message', (data) => handleMessage(JSON.parse(data)));
ws.on('close', () => scheduleReconnect());

// Message types
{ type: 'ping' }
{ type: 'notification', data: {...} }
{ type: 'status_update', data: {...} }
```

### Sentry (Error Tracking)

```typescript
// Configurazione automatica via @sentry/nextjs
// File: sentry.client.config.ts, sentry.server.config.ts

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.1,
});
```

### Zoho (Email/CRM)

```typescript
// Integrazione via backend
POST /api/email/send           // Invia email
GET  /api/email/inbox          // Lista email
POST /api/email/zoho/connect   // Collega account
GET  /api/crm/contacts         // Contatti CRM
```

### Pollinations AI (Image Generation)

```typescript
// Generazione immagini
const imageUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}`;

// Usato in ChatInputBar per "Generate Image" feature
```

---

## 12. Autenticazione e Sicurezza

### Token Flow

```
1. User Login → POST /api/auth/login
                     ↓
2. Backend sets cookies:
   - nz_access_token (HttpOnly)
   - nz_csrf_token
                     ↓
3. Frontend stores in localStorage:
   - auth_token (for API calls)
                     ↓
4. Subsequent requests include:
   - Authorization: Bearer {token}
   - X-CSRF-Token: {csrf}
   - Cookie: nz_access_token=...
```

### Protected Routes

```typescript
// Middleware pattern (in page components)
useEffect(() => {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    router.push('/login');
  }
}, []);

// Server-side (API routes)
const token = request.cookies.get('nz_access_token');
if (!token) {
  return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
}
```

### CSRF Protection

```typescript
// Double-submit pattern
const csrfToken = getCookie('nz_csrf_token');
fetch('/api/...', {
  headers: {
    'X-CSRF-Token': csrfToken,
  },
});
```

### Security Headers

```typescript
// Impostati dal backend e forwarded
Content-Security-Policy: default-src 'self'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 13. Testing

### Setup

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.tsx'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
});
```

### Test Types

```bash
# Unit tests
npm run test

# Coverage report
npm run test:coverage

# E2E tests
npm run test:e2e

# Smoke tests
npm run test:smoke
```

### Test Examples

```typescript
// Component test
import { render, screen } from '@testing-library/react';
import { MessageBubble } from '@/components/chat/MessageBubble';

test('renders message content', () => {
  render(<MessageBubble message={{ content: 'Hello', role: 'user' }} />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});

// Hook test
import { renderHook, act } from '@testing-library/react';
import { useChatMessages } from '@/hooks/useChatMessages';

test('adds message', () => {
  const { result } = renderHook(() => useChatMessages());
  act(() => {
    result.current.addMessage({ content: 'Test', role: 'user' });
  });
  expect(result.current.messages).toHaveLength(1);
});

// API test
import { ChatApi } from '@/lib/api/chat';

test('sends message', async () => {
  const api = new ChatApi();
  const response = await api.sendMessage('Hello');
  expect(response.answer).toBeDefined();
});
```

---

## 14. Deployment

### Build Process

```bash
# Local build
npm run build

# Output
.next/
├── standalone/       # Self-contained server
├── static/           # Static assets
└── cache/            # Build cache
```

### Deploy to Fly.io

```bash
# Deploy
fly deploy

# Deploy con rebuild
fly deploy --remote-only

# Logs
fly logs

# Scale
fly scale count 2

# Secrets
fly secrets set KEY=value
```

### CI/CD (Manual)

```bash
# 1. Build locally
npm run build

# 2. Test
npm run test

# 3. Deploy
fly deploy --remote-only

# 4. Verify
curl https://nuzantara-mouth.fly.dev/api/blog/articles
```

### Rollback

```bash
# List releases
fly releases

# Rollback to previous
fly deploy --image registry.fly.io/nuzantara-mouth:previous-tag
```

---

## 15. Performance

### Ottimizzazioni Applicate

| Area | Tecnica | Impatto |
|------|---------|---------|
| Images | Next.js Image + remote patterns | -60% bandwidth |
| Code | Dynamic imports | -40% initial JS |
| Lists | React Virtual | Smooth scroll 1000+ items |
| Chat | SSE Streaming | Real-time response |
| Cache | localStorage | Faster subsequent loads |
| CSS | Tailwind purge | -80% CSS size |
| Build | Standalone output | Minimal Docker image |

### Metrics Target

| Metrica | Target | Attuale |
|---------|--------|---------|
| LCP | < 2.5s | ~2.0s |
| FID | < 100ms | ~50ms |
| CLS | < 0.1 | ~0.05 |
| TTI | < 3.8s | ~3.0s |

### Monitoring

```typescript
// Sentry Performance
Sentry.startTransaction({ name: 'chat-message' });

// Custom metrics
performance.mark('chat-start');
// ... operation
performance.mark('chat-end');
performance.measure('chat-duration', 'chat-start', 'chat-end');
```

---

## 16. Troubleshooting

### Errori Comuni

| Errore | Causa | Soluzione |
|--------|-------|-----------|
| `EACCES: permission denied` | Docker permissions | `RUN chown -R nextjs:nodejs ./.next` |
| `MDX parse error` | Complex JSX in MDX | Strip imports, use fallback |
| `WebSocket disconnect` | Network issues | Auto-reconnect logic |
| `401 Unauthorized` | Token expired | Refresh token or re-login |
| `Image not found` | Missing in public/ | Add image to correct folder |

### Debug Commands

```bash
# Check Fly.io logs
fly logs -a nuzantara-mouth

# SSH into machine
fly ssh console -a nuzantara-mouth

# Check machine status
fly status -a nuzantara-mouth

# Local dev with verbose
DEBUG=* npm run dev
```

### Health Checks

```bash
# API health
curl https://nuzantara-mouth.fly.dev/api/blog/articles | jq '.total'

# Image health
curl -I https://nuzantara-mouth.fly.dev/images/zantara-avatar.png

# WebSocket (manual test)
wscat -c wss://nuzantara-rag.fly.dev/ws
```

---

## Appendice A: Quick Reference

### Comandi Frequenti

```bash
# Development
npm run dev                    # Start dev server
npm run build                  # Production build
npm run lint                   # Lint code
npm run test                   # Run tests

# Deployment
fly deploy --remote-only       # Deploy to Fly.io
fly logs                       # View logs
fly status                     # Check status

# Blog
# Add article: create file in src/content/articles/{category}/{slug}.mdx
# Add image: save to public/images/blog/{category}/{slug}.jpg
```

### Import Paths

```typescript
// Components
import { Button } from '@/components/ui/button';
import { ChatInputBar } from '@/components/chat/ChatInputBar';
import { ArticleCard } from '@/components/blog/ArticleCard';

// Hooks
import { useChat } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';

// API
import { ChatApi } from '@/lib/api/chat';
import { ApiClientBase } from '@/lib/api/client';

// Types
import type { Message, Source } from '@/types';
import type { Article, ArticleCategory } from '@/lib/blog/types';

// Utils
import { cn } from '@/lib/utils';
import { TIMEOUTS, PAGINATION } from '@/constants/config';
```

### File Naming Conventions

```
Components:    PascalCase.tsx     (e.g., MessageBubble.tsx)
Hooks:         camelCase.ts       (e.g., useChat.ts)
Utils:         camelCase.ts       (e.g., utils.ts)
Types:         camelCase.ts       (e.g., types.ts)
API:           camelCase.ts       (e.g., chat.api.ts)
MDX:           kebab-case.mdx     (e.g., visa-guide-2025.mdx)
Images:        kebab-case.jpg     (e.g., golden-visa.jpg)
```

---

*Documentazione generata automaticamente da Zantara AI*
*Per aggiornamenti: modifica DOCUMENTATION.md nella root del progetto*
