---
date: 2026-05-28
domain: company
client_case: bali-zero-internal-kbli-2025-bps-december-verify
author: deep-researcher (Antonello/Bali Zero)
status: draft
sources:
  - "PRIMARY: Peraturan BPS No. 7 Tahun 2025 — KBLI 2025 (PDF 623 pp, letto direttamente: /tmp/kbli-2025.pdf da legalitas.org/download/kbli-2025-compressed.pdf, estratto /tmp/kbli-2025-full.txt)"
  - "BPS official news 2025-12-19 + 2026-04-27 (bps.go.id) — rilascio KBLI 2025 + tabel konversi 2020-2025"
  - "WebSearch (hukumonline, smartlegal, golaw, ukmindonesia, MUC, prolegal, Selaras Law) 2026-05-28 — transizione + OSS timeline"
  - "agy Gemini 3.1 Pro (Bahasa recon BPS reg + content creator + OSS) — /tmp/deep-research-kbli2025-gemini.txt"
  - "DeepSeek V4 Pro (reasoning transizione 2020->2025 + impatto registrazione PMA) — /tmp/deepseek-raw2.json"
  - "NB-3 Company Setup Indonesia (UUID 933509f9-1561-403d-bd44-4a7a67a36df2) — cross-check ground-truth, parzialmente CORRETTO da questa ricerca"
partial: false
---

# KBLI 2025 + Peraturan BPS — Verifica Fonte Primaria

## Question (verbatim Antonello)

Verifica EMPIRICA con fonte primaria letta direttamente di due dubbi su KBLI Indonesia: (1) "Hanno cercato in KBLI del 2025?" — esiste davvero un KBLI 2025, qual e la fonte primaria, cosa dice sui codici content creator. (2) "E la legge Badan Statistik di dicembre 2025?" — esiste un atto BPS di dicembre 2025 che la ricerca precedente non ha visto. Determinare se il pivot "PT PMA content creator" del carosello regge.

## TL;DR (3 bullet)

- **L'operatore aveva RAGIONE: il KBLI 2025 E un atto di dicembre 2025.** Peraturan BPS No. 7 Tahun 2025, ditetapkan Jakarta 17 dic 2025, diundangkan 18 dic 2025, abroga Peraturan BPS No. 2/2020. NON e un atto di inizio 2025: la ricerca precedente lo trattava come gia-effettivo, ma e di fine 2025 con transizione 6 mesi fino al 18 giugno 2026.
- **Decisivo per Bali Zero OGGI (28 mag 2026): OSS usa ANCORA KBLI 2020.** KBLI 2020 e 2025 girano in PARALLELO durante la transizione; conversione automatica OSS+AHU entro 18 giu 2026. Una PT PMA registrata oggi usa codici KBLI 2020, convertiti dopo dal sistema. I codici "nuovi" del KBLI 2025 NON sono ancora registrabili come tali su OSS.
- **NB-3 va corretto su 2 punti, confermato su 1.** ERRORE: "74149 Desain Konten Kreatif Lainnya = codice nuovo/granulare KBLI 2025" -> nel testo BPS 7/2025 il 74149 NON ESISTE (e un codice KBLI 2020); KBLI 2025 ha invece 74194 "Desain Konten Gim" + 74199 "Desain Khusus Lainnya YTDL". CONFERMATO da primaria: 73100 Periklanan resta PMA TERBATAS 49% (numero invariato nel 2025, % invariata).

## RISPOSTA ALLE 2 DOMANDE

1. **KBLI 2025 esiste?** -> **SI, confermato leggendo il PDF.** Peraturan Badan Pusat Statistik No. 7 Tahun 2025 tentang Klasifikasi Baku Lapangan Usaha Indonesia. Header verbatim dal PDF: _"PERATURAN BADAN PUSAT STATISTIK NOMOR 7 TAHUN 2025 ... Ditetapkan di Jakarta pada tanggal 17 Desember 2025 ... KEPALA BADAN PUSAT STATISTIK, AMALIA ADININGGAR WIDYASANTI. Diundangkan di Jakarta ..."_. Basato su ISIC Rev. 5 (raccomandazione UN Stat Commission 11 mar 2024). Struttura: 22 categorie A-V (era 21 A-U nel 2020), 87 golongan pokok, 257 golongan, 519 sub-golongan, 1.560 kelompok. **LETTO DIRETTAMENTE: SI** (PDF 623 pagine scaricato e parsato).

