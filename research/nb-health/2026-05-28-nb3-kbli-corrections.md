---
date: 2026-05-28
domain: nb-health
notebook: NB-3 Company Setup Indonesia
notebook_uuid: 933509f9-1561-403d-bd44-4a7a67a36df2
type: correction-report
severity: P2
discovered_by: deep-researcher (primary-source verification, Peraturan BPS 7/2025 PDF 623pp letto direttamente)
trigger: Antonello challenge "hanno cercato nel KBLI 2025? e la legge BPS di dicembre 2025?"
adversarial_review: codex
sources:
  - research/company/2026-05-28-kbli-2025-bps-december-verify.md
  - research/visa/2026-05-28-e33g-kbli-content-creator-pivot.md
  - "PRIMARY: Peraturan BPS No. 7 Tahun 2025 (KBLI 2025, 623pp, letto direttamente)"
---

# NB-3 — Segnalazione imprecisioni KBLI 2025 (2 errori + 1 nota)

> ⛔ **SCADUTO COME CONSIGLIO OPERATIVO — leggi §Adversarial review prima di agire.**
> Questo documento è del **2026-05-28** e parla al presente di maggio 2026. La
> scadenza che descrive come futura — **18 giugno 2026**, transizione KBLI
> 2020→2025 — **è passata**. Al 2026-07-29 la riga "OSS registra ancora con
> KBLI 2020, si converte dopo" **non va più seguita** per una PT PMA nuova.
> Il reperto storico (NB-3 aveva 2 imprecisioni) resta valido; la *raccomandazione*
> no. Vale anche la conferma §CONFERMATO: la catena di fonti che cita è rotta.

Discovered durante verifica fonte primaria del KBLI 2025 per il pivot carosello content creator. NB-3 (Company Setup Indonesia) ground-truth ha 2 imprecisioni materiali + 1 nota di contesto. Nessuna è "bugia": NB-3 cita documenti reali, ma datati/versionati male.

**Decisione su correzione → operatore (Antonello). Questa è una segnalazione, non un auto-edit di NB.** Symbiosis Law 2 (OSINT/NB curati) + Law 5 (Zero decide su strutturale).

---

## ERRORE 1 (P2) — Codice 74149 "Desain Konten Kreatif Lainnya" attribuito a KBLI 2025

**NB-3 source_id `4f7bfcb6`** presenta `74149 — Aktivitas Desain Konten Kreatif Lainnya` citando un Lampiran "PRESIDEN REPUBLIK INDONESIA" (74141/74142/74149) come se fosse KBLI 2025.

**Realtà (verificata sul PDF Peraturan BPS 7/2025, grep esaustivo)**:

- `74149` → **0 match** nel testo KBLI 2025. È un codice **KBLI 2020**.
- Subgruppo 7419 del KBLI 2025 = `74191` (interior) / `74192` (grafis) / `74193` (desain khusus film-video-TV) / `74194` (desain konten gim, NUOVO) / `74199` (desain khusus lainnya YTDL).
- Il 74149 del 2020 è stato assorbito (verso 74199 YTDL).

**Causa radice**: NB-3 ha conflato la **matrice rischio OSS-RBA / Lampiran Perpres** (numerazione KBLI 2020) con il testo BPS KBLI 2025. Il documento citato è reale ma è un Lampiran Perpres su base KBLI 2020, non il Peraturan BPS 7/2025.

**Correzione proposta**: rimuovere 74149 come "codice nuovo/granulare KBLI 2025". Aggiungere nota: "74149 = KBLI 2020; in KBLI 2025 i codici design content sono 74194 (Desain Konten Gim) + 74199 (YTDL). I veri codici creator 2025 sono 59112/60103/60203/60390/90113/90200."

---

## ERRORE 2 (P2) — Tempistica OSS / KBLI 2025 "già mandatorio"

**NB-3 source_id `bbf21201`** afferma che OSS è già obbligato a usare KBLI 2025 a maggio 2026 ("31 mag 2026 full migration OSS RBA 1.2 + KBLI 2025").

**Realtà (WebSearch tier-2 convergente + Pasal 5 primaria + Permen BKPM 5/2025 Pasal 393)**:

- Al 28 maggio 2026 **OSS opera ANCORA su KBLI 2020**.
- KBLI 2020 e 2025 girano in **PARALLELO** durante la transizione.
- Cutoff legale conversione automatica: **18 giugno 2026** (Pasal 5 BPS 7/2025 = 6 mesi da promulgazione 18 dic 2025).
- Conversione AUTOMATICA lato-sistema (Permen BKPM 5/2025 Pasal 393), non a carico del cliente.

**Impatto pratico**: una PT PMA aperta a maggio/giugno 2026 si registra con codici KBLI **2020**, convertiti automaticamente dopo. Affermare "KBLI 2025 già mandatorio" rischia di far selezionare codici non ancora accettati da OSS.

**Correzione proposta**: aggiornare la entry a "coesistenza parallela KBLI 2020/2025 fino al 18 giu 2026; OSS registra ancora con KBLI 2020 a maggio 2026; conversione automatica lato-sistema". Mantenere il flag di verifica empirica OSS al momento del deposito akta.

---

## CONFERMATO (NB-3 corretto) — 73100 Periklanan PMA 49%

**NB-3 source_id `4539bbfb`**: _"73100 — AKTIVITAS PERIKLANAN PMA: TERBATAS (max 49% WNA) — cond: Kemitraan dengan badan usaha dalam negeri"_ + nota errore comune (confusione con rilascio iniziale Perpres 10/2021).

**Verificato CORRETTO**: il cap 49% deriva dalla Daftar Positif Investasi (Perpres 10/2021 jo 49/2021 jo 14/2024), àncora alla descrizione/numero KBLI (73100 invariato 2020→2025). NB-3 aveva ragione contro Gemini (che citava Perpres 10/2021 superata). **Nessuna correzione — anzi NB-3 ha già la nota anti-errore giusta.**

---

## Riepilogo per la curation

| #   | NB-3 source_id | Tipo                                 | Azione                                    |
| --- | -------------- | ------------------------------------ | ----------------------------------------- |
| 1   | `4f7bfcb6`     | ERRORE (74149 = KBLI 2020, non 2025) | Correggere/rimuovere                      |
| 2   | `bbf21201`     | ERRORE (OSS già su 2025)             | Aggiornare a coesistenza fino 18 giu 2026 |
| 3   | `4539bbfb`     | CORRETTO (73100 = 49%)               | Nessuna azione — conferma                 |

**Fonte data per aggiungere a NB-3 se l'operatore approva**: Peraturan BPS No. 7 Tahun 2025 (KBLI 2025, ISIC Rev. 5, 17 dic 2025, transizione 18 giu 2026). Codici creator 2025: 59112 (vlog/podcast verbatim), 60103/60203 (streaming), 60390 (social), 90113 (jurnalis independen), 90200 (influencer-as-talent), 74194 (gim).

**Pattern meta**: NB-3 cita documenti reali ma con versione/data sbagliata (Lampiran Perpres 2020 spacciato per KBLI 2025; tempistica OSS ottimistica). Il rischio NB non è hallucination ma **version-drift su normativa che cambia** — il KBLI è passato da 2020 a 2025 a dicembre e NB-3 non ha catturato la transizione. Suggerimento per nb-curator: flag delle entry KBLI come "version-sensitive — verify against latest BPS Peraturan".

---

## Adversarial review

**Seat**: `codex` (`gpt-5.6-terra`, effort high, sandbox read-only), eseguito il
**2026-07-29** — **due mesi** dopo la stesura, e questo è il punto: il brief
chiedeva esplicitamente di giudicare il documento *come lo leggerebbe un collega
OGGI*, non come era corretto il giorno in cui è nato.
Generator ≠ grader: il documento l'ha scritto un seat Claude (`deep-researcher`),
il refuter è di famiglia diversa. **Un solo seat**: `kimi-k3` provato e morto
(HTTP 403, quota esaurita), Gemini a crediti esauriti — quindi soglia minima, non
accordo (W100). Non è stampato con l'esenzione macchina del gate nb-curator:
questo è un deliverable di ricerca e viene giudicato come tale.

**Sette obiezioni sopravvissute.** Le due più gravi le ho ri-verificate io prima
di trascriverle (W65: anche il refuter allucina).

