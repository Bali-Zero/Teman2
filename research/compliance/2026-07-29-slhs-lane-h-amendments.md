---
date: 2026-07-29
domain: compliance
client_case: none-product-research
adversarial_review: codex
sources:
  - https://renbut.kemkes.go.id/regulasi/Permenkes%20Nomor%2011%20Tahun%202025%20%20tentang%20Standar%20Kegiatan%20Usaha%20dan%20Standar%20ProdukJasa%20pada%20Penyelenggaraan%20Perizinan%20Berusaha%20Berbasis%20Risiko%20Subsektor%20Kesehatan.pdf (official Kemkes source, fetched+pdftotext'd 2026-07-29, 540pp, HTTP 200, byte-identical to docs.paralegal.id mirror — cross-checked)
  - https://docs.paralegal.id/PERMEN/PERMENKES/2025/PERMENKES-11-2025.pdf (mirror, identical bytes to renbut.kemkes.go.id, fetched 2026-07-29)
  - https://peraturan.go.id/files/bn317-2022.pdf (Permenkes 8/2022 full text, Berita Negara No.317/2022, fetched+pdftotext'd 2026-07-29, HTTP 200)
  - https://farmalkes.kemkes.go.id/en/unduh/permenkes-17-2024/?wpdmdl=183097 (Permenkes 17/2024 full text, official Kemkes Ditjen Farmalkes download, fetched+pdftotext'd 2026-07-29, HTTP 200, 20658 lines extracted)
  - https://jdih.kemkes.go.id/storage/documents/pdfs/2026permenkes006.pdf (Permenkes 6/2026 "Rumah Sakit", fetched+pdftotext'd 2026-07-29, checked for SLHS relevance — ruled out, see §5)
  - WebSearch (Claude, 2026-07-29) — used only to LOCATE regulation numbers/URLs, never as the basis for a verbatim claim; every number-bearing claim below is re-verified against the primary PDFs above in this same turn
---

# SLHS — Lane H: gli emendamenti a Permenkes 14/2021, e la scoperta che rende la domanda incompleta

## Nota di metodo

Ogni citazione qui sotto è verbatim da un PDF scaricato ed estratto con `pdftotext -layout` **in questo
turno**, con numero di riga nel `.txt` estratto e numero di pagina del PDF ricostruito da conteggio dei
form-feed (`awk '/\f/'`). Nessun numero è preso da un riassunto AI di WebSearch senza controllo sul testo
primario. Dove una fonte secondaria (WebSearch summary) ha SUGGERITO una pista, questa è stata sempre
verificata scaricando e grepando il PDF ufficiale corrispondente prima di essere riportata come fatto.

