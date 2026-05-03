# Mata Garuda — indonesia-civic-stack Evaluation

> Data: 2026-04-09 | Sessione S03
> Test reali: 11 moduli testati su Pro (Bali IP)
> Valutazioni: DeepSeek API + Gemini 2.5 Pro CLI + Exa agent + test diretti
> Repo: github.com/suryast/indonesia-civic-stack v1.1.0
> PyPI: `pip install "indonesia-civic-stack[all]"`

---

## Overview

15 moduli, 46 MCP tool, Python SDK + MCP server + REST API.
Wrappa 14 portali governativi indonesiani in un'interfaccia unificata.
Ogni modulo ritorna `CivicStackResponse` con: result, found, status, confidence, source_url, fetched_at, module.

## Test Reali (Pro machine, Bali IP, 2026-04-09)

| Modulo | Tool testato | Risultato | Note |
|--------|-------------|-----------|------|
| **BPOM** | search("paracetamol") | ✅ **OK** | Risultati corretti, veloce |
| **BMKG** | get_latest_earthquake() | ✅ **OK** | Dati earthquake real-time (M 4.5, timestamp corretto) |
| **BPJPH** | search("mie instan") | ✅ **OK** | 1 risultato (errore 500 interno gestito gracefully) |
| **KPU** | search("Joko") | ⚠️ **DEGRADED** | JSONDecodeError interno ma ritorna risultato wrappato |
| **JDIH** | search("visa") | ✅ **OK** | Risultato trovato (title: "48") — formato minimo |
| **KSEI** | search("saham") | ⚠️ **DEGRADED** | 404 interno ma risultato wrappato |
| **DJPB** | search("infrastruktur") | ⚠️ **DEGRADED** | 404 interno ma risultato wrappato |
| **LPSE** | search("bali") | ⚠️ **EMPTY** | 0 risultati (portali dead Mar 2026) |
| **SIMBG** | search("Badung") | ❌ **FAIL** | 0 risultati. API nazionale errore, portali regionali dead |
| **LHKPN** | search("Iman Warih") | ❌ **FAIL** | JSONDecodeError — reCAPTCHA v3 fallisce (serve Playwright visible) |
| **AHU** | fetch("PT Bali Zero") | ❌ **FAIL** | 404 senza proxy, Camoufox 298MB scaricato |
| **OSS/NIB** | fetch("restoran bali") | ❌ **FAIL** | Playwright can't find form inputs (page restructured) |
| **OJK** | fetch("BCA") | ❌ **FAIL** | 404 su SharePoint (migration Apr 2026) |
| **BPS** | Non testato | ⚠️ | Richiede BPS_API_KEY (gratis, da registrare) |

**Risultato finale**: 
- ✅ **3 moduli OK** (BPOM, BMKG, BPJPH, JDIH) 
- ⚠️ **4 moduli DEGRADED ma usabili** (KPU, KSEI, DJPB, LPSE)
- ❌ **5 moduli FAIL** (SIMBG, LHKPN, AHU, OSS, OJK)
- **BPS** non testato (serve API key)

**Conclusione**: ~30% dei moduli funziona bene, ~30% degradato ma usabile, ~35% rotto. 
**Utilizzabilita effettiva: ~60%** — comunque un asset enorme per i moduli che funzionano.

## Valutazione per Modulo (consensus DeepSeek + Gemini + test)

### CRITICAL per Mata Garuda (Score 9-10)

| Modulo | Score | Tool | Stato | Strategia |
|--------|-------|------|-------|-----------|
| **AHU** | 10/10 | lookup/directors/verify/search | ⚠️ Ristrutturato | **Nostro scraper primario**, civic-stack fallback |
| **OSS/NIB** | 10/10 | lookup/verify/search | ⚠️ Ristrutturato | **Nostro scraper primario**, civic-stack fallback |
| **LHKPN** | 10/10 | get/search/pdf | Test fallito | **Nostro scraper primario** (reCAPTCHA solved), civic-stack backup |
| **JDIH** | 10/10 | search/get | OK ma minimo | Civic-stack + nostro NER per enrichment |

### HIGH per Mata Garuda (Score 7-9)

