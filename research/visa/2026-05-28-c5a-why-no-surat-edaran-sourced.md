---
date: 2026-05-28
domain: visa
client_case: bali-zero-internal-c5a-why-no-surat-edaran
status: draft
author: deep-researcher (Claude Opus 4.7 orchestrator + Gemini 3.1 Pro + DeepSeek V4 Pro + Codex GPT-5.5 + primary fetches)
panel: 3-LLM full this run (Gemini agy Bahasa + DeepSeek V4 Pro legal-mechanics + Codex GPT-5.5 web recon) + direct imigrasi.go.id fetches. Convergent.
redteam: DeepSeek V4 Pro devils-advocate gate, verdict BLOCK→fixes applied (1 critical + 1 high + 2 medium, all addressed in-band).
sources:
  # Tier 1 primary government (fetched this session)
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C5A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C5
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C18
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C19
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C22A
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C7A
  - https://www.imigrasi.go.id/pejabat
  - https://bengkulu.imigrasi.go.id/berita-utama/hendarsam-marantoko-resmi-dilantik-sebagai-direktur-jenderal-imigrasi
  - https://ngurahrai.imigrasi.go.id/imigrasi-bali-amankan-62-wna-bermasalah-pada-patroli-dharma-dewata/
  - https://kemenimipas.go.id/berita-utama/15-program-aksi-kemenimipas-perkuat-poros-kinerja-kemenimipas-2026
  - https://bengkalis.imigrasi.go.id/2026/05/13/dirjen-imigrasi-penangkapan-320-wna-buktikan-pengawasan-berjalan/
  # Tier 2 media
  - https://www.tempo.co/hukum/dirjen-imigrasi-baru-hendarsam-marantoko-dilantik-1-april-2122793
  - https://metro.tempo.co/read/2095707/politikus-gerindra-hendarsam-marantoko-dilantik-sebagai-dirjen-imigrasi
  - https://balinews.id/imigrasi-perketat-pengawasan-konten-sponsor-dan-promosi-dengan-visa-turis-dilarang/
  - https://bali.antaranews.com/berita/404748/imigrasi-bali-jaring-62-wna-selama-operasi-patroli-dharma-dewata
  - https://regional.kompas.com/read/2026/05/06/163223178/62-wna-bermasalah-terjaring-patroli-dharma-dewata-di-bali-terancam
  - https://m.batamtoday.com/berita216127-Yuldi-Yusman-Resmi-Jabat-Plt-Dirjen-Imigrasi-Gantikan-Saffar-Godam.html
  # Legal authority / numbers NOT independently verified this session (see caveats in body)
  - PP 11/2017 Pasal 14 (Plt authority equivalence) — DeepSeek-cited
  - SE MenPANRB 15/2014 (Plt strategic-decision doctrine) — DeepSeek-cited
  - SE Dirjen IMI-417.GR.01.01/2025 — Gemini-cited, NOT independently verified
  - Kepmen M.IP-08.GR.01.01/2025 (C5A creation) — prior-research/prompt-established, NOT re-verified this session
  - SK Presiden 187-188/TPA/2025 (Hendarsam appointment) — media-reported, NOT verified on primary
---

# Perché il Dirjen non ha emesso la Surat Edaran C5A — i motivi

## RISPOSTA DIRETTA

Il motivo più difendibile è una **combinazione di deprioritizzazione + clima enforcement, NON di incapacità sistemica**: la prova decisiva è che **C5A è l'unico indeks dormiente in un campione di 7 indeks adiacenti della serie C, tutti attivi** (C5, C7A, C18, C19, C22, C22A = attivi con dati completi; solo C5A = "Data Belum Tersedia", verificato oggi). Questo isola C5A come **scelta specifica** (Motivo 3 + Motivo 1), non come backlog generico. Il Motivo 2 (Dirjen Plt non firma) è **CONFUTATO** su due fronti: il Plt firmava SE comparabili (C18 e Pendidikan, documentati nella prior research), e da **1 aprile 2026 c'è un Dirjen DEFINITIVO** (Hendarsam Marantoko) — eppure C5A resta fermo, quindi la causa non è il vincolo di poteri dell'acting. **Nessuna dichiarazione ufficiale spiega il ritardo**: il verdetto è la lettura più plausibile delle circostanze documentate, non un fatto dichiarato.

