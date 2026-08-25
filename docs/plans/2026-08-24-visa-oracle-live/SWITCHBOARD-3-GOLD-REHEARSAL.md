# Switchboard #3 — la prova a zero divergenze non è ottenibile così com'è strumentata

> Misurato 2026-08-25 su `feature/visa-oracle` allineato a main, con
> `gold_replay_driver --offline`. Pack usato: **seq-13 firmato**
> (`payload_sha256 b9edb809…`, il più alto FIRMATO su disco — seq-14 e seq-15 sono
> candidati non firmati e il driver correttamente li ignora).

## Il numero

```
personas_total            20
personas_match             4
personas_with_divergence  16
explained_divergences      0
unexplained_divergences   16
overall_pass           False   (gate G-b)
```

Lo switchboard #3 chiede _«zero-divergence report engine↔consultants — acknowledge,
sign»_. Siamo a **16 su 20**. Non è una rifinitura: è la voce che non si può firmare.

## Perché il numero da solo mentirebbe

Dodici delle sedici sono il motore **più conservativo** dell'atteso (concede meno, o
chiede una mano). Quattro vanno nella direzione opposta — l'unica che fa danno a un
cliente:

| #   | atteso                                                         | ottenuto                         |
| --- | -------------------------------------------------------------- | -------------------------------- |
| 8   | `NEEDS_INPUT` (matrimonio non verificato)                      | `SUPPORTED_CANDIDATES [C1,E31D]` |
| 9   | `NO_SUPPORTED_PATH` `DIRECT_ONSHORE_CONVERSION_UNSUPPORTED`    | `SUPPORTED_CANDIDATES [D12]`     |
| 10  | `HUMAN_REVIEW_REQUIRED`                                        | `SUPPORTED_CANDIDATES [D12]`     |
| 16  | `NO_SUPPORTED_PATH` `INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM` | `SUPPORTED_CANDIDATES [D12]`     |

Letta ingenuamente, la riga #16 dice «il motore approva un investitore con capitale
sotto il minimo». **Non affermarlo**: il nome del codice lo smentisce da solo.

## La causa strutturale, ed è la cosa da portare a Zero

`INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM` contiene la parola **FIXTURE** nel proprio
nome. Quell'attesa non descrive la policy indonesiana: descrive la policy della
**fixture sintetica** (`_gold_fixtures.py`, il cui docstring dichiara sé stesso
«synthetic engine-test policy, not production Indonesian legal assertions»). Stessa
storia per `DIRECT_ONSHORE_CONVERSION_UNSUPPORTED`, che la fixture nomina
esplicitamente come la ragione cablata per le personas 9 e 16.

Cioè: **le 20 attese sono state scritte contro il pack-FIXTURE, e il driver le
replica contro il pack FIRMATO.** Sono due policy diverse per costruzione — è
esattamente la doppia-corpus già trovata sulla persona #15 (la fixture dichiara
`E23 covered_purposes = [EMPLOYMENT, TOURISM]`, il pack firmato solo `[EMPLOYMENT]`),
generalizzata a tutto il corpus.

Ne segue che **un report a zero divergenze non è raggiungibile con questa
strumentazione**, per nessuna quantità di lavoro sul motore: si può azzerare solo
facendo coincidere due policy che sono deliberatamente diverse. Inseguire lo zero qui
significherebbe o piegare il pack firmato alla fixture (regolatoriamente falso), o
riscrivere le attese finché tornano (il peccato che il corpus oro esiste per
impedire).

## Le tre strade, e quale consiglio

1. **Ri-ancorare il corpus al pack firmato** — riscrivere le 20 attese contro seq-13,
   una per una, con la ragione normativa di ciascuna. È l'unico modo per cui «zero
   divergenze» torna a significare qualcosa. Costo alto, e va fatto da chi può citare
   la norma, non da chi guarda l'output (altrimenti si sta certificando il motore con
   sé stesso).
2. **Cambiare cosa firma #3**: non «zero divergenze» ma «**zero divergenze
   PERMISSIVE**» — le quattro sopra a zero, le conservative elencate e accettate per
   iscritto. Difendibile: la direzione che danneggia un cliente è una sola.
3. **Tenere due gate separati**: fixture↔motore (già verde, è la suite unitaria) e
   firmato↔norma (nuovo, ed è quello che #3 vorrebbe davvero).

**Raccomando (2) come firma di oggi e (1) come lavoro vero**, perché (2) è onesto su
ciò che è stato misurato e non finge che le conservative siano sparite, mentre (1) è
il solo che rende il numero pieno significativo.

## Limite dichiarato

Le quattro righe permissive **non sono state singolarmente ri-derivate contro la
norma** in questo passaggio: so che le loro attese sono fixture-specifiche (dai nomi
dei codici e dal docstring della fixture), **non** so ancora se il pack firmato abbia
per esse la regola giusta. Prima di firmare qualunque versione di #3, quelle quattro
vanno lette a mano contro il Kepmen/Permenkumham — sono l'unico posto dove un errore
del pack firmato produrrebbe un «sì» sbagliato a un cliente vero.