| Modulo | Score | Tool | Stato | Strategia |
|--------|-------|------|-------|-----------|
| **BPJPH** | 9/10 | check/lookup/status/cross-ref | OK | **Civic-stack primario** |
| **OJK** | 9/10 | check/search/status/waspada | ⚠️ SharePoint | Nostro scraper per Waspada, civic-stack per resto |
| **BPS** | 9/10 | search/indicator | Serve API key | **Civic-stack primario** (con BPS_API_KEY) |
| **BPOM** | 8/10 | check/search/status | OK | **Civic-stack primario** |
| **LPSE** | 8/10 | vendor/search/tenders/portals | Empty results | **Nostro scraper primario** (con Cloudflare bypass) |
| **DJPB** | 8/10 | search/get | OK (degraded) | **Civic-stack primario** |
| **SIMBG** | 8/10 | search | FAIL | Aspettare fix o costruire nostro |

### MEDIUM per Mata Garuda (Score 6-7)

| Modulo | Score | Tool | Stato | Strategia |
|--------|-------|------|-------|-----------|
| **KPU** | 7/10 | candidate/search/results/finance | OK (degraded) | **Civic-stack primario** per OSINT politico |
| **KSEI** | 7/10 | search/get | OK (degraded) | **Civic-stack primario** per financial intel |
| **BMKG** | 6/10 | earthquake/weather | OK | **Civic-stack primario** per disaster alerts |

## Strategia di Integrazione [DECIDED]

### Dual-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│              MATA GARUDA                         │
├─────────────────────────────────────────────────┤
│  LAYER A: civic-stack (community maintained)     │
│  ├─ Working: BPOM, BPJPH, BPS, BMKG, KPU, DJPB │
│  ├─ Backup: AHU, OSS, LHKPN                     │
│  └─ Monitor: OJK, LPSE, SIMBG                   │
├─────────────────────────────────────────────────┤
│  LAYER B: nostri scrapers (battle-tested)         │
│  ├─ Primary: AHU, OSS, LHKPN (reCAPTCHA solved) │
│  ├─ Primary: LPSE (Cloudflare bypass)            │
│  └─ Custom: Immigration, Tax, Property           │
├─────────────────────────────────────────────────┤
│  LAYER C: health monitor                         │
│  └─ Ogni 6h: testa ogni endpoint civic-stack     │
│  └─ Se fallisce 3x: switch a nostro scraper      │
│  └─ Se si riprende: reattiva civic-stack          │
└─────────────────────────────────────────────────┘
```

### MCP Integration [DECIDED]

**Aggiungere civic-stack come MCP server SEPARATO** da nuzantara-mcp.

Motivi:
1. Cicli di manutenzione diversi (upstream vs nostro)
2. Profili di affidabilita diversi
3. Facile disabilitare moduli problematici
4. Separazione chiara di responsabilita

```bash
# Installare
pip install "indonesia-civic-stack[mcp]"

# Aggiungere a Claude Code
claude mcp add civic-stack -- civic-stack-mcp

