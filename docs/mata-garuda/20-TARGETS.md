# Mata Garuda — Target & Intelligence Products

> Data: 2026-04-08 | Sessione: brainstorming iniziale

## Chi Riceve Cosa

### Consumatore 1: Zero (Owner)

**Bisogno**: visione completa e anticipazione. Sapere tutto prima che diventi un problema.

| Intelligence Product | Cosa contiene | Frequenza | Canale |
|---------------------|---------------|-----------|--------|
| Daily Briefing | Priority changes + market signals + noise summary | 07:00 WITA | TG privato |
| Regulation Alert | Semantic diff: "requisito X cambiato da A a B" con impact score | Real-time | TG privato |
| Contradiction Alert | "Articolo dice X, ma Zantara dice Y ai clienti" | Real-time | TG privato |
| OSINT Enrichment | Nuove menzioni target tracked, movimenti personale | Continuous | UI locale + TG |
| Weekly Strategic | Trend, pattern, raccomandazioni, competitor moves | Domenica 08:00 | TG privato + file |
| Source Health Report | Fonti disattivate, aggiunte, anomalie | Settimanale | TG privato |
| Autonomy Log | Decisioni L2 prese dal sistema | Settimanale | TG privato |

### Consumatore 2: Clienti Bali Zero (5000+)

**Bisogno**: "questa cosa mi riguarda?" Solo informazioni rilevanti al loro caso.

| Intelligence Product | Cosa contiene | Frequenza | Canale |
|---------------------|---------------|-----------|--------|
| Breaking Alert | Cambiamento normativo urgente che li tocca direttamente | Solo quando succede | WhatsApp broadcast + email |
| Weekly Newsletter | Top 5 notizie della settimana, curate per relevance | Venerdi | Email digest |
| Blog Updates | Long-form analysis su cambiamenti importanti | 2-3/settimana | balizero.com/news |

**Filtro**: articoli con business_impact > 0.6 per il topic del cliente (visa holder → visa news)

### Consumatore 3: Zantara AI (RAG Backend)

**Bisogno**: knowledge sempre aggiornato per rispondere con precisione.

| Intelligence Product | Cosa contiene | Frequenza | Canale |
|---------------------|---------------|-----------|--------|
| KB Update | Nuovi fatti verificati da T1 sources | Continuous | Qdrant upsert + KG edge |
| Contradiction Fix | Correzione automatica di info obsolete nel KB | Quando detected | Qdrant update + log |
| New Entities | Nuove normative, organizzazioni, requisiti | Quando detected | PostgreSQL + Qdrant |

### Consumatore 4: War Room (Content Pipeline)

**Bisogno**: topic rilevanti che interessano al pubblico, angoli giornalistici.

| Intelligence Product | Cosa contiene | Frequenza | Canale |
|---------------------|---------------|-----------|--------|
| Topic Selection | Top 3 temi dal briefing con angolo content | Mercoledi + Sabato | JSON per topic_selector |
| Trend Alert | Tema emergente con volume crescente | Quando detected | Trigger pipeline |

### Consumatore 5: Team (Damar, Surya)

**Bisogno**: task concreti derivati dall'intelligence.

| Intelligence Product | Cosa contiene | Frequenza | Canale |
|---------------------|---------------|-----------|--------|
| QA Task | "Verifica che queste 5 righe KB siano ancora corrette" | Quando contradiction | TG task a Surya |
| Design Brief | "Crea visual per questo topic" | Quando War Room produce | TG task a Damar |

### Consumatore 6: OSINT Nexus (Solo Zero, Blindato)

**Bisogno**: nuovi dati da fonti pubbliche che arricchiscono il graph.

| Intelligence Product | Cosa contiene | Frequenza | Canale |
|---------------------|---------------|-----------|--------|
| Entity Mentions | Menzioni di ufficiali/organizzazioni tracked | Continuous | garuda:osint stream |
| Procurement Updates | Nuovi tender LPSE con link a entita note | Quando detected | garuda:osint stream |
| Personnel Changes | Mutasi, pelantikan, rotasi | Quando detected | garuda:osint stream |

## Mappa Intelligence Products → Layer

```
LAYER 4 (Analyst Agents) produce:
  │
  ├─ Daily Briefing Agent
  │   └─ → Zero (TG), Zantara (KB update)
  │
  ├─ Regulation Alert Agent
  │   └─ → Zero (TG), Clienti (WhatsApp se impact > 0.8), Zantara (KB fix)
  │
  ├─ Contradiction Agent
  │   └─ → Zero (TG), Surya (QA task), Zantara (flag)
  │
  ├─ Weekly Digest Agent
  │   └─ → Zero (TG), Clienti (email newsletter)
  │
  ├─ War Room Topic Agent
  │   └─ → War Room (JSON), Damar (design brief)
  │
  ├─ OSINT Feed Agent
  │   └─ → Neo4j locale (BLINDATO)
  │
  └─ Source Health Agent
      └─ → Zero (TG report)
```

## [OPEN] Da approfondire

- Newsletter tool: Resend? SendGrid? Fly.io built-in?
- WhatsApp broadcast: limiti Meta API per broadcast non-template?
- Client segmentation: come mappare cliente → topic di interesse?
- Filtro privacy: assicurarsi che nessun dato OSINT finisca nei product clienti
