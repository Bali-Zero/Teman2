---
name: intake
description: "Intake corner — the live shared context for the document-intake organism (WhatsApp/Drive docs → OCR → classify → extract → route → attach-to-client). Load BEFORE touching the intake pipeline, the review_pending queue, the refinery pilot, the auto-attach gates, or the CRM writer — or when Zero says /intake, 'coda intake', 'review queue', 'auto-attach', 'refinery'. Holds: the north star (drain the queue with ZERO mis-attribution), the anatomy map (every table/file/gate/flag), the tier logic, LIVE STATE, and the blood-bought rules (2026-05-17 identity-hallucination scar)."
---

# INTAKE — the document-intake organism

> **North star:** every document that arrives (passport, KITAS, visa, KTP, akta, NIB, NPWP,
> bank statement…) lands attached to the RIGHT client, or is honestly quarantined — **never
> attached to the wrong person.** The backlog is finite (~35.8k `review_pending`); drain it by
> corroboration, not by guessing. **A wrong attach is worse than an unattached doc** (2026-05-17
> scar: name-frequency auto-attach → 12 mis-attributed summaries purged by hand).

---

## 0. The one rule that governs everything

**Auto-commit ONLY on strong-identifier corroboration** (passport / KITAS / NPWP / NIK **number equal**
between the document and the client record). **Name-only is NEVER an auto-commit** — it is the exact
failure mode of the 2026-05-17 identity-hallucination scar. Name-only, at most, pre-fills a decision;
it never writes autonomously without a second concordant signal. The refinery may **quarantine** (say
"not attachable") — that is a correct terminal state, not a failure. Forcing an attach on the ~25k
no-match mountain is forbidden.

---

## 1. Anatomy — where the organism lives

**DB (LOCAL, not Fly — scar W87):** `nuzantara_dev` on `127.0.0.1:5432`, user `nuzantara` (trust auth,
SELECT-only for inspection). The MCP `postgres-nuzantara` points at PROD and is the WRONG store for
intake — always use the local dev DB for intake work.

Core tables:

| Table                             | Key columns                                                                                                                                                                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `document_routing_proposal` (`p`) | `id`, `queue_id`, `status` (**review_pending** / review_claimed / routed / **auto_routed**), `entity_resolution` (JSON: `candidates[]{table,id}`, `doc_type`, `decision`), `routing` (JSON: `fields`, `decision`), `commit_gate` |
| `intake_queue` (`q`)              | `id`, `stage_output` (JSON: `classify.ocr_text_per_page[]`, `extract.fields`, `ocr.pages[]`), `source`, `source_ref`, `blob_hash`, `pipeline_version`                                                                            |
| `intake_commit_audit`             | `proposal_id`, `client_id`, `outcome` (dry_run/blocked/committed/failed/rolled_back), `committed_by`, `dry_run` (bool) — every decision recorded, reversible                                                                     |
| `clients`                         | `id`, `full_name`, `phone_normalized`, `passport_number`, `kitas_number`, `nationality`, `deleted_at` (soft-delete)                                                                                                              |

**Extracted fields shape:** `routing.fields` (fallback `stage_output.extract.fields`); each value is
`{value, confidence, source_page}` or a scalar. Strong-id keys: `passport_no`, `kitas_no`.
**Strong-id normalization (canonical):** `re.sub(r"[^A-Za-z0-9]","",str(v)).upper()`, keep only `len>=6`.

**Pipeline (code, in `apps/backend-rag/backend/services/intake/`):**

- `routing.py:1290` → `_try_auto_attach_after_route()` runs the auto-attach gates right after a proposal is routed.
- `auto_attach.py` — the 3 **already-built, tested** gates (all default OFF):
  - `try_auto_attach` (LEVA-2): strong-id ⟂ **phone** concordance.
  - `try_direct_phone_auto_attach`: direct-chat phone-only.
  - `try_nameid_auto_attach` (LEVA-3): strong-id + document-subject-**name** concordance (no-phone sources).