---

## I 5 motivi — status di evidenza

| Motivo                                                     | Status                                    | Fonte / Prova                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Tier                                   |
| ---------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| **1 Transizione istituzionale / deprioritizzazione niche** | **STRONGLY INFERRED**                     | Renstra/15 Program Aksi 2026 prioritizzano Golden Visa/GCI/investitori e digitalizzazione, non indeks niche. Convergenza Gemini + DeepSeek + Codex. Lo split Kemenkumham→Kemenimipas (Perpres 154/2024, 21 ott 2024) crea backlog regolatorio plausibile. NON dichiarato che C5A sia "lasciato indietro" — inferito dalla direzione di policy.                                                                                                                                                                      | secondary gov priorities + inference   |
| **2 Dirjen Plt non firma atti strutturali**                | **CONFUTATO**                             | (a) Yuldi Yusman come Plt firmava SE comparabili (C18 e Pendidikan documentati nella prior research; Gemini cita anche SE IMI-417.GR.01.01/2025 perpanjangan, **MA quel numero NON è verificato indipendentemente**). (b) **Da 1 apr 2026 il Dirjen è DEFINITIVO** (Hendarsam Marantoko) — C5A resta fermo anche con titolare pieno. PP 11/2017 Pasal 14: il Plt ha autorità equivalente salvo limiti espliciti. La confutazione regge sui DUE SE documentati + sul definitivo, NON sull'SE IMI-417 non verificato. | primary (nomina) + legal authority     |
| **3 Volontà politica anti-creator**                        | **STRONGLY INFERRED**                     | Operazione Dharma Dewata (15 apr–4 mag 2026, 62 WNA fermati) + comunicazione Imigrasi 23 mag 2026 (BaliNews/IG ufficiale) che indirizza i creator a **izin kerja / E33G Remote Worker** e NON menziona MAI il C5A — l'indeks creato apposta per loro. Aprire un canale "soft" (visit-visa) per i creator mentre si fa retata sui creator è contraddittorio con la narrativa enforcement. Vedi CAVEAT sotto: la guida E33G è su canale media/IG, non sul comunicato-madre.                                           | secondary gov/media + strong inference |
| **4 Design/enforcement irrisolto (confine income ID)**     | **WEAKLY INFERRED / NO EVIDENCE diretta** | Logicamente plausibile (verificare "no reddito ID" è arduo), e WebSearch riporta una parafrasi di posizione Imigrasi ("ciò che si valuta non è solo se viene pagato, ma scopo/forma/impatto economico") — ma è **parafrasi media, non verbatim governativo**, e nessun risalah DPR Komisi III / draft juknis / dichiarazione trovata che leghi questo nodo specificamente al blocco C5A. Gemini + DeepSeek: NO EVIDENCE diretta.                                                                                    | inference + media paraphrase           |
| **5 Ridondanza con E33G**                                  | **NO EVIDENCE**                           | Sono corsie legali diverse: C5A = Visa Kunjungan (visit, breve, 60gg); E33G = KITAS remote-worker (lungo, ~USD 60k/anno reddito, sponsor). Nessuna regola rende un visit-index ridondante perché esiste un KITAS simile. Nessuna dichiarazione di sovrapposizione. Gemini + DeepSeek concordi: speculativo, scartato.                                                                                                                                                                                               | inference (refuted)                    |

---

## Quanti altri indeks sono nello stesso limbo? (il dato critico)

**Campione empirico verificato oggi 2026-05-28** (fetch diretti alle pagine di dettaglio imigrasi.go.id):

