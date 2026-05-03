# Mata Garuda — Security & OSINT Firewall

> Data: 2026-04-08 | [DECIDED]

## Regola Assoluta

**Dati OSINT = proprieta esclusiva di Zero. MAI esposti a frontend, clienti, team, cloud.**

## Architettura Firewall

```
                    ZONA PUBBLICA                    ZONA BLINDATA
              (distribuibile)                   (solo Zero, solo Pro)
         ┌─────────────────────┐           ┌─────────────────────┐
         │                     │  ONE-WAY  │                     │
         │  garuda:enriched    │ ────────► │  garuda:osint       │
         │  (news, regolamenti,│    IN     │  (feed al graph)    │
         │   market signals)   │           │                     │
         │                     │  BLOCCATO │  Neo4j locale       │
         │                     │ ◄──────── │  OSINT Nexus UI     │
         └─────────────────────┘   OUT     │  Dossier generator  │
              │                             │  Power scoring      │
              ▼                             │  LHKPN analysis     │
         Frontend (balizero.com)            └─────────────────────┘
         Clienti                                    │
         Team (Damar, Surya)                        ▼
         Zantara AI (RAG)                    Solo Zero:
         Newsletter                          - TG privato
         Social media                        - Terminal Pro
         API pubblica                        - osint-nexus-ui localhost:3333
```

## Regole Operative

### PERMESSO (one-way IN verso OSINT)
- Articoli news pubblici → arricchiscono Neo4j graph (nuove menzioni di target)
- Dati procurement LPSE (pubblici) → aggiornano tender history
- LHKPN (pubblici) → aggiornano asset declarations

### VIETATO (out da OSINT)
- ❌ Dossier → frontend
- ❌ Power score → API
- ❌ Relationship graph → qualsiasi consumer esterno
- ❌ OSINT entities → Qdrant su Fly.io
- ❌ Target profiles → Telegram group/channel
- ❌ Anomaly alerts OSINT → chiunque non sia Zero
- ❌ Neo4j query results → backend RAG

### Enforcement Tecnico

1. **Redis stream separato**: `garuda:osint` ha consumer group `osint-local-only`
   - Nessun consumer esterno puo iscriversi
   - Stream esiste SOLO su Redis locale Pro, MAI su Fly.io Redis

2. **Neo4j**: porta 17687 bind SOLO su localhost
   - Nessun port forwarding
   - Nessun tunnel SSH esposto

3. **osint-nexus-ui**: localhost:3333
   - Nessun reverse proxy
   - Nessun deploy Vercel

4. **Code review check**: qualsiasi PR che importa da `osint_nexus` in codice che gira su Fly.io → BLOCK

## Classificazione Dati

| Dato | Classificazione | Storage | Distribuzione |
|------|----------------|---------|---------------|
| Articoli news | PUBBLICO | Qdrant + PostgreSQL (Fly.io) | Tutti |
| Scores/classification | INTERNO | PostgreSQL (Fly.io) | Zantara, team |
| NER entities (da news) | INTERNO | PostgreSQL (Fly.io) | KG backend |
| OSINT entities | BLINDATO | Neo4j locale Pro | Solo Zero |
| OSINT relations | BLINDATO | Neo4j locale Pro | Solo Zero |
| Dossier | BLINDATO | File locale Pro | Solo Zero |
| LHKPN analysis | BLINDATO | Neo4j locale Pro | Solo Zero |
| Power scores | BLINDATO | Neo4j locale Pro | Solo Zero |
