---
date: 2026-06-19
domain: compliance
client_case: none
status: BLUEPRINT (awaiting Zero GO before build)
sources:
  - data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json (2422 rec, ground-truth, 2026-06-19)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (our v8.0, 1563, enriched-but-presumed)
  - Gemini 3.5 Flash study (book genre) + DeepSeek V4 Pro study (schema) — /tmp/kbli-blueprint/
  - scripts/kbli_enrich_generate.py (how intel_2026 was generated: local DeepSeek-R1, LLM-invented)
---

# KBLI 2025 — BLUEPRINT dei 3 cantieri

> Mandato Zero (2026-06-19): partendo dai 2422 KBLI OSS estratti — (1) come arricchirli in
> modo coerente andando oltre il nostro intel_2026; (2) rifare il kbli-navigator; (3) prodotti
> community: articoli Pulitzer-level + un libro-guida (genere studiato).

## § META-PATTERN (il vero topic, di 2° ordine)

I 3 cantieri NON sono 3 progetti: sono **UNA catena con una sola radice**. Schema-dato → (navigator
+ libro + articoli) ne sono *viste*. La malattia che li minaccia tutti è UNA: **la presunzione
LLM travestita da fatto.** L'abbiamo vista 3 volte nello stesso giorno, in 3 contesti diversi:
1. I 4 titoli forestali 02xxx sbagliati nel nostro JSON (titolo 2020 su uraian 2025).
2. Il nostro `intel_2026` generato da un prompt che *ordina* all'LLM di inventare prezzi/location/tip.
3. Gemini, scrivendo il mock del libro, ha **allucinato 5 codici KBLI su 12** (55120/55130/62019/
   86903/96200 = KBLI 2020 morti) — verificato su disco oggi.

**La cura strutturale (unica, vale per tutti e 3):** uno schema a **strati con provenance**, dove il
fatto e la narrativa sono fisicamente separati e nessun consumatore può scambiare l'uno per l'altro.
Gemini (genere-libro) e DeepSeek (schema) ci sono arrivati indipendentemente — convergenza forte.

---

## CANTIERE 1 — Schema di arricchimento v2 (la RADICE)

### Cosa avevamo "in più" (audit del nostro JSON, da cui ripartire)
| Campo nostro | Coverage | Giudizio |
|---|---|---|
| per_skala[] (licenze PP28, 15 sotto-campi) | 88% | 🟢 ORO operativo — tenere, ancorare a PP28 |
| PMA (status/max_asing/prioritas/kondisi/nota/source) | 100% | 🟢 tenere, strutturare la citazione regolatoria |
| status_mapping → KBLI 2020 | ~100% | 🟢 tenere — è il radar anti-rinumerazione (266 RINUMERATO) |
| sektor_id | 86% | 🟡 tenere |
| intel_2026 (whatItMeans/baliContext/zantaraOpener/...) | **32%** | 🔴 LLM-inventato, non ancorato = la malattia. Isolare in L3. |

### Lo schema v2 — 4 strati con provenance (sintesi DeepSeek, validata)
- **L0 — Ground truth OSS**: judul_id, uraian_id, ruang_lingkup_raw, id_kategori, id_version,
  subklasifikasi (IG00x). Provenance=OSS_API, confidence=HIGH SEMPRE. Immutabile.