| Indeks  | Stato pagina dettaglio                                     |
| ------- | ---------------------------------------------------------- |
| C5      | **ATTIVO** (no sponsor, 60gg, Rp 2jt, documenti completi)  |
| **C5A** | **"Data Belum Tersedia"** (DORMIENTE — unico del campione) |
| C7A     | **ATTIVO** (30gg, dati completi)                           |
| C18     | **ATTIVO** (sponsor, 90gg, Rp 4jt, documenti)              |
| C19     | **ATTIVO** (60gg, Rp 3jt, dati completi)                   |
| C22     | **ATTIVO** (180gg, dati completi)                          |
| C22A    | **ATTIVO** (180gg, dati completi)                          |

**Lettura del dato (con caveat di portata esplicito)**: il catalogo `daftar-visa-indonesia` elenca ~99 codici come link (A/B/C/D/E series). **Nel campione di 7 indeks adiacenti della serie C, C5A è l'UNICO dormiente; 6 su 7 sono attivi.** Se nelle altre serie (in particolare la serie E, dove indeks di recente conio potrebbero essere anch'essi dormienti) esista una "coda larga" di "Data Belum Tersedia" è **NON VERIFICATO** — lo sweep completo dei ~110 dettagli NON è stato eseguito. La home mostra i codici come link ma NON lo stato dettaglio senza aprire ogni pagina.

**Conseguenza per la diagnosi**: limitatamente alla serie C adiacente, il dato SPOSTA il peso da Motivo 1 puro (capacità sistemica → produrrebbe MOLTI indeks fermi) verso una **causa specifica** del singolo indeks (Motivo 3 enforcement-climate + Motivo 1 come deprioritizzazione mirata di un niche scomodo). Gemini lo dichiara esplicitamente: _"sebab spesifik (pilihan prioritas / penundaan politis), bukan sebab sistemik dari kegagalan IT."_ Questa conclusione è solida per la serie C, NON estesa all'intero catalogo finché non si completa lo sweep.

---

## Dichiarazioni ufficiali (verbatim o "NESSUNA")

- **Sul ritardo C5A specifico: NESSUNA.** Nessuna fonte (siaran*pers Imigrasi, Kemenimipas, media, jdih, sweep Gemini/Codex) contiene una dichiarazione che spieghi perché C5A non è operativo. Codex (solo fonti governative): *"I found no official statement saying C5A has become operational, and no official explanation saying why it is not usable."\_

- **Guida ai creator (verbatim, media-sourced) — BaliNews 23 mag 2026, attribuito a "Ditjen Imigrasi" via IG ufficiale**: i creator/digital worker devono usare _"izin kerja atau visa E33G Remote Worker sebelum datang ke Indonesia"_. **NON menziona C5A.** → prova indiretta più forte del Motivo 3: l'indeks dedicato non viene proposto nemmeno quando il tema è esattamente "che visto deve usare un creator".

- **CAVEAT onesto (sollevato da Codex)**: la pagina UFFICIALE Dharma Dewata di Ngurah Rai (imigrasi.go.id subdomain) NON menziona C5A, E33G, "content creator", Canggu né Ubud — elenca violazioni generiche (overstay, dati falsi, lavoro senza permesso, investimento fittizio). La connessione "creator → E33G non C5A" è documentata sul canale **media/IG**, non sul comunicato-madre. Quindi Motivo 3 è STRONGLY INFERRED, non DOCUMENTED al massimo grado.

- **Dirjen attuale (primario per la carica, numero SK media-reported)**: Hendarsam Marantoko, politico Gerindra + avvocato business-law (HMP Law Firm), _"resmi dilantik sebagai Direktur Jenderal Imigrasi pada Rabu (1/4/2026)"_; serah terima da Plt Yuldi Yusman. La carica + data sono confermate da imigrasi.go.id/pejabat, Tempo, IDN Times, bengkulu.imigrasi.go.id e citate in un articolo Imigrasi del 13 mag 2026 (Hendarsam come Dirjen). Il numero **SK Presiden 187-188/TPA/2025 è media-reported (kemenimipas via WebSearch) e NON verificato verbatim sul primario** — usare la carica come fatto, il numero SK come "media-reported".

---

## Cronologia che spiega il ritardo

