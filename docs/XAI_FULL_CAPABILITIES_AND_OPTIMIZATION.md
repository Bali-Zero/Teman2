# xAI API — Full Capabilities & Optimization Guide for Nuzantara

> Tutto cio' che xAI offre e come sfruttarlo al massimo per il blitz X.
> Costo stimato: $0/mese (coperto da data sharing $150/mo credits).

---

## 1. MODELLI DISPONIBILI

| Modello                         | Contesto | Input $/M     | Output $/M | Cache $/M | Specialty                            |
| ------------------------------- | -------- | ------------- | ---------- | --------- | ------------------------------------ |
| **grok-4.20-reasoning**         | 2M       | $2.00         | $6.00      | $0.20     | Top tier, reasoning chain            |
| **grok-4.20-non-reasoning**     | 2M       | $2.00         | $6.00      | $0.20     | Top tier, diretto                    |
| **grok-4.20-multi-agent**       | 2M       | $2.00         | $6.00      | $0.20     | Orchestrazione multi-agente          |
| **grok-4-1-fast-reasoning**     | 2M       | **$0.20**     | **$0.50**  | $0.05     | **NOSTRO PICK** — 10x piu' economico |
| **grok-4-1-fast-non-reasoning** | 2M       | $0.20         | $0.50      | $0.05     | Fast senza reasoning                 |
| **grok-imagine-image**          | —        | **$0.02/img** | —          | —         | Immagini standard                    |
| **grok-imagine-image-pro**      | —        | **$0.07/img** | —          | —         | Immagini premium                     |
| **grok-imagine-video**          | —        | **$0.05/sec** | —          | —         | Video 1-15 sec                       |

### Scelta per noi:

- **Research/search**: `grok-4-1-fast-reasoning` ($0.20/$0.50) — 10x cheaper del top, stesse tools
- **Image generation**: `grok-imagine-image` ($0.02/img) — 50 immagini = $1
- **Video clips**: `grok-imagine-video` ($0.05/sec) — 10 sec clip = $0.50

### Tutti i modelli supportano:

- x_search (ricerca X/Twitter)
- web_search (ricerca web)
- Code execution (Python sandbox)
- File attachments
- Image understanding (vision)
- Video understanding (solo x_search)
- Function calling (custom tools)
- Collections search
- MCP tools

---

## 2. TOOLS DISPONIBILI

### 2.1 x_search (Ricerca X/Twitter)

**Parametri:**
| Parametro | Tipo | Descrizione | Limite |
|-----------|------|-------------|--------|
| `allowed_x_handles` | Array | Solo post da questi handle | Max 10 |
| `excluded_x_handles` | Array | Escludi post da questi handle | Max 10 |
| `from_date` | ISO8601 | Inizio periodo | YYYY-MM-DD |
| `to_date` | ISO8601 | Fine periodo | YYYY-MM-DD |
| `enable_image_understanding` | Boolean | Analizza immagini nei post | |
| `enable_video_understanding` | Boolean | Analizza video nei post | Solo x_search |

**Nota**: `allowed_x_handles` e `excluded_x_handles` sono mutuamente esclusivi.

**Modalita' di ricerca**: keyword search, semantic search, user search, thread fetch.

**Costo**: $5 per 1,000 chiamate.

### 2.2 web_search (Ricerca Web)

**Parametri:**
| Parametro | Tipo | Descrizione | Limite |
|-----------|------|-------------|--------|
| `allowed_domains` | Array | Solo da questi domini | Max 5 |
| `excluded_domains` | Array | Escludi questi domini | Max 5 |
| `enable_image_understanding` | Boolean | Analizza immagini trovate | |

**Costo**: $5 per 1,000 chiamate.

### 2.3 Image Generation

**Endpoint**: `POST /v1/images/generations`

```python
response = client.image.sample(
    model="grok-imagine-image",
    prompt="Professional infographic about Indonesia KBLI 2025...",
    n=4,                    # fino a 10 varianti
    aspect_ratio="16:9",    # o 9:16, 1:1, 4:3, etc.
    resolution="2k",        # 1k o 2k
    response_format="url"   # o "b64_json"
)
```

**Aspect ratio supportati**: 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 2:1, 1:2, 19.5:9, 20:9

**Image editing**: supporta fino a 5 immagini input per multi-image editing.

