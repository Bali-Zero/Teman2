# Research Capture — "Anima Indonesiana" per KBLI Navigator

**Data**: 2026-08-11
**Mandato**: Zero — decorativi eleganti e sobri per KBLI Navigator (app macOS Bali Zero, 1.559 codici KBLI 2025), che parlino di «Indonesia Maju» / «Golden Age 2045», audience anche istituzionale (BKPM). NON un moodboard turistico-balinese: registro economico-nazionale, sobrio, quasi da "carta filigranata".
**Metodo**: WebSearch + WebFetch estensivo, nessuna modifica all'app.
**Scope check**: l'app non è stata toccata; questo è solo research capture.

**Nota operativa (2026-08-11)**: al momento della stesura il disco del checkout principale `/Users/nuzantara/nuzantara` era al 96% (≈578Mi liberi) e il broker worktree (`scripts/agent_start.py`) non riusciva a creare un worktree pieno ("No space left on device"); `--cleanup` non ha potuto liberare nulla perché ogni worktree esistente ha lavoro non mersato legittimo (WIP-safe by design). Questo file è quindi stato scritto nell'area di scratch convenzionale `REPO_ROOT/.worktrees/docs-kbli-nav-indonesian-soul/research/design/...` (path esplicitamente consentito dall'hook `worktree_file_write_check.py`), NON nel path finale `research/design/2026-08-11-kbli-navigator-indonesian-soul.md` del checkout main. Va copiato lì (semplice `cp`, pochi KB, nessun bisogno di un worktree pieno) non appena c'è spazio disco o da chi ha accesso in scrittura al main checkout.

---

## 1. Visi Indonesia Emas 2045 — pilastri, linguaggio visivo, retorica ufficiale

La **Golden Indonesia 2045 Vision** (Visi Indonesia Emas 2045) è stata formulata dal Kementerian PPN/Bappenas e lanciata da Joko Widodo il 9 maggio 2019, per il centenario dell'indipendenza (1945→2045). È il quadro dentro cui il governo attuale (Prabowo) inquadra RPJPN 2025-2045.

**I quattro pilastri ufficiali**:
1. Sviluppo umano e padronanza di scienza/tecnologia
2. Sviluppo economico sostenibile
3. Sviluppo equo (pemerataan)
4. Rafforzamento della resilienza nazionale e della governance

Ancorati esplicitamente a Pancasila e alla Costituzione del '45. La visione finale: **"Negara Nusantara Berdaulat, Maju, dan Berkelanjutan"** (Stato-Arcipelago Sovrano, Avanzato e Sostenibile), attuata via 8 agenda pembangunan, 17 arah pembangunan, 45 indikator utama.

**Target economici 2045**: 5ª economia mondiale, GDP ~$7.3 trilioni, reddito pro capite ~$25.000, uscita dalla middle-income trap.

**Linguaggio visivo/retorico ricorrente nelle comunicazioni ufficiali** (osservato su loghi, portali, materiali Bappenas):
- **Oro/dorato** come colore dominante — "Emas" non è solo nel nome, è letteralmente la palette (gradazioni oro-ambra su sfondo scuro o bianco).
- **Arco 1945 → 2045**: un secolo esatto, spesso reso graficamente come linea ascendente, timeline, o arco che "sale". La retorica è quella del compimento di una promessa (indipendenza → maturità della nazione), non della crescita infinita.
- **Garuda** compare nei materiali ufficiali come richiamo identitario ma quasi mai come la riproduzione fedele e integrale dell'emblema di Stato (che è regolamentato per legge, vedi §2) — più spesso come silhouette alare astratta o motivo di sfondo.
- Il logo ufficiale "Indonesia Emas 2045" è un lettering/monogramma, non un'illustrazione pittorica.

**Nota d'uso per KBLI Navigator**: il logo "Indonesia Emas 2045" e il claim stesso sono di proprietà/uso istituzionale Bappenas — non vanno riprodotti o citati come se l'app fosse un prodotto governativo. Ciò che si può prendere in prestito legittimamente è il **registro visivo** (oro, arco ascendente, sobrietà tipografica), non il logo.

