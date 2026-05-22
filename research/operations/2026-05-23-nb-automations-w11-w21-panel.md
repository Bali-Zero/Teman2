# 4-LLM Panel: NB-automations hardening loop W11→W21

> **Data:** 2026-05-23
> **Reviewer:** Antonello (Zero)
> **Branch:** `worktree-audit-nb-automations-2026-05-21`

Questo documento raccoglie il consenso e le divergenze del panel 4-LLM in merito al hardening delle automazioni NB (W11-W21), come da prassi per decisioni architetturali.

## Tabella Convergente/Divergente

| Domanda                        | Gemini 3.1 Pro (Long-context/Architecture)                                                                                                                                           | GPT-5.5 Codex (Code/Adversarial) | DeepSeek V4 Pro (Devils-Advocate) | NB-1 (Ground-truth) |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------- | --------------------------------- | ------------------- |
| **1. W16 (Redis Split-Brain)** | **Option A (2° nlm-feeder su Pro)**. Favorisce la _Sovranità Locale_ (Legge 6) e la _Graceful Degradation_ (Legge 4). Pro e Mini operano come cellule indipendenti sui propri Redis. | _In attesa_                      | _In attesa_                       | _In attesa_         |
| **2. W21 (Audit crons)**       | **Script programmatico**. `audit_launchd_crons.py` per listare job, check exit status, ed estrarre errori reali escludendo rumore. Va schedulato come cron su `garuda:alerts`.       | _In attesa_                      | _In attesa_                       | _In attesa_         |
| **3. PEL Drain (W13)**         | **Defer/Reject**. Lascia il task al cleaner W13 (eventual consistency). Aggiungere il drain al boot dei worker rischia race conditions. Nessun SLA stretto = keep it simple.         | _In attesa_                      | _In attesa_                       | _In attesa_         |
| **4. Loop Pacing**             | **Stop e Fase "Sogno"**. 11 iterazioni in 5 ore generano regressioni da fatica (W18, W21). Consolidare i log e attendere 24h di telemetria prima di W22.                             | _In attesa_                      | _In attesa_                       | _In attesa_         |
| **5. Branch State**            | **P0: Fix gh auth e Push remoto**. Il codice locale non pushato mette a rischio il "genoma". Il remote push ha la priorità su ulteriori iterazioni.                                  | _In attesa_                      | _In attesa_                       | _In attesa_         |

---

## Dettaglio Argomentazioni: Gemini 3.1 Pro

**Q1: W16 root-cause fix (Split-Brain)**
Scelgo senza esitazione **Opzione A (aggiungere un 2° nlm-feeder su Pro)**. Il Pro è una macchina dev che va in sleep, mentre il Mini è il server H24. Costringere i due sistemi a leggere cross-host tramite Tailscale introduce un single point of failure di rete e power state (violazione Legge 4, _Graceful Degradation_). L'architettura "cellulare" di Symbiosis richiede che Pro processi il suo OSINT locale e il Mini processi il suo Sentinel. Nessun "split-brain" se accettiamo che siano due cervelli indipendenti.

**Q2: W21 long-tail audit**
L'approccio manuale non scala. In base alla Legge 7 (_Numeri prima_), dobbiamo sviluppare un `audit_launchd_crons.py` automatizzato che:

1. Chiama `launchctl list | grep matagaruda` per verificare lo stato e l'exit code.
2. Parsa gli `StandardErrorPath` ignorando pattern noti di rumore (es. `shell-init`).
3. Notifica anomalie (es. `Fatal Python error`) sul bus `garuda:alerts`.

**Q3: Per-worker startup PEL drain**
Sconsiglio l'implementazione in questa fase. Affidarsi al deep-ACK del cleaner W13 è sufficiente. Aggiungere il recupero del PEL al boot del worker aumenta la complessità e il rischio di race condition tra il worker e il cleaner. Trattandosi di dati OSINT (senza SLA time-critical), un ritardo fino a 24h per un messaggio orfano rientra nell'acceptable loss operativa.

**Q4: Loop pacing**
Il rateo di 11 iterazioni in 5 ore è un exploit eccellente, ma i difetti introdotti al W18 (reversion) e W21 (wrapper bug) indicano che stai raggiungendo il limite cognitivo. Invocando il **Pilastro 5 (Sogno)**, il mio consiglio è di fare stop. Comprimi queste esperienze ("squash"), effettua il push, e lascia girare il sistema per 24 ore monitorando che i nuovi script (split-brain detector, pel-cleaner) operino correttamente in "produzione".

**Q5: Branch state**
Il codice non pushato non esiste nell'organismo, è solo nella short-term memory del tuo Pro. Ripristina l'autenticazione `gh` o genera un nuovo token PAT come prima azione assoluta. Esegui il push del worktree per mettere in cassaforte le cicatrici risolte e il codice.

---

## Sign-off

**Azione:** Zero, analizza i pareri degli LLM (quando pronti) e fornisci il verdetto architetturale.