- `writer.py` — the SINGLE safe commit path (reuse it, never raw SQL):
  - `plan_commit(proposal, conn, *, committed_by, override_client_id=None, …) -> CommitPlan` (`.blocked`, `.block_reasons`, `.ops`). READ-ONLY; validates against current DB (P0#3: e.g. **soft-deleted client → blocked**).
  - `execute_commit(plan, conn, *, dry_run=True, advance_from="review_claimed", advance_to="routed") -> CommitResult` (`.outcome`, `.audit_id`). System auto-attach uses `advance_from="review_pending", advance_to="auto_routed"`. `dry_run=False` **requires** `INTAKE_WRITER_ENABLED` truthy, else raises before any write.
  - `rollback_commit(conn, client_id=…, idempotency_key=…, committed_by=…)` — detaches + reopens the proposal.
- `extract.py` — field extraction; `client_enricher.py` — writes doc strong-id onto the client (backfill primitive), same TX as the doc write.

**Feature flags (env, read at call time, ALL default OFF; both the specific flag AND `INTAKE_WRITER_ENABLED` must be on for any autonomous write):**
`INTAKE_WRITER_ENABLED` · `INTAKE_AUTO_ATTACH_ENABLED` · `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED` · `INTAKE_NAMEID_AUTO_ATTACH_ENABLED`.
**Arming pattern:** for a surgical batch, set the flags **in the batch process env only** (never flip the live routing daemon / never a Fly secret) → blast radius = exactly the proposals the batch iterates.

---

## 2. The tier logic (what may write, and how)

| Tier                                                           | Signal                                             | Precision (135 ground-truth)                                   | Headless?                                   |
| -------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------- |
| **Deterministic strong-id**                                    | doc passport/kitas == candidate's, exactly 1 match | **61/61 = 100%**                                               | ✅ safe — arm it                            |
| Panel-unanimous name-only + 2nd signal (phone/nationality/DOB) | both LLMs MATCH same client + a corroborator       | ~100% in-sample (survivor bias)                                | ⚠️ only with the raised bar, measured first |
| Single-model name-only                                         | one LLM MATCH, dissent                             | **owns the only error** (prop 12923: picked 4037 vs truth 659) | ❌ quarantine, never auto                   |
| No match / 0-candidate                                         | —                                                  | —                                                              | quarantine (correct terminal state)         |

**Ambiguity even at strong-id level:** if a doc strong-id matches **>1** client → exclude (data-quality
lead, usually duplicate client records — see the 62130 case, 7 clients one passport).

---

## 3. The refinery pilot (the measuring instrument)

`scripts/intake_refinery_pilot.py` (worktree `backend-rag-intake-refinery`). Panel = `qwen3.5:9b` +
`aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` (local Ollama, `think:false`, `format:json`) + DeepSeek
(dead, 402). Modes: `--mode groundtruth` (precision vs `intake_commit_audit` committed truth) /
`--mode sample-review` (dry triage of `review_pending`). Run: `cd apps/backend-rag && source .venv/bin/activate`
then `PYTHONPATH=. python scripts/intake_refinery_pilot.py --mode groundtruth --limit 135`.

**Proven findings (2026-07-18):**

- **Panel width / model strength is SECOND-ORDER.** SEA-LION-32B over qwen-9B added **0** auto-commits
  (rescued 1 NONE→triage-candidate). The auto-commit bottleneck is **structural** (CRM has ~2.6% passport,
  0% kitas) — no model can corroborate against absent data. A cloud seat (GLM etc.) is not the lever.
- Deterministic tier: **100% precision**. Name-only single-model owns the only observed error.

---

## 4. Sizing of the 35,796 `review_pending` (read-only scan, 2026-07-18)

- `HAS_DOC_STRONGID` = **5,147** (passport 3,783 / kitas 920 / visa 444).
- `DET_MATCH_NOW` ≈ **20-21** — doc strong-id already equals a candidate → auto-committable today.
- `N1_BACKFILL_FUEL` = **1,338** — single-candidate + doc strong-id the client LACKS → each confirmed
  attach writes that id onto the client (`client_enricher.py`), compounding future auto-corroboration.
- **~25,402 (71%) zero-candidate** — strong-id CORROBORATES, it does not FIND → needs Station 1+2
  (re-OCR + all-clients strong-id/name re-search). This is the volume; the panel does not touch it.

**The levers, in order of volume:** identity-backfill (1,338) + re-OCR/re-search (25k) ≫ deterministic
tier (20) ≫ panel width (0). Reviewers/LLMs drain the human tail; they do not replace the missing
structural signal.

**UPDATE 2026-07-18 — Station 1+2 rescue MEASURED, the 25k mountain is structurally stuck** (full-pop
scans, report `research/operations/2026-07-18-intake-station1-2-rescue-recall.md`):

- **Every one of the 25,400 carries `reason="no strong identifier, no fuzzy name >= 0.40"`** — fase4
  already ran strong-id + fuzzy≥0.40 and correctly found nothing. NOT a too-narrow bug.
- **Station 2 (re-search on already-extracted data, no re-OCR) recovers ~9 of 25,400 (0.04%)**:
  strong-id→client **2**, person-name→client(≥0.45) **7**, company-name→client **1**, transitive
  blob-inherit **0**. Root cause: the CRM has **313 passports / 1 kitas / 62 company_names** — it
  lacks the keys to match against. Strong-id CORROBORATES, it does not FIND.
- **Instrument validated (W65):** attached docs' names trigram-match their own client at avg 0.79,
  ≥0.45 in 90% (87/97). So the 7/5,661 is real — the subjects are genuinely not in the CRM
  (prospect / third-party on KTP-KK-akta / never-entered), ~88% genuine no-match.
- **Station 1 (re-OCR) structurally BLOCKED at scale:** of the 25,400 blobs only **594 (2.3%) still
  exist on disk** — `com.nuzantara.intake-blob-retention` (TTL=7d) unlinked the rest. **Of the 594
  present, 0 are stubs.** You cannot re-OCR files that are gone. Re-fetch from Drive is possible
  (`source_ref="drive:<file_id>"`, 24,276 IDs) but costs 24k downloads + 24k vision passes for a
  ~0.1% match ceiling — economically absurd, and does not fix the missing CRM keys.
- **Station 0 (dedup/junk) is the one real-volume lever left** (reads blob_hash, not the blob file):
  **2,152 removable exact-dup blobs** (1,090 groups) + **203 hard-junk non-docs** (.zip/.aae/.mp4/…)
  → 2,355 rows (9%) can reach a correct terminal state, zero mis-attribution risk. Queue hygiene,
  not recovery. Reproducible: `scripts/intake_station0_report.py` (dry-run).
- **The real levers (root cause):** (1) identity-backfill (fill CRM keys so future docs corroborate);
  (2) retention-TTL extension / cold blob-archive (so re-processing has raw material). NOT more
  re-OCR, NOT panel width, NOT a cloud reviewer seat.

---

## 5. LIVE STATE (update on every material change)

- **2026-07-20 — LANE A CHIUSA (F26 + PROVE-LIVE su entrambe le superfici) · LANE B: PR #2879
  aperta, 3 gate CI risolti, wave-1 execution ancora sospesa su GO Zero.**
  **Lane A:** round-17b (Codex diretto, teammate sibling non più raggiungibile dopo un
  riavvio harness) ha confermato F24/F25 CHIUSI e sollevato **F26** (MEDIUM): la
  risoluzione whatsapp era veto-only, non poteva fare da ANCORA quando phone/phone_normalized
  erano assenti. Fix: `_resolution_anchor(norm_val, raw_val, wa_val)` in `crm_delivery.py` —
  un solo oracolo per pre-lock/under-lock/post-upload, ognuno fail-closed su colonna
  inutilizzabile o ≥2 core divergenti. Re-verify CLEAN. PR #2787 era già stata mergiata da
  una sessione sibling PRIMA che i fix round-17 atterrassero → nuovo branch/PR **#2866** da
  post-merge origin/main, auto-merge riarmato, mergiato, **Fly v3856 deployato** (health 200,
  GH_SHA match) e **worker locale `com.nuzantara.intake-worker` riavviato** (`launchctl
kickstart -k`, PID nuovo 42298 confermato fresco — il PID precedente 70682 girava codice
  stale rispetto al checkout `~/nuzantara-deploy` già aggiornato). **PROVE-LIVE completo su
  entrambe le superfici.**
  **Lane B:** commit+push del build (`b0345b010d`) + **PR #2879 aperta** (branch
  `agent/nuzantara/backend-rag/intake-clienti-non-a-crm`) con auto-merge armato — i 10 round
  Codex (6→15, CLEAN) fungono da adversarial review. 3 required check CI fallivano al primo
  giro: **`check-docs-sync`** (README.md/docs/AI_ONBOARDING.md — DOCSYNC block stale, main
  era avanzato dal taglio del branch: W86, regen nello stesso commit) · **`antidotes`**
  (`test_pending_arms_report.py::test_real_ledger_has_zero_phantom_operator` — la voce
  R13-3 in PENDING-ARMS.md usava "single-operator tool" in prosa, substring-match sul campo
  owner del classificatore phantom-operator; riformulato "single-user tool") · **`R1 gate —
adversarial review present`** (`scripts/check_adversarial_review.py` richiede frontmatter
  YAML `---...---` con `adversarial_review: codex` + sezione `## Adversarial review` — il
  design doc aveva solo prosa `date:/domain:/...` senza i delimitatori `---`; aggiunta la
  fence + una sezione che riassume l'intero arco a 10 round). Tutti e 3 verificati verdi
  localmente (agent backend-verifier indipendente) prima del push (commit `a78769c770`,
  W97 confermato). **Wave-1 EXECUTION resta sospesa**: voce dedicata in PENDING-ARMS
  (`operator[business]`) — è la prima creazione reale di contatti CRM da questa pipeline
  contro il book vivo, richiede GO esplicito di Zero.

- **2026-07-19 — CLIENTI-NON-A-CRM (GO Zero): census DONE, design at adversarial gate.**
  Program: auto-create missing contacts from drive/doc identity signals (the 88%-ceiling
  attack; precedent PR #2669 wa-intake autocreate). Census on the 8,255 identity docs
  (passport/kitas/visa/ktp/npwp with saved extract fields, review_pending+quarantine):
  **A auto-creatable 3,348 docs → 2,586 distinct sids → wave-1 effective 1,691 contacts**
  (exclusive-name sids only; 895 multi-sid/289 names → quarantine review) · B name-conflict
  4,008→410 · B id-already-exists 403→179 (data-quality leads, NEVER merge) · B incomplete
  295 · C discard 201. Design: `research/operations/2026-07-19-drive-contact-autocreate-design.md`
  — origin='drive-intake', killswitch default OFF, m248 strong-id advisory locks, NIK never
  written to npwp column (lead_metadata only), batch_id reversibility with guards (docs/
  practices/human-touch), post-create route-only reroute (0 auto-attach — creates contacts,
  never attaches). **Gate round-1: NO-GO, 11 BLOCKER** (identity≠client, syntactic-only
  evidence, renewed-passport dup risk, lock≠constraint, NIK invisible, no tombstone,
  non-atomic report…). **REVISION v2 written** (same spec file): local
  `intake_identity_ledger` with UNIQUE(kind,canonical_value) as the single
  constraint/recovery/tombstone/NIK mechanism; evidence gate = validate.valid +
  distinct-blob agreement + matcher's own validator; fuzzy-name ≥0.45 exclusion vs
  existing clients; ≥0.6 name-variant clustering; per-candidate in-TX revalidation with
  fields fingerprint; companies-npwp namespace; hardened rollback (FOR UPDATE + FK sweep +
  content-vs-ledger); manifest-digest apply gate, hard-cap 200. **Gate round-2: 8 BLOCKER
  residui** (reroute può AUTO_ATTACH se i killswitch del worker sono armati → serve
  soppressione per-queue o verifica killswitch; ledger non vincola clients/companies —
  unicità key-book aperta; revalidazione pre-INSERT deve rieseguire TUTTO il predicato A;
  NIK → ESCLUDERE i 59 dalla wave 1; rollback con full-row business fingerprint;
  `validate.valid IS TRUE` + validator SSOT nominato (routing.\_normalize_passport NON
  applica 6-9); pulire contraddizioni interne v2; census v2 per-kind coi nuovi gate PRIMA
  del GO). Il resto del round-1 è chiuso. **REVISION v3 written (same spec file, 2026-07-19):
  all 8 closed** — (1) reroute-can-auto-attach CONFIRMED REAL on the live worker (plist:
  all 4 killswitch armed by m248) → per-batch suppression keyed on
  `pipeline_version='v2.3-drive-autocreate'` at the `_try_auto_attach_after_route`
  chokepoint (guilt+innocence tests, W99 marker-survives-rewrite test) + post-lot
  0-auto_routed assertion with freeze; (2) global unique impossible (62130: 7 clients/1
  passport) → in-TX recheck under lock vs clients+companies + post-lot key sweep with
  freeze; (3) census and apply share ONE `candidate_predicate()` — full re-run in-TX,
  fingerprint is short-circuit only; (4) KTP/NIK 59 OUT of wave 1; (5) rollback = full-row
  business fingerprint (content, not updated_by proxy) + FOR UPDATE + FK sweep; (6)
  validator honesty: NO existing 6-9 validator exists (routing=strip+upper,
  ClientValidator=`[A-Z0-9]+`) → new named `drive_autocreate_validity.py` (passport
  `^(?=.*[0-9])[A-Z0-9]{6,9}$` ICAO 9303, kitas ≥6 alnum+digit, npwp 15/16 ASCII);
  matching-normalization stays routing.py's own; validate-stage branch fixed by census-v2
  measurement, never silent; (7) contradictions resolved (clustering gate IS wave-1, UX is
  wave-2; GO=program, apply=GO-WAVE-1); (8) GO binds to census-v2 per-kind numbers +
  manifest digest, not the v1 1,691. **CENSUS V2 EXECUTED (2026-07-19):** built
  `scripts/intake_drive_contact_autocreate.py --census` (read-only) +
  `backend/services/intake/drive_autocreate_validity.py` (creation validity ≠ matching
  normalization; 17 guilt+innocence tests green; predicate `classify_perimeter` shared
  census/apply, tests import it from the script — no drift twin). Numbers: perimeter
  7,895 · validate coverage 1.0 → STRICT branch · **A-effective 252 contacts (passport
  158 / kitas 88 / npwp 6)** vs v1's 1,691 (−85% — the gates working: 1,759 "passport
  numbers" were 35-char MRZ lines; v1's ≥6-no-max bar measured OCR debris). Key-book
  impact: kitas 1→89 (×89), passport 313→471, npwp 291→297. Buckets: incomplete 2,304 ·
  name-conflict 1,847 · validate-not-true 1,559 · non-drive 850 · multisid/cluster 710 ·
  id-exists 231 · possible-existing-person 92 · discard 21. Manifest digest `d2cbcb5b…5e04`.
  **Gate round-3 (Codex sol xhigh, 2026-07-19): FINDINGS — 8 BLOCKER + 2 MAJOR + 1 MINOR.**
  Veri e riproducibili: (R3-1) allowlist root dichiarata ma NON nel predicato; (R3-2)
  manifest troppo magro (no pids/qids/blob_hash/fingerprint/branch/thresholds) + perimetro
  non latest-proposal-per-queue; (R3-3) STRICT fail-open su doc SENZA stage validate
  (`has_validate=False` arriva in A); (R3-4) divergenza normalizzazione: routing strippa
  solo `[\s.\-/]`, il modulo strippa TUTTO il non-alnum → `AB#123456` canonicalizza diverso
  tra census e matcher; (R3-5) race writer-umano-non-committato sfugge a recheck+sweep
  immediato → serve re-sweep ritardato + residuo dichiarato; (R3-6) soppressione
  auto-attach ancora solo prosa — serve il wiring in routing.py + test guilt/innocence
  PRIMA del GO; (R3-7) rollback: fingerprint non esaustivo + child-insert FK che attende il
  FOR UPDATE e committa DOPO il soft-delete; (R3-8) `--dsn` fail-open → apply deve
  attestare current_database+località; (R3-9 MAJOR) distinct-blob agreement inerte come
  implementato → dichiarare la barra single-doc o richiedere ≥2 blob; (R3-10 MAJOR)
  clustering calcolato su nomi PRE-gate (contamina: 710 doc over-cut) → cluster su coppie
  (sid,nome) ELIGIBLE con sid diversi. **v3.1 BUILT (stesso giorno): tutti gli 11 chiusi
  IN CODICE** — allowlist nel predicato, perimetro latest-per-queue + manifest ricco
  (pids/qids/blobs/ffps/branch/thresholds/code-SHA), STRICT senza fail-open, proiezioni
  mirror `[\s.\-/]` verbatim, attestazione book locale, barra single-doc dichiarata,
  clustering two-pass su eligible con sid-diversity, **soppressione auto-attach CABLATA in
  routing.py** (`AUTO_ATTACH_SUPPRESSED_PIPELINE_VERSIONS={'v2.3-drive-autocreate'}` al
  chokepoint, 3 test guilt/innocence/edge). **Census v2.1: A-effective 435 contatti
  (passport 208 / kitas 221 / npwp 6)** — la decontaminazione del cluster restituisce +183
  candidati che il gate sporco bruciava; kitas book 1→222. R3-5 dichiarato
  accept-and-detect (re-sweep ritardato + freeze; residuo = stessa esposizione di ogni
  create manuale odierno). **Gate round-4: FINDINGS — 3 residui, il primo GRAVE e vero
  (R4-1/W99): il builder mette `pipeline_version` al TOP-LEVEL del proposal, il chokepoint
  leggeva la forma annidata inesistente → soppressione MAI attiva in produzione, e i test
  costruivano proprio la forma fantasma — Codex l'ha riprodotto sul builder reale.**
  v3.2 (stesso giorno): (R4-1) chokepoint legge il top-level + test END-TO-END
  `test_suppressed_pipeline_version_end_to_end` che attraversa route_stage→builder→
  chokepoint con env armato; (R4-2) manifest con tuple per-doc (pid,qid,status,blob,ffp)
  - `script_sha256`/`validator_sha256` dei byte esatti (un git-SHA di worktree sporco non
    vincola nulla); (R4-3) coppie trigram calcolate sull'INTERO set eligible PRE-esclusione
    (non-transitività: A~esistente, A~B cross-sid, B!~esistente → B ora clusterizza).
    Census v2.2: clustered 171→182, **A-effective INVARIATO 435** (i doc dei nomi
    neo-clusterizzati erano già in quarantena per gate precedenti) — ora certificabile.
    **Gate round-5: 1 solo blocker R5-1 (manifest self-reference)** — costruire l'apply
    cambia `script_sha256`, quindi il digest approvato al round-5 non può mai essere
    presentato all'apply costruito; chiusura prescritta dal gate stesso: build apply →
    rigenera manifest → re-gate il digest nuovo. **APPLY/ROLLBACK COSTRUITI (2026-07-19):**
    `_compute_census` condiviso census/apply (digest ri-derivato dallo STESSO code-path,
    mismatch=exit 3); ledger `intake_identity_ledger` UNIQUE(kind,canonical*value);
    `_apply_one` per-candidato in-TX (advisory strong-id lock del wire enricher →
    rivalidazione under-lock: key 0-owner su clients+companies, nome <0.45 vs vivi,
    evidenza per-doc immutata su pid/status/fields-fingerprint → ledger planned → INSERT
    clients origin='drive-intake' created_by='system:drive-intake-autocreate'
    lead_metadata{auto_created_from_drive,batch_id,sid_kind} → ledger created +
    business_fingerprint full-row incl. deleted_at); `StrongIdLockBusy`=skip per-candidato
    mai batch-abort; post-lotto: key sweep expect_max=1 (freeze exit 4), reroute
    supersede+reset con tag `v2.3-drive-autocreate` (soppressione già cablata+e2e-testata),
    drain-poll 300s, assert 0 auto_routed + 0 audit nuovi → reroute_verified; re-sweep
    ritardato a inizio-lotto-successivo + sweep finale (R3-5); rollback per batch_id =
    lock + FOR UPDATE + fingerprint-equality (drift=guard content_drift, mai delete) + FK
    sweep information_schema + soft-delete + ledger rolled_back. Killswitch
    `INTAKE_DRIVE_AUTOCREATE_ENABLED` process-env default OFF (senza = dry-run plan);
    `--manifest <digest>` obbligatorio; cap 200, default 1 lotto. Verifier indipendente:
    AST ok, 0 mismatch attributi, colonne clients tutte reali (migration 213/223/246/248),
    18/18 test predicato, ruff pulito. **Census v2.3 post-build: OGNI numero identico alla
    v2.2 certificata (435 = 208/221/6), cambia solo il digest via script_sha256** →
    `59b6287c0f83…f791`. **Loop gate profondo rounds 6→7→8 (tutti FINDINGS, tutti chiusi
    stesso giorno):** R6 8 fix (collision detect-fast+race-test, cardinalità esatte,
    committed_at, evidence lock+full-rederive, manifest binda routing+enricher, limiti
    wave-1 enforced, rollback schema-drift, report PII-free) · R7 6 fix (`--verify-batch`
    ritardato per il residuo two-uncommitted-writers — inchiudibile in-process, protocollo
    T+delay e T+1d; probe live name-gates; freshness col tag; reroute TX-atomico + fence
    status/lease; batch-id uuid; redazione fatale exit 5) · R8 7 fix (probe riscritte
    sulla semantica REALE di classify_perimeter — arm conflict id-keyed + arm cluster
    name/trigram; verify non-vacuo con owner ESATTO + screen nomi; rollback CAS su
    `reroute_proposal_ids` con abort totale; freshness causale su pid pre-reset catturati
    sotto lock; ordine lock globale code→proposte; 7 test comportamentali — 12/12 nel
    file apply). Census v2.6: 435 INVARIATO, digest `1a66d24c…ffb2`. **Round-9:
    FINDINGS (5) — tutti chiusi stesso giorno:** R9-1 rollback PHASE-AWARE (CAS con
    fallback su `source_proposal_ids` quando `reroute_proposal_ids` è NULL: pre-reroute
    = nulla da restaurare, mid-reroute = coda già in re-route, unverified-fresh col
    nostro tag = restore, foreign = abort totale — prima un freeze pre-reroute rendeva
    il rollback strutturalmente impossibile) · R9-2 Arm B legge l'id di ogni riga con
    l'ESPRESSIONE census in SQL (`COALESCE(fl->key->>'value', fl->>key)` per ogni key,
    niente re-parse Python: un oggetto npwp senza member 'value' formava SID nel census
    ma spariva dal probe) · R9-3 name-gates ripetuti POST-INSERT in-TX + nel
    `--verify-batch` ritardato (residuo = two-uncommitted-writers, conseguenza limitata:
    dup→AMBIGUOUS mai auto-attach) · R9-4 drain null-safe (`IS DISTINCT FROM`; stage
    NULL restava fuori dal pending count = drenato per errore) · R9-5 6 test
    comportamentali nuovi (gates guilt A/B+innocence+malformed-shape, rollback NULL
    entrambe le direzioni, drain verbatim-extracted, verify document_gate exit 4) —
    **36/36 nel file apply+validity.** Census v2.7: numeri INVARIANTI (7.895/435/1.988),
    digest `e2b50dde39e24697b8a7bb7995eff831bbc3659c972635f781aa0d04073a982d`.
    **Round-10: FINDINGS (6) — tutti chiusi:** R10-1 probe senza filtro status
    (un conflitto auto_routed non sparisce più dal verifier; controesempio LEVA-3
    overlap/min VERIFICATO — subset-name = 1.0; `attached_docs_info` nel verify) ·
    R10-2 tag batch-qualificato `v2.3-drive-autocreate:<uid8>` (VARCHAR(32) forza
    il qualifier corto; suppression exact-or-`:`; rollback accetta solo i tag del
    PROPRIO batch) + ramo mid-reroute legge lo status coda: `dead` → REVIVE ·
    R10-3 CAS preventivo pre-supersede (freeze a stato-estraneo-intatto) · R10-4
    oracolo `_sql_field_proj` fail-closed OVUNQUE (oggetto senza 'value' → NULL,
    mai serializzato: `{"confidence": 0.123…}` non conia più un NPWP) + **npwp
    ESCLUSO dalla creazione** (bucket `B_npwp_person_ambiguous`, 28 doc — persona/
    azienda ambiguo, review è il terminale) · R10-5 manifest binda anche worker/
    auto_attach/writer (7 file) · R10-6 rollback exit 4 se guarded + 7 test nuovi.
    Battery 22/22. Census v2.8: A_effective **430** (−6 npwp, +1 drift live,
    perimetro 7.901), digest
    `5247a6276e9e9443607a02b4de57d9e0de783f0155f6e2fb60e3625844a8927d`.
    **Round-11 (sol xhigh, 2026-07-20): FINDINGS (5) — tutti chiusi stesso giorno:**
    R11-1 il member 'value' è ANCH'ESSO tipato nel CASE (un value oggetto/array veniva
    serializzato da `->>'value'` → nome cliente = JSON letterale) · R11-2 census/apply
    SIMMETRIA: `_live_gate_preflight` esegue al census le STESSE `_live_name_gates`
    dell'apply e demota in `B_live_gate_would_flag` (il cluster census girava solo su
    `pre.a_sids` — i doc npwp parcheggiati erano invisibili al census ma visti dai probe
    live → manifest sovrastimato; ora il digest binda anche lo stato-nomi live: un doc
    confliggente tra census e apply invalida il digest, fail-closed) · R11-3
    ATTESTAZIONE WORKER: `stages_sha256` nel manifest (8 file) + `_worker_attestation()`
    su apply ARMED — byte deploy==manifest per 7 moduli intake, worker avviato DOPO il
    mtime più recente (`ps -o etime=`), env daemon senza STUB né flag auto-attach
    (arming batch-only); ogni errore probe = failure (W84). CONSEGUENZA: wave-1
    meccanicamente bloccata finché il branch Lane B (suppression prefix in routing.py)
    non è merged+pulled in `~/nuzantara-deploy`+worker kickstartato · R11-4 rollback
    batch sconosciuto = exit 2 `unknown_batch` (prima: successo vacuo exit 0) · R11-5
    bound onesto (il residuo è l'attach UMANO pre-verify: rollback rifiuta su fk_refs →
    guarded exit 4; commento riscritto) + `run_verify` PERSISTE
    `verify_conflict:<gate>` come guard_reason sul ledger. +6 test (28+ nel file apply).
    **Census v2.9 ESEGUITO: A_effective 430 → 275 contatti (317 doc) —
    `B_live_gate_would_flag` 168 doc.** Il gate aveva ragione sulla sovrastima: il
    grosso delle demotion è `cluster_appeared` dal book COMPLETO delle proposal
    (es. candidato con doc passport E doc kitas sotto lo stesso nome = sid diversi
    = review, mai auto-create). Digest v2.9
    `bf644ee4b49b643b3da6ca9ebd775f7c11c39662b3a8ab0eb1a1584825764ef4`.
    **Round-12: FINDINGS (4) — tutti chiusi stesso giorno:** R12-1 stringa JSON
    serializzata (`'{"label":"JOHN SMITH"}'` è scalar-typed, passa la proiezione
    SQL tipata — `valid_name` ora rigetta caratteri strutturali `{}[]"\:=<>|`;
    probe live: 0/1.757 client vivi, 18 nomi estratti tutti spazzatura OCR/JSON,
    nessuno sopravvive al nuovo census) · R12-2 provenance del worker
    (`_worker_attestation` ora verifica anche che il PID esegua DAVVERO dal
    deploy root — cmdline token o cwd via `lsof`, non solo hash che matchano
    a un root configurabile — una copia/symlink retargeted con byte corretti
    ma altrove ora fallisce `worker_not_running_from_deploy_root`) · R12-3
    l'attestation è uno snapshot pre-drain, non un fence: `_reroute_lot`
    ri-attesta DOPO il drain+freshness, PRIMA di certificare — un restart del
    worker o una mutazione deploy DURANTE la finestra di drain ora congela il
    lotto invece di certificarlo silenziosamente · R12-4 rollback disarmato su
    righe live = exit 6 (distinto da exit 2 unknown-batch e exit 0
    clean-success — prima "niente da fare" copriva due stati diversi). +6 test,
    55/55 verdi. **Census v2.10: popolazione INVARIATA (275/317) — R12-1 chiude
    un gap teorico a impatto zero sul book vivo, non una regressione.** Digest
    `46ecfd8c9ca8a838e1782b743c9212ac894cadf18989a99617a8e77de05824db`.
    **Round-13: FINDINGS (4) — 2 chiusi, 2 DICHIARATI (non inseguiti):** R13-1
    literal JSON strutturale-free (`valid_name("false")` → `"FALSE"`, 5 lettere
    senza caratteri strutturali — placeholder set esteso a
    `NULL|TRUE|FALSE|UNDEFINED`) · R13-2 il token di provenance accettava
    QUALSIASI argomento path-like (un worker esterno con `--config <root>/x`
    passava) — ristretto al solo token ESEGUIBILE (argv[0], o argv[1] se
    argv[0] è uno shell/interprete noto, come la reale forma launchd di
    questo repo `/bin/bash <root>/…/worker-run.sh`) · **R13-3 DICHIARATO**
    (bypass via mtime retrodatati richiede auto-sabotaggio deliberato
    dell'operatore sul proprio stesso tool — fuori dal threat model reale;
    serve self-attestation in `worker.py`, lane futura, non blocca wave-1)
    · **R13-4 DICHIARATO** (TOCTOU freshness→ledger `reroute_verified`: la
    flag è bookkeeping, non un gate di sicurezza — i gate veri (owner,
    nome, document_gate) sono ri-eseguiti indipendentemente da
    `--verify-batch` a T+delay/T+1d, stesso bound già accettato di R9-3).
    Ledger PENDING-ARMS aggiornato con entrambe le dichiarazioni + criterio
    di riapertura. 56/56 verdi. Census v2.11: popolazione INVARIATA
    (275/317), digest
    `ed4d702f298052fb1690cff518116314364f735c55d780be7f3536207be24c82`.
    **Round-14: FINDINGS (1) — R14-1: la fallback cwd del check R13-2 restava
    un'alternativa INDIPENDENTE** (un eseguibile esterno con cwd impostata sul
    deploy root passava comunque, vanificando R13-2) — **chiuso:** cwd non è
    più un segnale indipendente, serve SOLO a risolvere un token eseguibile
    RELATIVO (raro) in path assoluto prima dello stesso check under-root; un
    eseguibile esterno assoluto ora fallisce SEMPRE `worker_not_running_from*
    deploy_root`indipendentemente dalla cwd. R13-3/R13-4 confermati validi
