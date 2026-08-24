# Switchboard #5 — prezzi e termini per tier

> Firma richiesta a Zero (mandato §5). Misurato 2026-08-25 sul repo vivo, non dedotto.
> **Nessun prezzo è trascritto qui, per scelta**: la regola d'oro #11 dice che i prezzi vivono in
> `PricingTool` e in nessun altro posto. Un listino dentro un documento nasce già vecchio e diventa
> una seconda verità. Quello che firmi sono **la copertura e i termini**, non delle cifre.

## Il fatto che decide la firma, prima di tutti gli altri

**Lo schermo del verdetto contraddice il tuo ruling su T2.** Il mandato dice: _«T2 —
self-purchase + consulente **sempre incluso, dentro il prezzo, mai un ripiego**»_.

Quello che il visitatore legge oggi, su ogni prodotto, è una riga sola e uguale per tutti
(`engine-adapter.ts:62-67`, applicata a `:719` sul percorso motore reale):

> **«Choose whether to contact a Bali Zero advisor»** · «Pilih apakah akan menghubungi konsultan
> Bali Zero»

«Scegli se» è esattamente l'opposto di «incluso, mai un ripiego» — e vale per **19 prodotti T2**,
cioè i più significativi del catalogo. Non è una sfumatura di copy: a un cliente che compra un
E31 o un E28A stiamo dicendo che il consulente è facoltativo, mentre la tua regola dice che è
parte del servizio che ha già pagato.

Come ci si è arrivati, senza colpe da distribuire: `NEXT_STEPS` è un array piatto di 3 voci
applicato a ogni esito, e **`tier` non compare nemmeno una volta** in `engine-adapter.ts` — il
contratto di wire non porta il tier, quindi la schermata non potrebbe differenziare neanche
volendo. Da oggi il client **sa** il tier (`product-tier-map.ts`, lane V2), ma quella conoscenza
non arriva alla copy.

**Non firmare dei termini T2 mentre il prodotto dice il contrario.** O si cambia la riga, o si
cambia la regola: sono entrambe decisioni tue, ma non possono restare entrambe in piedi.

## La copertura, che invece è sana

|                                                       |                                                            |
| ----------------------------------------------------- | ---------------------------------------------------------- |
| Prodotti nel pack firmato                             | **38**                                                     |
| Con `pricing_key`                                     | **26**                                                     |
| Senza (→ `CONTACT_REQUIRED`, mai un prezzo inventato) | **12** — E28B/C/D/F · E33A/B/C · E23U/E23V · E30/E30E/E30F |
| Chiavi che **non risolvono** in PricingTool           | **0**                                                      |

La giuntura è la **coppia** `(item_key, category)`, non la sola chiave (`pricing_adapter.py:138-139`).
Tutte e 26 risolvono oggi, misurate istanziando il servizio vero e ripercorrendo il codice
dell'adapter. **Ma è una fotografia, non una garanzia**: il prezzo sta in un file JSON in memoria e
il pack sta altrove; nessun gate CI è stato trovato che rifaccia questa verifica quando uno dei due
cambia. Oggi 0 dangling; domani nessuno se ne accorgerebbe.

I 12 senza chiave si comportano correttamente — instradano a un consulente invece di mentire. Tre
di essi (E30, E30E, E30F) sono però **raccomandabili e senza prezzo**: il motore li propone come
candidati validi. È la stessa cosa già annotata in `TIER-MAP.md`.

## La deriva inversa, che nessuno stava guardando

Le quattro categorie visto di PricingTool contengono **62 righe**; i 26 `pricing_key` ne puntano
**19**. **43 righe non sono raggiungibili da nessun prodotto del pack** — e fra queste
**l'intera categoria `kitap_permits` (3 su 3)**: prezzata, pulita, e invisibile all'Oracolo.

Le non-puntate hanno una forma riconoscibile: varianti «(Altus/Onshore)», «(Extend)» e i tagli
pluriennali (2 e 5 anni). Il pack punta quasi solo alle basi «(Offshore)». Detto senza gonfiarlo:
**è una forma, non un conteggio di bug** — alcune di quelle righe possono essere legittimamente
fuori catalogo per un primo rilascio. Ma «rinnovo» ed «estensione» sono il pane di questa agenzia,
e oggi l'Oracolo non sa venderli.

## Il difetto di freschezza, che è il più insidioso

Il file dei prezzi dichiara la propria data di aggiornamento: `metadata.last_updated: "2026-05-06"`.
La sua storia reale dice altro — **quattro modifiche di prezzo dopo quella data**: 2026-08-12,
2026-08-19 (ricalibrazione E33 su tuo ruling), 2026-08-20 (E30A/E30B su regola PNBP+3jt),
2026-08-23 (E33E). Il campo che dovrebbe dire «quanto è fresco questo prezzo» è indietro di tre
mesi e mezzo.

E c'è il pezzo che lo rende strutturale: **i test fissano la data stantia come valore atteso**
(`test_pricing_adapter.py:44`, e altri) — quindi non solo nessuno controlla che
`last_updated` segua le modifiche, ma la suite **codifica** che resti ferma. Un campo di
provenienza che nessuno aggiorna e che i test difendono non è una garanzia: è un'etichetta.

Un prezzo senza provenienza dimostrabile non si può approvare responsabilmente — e questa è
l'unica ragione per cui non ti chiedo di firmare oggi anche una lista di prodotti-per-tier a
prezzo: prima il campo deve dire il vero.

## Cosa NON concludere da questo documento

- **Non** «la pipeline prezzi è sana»: la parte cablata lo è oggi, e non c'è nulla che la tenga sana domani.
- **Non** «T2 non è definito»: T2 è definito **strutturalmente** (mappa dei tier). Mancano i **termini
  al cliente**, che è un'altra cosa.
- **Non** «c'è un rischio valuta»: non esiste. `IDR` è un `Literal` sul modello backend e un check
  sul validatore frontend — nessun prodotto può produrre altro. Non aggiungere guardie qui.
- **Non** «`kitap_permits` non è prezzato»: è prezzato, è **irraggiungibile**. Difetto diverso, cura diversa.

## Le domande per te

1. **T2, e va sciolta prima delle altre**: la riga «scegli se contattare un consulente» la
   cambiamo (il consulente T2 diventa dichiarato come incluso), oppure il ruling T2 si ammorbidisce?
   Non firmo termini che il prodotto smentisce.
2. **Termini T2, il testo**: cosa promettiamo esattamente — contatto entro quante ore, in che
   lingua, di chi è il nome? Oggi **non esiste una sola riga** di termini T2 in nessuna superficie
   cliente: cercata in `apps/mouth`, `apps/backend-rag` e `docs/`, zero.
3. **Rinnovi ed estensioni**: le 43 righe non raggiungibili (incluso KITAP intero) entrano nel
   catalogo dell'Oracolo o restano fuori dichiaratamente? È una decisione di prodotto, non un bug
   da chiudere in silenzio.

**Quello che faccio io senza chiederti nulla**, se non mi fermi: rendere `metadata.last_updated`
verificabile — un controllo che va rosso quando il file dei prezzi cambia senza che la sua data si
muova, e i test che smettono di fissare una data stantia come atteso. Il _quanto costa un visto_ è
tuo; il _poter dimostrare quando è cambiato_ è mio.
