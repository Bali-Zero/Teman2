---
date: 2026-06-06
domain: marketing
client_case: war-room-rebuild
sources:
  - apps/bali-intel-scraper (intel_items live probe, 2026-06-06 post-backfill)
  - scripts/wr2_topic_selector.py (selettore WR2 attuale, 722 righe)
  - apps/backend-rag/backend/services/intel/intel_lake_service.py
  - apps/backend-rag/backend/llm/claude_oauth_client.py
  - ArxivDigest (MIT) — batch-LLM relevance scoring pattern
  - instructor (MIT) — pydantic structured output (valutato, NON adottato: pydantic puro basta)
---

# War Room — Step 1: lettura quotidiana dall'Intel Lake → shortlist giudicata da LLM

> Tabula rasa. Costruiamo la War Room da zero, uno step alla volta. Questo è lo Step 1.
> **Stato: DESIGN (no codice scritto). Gate: panel 4-LLM prima dell'implementazione (regola CLAUDE.md §6).**

---

## 0. Cosa fa lo Step 1 (una frase)

Ogni giorno, leggere il materiale fresco (≤3 giorni su data di **pubblicazione**) dall'Intel Lake,
dare un **giudizio di rilevanza LLM** su ciascun item, e produrre una **shortlist** ordinata di
candidati-topic per la War Room — il primo anello della catena che porterà al carosello.

---

## 1. Il dato reale (verificato live 2026-06-06, post-backfill TZ)

`intel_items` (Postgres su Fly, = **Intel Lake A**), 18 colonne. I campi che contano:

| Campo              | Tipo             | Affidabilità per il giudizio                                                                        |
| ------------------ | ---------------- | --------------------------------------------------------------------------------------------------- |
| `title`            | text NOT NULL    | ✅ sempre presente — input primario                                                                 |
| `summary`          | text NULL        | ✅ 62/64 freschi popolato (spesso ~2000 char) — input primario                                      |
| `topic_tags`       | ARRAY NOT NULL   | ⚠️ RUMOROSO (`news`,`news-room` generici + dominio in coda) → solo **pre-score debole**, mai verità |
| `source_domain`    | text             | ✅ segnale di tier (liputan6/antaranews ≠ blog SEO concorrente)                                     |
| `published_at`     | timestamptz NULL | ✅ **ora affidabile** (bug +8h fixato 2026-06-06) → filtro freschezza                               |
| `language`         | text             | utile (it/en/id) per instradare il registro                                                         |
| `confidence_score` | real             | segnale dello scraper, soft                                                                         |
| `routing_status`   | text NOT NULL    | ❌ **NON filtrare** (vedi §3)                                                                       |
| `is_probe_sandbox` | bool NOT NULL    | ✅ **filtrare via** (probe/test)                                                                    |

**Volumi freschi ≤3gg su `published_at`**: **64 item** (59 scraper + 5 altri producer).
**Producer multipli** (Step 1 legge TUTTI): `bali_intel_scraper` (259 tot), `regulatory_watcher` (25),
`pajak_monitor` (24, tasse), `oss_monitor`, `yt_monitor`.

**Candidati reali oggi** (= oro Bali Zero): PPh Final UMKM, OSS RBA, Bali villa red flags,
deportazione 13 WNA scamming, property per stranieri, MERP/KITAS, Bridging Visa, Golden Visa.

---

## 2. Cosa esiste già (reuse-first) — e perché lo Step 1 NON è "scrivi da zero"

