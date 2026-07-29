---
date: 2026-07-29
domain: compliance
client_case: none-product-research
sources:
  - postgres-nuzantara (Fly prod, nuzantara_readonly role) — tables whatsapp_message_context, conversation_messages, meta_inbox_messages, query_analytics
  - Pro local mirror DB `nuzantara_dev` (nuzantara@Nuzantara, live WhatsApp mirror, current through 2026-07-29) — table whatsapp_message_context
  - mcp__nuzantara-mcp__get_failed_queries / get_query_analytics (both 404 — endpoint not deployed, declared as [LACUNA])
---

# Lane E — Does real client demand for SLHS exist?

## Verdict

**DOMANDA ESISTENTE, PICCOLA E RECENTE — non "domanda da creare da zero".** Il termine SLHS (Sertifikat
Laik Higiene Sanitasi) e i suoi sinonimi compaiono in **29 messaggi WhatsApp distinti** su ~74.000
scambiati a giugno-luglio 2026 (~0,04%), distribuiti su **10 client_id distinti**, e — punto decisivo —
**in almeno 2 casi il team (Surya, Ari, Tamon) sta già seguendo attivamente il cliente attraverso il
processo**, non lo sta ignorando né rimandando. Il segnale è debole in volume assoluto ma è: (a) organico
(non da una campagna nostra), (b) in crescita mese su mese, (c) collegato a un vero mismatch di prodotto —
lo gestiamo ad-hoc dentro il servizio di company-setup, non come voce di listino a sé.

## Metodo e superfici interrogate

Terminologia cercata (case-insensitive, `ILIKE`): `higiene`, `hygiene`, `sanitasi`, `SLHS`, `laik sehat`,
`laik higiene`, `dinas kesehatan`, `health certificate`, `food permit`, `keamanan pangan`, `penjamah`,
`sertifikat sehat`, `health permit`. Ogni query è stata eseguita in questo turno; ogni "zero" è stato
verificato con un controllo positivo sullo stesso campo/tabella (`visa`/`kitas`), per escludere che la
sonda stessa fosse cieca.

**Scoperta metodologica rilevante**: esistono DUE copie della tabella `whatsapp_message_context` con stati
diversi:
- **Fly Postgres prod** (quella dietro `postgres-nuzantara` MCP) — 77.446 righe, **ferma al 2026-05-25**.
- **Mirror locale sul Pro** (`nuzantara_dev`, DB locale, non è un ambiente di test nonostante il nome) —
  94.595 righe, **aggiornata in tempo reale fino a oggi 2026-07-29**.

La prima è uno snapshot stale; la seconda è la fonte viva. Tutti i numeri sotto vengono dalla seconda
salvo dove indicato. Questo è di per sé un finding operativo: chiunque misuri "quanto arriva dai clienti"
guardando solo il DB Fly sta guardando un mondo fermo a 2 mesi fa.

## Numeri (aggregati, mai testo di messaggio)

### Superficie 1 — WhatsApp mirror live (Pro, `nuzantara_dev.whatsapp_message_context`, 94.595 righe totali, 2022→oggi)

Controllo positivo: `visa`/`kitas` = 6.695 hit su 94.595 (la sonda funziona).

| Termine | Hit |
|---|---|
| SLHS (acronimo) | 22 |
| hygiene/higiene | 17 |
| laik sehat / laik higiene | 10 |
| sanitasi | 7 |
| dinas kesehatan | 6 |
| health certificate / health permit | 2 |
| penjamah | 2 |
| food permit / keamanan pangan / sertifikat sehat | 0 |

**Messaggi distinti che matchano almeno un termine: 29** (un messaggio può contenere più termini,
es. "SLHS" + "sertifikat laik sehat" nello stesso testo).

- **Per direzione**: 13 inbound (cliente→noi) · 16 outbound (noi→cliente).
- **Per collegamento a un client_id esistente**: 24/29 legati a un client_id già a CRM (9 inbound + 15
  outbound) · 5/29 senza client_id (4 inbound + 1 outbound — verosimilmente conversazioni non ancora
  riconciliate o thread interni di coordinamento team, non lead nuovi non tracciati).