1. **⛔ Il consiglio operativo è SCADUTO.** «OSS registra ancora con KBLI 2020 a
   maggio 2026 · coesistenza fino al 18 giu 2026 · conversione automatica dopo»
   era vero alla data di stesura. Dal **18 giugno 2026** le pratiche OSS nuove
   girano su KBLI 2025: al 29 luglio, indirizzare una PT PMA nuova verso codici
   2020 è sbagliato. Il documento deve dire "usa KBLI 2025 e verifica il codice
   nel flusso OSS corrente", e trattare la conversione automatica solo come
   disciplina delle posizioni **esistenti**.
2. **La catena di fonti del §CONFERMATO è rotta** — e il §CONFERMATO era la
   parte che il documento dichiarava *verificata corretta*. Il cap 49% su
   **73100 (Periklanan)** è attribuito a «Perpres 10/2021 jo 49/2021 jo
   **14/2024**». **Verificato da me in questo turno**: il
   [Perpres 14/2024](https://peraturan.go.id/id/perpres-no-14-tahun-2024) è
   *Penyelenggaraan Kegiatan Penangkapan dan Penyimpanan Karbon* — carbon capture
   & storage. Non tocca la Daftar Positif Investasi. Il numero può restare vero,
   ma **non è sostenuto dalla fonte citata**: va sostituito con la riga precisa
   dell'allegato vigente o della scheda OSS che riporta codice, limite e
   condizione di kemitraan. (La lezione dentro la lezione: la parte "confermata"
   è quella che nessuno ha ri-controllato.)
3. **«conversione automatica, non a carico del cliente» è troppo assoluto.**
   Pasal 393 dispone l'aggiornamento automatico del PBBR, ma la disciplina
   ufficiale distingue il puro cambio numerico (automatico) dalle modifiche
   sostanziali di *maksud/tujuan* o *ruang lingkup*, che richiedono un
   adeguamento a carico del soggetto. La condizione va scritta.
4. **`ditetapkan` ≠ `diundangkan`.** Il documento dà 17 dicembre 2025 in un punto
   e costruisce i "6 mesi → 18 giugno 2026" in un altro. L'aritmetica regge solo
   dalla **promulgazione del 18**; le due date vanno dichiarate entrambe e mai
   usate come sinonimi.
5. **«74149 è stato assorbito verso 74199»** — l'assenza di `74149` nel testo
   2025 e l'elenco dei codici 7419 non provano da soli una corrispondenza: le
   transizioni possono essere one-to-many. O si cita la riga della tabella di
   conversione BPS 2020→2025, o ci si limita a «74149 non è un codice KBLI 2025».
6. **«grep esaustivo su PDF 623pp» non è verificabile da chi legge.** È
   un'asserzione di provenienza non falsificabile: mancano URL canonico, data di
   download, SHA-256 del PDF, comando di estrazione, output delle query e
   riferimenti di pagina. Sostiene un'**assenza** (`74149` → 0 match), che è la
   classe di affermazione che più ha bisogno di apparato.
7. **«I veri codici creator 2025 sono 59112/60103/60203/60390/90113/90200/74194»**
   — "creator" non è una categoria giuridica, e l'elenco presenta come
   intercambiabili codici con perimetri diversi. Serve, per ciascuno, la
   descrizione e le esclusioni ufficiali, e vanno tenute separate quattro cose
   che il documento fonde: classificazione KBLI, ammissibilità PMA, rischio OSS,
   titolo di soggiorno.

**Disposizione.** Il documento resta come **reperto storico** — i due errori che
segnalava a NB-3 erano reali e restano reali. Ciò che non sopravvive è il suo
uso come guida operativa: l'avviso in testa lo dice, e le obiezioni 2/3/4/5/7
vanno discharged prima che una qualunque di queste righe raggiunga un cliente o
finisca in `apps/backend-rag/data/curated_qa/`.

**Il pattern, che vale più delle sette obiezioni.** Il documento stesso diagnostica
NB-3 con: *«il rischio NB non è hallucination ma **version-drift** su normativa che
cambia»*. Aveva ragione, e poi è caduto nella stessa malattia: due mesi dopo, è
lui la fonte con la versione vecchia. Una capture con consiglio operativo
time-bound ha bisogno di una **data di scadenza dichiarata**, non di una data di
stesura — altrimenti l'unica cosa che distingue il reperto valido dal consiglio
marcio è che qualcuno si ricordi di rileggerlo.