- **L1 — Fatti normalizzati (sourced)**: **title_en/description_en come CAMPI SEPARATI** (MAI
  impastati nel judul — è l'errore che ci ha dato i 374 "judul divergenti"!), structured_scope
  (parsato da ruang_lingkup), parent_hierarchy, related_kbli_official (dalle note BPS), keywords.
  confidence HIGH/MEDIUM.
- **L2 — Compliance NAZIONALE**: per_skala completo, PMA con citazione regolatoria STRUTTURATA,
  tka_ketentuan, compliance_effective_date. confidence HIGH (PP28/Perpres/BKPM). **Apertura nazionale
  != registrabilita a Bali (vedi L4).**
- **L4 — DIVIETI/MORATORIE BALI (strato sovrano-locale) -- aggiunto su input Zero**: lo strato che
  mancava, a Bali DECISIVO. Per ogni KBLI: bali_registrabile(bool), bali_status (TERTUTUP/TERBATAS/
  CHIUSO-BALI/BLOCCATO-CLASSE-RISCHIO/OK), motivo+fonte (lettera Gubernur/Pergub/Perda/moratoria),
  virtual_office_ok, note zonazione (green-zone/sempadan/RTRW), regole Banjar. confidence HIGH.
  Caso d'uso che lo giustifica da solo: villa 55203 = PMA-TERBUKA 100% NAZIONALE (L2) ma low/medium-
  low-risk a indirizzo Bali -> BLOCCATA dalla moratoria 13/5/2026 (L4). Senza L4 il navigator mentirebbe.
  Dati GIA raccolti+verificati: research/compliance/2026-06-09-bali-pma-kbli-moratorium-low-risk-block.md
  (moratoria whole-class + virtual-office ban, lettera B.27.000/642) + 2026-06-13-bali-pt-pma-category-
  classification.md (quick-ref per-KBLI: TERTUTUP 55130/47111-2/69100/86904 - TERBATAS 41011/52292/69200/
  86102 - CHIUSO-BALI 70209+proposti 68111/79110/77100). L4 INGERISCE questi, non li inventa.

> Schema a 5 STRATI: L0 OSS - L1 normalizzato - L2 compliance nazionale - L3 editoriale - L4 divieti Bali.
> L2 = "e aperto in Indonesia?"; L4 = "lo posso davvero aprire a Bali?". Due verita oggi confuse in un solo pma_status.
- **L3 — Narrativa editoriale (LLM, recintata)**: intel_2026, investor_usecase_tags,
  related_kbli_suggested, SEO. confidence=LOW SEMPRE + generation_meta{model, human_review,
  fact_sources_used}. **Nessun consumatore usa L3 come fatto.**

Ogni campo non-chiave = ValueObject `{value, provenance:{source, source_document, confidence,
last_verified, verified_by, expires_at}}`. Così non potremo MAI più non distinguere fatto da presunzione.

### CI anti-presunzione (il vaccino, da DeepSeek §5 — adottare)
- **title↔description mismatch** (cosine<0.4) → prenderebbe i 4 forestali AUTOMATICAMENTE.
- **cross-layer contamination scanner** → impedirebbe a Gemini di iniettare codici allucinati.
- **code-renumber awareness** (ledger 2020→2025), **ruang_lingkup completeness**, **source freshness**
  (confronto notturno con OSS id_version), **dead-code detector** (404 OSS → status INACTIVE).

---

## CANTIERE 2 — KBLI Navigator (un RAMO)

**Stato attuale** (verificato): Next.js su Vercel, consuma copia di FINAL_CLEAN (1563), sistema
"gold" separato per ~N codici curati, no intel_2026 inline. Difetti ereditati: titoli troncati/
sbagliati, dati presunti senza provenance, copertura editoriale a buchi.

**Rifacimento (proposta):**
1. **Sorgente unica**: il navigator legge L0+L1+L2 dello schema-v2 (NON una copia divergente).
2. **Detail page = i 4 strati visibili**: titolo ID ufficiale (L0) + EN canonico separato (L1) +
   ruang_lingkup espandibili come l'app OSS (L0, già estratti!) + matrice licenze per-skala (L2) +
   box PMA con citazione regolatoria (L2). L3 (narrativa) mostrato SOLO se human_review=APPROVED,
   altrimenti "AI-draft" watermark.
3. **Provenance tooltip** su ogni fatto ("fonte: OSS 2026-06-16" / "PP28/2024 art. X").
4. **2422 codici** (non più solo 1559 5-digit: anche la gerarchia categoria→gruppo navigabile).
5. SEO: nugget L3 in meta, mai nel titolo factual.

---

## CANTIERE 3 — Libro-guida + articoli (l'altro RAMO)

### Genere (studio Gemini, validato): "Narrative Relocation/Business Guide"
Modello: *Shoe Dog* (verità imprenditoriale) ⨯ *Lonely Planet* (sensoriale) ⨯ Nolo legal-guide
(utilità). Tecnica centrale = **Trojan Horse**: vendi il sogno (narrativa), consegna le regole
(verdura) nei momenti critici della trama. Voce = **"Pragmatic Sherpa"** (2ª persona per i consigli,
3ª per le storie). Protagonisti compositi (Mark/Sarah = clienti reali compressi).

### Struttura (3 parti)
- **Parte I — The Landing**: mindset, PT PMA vs Nominee (l'Original Sin).
- **Parte II — The Dreams** (cuore): 1 capitolo per archetipo di sogno imprenditoriale, ognuno col
  **modulo a 7 battute**: The Dream → The Reality Check → **Sidebar KBLI Fact Sheet** → The Money →
  The Timeline → The Bali Angle → The Pitfall (autopsia del fallimento #1 di quel KBLI).
- **Parte III — The Roots**: Banjar, HR, exit strategy.

### Monetizzazione/community (Gemini): libro = top-of-funnel.
- QR a fine di OGNI fact-sheet → "scan per lo stato LIVE 2026 di questo KBLI sulla piattaforma
  Nuzantara" (= il navigator! i due rami si chiudono in cerchio + lead-gen + email capture).
- Tier: Libro $25 → +community Circle/Discord $99/yr → +consulto 1h $500.
- **Regola d'oro del libro**: MAI hardcodare cifre esatte/leggi che scadono → metriche relative +
  rimando al dato live. (Esattamente l'anti-presunzione applicata all'editoriale.)

### ⚠️ GUARDRAIL CRITICO (lezione viva di oggi)
Gemini ha allucinato 5/12 codici KBLI nel mock. **Ogni codice/numero/regola nel libro DEVE
pescare da L0/L1/L2 dello schema-v2, MAI dalla memoria dell'LLM.** Il libro è un consumatore di L3
+ riferimenti factual, esattamente come navigator e quote-engine. Pipeline editoriale = stesso
CI anti-presunzione (un claim factual nell'articolo che diverge dal value corrente → alert).

---

## CANTIERE 3bis — 20 articoli editoriali per il website (Pulitzer-level)
Non capitoli di libro: pezzi standalone per balizero.com, ognuno ancorato a uno o piu KBLI + L4.
Stessa voce/guardrail del libro (codici da schema, MAI da memoria LLM). Angoli proposti (mix
evergreen + 2026-hot): la moratoria Bali spiegata (perche il tuo KBLI "aperto" e bloccato), villa
vs pondok-wisata (55203 vs 55130 TERTUTUP), il mito del virtual-office, beach-club stack (56101/
56301/56302), nominee vs PT PMA, zonazione green-zone, real-estate 68111 sotto moratoria, content-
creator codici veri 2025 (59112/60390 non 74149), wellness/clinica (86105/96220), F&B per stranieri,
import/export, IT high-risk come scappatoia legittima (63122), TKA/foreign-worker, paid-up vs
investimento 10mld, ecc. Ogni articolo: QR/-link al navigator. Pipeline = multi-LLM con gate fattuale.

## CANTIERE 4 — Re-ingestione Qdrant (sostituire l'attuale)
- **Collection attuale identificata**: `kbli_2025_final` (+ variante `_hybrid`, + `kbli_tka`), risolta
  via `resolve_collection_name()`. Consumata da kbli_notebook.py, dashboard_summary.py, knowledge/service.py.
- **VINCOLO FERREO (golden rule #9)**: embedding `text-embedding-3-small` 1536-dim FROZEN. Re-ingest =
  recreate con STESSO modello, payload nuovo (schema-v2 flat: kode/judul/uraian/... + bali_status L4).
  93k vettori globali — non cambiare il modello.
- Procedura: build payload da schema-v2 -> recreate collection (1536) -> re-embed -> verify count +
  smoke query -> swap atomico. Su Pro (dove gira Qdrant). NON su M5.
- Include il **Bali block note** che il file moratoria segnava come "pending" (Qdrant re-ingest mai fatto).

## CANTIERE 5 — Update NB-3 (Company, UUID 933509f9)
- NB-3 = SOLE consumer NotebookLM company/KBLI (Contract 2). Aggiungere: schema-v2 come source +
  lo strato L4 (moratoria/divieti Bali) che oggi NB-3 NON ha (portava solo status nazionale).
- **CORREGGERE 2 errori NB-3 noti** (gia documentati): (1) "74149 = codice nuovo 2025" e FALSO (74149
  non esiste nel 2025; e codice 2020); (2) conflation 2020/2025 su codici creator. Veri 2025: 59112/
  60103/60203/60390/90113/90200.
- Propagazione gia parziale: source afe820b0(v1)+81630d48(v2) aggiunti per la moratoria. Da consolidare.

## § VINCOLO CRITICO scoperto (L4 + warning Zero "non re-ingestire") — verificato su disco
1. **RIUSO inventariato** (NON rigenerare): L0 2422 (oggi) · per_skala 1381 · PMA 1563 · status_mapping
   1562 · **intel_2026 GIA su 504 codici** (RIUSA legacy/LOW, restano ~1055 da generare) · gold-content
   navigator (2MB ts) · Qdrant kbli_2025_final ESISTE (update delta, non recreate se payload uguale) ·
   NB-3 fonti afe820b0+81630d48 GIA aggiunte (verifica, non duplica).
2. **L4 NON ingeribile alla cieca**: i 2 file research-divieti-Bali usano numerazione KBLI 2020.
   Verificato: **10 codici-status su 20 sono MORTI nel 2025** (55193 villa->55203, 55110/55120 hotel->
   55101-106, 55130/55194/69100/69200/86904/01119/02100 da rimappare). L4 DEVE passare per il ponte
   2020->2025 (status_mapping + KBLI_2017_TO_2025_MAPPING.json) prima di entrare nello schema.
   = quarta apparizione della stessa malattia (presunzione/numerazione-stale). Conferma necessita di L1+provenance.

## § TERAPIA — cosa è già fatto in questa sessione
- Estratto + salvato il ground-truth OSS (2422). Comparato col nostro (report 2026-06-19).
- Diagnosticata la malattia comune (presunzione) e verificata 3× su disco.
- Studi di ampiezza Gemini+DeepSeek raccolti e VERIFICATI (5 codici allucinati intercettati).
- Pilota accommodation (26 KBLI 55xxx/56xxx) pronto per applicare schema-v2.

## § SOLO-OPERATORE (decisioni di Zero, prima di build)
1. **GO sullo schema-v2 a 4 strati?** È la radice — tutto il resto ne dipende.
2. **Arricchimento L2/L3 dei 2422**: con cosa? (Le fonti L2 = PP28/Perpres servono ingestione vera;
   L3 = LLM ma con gate. Costo/tempo da decidere.)
3. **Navigator**: rifare in-place o nuovo? (impatta SEO/URL esistenti su balizero.com/kbli-navigator)
4. **Libro**: lingua (EN per investitori esteri?), editore/self-pub, chi è l'autore-voce.

## Prossimo passo proposto (questa o prossima sessione)
Applicare schema-v2 alla VILLA (55203) end-to-end come prova viva: record completo 4-strati +
mock detail-page navigator + il vero capitolo-libro "The Boutique Villa" coi codici VERI (55203,
non il 55120 allucinato). Una colonna verticale prima di scalare a 2422.

Vedi [[discovery_oss_rba_kbli_api_extraction_2026_06_19]] · [[discovery_kbli_blueprint_2026_06_19]].