dal gate stesso in questo round. 58/58 verdi. Census v2.12: popolazione
INVARIATA (275/317), digest`0c773f7af5547cf5c117aca06f985656e60994646b14fad7072723e179c2c4d9`.
**Round-15: VERDICT CLEAN — WAVE-1 GO.** Arco gate 6→15 CHIUSO. Design doc
§v3.4→v3.7 con il meta-pattern completo (proxy-vs-stato-reale, dieci
round, una sola malattia). **Prossimo passo: esecuzione wave-1** (killswitch
`INTAKE_DRIVE_AUTOCREATE_ENABLED`nel process-env del batch +`--manifest 0c773f7a…`+ 1 lotto ≤200 + drain +`--verify-batch` a T+delay
    E T+1d) — sospesa per conferma esplicita Zero: è la PRIMA creazione reale
    di contatti CRM da questa pipeline, dati cliente reali, prima esecuzione
    mai fatta contro il book vivo.

- **2026-07-20 — PR #2787 MERGED (auto-merge riarmato da sessione sibling a CI verde,
  mergeCommit `b30103c32a`) + DEPLOY FATTO:** Fly v3850-v3852 (health 200 verificato,
  tutte le machine started), `~/nuzantara-deploy` pullato a `b30103c32` + worker
  running. I fix round-17 (F24 BLOCKER gate delivery 3-colonne + F25 upload proof)
  NON erano nel merge → follow-up PR dal branch
  `agent/nuzantara/backend-rag/intake-phone-reader-gates-r17` (commit `efd4a13a92`,
  109 test verdi), gate Codex round-17 in corso su quel PR. Class-audit LETTORI:
  8 sibling 2-di-3-colonne dichiarati in PENDING-ARMS (tutti fail-safe direction),
  PR dedicato a valle.