- **Distribuzione**: 10 client_id distinti, 6 numeri di telefono distinti — **non è un solo thread ripetuto**,
  è domanda sparsa su clienti diversi.
- **Trend mensile — zero prima di giugno 2026**: 0 hit in ogni mese da inizio mirror (2022) fino a maggio
  2026 incluso; poi **giugno 2026 = 10 (5 inbound + 5 outbound)**, **luglio 2026 = 19 (8 inbound + 11
  outbound)**. Base di confronto sul volume totale dello stesso periodo: maggio 5.776 msg, giugno 31.673,
  luglio 42.301 — il volume totale è cresciuto ~7×, il volume SLHS da 0 a 19: la crescita SLHS non è
  spiegabile solo dalla crescita generale del canale, è un salto da zero.

### Superficie 2 — WhatsApp mirror stale (Fly prod, fermo a 2026-05-25, 77.446 righe)

Controllo positivo: `visa`/`kitas` = 8.034 hit. Termine SLHS-family: **3 messaggi**, tutti **outbound**,
tutti sulla stessa singola relazione cliente (un cafe/F&B), nessuno collegato a un client_id in tabella —
lettere di Bali Zero VERSO il cliente su nuovi requisiti/cambio indirizzo KBLI, non domande in arrivo.
Zero segnale di domanda inbound qui — coerente col fatto che questa copia è ferma a prima che il segnale
esplodesse (giugno 2026).

### Superficie 3 — Bot WhatsApp diretto (`conversation_messages`, 816 righe, dal 2026-05-12) e Meta inbox (`meta_inbox_messages`, 533 righe, dal 2026-06-03)

Controllo positivo (`visa`/`kitas`): 136/816 e 69/533. Termine SLHS-family: **3 hit in ciascuna tabella**,
ma **tutti riconducibili a due episodi non-organici**, verificati leggendo il turno immediatamente
precedente di ogni hit (non il contenuto, la provenienza):
- **28 luglio 2026**: il "primo test col team" registrato in memoria (78 domande, 17 membri del team che
  interrogano il bot con scenari) — un membro del team ha posto una domanda ipotetica su un cliente che
  vuole aprire un cafe a Ubud; la risposta del bot menziona permessi obbligatori. È un test interno, non un
  cliente reale.
- **24 luglio 2026**: un thread dove il bot risponde direttamente ad "Antonello" con domande formattate
  come script di test (box-drawing characters, stile red-team) su un ristorante ipotetico a Canggu — è
  Zero stesso che sonda il bot, non un cliente.

Zero segnale organico su questa superficie.

### Superficie 4 — `query_analytics` (RAG query log, 6.976 righe, dal 2025-12-18)

Controllo positivo: 1.476/6.976. Termine SLHS-family: **2 hit**, entrambe con `session_id = NULL` (non
una sessione utente tracciata) e scritte in un italiano formale/analitico coerente con query di test del
sistema RAG, non con la forma colloquiale delle domande clienti osservate altrove. Trattate come rumore
di QA, non domanda.

Baseline di contesto (non domanda SLHS, ma interesse F&B in generale): query che citano codici KBLI F&B
(56101/56102/56210/55111/56301/56303) o le parole ristorante/cafe/restaurant = **54/6.976 (~0,8%)** — il
verticale F&B è un tema ricorrente nel RAG; SLHS ne è oggi una frazione piccola (2/54).

### Superficie 5 — RAG failed-queries / query-analytics endpoint

`mcp__nuzantara-mcp__get_failed_queries` e `get_query_analytics` → **[LACUNA] HTTP 404** su entrambi
(`/api/query-analytics/failed`, `/api/query-analytics/volume` non deployati). Non posso quindi dire quante
domande su SLHS il bot RAG ha ricevuto e non saputo rispondere per via di questo strumento — sostituito
dalla superficie 4 (`query_analytics` via Postgres diretto), che copre lo stesso dominio dato ma non il
verdetto ABSTAIN/CAUTIOUS esplicito.