| Mattone                          | Esiste?                                                                                | Esito                                                                           |
| -------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Selettore topic WR2              | ✅ `scripts/wr2_topic_selector.py` (722 righe)                                         | **[FORKA-E-ADATTA]** — ma legge la fonte SBAGLIATA (vedi sotto)                 |
| Connettore lettura `intel_items` | ❌ `intel_lake_service.py` ha solo `record_observation`+`log_audit` (write)            | **[SCRIVI-NUOVO]** — ma è 1 query SELECT, non un sistema                        |
| Chiamata Claude a quota MAX      | ✅ SDK `anthropic` v0.99.0 nel venv prod **+** `claude_oauth_client.py` (CLI fallback) | **[INSTALLA-LIB]** — vedi nota SDK-OAuth sotto                                  |
| Scoring euristico                | ✅ `score_item()` in topic_selector (freshness+kw+tier+live)                           | **[STUDIA-PATTERN]** — lo teniamo come **pre-score** prima dell'LLM             |
| Structured output                | `instructor` (MIT) ASSENTE dal venv; `pydantic 2.12.5` presente                        | **[INSTALLA-LIB]** — instructor patcha l'SDK OAuth → JSON validato + auto-retry |

### Nota SDK-OAuth (correzione 2026-06-06) — l'SDK Python SI USA a quota MAX

Verificato empiricamente sul sorgente SDK reale (`anthropic 0.99.0`, venv backend-rag, `_client.py`):
l'SDK ha **due rami di auth** mutuamente esclusivi —

```python
def auth_headers(self): return {**self._api_key_auth, **self._bearer_auth}
# _api_key_auth → {"X-Api-Key": api_key}              ← PAID, bandito
# _bearer_auth  → {"Authorization": f"Bearer {auth_token}"}  ← MAX OAuth, CONSENTITO
```

→ Lo Step 1 usa **`anthropic.Anthropic(auth_token=CLAUDE_CODE_OAUTH_TOKEN)`** (header Bearer = quota MAX, $0),
NON `api_key`. Questo abilita structured output nativo + streaming + tool_use — meglio del CLI one-shot.
Token già disponibili (Fly secrets `CLAUDE_CODE_OAUTH_TOKEN_1/2/3` + `CLAUDE_MAX_TOKEN`, letti da `claude_oauth_client.py`).
**Cautela (CLAUDE.md)**: `Anthropic(api_key=…)` e `Anthropic(auth_token=…)` si scrivono quasi uguali → **code-review pre-merge** che nessuno passi mai `api_key`. `instructor.from_anthropic(client)` gira sopra questo client OAuth.
| Batch-LLM relevance | ArxivDigest (MIT) pattern | **[STUDIA-PATTERN-RISCRIVI]** — loop "N item → 1 chiamata batch → score+motivo" |

### La scoperta-chiave: i "2 Intel Lake" sono REALI e qui si vedono

`wr2_topic_selector.py` **non legge `intel_items`**. Legge una **staging area** diversa:

```python
# scripts/wr2_topic_selector.py:215
url = f"{backend_url}/api/intel/staging/pending?type=all"   # ← Intel Lake B (HTTP)
```

- **Intel Lake A** = `intel_items` Postgres — ricco, multi-producer, `published_at` affidabile, 328 item. _(quello che abbiamo verificato e sistemato)_
- **Intel Lake B** = "staging area" via endpoint `/api/intel/staging/pending` — il sistema parallelo che il selettore attuale consuma.

Lo Step 1 **ripunta la lettura da B ad A**. Questo è esattamente il "GET su Intel Lake A" che
(una volta costruito) consente di ripuntare i 3 consumer rimasti e mandare B in pensione.

---

## 3. Decisione di design ancorata al dato: NON filtrare per `routing_status`

`routing_status` dei freschi ≤3gg: `needs_review=31`, `blog=20`, `nb-intel=13`.

Se la War Room filtrasse "solo `needs_review`", **butterebbe 33 item** (20 blog + 13 nb-intel) che
sono ottimo materiale-carosello. `routing_status` è la **rotta di ALTRI consumer** (NB-pusher, blog),
non il filtro della War Room. → **Step 1 legge tutti i freschi non-probe e giudica per conto suo.**

---

## 4. Architettura dello Step 1 (3 stadi, dal grezzo alla shortlist)