**Costo**: $0.02/img standard, $0.07/img pro.

### 2.4 Video Generation

**Endpoint**: Async (submit → poll → download)

```python
result = client.video.sample(
    model="grok-imagine-video",
    prompt="Professional business briefing animation...",
    duration=10,           # 1-15 secondi
    aspect_ratio="16:9",   # o 9:16, 1:1
    resolution="720p"      # o 480p (default, piu' veloce)
)
```

**Input**: testo, immagine→video, reference images, video editing, video extension.

**Costo**: $0.05/sec → 10 sec = $0.50, 15 sec = $0.75.

### 2.5 Code Execution (Python Sandbox)

Grok puo' eseguire codice Python server-side. Utile per:

- Generare grafici/chart con matplotlib
- Processare dati
- Calcoli complessi

### 2.6 Function Calling (Custom Tools)

Puoi definire fino a **200 custom tools** per request. Grok decide quando usarli.
Supporta parallel tool calls (multipli in una response).

---

## 3. BATCH API — 50% SCONTO

Per operazioni bulk (non real-time):

- **50% sconto** su tutti i token
- **Non conta verso rate limit**
- Workflow: submit → poll → retrieve results
- Tipicamente completato in <24h
- Supporta: text models (chat), images, video

**Per noi**: batch processing di 100+ query di ricerca = costa meta'.

Con batch: `grok-4-1-fast-reasoning` diventa $0.10/$0.25 per M token.

---

## 4. OTTIMIZZAZIONI PER IL NOSTRO USO

### 4.1 Massimizzare risultati per chiamata x_search

**Attuale** (01_grok_scraper.py): 1 query generica → ~8-16 risultati.

**Ottimizzato**: query specifiche + date filter + handle filter:

```python
# PRIMA (generico)
"What are people saying about KITAS visa delays in Bali?"

# DOPO (ottimizzato — piu' risultati, piu' pertinenti)
tools = [{
    "type": "x_search",
    "x_search": {
        "from_date": "2026-03-22",
        "to_date": "2026-03-29",
        "excluded_x_handles": ["balizero"]  # escludi noi stessi
    }
}]
input = "Find all posts discussing KITAS processing delays, KITAS rejection, or immigration office wait times in Indonesia. Include specific complaints, timelines mentioned, and any positive experiences. Return each post with its URL, author handle, and key complaint."
```

### 4.2 Combinare x_search + web_search in una request

```python
tools = [
    {"type": "x_search", "x_search": {"from_date": "2026-03-01"}},
    {"type": "web_search", "web_search": {"allowed_domains": ["ddtc.co.id", "cnbcindonesia.com"]}}
]
input = "Research the latest changes to Indonesia's KITAS processing. First search X for expat complaints and real experiences. Then search news sites for official announcements. Compare what people experience vs what the government says."
```

**Costo**: $0.01 (2 tool calls) + ~$0.001 tokens = ~$0.011 totale.

### 4.3 Image generation per social — batch ottimizzato

```python
# Genera 10 header images in un colpo solo
for topic in topics:
    response = client.image.sample(
        model="grok-imagine-image",
        prompt=f"Professional dark infographic header, topic: {topic}. "
               f"Background #0c0c0e, accent #d4845a gold, clean typography, "
               f"business consulting style, 16:9, no text overlay",
        n=3,  # 3 varianti per topic
        aspect_ratio="16:9",
        resolution="2k"
    )
```

**10 topic × 3 varianti = 30 immagini = $0.60**

### 4.4 Video clip per social

```python
# Genera 10-sec clip per teaser Article
result = client.video.sample(
    model="grok-imagine-video",
    prompt="Smooth animation: dark background fading to reveal gold text "
           "'KBLI 2025: The Clock Is Ticking' with subtle Indonesian batik "
           "pattern elements. Professional, premium business consulting feel.",
    duration=10,
    aspect_ratio="16:9",
    resolution="720p"
)
```

**1 clip 10 sec = $0.50**. 5 clip per settimana = $2.50.

### 4.5 Competitor monitoring automatizzato

```python
# Monitor competitor mentions con handle filter
tools = [{
    "type": "x_search",
    "x_search": {
        "allowed_x_handles": ["emerhub", "incikigroup", "sevenstonesindo", "letsmoveindo"],
        "from_date": "2026-03-22"
    }
}]
input = "What have these Indonesia business service companies posted recently? Analyze their content strategy, engagement levels, and any client complaints or praise."
```

