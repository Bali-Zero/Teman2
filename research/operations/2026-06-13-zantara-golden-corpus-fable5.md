---
date: 2026-06-13
domain: operations
client_case: internal — Zantara Golden Corpus (guard-family class closure + persona golden set)
sources:
  - scripts/openclaw_whatsapp_bridge.py (live guard layer, verified == origin/main == HOME copy at session start)
  - research/operations/2026-06-13-knowledge-decay-audit-fable5.md (41 verified regulatory claims)
  - .claude/rules/cicatrix-scars.md W68 / W72 / W73 (guard-over-match family)
  - research/operations/2026-06-11-fable5-extra-task-allocation.md (§3 close-the-class + §7 persona-layer judgment)
status: SHIPPED — see PR (branch agent/nuzantara/zantara-golden-corpus)
---

# Zantara Golden Corpus — la quarta sweep della famiglia guard trova l'asse linguistico

> Topic scelto in autonomia (sessione Fable 5, 2026-06-13) dopo ricognizione
> anti-duplicazione: la sessione gemella lavorava l'Antibody-Debt ledger infra
> (#1376/#1382), l'altra il WR2 all-hero (#1374), una terza il knowledge-decay
> dei CONTENUTI (#1383). Questo lavoro chiude il quadrante mancante: il
> COMPORTAMENTO del layer che decide cosa arriva al cliente.

## 0. Executive summary

- **11 difetti reali trovati e fixati nel guard layer WhatsApp** — tutti
  confermati empiricamente sui guard live PRIMA del fix, tutti pinnati da
  regressione DOPO. La famiglia W68→W72→W73 aveva trovato 7+ bug sull'asse
  *predicato* (substring-trap, positive-gating); questa sweep trova il nuovo
  asse: **la lingua**. Il guard layer era calibrato in inglese su un canale
  che parla EN/ID/IT.
- **10 gap "wrong-answer-passes"**: risposte SBAGLIATE in indonesiano/italiano
  arrivavano al cliente non clobberate — `"KITAS kamu sudah disetujui"` (status
  inventato), `"la scadenza LKPM è il 10 luglio"` (deadline abrogata), zoning
  Airbnb IT/ID (il guard non si armava affatto), `"può detenere Hak Milik"`
  (l'accento batteva il marker con apostrofo), caffè IT mai riconosciuto, IVA
  IT mai armata + 1 over-match (risposta IT CORRETTA sul B211 "vecchia
  dicitura" clobberata) + **1 falso positivo nominee** trovato dal nuovo probe
  no_trigger ("can you book the hotel under my wife's name?" riceveva la
  lezione sull'illegalità del nominee).
- **GUARD_MATRIX estesa 20 → 80 casi**: pass+clobber × 3 lingue × 10 guard +
  probe no_trigger per ogni guard. **Nuovo META gate**: ogni `_guard_*` futuro
  FALLISCE la suite finché non porta copertura trilingue + no_trigger
  (dimostrato col guard fantasma: 3/3 gate scattano).
- **Catena estratta**: `_apply_reply_guards()` è ora l'unica fonte di verità
  dell'ordine di produzione (endpoint e test la condividono — l'ordering non
  può più driftare). 6 test full-chain nuovi (ordering, no double-mutation,
  format net).
- **Golden corpus seminato**: `apps/evaluator/zantara_persona_eval/golden_corpus.json`
  — 50 scenari × 3 lingue = 150 entry, 5 domini, 4 classi di comportamento
  atteso. Ogni fatto con fonte tracciabile; i load-bearing portano
  `verified_by` = knowledge-decay audit (41 claim verificate contro fonti
  ufficiali). I fatti deperibili portano `valid_until` (lezione F11). È il seme
  della **SSOT dei claim regolatori** che l'audit #1383 dichiarava mancante.
- **Esito finale: 165/165 test verdi** (102 pre-esistenti + 63 nuovi), 0 errori
  schema corpus.

## 1. Perché questo topic (criterio Fable-5-Extra, 3/3)

1. **Contesto totale**: corpus scar famiglia guard + bridge 1.9k righe + audit
   128 claim + 3 lingue + 5 domini regolatori tenuti insieme.
2. **Output load-bearing**: il guard layer decide cosa arriva al cliente
   pagante; il punto-medio è stretto (over-caution = fiducia persa,
   under-caution = responsabilità legale).
3. **Verifica del verificatore**: i `_guard_*` SONO verificatori post-LLM con
   track record di 7+ bug in 3 sweep; questa è la quarta, su un asse che le
   precedenti non vedevano.

## 2. Metodo (il pattern che ha funzionato)

1. **STADIO-0 su disco**: censimento guard su origin/main; scoperta che
   l'harness base W73 era GIÀ stato shippato (20 casi EN-only) — il valore non
   duplicato era l'estensione, non la costruzione.
2. **Probe empirico PRIMA dei fix**: 13 casi ID/IT sospetti eseguiti sui guard
   live → 10 GAP confermati. (Anti-allucinazione: nessun "bug" dichiarato senza
   averlo visto fallire in questo turn.)
3. **Fix chirurgici** con commento-cicatrice in-line per ognuno.
4. **Matrice come contratto**: i probe diventano casi permanenti; il META gate
   rende impossibile aggiungere un guard senza copertura trilingue.
5. **Gate-del-gate dimostrato**: guard fantasma iniettato → 3/3 meta-test
   falliscono con il messaggio giusto.

## 3. Gli 11 fix (file scripts/openclaw_whatsapp_bridge.py)

| # | Guard | Difetto | Fix |
|---|---|---|---|
| 1 | document_status | marker unsafe EN-only → "sudah disetujui" passava | marker ID/IT affermativi (sudah/telah disetujui, gia'/già approvat-, siap diambil, pronta/o per il ritiro) |
| 2 | legacy_b211 | risposta IT corretta "vecchia dicitura" clobberata | "vecchia/vecchio" word-boundary + "non più/tidak lagi" + route_framing corrente/attuale/saat ini |
| 3 | hak_milik | "può detenere" (accento) batteva i marker "puo'" | varianti accentate in _NEGATIONS e _CAN_OWN |
| 4 | lkpm | "10 luglio"/"tanggal 10 juli" non erano stale marker | mesi ID/IT per 7/10 + "tanggal 10" |
| 5 | property_zoning | secondo braccio trigger EN-only → mai armato su IT/ID | + zona, residenziale, residensial |
| 6 | tax_compliance | "IVA/tasse" mai armava il risk-suffix | + iva, tasse (word-boundary) |
| 7 | cafe_pma (msg) | "caffè" (doppia f) non conteneva "cafe" | + caffè/caffe/caffetteria |
| 8 | cafe_pma (reply) | reply-check cieco su caffè/ristorante | + caffè/ristorante/kafe/kedai |
| 9 | nominee | "book the hotel under my wife's name" → lezione nominee (FP) | + book the/book a/book me/hotel nei false-positive admin |
| 10 | (refactor) | ordering chain inline nell'endpoint, non testabile | `_apply_reply_guards()` + `_REPLY_GUARD_CHAIN` |
| 11 | (meta) | matrice EN-only, nessun obbligo trilingue | META gate lingue+no_trigger |

## 4. Cosa resta aperto (onesto)

- **HOME-fork sync (W50/51/52)**: il bridge live gira da
  `~/.openclaw/bin/openclaw_whatsapp_bridge.py`. A PR mergiata va sincronizzata
  la copia HOME + `launchctl kickstart -k gui/501/com.nuzantara.openclaw-whatsapp-bridge`,
  altrimenti i fix non proteggono i clienti reali. (Pianificato come step
  post-merge di questa stessa sessione.)
- **Il corpus è un seme, non un raccolto**: 150 entry coprono i fatti
  VERIFICATI disponibili oggi. Le claim non verificate (VOA 30+30, SPT
  deadline, Second Home funds) sono state deliberatamente ESCLUSE — un golden
  set inquinato è peggio di nessun golden set. Prossimo incremento: verificare
  quei fatti via NB/fonti e aggiungerli.
- **Runner live**: il corpus oggi gata schema+guard-cross-reference in CI; il
  passo successivo è il runner end-to-end (domanda → bridge → LLM → guard →
  scoring contro key_facts) sul pattern del quality-loop a 8 agenti, ma
  ripetibile a comando. Non costruito qui per scope discipline.
- **Freshness cron**: `validate_corpus.py --strict-freshness` va agganciato a
  un cron settimanale con Telegram alert (non a CI PR-blocking — scar flaky
  clock-race). COMP-003 (deadline KBLI 18/06) scade tra 5 giorni: primo test
  reale del meccanismo.

## 5. Numeri (Legge 7)

- Before: 20 casi matrice (EN-only), 0 probe no_trigger, 0 test full-chain,
  0 corpus, **10 wrong-answer-passes + 1 FP live** sui percorsi ID/IT.
- After: 80 casi matrice trilingue, 10 no_trigger, 6 full-chain, 150 entry
  corpus con fonti, **0 gap noti** sui probe, 165/165 verdi, 3/3 meta-gate
  dimostrati sul guard fantasma.