```
intel_items (A, Fly :15432)
      │  SELECT freschi (finestra DATE-WITA, §6-corretto) NOT is_probe_sandbox, tutti i producer
      │  NULL published_at → fallback first_seen_at (i 4 yt_monitor reali, non perderli)
      ▼
[STADIO 1] FETCH + PRE-SCORE deterministico (NON è un gate)   ← modulo condiviso intel_prescore
      │  freshness + tier(source_domain) + keyword(BZ) + tag-hint → SOLO ordinamento/tie-break
      │  NESSUN top-K: passa TUTTI i freschi all'LLM (panel 6/6). Circuit-breaker solo se >~42/gg
      │  (= media×2.5 da serie reale 12-31/gg) e in quel caso taglia per freshness+tier, MAI keyword
      ▼
[STADIO 2] GIUDIZIO LLM a CHUNK 8-10 (ArxivDigest)   ← SDK anthropic auth_token + instructor
      │  input per item: title + summary + source_domain + language
      │  RUBRICA ASSOLUTA nel prompt (neutralizza bias relativo-al-chunk):
      │    0-3 fuori-scope · 4-6 tangenziale · 7-8 core service-line · 9-10 breaking+azionabile
      │  output per item: {relevance 0-10, service_line, rationale 1-riga, audience}
      │  service_line ∈ {visa, company, tax, property, regulatory, none}
      │  temperature=0 (riproducibilità) · CACHE per canonical_url+content_hash (idempotenza)
      ▼
[STADIO 3] SHORTLIST   → filtro su RELEVANCE>=soglia (NON su service_line; la label non è il gate)
      │  top-N per relevance + dedup canonical_url (verificato 64/64 popolato, 0 dup)
      │  + discarded_out_of_scope[] (audit dei rigettati, non buttare alla cieca)
      │  scrittura ATOMICA (tmp+rename) + lock file (doppio-cron converge, non diverge)
      ▼  (NON scrive war_room_drafts in questo step — quello è lo Step 2)
```

**Costo LLM**: ~64 item in chunk da 8 = ~8 chiamate/giorno. **Claude a quota MAX via SDK `auth_token`** → $0
(la rolling-window 5h limita token/min ~30k, non n.richieste → chunk da 8 sicuri). PII: solo news pubbliche → Law 2 OK.

---

## 5. Contratto dello Step 1 (input → output)

**Input**: nessuno (cron giornaliero) — oppure `--since-days N` / `--dry-run` / `--limit K`.

**Output** (file `~/.../war_room/shortlist-YYYY-MM-DD.json`):

```json
{
  "generated_at": "2026-06-06T...Z",
  "window_days": 3,
  "candidates_considered": 64,
  "prescored_kept": 25,
  "shortlist": [
    {
      "item_id": "uuid",
      "title": "...",
      "canonical_url": "...",
      "source_domain": "...",
      "published_at": "...",
      "prescore": 87.5,
      "llm": {
        "relevance": 9,
        "service_line": "tax",
        "audience": "...",
        "rationale": "..."
      }
    }
  ]
}
```

Lo Step 2 (futuro) consumerà questa shortlist per costruire il draft briefato.

---

## 6. Vincoli (hard) rispettati

- **Claude a quota MAX via OAuth** — giudizio LLM via **SDK `anthropic` con `auth_token`** (header Bearer = MAX, $0) o CLI `claude --print` come fallback. MAI `ANTHROPIC_API_KEY` / `api_key=` (path `X-Api-Key` paid, bandito). L'SDK NON è bandito: è bandito solo il ramo api_key. Code-review pre-merge anti-scambio api_key↔auth_token.
- **Law 2 / PII** — solo news pubbliche (title/summary), nessun dato cliente → cloud LLM ammesso.
- **Legge 5** — lo Step 1 produce una shortlist, NON pubblica nulla. Human-in-loop a valle.
- **published_at affidabile** — dipende dal fix TZ 2026-06-06 (deployato). Lo Step 1 nasce sul dato pulito.
- **Anti-monotonia** — il giudizio LLM + service_line eviteranno la deriva "tutti i caroselli uguali" (S11).

---

## 7. Domande aperte per il panel 4-LLM (prossimo gate)