**La domanda del mandato era "quali emendamenti a Permenkes 14/2021 sono sopravvissuti" — la risposta
corretta è che la domanda stessa è superata**: Permenkes 14/2021, INSIEME a entrambi i suoi emendamenti
(8/2022 e 17/2024), è stato **abrogato in blocco** il 3 ottobre 2025 da una **nuova regolazione madre**
(Permenkes 11/2025), non da una "Perubahan Ketiga" formale. Questo cambia la cornice della domanda: non
si tratta di verificare se D1/D4 sono "ancora quelli emendati", ma di stabilire quale regola VIGE oggi
(2026-07-29, ~10 mesi dopo l'abrogazione) — ed è una terza generazione di testo, con un elenco KBLI
diverso e (fatto sorprendente) **nessun numero di durata esplicito per la SLHS**.

---

## 1. La catena completa (risposta a Domanda 1)

| # | Norma | Tipo | Tocca l'angka 83 (SLHS)? | Stato oggi (2026-07-29) |
|---|---|---|---|---|
| 0 | Permenkes 14/2021 | base | sì (origine, angka 83) | **ABROGATA** (vedi #3) |
| 1 | Permenkes 8/2022 "Perubahan atas..." | 1° emendamento | **NO** | **ABROGATA** insieme alla base |
| 2 | Permenkes 17/2024 "Perubahan Kedua atas..." | 2° emendamento | **SÌ**, riscrive angka 83 per intero | **ABROGATA** insieme alla base |
| 3 | **Permenkes 11/2025** "Standar Kegiatan Usaha dan Standar Produk/Jasa ... Subsektor Kesehatan" | **sostituzione integrale**, non un emendamento a 14/2021 | sì — angka SLHS ricompare come sezione F.1 | **VIGENTE**, ditetapkan 3 ottobre 2025, berlaku dalla stessa data |

Non è stata trovata nessuna "Perubahan Ketiga" formale a Permenkes 14/2021 — la ricerca (WebSearch mirata
su varianti "perubahan ketiga", "2025", "2026") non ha restituito nulla con quel titolo. Trovata invece,
verificata su testo primario, l'abrogazione integrale via Permenkes 11/2025, che è una regolazione NUOVA
(nuovo numero di Pasal-scheme, nuovo titolo — nota: "Sektor Kesehatan" nella vecchia serie diventa
**"Subsektor Kesehatan"** nella nuova, e il fondamento normativo cambia da PP 5/2021 a **PP 28/2025**).

**Clausola di abrogazione, verbatim** (Permenkes 11/2025, Pasal 39, righe 1170-1205 del `.txt` estratto,
a cavallo delle pagine PDF **21-22**). **Nota di precisione (post-review)**: la clausola non è un'abrogazione
assoluta di 14/2021+8/2022+17/2024 — ciascuna delle tre norme è abrogata **"sepanjang mengatur mengenai
standar kegiatan usaha dan/atau produk/jasa pada PB dan PB UMKU subsektor kesehatan yang diatur dalam
Peraturan Menteri ini"** (= nella misura in cui disciplina materie ora coperte da questo nuovo Permenkes).
Poiché Permenkes 11/2025 copre esplicitamente anche la sezione SLHS (§F.1, vedi sotto), l'effetto pratico
su SLHS è comunque un'abrogazione piena — ma la formula giuridica è "abrogazione per sovrapposizione di
materia", non un "dicabut" secco e incondizionato su TUTTO il contenuto delle tre norme precedenti:

> "Pada saat Peraturan Menteri ini mulai berlaku: [...] b. Peraturan Menteri Kesehatan Nomor 14 Tahun 2021
> tentang Standar Kegiatan Usaha dan Produk pada Penyelenggaraan Perizinan Berusaha Berbasis Risiko Sektor
> Kesehatan (Berita Negara Republik Indonesia Tahun 2021 Nomor 316) sepanjang mengatur mengenai standar
> kegiatan usaha dan/atau produk/jasa pada PB dan PB UMKU subsektor kesehatan yang diatur dalam Peraturan
> Menteri ini; c. Peraturan Menteri Kesehatan Nomor 8 Tahun 2022 tentang Perubahan atas Peraturan Menteri
> Kesehatan Nomor 14 Tahun 2021 [...] (Berita Negara Republik Indonesia Tahun 2022 Nomor 317) sepanjang
> mengatur mengenai standar kegiatan usaha dan/atau produk/jasa pada PB dan PB UMKU subsektor kesehatan
> yang diatur dalam Peraturan Menteri ini; dan d. Peraturan Menteri Kesehatan Nomor 17 Tahun 2024 tentang
> Perubahan Kedua atas Peraturan Menteri Kesehatan Nomor 14 Tahun 2021 [...] (Berita Negara Republik
> Indonesia Tahun 2024 Nomor 839) sepanjang mengatur mengenai standar kegiatan usaha dan/atau produk/jasa
> pada PB dan PB UMKU subsektor kesehatan yang diatur dalam Peraturan Menteri ini, **dicabut dan
> dinyatakan tidak berlaku**."

Colophon (righe 1218-1219, pagina PDF 23): "Ditetapkan di Jakarta pada tanggal **3 Oktober 2025**",
firmato Budi G. Sadikin. Pasal 40 (riga 1208): "Peraturan Menteri ini mulai berlaku pada tanggal
diundangkan" — cioè efficace dalla stessa data di promulgazione (la data di *diundangkan* nel colophon è
illeggibile nell'estrazione OCR/testo del PDF per un glifo corrotto, ma è corroborata come "3 Ottobre
2025, efficace la stessa data" da una sintesi WebSearch indipendente di jdih.kemkes.go.id — marcata
**[fonte secondaria per la sola data di *diundangkan*]**, non per l'abrogazione, che è verbatim primario).

**Nota residua (rilevante per operatività, non per D1/D4)**: la clausola transitoria Pasal 37 (riga
1146-1157) mantiene sotto il VECCHIO regime (14/2021 come modificato da 17/2024) le pratiche "masih dalam
proses permohonan, belum terverifikasi, atau belum berlaku efektif" finché il Sistema OSS non si adegua a
PP 28/2025 — quindi per un cliente con SLHS già in corso di richiesta, la base legale applicabile potrebbe
ancora essere la vecchia, a seconda dello stato del Sistema OSS (non verificabile da qui: richiede
controllo sul sistema OSS-RBA stesso, fuori scope di questo lane).

---

## 2. Domanda 2 — la validità di 3 anni

### 2a. Permenkes 8/2022 — non tocca SLHS

Il testo integrale di Permenkes 8/2022 (5 pagine + Pasal I/II + 1 solo lampiran) è stato scaricato e
grepato per intero. **Zero occorrenze** di "higiene sanitasi" o "SLHS" in tutto il documento
(`grep -n -i "higiene sanitasi\|SLHS" permenkes8-2022.txt` → nessun risultato). Il "Menimbang" dichiara
esplicitamente il proprio oggetto: "standar penyelenggaraan aktivitas pelayanan dialisis [...] perlu
disesuaikan" — l'unico punto modificato è **angka 82** (Standar Penetapan Aktivitas Penyelenggaraan
Pelayanan Dialisis), un servizio sanitario di dialisi, argomento estraneo a SLHS/angka 83. Confermato:
**Permenkes 8/2022 non tocca D1 né D4.**

### 2b. Permenkes 17/2024 — riscrive angka 83, MA conferma 3 anni verbatim

Permenkes 17/2024 elenca esplicitamente i 9 punti (angka) modificati in Pasal I (righe 129-150):

> "8. Angka 83. Standar Sertifikat Laik Higiene Sanitasi; dan"

è l'ottavo dei nove (riga 148). Nel lampiran riscritto (angka 83, riga 12097, pagina PDF **152**):

> "83. STANDAR SERTIFIKAT LAIK HIGIENE SANITASI"

seguito, riga 12340, dalla clausola di durata:

> "b. **Masa berlaku SLHS adalah 3 (tiga) tahun.**"

E nel template del certificato stesso (righe 17385-17386, pagina PDF 214):

> "Sertifikat Laik Higiene Sanitasi ........ berlaku selama 3 (tiga) [tahun ...]"

**Verdetto parziale**: attraverso ENTRAMBI gli emendamenti (8/2022 e 17/2024), la validità di **3 anni è
rimasta testualmente identica** a quella della base 14/2021 — 17/2024 ha riscritto l'intera sezione angka
83 (nuovo formato, nuove clausole procedurali: es. "Pemenuhan persyaratan SLHS 1 (satu) tahun sejak NIB",
persyaratan perpanjangan ecc.) ma **senza cambiare il numero di anni**.

### 2c. Permenkes 11/2025 (il regime VIGENTE oggi) — il numero sparisce

Qui il quadro cambia. Nella sezione SLHS di Permenkes 11/2025 (righe 28210-28742, "F. PERIZINAN
BERUSAHA UNTUK MENUNJANG KEGIATAN USAHA (PB UMKU) BIDANG KESEHATAN LINGKUNGAN — 1. SERTIFIKAT LAIK
HIGIENE SANITASI", pagine PDF **512-522**), è stata cercata sistematicamente la stringa di durata:

- `grep -n "(tiga) tahun"` sull'INTERO documento (540 pagine): **2 occorrenze**, entrambe fuori dalla
  sezione SLHS (righe 10961, 19692 — riguardano periodi di conservazione documenti bancari/altro).
- `grep -n "(lima) tahun"`: **7 occorrenze** (righe 22945, 22947, 23023, 23158, 23159, 23498, 25773),
  tutte fuori dalla sezione SLHS — la maggior parte riguarda Izin Edar alat kesehatan (righe 22945-23498),
  l'ultima (25773) è in una sezione successiva estranea a SLHS.
- Dentro la sezione SLHS stessa (righe 28210-28742), la sola menzione di durata è procedurale, non
  numerica: "Permohonan perpanjangan PB UMKU SLHS diajukan **paling lambat 3 (tiga) bulan sebelum** masa
  berlaku PB UMKU SLHS berakhir" (riga 28632-28633, pagina PDF 519) — dice QUANDO rinnovare (3 mesi
  prima della scadenza), **non quanto dura** la SLHS.
- Cercato anche a livello di articolato generale (Bab VI/VII, righe 1-1210): nessuna clausola generica di
  durata per tutti i PB UMKU; l'unico riferimento a "masa berlaku" nel corpo dell'articolato (riga 622) è
  un obbligo di REPORTING ("kewajiban [...] meliputi persyaratan, jangka waktu penerbitan, kewajiban, dan
  masa berlaku" — il pelaku usaha deve riportare la propria scadenza, non che la norma la fissi qui).

**Verdetto**: nel testo di Permenkes 11/2025, **non è stato trovato alcun numero di anni per la validità
della SLHS** — né nella sezione dedicata (angka F.1) né altrove nel documento di 540 pagine. Questo NON
significa che la SLHS non abbia scadenza (la sezione presuppone esplicitamente che ne abbia una, dato che
regola il "3 mesi prima" del rinnovo) — significa che **il numero non è (più) fissato nel testo del
Permenkes stesso**, diversamente da 14/2021 e 17/2024 dove compariva verbatim. Corroborato indirettamente
da una ricerca web sullo stato 2026 del pubblico generale: le fonti secondarie sul tema oggi si contraddicono
("3-5 anni" vs "1 anno"), sintomo compatibile con l'assenza di un numero fisso nella norma corrente
(**[NON VERIFICATO]** come SPIEGAZIONE della confusione — la confusione stessa è solo un'osservazione di
contesto, non una prova).

---

## 3. Domanda 3 — l'elenco dei sei KBLI

### 3a. Attraverso gli emendamenti (fino al 17/2024): invariato

L'elenco KBLI nella sezione angka 83 riscritta da Permenkes 17/2024 (righe 12098-12104, pagina PDF 152)
è, verbatim:

> "KBLI 56101 Restoran / KBLI 56290 Penyediaan Jasa Boga Periode Tertentu / KBLI 56210 Jasa Boga Untuk
> Suatu Event Tertentu (Event Catering) / KBLI 10391 Industri Tempe Kedelai / KBLI 10392 Industri Tahu
> Kedelai / KBLI 11052 Industri Air Minum Isi Ulang (Depot Air Minum)"

**Identico** ai sei codici estratti dalla lane precedente dalla base 14/2021 (stessi 6 codici, stesso
ordine sostanziale). **Permenkes 17/2024 riscrive l'intera struttura della sezione ma NON tocca l'elenco
KBLI.** Permenkes 8/2022 non tocca affatto angka 83 (v. §2a) quindi è irrilevante qui.

### 3b. Permenkes 11/2025 (il regime VIGENTE): elenco CAMBIATO — 7 codici, non 6

Nella sezione F.1 di Permenkes 11/2025 (righe 28212-28215, pagina PDF 512, subito sotto l'intestazione
"KBLI:" a riga 28211), l'elenco KBLI legato allo standard SLHS è, verbatim:

> "KBLI: (56101) Restoran; (56210) Jasa Boga untuk Suatu Event Tertentu (Event Catering); (56290)
> Penyediaan Jasa Boga Periode Tertentu; (56103) Kedai Makanan; (56303) Rumah Minum/Kafe; (68120) Kawasan
> Pariwisata; (11052) Industri Air Minum Isi Ulang (Depot Air Minum)"

Confronto diretto con l'elenco base/17-2024 (6 codici) → elenco 11/2025 (7 codici):

| Codice | Etichetta | Base 14/2021 + 17/2024 | Permenkes 11/2025 |
|---|---|---|---|
| 56101 | Restoran | ✅ | ✅ |
| 56290 | Penyediaan Jasa Boga Periode Tertentu | ✅ | ✅ |
| 56210 | Jasa Boga Untuk Suatu Event Tertentu | ✅ | ✅ |
| 11052 | Industri Air Minum Isi Ulang (Depot Air Minum) | ✅ | ✅ |
| 10391 | Industri Tempe Kedelai | ✅ | ❌ **RIMOSSO** |
| 10392 | Industri Tahu Kedelai | ✅ | ❌ **RIMOSSO** |
| 56103 | Kedai Makanan | ❌ | ✅ **AGGIUNTO** |
| 56303 | Rumah Minum/Kafe | ❌ | ✅ **AGGIUNTO** |
| 68120 | Kawasan Pariwisata | ❌ | ✅ **AGGIUNTO** |

Il testo della norma stessa spiega esplicitamente il perché dell'aggiunta di Kedai Makanan/Rumah Minum-Kafe
(righe 28330-28336, pagina PDF 514): "TPP sebagaimana dimaksud yang wajib SLHS antara lain Restoran, Jasa
Boga Untuk Suatu Event Tertentu, Usaha Penyediaan Jasa Boga Periode Tertentu, **Kedai Makanan, dan Rumah
Minum/Kafe termasuk yang berada di kawasan pariwisata**, serta DAM" — cioè l'ambito soggettivo dell'obbligo
SLHS si è ESTESO ai piccoli esercizi (kedai/kafe) e alle zone turistiche, mentre le due industrie alimentari
non-di-servizio (tempe/tahu) sono uscite dall'ambito SLHS in questa sezione. **Correzione dopo verifica
puntuale** (l'unica altra occorrenza di 10391/10392 in tutto il documento di 540 pagine, riga 29356): i due
codici NON sono spariti dal framework "Kesehatan Lingkungan" — sono stati **retrocessi da SLHS (certificato
pieno) al livello più leggero "3. LABEL HIGIENE SANITASI PANGAN (HSP)"** (riga 29348, pagina PDF 533),
il cui elenco KBLI (riga 29349-29356) include tempe/tahu insieme a una lista molto più ampia (Rumah/Warung
Makan, Kedai Minuman, Produksi Es, ecc.). Non è quindi un'uscita dalla vigilanza igienico-sanitaria, ma un
cambio di tier di certificazione — coerente con la struttura a 3 livelli (SLHS piena / Label HSP più leggero
/ SLS) già documentata dalla lane-A di questo stesso sprint per il regime 14/2021.

**Verdetto**: **l'elenco dei 6 KBLI NON è più quello vigente**. Sotto il regime attualmente in vigore
(Permenkes 11/2025, dal 2025-10-03), l'elenco è di **7 codici**, con 2 rimozioni (10391, 10392) e 3
aggiunte (56103, 56303, 68120) rispetto all'elenco base che la lane precedente ha estratto e verificato.

---

## 4. Domanda 4 — la pista "IKL / semplificazione formulario" — **CONFERMATA, dopo una prima ricerca fallita**

**Correzione di metodo**: la prima stesura di questa sezione dichiarava "zero occorrenze verbatim" di "IKL"
in Permenkes 17/2024, basandosi su un singolo comando grep con alternanza (`\bIKL\b\|Instrumen\|...`) che
non ha prodotto match nonostante il termine sia presente **29 volte** nel documento. Il grep-review
adversariale (seat `codex`, §Adversarial review sotto) ha ripetuto la ricerca in modo indipendente e ha
trovato l'errore. Rieseguito qui `grep -n -i "IKL" permenkes17-2024.txt` (esclusi i falsi positivi
"poliklinik"): **29 occorrenze reali**, a partire da riga 12327.

**IKL = "Inspeksi Kesehatan Lingkungan" (Ispezione di Sanità Ambientale)**, definita esplicitamente
verbatim a riga 12326-12327, pagina PDF 152, all'interno della stessa sezione angka 83 (SLHS):

> "p. Inspeksi Kesehatan Lingkungan yang selanjutnya disingkat IKL adalah kegiatan pemeriksaan dan
> pengamatan secara langsung terhadap media lingkungan dalam rangka pengawasan berdasarkan standar,
> norma, dan baku mutu yang berlaku untuk meningkatkan kualitas lingkungan yang sehat."

L'IKL è il meccanismo di verifica materiale sia per il **rilascio** che per la **vigilanza periodica**
della SLHS:

- **Rilascio** (riga 12757-12760, pagina PDF ~160): "dinas kesehatan/tim teknis terkait melakukan
  verifikasi IKL ke TPP. **IKL memenuhi syarat apabila mendapatkan nilai minimal 80**" — soglia numerica
  esplicita (punteggio minimo 80) per il superamento dell'ispezione.
- **Vigilanza periodica** (righe 12751-12809, pagina PDF ~161): "Penyelenggaraan pengawasan dilakukan
  dengan Inspeksi Kesehatan Lingkungan (IKL). a) IKL dilakukan oleh sanitarian/petugas kesehatan
  lingkungan **menggunakan form IKL sesuai TPP**. b) IKL dilakukan secara berkala [...] e) **Penetapan
  frekuensi pengawasan berdasarkan kategori risiko TPP**" — il formulario è specifico per tipo di TPP (si
  trovano infatti moduli nominati come "Form IKL JASA BOGA/KATERING", riga 12890, e "Form IKL Rumah
  Makan", riga 17976) e la frequenza dei controlli è calibrata sulla **categoria di rischio** del TPP —
  esattamente i due elementi ("formulario" e "indicatori di rischio") che la fonte secondaria del mandato
  attribuiva a questo emendamento.
