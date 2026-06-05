# Fix proposto — `published_at` timezone bug in bali_intel_scraper (dossier per 4-LLM panel)

**Data**: 2026-06-06
**Stato**: PROPOSTA — in review 3-LLM panel (Codex GPT-5.5 + DeepSeek V4 Pro + NB-1), NON eseguito
**Tocca**: codice scraper (sorgente) + backfill 142 righe su DB produzione → richiede panel pre-approval (CLAUDE.md §6)

## Sintomo (dati reali verificati sul Pro, 2026-06-06)

- `intel_items`: 328 tot. **15 item con `published_at > now()`** (nel futuro), tutti `pub=2026-06-06 / seen=2026-06-05`. **44 item con lag `first_seen::date - published::date = -1`**. **142 item** del producer `bali_intel_scraper` coinvolti.
- `published_at` popolato 306/328 (93%); i 22 NULL sono quasi tutti probe/test (`probe-sandbox.example.test` ×10, `test.balizero.com`).
- Pro è WITA: `date` → `04:10 WITA`, `date -u` → `20:10 UTC` (offset +8h).

## Causa (diagnosi, file:riga)

1. `apps/bali-intel-scraper/scripts/unified_scraper.py:218` (e `:266`): `'scraped_at': datetime.now().isoformat()` → datetime **naive** che rappresenta l'ora locale WITA (UTC+8).
2. `published_at` vero NON viene mai estratto dalla fonte: il campo `published` (stringa RSS, con offset `+0700`) resta solo stringa, mai convertito.
3. `apps/bali-intel-scraper/scripts/run_intel_pipeline.py:1825`: `"published_at": art.get("published_at") or art.get("scraped_at")` → siccome `published_at` è sempre None, ripiega su `scraped_at` (naive WITA).
4. `apps/backend-rag/backend/services/intel/intel_lake_service.py:191`: asyncpg lega il datetime naive a colonna `TIMESTAMPTZ` → **assume UTC** → ogni data risulta +8h nel futuro vs `NOW()` UTC.

→ Non è fonte sbagliata né parsing tz: è `datetime.now()` senza `timezone.utc`.

## Fix codice proposto (3 modifiche)

**(1) `unified_scraper.py:218` e `:266`** — rendere `scraped_at` UTC-aware:

```python
# PRIMA:
'scraped_at': datetime.now().isoformat()
# DOPO:
from datetime import timezone
'scraped_at': datetime.now(timezone.utc).isoformat()
```

**(2) `unified_scraper.py:207` (`_extract_from_feed_entry`)** — estrarre la VERA data articolo dal RSS, normalizzata a UTC, così non si ripiega più su scraped_at:

```python
from dateutil import parser as _dp
from datetime import timezone
_pub_str = entry.get('published', '')
_pub_dt = None
if _pub_str:
    try:
        _pub_dt = _dp.parse(_pub_str)                    # tz-aware se fonte dà +0700
        if _pub_dt.tzinfo is not None:
            _pub_dt = _pub_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        _pub_dt = None
# nel dict restituito:
'published_at': _pub_dt.isoformat() if _pub_dt else '',
```

**(3) `feed_parser.py:110,126,128`** (path backend app) — `datetime(*pp[:6])` → aggiungere `tzinfo=timezone.utc` (feedparser.published_parsed è già UTC ma senza tzinfo):

```python
from datetime import timezone
published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
```

## Backfill SQL proposto (142 item già sfasati)

Lo sfasamento è **uniforme +8h** (sempre `scraped_at` WITA, mai mix +7/+8 perché il valore non viene dalla fonte).

**Dry-run (conta, zero modifiche):**

```sql
SELECT COUNT(*) FROM intel_items ii
JOIN (SELECT DISTINCT item_id FROM intel_observations
      WHERE producer_name = 'bali_intel_scraper') obs ON ii.id = obs.item_id
WHERE ii.published_at > ii.first_seen_at
  AND ii.published_at < ii.first_seen_at + interval '9 hours';
```

**Backfill (solo dopo dry-run + go):**

```sql
UPDATE intel_items ii
SET published_at = published_at - interval '8 hours'
FROM (SELECT DISTINCT item_id FROM intel_observations
      WHERE producer_name = 'bali_intel_scraper') obs
WHERE ii.id = obs.item_id
  AND ii.published_at > ii.first_seen_at
  AND ii.published_at < ii.first_seen_at + interval '9 hours';
```

Guardia `< first_seen + 9h`: evita di toccare articoli legittimamente programmati nel futuro.

## DOMANDE AL PANEL (cercate i buchi)

