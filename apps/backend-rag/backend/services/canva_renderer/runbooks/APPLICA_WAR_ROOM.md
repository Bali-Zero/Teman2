# War Room — Carousel Apply Prompt (v3 — daily neutral)

> Questo prompt è neutro e riutilizzabile ogni giorno. Legge sempre i dati
> freschi dal file di output del giorno. Il chiamante (`claude_invoker.py`)
> antepone una riga "Apply the canva_pending.json at path: <PATH>" che vale
> più del placeholder qui sotto.

---

Leggi il file canva_pending.json indicato nell'header del prompt (il
chiamante inietta sempre un path assoluto). Esegui i seguenti step
nell'ordine esatto. Non chiedere conferma tra uno step e l'altro. Se un
tool fallisce, riprova una volta con parametri corretti prima di
segnalare il problema.

STEP 0 — Lettura e validazione input
Dal canva_pending.json estrai e tieni in memoria per tutta la sessione:

template_design_id — il template da usare come workspace
folder_id — la folder Canva di destinazione
topic — il titolo del carousel
tone — il tono editoriale (usato solo come riferimento)
operations — array di operazioni da applicare
slides — array con il contenuto completo di ogni slide (headline, subhead, body, notes, layout, slide_type, image_placement)
slides_count — numero totale di slide

Controlla ogni operazione replace_text:

Se il testo finisce senza punteggiatura finale (. ! ?) e sembra troncato, segnala: ⚠️ Slide N: testo probabilmente troncato
Se il testo supera 280 caratteri, segnala: ⚠️ Slide N: testo lungo (X chars) — potrebbe non entrare nel frame

Controlla ogni URL nelle operazioni upload-asset-from-url:

Deve essere nel formato https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/...
Se è in formato path-style (fly.storage.tigris.dev/nuzantara-warroom-images/...) convertila al formato subdomain prima di procedere

Se ci sono problemi bloccanti (nessun topic, nessuna operazione, template mancante), fermati e segnala. Warning non bloccanti: elencali e vai avanti.

STEP 1 — Apri il template in editing
Usa Start Editing Transaction sul template_design_id.

⚠️ NON usare create-design-from-candidate — richiede un job_id da generate-design e non funziona per duplicare template esistenti. Il template è il workspace di lavoro: viene modificato qui e poi duplicato.

Dalla risposta della transaction, estrai:

La lista di tutti gli elementi richtexts disponibili (con element_id e page_index)
La lista di tutti i frame/immagini disponibili (con element_id e page_index)

Tieni questa mappa per i passaggi successivi.

STEP 2 — Verifica e remap degli element ID
Per ogni operazione replace_text nel JSON:

Se element_id è valorizzato → cercalo nella lista richtexts della transaction
Se esiste → usa direttamente
Se NON esiste → cerca nella stessa pagina un elemento con ruolo analogo (prima occorrenza = headline, seconda = body) e usa quell'ID. Logga: 🔄 Remap slide N: [vecchio_id] → [nuovo_id]

ℹ️ A partire da 2026-03-31 il builder NON emette più operazioni con \_needs_remap: true. Le slide con layout heading-only (slide 9, 11) non hanno slot body nel template — il builder le salta direttamente. Se vedi element_id: null è solo per le immagini (step 4).

Per ogni operazione upload-asset-from-url:

Se element_id è valorizzato → usalo direttamente
Se element_id è null → cerca nella lista frame/immagini un elemento con il page_index corrispondente e usalo. Logga: 🖼️ Frame slide N: [element_id]

Se per una pagina non trovi nessun elemento adatto, segnala e salta quella slide.

STEP 3 — Applica i testi con intelligenza editoriale
Non eseguire un ciclo robotico di replace_text. Lavora da senior editorial designer: per ogni slide, prendi decisioni creative su gerarchia, spezzatura del testo ed enfasi visiva. Usa slides[] dal JSON — non solo operations[].
Struttura a 3 livelli
Il template ha 3 text element per pagina (non 1 combinato):
LivelloColoreContenutoHeadlineBianco, bold, grandePrima riga del titoloSubheadGiallo #f9ca55, medioSottotitolo / seconda rigaBodyBianco, regularBullets o prosa
Non concatenare headline + subhead in un unico elemento. Mappare sempre il contenuto sui 3 element_id separati del template per ogni pagina.
Headlines spezzate
Ogni headline va su 2 righe con \n, spezzando dove c'è tensione narrativa o il titolo supera ~4 parole. Esempi:

"ITALY'S GRIP: HOW IT WORKS" → "ITALY'S GRIP:\nHOW IT WORKS"
"THE TIE-BREAKER NOBODY READS" → "THE TIE-BREAKER\nNOBODY READS"
"WHAT 'DECOUPLING' ACTUALLY MEANS" → "WHAT 'DECOUPLING'\nACTUALLY MEANS"
"AIRE IS NOT ENOUGH" → lasciare su una riga se già corta e incisiva

Salient moment slides
Se slide_type: "D" o notes contiene "SALIENT MOMENT":

