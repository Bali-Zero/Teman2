# Ruling di Zero — 2026-08-25

> Sei decisioni chieste, sei date. Questo file è l'**autorità citabile**: ogni lane che tocca
> una di queste superfici cita la riga, non la propria interpretazione.

## 1. T2 — il consulente è VALORE, non un'opzione

**Ruling (verbatim):** _«sui T2 il consulente è incluso — lo schermo deve dirlo come valore ("un
consulente ti contatta, è compreso"), non offrirlo come opzione; l'opzione "chiama quando vuoi"
resta su tutti come pulsante, ma sui T2 il contatto è promessa, non scelta.»_

Due cose distinte, e vanno tenute distinte in codice:

- **Il pulsante C3** («parla con un consulente») resta su **ogni** schermata e **ogni** tier —
  invariato, è il contratto C3.
- **La riga di next-step** smette di essere unica: su T2 dichiara il contatto come **compreso e
  automatico**; su T1 resta la formulazione facoltativa; su T3 è l'unica strada.

La regola **non** si ammorbidisce. Se una superficie non sa il tier, il difetto è la superficie.

## 2. Termini T2 — la promessa, testuale

**Ruling (verbatim):** _«Un consulente ti contatta entro 24 ore lavorative, in inglese o nella tua
lingua (IT/ID disponibili)»_ — «promessa prudente che battiamo in pratica».

Va scritta in **due** posti, non uno: **pagina prodotto** _e_ **mail post-acquisto**.

## 3. Ritenzione wizard — 30 giorni, e il testo libero si ritira

**Ruling:** **30 giorni** (non i 90 dichiarati) — «bastano per il visitatore che torna e per
l'analisi funnel, minimizzano la ritenzione dichiarata». E: **sì, ritira il funnel vecchio a testo
libero** — «raccoglieva ambiguità che poi pagavamo a mano».

Conseguenza: la domanda 2 di `SWITCHBOARD-2-RETENTION.md` è chiusa. Non si costruisce una purge
su un campo che smette di esistere: si **ferma la raccolta** e resta solo **smaltire l'arretrato**.

## 4. Due porte — 301, e il noindex cade solo dopo il punto 1

**Ruling:** la vecchia porta si ritira con **301 → `/visa-oracle`** — «mai un motore non verificato
indicizzato col nostro nome sopra». Il **noindex sulla nuova si toglie SOLO dopo il fix del punto
1**; il redirect intanto conserva la SEO.

Ordine vincolante, non negoziabile: **301 subito** · **noindex via dopo il T2-copy**. Togliere il
noindex prima significherebbe indicizzare una pagina che dice ai clienti T2 il contrario del vero.

## 5. Mai una schermata a zero risultati

**Ruling (verbatim):** _«zero-risultati è vietato come schermata»_ — «per E28B serve una persona,
ma con il tuo profilo E28A è supportato: eccolo» + pulsante consulente. «Ogni vicolo cieco diventa
un candidato onesto + una mano tesa.»

È l'opzione **(2)** di `REVIEW-EMPTIES-CANDIDATES.md`: lo stato resta `HUMAN_REVIEW_REQUIRED` — la
precedenza a cinque esiti **non si tocca** — ma i candidati già calcolati **viaggiano con esso**.
Cambia cosa `assemble` porta sul ramo review, non chi vince.

## 6. E31D — resta a operatore

**Ruling:** niente estensione del vocabolario dei fatti. «Estendere il vocabolario arma ogni regola
che lo tocca (la cicatrice la conosciamo) per un caso raro e sfumato.» E31D va in
**`HUMAN_REVIEW`** con copy garbato; **si riapre solo se i numeri mostrano volume.**

## Minori

- **Rinnovi / estensioni / KITAP: FUORI dal catalogo v1.** «Sono flussi da cliente esistente,
  vivono nel portal/CRM, non nel wizard d'acquisizione.» Le 43 righe PricingTool non puntate non
  sono un difetto da chiudere: sono un confine di prodotto, ora dichiarato.
- **DPIA delta: annotato ora, firmato nel pacchetto unico d'accensione.** «Una cerimonia di firme,
  non gocce.»

---

## §7 — Il criterio della firma #3 (Zero, 2026-08-25, verbatim: «ok firma il criterio»)

**Contesto della richiesta.** Il mandato (§5) chiedeva per lo switchboard #3 una _«zero-divergence
report engine↔consultants»_. La misura sul pack **firmato** `rulepack-prod-013` dà 4/20 corrispondenze
e 16 divergenze. Aperte una per una: **quindici non sono difetti** — il corpus di prova è più vecchio
e più piccolo del motore (7), oppure il motore è deliberatamente **più prudente** delle attese (5),
oppure fa una domanda diversa ma arriva comunque (2). Una sola è un difetto: la #15.

**Il criterio è stato cambiato, e Zero l'ha firmato sapendolo.** Non si firma più «zero divergenze»,
si firma:

> **Ogni divergenza spiegata, e nessuna di esse un vicolo cieco.**

**Perché il vecchio criterio era la trappola, non l'obiettivo.** Portare le divergenze a zero
significherebbe riscrivere le attese del corpus per farle combaciare col motore — cioè **truccare la
prova**, e distruggere per giunta la testimonianza di cinque regole di sicurezza che stanno
funzionando. Il corpus è evidenza, non una manopola: resta vietato toccare le persone di prova o le
loro attese per far tornare un numero.

**Cosa NON è stato firmato.** La firma #3 **non** è concessa da questo ruling: è concesso il
criterio con cui sarà valutata. La #15 resta aperta — un vicolo cieco vivo, misurato — e finché non è
chiusa il registro d'accensione (`contracts/ignition_signatures.json`) tiene `signed: false` sulla
#3. Istruzione contestuale di Zero, stesso messaggio: **«vai avanti col vicolo cieco.»**

---

## Addendum — Rulings collected 2026-08-25 evening (switchboard #4/#5 + DPIA, via the orchestrating session)

Zero answered the distilled questionnaire live in the interactive session on M5. Verbatim
answers recorded by the session; the questionnaire's numbering follows the distilled list
(A/B/C/D grouping from TIER-MAP.md / SWITCHBOARD-5-PRICES-AND-TERMS.md / DPIA-DELTA).

1. **No-price products → T3 automatically: YES** («si»). The 12 unpriced products stay
   consultant-routed until they carry a price.
2. **T1 direct purchase: YES, with an always-visible escape hatch** — verbatim: «il percorso
   può portarli all'acquisto diretto, certo. ma c'è sempre un bottone, un qualcosa se si
   sentono smarriti per contattare il consulente». The "talk to a consultant" control is a
   REQUIREMENT on every tier's screen, not an option to design away.
3. **T2 model confirmed** — verbatim: «creare sempre il percorso e dare le info giuste, ma va
   bene incanalarlo al consulente». Full path + correct information, then channel to the
   consultant (contact included, 24h working-hours promise stands).
4. **E33A/B/C stay pull, never automated** — verbatim: «lasciamoli contattare un consulente.
   Sono per la strategia pull no push». The client reaches out; the system never pushes.
5. **E31D stays human-operator: YES** («si»).
6. **T2 verdict-screen copy change APPROVED** («confermo»): "un consulente ti contatta, è
   compreso" replaces "scegli se contattare un consulente" on the 19 T2 products.
9. **DPIA delta: one-page signed addendum APPROVED** («si») in place of a full new DPIA for
   the consultant-request table.

Items 8 (renewals/KITAP out of catalog v1), 10 (wizard retention 30 days), 11 (retire the
free-text funnel), 12 (proceed with dead end #15) were already ruled earlier on 2026-08-25 in
this document and were re-presented for courtesy only — they stand unchanged; no new answer
was required or recorded.

Note on #3 ignition: signature #3 WAS granted later the same day — Zero ran the seq-15
signing ceremony by hand and instructed the flip (commit on this branch: "feat(visa-oracle):
seq-15 signed bundle + ignition signature #3 granted by Zero"). The paragraph above this
addendum describes the earlier state and is superseded on that single point.