- **Mag 2025**: il Kepmen Kemenimipas che crea C5A entra in vigore (numero **M.IP-08.GR.01.01/2025 stabilito dalla prior research/prompt operatore, NON re-verificato su fonte primaria in questa sessione — trattare come unverified finché jdih non confermi**), durante Plt Yuldi Yusman (in carica dal 23 apr 2025).
- **Mag–lug 2025**: indeks comparabili attivati in 1-2 mesi (C18 eff. 14 giu 2025; Pendidikan Non Formal eff. 15 lug 2025) — **MENTRE** lo stesso Plt era in carica. Quindi il ritardo C5A non è "il Plt non firmava".
- **Apr 2024 → mar 2026**: serie di casi creator (Pick Me Trip, Bonnie Blue dic 2025, OnlyFans WNA mar 2026) costruisce il clima enforcement.
- **1 apr 2026**: Dirjen definitivo Hendarsam Marantoko si insedia. C5A ancora dormiente.
- **15 apr–4 mag 2026**: Operazione Dharma Dewata, 62 WNA fermati a Bali.
- **23 mag 2026**: comunicazione Imigrasi indirizza creator a E33G, non C5A.
- **28 mag 2026 (oggi)**: C5A = "Data Belum Tersedia". ~12 mesi dal Kepmen, zero SE, zero rollout.

Il gap non è "lento" (i pari ci mettevano ~18 giorni): è "atto esecutivo mai emesso, attraverso DUE titolari (Plt poi definitivo) e in coincidenza con un'ondata enforcement contro proprio quella categoria".

---

## Verdict: il motivo più difendibile

**Ranking evidence-weighted:**

1. **Motivo 3 (clima enforcement anti-creator) — il più difendibile come MOVENTE ATTUALE.** Status STRONGLY INFERRED. La coincidenza temporale è troppo netta: operazione anti-creator + guida ufficiale a E33G che ignora C5A + indeks isolato fra adiacenti tutti attivi. _Cosa lo proverebbe definitivamente_: una dichiarazione/SE Imigrasi che dica "C5A ditunda/ditahan karena…" o un risalah interno — NON trovata.

2. **Motivo 1 (deprioritizzazione niche post-split) — il più difendibile come CONDIZIONE ABILITANTE.** Status STRONGLY INFERRED. Spiega perché nessuno ha "spinto" C5A: le risorse regolatorie 2025-2026 sono su Golden Visa/GCI/investitori. _Cosa lo proverebbe_: un backlog regolatorio ufficiale che elenchi C5A come "pending" — NON trovato.

3. **Motivo 4 (design/enforcement income ID) — possibile nodo tecnico, ma non documentato.** Status WEAKLY INFERRED. _Cosa lo proverebbe_: draft juknis o hearing DPR Komisi III sul confine income — NON trovato.

4. **Motivo 2 (Dirjen Plt) — CONFUTATO** dai controesempi documentati (C18/Pendidikan) + dal fatto che ora c'è un definitivo e C5A resta fermo. Spiega al massimo una frazione del ritardo _storico_ 2025, non lo stato attuale.

5. **Motivo 5 (ridondanza E33G) — NO EVIDENCE,** scartato (corsie legali diverse).

**Sintesi in una frase**: C5A resta dormiente perché **nessuno ha interesse politico ad attivarlo ora** (clima enforcement, Motivo 3) **e nessuno ha incentivo amministrativo a prioritizzarlo** (niche post-split, Motivo 1) — non perché manchi il potere di firma (Motivo 2 confutato), né per redundanza (Motivo 5), e il nodo tecnico (Motivo 4) è plausibile ma non provato.

---

## Disagreements / open questions

