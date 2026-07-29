---
date: 2026-07-29
domain: compliance
client_case: none — cross-check lane for 3 prior contradictory SLHS lanes (2 Claude, 1 Gemini)
sources:
  - https://keslan.kemkes.go.id/unduhan/regulasi/No_14.pdf (Permenkes 14/2021, official Kemenkes mirror, primary)
  - https://peraturan.go.id/files/pp-no-28-tahun-2024.pdf (PP 28/2024, official peraturan.go.id, primary)
  - https://peraturan.go.id/files/bn55-2023.pdf (Permenkes 2/2023, official peraturan.go.id, primary)
adversarial_review: codex
---

# SLHS — Lane F: primary-text grep (verbatim only)

## Adversarial review — Codex GPT-5.6 `sol` (effort high), 2026-07-29

> ⛔ **VERDETTO: DO-NOT-SHIP come guida corrente.** Generatore = Claude (lane Sonnet); grader = Codex, famiglia diversa. Le obiezioni sotto sono quelle SOPRAVVISSUTE: ognuna è stata riletta contro il file e, dove tocca un numero, ri-verificata a mano sul dataset canonico.
>
> Questo file è archiviato come **nota di lavoro superata**, non come fonte. Serve la tracciabilità di come ci siamo arrivati; le sue conclusioni non si citano. L'autorità sul regime vigente è `2026-07-29-slhs-lane-h-amendments.md`, l'arbitro sui codici è `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (campo `kode_kbli_2025`).
>
> Difetti concreti trovati dal reviewer (seat di famiglia diversa dall'autore):
>
> 1. Presenta come vigenti una durata ("3 tahun", "chiude il conflitto 3 vs 5 anni") e un elenco di 6 codici che sono entrambi abrogati per questa materia.
> 2. 10391 e 10392 sono dichiarati "da verificare": il dataset canonico li chiude già — **non esistono** in `kode_kbli_2025`. Nemmeno 56103 e 68120 esistono; 11052 e 56303 sì.
> 3. Chiede "a qualcuno con accesso MCP/Qdrant/Postgres" di verificare codici che un JSON locale già presente decide da solo.
> 4. Tratta come ipotetico un emendamento (17/2024) che invece riscrive espressamente la sezione SLHS — cioè omette proprio quello materialmente pertinente.
> 5. Il rule-out di Pasal 1080-1090 esibisce un comando su **pagina 22208** mentre lo stesso file colloca la fine della norma a pagina 477-483: è un numero di riga passato come numero di pagina, quindi la prova non è riproducibile.
> 6. Le prove negative ("0 hits", "nessun 5 (lima) tahun") non hanno comando né output allegato: non sono auditabili.
> 7. Contraddizione interna: chiama Permenkes 17/2024 "the 2026 amendment".


**Method note:** all 3 documents were fetched as PDF from official government mirrors, converted with
`pdftotext -layout`, and every claim below was independently re-verified with a **second, page-scoped**
`pdftotext -f <page> -l <page>` extraction (not just a grep on the concatenated `.txt`) — the
concatenated-file → physical-page mapping via form-feed counting proved UNRELIABLE for the PP 28/2024 file
(off by 5-10 pages) and was discarded in favor of a brute-force per-page scan. Do not trust a page number
in this report that isn't paired with a `pdftotext -f N -l N` command below.

**OCR/glyph caveat:** PP 28/2024's official PDF has a font-substitution defect — digit "1" and "0" are
inconsistently rendered as glyphs that extract as `l`/`I` and `O` (e.g. "Pasal ll7l" for "Pasal 1171",
"2OL4" for "2014"). Grepping literal digit strings against this file gives **false negatives**; every
search below was cross-checked with the corrupted-glyph variant before being declared "not found."

---

### D1 — SLHS validity period

**Verdetto**: RISPOSTA VERBATIM — **3 (tiga) tahun**, stated in the certificate-template Lampiran of
Permenkes 14/2021 itself. Permenkes 2/2023 does **not** mention SLHS or "Laik Higiene" at all (0 hits) —
it is not a competing source for this number, it's simply silent on it.

**Stringa verbatim**:
> Ketentuan :
> Sertifikat Laik Higiene Sanitasi ........ berlaku selama 3 (tiga) tahun
> sejak tanggal diterbitkan.

— from the "CONTOH SERTIFIKAT LAIK HIGIENE SANITASI" (example certificate) block inside Lampiran §83
"STANDAR SERTIFIKAT LAIK HIGIENE SANITASI" of Permenkes 14/2021.

**Fonte**: `permenkes14_2021.pdf`, physical PDF page **1742** (printed page footer also reads "- 1742 -" —
no offset drift on this document, confirmed by direct extraction).

**Comando eseguito**:
```
curl -sL -o permenkes14_2021.pdf "https://keslan.kemkes.go.id/unduhan/regulasi/No_14.pdf"
pdftotext -layout -f 1742 -l 1742 permenkes14_2021.pdf -
```
(page pinned by chunked binary-search scan: `for start in 1 200 400 ... ; do pdftotext -layout -f $start -l $((start+199)) permenkes14_2021.pdf - | grep -c "berlaku selama 3"; done`, narrowed to page 1742.)

**Note**: this closes the "3 vs 5 years, unverifiable" conflict — the number **is** in the primary text,
in the certificate template annex, not in a body article. No competing "5 (lima) tahun" string exists
anywhere in either Permenkes 14/2021 or Permenkes 2/2023 (checked, 0 hits both files).

---

### D2 — PP 28/2024 sanctions article for kesehatan lingkungan / pangan olahan siap saji

**Verdetto**: RISPOSTA VERBATIM — **Pasal 251–252**, confirmed. **Pasal 1080–1090 is a different,
unrelated chapter** (Dokumen Karantina Kesehatan / Penanggulangan Wabah, BAB VIII "KEJADIAN LUAR BIASA DAN
WABAH") — ruled out by direct read of its full text.

**Important qualifier**: Pasal 251–252 is the **general kesehatan lingkungan sanctions clause**, covering
"pengelola, penyelenggara, atau penanggung jawab lingkungan permukiman, tempat kerja, tempat rekreasi,
serta tempat dan fasilitas umum" — it does **not** name "Tempat Pengelolaan Pangan (TPP)" or "SLHS"
literally. Pangan olahan siap saji is one of the three "media pangan" sub-categories (Pasal 251 context,
same Bagian Ketiga Belas "Kesehatan Lingkungan", ayat listing "a. pangan segar; b. pangan olahan; c. pangan
olahan siap saji"), so TPP/SLHS enforcement rides on this general clause rather than having its own
TPP-named pasal in the PP.

**Stringa verbatim** (Pasal 251 ayat 1, then Pasal 252 in full):
> Pasal 251
> (1) Setiap pengelola, penyelenggara, atau penanggung jawab lingkungan permukiman, tempat kerja, tempat
> rekreasi, serta tempat dan fasilitas umum wajib menyelenggarakan Kesehatan lingkungan.
>
> Pasal 252
> (1) Setiap pengelola, penyelenggara, atau penanggung jawab lingkungan permukiman, tempat kerja, tempat
> rekreasi, serta tempat dan fasilitas umum yang tidak melaksanakan kewajiban sebagaimana dimaksud dalam
> Pasal 251 ayat (1) dikenai sanksi administratif.
> (2) Sanksi administratif sebagaimana dimaksud pada ayat (1) berupa:
>     a. teguran lisan;
>     b. teguran tertulis;
>     c. penghentian sementara kegiatan atau usaha; dan/atau
>     d. pencabutan atau rekomendasi pencabutan izin.
> (3) Pengenaan sanksi administratif sebagaimana dimaksud pada ayat (2) dilakukan oleh Pemerintah Pusat,
> Pemerintah Daerah provinsi, atau Pemerintah Daerah kabupaten/kota sesuai dengan kewenangannya dan sesuai
> dengan ketentuan peraturan perundang-undangan.

**Fonte**: `pp28_2024_official.pdf`, physical PDF page **118** (printed page footer also reads "- 118 -" —
no drift on this page).

**Comando eseguito**:
```
curl -sL -o pp28_2024_official.pdf "https://peraturan.go.id/files/pp-no-28-tahun-2024.pdf"
pdftotext -layout -f 118 -l 118 pp28_2024_official.pdf -
```
Rule-out of the 1080-1090 candidate:
```
pdftotext -layout -f 22208 -l 22208 pp28_2024_official.pdf -   # (line-mapped, then page-scan-verified 21151-23130 range)
# content = "Pasal 1080" Dokumen Karantina Kesehatan / Pasal 1084 "Penanggulangan Wabah" — BAB VIII, unrelated to TPP/SLHS.
```

---

### D3 — PP 28/2024 abrogation clause for PP 66/2014

**Verdetto**: RISPOSTA VERBATIM — **Pasal 1169 huruf q** (NOT Pasal 1170, either "angka 20" or "huruf q" —
both prior lanes had the wrong Pasal number; the letter "q" guess was half-right but attached to the wrong
article). The whole list runs a-z then aa-ee under **one** article, Pasal 1169, inside **BAB XIII KETENTUAN
PENUTUP**. PP 66/2014 is item **q** in that lettered list.

**Stringa verbatim**:
> BAB XIII
> KETENTUAN PENUTUP
>
> Pasal 1169
> Pada saat Peraturan Pemerintah ini mulai berlaku, semua peraturan perundang-undangan yang merupakan
> peraturan pelaksanaan dari:
> [...]
> q. Peraturan Pemerintah Nomor 66 Tahun 2014 tentang Kesehatan Lingkungan (Lembaran Negara Republik
> Indonesia Tahun 2014 Nomor 184, Tambahan Lembaran Negara Republik Indonesia Nomor 5570);
> [...]
> dicabut dan dinyatakan tidak berlaku.

**Fonte**: `pp28_2024_official.pdf` — Pasal 1169 heading on physical PDF page **477**; item "q." (PP
66/2014) on physical PDF page **482**; closing line "dicabut dan dinyatakan tidak berlaku." + next article
(Pasal 1171) on physical PDF page **483**.

**Comando eseguito**:
```
python3 -c "
import subprocess
for p in range(460, 495):
    out = subprocess.run(['pdftotext','-layout','-f',str(p),'-l',str(p),
        'pp28_2024_official.pdf','-'], capture_output=True, text=True).stdout
    if '66 Tahun' in out or 'dicabut dan dinyatakan' in out:
        print(p)
