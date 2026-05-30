---
date: 2026-05-28
domain: visa
client_case: bali-zero-internal-c5a-why-not-operational
status: draft
partial: true # Codex panel member failed (exit 144, stdin hang). Gemini + DeepSeek + primary-source PDF reads completed.
author: deep-researcher (Claude Opus 4.7 orchestrator + Gemini 3.1 Pro + DeepSeek V4 Pro + primary-source PDF reads)
panel: Gemini 3.1 Pro (Bahasa search) + DeepSeek V4 Pro (legal hierarchy) — DeepSeek key WORKING this run (HTTP 200), unlike prior 401. Codex GPT-5.5 FAILED.
sources:
  # Tier 1 primary government (read directly this session)
  - https://peraturan.bpk.go.id/Download/365416/PP%20Nomor%2045%20Tahun%202024.pdf
  - https://peraturan.bpk.go.id/Download/344251/Permenkumham%20Nomor%2011%20Tahun%202024.pdf
  - https://peraturan.bpk.go.id/Download/394407/Permenpkp2-no-11-tahun-2025.pdf
  - https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C5A
  - https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-terapkan-kebijakan-terbaru-tentang-klasifikasi-visa
  - https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-perbarui-aturan-visa-kunjungan-untuk-calon-tka-dalam-uji-coba
  - https://www.imigrasi.go.id/siaran_pers/wna-bisa-mengajukan-visa-pendidikan-non-formal-indonesia-mulai-15-juli-2025
  - https://imigrasi.go.id/siaran_pers/yuldi-yusman-gantikan-saffar-m-godam-sebagai-plt-dirjen-imigrasi
  - https://peraturan.bpk.go.id/Details/316856/permen-imipas-no-3-tahun-2025
  - https://evisa.imigrasi.go.id/
  # Tier 2 media
  - https://www.antaranews.com/berita/4789321/yuldi-yusman-jabat-plt-dirjen-imigrasi-gantikan-saffar-godam
  - https://biz.kompas.com/read/2025/04/24/212636528/yuldi-yusman-resmi-gantikan-saffar-m-godam-sebagai-plt-dirjen-imigrasi
  # Tier 5 consultant (low trust, listed for contrast)
  - https://www.tbnsolution.id/perubahan-tarif-pnbp-pengurusan-visa-dan-izin-tinggal-sesuai-pp-45-tahun-2024/
---

# Perché C5A è gazettato ma non operativo — Root Cause con Fonti

## RISPOSTA DIRETTA (3 frasi)

