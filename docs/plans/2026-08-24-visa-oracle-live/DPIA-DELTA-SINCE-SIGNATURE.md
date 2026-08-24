# La DPIA è firmata, e da allora il sistema si è mosso

> Misurato 2026-08-25 su disco, non dedotto. **Correzione di rotta di questa sessione**: avevo
> dichiarato la firma #1 dello switchboard «non ancora scritta». È scritta **e firmata** —
> `docs/audits/2026-08-20-visa-oracle-dpia-v2.md` §8, firmata da Zero di persona il 2026-08-23.
> Stavo per scriverne una seconda. Questo documento è il delta, non un rifacimento.

## Cos'è già chiuso, e va detto prima del resto

Switchboard **#1 (DPIA) è DONE**. La V2 chiude la ruling §A (retention analytics a 12 mesi) e
accetta esplicitamente i rischi residui in §D. Il documento è anche onesto in un modo che merita
di essere notato: dichiara che le righe DPO e Security/Infra **non sono state eseguite di persona**
ma adottate su istruzione (Legge 5), invece di far figurare tre firme dove ce n'è una. Un
documento che dichiara la propria debolezza è più affidabile di uno che la nasconde.

Restano vere le sue due righe **High** invariate: destinazione analytics non identificata, e
registro processor/subprocessor cross-border con celle `OPEN`.

## Il delta: cosa è cambiato DOPO la firma

La valutazione è «as of 2026-08-20/23». Il 2026-08-25 ho fuso in `feature/visa-oracle` una
superficie che la sua tabella dei flussi (V1 §2) non contiene.

|               |                                                                                                                                              |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Cosa          | `POST /api/visa-oracle/consultant-assignment` + tabella `visa_oracle_consultant_requests` (migrazione 281)                                   |
| Dati          | `evaluation_id` (UUID), `client_id` (UUID, **collegato a una persona quando esiste**), `tier`, `origin_screen`, `locale`, timestamp server   |
| Quando scatta | **al momento del consenso** — `requestConsultantAssignment` è chiamata dentro `setGranted` (`ConsentHandoff.tsx:313`, `setGranted` a `:273`) |
| Retention     | **nessuna.** Migrazione 281: zero `expires_at`, zero TTL, zero purge. `retention.py`: zero occorrenze di `consultant`                        |

### Perché non è un dettaglio tecnico

La riga **CRM** della tabella dei flussi V1 §2 dice, verbatim: _«Not implemented/authorized by
WhatsApp consent» · «Future CRM processor only after separate opt-in» · «**Must be assessed and
noticed before activation**»_.

Quello che ho fuso non è un CRM — scrive sul nostro Postgres, non a un processor terzo. Ma è
**una nuova conservazione durevole di dati personali, creata nell'istante del consenso**, che
quella tabella non prevede. E la domanda che la DPIA dovrebbe risolvere, e oggi non risolve, è
esattamente questa: **il consenso che il visitatore dà è per l'handoff WhatsApp — copre anche il
persistere di un record di instradamento?** Non è una domanda retorica: se la risposta è no,
l'attivazione va spostata o il consenso va riformulato.

### La parte che devo dire di me

Tre ore prima di fondere questa migrazione ho scritto `SWITCHBOARD-2-RETENTION.md`, che documenta
una tabella con dati di visitatori e **nessuna purge**, e ne fa una firma per Zero. Poi ho fuso
una **seconda tabella con la stessa identica mancanza**, con i suoi gate superati (Squawk pulito,
numero libero, guardia PII verificata) — perché nessuno di quei gate misura la retention. Il
difetto non è sfuggito a un controllo: **non esisteva un controllo che lo cercasse.** È la
famiglia #2 nella sua forma più pura, e questa volta l'ho prodotta io.

## Cosa NON è cambiato in peggio, per non gonfiare il reperto

- **Nessun campo di testo libero, nessun PII in chiaro.** Sei campi, tutti UUID o enum chiusi,
  `extra="forbid"`, più una guardia indipendente che rifiuta chiavi di forma PII prima ancora di
  Pydantic. Verificato leggendo il validatore (`consultant_assignment.py:127`, legato a `:177`).
- **`client_id` è oggi sempre `null`**: `OracleShell` non passa mai la prop. Il ramo
  visitatore-identificato è spedito ma non esercitato — il che riduce l'esposizione di oggi e
  **aumenta** il valore di decidere adesso, prima che venga cablato.
- **Una raccolta è DIMINUITA**: la lane V1 ha rimosso una domanda dell'intervista senza
  consumatore (`work.employer_country_code`). Minimizzazione reale, nella direzione giusta.

## E la lacuna più vecchia, che nessuna versione della DPIA copre

`visa_oracle_sessions` — la tabella del funnel legacy con `messages` in **testo libero** — non
compare in nessuna versione della DPIA, con nessun nome: cercati `quiz`, `messages`, `sessions`,
`free-text`, `testo libero`, `legacy` su V1 e V2, **zero occorrenze in entrambi**. È la superficie
con la peggiore postura di ritenzione dell'intero prodotto (TTL dichiarato nello schema, job che
lo applica inesistente) ed è quella **pubblica e indicizzata** (`TWO-DOORS.md`). Non è un difetto
introdotto oggi; è un difetto che oggi diventa impossibile da non vedere, perché ora ci sono
**due** tabelle senza purge invece di una.

## La domanda per Zero

Non «la DPIA è valida?» — lo è, per ciò che ha valutato. La domanda è **cosa fare del delta**, e
sono tre gesti di costo diverso:

1. **Addendum acknowledged, nessuna nuova firma.** Si annota che la superficie consultant è
   coperta dalla valutazione esistente perché non introduce categorie nuove (solo identificatori
   pseudonimi). Costo: zero. Rischio: la riga «must be assessed before activation» della V1 resta
   formalmente non onorata.
2. **Addendum firmato** — una pagina che valuta la nuova conservazione, con la sua riga di
   retention, e la si controfirma. Costo: basso. È ciò che raccomando.
3. **DPIA V3.** Sproporzionato oggi: nessuna categoria nuova di dati, nessun processor nuovo.

**Indipendentemente da quale scegli**, una cosa non è una decisione di business e la faccio io: le
due tabelle senza purge vanno entrambe in `retention.py`, che è il meccanismo che già esiste e già
funziona per `visa_decisions`. Non chiedo una firma per quello — chiedo la risposta a #2 di
`SWITCHBOARD-2-RETENTION.md` (per quanto si tengono), perché il **quanto** è tuo e il **come** è mio.