"
# -> 478, 482, 483; then:
pdftotext -layout -f 482 -l 482 pp28_2024_official.pdf - | grep -n -B2 -A2 "66 Tahun"
pdftotext -layout -f 477 -l 477 pp28_2024_official.pdf - | grep -n "Pasal 1169\|KETENTUAN PENUTUP"
```

---

### D4 — KBLI codes mapped to SLHS (Permenkes 14/2021 Lampiran)

**Verdetto**: RISPOSTA VERBATIM — 6 KBLI codes, listed directly under the PB-UMKU header for SLHS. **⚠️
NOMENCLATURE FLAG (partial — see caveat below): 3 of the 6 codes are OUTSIDE the F&B/hotel filter Zero
supplied, so this lane can only confirm 3 of 6, not rule the other 3 in or out of KBLI 2025.**

**Stringa verbatim** (Lampiran §F "STANDAR PENUNJANG KEGIATAN USAHA KESEHATAN LINGKUNGAN", §83 "STANDAR
SERTIFIKAT LAIK HIGIENE SANITASI", header block):
> KBLI 56101 Restoran
> KBLI 56290 Penyediaan Jasa Boga Periode Tertentu
> KBLI 56210 Jasa Boga Untuk Suatu Event Tertentu (Event Catering)
> KBLI 10391 Industri Tempe Kedelai
> KBLI 10392 Industri Tahu Kedelai
> KBLI 11052 Industri Air Minum Isi Ulang (Depot Air Minum)

(then, in the "1. Ruang Lingkup" body immediately below, each code gets a one-line business-scope
elaboration — 56101 incl. franchise/branch restaurants, 56290 split into skala menengah/besar (golongan
B/C), 56210 split into mikro-kecil/menengah/besar (golongan A/B/C), and "d. KBLI 10391 Industri Tempe
Kedelai dan KBLI 10392 Industri Tahu Kedelai — Untuk industri tempe kedelai dan tahu kedelai merupakan TPP
Tertentu.")

**Fonte**: `permenkes14_2021.pdf`, physical PDF page **1682** (printed footer "- 1682 -", no drift).

**Comando eseguito**:
```
pdftotext -layout -f 1682 -l 1682 permenkes14_2021.pdf -
```

**Cross-check against the KBLI 2025 filter Zero supplied** (F&B: 56101,56102,56210,56290,
56301-56306; hotel: 55101-55106,55201-55204,55209,55300,55400,55901,55909):

| Code cited by Permenkes 14/2021 | In Zero's 2025 filter? |
|---|---|
| 56101 Restoran | ✅ yes — exists in 2025 |
| 56290 Penyediaan Jasa Boga Periode Tertentu | ✅ yes — exists in 2025 |
| 56210 Jasa Boga Untuk Suatu Event Tertentu | ✅ yes — exists in 2025 |
| 10391 Industri Tempe Kedelai | ⚠️ NOT in filter — sektor C manufaktur (10xxx), not F&B/hotel |
| 10392 Industri Tahu Kedelai | ⚠️ NOT in filter — sektor C manufaktur (10xxx) |
| 11052 Industri Air Minum Isi Ulang (Depot Air Minum) | ⚠️ NOT in filter — sektor C manufaktur (11xxx, beverage industry) |

**No KBLI-2020-vs-2025 mismatch found for the 3 codes this lane could check** — 56101/56290/56210 are all
live 2025 codes, contrary to the hypothesis in the brief that the whole Lampiran might be running on stale
2020 nomenclature. But the brief's hypothesis is **not disproven either**: 10391/10392/11052 sit in food/
beverage-manufacturing sectors (10xxx/11xxx) that fell outside the filter list given to this lane — someone
needs to grep the **full** curated KBLI-2025 dataset (not just the F&B/hotel subset) for those 3 codes
specifically before the "OSS and our dataset speak different nomenclatures" claim can be made or retired.

---

## COSA RESTA APERTO

1. **D4 is only 50% closed.** 3/6 KBLI codes (10391, 10392, 11052) were not checked against the full
   curated KBLI-2025 dataset — only against the F&B/hotel subset supplied in the brief, which by design
   doesn't cover sektor C manufaktur pangan/minuman. Someone with `mcp__nuzantara-mcp__search_kbli` or
   direct Qdrant/Postgres access needs to run `10391`, `10392`, `11052` against the live KBLI-2025 corpus.
2. **D2's Pasal 251-252 does not literally name "SLHS" or "TPP"** — it's the umbrella kesehatan-lingkungan
   sanctions clause. If Bali Zero product copy needs a TPP/SLHS-specific sanctions citation, the delegation
   chain is Pasal 251-252 (general obligation + sanctions) → the "media pangan" sub-categorization a few
   pasal earlier in the same Bagian → Permenkes-level technical rules (14/2021's Lampiran) for the
   TPP-specific procedure. No pasal in PP 28/2024 names "TPP" or "SLHS" by acronym — that vocabulary lives
   only in the Permenkes.
3. **Permenkes 14/2021 has been amended twice** (Permenkes 8/2022, Permenkes 17/2024 — found in the
   original web search, not verified here) — this lane read the base 14/2021 PDF only. If either
   amendment touches §83 (SLHS) or the KBLI list, the 3-year figure or KBLI list could be superseded. Not
   checked — out of scope of "primary text of the base regulation," but flagged because it's exactly the
   kind of gap that produced the original 3-lane contradiction.
4. Did not re-verify D1's "3 tahun" against Permenkes 17/2024 (2026 amendment) — same caveat as #3.