- **Numero Kepmen C5A non re-verificato qui**: M.IP-08.GR.01.01/2025 viene dalla prior research/prompt, non da un fetch primario di questa sessione. Da confermare su jdih quando raggiungibile.
- **Numero SK Presiden Hendarsam (187-188/TPA/2025)**: media-reported, non verificato verbatim sul primario. La CARICA + data (1 apr 2026) sono invece multi-source confermate.
- **Discrepanza panel sulla SE del Plt**: Gemini cita SE IMI-417.GR.01.01/2025 firmata da Yuldi; Codex dice "no SE found". Risolta a favore del punto logico (un Plt FIRMA SE, e ci sono C18/Pendidikan documentati) — ma il numero SE di Gemini NON è verificato indipendentemente. La confutazione di Motivo 2 NON dipende da quel numero.
- **Frase "non solo se viene pagato"**: parafrasi WebSearch, NON verbatim governativo. NON usarla come citazione ufficiale.
- **Guida E33G > C5A**: documentata su media/IG, non sul comunicato-madre Dharma Dewata. Motivo 3 quindi STRONGLY INFERRED, non DOCUMENTED puro.
- **Campione indeks = 7, non 110**: la tesi "C5A isolato" è solida per la serie C adiacente, non esaustiva sull'intero catalogo. Open: sweep completo dei ~110 dettagli.
- **Nessuna prova diretta che il ritardo sia "volontario" vs "trascurato"**: Motivo 3 (volontà) e Motivo 1 (priorità) sono entrambi STRONGLY INFERRED e non mutuamente esclusivi; nessuna fonte dice quale pesa di più.

---

## Checklist for action

- [ ] **NON vendere C5A come prodotto** — confermato: "Data Belum Tersedia" oggi, zero SE, retata in corso sulla categoria. Indirizzare i content creator a **E33G Remote Worker** (è ciò che Imigrasi stessa raccomanda, 23 mag 2026).
- [ ] **Monitor del trigger reale di operatività**: cercare settimanalmente su `imigrasi.go.id/siaran_pers` un titolo "WNA Bisa Mengajukan Visa Konten Kreator / C5A Mulai [data]" — quello (non la pagina daftar-visa) è il segnale di attivazione. Improbabile finché Dharma Dewata è attiva.
- [ ] **Re-leggere il clima sotto Hendarsam Marantoko**: è un avvocato business-law di Gerindra, non un enforcer di carriera come Yuldi. Verificare se nei prossimi 3-6 mesi sposta la linea verso facilitazione (Golden Visa-style) — un suo eventuale pivot pro-business sarebbe il primo segnale plausibile di sblocco C5A.
- [ ] **Completare l'enumerazione indeks** (chiudere il caveat): sweep dei dettagli serie D/E per confermare che C5A è davvero fra i pochi dormienti e non in una coda larga (cambierebbe il peso Motivo 1 vs Motivo 3).
- [ ] **Verificare i 2 numeri unverified su jdih** quando raggiungibile: Kepmen M.IP-08.GR.01.01/2025 (creazione C5A) e SK Presiden 187-188/TPA/2025 (nomina Hendarsam).
- [ ] **Domanda scritta al Kanim Ngurah Rai/Denpasar** (via team): "Apakah indeks C5A sudah ada Surat Edaran Dirjen dan bisa diproses?" — l'unica via per una conferma di prima mano.

---

## Fonti per tier

### Tier 1 — Primary government (fetched/verificati questa sessione)

1. Pagina C5A — https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C5A — "Data Belum Tersedia" (2 fetch, oggi).
2. Catalogo indeks (~99 codici elencati) — https://www.imigrasi.go.id/wna/daftar-visa-indonesia
   3-7. Pagine dettaglio C5 / C7A / C18 / C19 / C22A — tutte ATTIVE con dati completi (fetch oggi). Prova del campione "C5A isolato" (serie C).
