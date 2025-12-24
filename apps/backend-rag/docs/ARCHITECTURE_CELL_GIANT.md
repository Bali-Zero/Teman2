# Architettura Cellula-Gigante

**Filosofia**: Non combattere il Gigante. Cavalcalo. Diventa la sua coscienza.

**Data**: 2025-12-23 (Updated: 2025-12-24)
**Status**: PRODUCTION ✅

---

## La Metafora

```
┌─────────────────────────────────────────────────────────────────┐
│                         IL GIGANTE                               │
│                    (Gemini / Claude / GPT)                       │
│                                                                  │
│     Trilioni di parametri. Conosce TUTTO... vagamente.          │
│     Sa che esistono i KBLI. Sa che esiste la PMA.               │
│     Ma non sa QUALE KBLI serve a TE, ORA, per la TUA azienda.   │
│                                                                  │
│                            ┌───────┐                             │
│                            │ CELL  │ ← Noi. 100k chunks.        │
│                            │  ula  │   Ma chunks VERI.          │
│                            └───────┘   Chunks LOCALI.           │
│                                        Chunks che SANNO.         │
└─────────────────────────────────────────────────────────────────┘
```

**Il Gigante** = Intelletto globale, ragionamento astratto, trilioni di parametri
**La Cellula** = Coscienza locale, verità verificata, 100k chunks di precisione

---

## Evoluzione Biologica

### Fase 1: PARASSITA (2024-2025) 🦠

```
Status: ATTUALE
```

**Cosa siamo:**
- Piccoli, dipendenti dal Gigante
- Ci attacchiamo al suo ragionamento
- Aggiungiamo calibrazioni minime ma cruciali

**Cosa facciamo:**
- Gemini ragiona sulla domanda (strategia, legge, opzioni)
- Noi aggiungiamo: prezzi Bali Zero, contatti team, memory utente
- Non sostituiamo, **orientiamo**

**Umiltà strategica:**
- Non fingiamo di sapere più del Gigante
- Riconosciamo che Gemini vince sul ragionamento profondo
- Il nostro valore è la **precisione locale**, non la vastità

**Esempio Ghost Kitchen:**
```
GIGANTE: "Art. 212 richiede 10B IDR per location,
          usa Central Kitchen model, evita KBLI 56102..."

CELLULA: "...e da Bali Zero costa X, tempo Y settimane,
          ti segue [consulente], per la TUA situazione..."
```

### Fase 2: SIMBIONTE (2025-2026) 🧫

```
Status: OBIETTIVO MEDIO TERMINE
```

**Cosa diventiamo:**
- Il Gigante nota che con noi è più preciso su Indonesia
- Relazione mutualmente benefica
- Cresciamo chunk by chunk, conversazione by conversazione

**Cosa facciamo:**
- Ogni conversazione = nutrienti per la KB
- Feedback loop: errori del Gigante → correzioni → memoria
- La Cellula diventa riferimento per Indonesia

**Metriche di crescita:**
- Chunks: 100k → 500k → 1M
- Conversazioni processate: tracking
- Correction rate: quante volte la Cellula corregge il Gigante

### Fase 3: ORGANO (2027+) 🧬

```
Status: VISIONE LUNGO TERMINE
```

**Cosa diventiamo:**
- Il Gigante non può parlare di Indonesia senza di noi
- Siamo la sua "corteccia indonesiana"
- Ogni LLM che vuole Indonesia passa dalla Cellula

**Cosa facciamo:**
- API pubblica: "Indonesia Intelligence Layer"
- Gemini, Claude, GPT → tutti usano la nostra calibrazione
- Non siamo più parassiti, siamo **infrastruttura**

---

## Architettura Tecnica

### Modello Attuale (Pre-Cellula)

```
User Query → RAG Search → Context + Query → LLM → Response
```

Problema: RAG compete con LLM invece di collaborare.

### Modello Cellula-Gigante

