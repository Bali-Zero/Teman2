---
date: 2026-07-29
domain: compliance
client_case: none-product-research
sources:
  - https://www.dinkes.denpasarkota.go.id/page/pelayanan-penerbitan-sertifikat-laik-hygiene-sanitasi-slhs-untuk-tempat-pengelolaan-pangan-tpp
  - https://diskes.badungkab.go.id/storage/diskes/file/PPT%20SOSIALISASI%20SERTIFIKASI%20LAIK%20SEHAT.pdf
  - https://dinkes.karangasemkab.go.id/standar-pelayanan/ertifikat-laik-higiene-sanitasi-tempat-pengolahan-pangan/
  - https://legalitas.org/tulisan/panduan-mengurus-sertifikat-laik-hygiene-sanitasi-slhs
  - https://readmore.id/administrasi/slhs-adalah-syarat-cara-daftar-sertifikat-laik-higiene
  - https://izin.co.id/blog/syarat-perpanjangan-sertifikat-laik-sehat/
  - https://izin.co.id/indonesia-business-tips/2025/09/03/beda-sertifikat-laik-sehat-dan-slhs/
  - http://www.indonesian-publichealth.com/sertifikat-laik-sehat-rumah-makan-dan-restoran/
  - https://www.ralali.com/blog/sop-mbg-sppg/panduan-lengkap-mengurus-slhs-untuk-jasa-boga-catering-mbg-syarat-terbaru-dan-estimasi-biaya/
  - https://bapelkesmas-diskes.baliprov.go.id/pelatihan-keamanan-pangan-siap-saji-bagi-penjamah-makanan-di-tempat-pengelolaan-pangan-tpp-uptd-bapelkesmas-dinas-kesehatan-provinsi-bali-24-s-d-26-maret-2025/
  - https://balailabkes.baliprov.go.id/pemeriksaan-rectal-swab/
  - https://www.kemkes.go.id/id/kemenkes-terbitkan-surat-edaran-percepatan-penerbitan-slhs
  - https://kemkes.go.id/id/surat-edaran-nomor-hk0202ci42022025-tentang-percepatan-penerbitan-sertifikat-laik-higiene-sanitasi-untuk-satuan-pelayanan-pemenuhan-gizi-pada-program-makan-bergizi-gratis
  - https://phri.or.id/
  - https://dpmptsp.badungkab.go.id/
  - https://dpmptsp.gianyarkab.go.id/
adversarial_review: codex
---

# SLHS a Bali — procedura operativa (LANE B)

## Adversarial review — Codex GPT-5.6 `sol` (effort high), 2026-07-29