2. **Legge BPS dicembre 2025?** -> **TROVATA — ed E lo stesso Peraturan BPS 7/2025.** Non c'e un atto BPS "diverso/successivo" di dicembre: il 7/2025 stesso E l'atto di dicembre. La ricerca precedente lo citava ma non aveva visto che e datato 17-18 dicembre 2025 e che ha un periodo transitorio aperto. Nessun Peraturan BPS n. 9/10/11/12 del 2025 su KBLI (Gemini + WebSearch convergenti). Il finding chiave non e "un nuovo atto mancante" ma "l'atto citato era mis-datato e mis-interpretato come gia operativo".

## Cronologia atti BPS KBLI

| Atto                                                                  | Data                                                | Cosa fa                                                                                                                                | Letto direttamente?                                                 |
| --------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Peraturan BPS No. 2 Tahun 2020                                        | 2020 (BN 2020/1084)                                 | Stabilisce KBLI 2020 (standard precedente)                                                                                             | No (citato da Pasal 6 del 7/2025 che lo abroga)                     |
| **Peraturan BPS No. 7 Tahun 2025**                                    | **ditetapkan 17 dic 2025, diundangkan 18 dic 2025** | Stabilisce KBLI 2025 (ISIC Rev. 5); abroga BPS 2/2020 (Pasal 6); in vigore dalla promulgazione (Pasal 7); transizione 6 mesi (Pasal 5) | **SI — PDF 623 pp**                                                 |
| Surat Edaran Bersama (Menteri Investasi + Menteri Hukum + Kepala BPS) | 2026 (citato fonti tier-2)                          | Disciplina la coesistenza parallela KBLI 2020/2025 su OSS+AHU fino al 18 giu 2026                                                      | No (testo SE non recuperato; riportato da hukumonline/ukmindonesia) |
| BPS "Tabel Konversi KBLI 2020-2025"                                   | 27 apr 2026 (bps.go.id news 897)                    | Tabella di mappatura codici 2020->2025 per la conversione                                                                              | No (annuncio letto, tabella non parsata)                            |

Pasal 5 verbatim dal PDF: _"Pada saat Peraturan Badan ini mulai berlaku, seluruh penggunaan KBLI yang sudah ada pada masing-masing pengguna KBLI wajib menyesuaikan dengan ketentuan Peraturan Badan ini paling lambat 6 (enam) bulan sejak Peraturan Badan ini diundangkan."_ -> cutoff 18 giugno 2026.
Pasal 6 verbatim: _"... Peraturan Badan Pusat Statistik Nomor 2 Tahun 2020 ... dicabut dan dinyatakan tidak berlaku."_
Pasal 7 verbatim: _"Peraturan Badan ini mulai berlaku pada tanggal diundangkan."_

## Codice content creator nel KBLI 2025 [DOCUMENTED — letto nel PDF]

**Indonesia non ha un singolo "content creator code".** Nel testo BPS 7/2025 l'attivita creator e distribuita su codici 5-cifre (kelompok). Estratti verbatim dal PDF:

| KBLI 2025 (5-digit) | Judul verbatim                                                   | Copre (verbatim sintetico)                                                                                                                           | Pertinenza creator                                              |
| ------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **59112**           | AKTIVITAS PRODUKSI FILM, VIDEO, DAN PROGRAM TELEVISI OLEH SWASTA | _"...vlog (video blogging), dan siniar video (video podcast) yang dikelola oleh swasta atas dasar balas jasa"_                                       | **Spina dorsale**: vlog + video podcast esplicitamente nominati |
| **60103**           | AKTIVITAS DISTRIBUSI DAN STREAMING AUDIO ATAS PERMINTAAN         | streaming/distribuzione audio on-demand                                                                                                              | Podcast/audio streaming                                         |
| **60203**           | AKTIVITAS DISTRIBUSI DAN STREAMING VIDEO ATAS PERMINTAAN         | streaming/distribuzione video on-demand                                                                                                              | Video streaming on-demand                                       |
| **60390**           | AKTIVITAS SITUS JEJARING SOSIAL DAN DISTRIBUSI KONTEN LAINNYA    | _"...situs jejaring sosial dan platform distribusi (berbagi) konten ... blog dan wiki, situs video gim (game online), penyediaan e-book..."_         | Distribuzione contenuti social                                  |
| **90113**           | AKTIVITAS JURNALIS BERITA INDEPENDEN                             | _"...pencarian berita oleh perorangan ... dipublikasikan sendiri melalui media cetak maupun digital"_                                                | Blogger/giornalista indipendente                                |
| **90200**           | AKTIVITAS SENI PERTUNJUKAN                                       | seni pertunjukan; cross-ref del PDF colloca _"aktivitas aktor independen (termasuk influencer dalam vlog)"_ nel golongan pokok 90 / subgolongan 9020 | **Influencer-as-talent**: la persona che appare                 |
| **74194**           | AKTIVITAS DESAIN KONTEN GIM                                      | game content design                                                                                                                                  | Creator gaming/design                                           |

> **Nota chiave sulla logica del 2025**: il PDF usa cross-reference ripetuti — _"aktivitas aktor independen (termasuk influencer dalam vlog) ... lihat subgolongan 9020"_ e _"aktivitas blogger independen, lihat subgolongan 9011/90113"_. Cioe: chi PRODUCE il contenuto come azienda sta in 59112/60xxx; chi E il talent/influencer come persona sta in 90 (seni pertunjukan / jurnalis independen). Questo e piu granulare del KBLI 2020.

**Codice 74149 "Desain Konten Kreatif Lainnya" — NON ESISTE in KBLI 2025** [DOCUMENTED — prova di assenza dal PDF]:
Ricerca esaustiva nel testo BPS 7/2025: stringhe `7414`, `74141`, `74142`, `74149`, `DESAIN KONTEN KREATIF` -> **1 solo match: 74194 "DESAIN KONTEN GIM"**. Il subgruppo 7419 del KBLI 2025 e esattamente: 74191 (interior), 74192 (grafis/komunikasi visual), 74193 (desain khusus film/video/TV), 74194 (konten gim), 74199 (desain khusus lainnya YTDL). NESSUN 74149. Gemini conferma: nel KBLI 2020 il 74149 esisteva ("Desain Konten Kreatif Lainnya") ma nel 2025 e stato convertito/assorbito (verso 74199 YTDL). **Il 74149 e un codice KBLI 2020, non un "codice nuovo granulare 2025" come scritto nella ricerca precedente.**

## OSS recepisce KBLI 2025? (CRITICO per registrazione PMA oggi)

**NO — al 28 maggio 2026 OSS opera ANCORA su KBLI 2020.** [DOCUMENTED — WebSearch convergente hukumonline/ukmindonesia/golaw, INFERRED su data esatta migrazione]

- Per aprile 2026 il sistema OSS processa le perizinan con KBLI 2020 (ukmindonesia, hukumonline).
- Conversione automatica OSS+AHU a KBLI 2025 da completare entro **18 giugno 2026** (6 mesi da promulgazione, Pasal 5 + Surat Edaran Bersama).
- Durante la transizione **KBLI 2020 e 2025 girano in PARALLELO**.
- Permen Investasi/BKPM 5/2025 Pasal 393 (verbatim via NB-3 source cc06b0a7): _"Dalam hal terjadi perubahan pengaturan KBLI yang ditetapkan oleh kepala badan ... Sistem OSS secara otomatis melakukan penyesuaian dan pemutakhiran PBBR mengikuti ketentuan KBLI yang baru."_ -> la conversione e AUTOMATICA lato sistema, non a carico del cliente.