Body svuotato ("") — nessun testo nel body element
Solo headline + subhead: tutta la forza va sulla frase + immagine
Non aggiungere bullets o testo aggiuntivo

Body text

Usare \n\n tra ogni bullet per respirabilità
Se il contenuto ha 3 bullets e c'è logica narrativa, valutare un quarto che completi l'arco informativo
Massimo ~40 parole per bullet, nessun muro di testo

Aggiorna il titolo del design con il topic dal JSON.
Applica tutte le operazioni in bulk con perform-editing-operations (slide 1-6 in un blocco, slide 7-11 in un secondo blocco).

STEP 3.5 — Formatting editoriale (bold + keyword color)
Dopo i replace_text, esegui un secondo pass di formattazione. Non saltare questo step — è ciò che trasforma il carousel da flat a curato.
Bold selettivo sul body
Per ogni elemento body: applica format_text con font_weight: bold sull'intero elemento. Poi usa find_and_replace_text per "marcare" visivamente i termini chiave (il testo rimane identico, il bold globale li valorizza già).
Termini da enfatizzare (bold o colore giallo #f9ca55)
Scegliere 2-3 per slide, non di più:

Acronimi legali IT: AIRE, IRPEF, DTT, TUIR, UUPA
Acronimi legali ID: KITAS, KITAP, E33G, NPWP, PT PMA, IMTA, BPN, PPAT, BPHTB, PPh, PNBP, PBB, OSS, LKPM, NIB, ITAS, ITAP
Concetti chiave: center of vital interests, Hak Pakai, tie-breaker, fiscal domicile, nominee agreement, Hak Milik, leasehold
Numeri shock: percentuali (35%, 43%), cifre IDR/USD, anni (30 years, 80 years)

STEP 4 — Inserisci le immagini
Per ogni operazione upload-asset-from-url:

Chiama Upload Asset From URL con l'URL dell'immagine
Ottieni l'asset_id restituito
Usa Perform Editing Operations per posizionare l'asset nel frame del page_index corrispondente (trovato allo step 2)

Decisioni di posizionamento per tipo di layout:

layout: "full_bleed" → update_fill sul frame full-background
layout: "split" → immagine nella metà inferiore o destra (coordinate: left=540, top=0, width=540, height=1350)
element_id: null → usare insert_fill con coordinate calcolate in base al campo placement nel JSON
Cover: sempre full-bleed, testo overlay

Al termine usa Commit Transaction.

STEP 5 — Duplica il template → crea il design finale
Usa Resize Design con:

design_id: il template_design_id dal JSON
width: 1080
height: 1350
title: il topic dal JSON

Salva il new_design_id restituito. Questo è il design finale — non il template.

STEP 6 — Sposta nella folder carousel
Usa Move Item To Folder con:

item_id: il new_design_id dello step 5
folder_id: il folder_id dal JSON

STEP 7 — Verifica visiva
Usa Get Design Thumbnail per le pagine 1, centrale e ultima del new_design_id.
Checklist:

Cover (pagina 1): immagine posizionata, headline leggibile
Slide centrale: testo non troncato, body visibile, bold sui termini chiave
Ultima slide (CTA): headline + subhead presenti, logo Bali Zero visibile
Nessuna pagina vuota o con testo placeholder del template

Se trovi problemi (testo mancante, immagine non posizionata), rientra in editing sul new_design_id e correggi. Se tutto OK, procedi.

STEP 8 — Aggiorna il file e riporta
Aggiorna canva_pending.json aggiungendo/sovrascrivendo:
json{
"design_id": "<new_design_id>",
"design_url": "https://www.canva.com/design/<new_design_id>/edit",
"status": "applied",
"applied_at": "<ISO timestamp>"
}
Output finale da mostrare:
✅ Carousel applicato
Topic: <topic>
Design: https://www.canva.com/design/<new_design_id>/edit
Folder: <folder_id>
Testi applicati: X / Y
Immagini inserite: X / Y
Remap effettuati: X
⚠️ Warning: <lista o "nessuno">

Note tecniche ricorrenti (da non dimenticare ogni sessione):

resize-design restituisce un nuovo design ID — salvarlo subito
Gli element ID del template cambiano se il template viene modificato manualmente da Canva — rifare lo step 2 se il template è stato toccato
Le URL Tigris devono essere in formato subdomain, non path-style
Il template DAHE6lx1lf8 è il workspace permanente — viene sempre sovrascritto e poi duplicato
La folder FAHEwkTYduI è la "Carousel" folder di Bali Zero
Slide 9 e 11: layout heading-only — NON hanno slot body. Il builder non emette operazioni body per queste. Normale.
Il template ha 3 text element per pagina (headline/subhead/body) — MAI concatenarli in un unico replace_text
Salient moment slides (slide_type: "D"): body element vuoto, solo headline + subhead
STEP 3.5 obbligatorio: bold + keyword color — non saltarlo, è il passo che differenzia il ciclo robotico dal design curato
Se element_id: null in un'operazione immagine → usare insert_fill con coordinate esplicite