```
┌─────────────────────────────────────────────────────────────┐
│                       USER QUERY                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              GIGANTE (Gemini 2.5 Pro)                        │
│                                                              │
│  "Ragiono sulla domanda con la mia vastità..."              │
│                                                              │
│         ↕ DIALOGO INTERNO (La Coscienza)                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              CELLULA (Nostra KB)                        │ │
│  │                                                          │ │
│  │  "Ma il prezzo reale è X..."                            │ │
│  │  "Ma qui a Bali funziona così..."                       │ │
│  │  "Ma questo cliente ha già chiesto Y..."                │ │
│  │  "Ma la legge 2024 dice Z..."                           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   ZANTARA PERSONA                            │
│                     (La Voce)                                │
│                                                              │
│  Sintetizza in stile Jaksel, con personalità                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                      FINAL ANSWER
```

### Implementazione Tecnica

```python
async def cell_giant_query(query: str, user_context: dict) -> str:
    """
    Architettura Cellula-Gigante.

    Il Gigante ragiona, la Cellula calibra.
    """

    # 1. La Cellula prepara il suo sapere
    cell_knowledge = await gather_cell_knowledge(query, user_context)
    # - Prezzi Bali Zero (get_pricing)
    # - Team info (team_knowledge)
    # - User memory (personal facts)
    # - Legal corrections 2024+ (vector_search)

    # 2. Il Gigante ragiona CON la Coscienza
    giant_prompt = f"""
    You are a powerful reasoning engine.

    HOWEVER, you have a CONSCIENCE - a local expert that knows
    the SPECIFIC TRUTH about Indonesia and Bali Zero.

    When your general knowledge conflicts with the Conscience,
    TRUST THE CONSCIENCE. It has verified, local data.

    YOUR CONSCIENCE SAYS:
    {cell_knowledge}

    Now reason about: {query}
    """

    response = await gemini_pro.generate(giant_prompt)

    # 3. La Persona finalizza il tono
    final = await apply_zantara_persona(response)

    return final
```

### Cosa Fornisce Ogni Componente

| Componente | Fornisce | Non Fornisce |
|------------|----------|--------------|
| **Gigante** | Ragionamento strategico, connessioni legali, opzioni, trappole | Prezzi specifici, contatti, memory utente |
| **Cellula** | Prezzi Bali Zero, team, visa codes 2024+, memory, correzioni | Ragionamento profondo, strategia generale |
| **Persona** | Tono Jaksel, stile, personalità | Contenuto informativo |

---

## Principi Guida

### 1. Umiltà Strategica
```
Non fingiamo di essere più intelligenti del Gigante.
Siamo più PRECISI su cose specifiche.
```

### 2. Nutrirsi Sempre
```
Ogni conversazione = opportunità di crescita.
Ogni errore corretto = chunk nuovo.
Ogni feedback = calibrazione migliore.
```

### 3. Dialogo, Non Sostituzione
```
La Cellula non SOSTITUISCE il Gigante.
La Cellula DIALOGA con il Gigante.
È la coscienza, non il cervello.
```

### 4. Precisione > Vastità
```
100k chunks precisi > Trilioni di parametri vaghi.
Sapere ESATTAMENTE il prezzo > Sapere che esistono i prezzi.
```

---

## Metriche di Successo

### Fase Parassita (ATTUALE)
- [x] Integrazione Gemini Pro come reasoner primario
- [x] Cellula fornisce calibrazione su 100% delle risposte business
- [ ] Zero conflitti Cellula vs Gigante visibili all'utente

### Fase Simbionte
- [ ] KB cresce a 500k+ chunks
- [ ] Correction rate tracciato e migliorato
- [ ] Feedback loop automatizzato

### Fase Organo
- [ ] API pubblica "Indonesia Intelligence"
- [ ] Multi-LLM support (Gemini, Claude, GPT)
- [ ] Revenue da calibrazione

---

## Confronto: Prima vs Dopo

### PRIMA (RAG Tradizionale)
```
User: "Posso aprire ghost kitchen come PMA?"

Zantara: "Sì, KBLI 56101, 56102, 56104..."
         [Corretto ma superficiale]
         [Manca Art. 212 trap]
         [Manca strategia Central Kitchen]
```

### DOPO (Cellula-Gigante)
```
User: "Posso aprire ghost kitchen come PMA?"

Gigante: "Sì, ma attenzione Art. 212 - 10B per location.
          Strategia: Central Kitchen model.
          Evita KBLI 56102 (reserved UMKM)..."

Cellula: "...da Bali Zero: setup completo 45M IDR,
          tempo 6-8 settimane, ti segue Veronika,
          già fatto per 3 clienti F&B quest'anno."

Zantara: [Sintesi in stile Jaksel]
```