### 4.6 Lead detection automatizzata

```python
tools = [{
    "type": "x_search",
    "x_search": {
        "from_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "to_date": datetime.now().strftime("%Y-%m-%d")
    }
}]
input = """Find people on X who in the last 24 hours:
1. Asked about setting up a company in Bali or Indonesia
2. Complained about visa processing or agents
3. Asked about KBLI codes or business licenses
4. Mentioned moving to Bali and needing business advice
Return each person's handle, their exact question, and suggested reply approach."""
```

**Questo gira ogni giorno come cron job → feed diretto al reply farming.**

### 4.7 Vision: analizza post competitor con immagini

```python
tools = [{
    "type": "x_search",
    "x_search": {
        "enable_image_understanding": True,
        "allowed_x_handles": ["emerhub"]
    }
}]
input = "Analyze Emerhub's recent posts including any images or infographics they shared. What visual style do they use? What topics get the most engagement?"
```

### 4.8 Video understanding: analizza video su X

```python
tools = [{
    "type": "x_search",
    "x_search": {
        "enable_video_understanding": True,
        "from_date": "2026-03-01"
    }
}]
input = "Find and analyze videos posted on X about Indonesia business setup, visa processing, or Bali property. What content performs best? What's missing?"
```

---

## 5. PIPELINE QUOTIDIANA OTTIMIZZATA

### Morning Intel Run (08:00 WITA) — ~$0.08/giorno

```
1. x_search: lead detection (chi ha chiesto di business/visa ieri?)     $0.005
2. x_search: competitor monitor (cosa hanno postato?)                   $0.005
3. x_search: trend detection (cosa sta trending su Indonesia business?) $0.005
4. web_search: regulatory news (nuove normative da fonti ufficiali)     $0.005
5. Grok reasoning: sintetizza tutto in daily brief                      $0.06
```

**Output**: Daily brief con lead list + competitor moves + trending topics + regulatory alerts.
**Costo**: ~$0.08/giorno = ~$2.40/mese (vs $150 credits disponibili).

### Weekly Content Generation — ~$0.80/settimana

```
1. Image generation: 5 header images per Articles/rubriche              $0.10
2. Image generation: 10 social cards/infografiche                       $0.20
3. Video: 2 clip teaser per Articles (10 sec ciascuno)                  $1.00
4. Research: deep dive su topic della settimana                         $0.10
```

**Costo**: ~$1.40/settimana = ~$5.60/mese.

### Monthly Total: ~$8/mese

Ampiamente entro i $150 free credits. Avanziamo ~$142/mese per altri usi.

---

## 6. CONFRONTO CON ALTERNATIVE

| Feature             | xAI x_search                    | X API search/recent | Exa            | Brave        |
| ------------------- | ------------------------------- | ------------------- | -------------- | ------------ |
| Costo               | $5/1K calls + data sharing free | $200/mo Basic       | $5/1K calls    | Free (2K/mo) |
| Ricerca X           | Nativa, deep                    | Nativa, basic       | Solo URL x.com | No           |
| Date filter         | Si                              | Si                  | Si             | Si           |
| Handle filter       | Si (10)                         | No                  | No             | No           |
| Image understanding | Si                              | No                  | No             | No           |
| Video understanding | Si                              | No                  | No             | No           |
| Web search          | Si (5 domini)                   | No                  | Si (deep)      | Si           |
| Semantic search     | Si                              | No                  | Si (forte)     | No           |
| Batch 50% off       | Si                              | No                  | No             | No           |
| Image gen           | Si ($0.02)                      | No                  | No             | No           |
| Video gen           | Si ($0.05/s)                    | No                  | No             | No           |

**xAI vince su tutto tranne Reddit** (dove Exa resta necessario).

---

## 7. COSE CHE NON STIAMO USANDO (ANCORA)

1. **Image generation via API** — possiamo generare header images programmaticamente
   invece di usare Grok Imagine manualmente su X
2. **Video generation** — clip teaser automatici per ogni Article
3. **Image understanding su post competitor** — analizza visual strategy competitor
4. **Video understanding** — analizza video content su X
5. **Code execution** — generare chart/infografiche con matplotlib via API
6. **Batch API** — 50% sconto per bulk research
7. **Multi-agent model** — orchestrazione di ricerche complesse
8. **Lead detection giornaliera** — cron job che trova chi chiede di business/visa
9. **Competitor monitoring giornaliero** — tracking automatico

