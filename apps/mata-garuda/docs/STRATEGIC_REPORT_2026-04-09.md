# MATA GARUDA — Report Strategico

> Generato: 2026-04-09 | Autore: Claude Opus + Zero
> Basato su: audit completo codebase + ricerca OSINT esaustiva

---

## 1. STATO REALE (dall'audit)

### Cosa esiste e funziona

- **3 agenti** registrati: Dummy Agent (template), Meta Agent (manager), Regulation Watcher (operativo)
- **12 tool** registrati: 5 meta, 3 scraper, 4 stream
- **105 test** pass (7.17s)
- **Cron daily** attivo: LaunchAgent 06:00 WITA, TCC-safe bridge
- **Lamarckian feedback loop** implementato: retry, feedback, GENOME mutation, fitness tracking, auto-revert
- **Path firewall** OSINT blindato enforced
- **Multi-account fallback** per CLI runtime (3 OAuth token)

### Cicli APERTI

| Ciclo | Problema |
|-------|---------|
| `garuda:raw` stream | Ha dati (10 reg) ma **nessun consumer** — scraping nel vuoto |
| Meta Agent | Ha tool ma **nessuna logica di business** operativa |
| Escalation Lamarckian | È un messaggio di testo, non un'azione automatica |
| GENOME constraints | Documentazione, non enforced a runtime |

### Cicli CHIUSI

| Ciclo | Stato |
|-------|-------|
| CLI → Agent → case_resolved | ✅ 3/3 success |
| Scrape → Publish → Verify stream | ✅ 10 items garuda:raw |
| GENOME mutation → auto-revert | ✅ Testato (mai triggerato, 0 fallimenti) |

---

## 2. SCOPERTE DALLA RICERCA

### Dataset aperti già esistenti

| Fonte | Regolamenti | Tipo | Auth |
|-------|-------------|------|------|
| **Pasal.id API** | 40.143 reg, 937.155 articoli | REST JSON, AGPL-3.0 | Nessuna |
| **API JDIH Perpusnas** | Aggregatore nazionale JDIH | REST JSON | Token GET |
| **Open-Technology-Foundation** | 5.817 testi, SQLite 1.1GB | Download | Nessuna |

Queste tre fonti rendono **inutile** scrapare 15 siti JDIH con regex custom.

### Mappa completa fonti (per priorità)

**TIER 1 — Governative primarie (alta priorità, basso rumore)**

| Fonte | URL | Scrapabilità | Priorità |
|-------|-----|-------------|----------|
| peraturan.go.id | peraturan.go.id/harmonpusat | ALTA — curl+regex | GIÀ FATTO |
| API JDIH Perpusnas | api-jdih.perpusnas.go.id | ECCELLENTE — unica API gov | MASSIMA |
| JDIH Kemenkumham | jdih.kemenkumham.go.id | Da verificare | ALTA |
| JDIH Bali Province | jdih.baliprov.go.id | 404 su Perda (URL cambiato) | ALTISSIMA per Bali |
| Bank Indonesia | bi.go.id/en/publikasi/peraturan | MEDIA — SharePoint | ALTA per fintech |
| OJK | ojk.go.id/en/regulasi | MEDIA — SharePoint | ALTA per finanza |
| Pajak/DJP | pajak.go.id | Da verificare | ALTISSIMA per business |
| JDIH Kemenkeu | jdih.kemenkeu.go.id | Da verificare | ALTA |
| JDIH Kemnaker | jdih.kemnaker.go.id | Da verificare | ALTA per assunzioni |
| Imigrasi | imigrasi.go.id | BASSA — sito informativo | MEDIA |

**TIER 2 — Aggregatori privati (medio, alto valore editoriale)**

| Fonte | Contenuto | Priorità |
|-------|-----------|----------|
| **Pasal.id** | 40K reg, API REST pubblica, MCP server | MASSIMA |
| **DDTCNews** | News fiscale quotidiana | ALTA |
| DDTC Perpajakan | Documentazione fiscale | ALTA |

**TIER 3 — Internazionali (bassa priorità, alta qualità)**

ASEAN Briefing, EY Tax Alerts, World Bank — utili come reference, non per monitoring.

**TIER 4 — YouTube/Social (per NLM ingestion)**

Video consulenti visa/tax (LetsMoveIndonesia, BaliLegals, etc.) — NON fonti primarie, utili per early signal via NLM.

### Cosa NON fare

- **NON scrapare Hukumonline** — a pagamento, Pasal.id è migliore e gratis
- **NON scrapare OSS/BKPM** — sistema transazionale, non database
- **NON monitorare social media** — rumore puro
- **NON costruire NLP custom** — `claude --print` con buon prompt batte tutto
- **NON scrapare 15 siti JDIH** — l'API Perpusnas li aggrega già
- **NON inseguire completezza** — servono ~200 reg/anno rilevanti su 500+

---

## 3. PIPELINE COMPLETA — 7 Layer

