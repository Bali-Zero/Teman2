# ZANTARA Webapp - Note Progetto

## API Keys & Servizi

⚠️ **IMPORTANTE:** Le API keys NON devono essere committate nel repository. Usa variabili d'ambiente.

| Servizio         | Provider                  | Variabile d'Ambiente          | Note                                    |
| ---------------- | ------------------------- | ----------------------------- | --------------------------------------- |
| Image Generation | Google AI Studio (Imagen) | `NEXT_PUBLIC_GOOGLE_IMAGEN_API_KEY` | Configurata in `.env.local` (non committata) |
| RAG Backend      | nuzantara-rag.fly.dev     | Già configurato               | Backend remoto                           |

### Setup API Keys

1. Crea un file `.env.local` nella root di `apps/mouth/`
2. Aggiungi le variabili:
   ```bash
   NEXT_PUBLIC_GOOGLE_IMAGEN_API_KEY=your_api_key_here
   ```
3. **NON committare** `.env.local` (già in `.gitignore`)

---

## FUNZIONALITÀ NELLA WEBAPP

### 1. Login

- Endpoint: `/api/auth/login`
- Email + PIN → JWT Token
- Pagina: `/login`

### 2. Chat AI (principale)

- Endpoint: `/api/agentic-rag/query` (RAG completo + visione)
- Alternativa: `/api/agents/synthesis/cross-oracle` (multi-Oracle)
- WebSocket: `/ws` (streaming real-time)
- Pagina: `/chat`

### 3. Generazione Immagini

- Endpoint: `/api/v1/image/generate`
- Provider: Google Imagen
- UI: Bottone nella chat (accanto all'input)

### 4. History Conversazioni

- Endpoint: `/api/bali-zero/conversations/history`
- Save: `/api/bali-zero/conversations/save`
- UI: Sidebar sinistra con lista chat

### 5. Team Status

- Endpoint: `/api/team/members` (chi è online)
- Clock In: `/api/team/clock-in`
- Clock Out: `/api/team/clock-out`
- UI: Sidebar o header con avatar team online

### 6. Admin Dashboard (solo zero@balizero.com)

- Vede TUTTE le conversazioni di tutti
- Vede report team (clock in/out, ore lavorate) - NO email/whatsapp, solo dashboard
- Estrae insight per knowledge base
- Pagina: `/admin`

---

## FUNZIONALITÀ NEL BACKEND (NON in webapp per ora)

### Intel & News

| Endpoint              | Descrizione                  |
| --------------------- | ---------------------------- |
| `/api/intel/search`   | Cerca notizie in 8 categorie |
| `/api/intel/critical` | Alert notizie critiche       |
| `/api/intel/trends`   | Topic di tendenza            |

### Compliance & Scadenze

| Endpoint                        | Descrizione                  |
| ------------------------------- | ---------------------------- |
| `/api/agents/compliance/track`  | Traccia scadenze visti/tasse |
| `/api/agents/compliance/alerts` | Alert scadenze imminenti     |

### Document Ingestion

| Endpoint             | Descrizione                  |
| -------------------- | ---------------------------- |
| `/api/ingest/upload` | Upload PDF al knowledge base |
| `/api/legal/ingest`  | Ingest documenti legali      |

### Productivity

| Endpoint                              | Descrizione            |
| ------------------------------------- | ---------------------- |
| `/api/productivity/gmail/draft`       | Scrivi bozza email     |
| `/api/productivity/calendar/schedule` | Crea evento calendario |
| `/api/productivity/drive/search`      | Cerca su Google Drive  |

### Ricerca Autonoma

| Endpoint                          | Descrizione                    |
| --------------------------------- | ------------------------------ |
| `/api/agents/research/autonomous` | Ricerca approfondita AI-guided |

### Knowledge Graph

| Endpoint                              | Descrizione            |
| ------------------------------------- | ---------------------- |
| `/api/agents/knowledge-graph/extract` | Estrai entità da testo |

### Pricing

| Endpoint                        | Descrizione        |
| ------------------------------- | ------------------ |
| `/api/agents/pricing/calculate` | Calcola preventivi |

### Notifications

| Endpoint                  | Descrizione                  |
| ------------------------- | ---------------------------- |
| `/api/notifications/send` | Invia notifiche multi-canale |
| `/webhook/whatsapp/`      | Webhook WhatsApp             |
| `/webhook/instagram/`     | Webhook Instagram            |

---

## Decisioni Design

### Logo

- Sfondo nero interno al cerchio
- Anello bianco/argento 3D
- Mappa Indonesia rossa
- Testo "ZANTARA" bianco 3D

### Palette Colori

```css
--bg-primary: #18181b; /* Sfondo principale */
--bg-secondary: #27272a; /* Card, sidebar */
--bg-elevated: #3f3f46; /* Hover, elementi elevati */
--bg-input: #1f1f23; /* Input fields */
--accent-red: #dc2626; /* Accent dal logo */
--text-primary: #fafafa; /* Testo principale */
--text-secondary: #a1a1aa; /* Testo secondario */
```

### UI Chat

- Stile ChatGPT/Claude
- Bottone immagine accanto all'input
- History sidebar a sinistra
- Team online in sidebar o header

---

## Domini

- zantara.balizero.com → Webapp team (questa)
- ayo.balizero.com → Team portal
- my.balizero.com → Client portal

## Da Ricordare

- Memoria collettiva (Qdrant) = condivisa tra tutti
- History conversazioni (PostgreSQL) = privata per utente
- Admin vede tutto per nutrire il sistema
- Image Generation = Google Imagen, NON DALL-E