Fonti: [Golden Indonesia 2045 Vision — Wikipedia](https://en.wikipedia.org/wiki/Golden_Indonesia_2045_Vision) · [Bappenas — Visi Indonesia 2045](https://www.bappenas.go.id/tags-berita/340) · [Bappenas — Peluncuran RPJPN 2025-2045](https://bappenas.go.id/id/berita/luncurkan-rancangan-akhir-rpjpn-2025-2045-presiden-paparkan-visi-indonesia-emas-2045-c29Ju) · [indonesia2045.go.id](https://indonesia2045.go.id/) · [ACLC KPK — The Vision of Indonesia 2045](https://aclc.kpk.go.id/learning-materials/governance/infographics/the-vision-of-indonesia-2045) · [Indonesia Emas 2045 — Brands of the World](https://www.brandsoftheworld.com/logo/indonesia-emas-2045)

---

## 2. Iconografia economico-nazionale

### Padi & Kapas (riso e cotone) — sila kelima Pancasila
Simbolo della quinta sila ("Keadilan sosial bagi seluruh rakyat Indonesia" — giustizia sociale per tutto il popolo indonesiano). Il **padi** (riso) rappresenta la disponibilità di cibo, la **kapas** (cotone) la disponibilità di vestiario: i due bisogni primari, la cui soddisfazione è precondizione della prosperità. È letteralmente **il simbolo civico della giustizia economica** nella filosofia di Stato — non un ornamento decorativo ma il segno ufficiale della sila che parla di benessere/equità sociale.

Rilevanza diretta per KBLI Navigator: un navigatore di codici che classificano l'attività economica nazionale è, concettualmente, uno strumento al servizio della stessa "giustizia sociale/economica" che padi & kapas rappresentano. Rischio di appropriazione: **basso** — è un simbolo civico/costituzionale di uso comune (compare su monete, francobolli, materiale scolastico), non sacro né riservato.

Fonti: [Kompas — Lambang Sila Ke-5: Padi dan Kapas](https://www.kompas.com/skola/read/2021/04/28/171416069/lambang-sila-ke-5-padi-dan-kapas) · [Bobo/Grid — Makna Simbol Padi dan Kapas](https://bobo.grid.id/read/083858936/makna-simbol-padi-dan-kapas-dalam-sila-ke-5-pancasila-materi-kelas-4-sd?page=all)

### Kepala Banteng (testa di banteng/toro selvatico) — sila keempat Pancasila
Simbolo della quarta sila ("Kerakyatan yang dipimpin oleh hikmat kebijaksanaan dalam permusyawaratan/perwakilan" — democrazia deliberativa/rappresentativa). Il banteng è animale sociale che si raduna in branco: simboleggia il musyawarah (consultazione/consenso collettivo). Sfondo rosso = coraggio; testa nera = colore della "terra patria". Meno pertinente a un tema puramente economico rispetto a padi & kapas, ma utile come nota di contesto (evocare "un sistema di regole condivise", cioè cosa sono le KBLI stesse — una tassonomia concordata).

Fonti: [Kompas — Lambang Sila Ke-4: Kepala Banteng](https://www.kompas.com/skola/read/2021/04/28/142716669/lambang-sila-ke-4-kepala-banteng) · [Kumparan — Makna Lambang Sila Keempat](https://kumparan.com/ragam-info/mengenal-makna-lambang-sila-keempat-pancasila-lengkap-dengan-contohnya-218s9v40bKm)

### Garuda Pancasila — limiti d'uso legali
Regolato dalla **Legge n. 24/2009** su Bandiera, Lingua e Simboli di Stato. Art. 51: l'emblema va usato in documenti statali, atti governativi, passaporti, diplomi, documenti ufficiali. Art. 57: **vietato** danneggiarlo/oltraggiarlo, e vietato **creare un emblema uguale o simile** per uso di privati, partiti, associazioni, organizzazioni o aziende. Sanzione fino a 1 anno di carcere o 100 milioni IDR di multa. Nel 2024 la registrazione del logo Garuda sulla maglia della nazionale di calcio (registrato da un privato) ha generato una controversia pubblica proprio su questo punto — dimostra quanto il tema sia sensibile anche quando l'uso è "patriottico" e non commerciale predatorio.

**Implicazione diretta per il Navigator**: **non riprodurre l'emblema di Stato** (Garuda con scudo Pancasila, motto Bhinneka Tunggal Ika) in nessuna forma stilizzata riconoscibile. Ciò che resta lecito: evocare la *silhouette alare* in modo estremamente astratto (un'ala, non l'uccello completo con scudo), oppure — meglio — evitare del tutto la Garuda e usare simboli economico-civici minori (padi/kapas, tumpal, motivi tessili) che non sono protetti come emblema di Stato.

Fonti: [Hukumonline — Hukumnya Penggunaan Lambang Garuda Pancasila pada Produk Komersial](https://www.hukumonline.com/klinik/a/hukumnya-penggunaan-lambang-garuda-pancasila-pada-produk-komersial-lt4e9d6aaa12e80/) · [Kompas — Hal yang Dilarang Dilakukan terhadap Lambang Negara](https://nasional.kompas.com/read/2022/05/26/02300051/hal-yang-dilarang-dilakukan-terhadap-lambang-negara) · [detik — Penggunaan Lambang Negara RI dalam Undang-Undang](https://news.detik.com/berita/d-6858216/penggunaan-lambang-negara-ri-dalam-undang-undang-cek-di-sini) · [Kontroversi Logo Garuda Jersey Timnas — Jawa Pos](https://www.jawapos.com/sepak-bola/014775344/kontroversi-logo-garuda-di-jersey-timnas-indonesia-didaftarkan-personal-begini-aturan-undang-undangnya)

### Pinisi (nave a vela sud-sulawesi)
Riconosciuta UNESCO nel 2017 come "The Art of Boatbuilding in South Sulawesi" (patrimonio culturale immateriale). Costruita dai maestri d'ascia Konjo di Ara (Bulukumba), usata storicamente da Bugis e Makassar come **nave da carico/commercio** — non da guerra né da culto. È l'icona per eccellenza del commercio marittimo arcipelagico indonesiano: rilevanza tematica diretta per un'app di classificazione economica (KBLI = attività economiche, il pinisi = veicolo storico dello scambio economico tra le isole).

Fonti: [Wikipedia — Pinisi](https://en.wikipedia.org/wiki/Pinisi) · [Kraken Travel — Indonesian Pinisi Boats](https://kraken.travel/story/pinisi-boats/)

### Nusantara / arcipelago come motivo cartografico
Il concetto di **Wawasan Nusantara** (visione arcipelagica indonesiana) è la dottrina nazionale che unifica terra, mare, aria in un'unica entità politico-economica-culturale. Compare anche nel nuovo emblema di IKN (§5): "sette tronchi = sette grandi isole/arcipelaghi". Un profilo cartografico astratto dell'arcipelago (silhouette, non mappa turistica con palme) è un motivo "safe" e diretto per rappresentare "economia nazionale a scala arcipelagica" — è letteralmente il perimetro entro cui vigono i 1.559 codici KBLI.

Fonti: [Wikipedia — Wawasan Nusantara](https://en.wikipedia.org/wiki/Wawasan_Nusantara)

---

## 3. Design system delle rupiah (serie 2022) — il miglior precedente di eleganza economico-istituzionale

La serie 2022 (lanciata 17 agosto 2022, 77° anniversario indipendenza) è stata premiata dalla **International Association of Currency Affairs (IACA)** come miglior nuova serie di banconote al mondo. Tema: **"Uniting Diversity"** (Persatuan dalam Keberagaman). Fronte = eroe nazionale + fiore; retro = danza tradizionale + paesaggio/fauna naturale. Ogni taglio ha un colore dominante distintivo per riconoscibilità immediata.

**Tabella completa delle 7 denominazioni** (fronte: eroe; retro: danza — paesaggio/flora):

| Taglio | Colore dominante | Eroe (fronte) | Danza (retro) | Paesaggio/Flora (retro) |
|---|---|---|---|---|
| Rp 1.000 | — | Tjut Meutia | Tari Tifa | Banda Neira & Anggrek Larat |
| Rp 2.000 | grigio/viola | Mohammad Hoesni Thamrin | Tari Piring | Ngarai Sianok & bunga Jeumpa |
| Rp 5.000 | arancio/verde/rosa | Dr. K.H. Idham Chalid | Tari Gambyong | Gunung Bromo & Sedap Malam |
| Rp 10.000 | viola/blu/arancio | Frans Kaisiepo | Tari Pakarena | Wakatobi National Park & Cempaka |
| Rp 20.000 | verde/blu/marrone/viola | Dr. G.S.S.J. Ratulangi | Tari Gong | Derawan & Anggrek Hitam |
| Rp 50.000 | blu | Ir. H. Djuanda Kartawidjaja | Tari Legong | Komodo National Park & Jepun Bali |
| Rp 100.000 | rosso, multicolore | Soekarno & Mohammad Hatta | Tari Topeng Betawi | Raja Ampat & Anggrek Bulan |

**Elementi di sicurezza/design che costituiscono il "linguaggio visivo istituzionale" da imitare** (senza copiare, ovviamente, i motivi di sicurezza reali): micro-printing, intaglio, guilloché (linee geometriche fitte e regolari), immagini latenti, tinte otticamente variabili. Il risultato percettivo è un **hairline engraving denso ma ordinato**, mai caotico — la texture che rende "ufficiale" un documento senza essere pesante.

**Perché è il miglior precedente per il Navigator**: la rupiah dimostra che l'iconografia economico-nazionale indonesiana (eroi, fauna endemica, danze, paesaggi) può convivere con un registro **sobrio, tecnico, sicuro** — è denaro, non souvenir. Il tono — non i soggetti specifici — è il modello da trasporre: fine hairline pattern, palette per "categoria" (qui: colore per taglio; nel Navigator: colore per settore KBLI?), micro-ornamento a bassa intensità.

Fonti: [Currency Affairs / IACA — Indonesia 2022 Rupiah Banknote Series](https://currencyaffairs.org/document/indonesia-2022-rupiah-banknote-series/) · [Coin World — Bank Indonesia releases new series](https://www.coinworld.com/news/paper-money/bank-indonesia-releases-new-series-of-rupiah-bank-notes) · [Keesing Platform — Indonesia Celebrates 77th Anniversary with New Banknotes](https://platform.keesingtechnologies.com/indonesia-celebrates-its-77th-anniversary-with-new-banknotes/) · [Kompas — Gambar yang Tertera pada 7 Uang Rupiah Kertas Terbaru](https://www.kompas.com/tren/read/2022/08/18/143100565/gambar-yang-tertera-pada-7-uang-rupiah-kertas-terbaru) · [Wikipedia — Indonesian 100,000 rupiah note](https://en.wikipedia.org/wiki/Indonesian_100,000_rupiah_note)

---

## 4. Tessile e pattern — significati e vincoli culturali

### Batik — motivi e restrizioni (Giava centrale, "batik larangan")
Il **batik** indonesiano è Patrimonio Culturale Immateriale UNESCO dal **2009** (tecnica, simbolismo, ruolo rituale dalla nascita alla morte).

- **Kawung**: cerchi geometrici che richiamano la sezione della palma da zucchero (aren), XIII secolo. Simboleggia autocontrollo interiore, saggezza, purezza. Storicamente riservato alle famiglie reali; oggi ampiamente indossato/usato senza le stesse restrizioni formali del parang. **Rischio: basso-medio** — resta percepito come "nobile" ma non genera controversie nell'uso quotidiano/commerciale moderato.
- **Parang (in particolare Parang Rusak)**: dal 1785 (Sultano Hamengku Buwono I) è il **primo motivo formalmente vietato** ai non reali nelle corti di Yogyakarta e Surakarta; un regolamento coloniale del 1927 ("Rijksblad van Djokjakarta") disciplinava chi potesse indossare quali motivi. Il Parang Rusak Barong (>10cm) resta riservato a Re e Principe ereditario nelle corti tuttora esistenti. **Rischio: alto** — va evitato o usato solo in forma estremamente astratta/irriconoscibile, mai come pattern-a-nome "parang".
- **Mega Mendung**: nuvole a gradazioni concentriche, Cirebon, influenza cinese (le nuvole rappresentano nirvana/trascendenza nella cultura cinese, poi reinterpretate localmente). Significa pazienza, calma, chiarezza mentale in mezzo alla tempesta. Anch'esso storicamente riservato ai re, **oggi liberamente indossato da tutti**. Metafora particolarmente calzante per un navigatore che porta ordine/calma dentro 1.559 codici (la "tempesta" burocratica). **Rischio: basso**, se astratto (non riprodurre il repeat-pattern tessile riconoscibile, ma solo la logica ad archi concentrici).
- **Truntum**: create da una consorte reale di Solo, simbolo di amore eterno/speranza, portato dai genitori degli sposi ai matrimoni. Poco pertinente al registro economico-istituzionale — da scartare per il Navigator.

**Controversia utile da citare come monito**: il caso 2023-24 del brand newyorkese *Aimé Leon Dore*, che ha commercializzato camicie con print "batik" etichettato genericamente come motivo astratto, prodotte in India senza coinvolgere designer/produttori batik indonesiani — ha sollevato accuse di **eksploitasi budaya** (appropriazione culturale) e ha costretto il brand a correggere il naming in "batik inspired print". Alcuni motivi batik creativi sono registrati come HKI (proprietà intellettuale) e richiedono licenza d'uso. Lezione diretta: se il Navigator userà pattern ispirati al batik, meglio (a) restare su motivi geometrici generici non attribuibili a una bottega/regione specifica, o (b) disegnare pattern originali "in stile" batik piuttosto che riprodurre un motivo storico nominato.

Fonti: [UNESCO ICH — Indonesian Batik](https://ich.unesco.org/en/RL/indonesian-batik-00170) · [The Jakarta Post — Batik selected for UNESCO cultural heritage list](https://www.thejakartapost.com/news/2009/09/08/batik-selected-unesco-cultural-heritage-list.html) · [Studio Gypsied — 5 Ancient Batik Patterns of Central Java](https://studiogypsied.com/blogs/textile-stories-asia/5-ancient-indonesian-batik-patterns-their-meanings) · [detik Jogja — Batik Parang Rusak: Sejarah, Simbolisasi, dan Aturan Penggunaan di Keraton](https://www.detik.com/jogja/budaya/d-8208480/batik-parang-rusak-sejarah-simbolisasi-dan-aturan-penggunaan-di-keraton) · [Kraton Jogja — Motif Batik Larangan Keraton Yogyakarta](https://www.kratonjogja.id/kagungan-dalem/12-motif-batik-larangan-keraton-yogyakarta/) · [Kompas — Ragam Motif Batik Larangan di Keraton Yogyakarta dan Surakarta](https://yogyakarta.kompas.com/read/2022/12/10/090105678/ragam-motif-batik-larangan-di-keraton-yogyakarta-dan-surakarta-tidak?page=all) · [We Are Mandalas — The Iconic Batik Megamendung](https://wearemandalas.com/en-int/blogs/articles/megamendung-batik-characteristics-indonesian-heritage-modern-fashion) · [Kadek Satria — Batik Mega Mendung: A Well Known Batik Pattern from Cirebon](https://kadeksatria.wordpress.com/2016/03/14/batik-mega-mendung-a-well-known-batik-pattern-from-cirebon/) · [BPIPI Kemenperin — Etika dalam Estetika Pengadopsian Batik pada Desain Alas Kaki](https://bpipi.kemenperin.go.id/etika-dalam-estetika-pengadopsian-batik-pada-desain-alas-kaki/)

### Songket e Tenun Ikat
**Songket**: tessuto broccato a mano (seta/cotone) con fili d'oro/argento, motivi che evocano ricchezza e grandezza, tradizionalmente per cerimonie reali/matrimoni (Sumatra, Bali, Kalimantan). Il richiamo "oro" è tematicamente coerente con "Indonesia Emas", ma l'uso di *fili metallici dorati intrecciati* come motivo digitale rischia di scivolare nel kitsch se reso troppo letterale (oro lucido, effetto "gioiello").

**Tenun Ikat**: tessuto artigianale su telaio tradizionale, diffuso nelle isole esterne (NTT/Flores/Sumba/Sumatra), pattern geometrici ottenuti per resist-dyeing dei fili *prima* della tessitura. A differenza del batik giavanese, l'ikat **non ha una storia di riserva regale/di corte** paragonabile al parang — è tessuto "del popolo" (rakyat) delle isole periferiche. Questo lo rende culturalmente più sicuro da evocare in un contesto istituzionale nazionale (non regionale/dinastico), e la sua logica intrinsecamente geometrica (ordito/trama) si presta bene a diventare un pattern UI (griglia, weave a bassa opacità).

Fonti: [Wikipedia — Songket](https://en.wikipedia.org/wiki/Songket) · [Wikipedia — Tenun](https://en.wikipedia.org/wiki/Tenun) · [Fromnusa — Indonesian Fashion: How Heritage Textiles Are Shaping Modern Style](https://fromnusa.com/blogs/news/indonesian-fashion-heritage-textiles-modern-style)

### Tumpal — il motivo più "sicuro" in assoluto
Bordo triangolare (fila di triangoli, detto anche "pucuk rebung"/germoglio di bambù o "lawi ayam"), di origine pre-induista/austronesiana, diffuso in **tutto** l'arcipelago (non riservato a una corte o regione), simboleggia crescita, fertilità, la montagna sacra (Meru), forza vitale. Compare come bordo su kain/sarong in praticamente ogni tradizione tessile indonesiana — è il motivo più trasversale e meno "di proprietà" di un singolo gruppo. Perfetto come elemento geometrico puro (divisori, bordi di card, rule tra sezioni).

Fonti: [Academia.edu — The Tumpal Border: Histories and Interpretations](https://www.academia.edu/118097974/The_Tumpal_Border_Histories_and_Interpretations) · [Mandarin Mansion Glossary — Tumpal](https://www.mandarinmansion.com/glossary/tumpal)

---

## 5. Precedenti di traduzione sobria — istituzioni e brand che l'hanno già fatto bene

- **IKN / Nusantara — Emblema "Pohon Hayat" (Albero della Vita)**: vinto tramite concorso ADGI (500+ designer, 10 finalisti, voto pubblico >500.000 persone), disegnato da Aulia Akbar, adottato 30 maggio 2023. 5 radici = Pancasila; 7 tronchi = i sette grandi raggruppamenti insulari; sfera con 17 fiori = 17 agosto/indipendenza eterna. Ispirazione da wayang, Borobudur, Dayak, Bugis, Asmat — sintetizzata in un **unico simbolo astratto**, non un collage pittorico. Il lettering usa il font "IKN Sutasoma", derivato dalla scrittura Pallava dell'iscrizione Yupa di Kutai (Kalimantan Est) — cioè **tipografia radicata nella storia** invece di un font generico. È probabilmente il miglior esempio contemporaneo di "molte fonti tradizionali → un solo simbolo sobrio e istituzionale".
- **Garuda Indonesia — livree batik**: la compagnia ha lanciato livree a tema batik (es. "Batik Tambal" 2020, "Mega Mendung"/"Kembara Angkasa" 2023) tramite concorsi di design studenteschi, applicando il motivo come **pattern esteso e ripetuto** sulla fusoliera — un uso di batik reale ma controllato (competizione ufficiale, motivi non "larangan", intento dichiaratamente culturale/commemorativo).
- **Padiglione Indonesia — Expo 2020 Dubai**: facciata avvolta in "toppe" di diversi tessuti batik tradizionali indonesiani, reinterpretando pattern di tessitura storici in chiave architettonica contemporanea — descritto come "ponte elegante tra storia e modernità". Tema: "Unity in Diversity" / "Creating the Future, From Indonesia to the World".
- **Bank Indonesia — identità visiva**: il logo BI è un **monogramma "BI" stilizzato**, non un'illustrazione — deriva dall'emblema storico di De Javasche Bank, ri-contestualizzato dopo la nazionalizzazione. Approccio "letterforma, non pittogramma": è lo standard delle banche centrali per comunicare disciplina/permanenza. Lezione: per un tool istituzionale, spesso la sobrietà massima è *non* usare simboli pittorici affatto, ma tipografia/monogrammi solidi + micro-texture (guilloché, cfr §3) come unico ornamento.
- **Danantara Indonesia** (fondo sovrano BUMN, lanciato 24 feb 2025): possiede linee guida di brand formalizzate ("Danantara Indonesia Brand Guidelines"), sostituendo il branding precedente "BUMN Untuk Indonesia" — segnale che anche le nuove istituzioni economiche di punta stanno investendo in identità visive proprie e coerenti (utile come riferimento di "che aspetto ha oggi l'establishment economico indonesiano" quando si presenta al pubblico).

Fonti: [Seasia.co — The New Logo of the Capital Nusantara: Pohon Hayat](https://seasia.co/2023/06/01/the-new-logo-of-the-capital-nusantara-pohon-hayat-the-source-of-life) · [Wikipedia — Emblem of Nusantara](https://en.wikipedia.org/wiki/Emblem_of_Nusantara) · [Rumah123 — Makna Logo IKN Nusantara dan Filosofi Pohon Hayat](https://www.rumah123.com/ikn/logo-ikn-nusantara/) · [The Jakarta Post — Batik 'tambal' motif adorns Garuda Indonesia aircraft](https://www.thejakartapost.com/travel/2020/12/02/batik-tambal-motif-adorns-garuda-indonesia-aircraft.html) · [Kompas Travel — Motif Batik Mega Mendung dan Awan Hiasi Badan Pesawat Garuda Indonesia](https://travel.kompas.com/read/2023/03/02/232150727/motif-batik-mega-mendung-dan-awan-hiasi-badan-pesawat-garuda-indonesia?page=all) · [Setkab — 11,000 People Visit Indonesia's Pavilion at Expo 2020 Dubai](https://setkab.go.id/en/11000-people-visit-indonesias-pavilion-at-expo-2020-dubai/) · [Expo 2020 Dubai — Indonesia Pavilion](https://www.expo2020dubai.com/en/understanding-expo/participants/country-pavilions/indonesia) · [Artbox Creative — Bank Indonesia Logo](https://artboxcreative.net/bank-indonesia-logo/) · [Wikipedia — Danantara](https://en.wikipedia.org/wiki/Danantara)

---

## 6. Anti-pattern — cosa evitare assolutamente

1. **Cliché turistico balinese fuori contesto**: tramonti, palme, "candi bentar" (portali balinesi), templi in stile Bali su un'app che parla di codici KBLI nazionali (validi per tutta Indonesia, non solo Bali) è un errore concettuale prima ancora che estetico — confonde "Bali Zero l'azienda" con "l'Indonesia come Paese economico". La ricerca sul kitsch turistico balinese (kriya vs kriya retro/"kitsch") mostra proprio questa tensione tra artigianato autentico e riproduzioni per turisti — da tenere fuori.
2. **Kitsch dorato**: oro lucido, effetto metallizzato/gioiello, gradient dorati pesanti — evoca "certificato da parete" o packaging da spa, non "istituzione economica seria". L'oro va usato come i governativi lo usano nel logo Emas 2045: **accento tipografico sottile**, non superficie.
3. **Pattern sacri/reali fuori contesto**: qualunque uso riconoscibile di **Parang** (specialmente Parang Rusak) fuori dal suo registro storico è un errore culturale documentato (§4) — ed è esattamente il tipo di errore per cui i brand stranieri vengono criticati pubblicamente (caso Aimé Leon Dore, §4).
4. **"Wayang ovunque"**: le sagome di wayang kulit sono già il motivo decorativo indonesiano più abusato nel design "genericamente esotico" internazionale — usarlo ancora, specie su un tool economico-normativo, comunica "clip-art culturale" invece di "istituzione seria". Stesso discorso per la Garuda Wisnu Kencana / templi come hero-image.
5. **Riproduzione dell'emblema di Stato (Garuda Pancasila completo)**: illegale/impropria per un attore privato (§2) — anche in forma "ispirata", rischia di apparire come un claim di ufficialità che l'app non ha.
6. **Riuso del logo "Indonesia Emas 2045" o del claim ufficiale Bappenas as-is**: l'app può *parlare lo stesso linguaggio* (oro, arco 1945-2045, sobrietà) ma non può appropriarsi del logo/claim di una campagna governativa specifica.
7. **Densità decorativa eccessiva**: qualunque pattern tradizionale (batik, tenun, tumpal) usato a piena opacità/piena saturazione su un'interfaccia funzionale (tabella di 1.559 codici) compete con la leggibilità. La lezione della rupiah (§3) è che anche il precedente "più decorato" di tutti resta **funzionale prima che ornamentale** — l'ornamento è cornice, mai contenuto.

Fonti: [Tandfonline — Sacred and profane kriya in the island of Bali](https://www.tandfonline.com/doi/full/10.1080/23311886.2024.2376287) · [Koran Sulindo — Kontroversi Batik: Simbol Budaya yang Diperebutkan](https://koransulindo.com/kontroversi-batik-simbol-budaya-yang-diperebutkan/) · [Sekar Jagad — Larangan Menggunakan Batik yang Berkaitan dengan Filosofi Budaya](https://sekarjagad.id/id/blog/larangan-menggunakan-batik-yang-berkaitan-dengan-filosofi-budaya)

---

## Motivi candidati per il Navigator (ordinati per adeguatezza)

Criterio: pertinenza tematica (economia/prosperità/nazione) × sicurezza culturale (non regale/non sacro/non protetto per legge) × traducibilità in decorativo sobrio (line-art / alpha bassa / watermark, mai pattern a piena saturazione).

1. **Padi & Kapas (riso e cotone, sila kelima Pancasila)**
   *Significato*: cibo e vestiario, cioè la giustizia sociale/economica come fondamento della Repubblica.
   *Perché è adatto/sicuro*: simbolo civico, non regale né sacro; uso comune e non controverso; è tematicamente il simbolo *più* pertinente possibile a un'app che classifica l'attività economica nazionale.
   *Come renderlo sobrio*: un rametto di riso stilizzato in line-art monocromatica (1px), usato come piccolo ornamento d'angolo in intestazioni/report PDF, o come motivo a bassissima opacità (3-5%) nel footer/watermark — mai a colori, mai come illustrazione centrale.

2. **Tumpal (bordo triangolare geometrico)**
   *Significato*: crescita, fertilità, montagna sacra/forza vitale — motivo pan-indonesiano, non attribuibile a una singola corte o regione.
   *Perché è adatto/sicuro*: il più "neutro" di tutti i motivi tessili indonesiani — nessuna storia di riserva regale, presente in quasi ogni tradizione tessile dell'arcipelago.
   *Come renderlo sobrio*: fila sottile di triangoli come rule/divisore tra sezioni di contenuto (es. tra categorie KBLI), 1px stroke, nessun riempimento colorato.

3. **Estetica guilloché "in stile rupiah 2022"** (non un motivo, ma una texture/registro)
   *Significato*: il precedente istituzionale più autorevole di "eleganza economica indonesiana" (premiato IACA).
   *Perché è adatto/sicuro*: non è un simbolo culturale specifico da appropriarsi, ma un **linguaggio tecnico** (hairline engraving, micro-pattern geometrico regolare) — zero rischio culturale, massima resa "documento ufficiale".
   *Come renderlo sobrio*: micro-pattern di linee sottilissime e regolari (non i motivi di sicurezza reali, che sono protetti) come sfondo di card/header, opacità 4-8%, monocromatico sul colore di superficie.

4. **Kawung (cerchi geometrici, sezione di palma da zucchero)**
   *Significato*: autocontrollo, saggezza, purezza; storicamente regale ma oggi di uso comune.
   *Perché è adatto/sicuro*: rischio medio-basso (era "larangan" ma non ha lo stesso peso simbolico/legale del parang oggi); la sua struttura a cerchi in griglia offset è visivamente affine a una "matrice di codici".
   *Come renderlo sobrio*: pattern di cerchi concentrici minuscoli, alpha 3-5%, solo come texture di sfondo per pannelli vuoti/empty-state — mai come stampa a piena intensità che lo renda riconoscibile come "batik".

5. **Tenun ikat (intreccio geometrico astratto)**
   *Significato*: tessuto "del popolo" delle isole esterne (NTT, Sumatra, ecc.), nessuna esclusiva di corte.
   *Perché è adatto/sicuro*: rappresenta la diversità arcipelagica *fuori* da Giava/Bali, bilanciando l'inevitabile giavacentrismo del batik; intrinsecamente geometrico (logica ordito/trama), facile da astrarre in griglia UI.
   *Come renderlo sobrio*: motivo a intreccio diagonale sottile come texture di sfondo per una sezione "About"/onboarding, mai come sfondo dell'intera tabella dati.

6. **Silhouette cartografica dell'arcipelago (Nusantara)**
   *Significato*: il perimetro stesso entro cui vigono le KBLI — l'intera nazione-arcipelago come unità economica.
   *Perché è adatto/sicuro*: puramente geografico/astratto, nessuna connotazione religiosa o dinastica; eco diretta del simbolismo IKN ("7 tronchi = 7 raggruppamenti insulari").
   *Come renderlo sobrio*: outline sottile (non mappa dettagliata, non palme/spiagge) come watermark di sfondo nella schermata "About"/splash, in un solo tono, mai a colori bandiera.

7. **Pinisi (silhouette di scafo, non vele spiegate drammatiche)**
   *Significato*: nave da commercio storica, patrimonio UNESCO 2017 — l'icona per eccellenza dello scambio economico arcipelagico.
   *Perché è adatto/sicuro*: è esplicitamente un veicolo di *commercio*, non un simbolo religioso/regale; riconoscibile ma non "turistico" se reso in modo minimale.
   *Come renderlo sobrio*: icona single-line (stile line-icon, non illustrazione 3D/glossy) per stati vuoti o loading, mai come hero image patinata da brochure da crociera.

8. **Arco dorato ascendente 1945→2045** (device grafico astratto, non il logo ufficiale)
   *Significato*: eco del registro visivo "Indonesia Emas 2045" — il secolo dell'indipendenza come traiettoria di crescita.
   *Perché è adatto/sicuro*: è un *device* generico (linea/arco con gradiente oro), non il logo protetto della campagna Bappenas — comunica "stiamo nello stesso racconto nazionale" senza appropriarsi del marchio governativo.
   *Come renderlo sobrio*: sottile linea di progresso/accent-bar con gradiente oro tenue, usabile in un grafico o in una progress-bar, mai come badge "Indonesia Emas 2045" apposto sull'interfaccia.

9. **Mega Mendung astratto (arco di nuvole concentriche, non il repeat-pattern tessile)**
   *Significato*: calma dentro la tempesta — metafora diretta per "un navigatore che porta ordine dentro 1.559 codici".
   *Perché è adatto/sicuro*: oggi di uso comune (non più riservato ai re), ma da tenere **ben astratto** per non scivolare in "stampa batik decorativa".
   *Come renderlo sobrio*: 2-3 archi concentrici stilizzati (non il repeat a griglia) come piccolo elemento grafico isolato, ad es. accanto a un messaggio di stato "tutto risolto"/nessun errore — non come sfondo esteso.

10. **Fregio geometrico ispirato ai rilievi di Borobudur** (bassa priorità, usare con cautela)
    *Significato*: profondità civilizzazionale, ampiamente usata in contesti istituzionali indonesiani (francobolli, passaporti).
    *Perché è "adatto con cautela"*: patrimonio UNESCO, non regale né settario — ma il rischio di scivolare nel cliché "tempio" è alto se reso pittoricamente.
    *Come renderlo sobrio*: **solo** la fascia ornamentale geometrica ripetuta (meandro/loto astratto), mai una scena narrativa/pittorica del tempio — e solo se serve davvero un tocco "profondità storica" in una sezione editoriale, non nell'app quotidiana.

**Raccomandazione d'insieme**: per un tool funzionale (tabella/ricerca di 1.559 codici), i motivi #1-3 (padi & kapas, tumpal, guilloché) sono i più sicuri da implementare per primi — pertinenza economica diretta, zero rischio culturale, e già testati come registro dal precedente rupiah. I motivi #6-8 (arcipelago, pinisi, arco dorato) sono ottimi per schermate "About"/onboarding dove serve raccontare la missione. I motivi #4-5 e #9 vanno bene come texture di sfondo a bassissima intensità. Il #10 è opzionale/da valutare solo per materiale editoriale, non per l'interfaccia primaria.

---

*File destinazione finale: `/Users/nuzantara/nuzantara/research/design/2026-08-11-kbli-navigator-indonesian-soul.md` (staging attuale: vedi nota operativa in testa al file).*