1. Il backfill `-8h` è davvero sicuro? La guardia `published_at > first_seen AND < first_seen+9h` cattura SOLO i veri sfasati, o rischia falsi positivi/negativi? Esiste un caso in cui lo sfasamento NON è +8 (es. scraper girato da un'altra macchina UTC, o DST — l'Indonesia non ha DST, ma confermate)?
2. Il fix (2) che estrae `published` RSS: cosa succede se la fonte dà una data SENZA timezone (naive) o solo `YYYY-MM-DD`? `_dp.parse` la rende naive → `.tzinfo is None` → la lascio naive: è giusto assumerla UTC o introduco un nuovo bug? Meglio fallback esplicito?
3. C'è un rischio che fixare lo scraper + backfill insieme crei una finestra di doppio-conteggio o di item che "saltano" il filtro 3gg durante la transizione?
4. Ordine: fix-codice PRIMA o backfill PRIMA? (proposta: fix-codice prima → nuovi item giusti; poi backfill → vecchi item giusti). Confermate o invertite?
5. C'è un consumer a valle che si rompe se `published_at` di 142 item cambia di -8h? (router intel usa first_seen non published; NB-pusher; observability dashboard con `first_seen > now-7d`). Verificate impatto.
6. Il fix (1) cambia `scraped_at` da naive a aware: rompe qualche altro consumer di `scraped_at` che lo assumeva naive-locale?

---

## ESITO PANEL (Codex GPT-5.5 + DeepSeek V4 Pro, 2026-06-06) — convergenza, 3 difetti reali bloccati

- **#2 SBAGLIATO** (Codex)/RISCHIOSO (DS): `.replace(tzinfo=None)` su data naive ricrea il bug all'indietro → salvare **sempre UTC-aware**; date nude → assumi WITA esplicito, mai naive; nessuna data → NULL (non scraped_at).
- **#1 RISCHIOSO**: guardia `<first_seen+9h` troppo larga (becca post programmati) → restringere a `published_at > now()` (sintomo certo).
- **#3+#6 RISCHIOSO**: scraper vivo durante backfill = nuovi sfasati + 2 epoche su scraped_at; fix incompleto (6 scraped_at, non 2) → pausa writer + fixarli TUTTI + import `timezone`.
- **#4 SICURO**: ordine = pausa scraper → fix codice tutti gli host → verifica no nuovi published>now → backfill.

## FIX v2 APPLICATO (worktree, NON deployato/eseguito)

- `unified_scraper.py`: aggiunti helper `utc_now_iso()` + `normalize_published()` (assume Asia/Makassar se naive, sempre UTC-aware, None se assente); **5 `scraped_at` → `utc_now_iso()`**; `published_at` normalizzato nei 2 path (feed entry + parse_article).
- `run_intel_pipeline.py:1825`: `published_at or scraped_at` → **solo `published_at`** (può essere None, mai scraped_at).
- `feed_parser.py` (codice morto, importato solo da sé — fixato comunque anti-trappola): 4× `datetime(*..parsed[:6])` → `+ tzinfo=timezone.utc`.
- `py_compile` OK su tutti e 3. 0 `scraped_at` naive residui, 0 fallback-scraped_at residui.

## BACKFILL v2 (guardia ristretta dal panel)

```sql
UPDATE intel_items SET published_at = published_at - interval '8 hours'
WHERE id IN (SELECT DISTINCT item_id FROM intel_observations WHERE producer_name='bali_intel_scraper')
  AND published_at > now() + interval '1 hour';   -- solo i CERTI nel futuro
```

## DRY-RUN ESEGUITO 2026-06-06 (zero modifiche, sul Pro)

- **15 item** toccati (vs 142 della guardia v1 → **127 ambigui salvati**).
- **0 item** resterebbero nel futuro dopo -8h → sfasamento confermato uniforme +8h.
- Prova ai dati: tutti `pub=06-06 01:0X` / `seen=06-05 17:3X` (= esatto offset WITA). Sono oro Bali Zero (PPh UMKM, OSS RBA, red flags villa, deportazione 13 WNA, scam syndicate, Golden Visa).

## PROCEDURA SICURA (da eseguire con go Antonello, scraper gira LOCALE sul Pro via OpenClaw cron 03:00 WITA)

1. PAUSA scraper cron (launchctl disable / OpenClaw) — niente nuovi sfasati.
2. Deploy fix: `git pull` sul Pro (+ Mini se replica). Lo scraper NON è su Fly → niente pipeline Fly, è un pull locale.
3. Verifica: nuovi item non hanno `published_at > now()`.
4. Backfill v2 (i 15 certi).
5. Riattiva scraper.

## APERTI (onesti)

- I **44 lag-1 ambigui** (data-only WITA→00:00, non-futuri): il fix-codice li sistema per il futuro; i vecchi li LASCIO (rischio basso, "1 giorno prima", e -8h potrebbe essere sbagliato se erano date legittime). Non backfillati.
- **NB già pushati**: il backfill non li riscrive su NotebookLM (impatto basso).
- `unified_scraper.py:388` `'timestamp': datetime.now()` (metadata di run, non published_at) lasciato naive — non nel path del bug.