## Forma lessicale con cui arriva (parafrasata, mai citazione verbatim)

Osservando i 29 hit della superficie live (senza copiare testo):

- **L'acronimo "SLHS" viene usato direttamente e correttamente da almeno un cliente straniero**, in un
  thread di più settimane con il team (case reference interno: client_id nella cache aggregata, non
  riportato qui) — sa già il nome tecnico del documento.
- **La resa indonesiana informale "sertifikat laik sehat"** (variante colloquiale, tecnicamente il nome
  corretto è "Sertifikat Laik Higiene Sanitasi") è la forma più frequente lato indonesiano/team interno —
  usata in uno scambio interno di coordinamento (nessun client_id collegato) su come soddisfare un
  requisito di KBLI a rischio medio-basso.
- **"Health certificate" in inglese** compare in almeno un thread con cliente straniero, nel contesto di
  "posso procedere solo dopo l'approvazione del mio health certificate" — segnale di dipendenza/blocco di
  processo, non di semplice curiosità.
- **Un termine adiacente e spesso mescolato nello stesso thread: "Sertifikat Standar" (SS)** — un
  documento OSS diverso ma discusso a fianco di SLHS/health-certificate nella stessa conversazione
  (apertura conto bancario bloccata in un caso perché la banca non accettava un Sertifikat Standar in
  quello stato). Rischio SEO/prodotto: se costruiamo una pagina "SLHS" isolata dal resto del pacchetto
  permessi F&B (SS, NIB, PB-UMKU), rischiamo di rispondere solo a un pezzo della domanda reale, che arriva
  a grappolo.
- **[ESEMPIO SINTETICO]** — forma tipica osservata (non è una citazione, è una parafrasi rappresentativa
  del pattern): *"stiamo per aprire, ci hanno chiesto anche l'SLHS oltre alla Sertifikat Standar, chi se ne
  occupa da voi?"*

## Cosa abbiamo risposto quando è arrivata

Nei 2 casi con client_id collegato e più scambi (non un singolo messaggio isolato), il pattern osservato
(per struttura del thread, non per contenuto) è: **il team ha risposto e accompagnato il cliente nel
processo** — follow-up multipli su più settimane (10-25 giorni), aggiornamenti di stato reciproci
("quasi completato"), coordinamento su documenti collegati (NIB, BPJS, conto bancario). Non c'è evidenza
nei dati di un cliente lasciato senza risposta su questo tema specifico. Questo è il punto strategico più
importante: **la domanda non è "inevasa"** nel senso di ignorata — è **gestita ad-hoc, dentro il servizio
di company-setup, senza essere un prodotto a sé con un prezzo e una pagina propri.** La domanda del team
lead ("creare o già in inbox?") ha quindi una terza risposta oltre le due proposte: è già in inbox E già
gestita, ma non è ancora un prodotto — è lavoro invisibile dentro un altro servizio.

## Limiti dichiarati

- Non ho potuto interrogare l'endpoint RAG failed-queries/analytics dedicato (404, superficie 5) — il dato
  equivalente via Postgres diretto (superficie 4) copre lo stesso periodo ma non isola il verdetto
  ABSTAIN esplicito.
- Non esiste una tabella di analytics sulle pagine KBLI viste (`analytics_map_lookups` esiste ma non è
  stata verificata contenere pageview KBLI per codice F&B — fuori scope del tempo disponibile, dichiarato
  qui piuttosto che stimato).
- I 5 hit "senza client_id" sulla superficie live non sono stati riconciliati a un lead specifico — non so
  se sono thread di coordinamento interno o lead non ancora agganciati al CRM; l'ho dichiarato come
  ambiguità, non risolto per non rischiare di esporre PII nel tentativo di chiarirlo.