> **DISACCORDO su data esatta — vedi sezione Disagreements.** NB-3 dice "OSS gia obbligato a usare KBLI 2025 a maggio 2026, migrazione OSS RBA 1.2 entro 31 mag 2026". Le fonti web tier-2 dicono "OSS ancora su KBLI 2020 ad aprile 2026, cutoff 18 giu 2026". Risoluzione operativa: trattare maggio 2026 come fine-transizione con coesistenza, non come "2025 gia mandatorio".

**Implicazione netta**: un codice content creator "nuovo" del KBLI 2025 NON e usabile come tale su OSS oggi per aprire una PT PMA — si seleziona il codice KBLI 2020 equivalente (59112/60390/73100/74xxx 2020) e il sistema lo converte. Confermato da DeepSeek (punto 2): _"No, not yet. OSS only accepts KBLI 2020 codes ... practical use awaits conversion."_

## PMA% content creation codes (chiusura disaccordo 73100)

**73100 Periklanan = PMA TERBATAS max 49% WNA con kemitraan badan usaha dalam negeri.** [DOCUMENTED — confermato da fonte primaria + NB-3 + DeepSeek convergenti]

- Il **numero 73100 e INVARIATO** dal KBLI 2020 al 2025 (verificato: nel PDF 7/2025 esiste "73100 AKTIVITAS PERIKLANAN"). Quindi la % di proprieta estera NON e toccata dal cambio versione KBLI.
- DeepSeek (punto 4, DOCUMENTED+INFERRED): _"The cap is unaffected. The Positive Investment List (Perpres 10/2021 jo 49/2021 jo 14/2024) anchors to KBLI 2020 descriptions and numbers. 73100 retains its number, so the ownership restriction is identical. The cap travels with the activity, not the KBLI version."_
- NB-3 (source 4539bbfb + 0d22657c): _"73100 — AKTIVITAS PERIKLANAN PMA: TERBATAS (max 49% WNA) — cond: Kemitraan dengan badan usaha dalam negeri"_ + nota errore comune (confusione con Perpres 10/2021 rilascio iniziale).
- **Disaccordo 49% vs 100% del file precedente -> CHIUSO a favore di 49% TERBATAS.** Ragione: il cap deriva dalla Daftar Positif Investasi (Perpres), non dal KBLI; 73100 e esplicitamente listato come settore con partnership obbligatoria. Gemini citava Perpres 10/2021 (versione superata da 14/2024). **Per il creator agency la soluzione pulita resta evitare 73100 e usare i TERBUKA 100%: 59112 + 60390 + 60103/60203 + 74192/74193/74194.**

Codici TERBUKA 100% confermati (NB-3 source 0d22657c, coerenti con descrizioni PDF): 59112, 60390, 60103, 60203, 74192, 74193, 74194, 90113, 90200, 73201 (penelitian pasar). Verifica finale % in OSS per ogni progetto (la % e nel Lampiran Perpres, non nel BPS).

## Implicazione per Bali Zero (cosa cambia rispetto al file precedente)

Il file precedente (`research/visa/2026-05-28-e33g-kbli-content-creator-pivot.md`) regge nella sostanza (E33G vs PT PMA, E28A vs E23, jabatan Creative Director) ma va corretto/integrato su:

1. **Data KBLI 2025**: non "atto generico 2025 gia operativo" ma "Peraturan BPS 7/2025 del 18 dic 2025, in transizione fino al 18 giu 2026". L'operatore aveva ragione: nessuno aveva letto la data.
2. **74149**: rimuovere "Desain Konten Kreatif Lainnya, codice nuovo/granulare KBLI 2025". E un codice KBLI 2020. Nel KBLI 2025 i codici design content sono 74194 (gim) + 74199 (YTDL). I veri codici creator 2025 sono 59112/60103/60203/60390/90113/90200.
3. **OSS = KBLI 2020 oggi**: il punto operativo decisivo. Una PT PMA aperta a maggio/giugno 2026 si registra con codici KBLI 2020, conversione automatica. Il "codice content creator nuovo" e teorico finche OSS non converte (entro 18 giu 2026).
4. **73100 chiuso a 49% TERBATAS** (non piu "disaccordo aperto"): il cap viaggia con l'attivita via Perpres, indipendente dalla versione KBLI.