- **Reportistica**: tra i dati che vanno riportati nel sistema e-monev c'è esplicitamente "Data hasil
  IKL" (riga 12866).

**IKL non è né nuovo né rimosso — attraversa anche Permenkes 11/2025 (il regime vigente oggi)**: lo stesso
concetto, con la stessa soglia numerica, ricompare nella sezione SLHS del testo attualmente in vigore
(`grep -niw "IKL" permenkes11-2025.txt` → 20 occorrenze). Riga 28507-28509, pagina PDF ~518: "Hasil IKL
yang menunjukkan TPP memenuhi [...] dengan nilai minimal 80" — **la soglia 80 è sopravvissuta intatta**
dal 2024 al regime 2025. Riga 28785: "disingkat IKL adalah kegiatan pengamatan dan..." (definizione
ripetuta, questa volta anche nella sezione SLS). Riga 29165: "IKL memuat indikator persyaratan kesehatan"
— uso esplicito del termine "indikator" accanto a IKL, ulteriore corroborazione lessicale della
descrizione della fonte secondaria.

**Verdetto (corretto)**: la pista "IKL — formulario e indicatori di rischio" **È CONFERMATA** dal testo
primario, con dettaglio molto più preciso di quanto suggerito dalla fonte secondaria: IKL è il meccanismo
di ispezione materiale (soglia 80/100) sia per il rilascio sia per la vigilanza periodica della SLHS, con
formulario differenziato per tipo di TPP e frequenza calibrata sulla categoria di rischio. **Non è
verificabile da qui, per assenza del testo base 14/2021 in questo lane, se l'apparato IKL sia stato
INTRODOTTO da 17/2024 o solo riformulato** — ma è verificato con certezza che è **presente e sostanziale**
in 17/2024 e **sopravvive, soglia numerica inclusa, nel regime oggi vigente** (Permenkes 11/2025).

