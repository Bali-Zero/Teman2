# SHADOW non è un audit — misurato 2026-08-25

> Reperto della lane V2, esteso e verificato indipendentemente dall'orchestratore.
> Tocca una **premessa del mandato**, non un difetto di codice: va letto prima di
> firmare la casella #3 dello switchboard (§5).

## Il fatto, in una riga

Due richiedenti che differiscono per **nazionalità, scopo e durata** producono dal
motore in SHADOW un verdetto **byte-identico**.

```
run 1  USA / LONG_TOURISM / 12 mesi  ->  HUMAN_REVIEW_REQUIRED, 0 candidati,
       ['BRIDGING_FROM_VISIT_ITK_PROHIBITED', 'BRIDGING_ONSHORE_ONLY',
        'BRIDGING_TO_BRIDGING_PROHIBITED', 'BRIDGING_ADVERSE_HISTORY']
run 2  GBR / STUDENT / 6 mesi        ->  identico, stesso ordine
```

Non è un campione: è una conseguenza strutturale, e si dimostra contando.

## Perché, per costruzione

`shadow.py::build_shadow_facts` adatta una submission del **vecchio funnel a 4
domande** verso `ApplicantFacts`. Il suo stesso docstring lo dichiara:

> «the 3 KNOWN-able ones (`person.nationalities`/`intent.purposes`/
> `intent.stay_days`) … **The remaining 41 stay `UNKNOWN(NOT_ASKED)`**»

Contro il pack firmato `rulepack-prod-013` (111 regole, 45 fact path importati
dall'enum — non da regex):

|                                                     | n      |
| --------------------------------------------------- | ------ |
| fact path totali (`APPLICANT_FACT_PATHS`)           | **45** |
| fatti che SHADOW può rendere KNOWN                  | **3**  |
| regole valutabili interamente sotto shadow          | **23** |
| regole che toccano un fatto che shadow non pone MAI | **88** |
| di queste, `on_unknown=HUMAN_REVIEW`                | **4**  |

Le 4 sono tutte bridging, e scattano **incondizionatamente a ogni valutazione**:

```
hf.bridging.offshore            HARD_FILTER   immigration.currently_in_indonesia
hf.bridging.from-visit-itk      HARD_FILTER   immigration.current_status_code
hf.bridging.to-bridging         HARD_FILTER   immigration.current_status_code
review.bridging.adverse-history HUMAN_REVIEW  immigration.currently_in_indonesia,
                                              immigration.violation_history
```

`HUMAN_REVIEW_REQUIRED` precede `SUPPORTED_CANDIDATES` nel contratto a cinque
esiti. Quindi ogni riga SHADOW della superficie MATCH è, e sarà, quel verdetto.

## Il punto che è facile sbagliare: **il motore ha ragione**

Non è un bug del motore, e chiamarlo così porterebbe alla cura sbagliata. A chi
conosce 3 fatti su 45, «non posso decidere, serve una persona» è la risposta
**corretta** — è esattamente la disciplina T3 che il mandato impone.

Il difetto non è nella risposta. È nell'**aspettativa** che quella risposta
costituisca un audit. Cicatrice #2 applicata all'apparato di prova invece che a un
cron: la sonda gira, esce verde, e non può diventare rossa per nessuna ragione
legata alla cosa che dovrebbe misurare.

## Chi ci si appoggia — la parte che costa

`shadow_evidence.py::collect_shadow_evidence` è il raccoglitore di prove G-a/G-c di
**produzione**: legge queste righe, ne conta volume, ampiezza e grounding, ed è la
base su cui si deciderebbe di armare ENFORCE. Legge una tabella in cui ogni riga
dice la stessa cosa.

E il taglio più profondo: **`visa_decisions` non registra da quanti fatti è nata una
decisione.** Nessuna colonna distingue una valutazione su 3 fatti da una su 45. Non
si tratta di leggere male le righe — l'informazione che discrimina non c'è. È
famiglia #9: uno stato letto attraverso un proxy che non porta il dato decisivo.

**Una cosa a favore del disegno esistente, e va detta:** il repo _sa già_ che una
proiezione verde non basta — esiste
`test_shadow_evidence.py::test_green_shadow_projection_still_cannot_arm_enforce`.
La guardia c'è al momento di ARMARE. Manca al momento di MISURARE, ed è lì che
qualcuno leggerà «shadow è verde» e lo riporterà a Zero come progresso.

## Conseguenza sul mandato — è questo che chiede una decisione

§5, firma #3, presuppone una «gold-persona suite / rapporto di zero-divergenza
motore↔consulente». Sulla superficie MATCH quel rapporto **non può significare ciò
che la firma assume**: la divergenza sarebbe misurata contro un motore che risponde
la stessa cosa a chiunque. Un rapporto di zero divergenze, lì, è verde per lo stesso
motivo per cui è privo di informazione.

## Tre cure, costate

1. **Non far girare SHADOW sulla superficie MATCH.** È la superficie a 4 domande;
   non ha i fatti per informare nulla. Spostare l'audit sulla superficie ORACLE, che
   le domande le fa davvero. _Costo: un flag. Non perde niente, perché oggi non
   guadagna niente._
2. **Rendere la sonda capace di diventare rossa**: registrare la copertura dei fatti
   sulla riga, e far rifiutare a `collect_shadow_evidence` le righe sotto soglia —
   «una decisione presa su 3 fatti su 45 non è una prova». _Costo: una colonna +
   un gate. È la cura strutturale._
3. **Lasciare tutto e annotare il limite.** _Costo zero oggi, e il prezzo è che la
   prossima sessione legge «shadow verde» e ci costruisce sopra._ Sconsigliata: è
   precisamente il modo in cui questa classe di difetto sopravvive.

**Raccomandazione**: 1 subito (toglie l'illusione oggi), 2 come mandato a sé.
La 2 senza la 1 lascia in piedi per settimane una tabella che sembra evidenza.

## Provenienza

Trovato da V2 (`FUNNEL-DIVERGENCE.md`, 12/12 collasso). Verificato in modo
indipendente dall'orchestratore: la funzione riletta su disco, le 4 regole estratte
dal pack firmato, il conteggio dei fact path **importando l'enum** e non con una
regex — la prima sonda a regex aveva risposto `0`, che è il segnale di strumento
rotto, non di mondo vuoto. Il pack è stato verificato e compilato per davvero
(`verify_rule_pack` → VERIFY OK, kid `prod-2026-07-1`); nessuna firma è stata finta.