**Il pivot "PT PMA content creator" REGGE** — anzi e rafforzato: i codici TERBUKA 100% (59112/60390/streaming/design) esistono e coprono vlog/podcast/streaming/social esplicitamente nel testo 2025. Ma il messaggio carosello va calibrato: "i codici esistono nel KBLI 2025 ma si registrano oggi via equivalenti KBLI 2020 con conversione automatica entro giugno 2026" — non promettere un "codice content creator dedicato gia registrabile".

## Disagreements / open questions

- **OSS mandatorio KBLI 2025 a maggio 2026? (NB-3) vs ancora KBLI 2020 (web tier-2)**: NB-3 (source bbf21201) dice "31 mag 2026 full migration OSS RBA 1.2 + KBLI 2025, OSS gia obbligato". Web tier-2 (ukmindonesia/hukumonline) dice "OSS ancora su KBLI 2020 ad aprile 2026, cutoff legale 18 giu 2026, coesistenza parallela". **Risoluzione: trusting il quadro coesistenza-parallela (tier-2 + Pasal 5 primaria + Permen BKPM 5/2025 Pasal 393 conversione automatica).** Anche se la migrazione tecnica OSS RBA 1.2 fosse il 31 mag, la conversione e lato-sistema e i codici 2020 restano accettati in transizione. Per Bali Zero: NON contare su un codice 2025 "puro" registrabile prima del completamento conversione; usare equivalente 2020. **Verifica empirica raccomandata su oss.go.id prima di un deposito akta a giugno.**
- **74149 nella fonte NB-3 (source 4f7bfcb6)**: NB-3 cita un Lampiran "PRESIDEN REPUBLIK INDONESIA" con 74141/74142/74149 — questo e un Lampiran Perpres OSS-RBA basato su **KBLI 2020**, NON il testo BPS 7/2025. NB-3 ha conflato la matrice rischio OSS (numerazione 2020) con il KBLI 2025. **Azione: correggere NB-3** (vedi checklist). Non e che NB-3 mente: cita un documento reale, ma datato KBLI 2020, presentandolo come KBLI 2025.
- **Diundangkan: data esatta e numero Berita Negara**: il PDF mostra "Ditetapkan ... 17 Desember 2025" chiaro; la riga "Diundangkan di Jakarta pada tanggal **_" e il "BERITA NEGARA ... NOMOR _**" hanno glifi corrotti nell'estrazione (caratteri non-ASCII). Gemini + 2 fonti tier-2 (MUC, Selaras) convergono su **18 dicembre 2025** come data di promulgazione. Tratto 17 dic = penetapan, 18 dic = pengundangan (DOCUMENTED penetapan, INFERRED-convergente pengundangan).
- **Tabel Konversi 2020->2025**: pubblicata BPS 27 apr 2026 ma non parsata in questa ricerca. Per la mappatura esatta di un codice cliente 2020->2025, scaricarla quando serve (bps.go.id news 897).

## Checklist for action (Bali Zero)