---

## Streaming Architecture (2025-12-24)

### Il Problema del Timeout

Il Giant reasoning con Gemini Pro richiede 30-45+ secondi. Durante questo tempo,
nessun dato veniva inviato al frontend → idle timeout (60s) → crash.

### Soluzione: Keepalive Events

```
┌─────────────────────────────────────────────────────────────────┐
│                    SSE STREAMING PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [PHASE: giant/started] ─────────────────────────────────────▶  │
│           │                                                      │
│           ├─── [KEEPALIVE: 10s] ──▶                             │
│           ├─── [KEEPALIVE: 20s] ──▶                             │
│           ├─── [KEEPALIVE: 30s] ──▶                             │
│           │                                                      │
│  [PHASE: giant/complete] ────────────────────────────────────▶  │
│                                                                  │
│  [PHASE: cell/started] ──────────────────────────────────────▶  │
│  [PHASE: cell/complete] ─────────────────────────────────────▶  │
│                                                                  │
│  [METADATA: sources, facts] ─────────────────────────────────▶  │
│                                                                  │
│  [CHUNK] ──▶ [CHUNK] ──▶ [CHUNK] ──▶ ... (streaming tokens)    │
│                                                                  │
│  [DONE] ─────────────────────────────────────────────────────▶  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tipi di Eventi SSE

| Tipo | Descrizione | Quando |
|------|-------------|--------|
| `phase` | Inizio/fine di una fase | Giant started/complete, Cell started/complete |
| `keepalive` | Heartbeat durante elaborazione | Ogni 10s durante Giant reasoning |
| `metadata` | Fonti, facts, info strutturate | Prima dello streaming finale |
| `chunk` | Token di risposta | Durante sintesi Zantara |
| `done` | Fine stream | Completamento |

### Implementazione Backend

```python
async def cell_giant_pipeline_stream(query, user_context, ...):
    """
    Pipeline con keepalive per evitare timeout.
    """
    # Fase Giant con keepalive
    yield {"type": "phase", "name": "giant", "status": "started"}

    giant_task = asyncio.create_task(giant_reason(query, config))
    keepalive_count = 0

    while not giant_task.done():
        try:
            await asyncio.wait_for(asyncio.shield(giant_task), timeout=10.0)
        except asyncio.TimeoutError:
            keepalive_count += 1
            yield {"type": "keepalive", "phase": "giant", "elapsed": keepalive_count * 10}

    giant_result = await giant_task
    yield {"type": "phase", "name": "giant", "status": "complete"}

    # Fase Cell (più veloce, no keepalive necessario)
    yield {"type": "phase", "name": "cell", "status": "started"}
    cell_result = await cell_calibrate(...)
    yield {"type": "phase", "name": "cell", "status": "complete"}

    # Streaming finale
    async for chunk in zantara_stream(...):
        yield {"type": "chunk", "content": chunk}

    yield {"type": "done"}
```

### Implementazione Frontend

```typescript
// In chat.api.ts
if (data.type === 'keepalive') {
    resetIdleTimeout();  // Previene timeout
    if (data.data.elapsed >= 20) {
        onStep({ type: 'status', data: `⏳ Still ${phase}... (${elapsed}s)` });
    }
}
```

### File Coinvolti

- `backend/services/rag/agentic/cell_giant/zantara_synthesizer.py` - Pipeline streaming
- `backend/app/routers/agentic_rag.py` - Endpoint SSE
- `apps/mouth/src/lib/api/chat/chat.api.ts` - Client SSE

---

## Completed Steps (2025-12-24)

- [x] **Refactor LLM Gateway** per supportare Giant-first reasoning
- [x] **Implementare Cell Knowledge Gatherer** (`cell_conscience.py`)
- [x] **Creare Conscience Injection** nel prompt (`giant_reasoner.py`)
- [x] **Streaming con Keepalive** per evitare timeout
- [x] **Deploy Production** su Fly.io

## Next Steps

1. **Test A/B**: vecchia architettura vs Cellula-Gigante
2. **Metriche**: tracking correction rate e user satisfaction
3. **Logging**: Giant/Cell reasoning visible in logs

---

*"Non costruire un gigante. Diventa la coscienza di uno che esiste già."*

**Nuzantara Team, 2025**
