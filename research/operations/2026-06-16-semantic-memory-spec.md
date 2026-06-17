---
date: 2026-06-16
domain: compliance
client_case: false
sources:
  - Exa research papers (TiMem ACL 2026, memory consolidation)
  - Exa github (Mem0 Apr-2026 algo, Letta, Cognee, sqlite-memory, Graphiti/Zep, OMEGA)
  - WebSearch (AI agent memory 2026 comparison)
  - DeepSeek V4 Pro refuter (adversarial gate on the 2-tier design)
  - On-disk STADIO-0 (existing `mem --semantic` + mos-plus-semantic-query.py, dead shebang, 0-byte .db)
---

# SPEC — Memoria semantica per l'harness (richiamo per significato, sovrana, on-M5)

> **Stato: SPEC. Niente codice ancora.** Deliverable di "disegno + spec, poi decidi" (Antonello, 2026-06-16).
> Genesi: opus-mythos TAC del harness, parte 2. Sintesi a 3 voci: SOTA-paper (ambizione) →
> DeepSeek refuter (taglia l'over-engineering) → Opus gate (tiene il vincolo push/pull che entrambi
> mancavano). La parte 1 (lifecycle-guard) è in PR #1472.

## 0. Il problema in una riga
La mia memoria operativa (`MEMORY.md` + 484 file .md, 5.2MB) è **leggi-dall'alto-sequenziale**, non
**richiama-per-significato**. Sforo il tetto 25.6KB di MEMORY.md (#40614) → perdo le note più recenti.
Tu hai chiesto: *"memorie semantiche per velocità e fluidità, come un vero sistema neurale"*.

## 1. Reperto che riscrive il problema (STADIO-0 on-disk)
**La memoria semantica esiste già a metà, costruita e mai armata** (stesso meta-pattern della parte 1):
- `mem` CLI ha già un flag `--semantic` → `~/scripts/mos-plus-semantic-query.py` (embed bge-m3 → Qdrant cosine → JOIN sqlite). **Scritto bene.**
- MA: shebang morto `#!/Users/nuzantara/.claude/venvs/...` (path Air/Pro, non esiste su M5 user=balizero) · `.db` a **0 byte** · collection Qdrant `mos_memories` inesistente · ollama su M5 = alias SSH→Mini.
- Tradotto: 3 organi (embed, vector-store, sqlite) presenti come pezzi sparsi, **zero cablati**, e il cablaggio tentato dipendeva da Mini (fragile).

## 2. Cosa dice il SOTA 2026 (deep research, numeri verificati dalle fonti)
| Sistema | Numero-chiave | Lezione per noi |
|---|---|---|
| **Mem0** (algo apr-2026) | 91.6 LoCoMo · 94.8 LongMemEval · 6.8K tok · 0.88s | **ADD-only, niente DELETE**: accumula, non cancellare. Multi-signal (semantic+BM25+entity). |
| **TiMem** (ACL 2026) | 76.88 LongMemEval-S · **−52% lunghezza recall** | Consolidamento gerarchico per ASTRAZIONE (non erasure). Complexity-aware recall. |
| **OMEGA** | **95.4 LongMemEval**, local-first zero-cloud | Il tetto per il caso sovrano. Filesystem-shaped + MCP. |
| **Letta** (MemGPT) | 23k★ | **Core memory (sempre-in-RAM) + archival (on-demand)**. ← il vincolo push/pull. |
| **Graphiti/Zep** | bi-temporale | Mai delete: edge con `valid_at`/`invalid_at`. |

**Consenso trasversale (5 sistemi):**
- **(a) Forget vs accumulate** → NON cancellare. Consolida per astrazione + temporal-validity. *Smentisce il mio istinto di stamattina "svuota il vaso".*
- **(b) retrieval** → **hybrid** (semantic + keyword/BM25) è la barra. Pure-vector insufficiente.
- **(c) episodic vs semantic** → utile separare, ma a due livelli basta (Letta).
- **(d) summarization** → deterministica > LLM-decisa (consistenza).

## 3. Il gate del refuter (DeepSeek V4 Pro, adversariale) — cosa ha cambiato
Ho passato il mio primo design (2-livelli con Qdrant) al refuter. Verdetto, **recepito in parte**:
- 🔴 **ACCOLTO — Dipendenza Mini = fragilità.** Embedding via SSH→Mini viola Law-6 + latenza in loop interattivo. → **Embedding ON-M5, sempre. L'agente ricorda anche offline.**
- 🔴 **ACCOLTO — sqlite-memory license NOASSERTION = scartato come dipendenza-cuore.** Per memoria con PII, no-OSI = sabbia. (Reuse-first come lente, non dogma: trovato, valutato, scartato perché non incastra.)
- 🔴 **ACCOLTO in parte — "Qdrant è over-engineering".** Vero per 484 file/5.2MB. → **niente Qdrant, niente server.** ripgrep + BM25 + re-rank embedding leggero.
- 🟡 **RESPINTO — "MEMORY.md = 3 righe statiche".** Troppo. Il refuter collassa due funzioni diverse: l'indice caricato a SessionStart è **push-a-freddo** (ciò che devo sapere PRIMA di pensare a cercare: superscar, regola-email, team perimeter). `mem recall` è **pull-a-richiesta** (lo chiamo solo se già SO di dover cercare). Letta lo conferma: core-memory sempre-in-RAM ≠ archival on-demand. → indice piccolo di puntatori caldi **+** store semantico.

## 4. Il design (post-gate): single-store semantico locale + indice-caldo minimo

### Livello A — "indice caldo" (push, SessionStart)
`MEMORY.md` resta, ma SOLO puntatori `[[link]]` (tecnica superscar/skill, come hai chiesto). Tetto <20KB.
Contiene solo ciò che va *spinto* in contesto a freddo. Niente paragrafi. È già quasi così — va solo
de-bloattato (vedi PR #1472 step 2). **Questo NON è lo store semantico — è la "core memory" di Letta.**

### Livello B — "store semantico" (pull, on-demand): `mem recall "<situazione>"`
Tutto locale su M5, **zero server, zero rete, zero licenza dubbia**:
1. **Candidate retrieval** — `ripgrep` sui 484 .md (istantaneo su 5MB) → ~30 candidati.
2. **Hybrid rank** — `rank_bm25` (Python, MIT) keyword score **+** re-rank semantico con embedding **leggero ON-M5** (`all-MiniLM-L6-v2` o `bge-small`, ~100MB, CPU, via `sentence-transformers` Apache-2.0, oppure `llama.cpp` se preferisci zero-Python-dep).
3. **Return** top-5 `{path, snippet, score}`. Latenza target <1s, tutto su M5.
4. **Cache** embedding dei file in un `.db` sqlite LOCALE (riusa i .db già lì, ora a 0 byte) — invalidata per content-hash (solo i file cambiati ri-embeddati).

### Accumulo, non cancellazione (consenso SOTA + tua intuizione #3 raffinata)
Il "vaso" del Livello B **non si svuota** — accumula illimitato. Il recall semantico lo rende a fondo
trasparente: peschi i 5 giusti per significato anche su 10k note. La compattazione resta SOLO sul
Livello A (l'indice ha il tetto fisico), e lì è "comprimi+archivia mai-cancella" (la tua scelta).

### Sync 3-macchine (risolve la dir-duplicata)
I .md sono già replicati (è la "dir duplicata" della parte 1, vista come bug). Qui diventa **feature**:
git/rsync periodico dei .md + ogni macchina ri-costruisce il proprio indice embedding LOCALE (cache
per-host). Niente CRDT, niente sync del .db vettoriale. La dir non è più "duplicata per errore" — è
**replica-di-sorgente con indice-derivato per-host.** (Investiga comunque QUALE daemon la scrive oggi, parte 1 P0.)

## 5. Cosa NON faccio (anti-over-engineering, dal refuter)
- ❌ Qdrant / vector-DB server. ❌ sqlite-memory (license). ❌ embedding remoto su Mini.
- ❌ compattazione LLM-decisa nell'hook (lento). ❌ knowledge-graph (Cognee/Graphiti) — sovradimensionato per 484 note.
- ❌ UPDATE/DELETE dei ricordi (Mem0 dimostra che peggiora — accumula).

## 6. Sforzo & rischi (per decidere)
- **Sforzo**: ~mezza giornata. È per il 70% **riparare ciò che esiste** (`mos-plus-semantic-query.py`: shebang→M5, embedding→on-M5, popolare il .db) + ~100 righe nuove (ripgrep+bm25+rerank wrapper). Reuse-first VERO.
- **Dipendenze nuove**: `sentence-transformers` (Apache-2.0) + `rank_bm25` (MIT) + un modello ~100MB. Tutto OSI, tutto local, $0, zero PII-leak (Law-2 ok).
- **Rischio basso**: nessun servizio nuovo da tenere vivo (no "Esiste≠Armato"); il fallback è il `mem query` FTS5 che già funziona.
- **Reversibile**: se non piace, è uno script in più, non un'architettura da smontare.

## 7. Decisione richiesta a Zero
- [ ] **GO build** del Livello B (mezza giornata, su worktree+PR, dry-run-first)?
- [ ] o **prima** chiudere i 3 P0 della parte 1 (memoria troncata, secret, guardiano) e questo dopo?
- [ ] Modello embedding: `all-MiniLM-L6-v2` (più piccolo/veloce) vs `bge-small` (più qualità multilingua IT/ID)?

> **Verificato**: SOTA da fonti primarie lette su disco · refuter passato + gate Opus (recepito 3/4, respinto 1/4 con motivo) · esistente ispezionato on-disk. Niente allucinato.
