# Switchboard #2 — ritenzione dei dati del wizard

> Firma richiesta a Zero (mandato §5). Misurato 2026-08-25 su disco, non dedotto.
> **Domanda per Zero in fondo.** Il resto è terreno, per farla decidere su fatti.

## Il fatto in una riga

La tabella che conserva **il testo libero digitato dai visitatori** dichiara nel proprio schema un
TTL di 90 giorni «ripulito da un job periodico». **Quel job non esiste.** Le righe si accumulano
per sempre, e chi legge lo schema crede che la ritenzione sia gestita.

## Cosa conserva, esattamente

`visa_oracle_sessions` (`migration_080a_visa_oracle_sessions.py:26-38`):

| colonna             | natura                                                                                                                |
| ------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `messages`          | **JSONB — testo libero del visitatore.** Può contenere qualsiasi cosa: nomi, numeri di passaporto, dettagli familiari |
| `quiz_answers`      | JSONB — nazionalità, scopo, durata                                                                                    |
| `recommended_visas` | JSONB                                                                                                                 |
| `language_detected` | VARCHAR(10)                                                                                                           |
| `ip_hash`           | VARCHAR(64) — hashato, corretto                                                                                       |
| `session_id`        | VARCHAR(64)                                                                                                           |
| `expires_at`        | `DEFAULT (NOW() + INTERVAL '90 days')`                                                                                |

Il commento della migrazione, verbatim (`:15`):

> `- expires_at: 90-day TTL, cleaned up by periodic job`

## Perché so che il job non esiste

Cercato il cancellatore su **tutte e tre le vie**, perché un'affermazione di assenza vale solo se
ha guardato anche quella indiretta:

| via                                                  | esito                                                          |
| ---------------------------------------------------- | -------------------------------------------------------------- |
| repo (`apps/`, `scripts/`, `infra/`)                 | 3 hit, **tutti** il `DROP TABLE` del rollback della migrazione |
| HOME-fork (`~/scripts`, `~/.openclaw`) — famiglia #1 | 0                                                              |
| launchd (`~/Library/LaunchAgents/*.plist`)           | 0                                                              |
| `pg_cron` / job lato DB                              | 0 (l'unico hit è un commento in un file WR2 non correlato)     |

C'è la **colonna**, c'è pure l'**indice** su di essa (`idx_visa_oracle_sessions_expires_at`,
costruito apposta per una purge). Manca la purge. È la forma esatta della famiglia #2: tutto
sembra armato tranne la cosa che agisce.

## Il contrasto che rende il difetto netto

Lo stesso motore ha una ritenzione **fatta bene** — sulla tabella meno sensibile.

`retention.py`, dal suo stesso docstring: _«No retention duration lives in application code.
Zero-approved policy rows…»_ — il TTL è una riga di policy, non una costante; ci sono
`purge_expired_decisions`, `purge_expired_idempotency`, e funzioni di **evidenza**
(`visa_decision_retention_evidence()`).

| tabella                     | purge                          | policy row | evidenza |
| --------------------------- | ------------------------------ | ---------- | -------- |
| `visa_decisions`            | ✅                             | ✅         | ✅       |
| `visa_evaluate_idempotency` | ✅                             | ✅         | ✅       |
| **`visa_oracle_sessions`**  | ❌                             | ❌         | ❌       |
| `visa_rule_packs`           | n/a (non sono dati di persona) |            |          |

Quella senza nulla è quella che tiene il testo libero.

## E converge con la questione delle DUE PORTE

`visa_oracle_sessions` è scritta **soltanto** da `visa_oracle.py`, il router del funnel LEGACY
(righe 646, 671, 693, 762). Il motore v2 (`visa_oracle_evaluate.py`) non la tocca: zero
riferimenti.

Quindi è la **stessa porta** di `TWO-DOORS.md`: quella pubblica e indicizzata, che gira su un
percorso di codice non verificato, è anche quella che accumula messaggi in chiaro senza scadenza.
Le due questioni hanno la stessa cura a monte — decidere cosa ne è di quel funnel — e questo è un
argomento in più per non lasciarlo dov'è.

## Cosa NON ho misurato, e lo dico perché non passi per coperto

**Quante righe ci siano davvero in produzione, e da quando.** In questa sessione è esposto solo il
Postgres **locale**; quello di Fly in sola lettura non è raggiungibile da qui. Un conteggio locale
presentato come prova sulla produzione sarebbe un proxy che non porta il dato che discrimina — lo
stesso errore che questo mandato ha già censito altrove. Il reperto regge su codice e schema, che
sono verificabili da chiunque riesegua i comandi qui sopra; il numero vivo va preso con la via
credenziale dell'operatore.

## La domanda per Zero

Non è «quanto teniamo i dati»: è **due domande**, e la seconda è quella che costa.

1. **Per quanto teniamo le sessioni del wizard?** I 90 giorni dichiarati vanno bene, o un funnel
   anonimo pre-account vuole meno (30? 7?). Nota che è una tabella diversa dalle _conversazioni_,
   che per decisione del 2026-08-08 stanno **5 anni e non si cancellano a orologio**: qui non
   c'è un cliente, c'è un visitatore anonimo che non ha ancora comprato nulla.

2. **Il funnel legacy deve continuare a raccogliere `messages` in testo libero?** Il motore v2 non
   ne ha bisogno — non scrive affatto in quella tabella. Se il vecchio funnel viene ritirato o
   messo noindex (switchboard TWO-DOORS), la raccolta si ferma da sola e la domanda 1 si riduce a
   smaltire l'arretrato. Se invece resta vivo, serve la purge **e** serve decidere se quel campo
   debba esistere: il modo più sicuro di conservare testo libero è non raccoglierlo.

**Raccomandazione**: armare la purge sulla policy-row esistente (riusa `retention.py`, non
inventare un secondo meccanismo) è lavoro nostro e piccolo. Ma non lo faccio prima della risposta a
2, perché costruire una purge su un campo che potrebbe non dover esistere significa consolidarne
la raccolta.