- [ ] **Correggere NB-3**: la entry "74149 Desain Konten Kreatif Lainnya = codice nuovo KBLI 2025" e errata. Aggiungere nota: 74149 e KBLI 2020; in KBLI 2025 (BPS 7/2025, 18 dic 2025) i codici sono 74194 Desain Konten Gim + 74199 YTDL; i codici creator 2025 sono 59112/60103/60203/60390/90113/90200. Source 4f7bfcb6 e un Lampiran Perpres OSS basato su KBLI 2020.
- [ ] **Correggere il file research/visa/2026-05-28-e33g-kbli-content-creator-pivot.md** (sezione B.1): aggiornare data KBLI 2025 (18 dic 2025 + transizione 18 giu 2026), rimuovere 74149 come "2025", chiudere 73100 a 49%.
- [ ] **Carosello**: NON promettere "codice content creator dedicato gia registrabile su OSS". Messaggio corretto: KBLI 2025 (dic 2025) riconosce esplicitamente vlog/podcast/streaming, ma a maggio-giugno 2026 si registra via equivalenti KBLI 2020 con conversione automatica entro 18 giu 2026.
- [ ] **Verifica empirica oss.go.id** prima di depositare un'akta PT PMA content creator a giugno 2026: confermare quale set di codici (2020 o 2025) il sistema accetta in quel momento, e la % PMA effettiva di 59112/60390 vs 73100.
- [ ] **Scaricare Tabel Konversi KBLI 2020-2025** (bps.go.id news 897, 27 apr 2026) e mapparla sui codici creator per la consulenza cliente.
- [ ] **Script consulenza "apro PT PMA content creator a giugno 2026"**: akta con codici (notaio sceglie 2020 o 2025 secondo stato OSS al momento), spina dorsale 59112+60390+streaming, evitare 73100 (49%), conversione automatica sistema entro 18 giu 2026, nessuna perizinan nuova richiesta (assicurazione governo).

## Fonti per tier + prove di assenza

### Tier 1 — primary (letto direttamente)

- **Peraturan BPS No. 7 Tahun 2025 (KBLI 2025)** — PDF 623 pp, letto: header + Pasal 5/6/7 + codici 59112/60103/60203/60390/74191-74199/90113/90200 + prova assenza 74149. File: /tmp/kbli-2025.pdf, /tmp/kbli-2025-full.txt (da legalitas.org/download/kbli-2025-compressed.pdf)
- Permen Investasi/BKPM 5/2025 Pasal 393 (conversione automatica OSS) — verbatim via NB-3 source cc06b0a7
- Perpres 10/2021 jo 49/2021 jo 14/2024 (Daftar Positif Investasi, cap 73100 49%) — citato, Lampiran non parsato

### Tier 2 — official news / law firm

- BPS official: bps.go.id/en/news/2025/12/19/828 (rilascio 18 dic 2025) + bps.go.id/id/news/2026/04/27/897 (Tabel Konversi) + /898 (no perizinan baru)
- hukumonline "BPS Perbarui KBLI 2025" + ukmindonesia "KBLI 2025 Mulai Berlaku ... OSS" (transizione 18 giu 2026, coesistenza parallela)
- MUC "BPS Updates KBLI List to Include Content Creator Businesses" + Selaras Law Firm "KBLI 2025 Legal Implications" (18 dic 2025, transizione 6 mesi)
- smartlegal "8 Pembaruan KBLI 2025" (podcast/streaming/gaming codes), golaw, prolegal, izinkilat

### Tier 3 — consultant / aggregator

- veritask, legalitas.org (host del PDF), badanperizinannasional, izinlegalitas, bplawyers, infiniti.id, valprointertech, kbli2025.com
- agy Gemini 3.1 Pro (Bahasa recon) + DeepSeek V4 Pro (reasoning transizione) — convergenti su 18 dic 2025 + OSS-2020-oggi

### Prove di assenza (letto nel PDF primario)

- **74149 "Desain Konten Kreatif Lainnya" NON esiste nel KBLI 2025** (grep esaustivo 7414/74141/74142/74149/DESAIN KONTEN KREATIF -> solo 74194 Desain Konten Gim). Subgruppo 7419 = 74191/74192/74193/74194/74199.
- Nessun Peraturan BPS n. 9/10/11/12 del 2025 su KBLI (Gemini + WebSearch). L'unico atto KBLI 2025 e il 7/2025.
- Nessun "codice content creator dedicato 5-cifre singolo" — resta distribuito su 59112/60xxx/90xxx (DOCUMENTED dal PDF).
