# Prompt per sessione Claude Code parallela — C5A Step 1 follow-up

> **Per**: Claude Code session su Pro machine (`nuzantara@Nuzantara`)
> **Da**: Antonello via Claude Opus 4.7 session 2026-05-26
> **Workdir di riferimento**: `/Users/nuzantara/Desktop/nuzantara/` (main branch)
> **File da modificare**: `research/visa/2026-05-26-c5a-content-creator-deep-research.md` (su branch `docs/visa-c5a-research-2026-05-26`, PR #877 aperto)
> **Branch handoff**: `git fetch && git checkout docs/visa-c5a-research-2026-05-26 && git pull`
> **Output finale**: commit + push su stesso branch → aggiorna PR #877

---

## Coordinate operative

| Aspetto | Valore |
|---|---|
| **Macchina** | Pro (`Nuzantara` hostname, M4 Pro 48GB) |
| **User** | `nuzantara` (whoami) |
| **Branch attivo PR #877** | `docs/visa-c5a-research-2026-05-26` |
| **Sibling-work in corso** | `fix/wa-mirror-12bug-batch-2026-05-26` (NON toccare, ha 5 file dirty modifiche altrui) |
| **Worktree disciplina** | NON necessario per questo task (3 edit chirurgici al singolo file research, no codice prod) |
| **Frontmatter `sources: 32`** | Aggiornare a `sources: N` (counter post-task) se aggiungi nuove fonti |
| **MEMORY.md update** | NON serve nuovo entry — append 1-line aggiornamento status al record esistente in `MEMORY_RESEARCH_CAPTURES.md` |

---

## Task — 3 edit chirurgici al dossier C5A

Il dossier è strutturato in 12 sezioni + 6 appendici (A-F). Devi modificare:

### TASK 1 — Layer GOSSIP §6: aggiungere interpretazione "aumm aumma"

**Trigger**: zero casi pubblici "creator on C5A challenged for activities" è SEGNALE, non rumore. Due ipotesi simmetriche da formalizzare.

**Cosa scrivere** (append alla fine di §6 prima del callout finale):

```markdown
### 6.4 — Lo zero come segnale [GOSSIP-UNVERIFIED-PLAUSIBLE]

**Osservazione empirica 2026-05-26**: tra le query WebSearch + Reddit + FB + IG eseguite (Appendix B + D), **zero casi pubblici identificati di "creator on C5A challenged for activities"**. Né deportazioni, né detenzioni, né enforcement event riportato in stampa o social. Per un visto attivo da 11 mesi (giu 2025 → mag 2026), in un paese con Dharma Dewata Task Force attiva e 165 deportazioni Q1 2026, lo zero è eloquente.

**Due interpretazioni simmetriche [GOSSIP-UNVERIFIED-PLAUSIBLE]**:

| | Interpretazione (I) — **Zero emissioni** | Interpretazione (II) — **Zero violazioni visibili** |
|---|---|---|
| Tesi | Pochissimi C5A emessi finora (forse <100 totali nazionali). Zero target perché zero universe. | Molti C5A emessi MA tutte le violazioni risolte fuori dalla luce pubblica via agency-mediation ("aumm aumma" pattern) |
| Meccanismo | Pagina ufficiale "Data Belum Tersedia" → agency non sanno processare → applicazioni manuali rare via Kantor Denpasar | Influencer posta su IG → Imigrasi nota → invita per "chiarimento" → agency interviene come mediator → settlement amministrativo senza atto pubblico |
| Indicatore atteso se vero | Statistiche Ditjen Imigrasi "C5A emessi 2025" molto basse (richiederebbe FOIA/PPID query) | Conversazioni informali con agenzie locali (PT-PMA dispatcher visa) rivelano case-by-case mediation |
| Plausibilità | Alta — pagina ufficiale gap, press release zero menzioni operative C5A | Alta — pattern indonesiano standard di "lebih baik selesai damai daripada heboh" applicato all'immigration enforcement quando il violator è "soft-power asset" (creator con audience) |
| Implicazione Bali Zero | Marketing C5A = pioneering, primo-mover advantage | Marketing C5A = positioning come mediator istituzionale (NON public claim) |

**Caveat operativo**: Bali Zero NON deve mai esplicitare in comunicazione pubblica (Step 2 media) l'interpretazione (II). È intelligence operativa interna, **non claim pubblicabile**. Se vera, la sua menzione esplicita compromette il meccanismo stesso (Imigrasi non gradisce agency che "spoilerano" la pratica della mediazione informale).

**Ipotesi convergenti su come testare empiricamente** (Step 2 follow-up):
1. PPID request a Ditjen Imigrasi: "Statistik penerbitan visa indeks C5A periode Juni 2025 – Mei 2026" → conferma/smentisce (I)
2. Conversazioni informali con 3-5 agency Bali competitor (Emerhub, LMI, Flado, Christian Teo) → cercare hint di pattern (II) senza chiedere direct
3. Monitor IG Stories di creator stranieri Bali noti per cambi recenti di visa status (es: chi era C1 a marzo e ora ha "long-stay" non specificato a giugno → C5A pilot pioneer?)

[OPINIONE — discreta] Più probabile (I) ATTUALMENTE, evoluzione verso (II) probabile entro 12 mesi man mano che agenzie battle-testano il workflow.
```

**Dove inserirlo**: cerca la riga `[GOSSIP-UNVERIFIED-PLAUSIBLE]: la community digitale è TUTTA al second-level` in §6 — aggiungi la nuova sotto-sezione `6.4` **prima** di quella riga conclusive (così resta come callout finale di §6).

---

### TASK 2 — Servizio #2 (§9): costi/requirements REALI, no [SPECULATIVE]

**Trigger**: Antonello ha richiesto chiaro su C5A pricing/requirements, non supposizioni.

**3-step execution**:

#### Step 2.A — Telefonata Kantor Imigrasi Kelas I Denpasar
- Numero: cerca su `denpasar.imigrasi.go.id` (probabilmente `(0361) 751038` o variant 2026)
- Domande structured:
  1. "Apakah saat ini Kantor Imigrasi Denpasar memproses aplikasi visa indeks **C5A** (Visa Kunjungan Konten Kreator)?" → yes/no/manual-only
  2. "Berapa biaya PNBP visa C5A untuk 60 hari pertama?" → IDR amount
  3. "Apakah perpanjangan visa C5A maksimum 1× (60+60=120 hari) atau 2× (60+60+60=180 hari)?" → 120 vs 180
  4. "Apakah sponsor harus PT/PT PMA terdaftar, atau bisa Penjamin Perorangan (individu WNI)?" → entity vs individual
  5. "Apakah aplikasi C5A bisa diajukan via portal eVisa atau hanya manual via Kantor?" → eVisa vs manual
- Output: tabella verbatim risposte + nome operatore + data/ora call

#### Step 2.B — PPID request a Kemenimipas per PDF Kepmen
- URL: `kemenimipas.go.id/ppid` o `ppid.kemenimipas.go.id`
- Subject: "Permohonan Salinan Keputusan Menteri Imigrasi dan Pemasyarakatan Nomor M.IP-08.GR.01.01 Tahun 2025 tentang Klasifikasi Visa"
- Template body:
  ```
  Yth. Pejabat Pengelola Informasi dan Dokumentasi
  Kementerian Imigrasi dan Pemasyarakatan

  Saya bermaksud memohon salinan dokumen resmi Keputusan Menteri Imigrasi
  dan Pemasyarakatan Nomor M.IP-08.GR.01.01 Tahun 2025 tentang Klasifikasi
  Visa, khususnya bagian yang memuat indeks visa C5A (Visa Kunjungan Konten
  Kreator), termasuk syarat, masa berlaku, biaya PNBP, dan persyaratan sponsor.

  Dokumen ini diperlukan untuk keperluan riset compliance perusahaan
  konsultan imigrasi PT Bali Zero (NIB [insert NIB Bali Zero]).

  Terima kasih atas perhatiannya.

  Hormat saya,
  [Antonello Siano - confirm with Antonello before send]
  ```
- Output: ricevuta PPID + ETA risposta (di solito 10 hari kerja)

#### Step 2.C — Sister visa cluster real-pricing (fallback se 2.A/2.B falliscono in 24h)
- Query directly su `peraturan.bpk.go.id` per **PP 45/2024** lampiran PNBP visa
- Cerca line items: C2, C5, C7, C7C, C9, B211A (storico)
- Tabulate verbatim PNBP per ciascuno → cluster average per "60-day non-tourism single-entry"
- Output: nuova tabella in dossier che sostituisce stima [SPECULATIVE]

**Dove aggiornare il dossier**:

Cerca la stringa esatta in §9:
```
[OPINIONE - SPECULATIVE pricing] Stima total client cost: IDR 8-13M
```

Sostituisci tutto il blocco con:

```markdown
### Servizio #2 — C5A Single Application (60 giorni iniziali) — **VERIFIED PRICING**

**Government PNBP (dato verificato)**:
- [FATTO] Biaya PNBP C5A 60 giorni: **IDR [VERBATIM da Kantor Imigrasi Denpasar OR PP 45/2024 lampiran]** — fonte: [call/PPID/PP citation]
- [FATTO] Extension fee (se applicabile): **IDR [VERBATIM]** per estensione 60 giorni
- [FATTO] Pattern estensione confirmed: **[60+60 OR 60+60+60]** — fonte: [verbatim]

**Bali Zero agency component**:
- Pre-application audit + document prep: IDR [4-7M, da definire post-pilot]
- Submission + tracking: IDR [2-3M]
- Sponsor structuring (Bali Zero PT come Penjamin): IDR [1-2M setup + monthly subscription se applicabile]

**Total realistic client cost (post-verifica)**: IDR [VERIFIED] — processing time [VERIFIED da Kantor]
```

Solo dopo le 3 verifiche empiriche. Se almeno 1 di 2.A/2.B/2.C fallisce, mantenere `[UNVERIFIED — verifica in corso]` per quel campo specifico, ma NO [SPECULATIVE] generico su tutto il servizio.

---

### TASK 3 — Appendix A: NB-2 deep-research + query strutturate

**Trigger**: Appendix A è attualmente vuoto (`NB-2 NON consultato in questo turn`). Va chiuso il gap.

**Pre-condizione**: verifica MCP `notebooklm` connesso via `claude mcp list | grep notebooklm`. Se non connesso, escalate ad Antonello (non procedere blind).

**Tool prefix**: `mcp__notebooklm-mcp__*`

#### Step 3.A — Deep-research NB-2 (single comprehensive query)

Esegui **una** query "deep research" mode (se NB-2 supporta) altrimenti standard query lunga:

```
Query NB-2: "Indeks visa C5A Visa Kunjungan Konten Kreator dalam sistem
klasifikasi visa Indonesia 110-tipe. Genesis hukum (Kepmen M.IP-08.GR.01.01
Tahun 2025), syarat substantif (sponsor, durasi, biaya PNBP, dokumen
pendukung), aktivitas yang diperbolehkan vs dilarang (no monetization in
Indonesia, foreign-paid monetization allowed), perpanjangan (60+60+60 vs
60+60), enforcement record di Bali sejak peluncuran. Reconcile dengan
predecessor C5 Visa Media dan Pers dan sister indeks C7C, E33G. Cita Pasal
specifik UU 6/2011 + Permenkumham 22/2023 + Permenkumham 11/2024 + PP 45/2024
yang berlaku verbatim."
```

UUID NB-2: `mcp__notebooklm-mcp__notebook_query` con `notebook_id` dal mapping `~/logs/nb-migration-mapping.json` o `reference_notebooklm_arsenal_full.md`. Se non trovi UUID NB-2 immediato, query `mcp__notebooklm-mcp__notebook_list` per cercare il NB con name="NB-2" o "Visa" o "Immigration".

Output: salva risposta verbatim in nuovo file `/tmp/c5a-nb2-deep.md` (per audit) + estrai chiavi 3-5 in dossier Appendix A.

#### Step 3.B — Serie 7 query strutturate (mirate)

Esegui in **sequence** queste 7 query specifiche, 1 per gap operativo aperto:

1. **Q-1 [PNBP esatto C5A]**: `"Berapa tarif PNBP resmi untuk Visa Kunjungan Konten Kreator C5A 60 hari menurut PP 45/2024 atau PMK 82/2023? Cantumkan pasal dan lampiran lengkap verbatim."`

2. **Q-2 [Pattern estensione]**: `"Apakah Visa Kunjungan C5A dapat diperpanjang maksimum 2 kali (60+60+60=180 hari) sebagaimana C5 pre-2025, atau hanya 1 kali (60+60=120 hari) menurut Kepmen M.IP-08.GR.01.01 Tahun 2025?"`

3. **Q-3 [Sponsor agency-as-sponsor]**: `"Apakah agency atau perusahaan konsultan imigrasi Indonesia berhak menjadi Penjamin (sponsor) untuk Visa Kunjungan C5A bagi konten kreator asing yang tidak memiliki hubungan kerja langsung dengan agency tersebut? Cek UU 6/2011 dan Permenkumham 22/2023."`

4. **Q-4 [Pasal 122 verbatim]**: `"Bunyi lengkap Pasal 122 huruf a UU Keimigrasian Nomor 6 Tahun 2011 sebagaimana diubah UU 63/2024 tentang sanksi pidana penyalahgunaan izin tinggal. Cantumkan ancaman pidana dan denda maksimum."`

5. **Q-5 [eVisa portal C5A]**: `"Apakah portal eVisa Direktorat Jenderal Imigrasi (evisa.imigrasi.go.id) saat ini menerima aplikasi visa C5A self-service, atau aplikasi C5A hanya dapat diajukan secara manual melalui Kantor Imigrasi setempat?"`

6. **Q-6 [Aktivitas dilarang C5A]**: `"Daftar aktivitas yang dilarang bagi pemegang Visa Kunjungan C5A, termasuk klarifikasi atas: (a) monetisasi YouTube/Instagram/TikTok dari platform asing, (b) brand collaboration dengan entitas Indonesia, (c) barter ekonomi (akomodasi gratis untuk konten promosi), (d) fan-meeting berbayar."`

7. **Q-7 [Migrasi C5 → C5A]**: `"Bagaimana visa indeks C5A dipisahkan dari C5 (Visa Media dan Pers) pada Kepmen M.IP-08.GR.01.01 Tahun 2025? Apakah pemegang C5 yang masih berlaku otomatis dikonversi ke C5A, atau harus mengajukan visa baru?"`

Output per ogni query: response verbatim NB-2 + URL/citation se NB-2 fornisce + flag "answered / partial / no-data" per ciascuna.

#### Step 3.C — Scrivere Appendix A nel dossier

Sostituisci l'intero blocco Appendix A attuale (cerca `### Appendix A — NotebookLM NB-2 query results` e il paragrafo `[INFO] Sessione: NB-2 (visa) NON è stata interrogata in questo turn`) con:

```markdown
### Appendix A — NotebookLM NB-2 query results (executed 2026-05-2[X])

**Deep-research query (Step 3.A)**:
[VERBATIM RESPONSE da NB-2 deep-research mode]

**Sources NB-2 cita**:
[Lista verbatim dei document_id che NB-2 referenzia nella risposta]

---

**Structured queries (Step 3.B)**:

#### Q-1 — PNBP esatto C5A
[VERBATIM Bahasa response]
Status: [answered / partial / no-data]

#### Q-2 — Pattern estensione
[VERBATIM]
Status: [...]

#### Q-3 — Sponsor agency-as-sponsor
[VERBATIM]
Status: [...]

#### Q-4 — Pasal 122 huruf a verbatim
[VERBATIM]
Status: [...]

#### Q-5 — eVisa portal C5A
[VERBATIM]
Status: [...]

#### Q-6 — Aktivitas dilarang C5A
[VERBATIM]
Status: [...]

#### Q-7 — Migrasi C5 → C5A
[VERBATIM]
Status: [...]

---

**Cross-reference applied to dossier**:
- §3 Hierarchy regulatoria: [updated/unchanged] basato su Q-1/Q-4
- §9 Servizio #2 pricing: [updated/unchanged] basato su Q-1
- §9 Servizio #3 extension: [updated/unchanged] basato su Q-2
- §9 Servizio #7 sponsor: [updated/unchanged] basato su Q-3
- §11 OQ-1: [chiuso/aperto] · OQ-2: [...] · OQ-3: [...] · OQ-4: [...]
```

---

## Commit + push istruzioni

Dopo le 3 task complete:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git fetch origin
git checkout docs/visa-c5a-research-2026-05-26
git pull --ff-only
# verifica branch
git rev-parse --abbrev-ref HEAD  # deve essere docs/visa-c5a-research-2026-05-26
# edit research/visa/2026-05-26-c5a-content-creator-deep-research.md
git add research/visa/2026-05-26-c5a-content-creator-deep-research.md
git commit -m "docs(visa): C5A dossier — gossip §6.4 'aumm aumma' + Servizio #2 verified pricing + Appendix A NB-2 queries

3 chirurgical edits post Antonello feedback 2026-05-26:
- §6 Layer GOSSIP: aggiunta sotto-sezione 6.4 con 2 interpretazioni 'zero casi' (I emissioni minime vs II mediation invisible 'aumm aumma'). Tabella simmetrica + caveat operativo no-public-claim.
- §9 Servizio #2: rimosso [SPECULATIVE pricing], inseriti dati VERIFIED da: telefonata Kantor Imigrasi Denpasar [risposte verbatim] + PPID Kepmen request submitted [ETA] + PP 45/2024 sister visa cluster cross-check.
- Appendix A: chiuso gap NB-2. Eseguita 1 deep-research query + 7 structured queries strutturate (PNBP, extension pattern, sponsor agency-as-sponsor, Pasal 122 verbatim, eVisa portal, aktivitas dilarang, migrazione C5→C5A). Cross-reference applicato a §3, §9, §11 OQ-1 a OQ-7.

Aggiorna PR #877.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"

# pre-commit hook gira prettier (~5s)
git push origin docs/visa-c5a-research-2026-05-26
```

---

## Stop conditions / escalation

Escalation ad Antonello via Telegram (`scripts/sentinel_lib/alerter.py` se preferisci, altrimenti scrivi un msg in chat) **prima** di procedere se:

1. **Kantor Imigrasi Denpasar non risponde** in 24h → procedi solo con Step 2.B + 2.C, marca PNBP C5A come `[UNVERIFIED — Kantor non risponde, PPID pending]` ma NON [SPECULATIVE]
2. **PPID Kemenimipas richiede signed letter** → escalate (richiede signature fisica Antonello)
3. **NB-2 MCP non connesso** → escalate (non procedere blind con NB query inventate)
4. **NB-2 risposta divergente** dal dossier corrente in ≥2 facts critici (F1 Kepmen date, F12 Bonnie Blue case, F23 PP 45/2024) → escalate (potrebbe richiedere correzioni più ampie)

---

## Notes coordinate Pro-specific

- **Anti-hallucination discipline** (CLAUDE.md global): ogni claim verifica con 2° tool call indipendente. Mai citare output di tool non eseguito **in questo turn**.
- **Worktree NON necessario** per questo task: 3 edit chirurgici a singolo file research = no rischio collision sibling.
- **MEMORY append**: dopo commit, append 1-line a `MEMORY_RESEARCH_CAPTURES.md` entry esistente (riga 9-10):
  ```
  [UPDATE 2026-05-2X]: NB-2 query batch eseguita + Servizio #2 pricing verified + Layer GOSSIP §6.4 'aumm aumma' interpretazione. Commit [SHA] PR #877.
  ```
- **PR #877 review**: lascia commento PR con TL;DR delle 3 edit + flag aree dove caveat persistono (PPID PDF ancora pending probabilmente, è OK).

---

**Esecutore**: leggi questo prompt, esegui le 3 task in sequence (1 → 2 → 3), commit + push, scrivi sommario 200 parole all'utente. Buon lavoro 🎯
