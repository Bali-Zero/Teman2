# 📚 FRONTEND NUZANTARA (MOUTH) - Indice Studio

> Guida completa per capire il frontend Next.js

---

## 🗺️ Mappa Documenti

| #   | Documento                                                | Contenuto          |
| --- | -------------------------------------------------------- | ------------------ |
| 0   | [FRONTEND_DEEP_STUDY.md](./FRONTEND_DEEP_STUDY.md)       | Overview completo  |
| 1   | [STUDY_01_CHAT_SYSTEM.md](./STUDY_01_CHAT_SYSTEM.md)     | Sistema Chat AI    |
| 2   | [STUDY_02_API_AND_STATE.md](./STUDY_02_API_AND_STATE.md) | API Client & State |

---

## 📊 Statistiche Codebase

```
mouth/src/
├── app/           →  ~50 pages/routes
├── components/    →  127 TSX files
├── hooks/         →  28 custom hooks
├── lib/           →  30+ modules
├── providers/     →  Context providers
└── types/         →  TypeScript defs
───────────────────────────────────────────────
TOTALE             →  ~30,000 LOC
```

---

## 🎯 Le 6 Aree del Frontend

```
1️⃣ APP (Routes)      → Pages, layouts, API routes
2️⃣ COMPONENTS        → 127 UI components
3️⃣ HOOKS             → 28 custom React hooks
4️⃣ LIB               → API client, utilities
5️⃣ PROVIDERS         → Context providers
6️⃣ TYPES             → TypeScript definitions
```

---

## 🔑 File Critici (Must-Read)

| File                                    | Perché            | Size |
| --------------------------------------- | ----------------- | ---- |
| `hooks/useChatPage.ts`                  | Chat orchestrator | 23KB |
| `components/chat/MessageBubble.tsx`     | Message display   | 21KB |
| `lib/api/client.ts`                     | Base API client   | 11KB |
| `components/chat/ThinkingIndicator.tsx` | AI thinking UI    | 25KB |
| `lib/ai-insights.tsx`                   | AI insights       | 19KB |
| `app/(workspace)/layout.tsx`            | Workspace layout  | 5KB  |

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────┐
│                   Pages/Routes                   │
│               (app/ directory)                   │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│                   Components                     │
│              (React UI Library)                  │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│                  Custom Hooks                    │
│            (State & Logic Layer)                 │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│                  API Client                      │
│              (Backend Communication)             │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│                   Backend                        │
│                (Nuzantara RAG)                   │
└─────────────────────────────────────────────────┘
```

---

## 📁 Route Groups (Next.js 14+)

| Group         | Path                           | Scopo            |
| ------------- | ------------------------------ | ---------------- |
| `(blog)`      | `/`, `/news`, `/services`      | Sito pubblico    |
| `(portal)`    | `/portal/*`                    | Portal clienti   |
| `(workspace)` | `/dashboard`, `/clients`, etc. | App team interno |

---

## 🧩 Component Categories

| Categoria    | Files | Descrizione       |
| ------------ | ----- | ----------------- |
| `ui/`        | 23    | Base UI (shadcn)  |
| `chat/`      | 19    | Chat interface    |
| `dashboard/` | 14    | Dashboard widgets |
| `crm/`       | 5     | CRM components    |
| `documents/` | 8     | Google Drive-like |
| `blog/`      | 10    | Blog/articles     |

---

## 🪝 Key Hooks

| Hook               | Purpose                |
| ------------------ | ---------------------- |
| `useChatPage`      | Main chat orchestrator |
| `useChatStreaming` | SSE streaming          |
| `useChatTTS`       | Text-to-speech         |
| `useDrive`         | Google Drive ops       |
| `useDashboardData` | Dashboard data         |
| `useWebSocket`     | Real-time connection   |

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
npm run test        # Unit (Vitest)
npm run e2e         # E2E (Playwright)

# Lint
npm run lint
```

---

## 📖 Ordine di Lettura Consigliato

### Giorno 1: Overview

- [ ] `FRONTEND_DEEP_STUDY.md`
- [ ] Esplora struttura `src/`

### Giorno 2: Chat System

- [ ] `STUDY_01_CHAT_SYSTEM.md`
- [ ] Leggi `useChatPage.ts`

### Giorno 3: API & State

- [ ] `STUDY_02_API_AND_STATE.md`
- [ ] Esplora `lib/api/`

### Giorno 4: Components

- [ ] Esplora `components/chat/`
- [ ] Esplora `components/dashboard/`

---

## 📚 Docs Esistenti

| Doc                | Size | Contenuto      |
| ------------------ | ---- | -------------- |
| `DOCUMENTATION.md` | 48KB | Full docs      |
| `CLAUDE.md`        | 5KB  | AI context     |
| `README.md`        | 9KB  | Overview       |
| `DRIVE_SYSTEM.md`  | -    | Documents page |

---

_Generato il 2026-01-28 | "UI/UX prima di tutto" 🎨_