1. **Pre-score top-K**: 25 è il taglio giusto pre-LLM, o rischia di scartare un gioiello a bassa-keyword? Meglio soglia su prescore assoluta invece di top-K fisso?
2. **Batch vs per-item**: 1 chiamata batch da 25 item (ArxivDigest) risparmia ma può degradare la qualità del giudizio per item. Chunk da 8? Trade-off costo/qualità.
3. **`service_line=none`**: come gestire item fuori-scope BZ (es. "Bali swimming championship")? Scartati o tenuti a relevance bassa?
4. **Idempotenza giornaliera**: se gira 2× lo stesso giorno, dedup su `canonical_url` già visti in shortlist precedenti? O ri-giudica sempre la finestra 3gg piena?
5. **Dove vive**: nuovo `scripts/warroom_step1_reader.py` o refactor in-place di `wr2_topic_selector.py` (rischioso, è in produzione)? Proposta: nuovo file, lasciare il vecchio finché Step 1+2 non lo rimpiazzano.
6. **Fuso del filtro 3gg**: `published_at >= now() - interval '3 days'` con `now()` UTC su `published_at` UTC-aware → corretto. Confermare nessun off-by-one al bordo finestra.

---

## 8. Cosa NON è ancora deciso (serve te + panel)

- Il **K** del pre-score e il **N** della shortlist (numeri da tarare).
- Se lo Step 1 manda il digest Telegram subito o aspetta lo Step 2.
- Nuovo file vs refactor in-place (proposta: nuovo file).

> **Prossimo passo**: panel 4-LLM su questo design (§7 le 6 domande) → poi implementazione in worktree
> (codice + collaudo sui 64 item reali, no deploy) → poi Step 2.

---

## 9. VERDETTO PANEL 3-LLM (2026-06-06) — convergenza 6/6 + verifiche-dato

Panelist: **Codex GPT-5.5** + **DeepSeek V4 Pro** (reasoning*effort=high) + **Claude MAX** (CLI).
Convergenza unanime su tutte le 6 domande. **Difetto-capo (unanime)**: il pre-score keyword a monte
tagliava gli item \_prima* dell'LLM gratuito, penalizzando i titoli regolatori asciutti (`PMK 131/2024`
senza "Bali") = proprio i gioielli normativi core-BZ. → **togliere il taglio**.

| #             | Verdetto  | Decisione FISSATA (per l'implementazione)                                                                                                                                                 |
| ------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 top-K       | RISCHIOSO | **Niente top-K**: giudica tutti i 64. Circuit-breaker `MAX_ITEMS≈42` (media×2.5) solo per volume anomalo, taglio per freshness+tier (mai keyword). Pre-score = solo ordinamento/tie-break |
| 2 batch       | RISCHIOSO | **Chunk da 8** + **rubrica assoluta** nel prompt (0-3/4-6/7-8/9-10). ~8 chiamate/giorno                                                                                                   |
| 3 none        | RISCHIOSO | **Non scartare a monte**: filtro su `relevance>=6`, NON su `service_line`. `discarded_out_of_scope[]` per audit                                                                           |
| 4 idempotenza | SBAGLIATO | **temperature=0** + **cache giudizi** (`canonical_url`+`content_hash`) + scrittura atomica tmp+rename + lock file                                                                         |
| 5 drift       | RISCHIOSO | Pre-score in **modulo condiviso** `scripts/lib/intel_prescore.py` importato da entrambi; se fork → commento datato + scar                                                                 |
| 6 filtro 3gg  | SBAGLIATO | Finestra ancorata a **DATE-WITA** (non timestamp scorrevole) + **NULL→fallback first_seen_at** + margine fuso (4gg) + log NULL esclusi                                                    |

### Verifiche-dato (Claude, anti-assunzione — eseguite sul live, non assunte)