---

## 5. Diligence aggiuntiva — nessuna norma più recente trovata

Cercato esplicitamente un ulteriore emendamento a Permenkes 11/2025 (oggi 2026-07-29, quasi 10 mesi dopo
la sua entrata in vigore). Trovato **Permenkes 6/2026** ("Rumah Sakit", jdih.kemkes.go.id, scaricato e
grepato) — cita Permenkes 11/2025 **una sola volta** (riga 74, come riferimento normativo "Mengingat", non
come oggetto di modifica) ed è per soggetto **completamente estraneo** (ospedali, non standard PB UMKU
kesehatan lingkungan/SLHS). **Escluso** come rilevante per D1/D4. Nessun'altra norma più recente di
11/2025 toccante SLHS è emersa dalle ricerche svolte.

---

## Adversarial review

**Seat**: `codex` (GPT-5.6 family, famiglia diversa dall'autore Claude Sonnet 5) — dispatchato via
`mcp__codex-redteam__codex` in sandbox read-only, puntato sugli STESSI file PDF/txt scaricati in questo
turno (`/private/tmp/claude-501/-Users-balizero-nuzantara/31e6e197-05e2-46f8-925c-59881818e7a7/scratchpad/slhs-lane-h/`),
con l'istruzione di ri-grepare indipendentemente ogni citazione verbatim del primo draft e segnalare
qualunque numero di riga, numero di pagina o stringa che non corrisponda esattamente al PDF sorgente, ed
essere adversariale (cercare attivamente un controesempio) sulla claim più consequenziale — l'assenza di
una durata numerica fissa per SLHS in Permenkes 11/2025.

**Esito, round 1 (sul primo draft)**: 3 claim su 7 PASS senza riserve, 4 FAIL. Il più grave: la claim §4
("IKL non compare mai in 17/2024") era **sostanzialmente falsa** — 29 occorrenze reali, il mio grep
originale con alternanza `\b...\|...\|...` non le aveva trovate. Gli altri 3 FAIL erano difetti di
citazione (numero di riga/pagina impreciso, non un fatto sbagliato): la clausola di revoca §1 attraversa
pp.21-22 non solo p.22 ed è qualificata da "sepanjang mengatur..." (non un'abrogazione assoluta e
incondizionata); l'intervallo pagine §2c era 512-522 non 512-518 e uno dei 7 match "(lima) tahun" cadeva
fuori dal range dichiarato; in §3b l'elenco KBLI era a righe 28212-28215 non 28211 e la frase sui TPP
obbligati era a righe 28330-28336/p.514 non 28270-28280/p.512. La claim più importante e più a rischio —
**nessuna durata numerica fissa per SLHS in tutto il testo di Permenkes 11/2025** — ha **retto** al
tentativo adversariale di trovare un controesempio (verdetto esplicito di Codex: "la conclusione più
importante [...] regge alla ricerca avversariale").

**Correzioni applicate**: tutte le 4 discrepanze sono state corrette nel corpo di questo file (§1, §2b,
§2c, §3b — numeri di riga/pagina rettificati, formulazione della revoca qualificata) e §4 è stata
**riscritta integralmente** con la ricerca IKL corretta, il testo verbatim della definizione, la soglia
numerica (nilai minimal 80) e la conferma che il meccanismo sopravvive nel regime 11/2025 vigente. Nessuna
seconda ripassata adversariale è stata eseguita sul testo corretto per limiti di tempo del lane — le
citazioni riparate sono state verificate a mano con `sed -n` sugli stessi file in questo turno (vedi
comandi sopra in §3b), non solo asserite.

---

## Verdetto finale

- `VALIDITÀ 3 ANNI: MODIFICATA — non più fissata in termini numerici nel regime vigente (Permenkes 11/2025, dal 2025-10-03; era ancora "3 (tiga) tahun" verbatim sotto 14/2021 e attraverso entrambi gli emendamenti 8/2022 e 17/2024, che non l'hanno mai toccata prima dell'abrogazione)`
- `ELENCO 6 KBLI: MODIFICATO — nel regime vigente (Permenkes 11/2025) sono 7 codici: +56103 Kedai Makanan, +56303 Rumah Minum/Kafe, +68120 Kawasan Pariwisata; -10391 Industri Tempe Kedelai e -10392 Industri Tahu Kedelai (retrocessi al livello più leggero "Label Higiene Sanitasi Pangan", non usciti dalla vigilanza igienico-sanitaria). L'elenco era rimasto INVARIATO attraverso 8/2022 e 17/2024 fino all'abrogazione del 2025-10-03.`
