# Analisi Completa Pagine Zantara

**Data Analisi**: 2025-01-05  
**Sito**: https://zantara.balizero.com  
**Pagine Analizzate**: `/login`, `/chat`, `/dashboard`

---

## 📄 1. PAGINA /login

### File: `apps/mouth/src/app/login/page.tsx`

### Struttura e Componenti

**Layout**:
- Split-screen design: 35% sinistra (form) + 65% destra (immagine Kintsugi)
- Background nero (`#212222`)
- Full-screen height

**Componenti Principali**:

1. **Form di Login** (sinistra)
   - Input email (`name="email"`, `type="email"`)
   - Input PIN (`name="pin"`, `type="password"`)
   - Button "Authenticate" (`type="submit"`)
   - Label: "Identity" e "Security Key"
   - Placeholder: `user@zantara.id` e `••••••••`

2. **Overlay Stati**:
   - `ACCESS GRANTED`: Overlay bianco su nero con testo "ACCESS GRANTED"
   - `ACCESS DENIED`: Overlay rosso (#CE1126) con testo "ACCESS DENIED"
   - `authenticating`: Dimming del form (opacity 0.5)

3. **Brand Identity** (sinistra):
   - Logo: `/images/balizero-logo-clean.png`
   - Footer: "SYSTEM v5.4" + status "ONLINE" (pulsante ciano)

4. **Right Panel** (solo desktop):
   - Immagine: `/assets/login/kintsugi-stone.png`
   - Text overlay: "Order from the raw" + "NILAI"

### Stati e Logica

**State Management**:
```typescript
loginStage: 'idle' | 'authenticating' | 'success' | 'denied'
email: string
pin: string
```

**Flusso Login** (`handleLogin`):

1. **Pre-submit**:
   - Check: `loginStage !== 'idle'` → return early
   - Log console dettagliati
   - Sound: `play('auth_start')`
   - Set stage: `authenticating`

2. **API Call**:
   - `api.login(email, pin)`
   - Aspetta risposta

3. **Success** (200 OK):
   - Set stage: `success`
   - Sound: `play('access_granted')`
   - Determina redirect: `user.role === 'client' ? '/portal' : '/dashboard'`
   - Delay 1.5s → `window.location.replace(redirectTo)`

4. **Error**:
   - Set stage: `denied`
   - Sound: `play('access_denied')`
   - Auto-reset dopo 2s → `idle`

### Interazioni e Bottoni

**Button "Authenticate"**:
- Disabilitato quando `loginStage !== 'idle'`
- Styling: `bg-white/5 hover:bg-[#CE1126]`
- Icon: ArrowRight (ciano, diventa bianco su hover)
- Glow effect solo su `idle`

**Input Fields**:
- Disabilitati su `loginStage !== 'idle'`
- Sound on focus: `play('focus')`
- Autofill styling custom (nero con testo bianco)

### API Calls

**Endpoint**: `/api/auth/login` (via `api.login()`)
- Method: POST
- Body: `{ email, pin }`
- Response: `{ user, access_token }`

### Accessibilità e UX

✅ **Punti di Forza**:
- Stati visivi chiari (granted/denied/authenticating)
- Feedback audio
- Disabilitazione form durante autenticazione
- Redirect basato su ruolo utente

⚠️ **Possibili Problemi**:
- Timeout hardcoded (1.5s) potrebbe essere troppo breve
- Nessuna validazione email lato client prima del submit
- `window.location.replace` forza reload completo (potrebbe essere evitato con Next.js router)

---

## 💬 2. PAGINA /chat

### File: `apps/mouth/src/app/chat/page.tsx` (1329 righe)

### Struttura e Layout

**Layout Generale**:
- Full-screen (`h-screen`)
- Background scuro (`#202020`)
- Flex layout: Sidebar (sinistra, fixed) + Main content (destra)

**Componenti Principali**:

1. **Sidebar** (width: 288px, `w-72`):
   - Header: Logo + "Zantara" + close button
   - "New Chat" button
   - Lista conversazioni (max 10)
   - Footer: Search Docs, Settings, Help, Dashboard link

2. **Main Header** (fixed top):
   - Menu button (apre sidebar)
   - Clock In/Out toggle (Online/Offline)
   - Message counter
   - Logo centrale
   - Notifications bell
   - User avatar + name dropdown

3. **Messages Area**:
   - Welcome screen (se nessun messaggio)
   - Lista messaggi (user/assistant)
   - Auto-scroll al bottom
   - ThinkingIndicator durante streaming

4. **Input Bar** (fixed bottom):
   - Action buttons: Paperclip (attach), Sparkles (image gen), Mic (voice), Camera (screenshot)
   - Textarea (multiline)
   - Send button (con loading state)
   - Image preview area (se allegate)
   - Keyboard shortcuts hint

### Stati e State Management

**Core States**:
```typescript
messages: OptimisticMessage[]
sessionId: string
currentStatus: string (per streaming)
input: string
thinkingElapsedTime: number
streamingSteps: Array<{type, data, timestamp}>
```

**UI States**:
```typescript
sidebarOpen: boolean
userName: string
userAvatar: string | null
isInitialLoading: boolean
isSearchDocsOpen: boolean
toast: {message, type} | null
isImageGenOpen: boolean
imageGenPrompt: string
attachedImages: Array<{id, base64, name, size}>
playingMessageId: string | null (TTS)
ttsLoading: string | null
```

**Hooks Custom**:
- `useConversations()`: gestione lista conversazioni
- `useTeamStatus()`: clock in/out
- `useAudioRecorder()`: registrazione vocale
- `useOptimistic()`: per messaggi ottimistici

### Funzionalità Principali

#### 1. **Invio Messaggi** (`handleSend`):

**Flusso**:
1. Validazione: text OR immagini richiesti
2. Crea `userMessage` (ottimistico)
3. Crea `assistantMessage` (pending, streaming)
4. Call `api.sendMessageStreaming()`:
   - `onChunk`: aggiorna content in tempo reale
   - `onDone`: finalizza messaggio, salva conversazione
   - `onError`: mostra errore
   - `onStep`: traccia steps (thinking, tool_call, observation, status)
5. Supporta immagini allegate (base64)
6. Supporta conversation history per context

#### 2. **Gestione Conversazioni**:

- `handleNewChat`: reset messages, nuovo sessionId
- `handleConversationClick`: carica conversazione esistente
- `handleDeleteConversation`: elimina conversazione

#### 3. **Audio/Voice**:

- **Recording**: `handleMicClick` → `startRecording()` / `stopRecording()`
- **Transcription**: useEffect processa `audioBlob` → `api.transcribeAudio()`
- **TTS**: `handleTTS()` → `api.generateSpeech()` → riproduci audio

#### 4. **Image Generation**:

- Modal per prompt immagine
- Submit → inserisce nel textarea: `Genera un'immagine: {prompt}`
- Backend genera immagine → mostra in messaggio

#### 5. **Image Attachments**:

- Upload multiplo (max 5 immagini, max 10MB ciascuna)
- Preview prima dell'invio
- Rimozione individuale

### Interazioni e Bottoni

**Header**:
- `Menu` → toggle sidebar
- `Clock In/Out` → `toggleClock()` (Online/Offline status)
- `Bell` → notifications (UI only)
- `User Avatar` → upload avatar (hidden file input)

**Sidebar**:
- `New Chat` → `handleNewChat()`
- `Conversation Item` → `handleConversationClick(id)`
- `Trash Icon` (hover) → `handleDeleteConversation(id)`
- `Search Docs` → apre `SearchDocsModal`
- `Dashboard` → `router.push('/dashboard')`

**Input Bar**:
- `Paperclip` → `handleImageButtonClick()` (apre file picker)
- `Sparkles` → `setIsImageGenOpen(true)`
- `Mic` → `handleMicClick()` (toggle recording)
- `Camera` → `handleScreenshotClick()` (file picker)
- `Send` → `handleSend()` (disabled se empty o pending)

**Messaggi**:
- `Copy` → copia testo
- `Volume2/Square` → TTS toggle (play/stop)
- `ThumbsUp/Down` → feedback (UI only, non implementato)
- `RefreshCw` → regenerate (UI only, non implementato)
- `Follow-up Questions` → click → invia automaticamente

### API Calls

**Principali Endpoints**:
- `api.sendMessageStreaming()`: streaming chat
- `api.getConversation(id)`: carica conversazione
- `api.getConversations()`: lista conversazioni
- `api.deleteConversation(id)`: elimina
- `api.transcribeAudio(blob, mimeType)`: trascrizione
- `api.generateSpeech(text, voice)`: TTS
- `api.getProfile()`: profilo utente
- `api.getClockStatus()`: stato clock
- `api.toggleClock()`: toggle clock

### Keyboard Shortcuts

- `Enter` → invia messaggio
- `Shift+Enter` → nuova riga

### Possibili Problemi

⚠️ **Potenziali Issue**:
1. **Sidebar mobile**: `translate-x-full` su mobile potrebbe non funzionare perfettamente
2. **Audio recording**: validazione `audioBlob.size < 1000` potrebbe essere troppo restrittiva
3. **Image upload**: limite 10MB potrebbe essere troppo per mobile
4. **TTS cleanup**: audioRef potrebbe non essere sempre pulito correttamente
5. **Follow-up questions**: UI presente ma non sempre popolata da backend
6. **Toast auto-dismiss**: 3s potrebbe essere troppo breve per errori importanti

---

## 📊 3. PAGINA /dashboard

### File: `apps/mouth/src/app/(workspace)/dashboard/page.tsx`

### Struttura e Layout

**Layout Generale**:
- Full-width container (`space-y-8`)
- Grid layout responsive
- Background ereditato dal layout workspace

**Componenti Principali**:

1. **System Status Banner** (condizionale):
   - Mostrato solo se `systemStatus === 'degraded'`
   - Warning banner giallo con icona AlertTriangle

2. **Zero-Only Widgets** (solo per `zero@balizero.com`):
   - **Analytics Dashboard Link**: card quadrata → `/dashboard/analytics`
   - **AiPulseWidget**: Zantara v6.0 pulse
   - **AutoCRMWidget**: widget CRM
   - **FinancialRealityWidget**: revenue e growth (condizionale se revenue presente)
   - **NusantaraHealthWidget**: health map sistema
   - **GrafanaWidget**: observability metrics

3. **AutoCRMWidget** (per tutti):
   - Grid 1 colonna (non-zero) o 2 colonne (zero)

4. **Stats Cards Grid** (4 cards):
   - Active Cases → `/cases`
   - Critical Deadlines → `/cases`
   - Unread Signals → `/whatsapp`
   - Session Time → `/team`

5. **Content Grid** (2 colonne):
   - **PratichePreview**: lista pratiche attive
   - **WhatsAppPreview**: lista messaggi WhatsApp

### Stati e State Management

**Core States**:
```typescript
isLoading: boolean
userEmail: string
systemStatus: 'healthy' | 'degraded'
stats: DashboardStats
cases: PraticaPreview[]
whatsappMessages: WhatsAppMessage[]
```

**DashboardStats Interface**:
```typescript
{
  activeCases: number
  criticalDeadlines: number
  whatsappUnread: number
  hoursWorked: string
  revenue?: { total_revenue, paid_revenue, outstanding_revenue }
  growth?: number
}
```

### Data Loading (`loadDashboardData`)

**API Calls (Promise.allSettled)**:

1. `api.crm.getPracticeStats()` → stats pratiche
2. `api.crm.getInteractionStats()` → stats interazioni
3. `api.crm.getPractices({ status: 'in_progress', limit: 5 })` → pratiche attive
4. `api.crm.getInteractions({ interaction_type: 'whatsapp', limit: 5 })` → WhatsApp recenti
5. `api.crm.getUpcomingRenewals(30)` → scadenze
6. `api.getClockStatus()` → ore lavorate
7. `api.crm.getRevenueGrowth()` → revenue (solo zero)

**Error Handling**:
- `Promise.allSettled`: gestisce fallimenti individuali
- Fallback values per ogni API call
- `systemStatus` = `degraded` se almeno una chiamata fallisce

**Data Transformation**:
- Practices → `PraticaPreview[]` (mapping campi)
- Interactions → `WhatsAppMessage[]` (mapping campi)
- Stats aggregati → `DashboardStats`

### Componenti Widget Importati

**Dashboard Components** (da `@/components/dashboard`):

1. **StatsCard**:
   - Icon, title, value
   - Link opzionale (`href`)
   - Varianti: `default`, `warning`, `danger`, `success`
   - Accent colors: `blue`, `teal`, `amber`, `purple`, `pink`, `emerald`, `cyan`

2. **PratichePreview**:
   - Lista pratiche
   - Loading state
   - Click → naviga a `/cases/[id]`

3. **WhatsAppPreview**:
   - Lista messaggi
   - `onDelete` callback
   - Loading state
   - Click → naviga a conversazione

4. **AiPulseWidget**:
   - Props: `systemAppStatus`, `oracleStatus`

5. **AutoCRMWidget**:
   - Nessuna prop richiesta

6. **FinancialRealityWidget**:
   - Props: `revenue`, `growth`

7. **NusantaraHealthWidget**:
   - Props: `className` (opzionale)

8. **GrafanaWidget**:
   - Props: `className` (opzionale)

### Interazioni e Bottoni

**Stats Cards**:
- Click → naviga a `href` (Link component)
- Hover effects

**Widgets**:
- **Analytics Dashboard**: Link → `/dashboard/analytics`
- **PratichePreview**: click pratica → `/cases/[id]`
- **WhatsAppPreview**: delete button → `onDelete(id)` → API delete

### Access Control

**Role-Based Rendering**:
- `isZero = userEmail === 'zero@balizero.com'`
- Se `isZero`: mostra widget aggiuntivi (Analytics, Financial, Nusantara, Grafana)
- Se `!isZero`: solo AutoCRM + Stats + Content Grid

### Performance e Loading

**Loading States**:
- `isInitialLoading`: mostra spinner generale
- Componenti individuali gestiscono loading states
- Stats cards mostrano `-` durante loading

**Data Fetching**:
- Tutte le chiamate in parallelo (`Promise.allSettled`)
- Nessun polling automatico (solo on mount)
- Error boundaries gestiti con fallback values

### Possibili Problemi

⚠️ **Potenziali Issue**:
1. **No refresh automatico**: dati vengono caricati solo al mount
2. **Error handling silenzioso**: fallimenti mostrano solo banner degradato, ma dati potrebbero essere inconsistenti
3. **System status**: `degraded` è binario, non graduale
4. **Revenue widget**: condizionale solo per zero, ma revenue potrebbe essere utile anche per altri admin
5. **WhatsApp delete**: callback inline, potrebbe essere ottimizzato

---

## 🔍 ANALISI COMPARATIVA

### Coerenza UI/UX

✅ **Punti di Forza**:
- Design system consistente (colori, spacing, typography)
- Loading states uniformi
- Error handling strutturato

⚠️ **Inconsistenze**:
- Login usa `window.location.replace`, Chat/Dashboard usano Next.js router
- Login ha feedback audio, altre pagine no
- Dashboard non ha polling, Chat ha real-time updates

### Architettura API

✅ **Pattern Comuni**:
- Tutte usano `api.*` wrapper
- Error handling consistente
- Type safety con TypeScript

⚠️ **Differenze**:
- Login: singola chiamata sincrona
- Chat: streaming con callbacks multipli
- Dashboard: batch calls con `Promise.allSettled`

### Performance

✅ **Ottimizzazioni**:
- Chat: `useOptimistic` per UI instantanea
- Dashboard: parallel fetching
- Lazy loading immagini

⚠️ **Possibili Miglioramenti**:
- Dashboard: aggiungere polling o refresh button
- Chat: debouncing per typing indicators
- Login: validazione lato client prima del submit

---

## 📝 RACCOMANDAZIONI

### Priorità Alta

1. **Login**:
   - Aggiungere validazione email lato client
   - Rendere timeout configurabile o basato su risposta API

2. **Chat**:
   - Implementare cleanup completo audio/TTS
   - Aggiungere debouncing per input
   - Gestire edge cases audio recording (permessi negati, formato non supportato)

3. **Dashboard**:
   - Aggiungere refresh button o polling opzionale
   - Migliorare error reporting (mostrare quali API hanno fallito)
   - Considerare cache per dati che cambiano poco

### Priorità Media

1. **Coerenza navigazione**: standardizzare su Next.js router
2. **Error messages**: migliorare UX per errori specifici
3. **Loading states**: uniformare animazioni e tempi

### Priorità Bassa

1. **Accessibilità**: aggiungere ARIA labels dove mancanti
2. **Analytics**: tracking eventi utente
3. **Testing**: test E2E per flussi critici

---

**Fine Analisi**

