# Federation Review Verdicts — Gemini + DeepSeek

> Review del Technology Enhancement Plan + Compliance Plan
> Reviewers: Gemini 3.1 Pro (adversarial), DeepSeek R1 671b (first-principles)
> Codex: FAILED (CLI argument error — da rilanciare)

---

## DIVERGENZE CRITICHE TRA I REVIEWER

### 1. bge-reranker-v2-m3 su 2GB Fly.io

| Reviewer | Verdetto | Motivazione |
|----------|----------|-------------|
| **Gemini** | **REJECT** | Pesa ~2.2GB float16 → OOM kill immediato su 2GB |
| **DeepSeek** | **DEFER** | Testare prima con query indonesiane. Deploy su worker separato. |
| **Azione** | **DEFER + INVESTIGATE** | Verificare dimensione reale. Alternativa: `bge-micro-v2` o reranking via API remota |

### 2. Rate limiter fail-closed vs fail-open

| Reviewer | Verdetto | Motivazione |
|----------|----------|-------------|
| **Gemini** | **REJECT fail-closed** | Fail-closed = DoS autoinflitto se Redis down |
| **DeepSeek** | **APPROVE fail-closed** | Fix prioritario per sicurezza |
| **Azione** | **COMPROMISE**: fail-open con fallback in-memory token-bucket a limiti più severi |

### 3. BERT indonesiano 522M su 2GB

| Reviewer | Verdetto | Motivazione |
|----------|----------|-------------|
| **Gemini** | **REJECT** | ~1GB+ RAM, crasherà su 2GB |
| **DeepSeek** | **DEFER** | Deploy come servizio separato (FastAPI + ONNX, 300MB) |
| **Azione** | **DEFER** — post-compliance, servizio ONNX separato |

### 4. GraphRAG su PostgreSQL (era SCARTATO)

| Reviewer | Verdetto | Motivazione |
|----------|----------|-------------|
| **Gemini** | **REJECT LO SCARTO** | PostgreSQL Recursive CTE + pgvector funziona senza Neo4j |
| **DeepSeek** | **RECONSIDER** | PostgreSQL 14+ WITH RECURSIVE + ltree, usa 161K archi esistenti |
| **Azione** | **REINTRODURRE** come enhancement V15: GraphRAG nativo PostgreSQL |

### 5. Dual pool asyncpg + psycopg3

| Reviewer | Verdetto | Motivazione |
|----------|----------|-------------|
| **Gemini** | **PROBLEMATICO** | Rischio connection starvation. Serve PgBouncer. |
| **DeepSeek** | **ACCETTABILE** con cautela | LangGraph richiede psycopg3. Override possibile ma instabile. |
| **Azione** | **MANTENERE dual pool + PgBouncer** per multiplexare connessioni |

---

## CONVERGENZE (ENTRAMBI CONCORDANO)

### Ordine esecuzione: COMPLIANCE PRIMA DI TUTTO

**Gemini**: "Compliance > Tech Debt. La non-compliance ti costa il 2% fatturato o blocco IP."
**DeepSeek**: "STOP all feature development until PSE registration filed."

### Ordine Quick Wins corretto (settimana 1):

| # | Azione | Gemini | DeepSeek |
|---|--------|--------|----------|
| 1 | PII Scanner Presidio + regex | APPROVE | Week 1 |
| 2 | Rate limiter fix (fail-open + in-memory fallback) | FIX APPROACH | Week 1 |
| 3 | PSE Registration | APPROVE | Week 1 (stop everything) |
| 4 | DPO Appointment | APPROVE | Week 1 (CTO interim) |
| 5 | PII Encryption pgcrypto | APPROVE | Week 1-2 |
| 6 | Qdrant scalar quantization | APPROVE | Week 2 |
| 7 | CI coverage fix | APPROVE | Week 2 |
| 8 | KG pruning + GIN index | APPROVE | Week 3-4 |

### Facade Pattern: UNANIME APPROVE
"Ottima scelta. Microservizi su codebase accoppiato = suicidio tattico."

### Self-RAG Reflection: APPROVE con cautela
- Gemini: "Aumenta latenza ma garantisce qualità legale"
- DeepSeek: "Solo per CONFIDENCE < 0.30, non su tutte le query"

### BM42: UNANIME APPROVE
"Cross-lingua nativo, RAM bassissima, perfetto per 2GB"

### Unified Conversation History: UNANIME APPROVE
"Schema ChannelMessage già esiste, serve solo persistence layer"

---

## SCOPERTA GEMINI: CRYPTO-SHREDDING per Audit Log WORM

Invece di scrivere PII in chiaro nel log immutabile:
1. Cifra PII con chiave unica per utente
2. Salva PII cifrata nel WORM log
3. Quando utente chiede cancellazione → elimina solo la chiave
4. Log resta integro (WORM compliant) ma PII irrecuperabile (UU PDP compliant)

**Soluzione elegante che risolve il conflitto WORM vs diritto all'oblio.**

---

## SCOPERTA GEMINI: LIMITE 2GB È IL VINCOLO DOMINANTE

"Manca un piano di scaling verticale (RAM) o spostamento workload ML su worker separati."

Modelli proposti incompatibili con 2GB:
- bge-reranker-v2-m3 (~2.2GB)
- cahya/bert-base-indonesian-522M (~1GB+)
- Stanza indonesiano (~200MB, questo CI STA)

**Soluzione**: Worker ML asincrono separato (Mac Pro locale per modelli grandi, Fly.io 2GB solo per API + routing).

---

## SCOPERTA DEEPSEEK: $10M VALUATION ASSESSMENT

```
Current:  ~$480K ARR (stima 5000 clients × ~$8/mo)
Target:   $1.2M ARR (10x multiple per AI SaaS SEA)
Gap:      2.5x growth needed
Probability: 65% con esecuzione perfetta

Required investment:
- Compliance: $25K (legal + DPO)
- Architecture: $40K (2 engineers × 2 mesi)
- Marketing: $100K (acquisition)

Risk: 3 nuovi AI immigration platform lanciati Q4 2024
```

---

## PIANO AGGIORNATO POST-REVIEW

### Settimana 1-2: SURVIVAL (compliance)
1. PSE Registration (legal)
2. DPO appointment (CTO interim)
3. PII scanner Presidio + regex custom indonesiani
4. Rate limiter: fail-open con in-memory fallback severo
5. PII encryption pgcrypto (passport_number, npwp)
6. Fix Telegram PII notification
7. Fix Gemini OCR consent flow

### Settimana 3-4: STABILITY (tech debt)
1. Qdrant scalar quantization
2. CI coverage fix
3. KG pruning + GIN index
4. Audit log crypto-shredding
5. Fix top 100 silent exceptions
6. Semantic cache Redis

### Mese 2-3: SCALABILITY (architecture)
1. RAG Facade Pattern
2. BM42 sparse vectors
3. Self-RAG reflection (solo CONFIDENCE < 0.30)
4. Unified conversation history
5. LangGraph Postgres checkpointing + PgBouncer
6. GraphRAG nativo PostgreSQL (WITH RECURSIVE + ltree)

### Deferred (Q3-Q4):
- bge-reranker (dopo verifica dimensione o servizio separato)
- BERT indonesiano (ONNX su servizio dedicato)
- KG confidence calibration
- Revenue: KG API, compliance upsell, visa predictor

---

*Federation Review Verdicts v1.0 — 29 marzo 2026*
*Reviewers: Gemini 3.1 Pro (adversarial, 61s), DeepSeek R1 671b (reasoning, $0.013)*
*Codex: da rilanciare (CLI error)*