---

---

## 8. AGGIORNAMENTO CRITICO: DATA SHARING PROGRAM

**Il programma data sharing da $150/mese e' stato DISCONTINUATO.**

Questo significa:

- I $25 free alla registrazione restano validi (30 giorni)
- Ma i $150/mese ricorrenti NON sono piu' disponibili per nuovi iscritti
- Il nostro costo reale sara' ~$8/mese dopo i $25 free

**Piano B**: $8/mese e' comunque minimo. Con i $25 free abbiamo ~3 mesi di runway
al ritmo attuale. Dopo, $8/mese e' accettabile.

---

## 9. SCOPERTE AGGIUNTIVE (dall'agente deep research)

### Multi-Agent Research (grok-4.20-multi-agent)

Una singola API call orchestra **4 o 16 agenti AI specializzati** in parallelo:

- 4 agenti (reasoning low/medium): ricerca rapida
- 16 agenti (reasoning high/xhigh): deep research multi-source
- Agenti specializzati in: search, data analysis, code/math, synthesis
- Usa tutti i tools server-side (web_search, x_search, code_execution)
- Solo il risultato dell'agente "leader" viene restituito
- **Costo**: $2.00/$6.00 per M token (top tier pricing)

**Per noi**: ideale per deep competitive intel e regulatory research mensili.

### Collections Search (RAG gestito da xAI)

- Upload PDF, Excel, CSV, codice → xAI li indicizza
- Semantic + keyword + hybrid search
- OCR e layout-aware parsing
- **$2.50 per 1,000 ricerche**
- Potremmo offloadare il KBLI/legal RAG qui come test

### Text-to-Speech ($4.20/M caratteri)

- 5 voci, 20+ lingue, speech tags (pause, risate, sussurri)
- REST + WebSocket streaming
- Potremmo generare audio version degli Articles

### Voice Agent ($0.05/min = $3/ora)

- WebSocket real-time, <1s latenza
- Supporta function calling, web_search, x_search durante la conversazione
- 100+ lingue
- Potenziale: customer service voice bot per Bali Zero

### Remote MCP Tools

- Connetti qualsiasi MCP server a Grok via API
- Potremmo collegare il nostro nuzantara-mcp → Grok analizza con i nostri 131 tools

### Prompt Caching

- Input cachato: $0.05/M (vs $0.20 normal) = **75% risparmio**
- Per query ripetitive con contesto fisso (es. system prompt KBLI)

### Cose che x_search NON puo' fare:

- No filtro engagement (min_likes, min_retweets)
- No filtro media type (solo immagini, solo video)
- No filtro lingua
- No ricerca Spaces
- No dati follower/profilo/analytics
- Per analytics serve ancora X API ($100-200/mo)

---

## 10. MATRICE COMPLETA: COSA USARE E QUANDO

| Bisogno                    | Tool xAI                     | Costo           | Alternativa           |
| -------------------------- | ---------------------------- | --------------- | --------------------- |
| Cercare tweet su topic     | x_search                     | $0.005/query    | X API $200/mo         |
| Cercare news regulatory    | web_search + allowed_domains | $0.005/query    | Exa $0.01             |
| Generare header image      | grok-imagine-image           | $0.02/img       | Fireworks $0.0003     |
| Generare video clip        | grok-imagine-video           | $0.50/10sec     | NLM Cinematic (Ultra) |
| Deep research multi-source | multi-agent (16 agenti)      | ~$0.50/query    | Gemini explore        |
| Analisi dati/chart         | code_execution (matplotlib)  | $0.005/call     | Locale Python         |
| RAG su documenti           | collections_search           | $0.0025/query   | Nostro Qdrant         |
| Audio di Articles          | TTS                          | $0.004/1K chars | NLM audio overview    |
| Bulk processing            | Batch API (50% off)          | meta' prezzo    | —                     |
| Lead detection             | x_search + date filter       | $0.005/query    | Manuale X Pro         |

_xAI API Optimization Guide v1.1 — 29 marzo 2026_
_Per: Nuzantara X Premium+ Blitz_
_Costo stimato: ~$8/mese ($25 free credits coprono primi ~3 mesi)_