# O via config
# ~/.claude/mcp.json aggiungere:
# "civic-stack": {"command": "civic-stack-mcp", "env": {"BPS_API_KEY": "..."}}
```

### Proxy Strategy

- 6 moduli richiedono IP indonesiano (AHU, OJK, OSS, LPSE, JDIH + parzialmente LHKPN)
- **Pro e Air sono a Bali** → IP indonesiano nativo, nessun proxy necessario
- Per CI/CD o testing da estero: Cloudflare Worker proxy gia documentato nel repo

## Moduli Mancanti — Da Costruire Noi

### Priority HIGH (core business)

| Modulo | Fonte | Perche |
|--------|-------|--------|
| **Imigrasi** | imigrasi.go.id | Core business BZ, visa status, stay permits |
| **DJP Tax** | pajak.go.id/CoreTax | NPWP verification, tax compliance |
| **ATR/BPN** | atrbpn.go.id | Property intelligence, land registry |
| **Putusan MA** | putusan.mahkamahagung.go.id | Court decisions (JSON API gia pubblica) |
| **Peraturan** | peraturan.go.id | Semantic diff regolamenti (FAISS fork) |

### Priority MEDIUM (OSINT enhancement)

| Modulo | Fonte | Perche |
|--------|-------|--------|
| **PPATK** | ppatk.go.id | Anti-money laundering intelligence |
| **BPK** | bpk.go.id | Audit reports |
| **Samsat** | samsat.id | Vehicle tax/ownership |
| **SIRUP** | sirup.lkpp.go.id | Pre-tender planning data |

## Evoluzione nell'Ecosistema Nuzantara (Gemini + DeepSeek)

### Short-term (settimane)
1. **Installare civic-stack come MCP server** su Pro
2. **BPS API key**: registrarsi su webapi.bps.go.id per dati statistici
3. **Cross-reference chain**: BPOM × BPJPH per due diligence F&B automatica
4. **JDIH monitoring**: cron per detect nuovi regolamenti → alert

### Medium-term (mesi)
1. **Due Diligence Automatizzata**: onboarding cliente → auto-check su AHU + OSS + OJK + BPOM + Halal
2. **Compliance Dashboard**: per ogni cliente, score di conformita aggregato
3. **Procurement Intelligence**: LPSE + DJPB → previsione tender basata su budget
4. **OSINT Cross-Reference**: AHU directors → LHKPN wealth → KPU campaign finance → anomaly detection

### Long-term (evoluzione organismo)
1. **Self-healing scraper monitor**: se un civic-stack tool fallisce, Mata Garuda auto-switcha al nostro scraper
2. **Contribuire upstream**: fixare moduli rotti (AHU, OSS, OJK) e mandare PR
3. **Nuovi moduli**: contribuire Immigration, Tax, Property al civic-stack open source
4. **API unificata**: esporre tutti i tool (nostri + civic-stack) via unico MCP garuda.gov()

## Rate Limiting & Performance

- civic-stack ha `RateLimiter` built-in per modulo (es. LHKPN: 0.25 req/sec)
- Non interferisce con i nostri 609 source scraper (fonti diverse)
- Per bulk operations: usare nostri scrapers (ottimizzati per throughput)
- Per single lookup: usare civic-stack (API piu pulita)

## Costi

| Voce | Costo |
|------|-------|
| civic-stack package | Free (open source, MIT) |
| BPS API key | Free (registrazione) |
| Proxy (se necessario) | Non necessario (siamo in Indonesia) |
| Playwright (per LHKPN, AHU, OSS) | Free (gia installato) |
| **Totale** | **$0** |

---

## L'Ecosistema Completo (Exa Agent Discovery)

civic-stack non e' un progetto isolato. E' parte di una **famiglia di tool** creata da Surya (suryast, Sydney AU):

```
┌─────────────────────────────────────────────────┐
│ LAYER 1: REFERENCE (docs + API catalog)          │
│ └─ indonesia-gov-apis (131⭐, 10 forks)          │
│    50+ endpoint gov documentati                  │
├─────────────────────────────────────────────────┤
│ LAYER 2: CODE (SDK + scrapers)                   │
│ └─ indonesia-civic-stack (questo)                │
│    14 moduli, 46 tool, Python + MCP              │
├─────────────────────────────────────────────────┤
│ LAYER 3: INTELLIGENCE (!!)                       │
│ └─ indonesia-civic-signal-monitor                │
│    Anomaly detection su dati governativi         │
│    DA INVESTIGARE — pattern simile a Mata Garuda │
├─────────────────────────────────────────────────┤
│ LAYER 4: STATUS (uptime tracking)                 │
│ └─ status.datarakyat.id                          │
│    Live daily status di 52 portali gov           │
│    (da US + Jakarta) → PERFETTO per health check  │
├─────────────────────────────────────────────────┤
│ LAYER 5: PRODOTTI B2C                             │
│ ├─ halalkah.id — 9.57M prodotti halal             │
│ ├─ legalkah.id — Fintech legality checker        │
│ └─ datarakyat.id — Landing + docs                │
└─────────────────────────────────────────────────┘
```

**Implicazioni per Mata Garuda**:

1. **indonesia-civic-signal-monitor** e' letteralmente quello che stiamo costruendo (anomaly detection su dati gov). **DA CLONARE E STUDIARE** prima di reinventare.

2. **status.datarakyat.id** ci risolve il problema del health monitoring gratis. Possiamo scrapparlo per sapere quali portali sono UP prima di tentare lo scraping.

3. La presenza di 3 prodotti B2C live (halalkah, legalkah) dimostra che civic-stack e' **battle-tested in produzione** — non solo un progetto accademico.

## Competitor & Alternative Tools

L'agent ha scoperto 2 alternative specializzate:

### `setiapam/bps-mcp-server` (32 tool vs 3 civic-stack)
- Copre TUTTI gli endpoint BPS API v1
- Fuzzy matching ("Jatim" → "Jawa Timur")
- Deeper di civic-stack per BPS
- **DECISION**: per BPS usare bps-mcp-server (32 tool) invece di civic-stack (3 tool)

### `Ansvar-Systems/indonesian-law-mcp` (TypeScript)
- 1,924 UU, 2,225 pasal
- 13 tool legal-specific: `search_legislation`, `build_legal_stance`, etc.
- Hosted endpoint: `mcp.ansvar.eu/law-indonesian-law-mcp/mcp`
- Complementare (non competitor) a civic-stack
- **DECISION**: valutare aggiunta per legal research (oltre a Pasal.id gia presente)

## Problemi Noti Critici (da evitare)

### CF Worker Limitation
```
Molti portali .go.id sono dietro Cloudflare.
Un CF Worker che fa fetch() verso altri CF-protected origins riceve 403/522.
→ NON possiamo usare Cloudflare Workers come proxy per tutti i portali
```

**Soluzione**: usare proxy residenziali o server in Jakarta (NOI siamo in Bali — no problem).

### Portal URL Instability
```
I portali gov indonesiani cambiano struttura URL senza preavviso.
civic-stack traccia questi cambi nel CHANGELOG ma i fix possono richiedere giorni/settimane.
```

**Soluzione**: il nostro dual-layer (civic-stack + nostri scrapers) assorbe queste instabilita.

### Degradation Policy Upstream
```
"A module that breaks for 60 days is flagged DEGRADED and may be archived"
```

**Soluzione**: se AHU/OSS/OJK non vengono fixati upstream entro 60 giorni, noi li manteniamo privatamente.

## Patterns da Rubare per Mata Garuda

### 1. Design Decisions per AI Agents (da civic-stack AGENTS.md)

```
1. Uniform response envelope — ogni tool ritorna CivicStackResponse
2. Error envelopes, not exceptions — agent ricevono structured error
3. Self-documenting tools — MCP descriptions con types, values, format
4. Deterministic naming — check_, search_, get_*_status pattern
```

**APPLICAZIONE**: il nostro MCP `garuda.*` deve seguire gli stessi 4 principi.

### 2. Ecosystem di File per AI Agents

| File | Purpose |
|------|---------|
| `AGENTS.md` | Architettura, patterns, critical rules (per tutti gli agenti) |
| `CLAUDE.md` | Commands, style guide (Claude Code) |
| `.cursorrules` | Cursor rules |
| `SKILL.md` | Skill discovery (AgentSkills format) |
| `PROMPTS.md` | Example prompts + interactive recipes |

**APPLICAZIONE**: abbiamo gia CLAUDE.md e GEMINI.md. Aggiungere AGENTS.md + SKILL.md + PROMPTS.md per Mata Garuda.

### 3. Due Diligence Pattern (Cross-Source)

```python
# Pattern verbatim da civic-stack:
async def check_company(name: str) -> dict:
    ahu, ojk, bpom, nib = await asyncio.gather(
        ahu_search(name),
        ojk_search(name),
        bpom_search(name),
        nib_search(name),
    )
    return {
        "registered": any(r.found for r in ahu),
        "ojk_licensed": any(r.found for r in ojk),
        "bpom_products": len([r for r in bpom if r.found]),
        "nib_valid": any(r.found for r in nib),
    }
```

**APPLICAZIONE**: il nostro `garuda.due_diligence(entity)` deve fare cross-source parallelo su N fonti, non seriale.

## Azioni Immediate [DECIDED]

1. [ ] Clonare `indonesia-civic-signal-monitor` (layer intelligence della famiglia)
2. [ ] Valutare `bps-mcp-server` (32 tool vs 3 per BPS)
3. [ ] Valutare `Ansvar-Systems/indonesian-law-mcp` (13 tool legal)
4. [ ] Scrapare `status.datarakyat.id` come health check per i nostri scrapers
5. [ ] Installare civic-stack MCP su Pro alongside nuzantara-mcp
6. [ ] Registrare BPS API key su webapi.bps.go.id
7. [ ] Aggiungere AGENTS.md + SKILL.md + PROMPTS.md per Mata Garuda
8. [ ] Testare AHU/OSS/OJK (serve Playwright + proxy optional)