- **2026-07-19 — PERSON-NPWP STRONG-ID LIVE (m248, PR #2775 merged) + BACKLOG REROUTED + WIRE PROVEN:**
  `routing._match_person_strong` now matches `clients.npwp` (exactly 15/16 ASCII digits, dup→AMBIGUOUS,
  cross-table collision with `companies.npwp_company`→AMBIGUOUS/unknown; 5 Codex adversarial rounds →
  CLEAN). Backlog reroute executed (`--reroute-npwp --apply`, `pipeline_version='v2.3-npwp'`, worker
  restarted from `~/nuzantara-deploy` first): **129 full-npwp review_pending docs** superseded+rerouted,
  drained <1min. BEFORE→AFTER: NO_MATCH 54→79 (25 noise→quarantine via LEVA-1), AMBIGUOUS 48→33,
  LINK 20→16, AUTO_ATTACH 5→1. **npwp method fired on 3 proposals: 1 unique match (161274→client 10659) + 2 dup groups (161316: 7042/10353; 161330: 4558/10715) correctly AMBIGUOUS.** The auto-commit
  tier is PROVEN wired to npwp presence: both LEVA gates evaluated 161274 and correctly HELD it —
  phone matches no client, doc subject name overlap 0.00 vs the candidate (trigram 0.000, 23-char
  readable name): affirmative contradiction → human review is the right terminal (data-quality lead:
  either client 10659's npwp is mis-entered or the doc belongs to an uncatalogued person). never-auto
  held: 0 auto commits, audit count unchanged. **Honest sizing: deterministic-drain population book-wide
  = 3 proposals only** (1 held + 2 dup groups); the 611 LINK_CANDIDATE "score 1.0" rows are
  `fuzzy_full_name` trigram-perfect, NOT strong-id (W88 proxy trap — measure by METHOD, never score).
  **npwp backfill fuel: 32 pending single-candidate docs carry a full npwp; 25 point at 16 distinct
  clients LACKING a valid npwp** — each human confirm now compounds the key book via `client_enricher`
  (npwp write fragment-gated 15/16 ASCII since this change; a partial OCR read is dropped, never stored).

- **2026-07-18 late night — LOCAL SNAPSHOT REFRESHED (safe method — NOT the stock script):**
  `nuz_db_refresh.sh` does `dropdb nuzantara_dev` — on the Pro that would DESTROY the
  local-authoritative intake state (247k `intake_queue` rows whose `stage_output` is the ONLY OCR
  copy, 71.8k proposals, audit; prod intake tables verified EMPTY 0/0/0). Safe procedure executed
  instead: safety dump of dev (209M) → full prod dump (368M, readonly role via the MCP proxy
  :15432) → restore into the separate DB **`nuzantara_prod_snapshot`** (complete fresh prod
  mirror, use it for cross-checks; needed `brew install postgis` — prod `clients.geo_point`) →
  content-swap of ONLY `clients` in `nuzantara_dev` (DELETE+COPY under
  `session_replication_role=replica`). Dev schema gained prod's 10 new columns — **`npwp` (291
  alive), `nib`, `tax_id`, visa/kitas expiry** — previously-invisible strong-id substrate;
  POSSIBLE new lever: a re-route could gain strong-id matches IF routing consults npwp (verify
  before claiming). Verified after: dev.clients=1,757 alive / 1,665 with folder / client 3346
  intact; intake untouched (audit=885 unchanged). Known residue: 21 `documents` + 6 `practices`
  rows orphaned by prod hard-deletes (report-only).

- **2026-07-18 night — `google_drive_folder_id` backfill CLOSED + PROD-DEDUP DISCOVERY:** the
  "173/11,744 populated" premise was STALE-SNAPSHOT math. Prod truth (verified twice: Fly API GET +
  readonly MCP SELECT): the CRM book was **mass-deduped on prod — 1,755 alive clients** (local
  snapshot still holds ~11.7k pre-dedup rows, 128/128 probed "alive" locally were dead/absent on
  prod), and **1,664/1,755 (94.8%) already have `google_drive_folder_id`** via the server-side
  ensure-folder flow. Session-as-reviewer backfill (`scripts/intake_drive_folder_id_backfill.py`,
  Tier-A bar: exact-name OR sim≥0.85 + Drive ancestor-walk ground truth + live-screen-BEFORE-
  bijectivity + TOCTOU re-check + never-overwrite): **234 candidates → 1 applied:verified (client 3346)**, 61 already served live, 128 dead on prod, 44 Drive-unresolved (folders renamed/moved
  post-enqueue — correct terminal skips). **The gdrive-backfill lever is exhausted; every local-book
  analysis (incl. the 88.5% ceiling below) needs recompute after `nuz_db_refresh.sh`.** Drive access
  gotcha: the SA alone sees NOTHING (404) — DWD impersonation `zero@balizero.com` is mandatory.

- **2026-07-18 evening — BACKLOG REROUTED through the m227 fix (EXECUTED, measured):**
  `scripts/intake_reprocess_backlog.py --reroute-drive-folder --apply` resumed **24,256** Drive
  0-candidate rows at route-only (stage_output PRESERVED — the blobs are retention-evicted, the saved
  fields are the only copy; the generic `--reprocess` would have WIPED them, locked by test). Worker
  restarted first (launchagent `com.nuzantara.intake-worker` runs from `~/nuzantara-deploy`, had
  pre-merge code in memory). Drained in ~5 min. **Outcome: 1,588 docs (6.5%) gained ≥1 candidate —
  1,285 LINK_CANDIDATE + 300 AMBIGUOUS** (676 LINK + 172 AMBIG live in review_pending; 588+128 in
  quarantine via the LEVA-1 noise filter, consultable). Methods: folder_name 1,665, fuzzy_full_name
  195, strong-id 3 (2 passport + 1 kitas — enricher backfill from prior attaches already compounding).
  **never-auto held: 0 auto_routed.** Side-win: 14,859 noise NO_MATCH moved review_pending→quarantine
  (review feed −~15k). Pipeline tag: `pipeline_version='v2.2-m227-folder'`.

- **2026-07-18 (m227 FOLDER FIX — the structural lever for the 24k drive backlog):** `routing.py::
_match_folder_name` was **root-segment-only** (`source_path.split('/')[0]`) — correct for Dropbox
  (client folder at root) but BLIND to Drive, whose 16 roots are staff/category folders
  (`PEMEGANG KITAS`, `EXTEND VISA`, `NOVI`…) and whose client folder sits at depth 2–3. So the folder
  signal (a NEVER-auto transport hint) structurally never fired on Drive → all 24,277 drive docs land
  0-candidate despite the logic existing (#2 exists≠armed). **Fix (new `_folder_segments`): scan EVERY
  segment, dedup by (table,id), keep FUZZY_APPLY_THRESHOLD=0.70 + ambiguity margin.** Recall
  (prod semantics): **1,231 docs (5.1%) gain a folder candidate, 1,005 unique → LINK_CANDIDATE**, ~95%
  precision (attached ground truth 19/20). 466 intake tests pass + 10 new (`test_intake_routing_folder.py`).
  Dual value: fixes ingress (future docs resolve at enqueue) + backlog (via `intake_reprocess_backlog.py`,
  operator-armed apply). Report: `research/operations/2026-07-18-intake-station1-2-rescue-recall.md`.
  **NOTE:** `client_id_hint` is NOT consumed by fase4 (only written) — the fix is in the matcher, not the hint.
- **Ceiling stays structural:** 88.5% of client-folders (3,591/4,057) name entities absent from the CRM
  (313 passports / 1 kitas / 62 company_names / 173 google_drive_folder_id of 11,748 clients). Folder
  recovers the ~5% catalogued; the rest are uncatalogued prospects (data gap). Root-cause levers:
  backfill `google_drive_folder_id`, extend blob-retention TTL, enter the ~1,215 uncatalogued folders.
- **2026-07-18:** deterministic tier proven (61/61) + **18 documents auto-attached** via `plan_commit`/
  `execute_commit` (tag `committed_by='system:refinery-deterministic'`, `review_pending`→`auto_routed`,
  reversible). Pilot v2 committed (`a4914660b`, adds SEA-LION panel + N-model gate).
- **OPEN — 3 soft-deleted-client proposals** (82041/82021/82034 → client 10236, `deleted_at` set):
  correctly refused by the writer, still `review_pending`. Decision: restore client vs re-route vs human.
- **OPEN — dedup anomaly 62130:** 7 clients share one normalized passport → likely duplicate client
  records; a direct lead into the CRM dedup problem.
- **NOT DONE — entry leak** (~3,084 wa-mirror rows never enqueued, ~80/day) + **1,345 rows frozen
  mid-pipeline since 2026-06-20** — separate upstream levers; the refinery drains, the leak bleeds.

---

## 6. Blood-bought rules (scars)

- **2026-05-17 identity-hallucination:** name-frequency auto-attach mis-attributed 12 → **never
  name-only auto**. Strong-id corroboration or quarantine.
- **W65 generator≠grader:** the model that proposes a match never grades it. The refinery uses a
  separate panel; any "confirmed" verdict is re-checked, not trusted.
- **W87 postgres access-wall:** intake lives on LOCAL `nuzantara_dev`, NOT the Fly-prod MCP. `✔ Connected`
  ≠ auth+query.
- **W96 test-writes-prod:** intake tests must redirect output/DB to fixtures, never touch the real queue.
- **Law 2 (UU PDP):** the refinery's _output_ is an attach decision (doc_id→client_id) INSIDE the system.
  Reports / memories / logs / skills **never** transcribe client PII (names, passport/kitas VALUES,
  phones) in clear — integers, `client_id`, field-name-matched only. Processing may use context; output may not.
- **Reversibility:** dry_run → measured precision → real write in batches, with `intake_commit_audit`
  - `rollback_commit` + a kill-switch (the flags). Never a blind mass write.

---

## 7. Design spec + references

- Full station design (Station 0 dedup/junk → 1 re-extract → 2 candidate-regen → 3 panel → 4 gate →
  5 commit): scratchpad `intake-refinery-design.md`.
- Memory: `discovery_refinery_panel_width_is_second_order_2026_07_18` (findings + sizing + precision).
- Writer/gate code is the ground truth — re-read `writer.py` / `auto_attach.py` in-turn before any mutation
  (anti-hallucination: never build on a remembered signature).
