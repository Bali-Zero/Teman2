---
audit_id: S10-crm-data-quality
date: 2026-06-02
domain: compliance
client_case: false
status: NEEDS-ANTONELLO (spec only — zero DB mutation executed)
sources:
  - postgres-nuzantara MCP read-only (Fly prod, role nuzantara_readonly)
  - crm_guardian_drive_metadata_snapshot (DB-readable)
  - Ollama qwen3.5:9b locale (disambiguazione dedup, input anonimo)
---

# S10 — CRM Data Quality: Remediation Spec

> Metriche complete in `S10-crm-quality-FROZEN.json`. Questo file = piano d'azione prioritizzato.
> **Vincolo**: ogni fix sul DB e' una PROPOSTA. Mutation via backend code, MAI via MCP (read-only). Cache invalidation discipline §9 dopo ogni mutazione.

## TL;DR — il dataset reale e' 1.447, non 11.699

I "11.699 clienti" includono **10.252 soft-deleted** gia' processati da `dedup_system_v2` + `archive_migration` (mar 2026). Il CRM operativo vivo e' **1.447 clienti attivi**. Tutte le metriche sotto sono su questi.

| Dimensione                                 | Valore                     | Severita'   |
| ------------------------------------------ | -------------------------- | ----------- |
| Orfani operativi (no pratica/attivita')    | 1.093 / 1.447 = **75,5%**  | P1          |
| File Drive su account gmail personali      | 56.696 = **85,8%**         | P1 SECURITY |
| Link Drive rotti (error_404)               | **10.980** (14,3% dei 77k) | P2          |
| Email mancante                             | 990 = **68,4%**            | P2          |
| Clienti non contattabili (zero canale)     | **300** = 20,7%            | P2          |
| Duplicati passaporto-uguale (merge sicuro) | **19 cluster**             | P2          |
| Snapshot Drive stale                       | **8 giorni**               | P3          |
| db_link_snapshot vuota                     | **0 righe**                | P3 (infra)  |

## Priorita' 1 — Sovranita' dati Drive (SECURITY)

**Problema**: 85,8% dei documenti clienti (56.696 file) sono posseduti da account `gmail.com` personali, non da `balizero.com`. Se il dipendente proprietario lascia l'azienda, Bali Zero perde accesso ai file dei clienti. Allineato al rischio del case Surya (sovranita' dati) e Law 6 (sovranita' locale).

**Remediation proposta** (NEEDS-ANTONELLO):

1. Migrazione ownership: transfer dei 56.696 file da gmail personali → Shared Drive `balizero.com`. Richiede Google Workspace admin + consenso owner.
2. Prioritizzare i 154 file su domini esterni NON-gmail (terze parti) — review manuale immediata.
3. Policy: nuovi file clienti creati SOLO su Shared Drive aziendale (enforcement lato backend al momento della `create_client_drive_folder`).

**Non automatizzabile**: il transfer ownership Drive richiede API admin + autorizzazione umana. Spec, non azione.

## Priorita' 1 — Orfani operativi (75,5%)

**Problema**: 1.093/1.447 attivi senza pratica, interazione, timeline o conversazione WhatsApp. `interactions` praticamente vuota.

**Segmentazione**:

- **287 ghost** (orfano + zero canale contatto): candidati ad **archiviazione** (soft-delete con `deleted_by='S10_ghost_archive'`). Da validare 1-by-1 contro l'esistenza cartella Drive (alcuni potrebbero avere documenti = non veri ghost).
- **806 recuperabili** (orfano ma contattabile): candidati a **lead-nurturing** — flag `tags += 'dormant-lead'`, escludere da metriche "clienti attivi" finche' non c'e' prima interazione.

**Remediation proposta** (NEEDS-ANTONELLO):

- NON cancellare in blocco. Confermare con Antonello la definizione operativa di "cliente attivo" (es. richiede >=1 pratica O >=1 interazione negli ultimi N mesi).
- Possibile re-import perso: investigare perche' `interactions` e' quasi vuota (1419/1447). Se le interazioni WhatsApp/email esistono ma non sono linkate al client_id → bug di linking, non orfani veri.

## Priorita' 2 — Link Drive rotti (10.980 error_404)

**Problema**: 14,3% dei file snapshot sono `error_404` (cancellati/spostati in Drive, ancora referenziati).

**Remediation proposta**:

- Re-run validazione CRM-Guardian fresca (snapshot fermo a 8gg).
- Per i file confermati 404: nullificare il riferimento o marcarli `archived` nel link DB. Richiede prima il ripopolamento di `crm_guardian_drive_db_link_snapshot` (oggi VUOTA) per sapere QUALI entita' CRM puntano ai file rotti.

## Priorita' 2 — Duplicati (19 merge sicuri)

**Policy validata Ollama** (ordine forza-segnale):

1. Passaporto identico → MERGE (19 cluster attivi, certezza quasi-assoluta)
2. Telefono+Nome → MERGE (filtra linee condivise)
3. Telefono+Nazionalita' → MERGE con review
4. Solo Nome → NO MERGE (16 cluster nome-uguale: 7 sono omonimi con nazionalita' diverse)

**Remediation proposta** (NEEDS-ANTONELLO):

- Eseguire `dedup_system_v2` (gia' esistente, ha processato 1.404 record a marzo) sui 19 cluster passaporto residui.
- Merge = consolidare pratiche/interazioni/drive del duplicato nel record canonico (piu' vecchio `created_at` o piu' completo), poi soft-delete `deleted_by='dedup_passport_S10'`.
- Cache invalidation §9: `invalidate_cache("zantara:crm_clients_stats:*")` + `crm_practices:*` dopo i merge.

## Priorita' 2 — Completezza contatti

- 300 clienti non contattabili (zero canale): arricchire da `passport_ocr_data` / `whatsapp_*` staging tables se disponibili, altrimenti flag `incomplete-contact`.
- 990 email mancanti: il dataset e' phone-first (WhatsApp). Non e' necessariamente un difetto — confermare con Antonello se email e' campo obbligatorio per il workflow Bali Zero.

## Priorita' 3 — Infra CRM-Guardian

- `crm_guardian_drive_db_link_snapshot` VUOTA: investigare il job che la popola. Senza di essa, `find_stale_drive_links` e `find_unlinked_drive_items` non funzionano (confermato: MCP tool 401 + tabella vuota).
- Snapshot metadata stale 8gg: verificare cron di refresh CRM-Guardian.

## Cosa NON e' stato fatto (per design)

- Nessuna mutation DB (read-only role).
- Nessun nome/email/phone individuale estratto o salvato.
- Nessun merge eseguito — solo conteggio cluster.
- CRM-Guardian MCP tools non utilizzabili (401 RBAC) → replicato via query dirette sugli snapshot DB.