3. Pejabat Imigrasi — https://www.imigrasi.go.id/pejabat — Hendarsam Marantoko = Dirjen definitivo (via Codex).
4. Nomina Hendarsam (primario) — https://bengkulu.imigrasi.go.id/berita-utama/hendarsam-marantoko-resmi-dilantik-sebagai-direktur-jenderal-imigrasi
5. Dharma Dewata ufficiale Ngurah Rai — https://ngurahrai.imigrasi.go.id/imigrasi-bali-amankan-62-wna-bermasalah-pada-patroli-dharma-dewata/ — 62 WNA; NON menziona C5A/E33G/creator (caveat Motivo 3).
6. 15 Program Aksi 2026 Kemenimipas — https://kemenimipas.go.id/berita-utama/15-program-aksi-kemenimipas-perkuat-poros-kinerja-kemenimipas-2026 — priorità Golden Visa/GCI/digitale (Motivo 1).
7. Articolo Imigrasi 13 mag 2026 (cita Hendarsam come Dirjen) — https://bengkalis.imigrasi.go.id/2026/05/13/dirjen-imigrasi-penangkapan-320-wna-buktikan-pengawasan-berjalan/

### Tier 2 — Mainstream media

13. Tempo — Hendarsam dilantik 1 apr 2026 — https://www.tempo.co/hukum/dirjen-imigrasi-baru-hendarsam-marantoko-dilantik-1-april-2122793
14. Tempo (profilo Gerindra) — https://metro.tempo.co/read/2095707/politikus-gerindra-hendarsam-marantoko-dilantik-sebagai-dirjen-imigrasi
15. BaliNews 23 mag 2026 — guida creator a E33G, no C5A — https://balinews.id/imigrasi-perketat-pengawasan-konten-sponsor-dan-promosi-dengan-visa-turis-dilarang/
16. ANTARA Bali — Dharma Dewata 62 WNA — https://bali.antaranews.com/berita/404748/imigrasi-bali-jaring-62-wna-selama-operasi-patroli-dharma-dewata
17. Kompas — 62 WNA Dharma Dewata — https://regional.kompas.com/read/2026/05/06/163223178/62-wna-bermasalah-terjaring-patroli-dharma-dewata-di-bali-terancam
18. BatamToday — Yuldi Yusman Plt dal 23 apr 2025, background enforcement — https://m.batamtoday.com/berita216127-Yuldi-Yusman-Resmi-Jabat-Plt-Dirjen-Imigrasi-Gantikan-Saffar-Godam.html

### Legal authority / numeri NON verificati indipendentemente (vedi caveat nel corpo)

19. PP 11/2017 Pasal 14 — Plt ha autorità equivalente al titolare salvo limiti espliciti (DeepSeek-cited).
20. SE MenPANRB 15/2014 — dottrina "Plt evita decisioni strategiche" (general doctrine, non codificata in UU 30/2014; DeepSeek-cited).
21. SE Dirjen IMI-417.GR.01.01/2025 — perpanjangan foto+wawancara, firmata da Yuldi come Plt (Gemini-cited, **UNVERIFIED**).
22. Kepmen M.IP-08.GR.01.01/2025 — creazione C5A (prior-research/prompt-established, **NON re-verificato questa sessione**).
23. SK Presiden 187-188/TPA/2025 — nomina Hendarsam (media-reported kemenimipas via WebSearch, **non verificato verbatim sul primario**).

### Prove di ASSENZA

- Nessuna dichiarazione ufficiale sul ritardo C5A (Codex su sole fonti gov + Gemini sweep = NOT FOUND / TIDAK DITEMUKAN).
- Nessun draft juknis / risalah DPR Komisi III sul confine income C5A (Motivo 4).
- Nessuna dichiarazione di ridondanza C5A↔E33G (Motivo 5).
- jdih.imigrasi.go.id NON interrogato questa sessione (residuo incertezza sull'assenza assoluta di una SE non indicizzata + sui 2 numeri unverified).

### Panel artifacts (in-session, non committati)

- `/tmp/c5a-why-se/agy-output.txt` — Gemini 3.1 Pro (37 righe, Bahasa).
- `/tmp/c5a-why-se/deepseek-output.txt` — DeepSeek V4 Pro legal-mechanics (52 righe).
- `/tmp/c5a-why-se/codex-output.txt` — Codex GPT-5.5 web recon (45 righe, sole fonti gov).
- `/tmp/c5a-why-se/dev-raw.json` — DeepSeek devils-advocate red-team verdict (BLOCK→fixes applied).
