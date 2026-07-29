---
date: 2026-07-29
domain: compliance
client_case: none-product-research
sources:
  - https://jdih.kemenkoinfra.go.id/cfind/source/files/pp/2024/pp-nomor-28-tahun-2024.pdf (PP 28/2024 full text, fetched+pdftotext'd 2026-07-29)
  - https://peraturan.bpk.go.id/Details/245563/permenkes-no-2-tahun-2023 (fetched 2026-07-29)
  - https://jdih.kemkes.go.id/documents/peraturan-menteri-kesehatan-nomor-2-tahun-2023 (fetched 2026-07-29)
  - https://www.kompasiana.com/handokosemarang2803/640aa09c4addee1b5b376e22/permenkes-no-2-th-2023-mencabut-6-kepmenkes-dan-11-permenkes?page=all (secondary, fetched 2026-07-29)
  - https://farmalkes.kemkes.go.id/en/unduh/permenkes-17-2024/ (fetched 2026-07-29)
  - https://dinkes.batam.go.id/wp-content/uploads/sites/35/2024/04/2.-SYARAT-IKL-RESTORAN-56101_2024.pdf (official Dinkes checklist, PDF text-extracted 2026-07-29 — usa numerazione KBLI 2020)
  - https://www.dpmptsp.purwakartakab.go.id/storage/assets/docs/85d11e0cdcedd92a60cde742b9e5b6c2.pdf (official DPMPTSP SOP doc, PDF text-extracted 2026-07-29 — idem, KBLI 2020)
  - https://dpmptsp.gowakab.go.id/berita/memahami-perbedaan-sertifikat-laik-higiene-sanitasi-dan-sertifikat-laik-sehat (secondary/gov blog, fetched 2026-07-29)
  - https://dinkes.jogjaprov.go.id/berita/detail/e-monev-hsp-pengoperasian-emonev-hsp-online-berbasis-web-dinas-kesehatan-kabkota-2019 (secondary/gov, search-summarized 2026-07-29)
  - https://www.hukumonline.com/berita/a/uu-kesehatan-resmi-terbit--11-uu-ini-dinyatakan-tak-berlaku-lt64d31b2e3e3eb/ (secondary legal news, search-summarized 2026-07-29, NOT primary-text verified)
  - apps/backend-rag/backend/kb/ and apps/backend-rag/data/curated_qa/ (internal KB, grepped 2026-07-29 — zero hits on "higiene|SLHS|sanitasi|laik sehat|jasaboga|tempat pengelolaan pangan")
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (Bali Zero authoritative KBLI dataset, 1559 codes, field kode_kbli_2025 + bps_2020_ancestors; queried directly with python3/json 2026-07-29 — see §4)
---

# SLHS (Sertifikat Laik Higiene Sanitasi) — Anatomia regolamentare, Indonesia 2026