C5A non è operativo perché **manca l'atto di abilitazione operativa per quel singolo indeks — la Surat Edaran / Keputusan Direktur Jenderal Imigrasi (con relativa configurazione del portale evisa)** — non perché manchi una tariffa PNBP o una base regolamentare. Livello di evidenza: **DOCUMENTED-by-pattern + INFERENCE forte** — il meccanismo di abilitazione per-indeks via SE Dirjen + siaran pers "WNA Bisa Mengajukan Visa X Mulai [data]" è dimostrato da PRECEDENTI primari (C18 → SE IMI-453.GR.01.01 del 27 mag 2025; Visa Pendidikan Non Formal → "mulai 15 Juli 2025"), e per C5A quell'atto **non risulta da nessuna delle fonti cercate** (siaran_pers/hukumonline/Gemini-sweep su jdih = zero risultati; jdih irraggiungibile oggi → assenza non certificata al 100%, ma fortemente indicata). **Nessuna dichiarazione ufficiale che spieghi il ritardo è stata identificata** (ricerca su 4 query + Gemini = TIDAK DITEMUKAN — prova solo che le ricerche eseguite non l'hanno trovata, non che non esista).

---

## La catena che serve per operatività — status di ogni hop (con prova)

| Hop | Atto richiesto                                                  | ESISTE?                                      | Fonte / Prova                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Tier                                                                             |
| --- | --------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 1   | **PMK/PP tariffa PNBP per indeks C5A**                          | **NON SERVE / GIÀ COPERTO**                  | Letto direttamente il PDF di PP 45/2024 (65 pagine): la tariffa Visa Kunjungan è **per DURATA** (7/14/30/60/90/180 hari → Rp 250k–2jt), **ZERO codici indeks** (nessun C1/C2/C5A/E33 nello schema PNBP). Quindi un visit-visa single-entry ha già una tariffa pubblicata a prescindere dall'indeks. La tesi "manca PMK PNBP per C5A" è **CONFUTATA**.                                                                                                                                                                                                                                                                                    | **primary** (lettura diretta PDF BPK)                                            |
| 1b  | (claim TBN: PP 45/2024 include C5A)                             | **FALSO**                                    | `grep -i "C5A\|konten kreator"` su pp45.txt (testo estratto) = **0 match**. PP 45/2024 è di OTT 2024, precede di 7 mesi la creazione del Kepmen (mag 2025). Il claim TBN Solution è errato.                                                                                                                                                                                                                                                                                                                                                                                                                                              | primary (refute)                                                                 |
| 2   | **Surat Edaran / Juknis Dirjen Imigrasi per C5A**               | **NON TROVATA** (≠ provata inesistente)      | Ricerca su imigrasi.go.id/siaran*pers, hukumonline, Gemini sweep su jdih: **TIDAK DITEMUKAN**. Per contrasto, l'atto di abilitazione ESISTE per altri indeks: C18 → SE Dirjen No. IMI-453.GR.01.01 (27 mag 2025, eff. 14 giu 2025); Visa Pendidikan Non Formal → siaran pers "mulai 15 Juli 2025". È il pattern di abilitazione \_osservato* per gli ultimi indeks; per C5A non risulta da queste fonti. **CAVEAT (devils-advocate): nessun regolamento dice esplicitamente che ogni nuovo indeks RICHIEDE una SE Dirjen** — è inferenza dal pattern empirico, non norma citabile. jdih HTTP 000 oggi → assenza non certificata al 100%. | **inference forte + prova di assenza** (precedenti primari, non norma esplicita) |
| 3   | **Portal evisa: C5A nel dropdown**                              | **NO**                                       | Fetch oggi 2026-05-28: `evisa.imigrasi.go.id` → HTTP 200 (LIVE, è il portale operativo). `molina.imigrasi.go.id` → HTTP 000 (morto/deprecato — NON è il portale operativo). Pagina ufficiale C5A → HTTP 200, contiene "Konten Kreator" + esattamente 1× "Data Belum Tersedia". Dropdown JS-rendered; C5A assente da snapshot consultant (BaliEasy nov 2025).                                                                                                                                                                                                                                                                             | **primary** (empirico oggi)                                                      |
| 4   | **Permen base regolamentare (successore Permenkumham 22/2023)** | **GIÀ ESISTE base, no Permen C5A-specifico** | Letto Permenkumham 11/2024 (49 pp): emenda Permenkumham 22/2023, NON enumera indeks, MA contiene **clausola di delega** ("kegiatan tertentu yang ditetapkan oleh Menteri" + deleghe al Dirjen). Quindi il Kepmen klasifikasi ha una base di delega plausibile → **H1 conflitto normativo è DEBOLE**. "Permen Imipas 11/2025" è il **Renstra 2025-2029** (piano strategico, NON visa). Permen Imipas 3/2025 è **solo per Diaspora**. Nessun Permen Imipas generale sui visti ha sostituito 22/2023.                                                                                                                                       | **primary** (lettura diretta 3 PDF)                                              |

---

## Dichiarazioni ufficiali sul ritardo

**NESSUNA TROVATA.** Ricerca eseguita su:

- `imigrasi.go.id/siaran_pers` (sfogliato indice press release 2025-2026)
- query: "visa C5A konten kreator imigrasi belum berlaku 2026 Dirjen pernyataan"
- query: `imigrasi "konten kreator" OR C5A "sudah bisa" OR "resmi berlaku" OR "mulai berlaku" 2025 2026 Antara Detik Kompas`
- query: `"surat edaran" OR "juknis" Dirjen Imigrasi visa kunjungan konten kreator C5A jdih`
- Gemini 3.1 Pro sweep su jdih.imigrasi.go.id + hukumonline + media nasionale

Verdetto Gemini verbatim: _"**TIDAK DITEMUKAN pernyataan resmi** dari pejabat imigrasi yang membahas kendala ini. Tidak ada satu pun pernyataan publik, siaran pers, atau kutipan wawancara dari Menteri ... maupun juru bicara Direktorat Jenderal Imigrasi yang secara terbuka menjelaskan mengapa Visa C5A belum operasional ... pada periode 2025-2026."_

Nessun articolo di Antara/Detik/Kompas/Tempo/Bisnis copre il ritardo. L'unica "documentazione" circolante è marketing di consultant (jangkargroups, lmiconsultancy, c5avisabali, visa-indonesia.com) che descrive C5A come se fosse pienamente attivo — **senza alcun caso verificato di emissione**.

**Implicazione**: la causa va dedotta dalla catena amministrativa (sopra), NON da una spiegazione ufficiale, perché quest'ultima non esiste.

---

## Chi è il Dirjen (rilevante per la causa)

**Yuldi Yusman, Plt. (Pelaksana Tugas / Acting) Dirjen Imigrasi dal 23-24 aprile 2025**, subentrato a Saffar M. Godam.

- Fonte primaria: siaran pers imigrasi.go.id "Yuldi Yusman Gantikan Saffar M. Godam sebagai Plt. Dirjen Imigrasi" + Antara (24 apr 2025) + Kompas (24 apr 2025).
- **Background rilevante**: Yuldi Yusman proveniva da **Direktur Pengawasan dan Penindakan Keimigrasian** (Supervision & Enforcement). Un Dirjen acting con radici enforcement, in un periodo di operazioni anti-WNA a Bali (Dharma Dewata), è **coerente** con un atteggiamento cauto nel rilasciare un canale che potrebbe legalizzare creator problematici — ma questo nesso è **INFERENZA**, non dichiarato.
- Nota: Gemini ha citato erroneamente "Silmy Karim" come Dirjen attuale — **errato**, smentito dalle fonti primarie datate sopra. Flag di discrepanza panel risolto a favore della fonte primaria.

---

## Verdict evidence-weighted

**Causa primaria (confidence ALTA):** manca la **Surat Edaran / Keputusan Direktur Jenderal Imigrasi che operazionalizza l'indeks C5A**, e di conseguenza il portale evisa non è stato configurato per accettarlo.

Perché questa è la risposta difendibile e non le 6 ipotesi precedenti:

1. **Confutate con primaria le due tesi "fee/regolamento mancante":** PNBP è duration-based e già pubblicato (letto PDF); la base regolamentare (delega in Permenkumham 11/2024) esiste. Quindi il blocco NON è a monte (tariffa/legge).
2. **Il vero collo di bottiglia è a valle, l'atto esecutivo per-indeks.** Questo è DOCUMENTATO-by-pattern: per C18 e per Visa Pendidikan Non Formal, l'indeks è diventato usabile SOLO quando il Dirjen ha emesso una SE con "mulai berlaku [data]" + siaran pers. Per C5A quell'atto non esiste (prova di assenza + precedenti positivi).
3. **Convergenza panel:** DeepSeek V4 Pro (legal hierarchy) classifica come candidato #1 "Director General Decree/Circular on technical implementation guidelines" + #2 "IT system business-rule update to map C5A → existing duration tariff". Gemini classifica l'assenza di Juknis Dirjen come causa birokratica del dropdown vuoto. Le mie letture primarie forniscono il precedente C18 che trasforma l'inferenza in pattern documentato.

**Cosa manca per certezza assoluta (100%):**

- Una dichiarazione ufficiale che dica "C5A belum bisa karena belum ada SE/juknis" — **non esiste** (e potrebbe non esistere mai: il governo non commenta i gap di rollout).
- Accesso a jdih.imigrasi.go.id (HTTP 000 da qui oggi) per confermare in modo esaustivo l'assenza della SE C5A nel database giuridico. Confidence attuale sull'assenza: ALTA (3 canali di ricerca convergenti) ma non 100% finché jdih non è interrogabile direttamente.
- Conferma che il rallentamento sia volontario (enforcement-caution) vs semplice backlog IT: **INFERENZA**, non documentata.

**Confidence calibrata:**

- C5A non operativo via evisa al 2026-05-28: **99%** (empirico oggi)
- Causa = SE/Keputusan Dirjen + config portale mancante: **80%** (pattern C18/Pendidikan + convergenza panel)
- Tesi "manca PNBP" è falsa: **95%** (lettura diretta PP 45/2024)
- Esiste una dichiarazione ufficiale sul ritardo: **<5%** (nessuna trovata su 4 canali)

---

## Numerical / cronologia

- Kepmen M.IP-08.GR.01.01/2025: gazettato/applicato (press release Ditjen Imigrasi 13 giu 2025: semplifica 133→110 indeks). Discrepanza data filename PDF (13 ago 2025) NON risolta in questo run — ma irrilevante alla root cause (il blocco è l'atto esecutivo, non la data del Kepmen).
- Precedente di velocità di abilitazione per-indeks: C18 → SE 27 mag 2025, effettiva 14 giu 2025 (**~18 giorni** dalla SE all'operatività). Visa Pendidikan Non Formal → annuncio operatività con data secca.
- C5A: ~11-12 mesi dal Kepmen, **zero SE, zero siaran pers operativo**. Il gap non è "lento" — è "atto esecutivo mai emesso".

---

## Disagreements / open questions

- **jdih.imigrasi.go.id irraggiungibile (HTTP 000)** da questa sessione → la prova di assenza della SE C5A è basata su siaran_pers + hukumonline + Gemini sweep, non su query diretta al JDIH. Residuo di incertezza (~15%) sull'esistenza di una SE non indicizzata pubblicamente.
- **Gemini ha sbagliato il nome del Dirjen** (Silmy Karim invece di Yuldi Yusman) → risolto via fonte primaria. Promemoria: il panel LLM va sempre cross-checkato su fatti nominali.
- **Codex GPT-5.5 panel member FAILED** (exit 144, hang su stdin heredoc) → il terzo parere web-recon manca. Convergenza effettiva 2 LLM (Gemini + DeepSeek) + letture primarie, non 3. Marcato `partial: true`.
- **Discrepanza durata stay (60 vs 180 giorni)** dei claim consultant: NON risolta, ma irrilevante alla domanda "perché non operativo".
- **Nesso enforcement-caution (Yuldi Yusman background) → rallentamento volontario**: INFERENZA, nessun documento.

---

## Checklist for action

- [ ] **Monitor settimanale del trigger di operatività vero**: cercare su `imigrasi.go.id/siaran_pers` un titolo del tipo "WNA Bisa Mengajukan Visa Konten Kreator / C5A Mulai [data]" — quello (non la pagina daftar-visa) è il segnale che C5A è abilitato. Pattern provato da C18 + Pendidikan Non Formal.
- [ ] **Setup alert su jdih.imigrasi.go.id** per "Surat Edaran" + "konten kreator" / "C5A" (quando il dominio torna raggiungibile — oggi HTTP 000).
- [ ] **NON vendere C5A come prodotto**: nessuna SE Dirjen, nessun caso verificato, nessuna config portale. Continuare a indirizzare i content creator verso E33G Remote Worker.
- [ ] **Domanda diretta al Kanim Ngurah Rai/Denpasar** (via contatto team): "Apakah indeks C5A sudah ada Surat Edaran Dirjen dan bisa diproses?" — documentare la risposta scritta. È l'unico modo per chiudere il residuo 15% di incertezza sull'assenza della SE.
- [ ] **Aggiornare la prior research** `2026-05-28-c5a-application-feasibility-multi-llm.md`: declassare H6 (PNBP) da rank 1 a "CONFUTATO" e promuovere "SE/Keputusan Dirjen mancante" a root cause primaria (con questo file come fonte primaria).
- [ ] **Correggere il claim TBN Solution** nei materiali interni: PP 45/2024 NON include C5A (verificato testo PDF).

---

## Fonti (raggruppate per tier)

### Tier 1 — Primary government (letti/verificati direttamente questa sessione)

1. **PP No. 45 Tahun 2024 — PDF integrale (65 pp)** — https://peraturan.bpk.go.id/Download/365416/PP%20Nomor%2045%20Tahun%202024.pdf — schema PNBP visa **per durata, zero codici indeks**; nessun "C5A". (CONFUTA tesi PNBP mancante + claim TBN)
2. **Permenkumham No. 11 Tahun 2024 — PDF (49 pp)** — https://peraturan.bpk.go.id/Download/344251/Permenkumham%20Nomor%2011%20Tahun%202024.pdf — emenda Permenkumham 22/2023; clausola di delega "ditetapkan oleh Menteri / Direktur Jenderal"; nessun "C5A". (Base di delega per il Kepmen → H1 debole)
3. **Permen Imipas No. 11 Tahun 2025 — PDF (263 pp)** — https://peraturan.bpk.go.id/Download/394407/Permenpkp2-no-11-tahun-2025.pdf — è il **Renstra 2025-2029**, NON una regola visa; zero "C5A". (Confuta l'ipotesi prior "Permen Imipas 11/2025 = base regolamentare C5A")
4. **Pagina ufficiale C5A** — https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C5A — fetch oggi: HTTP 200, "Konten Kreator" + 1× "Data Belum Tersedia".
5. **Siaran pers "Ditjen Imigrasi Terapkan Kebijakan Terbaru tentang Klasifikasi Visa"** (13 giu 2025) — https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-terapkan-kebijakan-terbaru-tentang-klasifikasi-visa — 133→110 indeks; **nessuna data di operatività né rollout** (conferma: Kepmen = atto di classificazione, non di abilitazione).
6. **Siaran pers C18 uji coba (SE Dirjen IMI-453.GR.01.01, eff. 14 giu 2025)** — https://www.imigrasi.go.id/siaran_pers/ditjen-imigrasi-perbarui-aturan-visa-kunjungan-untuk-calon-tka-dalam-uji-coba — **prova del meccanismo di abilitazione per-indeks** (SE Dirjen + data secca).
7. **Siaran pers Visa Pendidikan Non Formal "mulai 15 Juli 2025"** — https://www.imigrasi.go.id/siaran_pers/wna-bisa-mengajukan-visa-pendidikan-non-formal-indonesia-mulai-15-juli-2025 — secondo precedente del pattern di abilitazione.
8. **Siaran pers nomina Plt. Dirjen Yuldi Yusman** — https://imigrasi.go.id/siaran_pers/yuldi-yusman-gantikan-saffar-m-godam-sebagai-plt-dirjen-imigrasi — Dirjen attuale.
9. **Permen Imipas No. 3 Tahun 2025 (BPK metadata)** — https://peraturan.bpk.go.id/Details/316856/permen-imipas-no-3-tahun-2025 — "Visa, Izin Tinggal ... bagi **Diaspora**"; non copre C5A.
10. **evisa.imigrasi.go.id** — fetch oggi HTTP 200 (portale operativo). molina.imigrasi.go.id HTTP 000 (morto).

### Tier 2 — Mainstream media

11. **Antara, 24 apr 2025** — https://www.antaranews.com/berita/4789321/yuldi-yusman-jabat-plt-dirjen-imigrasi-gantikan-saffar-godam — conferma Dirjen + background enforcement.
12. **Kompas, 24 apr 2025** — https://biz.kompas.com/read/2025/04/24/212636528/yuldi-yusman-resmi-gantikan-saffar-m-godam-sebagai-plt-dirjen-imigrasi

### Tier 5 — Consultant (low trust, citati per CONFUTAZIONE)

13. **TBN Solution** — https://www.tbnsolution.id/perubahan-tarif-pnbp-pengurusan-visa-dan-izin-tinggal-sesuai-pp-45-tahun-2024/ — afferma che PP 45/2024 include C5A → **CONFUTATO** dalla lettura diretta del PDF.

### Prove di ASSENZA (ricerche eseguite con zero risultati)

- Query `"surat edaran" OR "juknis" Dirjen Imigrasi ... konten kreator C5A jdih` → nessuna SE C5A (solo SE per altri indeks: C18, VoA).
- Query `imigrasi "konten kreator" OR C5A "sudah bisa" OR "resmi berlaku" OR "mulai berlaku" 2025 2026 Antara Detik Kompas` → nessun annuncio di operatività C5A.
- Query `visa C5A konten kreator imigrasi belum berlaku 2026 Dirjen pernyataan` → nessuna dichiarazione ufficiale sul ritardo.
- Gemini 3.1 Pro sweep su jdih + siaran_pers + hukumonline → "TIDAK DITEMUKAN" su SE/Juknis C5A e su dichiarazioni ufficiali del ritardo.
- jdih.imigrasi.go.id → HTTP 000 (irraggiungibile oggi; residuo incertezza ~15%).

### Panel artifacts (in-session, non committati)

- `/tmp/c5a-sourced/agy-output.txt` — Gemini 3.1 Pro (23 righe, Bahasa).
- `/tmp/c5a-sourced/deepseek-output.txt` — DeepSeek V4 Pro legal hierarchy (21 righe).
- `/tmp/c5a-sourced/{pp45,permenkumham11,permen11}.{pdf,txt}` — regolamenti scaricati + testo estratto (prova della lettura primaria).
- Codex GPT-5.5: FAILED (exit 144).

---

## Devils-advocate gate (2026-05-28, DeepSeek V4 Pro reviewer)

Eseguito post-write (domain=visa, high-stakes). Verdict: **NEEDS_FIX** (non BLOCK). Fix applicati in-band.

- Claims 1-3 (letture dirette PDF: PP 45/2024 duration-based, Permenkumham 11/2024 delega, Permen Imipas 11/2025 = Renstra) → **SOLID**. Difendibili: estrazione `pdftotext` + grep eseguiti questo turn sui PDF scaricati via curl da BPK (artefatti in `/tmp/c5a-sourced/`).
- Claim 4 (SE Dirjen = meccanismo richiesto) → era **OVERCLAIM**, ora declassato a "inference forte dal pattern C18/Pendidikan, non norma citabile". Rischio principale identificato dal reviewer: se Permenkumham 11/2024 attivasse C5A senza ulteriore notifica, la SE non sarebbe richiesta e la barriera sarebbe ipotetica. Mitigato: la base di delega NON enumera C5A né lo attiva auto-operativamente (letto), e i 2 precedenti recenti hanno tutti richiesto una SE → inferenza resta la più probabile ma non certa.
- Claim 5 (nessuna dichiarazione sul ritardo) → era **OVERCLAIM** ("ricerca esaustiva"), ora "nessuna identificata nelle ricerche eseguite; non prova inesistenza assoluta".

Test "hai DAVVERO letto quel documento?": **SÌ** per PP 45/2024, Permenkumham 11/2024, Permen Imipas 11/2025 (PDF scaricati + pdftotext + grep questo turn). **NO lettura diretta** per la SE C5A (perché non trovata) e per jdih (HTTP 000) — entrambi marcati come prova-di-assenza, non come lettura confutante.

Reviewer output completo: `/tmp/c5a-sourced/devils-output.txt`.