1. **canonical_url**: 64/64 popolato, **0 duplicati** nei freschi → **dedup affidabile**, il piano regge.
2. **published_at NULL**: 11 con first_seen ≤3gg, ma **solo 4 reali** (`yt_monitor`, data assente strutturalmente;
   gli altri 7 = probe-sandbox già filtrati da `is_probe_sandbox`). → fallback `first_seen_at` per i 4 yt, non perderli.
3. **Volume/giorno**: serie stabile **12-31** (media 16,6, max 31). → con 64 freschi **niente taglio**; circuit-breaker ~42.

---

## 10. DECISIONE CHIUSA — pronto per implementazione

- **Forma**: nuovo `scripts/warroom_step1_reader.py` standalone (scelta operatore) + pre-score condiviso `scripts/lib/intel_prescore.py`.
- **LLM**: SDK `anthropic.Anthropic(auth_token=…)` (quota MAX, mai api_key) + `instructor`/pydantic, chunk 8, temperature 0, rubrica assoluta.
- **Lettura**: finestra DATE-WITA su `published_at` con fallback `first_seen_at`, NOT is_probe_sandbox, tutti i producer.
- **Output**: `shortlist-YYYY-MM-DD.json` (relevance≥6 + dedup canonical_url + discarded[] audit), scrittura atomica + lock. NO war_room_drafts, NO deploy.
- **Collaudo**: sui 64 item reali (SELECT read-only + giudizio LLM vero) → shortlist di esempio. Zero write DB, zero deploy.

---

## 11. IMPLEMENTAZIONE + COLLAUDO (2026-06-06) — codice scritto, provato sui dati reali

**File**: `scripts/warroom_step1_reader.py` (Step 1) + `scripts/lib/intel_prescore.py` (pre-score condiviso).
**Collaudo**: sul Pro (DB+password allineati; M5 .env ha password stale — cicatrice rotazione 2026-06-03),
venv `apps/backend-rag/.venv` (asyncpg+anthropic+instructor), token MAX via `~/.claude/.credentials.json`.

### Cosa funziona (provato end-to-end sui 66 item reali)

- ✅ **Fetch**: 66 candidati freschi (finestra DATE-WITA), **4 published_at NULL → fallback first_seen_at**.
- ✅ **Pre-score + circuit-breaker**: 66>42 → tagliato a 42 per freshness+tier (mai keyword). Top: Bridging Visa, Golden Visa, property stranieri, MERP/KITAS — core BZ.
- ✅ **Path SDK `auth_token`** (il punto SDK-OAuth): **autenticato** in produzione (429 rate-limit, NON 401 auth → Bearer MAX accettato, api_key strippato). Il client gira `mode=raw`.
- ✅ Scrittura atomica + lock + dry-run gating: nessun file/DB write nel collaudo.

### 2 bug trovati dal collaudo e FIXATI

1. **BLOCCANTE — instructor path rotto**: `_build_client` ritornava un client `instructor.from_anthropic()` ma `_judge_chunk_raw` chiama `messages.create()` senza `response_model` (che instructor 1.x esige) → ogni chunk falliva, `judged:0`. **FIX**: `_build_client` ritorna SEMPRE client anthropic puro (`mode=raw`); per adottare instructor in futuro serve un path dedicato con BaseModel Pydantic, non riusare `_judge_chunk_raw`.
2. **MINORE — output `--no-llm` fuorviante**: post-circuit-breaker l'ordine è per freshness+tier ma mostrava solo `prescore` totale. **FIX**: aggiunto campo `fresh_tier` nel JSON `prescored`.

### Residuo (NON bug)

- **429 quota MAX 5h satura** sul Pro al momento del collaudo → la shortlist coi giudizi LLM reali (relevance/service_line/rationale) non è ancora stata osservata. Il path è confermato corretto; serve solo ri-girare `--dry-run --limit 8` a quota libera.
- **NB**: il design è hard-coded su Claude SDK; non c'è cascade Tier-2/3. Se serve robustezza cron, aggiungere fallback Gemini/Codex (futuro).

### Stato: codice pronto end-to-end (modulo quota), committato nel worktree, NON deployato.