> ⛔ **VERDETTO: DO-NOT-SHIP come guida corrente.** Generatore = Claude (lane Sonnet); grader = Codex, famiglia diversa. Le obiezioni sotto sono quelle SOPRAVVISSUTE: ognuna è stata riletta contro il file e, dove tocca un numero, ri-verificata a mano sul dataset canonico.
>
> Questo file è archiviato come **nota di lavoro superata**, non come fonte. Serve la tracciabilità di come ci siamo arrivati; le sue conclusioni non si citano. L'autorità sul regime vigente è `2026-07-29-slhs-lane-h-amendments.md`, l'arbitro sui codici è `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (campo `kode_kbli_2025`).
>
> Difetti concreti trovati dal reviewer (seat di famiglia diversa dall'autore):
>
> 1. L'intera procedura poggia su Permenkes 14/2021, revocata per questa materia dal 2025-10-03.
> 2. Mancano due conflitti KBLI 2025 (56103 e 68120 non esistono nel dataset canonico).
> 3. Requisiti, SLA e costi presentati come operativi risultano in parte falsi o non tracciati a una fonte.


> Tag obbligatorio su ogni numero: **[D]** DICHIARATO (fonte ufficiale) · **[O]** OSSERVATO (racconto/prassi di terzi, non ufficiale) · **[S]** STIMATO (mia stima, assunzioni dichiarate). Un numero senza tag non è nella tabella finale.
>
> **Scope**: SLHS = *Sertifikat Laik Higiene Sanitasi*, il certificato specifico per attività **food & beverage** (ristorante, rumah makan, jasa boga/catering, depot air minum). **Non è lo stesso documento della Sertifikat Laik Sehat (SLS)**, che è più generica (alloggi, luoghi di intrattenimento, strutture pubbliche non-food) — le due certificazioni condividono l'ente emittente (Dinas Kesehatan) e parte del processo IKL, ma SLHS è quella pertinente a un cliente F&B [D, izin.co.id/beda-sertifikat-laik-sehat-dan-slhs]. Non confondere: alcuni consulenti online usano i due nomi come sinonimi — non lo sono.

---

## 0. Riepilogo esecutivo (per chi ha 60 secondi)

**Flusso in 15 righe:**
1. Precondizione: cliente ha già NIB via OSS (KBLI F&B: ristorante/rumah makan/jasa boga).
2. SLHS si richiede come **PB-UMKU** (Perizinan Berusaha untuk Menunjang Kegiatan Usaha) dentro OSS-RBA, non è la licenza primaria.
3. Il team del cliente completa **PKP** (Penyuluhan/pelatihan Keamanan Pangan) PRIMA di depositare: min. penanggung jawab + ≥50% dei penjamah pangan certificati [D].
4. In parallelo: campionamento e **uji laboratorium air bersih** (e a volte makanan matang/bahan mentah) presso lab accreditato/Labkesda.
5. Compilazione dossier (KTP, NIB, denah lokasi/dapur, bukti kepemilikan/sewa, foto, sertifikat PKP, hasil lab) + submission su OSS.
6. Verifikasi amministrativa dal Dinas Kesehatan Kab/Kota (elettronica).
7. Se completo → programmazione **IKL** (Inspeksi Kesehatan Lingkungan) on-site.
8. Ispettore compila form IKL/RM.2, assegna punteggio per bobot×nilai.
9. Soglia: componente IKL ≥ **80** [D] e/o punteggio totale tutte le variabili > **700** [D] (fonte: sintesi Permenkes 14/2021, non lampiran originale — vedi §4 per limite di questa fonte).
10. Se PASS → surat rekomendasi caricata su OSS.
11. Certificato emesso via sistema OSS (elettronico).
12. Se FAIL → nota di correzione + termine per rimediare + re-inspection.
13. Validità tipica dichiarata altrove in Indonesia: 1-3 anni [O] — **non confermato per nessuno dei 5 kabupaten Bali richiesti** (LACUNA).
14. SLA "ufficiale" varia moltissimo tra kabupaten (7 giorni Denpasar [D] vs 1 giorno Karangasem [D], ma quel "1 giorno" copre quasi certamente solo lo step amministrativo, non l'ispezione fisica — vedi §7).
15. Il vero collo di bottiglia non è l'ufficio: è (a) la disponibilità dei corsi PKP e (b) lo stato fisico della cucina.

**I 5 colli di bottiglia veri** (dettaglio §3, §5, §8):
1. **PKP — disponibilità dei corsi**: sessioni a batch (es. 3 giorni consecutivi, poche volte l'anno all'UPTD Bapelkesmas Prov. Bali), non on-demand — se il batch giusto è appena passato, si aspetta il prossimo.
2. **Stato fisico della cucina**: grease trap assente/non funzionante, alur kotor-bersih non separato — la causa di rigetto più citata, e non si risolve con un documento ma con un intervento edile.
3. **Tempo/esito del test di laboratorio acqua** (e cibo se richiesto): giorni di turnaround + rischio di dover ripetere se fallisce.
4. **Scheduling dell'ispezione IKL on-site**: dipende dalla disponibilità dell'ispettore Dinkes, nessuna fonte garantisce una data fissa oltre il generico "verrà programmata".
5. **Surat rekomendasi PHRI** (se applicabile — vedi nota di affidabilità in §2): uno stakeholder esterno in più nella catena sequenziale, anche se gratuito e in teoria rapido.

**Range di costo** (dettaglio §6): **da Rp 5,4 a Rp 25,5 juta** per un ristorante medio (4-5 addetti), fortemente dipendente da se la cucina richiede o meno un intervento edile — **assunzioni esplicite in §6, non prendere il numero senza leggerle**.

**Lacune aperte da verificare sul campo** (elenco completo in §9): SLA e tariffa ufficiale per Badung, Gianyar, Tabanan, Buleleng; costo reale del corso PKP a Bali per un'azienda privata; se la rekomendasi PHRI è ancora richiesta post-Permenkes 14/2021; validità in anni del certificato nei 5 kabupaten; se il rectal swab è mandatorio ovunque o prassi locale.

**File**: `/Users/balizero/nuzantara/research/compliance/2026-07-29-slhs-lane-b-procedura.md`

---

## 1. Il flusso completo, step per step

> Precondizione non-SLHS: l'attività deve già avere **NIB** (Nomor Induk Berusaha) via OSS con KBLI food & beverage. SLHS è tecnicamente un **PB-UMKU** (izin ausiliario), non la licenza di base [D, dpmptsp.badungkab.go.id + più fonti generiche].

| # | Step | Chi lo fa | Dove | Durata | Cosa può andare storto |
|---|------|-----------|------|--------|--------------------------|
| 1 | Cliente contatta l'agenzia | Cliente → Bali Zero | remoto | — | Cliente non ha ancora NIB/OSS attivo → si parte da zero, allunga tutto |
| 2 | Verifica precondizioni: NIB attivo, KBLI corretto, denah dapur esiste | Consulente | remoto | 1 giorno | KBLI sbagliato in fase NIB → SLHS non collegabile finché non si corregge |
| 3 | **PKP** — iscrizione e completamento corso per penanggung jawab + ≥50% penjamah [D] | Cliente/staff, prenotato da consulente | UPTD Bapelkesmas Prov. Bali (Jl. Gumitir No.135, Denpasar Timur) o provider privato [D] | 3 giorni corso classico [D, bapelkesmas-diskes.baliprov.go.id] + attesa batch | **Collo di bottiglia #1** — batch limitati/anno, se il batch è pieno o già passato si aspetta il successivo |
| 4 | Campionamento e **uji laboratorium** air bersih (± makanan) | Consulente coordina, tecnico lab preleva in loco | Labkesda kabupaten o lab privato accreditato | Prelievo 1 giorno + esito 2-5 giorni [S, basato su turnaround tipico lab pubblici] | Esito fuori standard → richiede intervento (es. filtrazione) + ripetizione test |
| 5 | Compilazione dossier documentale (§2) | Consulente | remoto | 2-3 giorni se tutto disponibile | Documenti di proprietà/locazione incompleti (SHM/sewa/IMB-PBG) sono spesso il ritardo silenzioso |
| 6 | (Se applicabile) richiesta **surat rekomendasi PHRI** | Cliente/consulente | Segreteria PHRI locale | Dichiarato gratuito e "tidak ada syarat berlebih" [D, phri.or.id] ma nessuna fonte dà SLA in giorni — **LACUNA** | Step extra sequenziale se il locale è hotel/resto/café associato |
| 7 | Submission OSS (PB-UMKU SLHS) con tutti gli allegati | Consulente | oss.go.id | 1 giorno tecnico | Upload nel modulo/kategori sbagliato — comune con OSS-RBA |
| 8 | Verifica amministrativa da Dinas Kesehatan | Dinkes kab/kota | elettronica, via OSS | Variabile per kabupaten (vedi §7) | Rigetto per documento mancante → si torna al punto 5 |
| 9 | Programmazione **IKL** (ispezione fisica on-site) | Petugas Dinkes | sede del cliente | Nessuna fonte dà un tempo fisso di attesa — **LACUNA/collo di bottiglia #4** | Location non pronta il giorno dell'ispezione = fallimento del ciclo |
| 10 | Ispezione IKL: compilazione form (RM.2 o equivalente), assegnazione punteggio | Petugas Dinkes | on-site | Mezza giornata circa [S] | Vedi §4-§8 per soglie e cause di fallimento |
| 11 | Se PASS: surat rekomendasi caricata, certificato emesso via OSS | Dinkes → OSS | elettronico | Ore-giorni dopo il PASS [S] | — |
| 12 | Se FAIL: nota correttiva + termine di rimedio + re-inspection | Dinkes | — | Termine variabile, non standardizzato nelle fonti trovate | Ciclo si ripete da step 9 |

---

## 2. Checklist documenti

| Documento | Chi lo emette | Costo | Tempo | Collo di bottiglia? |
|---|---|---|---|---|
| NIB / registrazione OSS | Cliente via OSS (precondizione, non parte di SLHS) | — | — | No (dovrebbe già esistere) |
| Akta pendirian + SK Kemenkumham | Notaio (per PT) | pratica separata | pratica separata | No, se azienda già costituita |
| NPWP azienda/personale | DJP | gratuito | — | No |
| KTP/paspor del penanggung jawab | — | — | — | No |
| Surat penunjukan penanggung jawab | Cliente (auto-redatto) | — | — | No |
| Denah lokasi + denah bangunan/dapur (alur pangan kotor→bersih) | Cliente/architetto | variabile [S] | variabile | Sì, se il layout attuale non separa fisicamente area kotor/bersih — vedi §8 |
| Bukti kepemilikan (SHM) o sewa (surat perjanjian sewa) + PBG/SLF o bukti bangunan | Notaio/BPN o proprietario | pratica separata | pratica separata | Sì, se il proprietario dell'immobile non collabora rapidamente |
| Foto fasilitas | Cliente | — | — | No |
| Formulir IKL / self-assessment | Dinkes (fornito) o compilato dal richiedente [D, Karangasem] | gratuito | — | No |
| **Hasil uji laboratorium air bersih** (± makanan matang/bahan mentah in alcuni kabupaten) | Labkesda o lab privato accreditato | Rp 450.000–1.500.000 [D, aggregato mercato, non Bali-specifico — vedi §6] | prelievo+esito 3-6 giorni [S] | Sì — collo di bottiglia #3 |
| **Sertifikat pelatihan PKP** — penanggung jawab (100%) + penjamah (≥50%) [D] | UPTD Bapelkesmas Prov. Bali o provider privato/BNSP | Non confermato per Bali (vedi §3) | 3 giorni corso + attesa batch | Sì — collo di bottiglia #1, il più grande |
| **Hasil pemeriksaan kesehatan penjamah pangan** (incl. rectal swab/usap dubur per Salmonella typhoid, Shigella, E. coli) | Puskesmas/Labkesda (es. Balai Labkes Prov. Bali offre il servizio) [D, balailabkes.baliprov.go.id] | Non trovato un prezzo Bali-specifico — **LACUNA** | Risultato 2-4 giorni [D, balailabkes.baliprov.go.id] | Moderato — dipende da disponibilità appuntamento |
| Surat rekomendasi PHRI (solo hotel/resto/café — affidabilità della fonte limitata, vedi nota sotto) | PHRI locale | Dichiarato gratuito [D, phri.or.id] | Non specificato | Step extra sequenziale se applicabile |
| Surat permohonan | Cliente | — | — | No |

**Nota di affidabilità sulla rekomendasi PHRI**: l'ho trovata citata solo da un aggregatore secondario (readmore.id), non da una fonte ufficiale Dinkes/PTSP che la elenchi tra i requisiti SLHS post-Permenkes 14/2021. Potrebbe essere un requisito residuo di uno schema di certificazione turistica precedente, o valido solo per membri PHRI. **LACUNA — va verificato per-kabupaten se è ancora richiesto e per quali categorie di esercizio.**

---

## 3. Il collo di bottiglia nascosto: PKP (Penyuluhan Keamanan Pangan)

- **Chi eroga a Bali**: UPTD Bapelkesmas Dinas Kesehatan Provinsi Bali, Jl. Gumitir No. 135, Biaung Kesiman Kertalangu, Denpasar Timur — corso classico osservato 24-26 marzo 2025 (3 giorni) con 37 partecipanti da ristoranti e ospedali (es. Jaan Bali Restaurant) [D, bapelkesmas-diskes.baliprov.go.id]. Esistono anche provider privati/BNSP (es. corsi HACCP a Bali, multi-giorno) [O].
- **Durata**: 3 giorni per il corso base "Keamanan Pangan Siap Saji" [D]. Corsi HACCP-competency-based osservati altrove: 2 giorni training + 1 giorno esame [O, non Bali-specifico].
- **Costo per persona**: **non trovato un prezzo ufficiale Bali-specifico** — LACUNA. Un provider non-Bali (Pusdiklat LSMAP) cita Rp 3.500.000 (senza alloggio) – Rp 4.500.000 (con alloggio) per corsi self-funded/swadana [O, non Bali]. Va verificato se il corso UPTD Bapelkesmas ha un costo diverso (potenzialmente sussidiato per enti pubblici, non chiaro per attività F&B private).
- **Quante persone del team devono averlo**: penanggung jawab = 100%; penjamah pangan (chi maneggia direttamente il cibo) = **minimo 50% del totale** [D, più fonti concordanti incl. readmore.id e legalitas.org].
- **Perché è il vero collo di bottiglia**: il corso NON è on-demand — gira a batch (poche sessioni/anno osservate dal calendario UPTD Bapelkesmas), quindi la variabile che decide la timeline non è la burocrazia ma **"quando è il prossimo batch disponibile"**. Un cliente che si presenta appena dopo la chiusura iscrizioni di un batch aspetta il successivo (potenzialmente mesi).

---

## 4. IKL (Inspeksi Kesehatan Lingkungan) — griglia di punteggio

- **Form di riferimento**: formulir IKL / RM.2 (nome della fonte-sintesi trovata; il lampiran originale Permenkes 14/2021 con i pesi (bobot) dettagliati per componente **non è stato leggibile** nei due PDF recuperati in questa sessione — entrambi erano scansioni immagine non testuali. **LACUNA — i pesi esatti per componente vanno recuperati con OCR o richiesti direttamente a Dinkes.**
- **Metodo di scoring**: punteggio = bobot (peso) × nilai (valore) per ciascuna variabile [D, indonesian-publichealth.com, che cita il testo Permenkes].
- **Soglia di superamento**:
  - Componente IKL da solo: **minimo 80** [D, fonte aggregata pdfcoffee/permenkes-sintesi — non ho potuto verificare sul lampiran originale, quindi tag D ma con nota di provenienza secondaria].
  - Punteggio totale su tutte le variabili (per rumah makan/restoran): **> 700** [D, stessa nota di provenienza].
- **7 macro-categorie osservate nella sintesi Permenkes 14/2021**:
  1. Lokasi e struttura dell'edificio
  2. Fasilitas sanitasi (acqua, scarichi, toilet)
  3. Area cucina e stoccaggio
  4. Gestione di cibo e cibo pronto
  5. Attrezzature (qualità fisica/chimica/batteriologica)
  6. Personale (igiene personale, APD)
  7. Controllo di infestanti e animali (mosche, scarafaggi, topi, animali domestici) [D, esplicitamente citato]
- **Motivi di bocciatura più frequenti** (vedi anche §8): assenza/malfunzionamento del grease trap, mancata separazione area kotor/bersih, ventilazione insufficiente, illuminazione inadeguata, sistema di smaltimento rifiuti scoperto/inadeguato, toilet non igienici, presenza di infestanti.
- **Quanto ci mette a venire**: nessuna fonte trovata dà un tempo fisso — dipende dal calendario dell'ispettore Dinkes locale. **LACUNA.**
- **Cosa succede se boccia**: nota di correzione + termine per rimediare, poi re-inspection (ciclo ripetuto) [D, pattern generico confermato da più fonti, nessun termine in giorni specificato per Bali — LACUNA sul numero di giorni concesso].

---

## 5. Per-kabupaten — cosa è confermato e cosa manca

| Kabupaten | Ufficio | Portale online | Tariffa | SLA dichiarato | Fonte |
|---|---|---|---|---|---|
| **Denpasar** | Dinas Kesehatan Kota Denpasar, Jl. Maruti No. 8, lv. 3 | oss.go.id | **Gratis** (Perwali No. 16/2014) [D] | **7 hari kerja** [D] | dinkes.denpasarkota.go.id |
| **Badung** | Dinas Kesehatan Kab. Badung + DPMPTSP Badung (PB-UMKU) | oss.go.id + DPMPTSP Badung | **[LACUNA — richiede verifica sul campo]** — Dinkes Badung ha un deck di sosializzazione su Permenkes 14/2021 (conferma che applicano lo schema) ma il PDF era una scansione immagine non testuale, tariffa/SLA non estraibili in questa sessione | **[LACUNA]** | diskes.badungkab.go.id (PDF non leggibile), dpmptsp.badungkab.go.id |
| **Gianyar** (incl. Ubud) | DPMPTSP Kab. Gianyar, Jl. Ngurah Rai No. 5-7, Gianyar 80511, tel. (0361) 942230 | presumibilmente oss.go.id (nessuna pagina SLHS dedicata trovata) | **[LACUNA]** | **[LACUNA]** | dpmptsp.gianyarkab.go.id (solo indirizzo/contatti trovati) |
| **Tabanan** | **[LACUNA — nessuna pagina ufficiale trovata in questa ricerca]** | **[LACUNA]** | **[LACUNA]** | **[LACUNA]** | — |
| **Buleleng** | Dinas Kesehatan Kab. Buleleng (conferma di svolgere corsi PKP tramite un articolo di news) | **[LACUNA]** | **[LACUNA]** | **[LACUNA]** | dinkes.bulelengkab.go.id (solo articolo PKP, non pagina servizio SLHS) |

**Punto di calibrazione (non uno dei 5 kabupaten richiesti, ma utile come riferimento same-island/same-regime)**: Dinas Kesehatan Kab. Karangasem dichiara SLA **1 giorno lavorativo se il documento è completo e non richiede correzioni**, e **gratuito** [D, dinkes.karangasemkab.go.id]. Questo "1 giorno" quasi certamente copre solo lo step amministrativo/OSS, non include la programmazione e l'esecuzione dell'ispezione fisica IKL — nessuna fonte lo rende esplicito, è una mia lettura [S]. **Non estrapolare questo dato a Badung/Gianyar/Tabanan/Buleleng senza verifica diretta** — è un pattern regionale plausibile, non una prova.

---

## 6. Costo totale reale — stima disaggregata (ristorante medio)

**Assunzioni dichiarate**: ristorante medio con 1 penanggung jawab + 4 penjamah pangan (quindi min. 2 dei 4 penjamah devono avere PKP per il 50%); cucina esistente con almeno una carenza fisica minore (scenario "typical", non worst-case).

| Voce | Range (IDR) | Tag | Note |
|---|---|---|---|
| Retribusi/tariffa ufficiale SLHS | Rp 0 | [D]/[S] | Confermato gratis a Denpasar e Karangasem; **assunto** (non confermato) uguale per gli altri 4 kabupaten — LACUNA |
| Uji laboratorium air bersih (1 round) | Rp 450.000 – 1.500.000 | [D] | Range di mercato aggregato, non Bali-specifico; lab pubblico verso l'estremo basso, privato verso l'alto |
| Corso PKP × 3 persone (1 PJ + 2 penjamah) | Rp 4.500.000 – 9.000.000 | [O]→[S] | Basato su tariffa provider NON-Bali (Rp 1,5-3jt/persona stimato pro-rata da un pacchetto Rp 3,5-4,5jt osservato altrove); **costo reale a Bali via UPTD Bapelkesmas non confermato — LACUNA prioritaria** |
| Pemeriksaan kesehatan penjamah (incl. rectal swab) × 4 persone | Rp 400.000 – 1.000.000 | [S] | Stima basata su costo tipico di esami di laboratorio singoli in Indonesia; prezzo Bali specifico non trovato |
| Sertifikat KHSM (se richiesto separatamente) | Rp 150.000 – 500.000 | [O] | Citato da un solo aggregatore, non verificato su fonte ufficiale |
| **Subtotale senza intervento edile** | **Rp 5.500.000 – 12.000.000** | | |
| Intervento edile (grease trap, separazione area kotor/bersih, tempat sampah tertutup) — SOLO se necessario | Rp 3.000.000 – 15.000.000+ | [S] | Altamente variabile per dimensione cucina; nessuna fonte con prezzo Bali specifico consultata in questa sessione |
| **Totale (typical, senza retrofit)** | **~Rp 5,5 – 12 juta** | | |
| **Totale (worst case, con retrofit)** | **~Rp 8,5 – 27 juta** | | |

Nota: questo NON include l'eventuale fee di servizio dell'agenzia (Bali Zero) per la pratica — quella è pricing interno, fuori scope di questa ricerca prodotto.

---

## 7. Timeline realistica end-to-end

- **Best case**: 1-2 settimane — SOLO se staff già certificato PKP, cucina già conforme, acqua già testata di recente e conforme. Baseline plausibile: 7 giorni lavorativi (Denpasar SLA) [D], coerente anche con il precedente accelerato Kemenkes per SPPG/MBG di **14 giorni** una volta documento completo [D, SE Kemenkes No. HK.02.02/C.I/4202/2025 — **attenzione: questo termine è specifico al programma Makan Bergizi Gratis, non una regola generale per ristoranti commerciali**, uso qui solo come proxy di "quanto velocemente il sistema PUO' muoversi quando tutto è in regola"].
- **Typical**: 3-6 settimane [S] — il fattore dominante è l'attesa del prossimo batch PKP (non on-demand) sommata al turnaround lab (giorni) e allo scheduling dell'ispezione IKL (variabile, non garantito).
- **Worst case**: 2-4+ mesi [S] — se serve intervento edile in cucina (grease trap, ristrutturazione layout), se il batch PKP giusto è appena passato, o se l'IKL fallisce e serve un ciclo di re-inspection.
- **Cosa la fa slittare**: (1) mancata disponibilità del corso PKP nei tempi del cliente; (2) esito lab fuori standard che richiede ripetizione; (3) cucina fisicamente non pronta il giorno dell'ispezione; (4) documenti di proprietà/locazione dell'immobile incompleti; (5) rigetto amministrativo per KBLI/NIB non allineato.

---

## 8. Motivi di fallimento più comuni (lista pratica per il prodotto)

Confermati da fonte (esplicitamente citati) o da inferenza diretta dalle 7 macro-categorie IKL (§4):

1. **Grease trap assente o non funzionante** — limbah cair scaricato direttamente in fogna senza filtrazione. Conseguenza osservata a Bali: teguran tertulis, fino a chiusura temporanea 7-14 giorni [O, non fonte primaria ufficiale ma riportato in modo specifico e coerente con la prassi di enforcement locale].
2. **Alur pangan non separato** (area kotor/area bersih non fisicamente distinte nel layout cucina) — causa di rigetto strutturale, non risolvibile con un documento.
3. **Ventilazione insufficiente.**
4. **Illuminazione inadeguata.**
5. **Sistema di smaltimento rifiuti scoperto/inadeguato** (tempat sampah non tertutup).
6. **Toilet non igienici.**
7. **Presenza di infestanti** (lalat, kecoa, tikus, hewan peliharaan) — categoria esplicita del form IKL [D].
8. **Personale senza APD/igiene personale carente** (guanti, cuffie, ecc.) — categoria esplicita "Personale" del form IKL.
9. **Stoccaggio bahan pangan a contatto diretto col pavimento** — inferito dalla categoria "area cucina e stoccaggio" del form IKL; **non ho trovato una fonte che lo citi verbatim in questa sessione**, lo marco come [S]/best-practice standard di settore, non come citazione diretta.
10. **Documenti PKP mancanti o sotto la soglia del 50%** — causa di fallimento puramente amministrativo, indipendente dallo stato fisico del locale.
11. **Esito lab acqua/cibo fuori standard.**

---

## 9. Lacune da verificare sul campo (elenco consolidato)

1. **[LACUNA — Dinkes/DPMPTSP Kab. Badung]**: tariffa ufficiale e SLA in giorni per SLHS (il PDF di sosializzazione trovato era una scansione immagine, non estraibile in questa sessione — va riletto con OCR o richiesto direttamente).
2. **[LACUNA — DPMPTSP/Dinkes Kab. Gianyar]**: procedura, tariffa, SLA specifici per SLHS (solo indirizzo/contatti trovati).
3. **[LACUNA — Dinkes/DPMPTSP Kab. Tabanan]**: nessuna fonte trovata affatto in questa ricerca — priorità alta per verifica diretta.
4. **[LACUNA — Dinkes Kab. Buleleng]**: pagina di servizio SLHS non trovata (solo un articolo su corsi PKP).
5. **[LACUNA — costo reale corso PKP a Bali]**: il prezzo per persona del corso UPTD Bapelkesmas Prov. Bali (o dei provider privati locali) non è mai stato dichiarato in nessuna fonte consultata — è il dato economico più importante mancante, dato che è il collo di bottiglia #1.
6. **[LACUNA — rekomendasi PHRI]**: verificare se è ancora un requisito reale post-Permenkes 14/2021 per i 5 kabupaten, o un residuo di uno schema precedente citato solo da un aggregatore.
7. **[LACUNA — validità in anni del certificato]**: nessuna fonte Bali-specifica trovata; le fonti generiche indonesiane danno 1-3 anni "a seconda del regolamento regionale" — va confermato per kabupaten.
8. **[LACUNA — obbligatorietà del rectal swab]**: confermato che il servizio esiste (Balai Labkes Prov. Bali lo offre), ma non ho trovato una fonte che lo renda esplicitamente MANDATORIO nel dossier SLHS in tutti i 5 kabupaten vs. prassi/raccomandazione locale.
9. **[LACUNA — bobot/pesi esatti del form IKL]**: la sintesi conferma soglie (80 sul componente IKL, >700 sul totale) ma i pesi per singola voce sono nel lampiran originale Permenkes 14/2021, che in questa sessione era solo recuperabile come scansione immagine non testuale.
10. **[LACUNA — tempo di scheduling dell'ispezione IKL on-site]**: nessuna fonte dà un numero di giorni; è il collo di bottiglia #4 e resta il più opaco.
11. **[LACUNA — costo intervento edile grease trap/layout]**: nessun prezzo Bali-specifico consultato in questa sessione (esiste una guida di settore su prezzi grease trap, non ancora letta).

---

## Note metodologiche

Ricerca condotta interamente in bahasa Indonesia + inglese via web search, 2026-07-29. Due PDF ufficiali (Dinkes Badung sosializzazione Permenkes 14/2021; appendice lampiran IKL da eprints.poltekkesjogja.ac.id) sono risultati scansioni immagine non testuali e non sono stati processati con OCR in questa sessione — sono la fonte primaria dei dati mancanti su bobot IKL e tariffa Badung, e vanno riletti con un tool OCR dedicato prima della prossima iterazione. Nessuna tariffa è stata inventata: ogni cifra riportata ha un tag di provenienza esplicito.