> ⛔ **CORREZIONE APPOSTA DOPO LA STESURA (2026-07-29) — NON CITARE I CODICI KBLI DI QUESTO FILE.**
> Questo dossier è affidabile sulla STRUTTURA (catena normativa, i tre livelli di certificato,
> SLHS vs SLS) e inaffidabile sui NUMERI DI CODICE: le sue liste KBLI sono state sbagliate due
> volte, e cita fra gli altri 56103 e 56104, che **non esistono in KBLI 2025**. L'arbitro unico è
> `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (campo `kode_kbli_2025`).
>
> Inoltre l'intero file ragiona su **Permenkes 14/2021**, che dal **2025-10-03** è revocato da
> **Permenkes 11/2025** per la parte PB-UMKU subsektor kesehatan — cioè esattamente l'SLHS. Vedi
> `2026-07-29-slhs-lane-h-amendments.md` e la §2 di `.claude/skills/slhs/SKILL.md`. Tenuto in
> archivio perché la sua ricostruzione strutturale resta utile e perché l'errore è istruttivo:
> tre famiglie di LLM hanno prodotto tre liste KBLI diverse e tutte sicure di sé.

## Nota di metodo

Nessuna norma citata qui è stata inventata. Ogni volta che una WebSearch AI-summary è stata l'unica fonte (senza verifica su testo primario in questo turno), è marcata **[NON VERIFICATO]** o **PROBABILE**. Il cuore duro del lane — la catena PP 66/2014 → PP 28/2024, e l'elenco delle 17 norme abrogate da Permenkes 2/2023 — è stato verificato su **testo primario scaricato ed estratto con `pdftotext`** (non riassunto AI di terzi), citato verbatim con numero di Pasal. La KB curata del progetto (`apps/backend-rag/backend/kb/`, `apps/backend-rag/data/curated_qa/`) è stata grepata per "higiene|SLHS|sanitasi|laik sehat|jasaboga|tempat pengelolaan pangan": **zero risultati** — il dominio SLHS non è ancora coperto dalla KB curata di Bali Zero.

**Revisione 2026-07-29 (post-review team-lead)**: §4 riscritta da zero dopo che una prima versione (basata su documenti Dinkes 2024 in numerazione KBLI 2020, senza incrocio col dataset KBLI 2025 autoritativo del progetto) è risultata contenere codici KBLI inesistenti nel 2025, marcati erroneamente CERTO. La causa non era invenzione ma vintage-confusion (KBLI 2020 vs 2025) non dichiarata. Corretto qui interrogando direttamente `data/source_documents/KBLI_2025_FINAL_CLEAN.json` con le mie mani (non fidandomi né della prima bozza né, acriticamente, della correzione ricevuta — vedi nota su un'affermazione del team-lead risultata anch'essa imprecisa, in fondo a §4).

---

## 1. Definizione

**SLHS = Sertifikat Laik Higiene Sanitasi.** È un certificato/sertifikat standar rilasciato dal Dinas Kesehatan Kabupaten/Kota (operativizzato via DPMPTSP nel sistema OSS-RBA) che attesta che un esercizio di somministrazione/lavorazione alimenti ha soddisfatto gli standard di igiene e sanitazione. Non è un "izin usaha" autonomo: è una **persyaratan/PB-UMKU (Perizinan Berusaha Untuk Menunjang Kegiatan Usaha) non-KBLI**, agganciata al NIB emesso via OSS, con verifica del Dinkes e finalizzazione DPMPTSP. **PROBABILE** sulla formulazione esatta della definizione Kemkes (fonte: riassunto search-AI di una pagina Kemkes, non verificata verbatim su testo primario in questo turno) — CERTO sulla natura giuridica "persyaratan/PB-UMKU, non KBLI stand-alone" (confermato da 3 documenti ufficiali Dinkes/DPMPTSP indipendenti: Batam, Purwakarta, ricerca OSS-RBA generale).

## 2. Catena normativa (tabella)

| Norma | Anno | Oggetto | Stato 2026 | Fonte |
|---|---|---|---|---|
| UU 36/2009 tentang Kesehatan | 2009 | Legge quadro sanità (precedente) | **ABROGATA** dall'UU 17/2023, Pasal 454 (11 leggi abrogate in blocco) | hukumonline.com (secondario) — **PROBABILE**, non verificato su testo primario UU 17/2023 in questo turno (2 tentativi di fetch diretto su peraturan.go.id e peraturan.bpk.go.id sono falliti con HTTP 500/403) |
| UU 17/2023 tentang Kesehatan | 2023 | Legge omnibus sanità | **VIGENTE** | titolo confermato via ricerca su peraturan.bpk.go.id |
| PP 66/2014 tentang Kesehatan Lingkungan | 2014 | Regolamento attuativo salute ambientale (fondamento storico dell'intero impianto SLHS) | **ABROGATA ESPLICITAMENTE** — CERTO, verbatim | PP 28/2024, Pasal 1170 huruf q: elenco di norme "**dicabut dan dinyatakan tidak berlaku**" include testualmente "Peraturan Pemerintah Nomor 66 Tahun 2Ol4 tentang Kesehatan Lingkungan" |
| PP 28/2024 tentang Peraturan Pelaksanaan UU 17/2023 tentang Kesehatan | 2024 | Regolamento attuativo generale della nuova legge sanità, include ora un capitolo proprio "Kesehatan Lingkungan" (Bagian Ketiga Belas, Pasal 245-253) | **VIGENTE** — ditetapkan/diundangkan **26 Juli 2024**, Lembaran Negara 2024 No.135, Pasal 1172: "mulai berlaku pada tanggal diundangkan" | testo primario, verbatim (Pasal 1172, colophon) |
| Permenkes 14/2021 tentang Standar Kegiatan Usaha dan Produk pada Penyelenggaraan Perizinan Berusaha Berbasis Risiko Sektor Kesehatan | 2021 | Contiene il lampiran tecnico "Standar SLHS TPP" usato per l'aggancio KBLI→SLHS in OSS-RBA | **VIGENTE**, come modificato (vedi 17/2024) | citato esplicitamente come base legale in 2 documenti ufficiali Dinkes/DPMPTSP 2024 (Batam, Purwakarta) |
| Permenkes 2/2023 tentang Peraturan Pelaksanaan PP 66/2014 tentang Kesehatan Lingkungan | 2023 | Regolamento attuativo di PP 66/2014; **abroga in blocco 6 Kepmenkes + 11 Permenkes** (17 norme totali) sui vecchi settoriali igiene/sanitazione, incl. le 4 chieste dal team | **STATO AMBIGUO/APERTO** — il suo fondamento (PP 66/2014) è stato abrogato da PP 28/2024, MA PP 28/2024 Pasal 1169 salva esplicitamente ("**dinyatakan masih tetap berlaku sepanjang tidak bertentangan dengan ketentuan dalam Peraturan Pemerintah ini**") le norme attuative delle PP elencate (incl. PP 66/2014, stessa lettera q) — quindi Permenkes 2/2023 **resta operativo per clausola transitoria** finché Kemkes non emette un nuovo Permenkes sotto il capitolo Kesehatan Lingkungan di PP 28/2024. CERTO sul meccanismo giuridico (testo primario); PROBABILE sulla conclusione pratica di continuità (nessun Permenkes sostitutivo trovato) — vedi §9 | testo primario PP 28/2024 Pasal 1169+1170 + peraturan.bpk.go.id (Permenkes 2/2023: ditetapkan 4 Gen 2023, diundangkan 12 Gen 2023) |
| Kepmenkes 1096/Menkes/PER/VI/2011 (Pedoman Higiene Sanitasi Jasaboga) | 2011 | Vecchio regolamento settoriale jasaboga | **ABROGATA** da Permenkes 2/2023 (voce 12 di 17 nell'elenco abrogazioni) | kompasiana.com (elenco secondario) — corroborato da 2 riassunti WebSearch indipendenti; contenuto NON verificato su testo primario Permenkes 2/2023 in questo turno |
| Kepmenkes 1098/Menkes/SK/VII/2003 (Persyaratan Higiene Sanitasi Rumah Makan dan Restoran) | 2003 | Vecchio regolamento settoriale RM/restoran | **ABROGATA** da Permenkes 2/2023 (voce 5 di 17) | idem |
| Permenkes 43/2014 (Higiene Sanitasi Depot Air Minum) | 2014 | Vecchio regolamento settoriale DAM | **ABROGATA** da Permenkes 2/2023 (voce 14 di 17) | idem |
| Kepmenkes 942/Menkes/SK/VII/2003 (makanan jajanan) | 2003 | Vecchio regolamento settoriale street food | **ABROGATA** da Permenkes 2/2023 (voce 4 di 17) | idem |
| Permenkes 17/2024 (Perubahan Kedua atas Permenkes 14/2021) | 2024 | **Seconda modifica** a Permenkes 14/2021 | **VIGENTE** | farmalkes.kemkes.go.id — titolo ufficiale confermato: "**Peraturan Menteri Kesehatan Nomor 17 Tahun 2024 tentang Perubahan Kedua Atas Peraturan Menteri Kesehatan Nomor 14 Tahun 2021 Tentang Standar Kegiatan Usaha Dan Produk Pada Penyelenggaraan Perizinan Berusaha Berbasis Risiko Sektor Kesehatan**". **CORREZIONE a una fonte secondaria**: legalitas.org (blog konsultan) lo cita erroneamente come "Permenkes 17/2024 tentang Higiene Sanitasi Jasa Boga" — è FALSO, è un emendamento generale a 14/2021, non una norma dedicata jasaboga; scartato come lead non confermato |

## 3. Mappa TPP → certificato

Fonte primaria per questa sezione: documento ufficiale Dinas Kesehatan Batam 2024 ("DAFTAR KBLI KESLING BERDASARKAN PERMENKES NO. 14 TAHUN 2021"), incrociato con il documento ufficiale DPMPTSP Purwakarta (SOP servizio SLHS). **Attenzione vintage**: entrambi i documenti, pur datati 2024, esprimono i codici in numerazione **KBLI 2020**, non KBLI 2025 (vedi correzione in §4). Il framework NON usa il termine "Tempat Pengelolaan Pangan (TPP)" come categoria di legge in PP 28/2024 (0 occorrenze nel testo primario grepato) — TPP è terminologia operativa/tecnica del lampiran Permenkes 14/2021 e della prassi Dinkes, non un termine definito a livello di PP.

Esistono **3 livelli distinti di certificazione**, NON un unico "SLHS per tutto il food" (livelli confermati dal documento Batam; i codici KBLI citati qui sono **KBLI 2020** — la traduzione in KBLI 2025 è in §4, e resta NON verificata per il punto specifico "quale codice fa scattare l'obbligo SLHS"):

1. **SLHS piena** (Sertifikat Laik Higiene Sanitasi) — per: Restoran, Penyediaan Jasa Boga Periode Tertentu, Jasa Boga Event Catering, Industri Tahu Kedelai/Tempe Kedelai, Depot Air Minum.
2. **"Label Pengawasan/Pembinaan" (Higiene Sanitasi Pangan)** — livello PIÙ LEGGERO, esplicitamente distinto da SLHS nello stesso documento ufficiale — per: Rumah/Warung Makan gol. A1/gol. A2, Kedai Makanan, gerai pangan keliling gol. A1/A2/B, Restoran e Penyediaan Makanan Keliling Lainnya/gerai jajanan/kantin/sentra pangan jajanan.
3. **SLS (Sertifikat Laik Sehat)** — certificato DIVERSO da SLHS, per strutture non-food-primarie: accomodazione (hotel bintang/melati, vila, pondok wisata, bumi perkemahan, ecc.), tempat hiburan con cibo/bevande, tempat rekreasi, tempat olahraga.

**Distinzione SLHS vs SLS vs SPP-IRT/PIRT vs PKP** (fonte: dpmptsp.gowakab.go.id, secondaria/gov, + ricerca incrociata):
- **SLHS** → TPP food-service (restoran, jasaboga, rumah makan, DAM).
- **SLS** → strutture non-food/TFU (Tempat Fasilitas Umum): hotel, tempat hiburan, rekreasi, olahraga. **ATTENZIONE**: alcune fonti secondarie usano "Sertifikat Laik Sehat" in modo generico/intercambiabile anche per il food — la distinzione netta SLHS(food)/SLS(non-food) è quella del documento ufficiale Batam 2024, presa come riferimento primario di questo lane.
- **SPP-IRT** (Sertifikat Pemenuhan Komitmen Produksi Pangan Olahan - Industri Rumah Tangga Pangan, ex-PIRT) → binario REGOLATORIO DIVERSO, per industria domestica di alimenti confezionati; è anch'esso PB-UMKU su OSS ma non è SLHS.
- **PKP** (Sertifikat Penyuluhan Keamanan Pangan) → certificato di FORMAZIONE prerequisito per il responsabile/cuoco del TPP; è un INPUT/documento richiesto per ottenere la SLHS, non un sostituto.

## 4. KBLI trigger — riscritta 2026-07-29 dopo verifica diretta sul dataset autoritativo

**Metodo di questa sezione**: ho interrogato io stesso, con `python3`/`json` (non fidandomi di un riassunto altrui), `data/source_documents/KBLI_2025_FINAL_CLEAN.json` — 1559 record, campo `kode_kbli_2025`, presente sia nel main checkout sia in questo worktree. Ogni codice sotto è stato **letto dal file**, non ricordato da una fonte web. Comando riproducibile: `python3 -c "import json; d=json.load(open('data/source_documents/KBLI_2025_FINAL_CLEAN.json')); [print(r['kode_kbli_2025'], r['judul']) for r in d['data'] if r['kode_kbli_2025'].startswith(('55','56'))]"`.

### 4.1 Verificato su disco — famiglie 55xxx (Akomodasi) e 56xxx (Makanan/Minuman), KBLI 2025

| Codice 2025 | Judul (KBLI 2025) | Ancestor KBLI 2020 (bridge meccanico, vedi §4.3) |
|---|---|---|
| 55101 | Aktivitas Hotel Bintang Lima | 55110 |
| 55102 | Aktivitas Hotel Bintang Empat | 55110 |
| 55103 | Aktivitas Hotel Bintang Tiga | 55110 |
| 55104 | Aktivitas Hotel Bintang Dua | 55110 |
| 55105 | Aktivitas Hotel Bintang Satu | 55110 |
| 55106 | Aktivitas Hotel Nonbintang | 55120 |
| 55201 | Aktivitas Rumah Tinggal Sewa (Homestay) | 55130 |
| 55202 | Aktivitas Hostel Remaja (Youth Hostel) | 55191 |
| 55203 | Aktivitas Vila | 55193 |
| 55204 | Aktivitas Apartemen Hotel | 55194 |
| 55209 | Aktivitas Penyediaan Akomodasi Jangka Pendek Lainnya | 55199 |
| 55300 | Aktivitas Penyediaan Bumi Perkemahan, Persinggahan Karavan, dan Taman Karavan | 55192 |
| 55400 | Aktivitas Jasa Intermediasi Akomodasi | 55900, 63122, 79990 |
| 55901 | Aktivitas Jasa Manajemen Akomodasi | 55900 |
| 55909 | Penyediaan Akomodasi Lainnya YTDL | 55900 |
| 56101 | Aktivitas Penyediaan Makanan di Bangunan Tetap | 56101, 56102, 56109 |
| 56102 | Aktivitas Penyediaan Makanan di Bangunan Tidak Tetap | 56103, 56104, 56109 |
| 56210 | Aktivitas Jasa Boga untuk Acara Tertentu (Event Catering) | 56210 |
| 56290 | Aktivitas Penyediaan Jasa Boga Lainnya | 56290 |
| 56301 | Aktivitas Bar | 56301 |
| 56302 | Aktivitas Kelab Malam atau Diskotek yang Utamanya Menyediakan Minuman | 56302 |
| 56303 | Aktivitas Rumah Minum/Kafe | 56303 |
| 56304 | Aktivitas Kedai Minuman | 56304 |
| 56305 | Aktivitas Rumah/Kedai Obat Bahan Alam | 56305 |
| 56306 | Aktivitas Penyediaan Minuman Keliling/Tempat Tidak Tetap | 56306 |
| 56400 | Aktivitas Jasa Intermediasi Penyediaan Makanan dan Minuman | 56101, 56102, 56103, 56104, 56109, 56210, 56290, 56301-56306, 63122, 79990 |
| 10307 | Pembuatan Tempe Kedelai | 10391 |
| 10308 | Pembuatan Tahu Kedelai | 10392 |
| 11052 | Industri Air Minum Isi Ulang (Depot Air Minum) | 11052 (invariato) |

Confermato inoltre: **47221 = "Perdagangan Eceran Minuman Beralkohol"** (commercio al dettaglio di bevande alcoliche) — NON "depot air minum". **56108** non esiste in KBLI 2025 e non compare nemmeno come ancestor KBLI 2020 di nessun codice 2025 nel dataset — nessuna traccia trovata, in nessuna direzione.

### 4.2 NON verificato — quale di questi codici fa scattare l'obbligo SLHS

**Questa è la domanda vera del brief, e resta aperta.** Nessuna delle fonti LLM consultate in questo lane (WebSearch, WebFetch, i due documenti Dinkes) legge o cita il testo del **Lampiran di Permenkes 14/2021** (come modificato da Permenkes 17/2024) — l'unica fonte che potrebbe rispondere con autorità. I documenti Batam/Purwakarta citano quel Permenkes come base legale ma riportano l'elenco KBLI-trigger già tradotto in **numerazione 2020**, non il lampiran stesso.

**Complicazione emersa dal bridge meccanico (§4.1)**: nel 2020, secondo il documento Batam, "Restoran" (56101-2020, SLHS piena) e "Rumah/Warung Makan gol. A1" (56102-2020, solo "Label Pengawasan" più leggero) erano **due codici KBLI distinti con due tier distinti**. Nel 2025, entrambi i codici 2020 (56101 e 56102, insieme al 56109) confluiscono nello **stesso** codice 2025 `56101` ("Bangunan Tetap"). Se il bridge è corretto, la distinzione di tier SLHS-piena/Label-leggero **non è più derivabile dal solo codice KBLI 2025** — potrebbe dover dipendere da scala d'impresa (`skala_usaha`) o da altri campi del lampiran, non dal codice. Non ho verificato questa ipotesi contro il lampiran stesso: è una deduzione dal bridge meccanico, non un fatto confermato.

### 4.3 Caveat obbligatorio — vintage KBLI 2020 vs 2025

Il dataset autoritativo del progetto è **KBLI 2025**. Il sistema OSS può ancora operare su **KBLI 2020** per NIB esistenti/preesistenti — "non esiste in KBLI 2025" **non significa** "non è mai esistito" o "non è più operativo in OSS per aziende già registrate sotto 2020". Il campo che collega le due annate, `bps_2020_ancestors`, esiste ed **è popolato più ampiamente di quanto inizialmente comunicato**: ho verificato io stesso, con lo stesso script, che **1.338 record su 1.559** (86%, non 8) hanno `bps_2020_ancestors.codes` non vuoto. **Ma** ogni singolo record fra questi 1.338 ha `adjudication_status: "mechanical-only"` e `inheritance_verdict: "not-adjudicated"` — **zero** mappature sono state verificate da un umano; sono tutte candidate generate meccanicamente. Questo è il vero limite, non il conteggio: il bridge 2020↔2025 è ampio ma interamente non auditato, quindi utilizzabile come **lead** (come ho fatto in §4.1/§4.2) ma **non citabile come ground truth** finché non passa una revisione umana o non è incrociato col lampiran ufficiale.

### 4.4 Codici del brief originale del team — verifica diretta

| Codice richiesto nel brief | Verificato? |
|---|---|
| 56101, 56102, 56210, 56290 (F&B) | Esistono in KBLI 2025 — vedi §4.1. Se innescano SLHS: NON verificato, §4.2. |
| 56301-56306 (famiglia bar/minuman) | Esistono tutti in KBLI 2025 — vedi §4.1. Copre anche 56303 (Rumah Minum/Kafe), il codice "rumah minum/bar" che il brief chiedeva esplicitamente. |
| 55111/55112/55130 (hotel/villa, dal brief originale) | **Nessuno dei tre esiste** in KBLI 2025. I codici 2025 reali per hotel/vila sono quelli in §4.1 (55101-55106, 55203, ecc.). |

## 5. Validità e rinnovo

- **Adempimento iniziale**: la SLHS va soddisfatta entro **1 (satu) tahun sejak NIB diterbitkan OSS** (eccetto DAM: prima del NIB) — CERTO, verbatim da 2 documenti ufficiali indipendenti (Batam, Purwakarta).
- **Rinnovo**: richiede "SLHS yang masih berlaku" + documenti tecnici aggiornati — CERTO (stesso testo), ma questo presuppone una scadenza la cui **durata in anni non è stata trovata in nessuna fonte primaria consultata in questo turno**.
- **Durata numerica**: fonti secondarie discordanti — alcune indicano 3 anni (prassi Sidoarjo), altre 5 anni (blog generico, senza citazione normativa) — **[NON VERIFICATO]**, marcato esplicitamente come incertezza aperta (§9). Non tentare di riportare un numero preciso senza prima aver letto il lampiran completo di Permenkes 14/2021 (non reperito in questa sessione — solo estratti via documenti Dinkes derivati).

## 6. Sanzioni

Fonte primaria: **PP 28/2024, Pasal 251-252** (verbatim, verificato su testo estratto):
- Pasal 251(1): ogni pengelola/penyelenggara/penanggung jawab di ambienti che rientrano nella Kesehatan Lingkungan (incl. tempat kerja, fasilitas umum — categoria che copre i TPP) **wajib menyelenggarakan Kesehatan lingkungan**.
- Pasal 252(1)-(2): la violazione è punita con **sanksi administratif**, in scala: (a) teguran lisan, (b) teguran tertulis, (c) penghentian sementara kegiatan atau usaha, dan/atau (d) **pencabutan atau rekomendasi pencabutan izin**.
- Pasal 252(3): sanzione imposta da Pemerintah Pusat, Provinsi o Kabupaten/Kota "sesuai dengan kewenangannya".

**CERTO** questa è la base legale generale di livello PP applicabile ai TPP oggi. Una fonte secondaria (search-summary) cita anche l'**UU 18/2012 tentang Pangan** come base per sanzioni specifiche pangan (denda, penghentian sementara, pencabutan izin) — **PROBABILE**, non verificato su testo primario UU 18/2012 in questo turno.

## 7. Autorità e IKL

- **Autorità emittente**: Dinas Kesehatan Kabupaten/Kota, operativizzata via DPMPTSP nel flusso OSS-RBA (SLHS = PB-UMKU / persyaratan non-KBLI) — **CERTO**, confermato da 2 documenti ufficiali indipendenti Dinkes/DPMPTSP (Batam, Purwakarta), entrambi 2024.
- **IKL (Inspeksi Kesehatan Lingkungan)**: condotta da tenaga sanitarian/tenaga kesehatan lingkungan, tramite **Formulir IKL** (compilato dal personale sanitario) + **Formulir Self Assessment** (compilato dal pelaku usaha, stesso formato ma senza uji laboratorium) — **CERTO**, verbatim documento Purwakarta.
- **Punteggio minimo di superamento (80)**: citato da una sola fonte secondaria aggregata (ricerca su un articolo dinkes.banjarmasinkota.go.id) — **[NON VERIFICATO]**, non ritrovato nei documenti primari estratti in questo turno.
- **e-monev HSP**: sistema web ufficiale (in uso da almeno il 2019 secondo dinkes.jogjaprov.go.id) per la raccolta/reporting dei dati di monitoraggio HSP dal livello Puskesmas → Dinkes Kab/Kota → Dinkes Provinsi → Kemkes centrale, usato come base per la verifica pre-emissione SLHS/SLS — **PROBABILE** (fonte governativa ma secondaria/blog istituzionale, non il testo del Permenkes che lo istituisce).

## 8. Cambiamenti 2024-2026

Questa è la domanda a più alto rischio segnalata dal brief, e qui la risposta è: **il cambiamento c'è, è strutturale a livello PP, ma NON ha (ancora) prodotto un nuovo Permenkes dedicato che sostituisca esplicitamente Permenkes 2/2023.**

1. **26 luglio 2024**: PP 28/2024 abroga esplicitamente PP 66/2014 (Pasal 1170 huruf q) — il fondamento storico dell'intero impianto SLHS/Kesehatan Lingkungan sparisce a livello PP.
2. **Ma** lo stesso PP 28/2024 (Pasal 1169) salva esplicitamente le norme attuative (Permenkes) delle PP abrogate elencate, incl. PP 66/2014, "sepanjang tidak bertentangan" con la nuova PP — quindi **Permenkes 2/2023 continua ad applicarsi** come diritto transitorio, e con esso restano morte le 4 vecchie norme settoriali (Kepmenkes 1096/2011, 1098/2003, 942/2003, Permenkes 43/2014) che il team chiedeva di verificare.
3. PP 28/2024 introduce un proprio capitolo "Kesehatan Lingkungan" (Bagian Ketiga Belas, Pasal 245-253) che ridefinisce l'impianto normativo A LIVELLO PP (media lingkungan, standar baku mutu, upaya penyehatan/pengamanan/pengendalian) ma **delega esplicitamente** (Pasal 248 ayat 6) "ketentuan lebih lanjut" a un futuro **Peraturan Menteri** — che, al momento di questa ricerca, **non risulta ancora emesso** come sostituto dedicato di Permenkes 2/2023.
4. **Permenkes 17/2024** (26 luglio 2024, coincidenza di data con PP 28/2024 non verificata) modifica per la seconda volta Permenkes 14/2021 (lo standard OSS-RBA sektor kesehatan che contiene il lampiran tecnico SLHS/TPP usato dai Dinkes) — ma **non è stato verificato in questo turno** se questa modifica abbia toccato specificamente il lampiran SLHS/TPP o altre parti di 14/2021.
5. **Nessuna evidenza trovata** di un cambio di nomenclatura del certificato stesso: i documenti ufficiali Dinkes datati 2024 (Batam, Purwakarta) continuano a chiamarlo "Sertifikat Laik Higiene Sanitasi (SLHS)" — il nome resta stabile operativamente anche se il suo fondamento a livello PP è cambiato.
6. **KBLI stesso ristrutturato nel frattempo (2025)**: la famiglia 56xxx è stata riorganizzata — il vecchio 56101-2020 "Restoran" e il vecchio 56109-2020 "catch-all makanan keliling/kantin" si sono ricombinati in modo non 1:1 nel nuovo 56101/56102-2025 (vedi §4.2). Questo significa che anche SE il lampiran SLHS di Permenkes 14/2021 non fosse mai stato riscritto, il suo aggancio KBLI potrebbe essere silenziosamente disallineato dalla ristrutturazione 2025 — un ulteriore canale di obsolescenza indipendente dalla catena PP 66/2014→28/2024.

## 9. INCERTEZZE APERTE

1. **Durata di validità della SLHS in anni**: nessuna fonte primaria consultata la specifica; fonti secondarie discordanti (3 vs 5 anni). Richiede lettura del lampiran completo di Permenkes 14/2021 (non reperito in questa sessione).
2. **Esiste già, o è in bozza, un nuovo Permenkes che sostituisca esplicitamente Permenkes 2/2023 sotto il fondamento di PP 28/2024?** Non trovato. L'assunzione operativa corrente è continuità via clausola transitoria (Pasal 1169), ma questa è un'inferenza giuridica, non una conferma diretta di un testo che lo dichiari.
3. **UU 17/2023 Pasal 454 che abroga UU 36/2009**: fonte solo secondaria (riassunto AI di ricerca web + titolo hukumonline). Due tentativi di fetch diretto su testo primario (peraturan.go.id, peraturan.bpk.go.id) sono falliti con errori server (500/403) in questa sessione — da riverificare quando le fonti primarie sono raggiungibili.
4. **Contenuto esatto delle modifiche di Permenkes 17/2024** al lampiran SLHS/TPP di Permenkes 14/2021: solo il titolo generale ("Perubahan Kedua") è stato verificato; il contenuto specifico no.
5. **Punteggio minimo IKL (80)** e dettagli del sistema **e-monev HSP**: solo fonti secondarie/gov-blog, non il testo del Permenkes che li istituisce.
6. **Base legale sanzioni pangan specifiche (UU 18/2012 tentang Pangan)**: citata solo da fonte secondaria aggregata, non verificata su testo primario in questo turno.
7. **LA LACUNA PIÙ COSTOSA — mappatura KBLI 2025 → obbligo SLHS**: verificati su disco 28 codici KBLI 2025 delle famiglie 55xxx/56xxx/103xx/110xx (§4.1), ma **nessuna fonte consultata dice quali di questi facciano scattare l'obbligo SLHS** — l'unica fonte che potrebbe saperlo è il Lampiran di Permenkes 14/2021 (come modificato da 17/2024), non ancora letto direttamente in questa sessione. È la lacuna più costosa perché determina a quali clienti Bali Zero può vendere il servizio SLHS con certezza legale. Aggravante: il bridge KBLI 2020↔2025 che permetterebbe di tradurre l'elenco-trigger 2020 (noto, da Batam/Purwakarta) in codici 2025 è interamente `mechanical-only`/`not-adjudicated` (§4.3) — nessun umano lo ha verificato — e mostra almeno un caso (56101/56102-2020 confluiti nello stesso 56101-2025) dove la distinzione di tier che serve a rispondere alla domanda potrebbe essersi persa nella transizione.

---

# Riassunto compatto (return-value)

1. SLHS = certificato/PB-UMKU rilasciato da Dinas Kesehatan Kab/Kota via OSS-RBA per TPP food-service — non è un izin usaha autonomo. **CERTO** (natura giuridica), PROBABILE (formulazione esatta definizione Kemkes).
2. **PP 66/2014 (fondamento storico SLHS) è stato esplicitamente ABROGATO da PP 28/2024, Pasal 1170 huruf q**, verificato verbatim su testo primario. **CERTO**.
3. **Ma Permenkes 2/2023 (che implementava PP 66/2014, e che nel 2023 aveva già abrogato le 4 vecchie norme settoriali — Kepmenkes 1096/2011, 1098/2003, 942/2003, Permenkes 43/2014) RESTA VALIDO** grazie alla clausola transitoria di PP 28/2024 Pasal 1169 ("sepanjang tidak bertentangan"). **CERTO sul meccanismo, PROBABILE sulla conclusione pratica di continuità** (nessun Permenkes sostitutivo trovato).
4. Le 4 vecchie norme settoriali chieste dal team (jasaboga 1096/2011, rumah makan 1098/2003, DAM 43/2014, makanan jajanan 942/2003) sono **TUTTE ABROGATE**, ma questa conferma proviene da un elenco secondario (kompasiana) corroborato solo da riassunti WebSearch, non da lettura diretta del testo primario di Permenkes 2/2023. **PROBABILE**, non CERTO in senso stretto.
5. Esistono **3 livelli distinti di certificazione**, non 1: SLHS piena (restoran/jasaboga/DAM/industri tahu-tempe), "Label Pengawasan/Pembinaan" più leggero (warung makan A1/A2, kantin, gerai jajanan), e SLS separata (hotel, tempat hiburan/rekreasi/olahraga). **CERTO** che i 3 livelli esistano (documento ufficiale Dinkes Batam 2024); **NON VERIFICATO** come si mappino sui codici KBLI 2025 — vedi #6.
6. **§4 riscritta 2026-07-29**: la prima bozza citava codici hotel/villa (55110/55120/55193/55130) come "CERTO" — erano in realtà codici **KBLI 2020**, non 2025, presentati senza dichiarare il vintage. Verificato ora io stesso, direttamente su `data/source_documents/KBLI_2025_FINAL_CLEAN.json`: i codici KBLI 2025 reali sono 55101-55106 (hotel bintang/nonbintang), 55201-55209 (homestay/hostel/vila/apartemen/altro), 55300/55400/55901/55909. **Correzione a mia volta a un'affermazione del team-lead**: il campo `bps_2020_ancestors` non è popolato "per 8 codici su 1.559" ma per **1.338 su 1.559** — verificato con lo stesso script; il vero limite è che tutti e 1.338 sono `mechanical-only`/`not-adjudicated` (zero verifica umana), non il conteggio. La **mappatura KBLI 2025→obbligo SLHS resta NON verificata** — nessuna fonte consultata la conferma; vedi §9 punto 7.
7. **56303 esiste in KBLI 2025** ("Aktivitas Rumah Minum/Kafe") — copre il "rumah minum/bar" chiesto dal team. Se innesca SLHS: non verificato.
8. **Durata di validità della SLHS in anni: NON VERIFICATA** su fonte primaria — 3 vs 5 anni discordanti tra fonti secondarie. Flag esplicito, nessun numero riportato come certo.
9. Sanzioni: **PP 28/2024 Pasal 251-252** (teguran lisan → tertulis → penghentian sementara → pencabutan izin) — **CERTO**, verbatim su testo primario.
10. **Permenkes 17/2024 NON è "tentang Higiene Sanitasi Jasa Boga"** come erroneamente riportato da una fonte secondaria (legalitas.org) — è la "Perubahan Kedua" generale a Permenkes 14/2021, titolo ufficiale verificato via farmalkes.kemkes.go.id. **CERTO** questa correzione.

**File scritto**: `/Users/balizero/nuzantara/research/compliance/2026-07-29-slhs-lane-a-regulatory.md` (via PR dal worktree `.worktrees/docs-slhs-lane-a/`, per disciplina di isolamento worktree del repo)