```
L1 COLLECTION ──→ L2 DEDUP/NORM ──→ L3 CLASSIFY ──→ L4 RELEVANCE
    ↑                                                      ↓
    │                                                 L5 ANALYSIS
    │                                                      ↓
L7 MAINTENANCE ←── L6 ALERT/PRODUCE ←─────────────────────┘
```

| Layer | Cosa fa | Agente | Stato |
|-------|---------|--------|-------|
| **L1 Collection** | Multi-source harvesting | Regulation Watcher + nuovi | PARZIALE |
| **L2 Dedup/Norm** | SHA256 dedup, schema unificato, SQLite KB | Normalizer | MANCA |
| **L3 Classify** | Tag automatici (immigration, tax, labor...) | Classifier | MANCA |
| **L4 Relevance** | Score 1-5 per "PT PMA a Bali" | Relevance Scorer | MANCA |
| **L5 Analysis** | Summary, impact assessment, cross-ref | Analyst | MANCA |
| **L6 Alert/Produce** | TG alert, digest, NLM briefing audio | Distributor | MANCA |
| **L7 Maintenance** | Status check, decay, archival | Maintainer | MANCA |

### Pesi di rilevanza per il caso d'uso

| Ambito | Peso |
|--------|------|
| Immigration/Visa | 5 |
| Tax/Fiscal | 5 |
| Investment/Licensing | 4 |
| Labor/Manpower | 4 |
| Provincial Bali | 4 |
| Financial/Banking | 3 |
| Property | 3 |
| Environmental | 2 |
| Procurement | 1 |

---

## 4. NLM — Potenziale non sfruttato

| Capability | Uso per Mata Garuda |
|-----------|-------------------|
| YouTube ingestion | Early signal da video consulenti visa/tax |
| Cross-notebook query | Collegare normative di ministeri diversi |
| Audio briefing | Podcast settimanale per Zero |
| Source clustering | Scoprire pattern normativi (es: "7 reg fintech in 3 mesi") |

Notebook dedicati: Tax, Immigration, Investment, Labor, Bali Provincial.

---

## 5. RISCHI E FAILURE MODES

| Rischio | Probabilità | Mitigazione |
|---------|------------|-------------|
| **Information overload** | ALTA | Relevance scoring implacabile — è l'elemento critico |
| Cambio struttura HTML | MEDIA | HTML shape monitor + privilegiare API su scraping |
| Anti-scraping .go.id | BASSA | curl con UA realistico, delay 2-5s, max 50 req/giorno/sito |
| Regolamenti revocati | MEDIA | Campo status in KB, check mensile via Pasal.id API |
| Rate limiting | BASSA | Volume basso (50-100 pagine/giorno totali) |

---

## 6. PIANO DI ESECUZIONE — 5 Fasi

### Fase 1: Chiudere il ciclo aperto (2 sprint) — PRIORITÀ MASSIMA

1. **SQLite KB locale** — schema persistente
2. **Normalizer agent** — legge garuda:raw, dedup, normalizza, scrive in SQLite
3. **Relevance Scorer agent** — `claude --print` per score 1-5 + tag
4. **TG Alert** — per score >= 4, notifica immediata a Zero

Risultato: **ciclo chiuso** scrape → normalize → score → alert.

### Fase 2: Potenziare L1 Collection (1-2 sprint)

| Harvester | Fonte | Difficoltà |
|-----------|-------|-----------|
| Pasal.id Harvester | API REST JSON, 40K reg | Bassa |
| JDIH Perpusnas Harvester | API REST JSON, token auth | Bassa |
| DDTCNews Scraper | news.ddtc.co.id | Media |
| JDIH Bali Scraper | jdih.baliprov.go.id | Media |

### Fase 3: NLM Integration (1 sprint)

- Notebook dedicati per topic
- YouTube ingestion per early signal
- Cross-notebook query
- Audio briefing settimanale

### Fase 4: Analysis layer profondo (1-2 sprint)

- Analyst agent — summary, impact assessment, cross-reference
- "Cosa cambia per PT PMA a Bali?" — prompt specifico
- Timeline: vigore, periodi transitori

### Fase 5: Maintenance continua (ongoing)

- Status checker mensile
- HTML shape monitor
- Bulk import dataset Open-Technology-Foundation (una tantum)

### Stima totale

| Fase | Sprint | Risultato |
|------|--------|-----------|
| Fase 1 | 2 | Ciclo chiuso: scrape → KB → score → alert TG |
| Fase 2 | 1-2 | 4+ fonti, copertura ~90% reg rilevanti |
| Fase 3 | 1 | NLM briefing + YouTube intel |
| Fase 4 | 1-2 | Analisi profonda per reg critici |
| Fase 5 | continua | Manutenzione, decay, monitoring |

**Sistema funzionante end-to-end: ~5-7 sprint.**

---

## 7. RISCHIO PRINCIPALE

Non è tecnico. È **information overload**. L'Indonesia produce ~500 regolamenti/anno. Senza un filtro implacabile di rilevanza, il sistema diventa un archivio morto. Il relevance scoring è l'elemento critico, non il numero di fonti.
