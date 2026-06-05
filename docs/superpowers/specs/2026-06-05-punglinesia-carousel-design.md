---
date: 2026-06-05
domain: regulatory
client_case: false
sources:
  - https://www.thejakartapost.com/indonesia/2026/06/05/deputy-immigration-minister-suspected-of-extorting-foreigners-over-stay-permit
  - https://jakartaglobe.id/news/deputy-immigration-minister-silmy-karim-detained-in-foreign-residency-permit-corruption-case
  - https://www.aljazeera.com/news/2026/6/4/indonesia-arrests-officials-in-crackdown-on-corruption
  - https://en.antaranews.com/news/417911/kpk-detains-dy-minister-7-officials-in-immigration-extortion-case
  - https://www.antaranews.com/berita/5594560/kpk-silmy-karim-dan-tujuh-tersangka-raup-rp145-m-selama-2022-2026
---

# PUNGLINESIA — WR2 editorial carousel (design spec)

**Status:** design APPROVED by Antonello (2026-06-05). Slides rendered (v1). Legal
red-team pending. NOT published — Legge 5 (human publishes manually after gate).

## 1. Concept

`PUNGLINESIA` = **PUNGLI** (_pungutan liar_ — the endemic illegal-levy/extortion of
Indonesian bureaucracy) + **(Indo)NESIA**. Coined by Antonello on the 2026-06-04 KPK
arrest of a sitting deputy immigration minister, framed against Italy's _Tangentopoli /
Mani Pulite_ (1992). Editorial thesis carried verbatim from the source graphic:
**"BUKAN OKNUM. INI PENYAKIT SISTEMIK."** (not a rogue individual — a systemic disease).

## 2. Decisions (locked)

| Axis        | Decision                                                                                                                                                 |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Destination | Public editorial, Bali Zero IG channel                                                                                                                   |
| Archetype   | `news-flash` (constitution Art. 13)                                                                                                                      |
| Domain      | `regulatory` (immigration/visa corruption)                                                                                                               |
| Language    | **100% Bahasa Indonesia**                                                                                                                                |
| Audience    | **Indonesian public** (civic voice "kita", not expat)                                                                                                    |
| Register    | analitico + militante                                                                                                                                    |
| Production  | **Hand-authored** via brand cortex (NOT the autonomous WR2 generator — topic legally sensitive + WR2 autopsy 2026-06-04 showed the generator unreliable) |

## 3. Grounded facts (attribute ALL to KPK)

- **Silmy Karim**, Wakil Menteri Imigrasi dan Pemasyarakatan (2024–2026).
- KPK detained him **2026-06-04**, named **tersangka** (suspect — NOT convicted). Turned himself in 2026-06-03.
- Alleged **pemerasan** (extortion) on processing **izin tinggal** (stay permits) for **WNA** (foreign nationals).
- ~**Rp 100 juta/week** to Karim since he was Dirjen Imigrasi (Jan 2023–Oct 2024, under Jokowi).
- Karim + 7 officials allegedly took **Rp 145,5 miliar** total, Ditjen Imigrasi, **2022–2026**.
- Operation 2–3 June: **17 arrested** (8 ASN/state officials + 9 private "perantara"/calo).
- Case originated from the **RPTKA** (foreign-worker-permit) case at Kemenaker.

## 4. Risk guardrails (NON-NEGOTIABLE — high-risk path: foreign brand, ID language, ID audience, domestic state-corruption topic)

1. **No presumption of guilt.** Karim named ONCE (S3), always with `dugaan` / `tersangka` / `sumber angka: KPK`. Never asserts he is guilty — reports KPK's public action.
2. **No state-symbol mockery.** Garuda REMOVED from the graphic (UU 24/2009 _penghinaan lambang negara_ is a criminal offense). Dossier texture only.
3. **Pro-KPK / pro-reform stance.** PUNGLINESIA = the disease KPK is curing. The piece channels civic anti-pungli sentiment toward the institutional cure — never anti-government, never partisan, never inciting.
4. **Verbatim numbers** (Art. 6.4) — also the legal shield: reporting public record.
5. **No commercial CTA** (Art. 6.6). Bali Zero is publisher/observer, not protagonist.
6. **Legal red-team** (`devils-advocate`) before the gate. **Telegram review gate** (Legge 5) — Antonello publishes by hand.

## 5. Slides (final copy, 6 × 1080×1350)

```
S1 COVER (cover/statement) · badge "KPK · 04.06.2026" · veins + dossier, NO Garuda
   PUNGLINESIA  [PUNGLI red / NESIA white]
   BUKAN OKNUM. INI PENYAKIT SISTEMIK.

S2 KITA SEMUA TAHU RASANYA (recognition — civic "kita" voice)
   Amplop di loket. "Uang pelicin" biar cepat. Calo menunggu di depan kantor.
   Pungli bukan berita baru buat kita — ia sudah jadi BIAYA HIDUP.

S3 REKAMAN KPK (evidence-carved adapted, dossier bg) · the ONLY slide with the name
   §1 KPK menahan Wakil Menteri Imigrasi Silmy Karim, ditetapkan tersangka
   §2 17 orang ditangkap dalam 48 jam (2–3 Juni 2026)
   §3 Dugaan pemerasan pengurusan izin tinggal WNA
   §4 Rp 145,5 miliar · 2022–2026 · sumber angka: KPK
   CATATAN KAMI: Izin itu hak, bukan barang dagangan.

S4 BUKAN SATU OKNUM (stat-forward)
   Rp 145,5 M / dalam empat tahun · ~Rp 100 jt / setiap minggu · 9 calo / swasta di dalam sistem
   Ini bukan pegawai nakal — ini MESIN yang terlanjur dianggap wajar.

S5 DUNIA PERNAH LIHAT INI (Tangentopoli bridge = shared hope, not a lecture)
   Italia, 1992. Satu penangkapan kecil membuka operasi "Tangan Bersih" (Mani Pulite)
   — dan meruntuhkan satu republik yang korup. Mereka berhenti menyebutnya oknum.
   Pertanyaannya: apakah ini giliran kita?

S6 CLOSING (statement-bomb, veins, bookend with cover) · zero CTA
   PUNGLI BUKAN TAKDIR. OBATNYA PUNYA NAMA: KPK.
```

Narrative arc: _we all live it_ (S2) → _this time it reached the top_ (S3) → _it's a machine, not a man_ (S4) → _the world has seen this and cured it_ (S5) → _pungli isn't fate, the cure has a name_ (S6).

## 6. Production artifacts

- Generator: `research/marketing/punglinesia-2026-06/build.py` (shared CSS, brand tokens, deterministic SVG veins, dossier stamps).
- Cover (S1): uses Antonello's ORIGINAL raster wordmark via `cover_from_source.py` — crops the wordmark+veins band (Garuda + "BRIEF GRAFIS" annotation excluded), fades it into the portrait canvas; subtitle + empirical anchor ("17 TERSANGKA · 48 JAM · Rp 145,5 M", placed at the foot) re-rendered in CSS. Source: `~/Desktop/PHOTO-2026-06-05-12-55-13.jpg`.
- Render: `chrome-headless-shell` → `png/slide{1..6}.png` (verified 1080×1350).
- Brand compliance: Montserrat 800, palette antracite/black/white/yellow/red only, no emoji, no forbidden phrases, no CTA.

## 7. v2 — legal red-team applied (2026-06-05)

`devils-advocate` (DeepSeek) verdict on v1 = **BLOCK** (2 BLOCKER, 4 WARN, 2 tweak). All applied in `build.py` v2:

- [x] **BLOCKER#1** S4 — separated system-total (Rp 145,5 M · 2022–2026) from Karim's personal weekly take (~Rp 100 jt/mgg · 2023–2024 Dirjen) + period qualifiers + footer "Sumber: KPK · 4 Juni 2026". (was a 7× math contradiction readable with a calculator)
- [x] **BLOCKER#2** S5 — softened: removed "meruntuhkan satu republik yang korup" + the rhetorical "apakah ini giliran kita?" (foreign PT PMA → UU ITE Pasal 28(2) exposure; no UU 40/1999 press shield). Kept the Mani Pulite bridge as shared-hope; new close "Setiap sistem bisa dibersihkan — kalau berhenti dianggap wajar."
- [x] WARN#3 S3 — full title "Wakil Menteri Imigrasi **dan Pemasyarakatan**".
- [x] WARN#5 S1 — cover empirical anchor "17 TERSANGKA · 48 JAM · Rp 145,5 M" (Art. 6.9).
- [x] OK#7 S4 — re-attributed to KPK (footer source line).
- [x] OK#8 S5 — dropped "kecil" (Mario Chiesa was not a minor official).
- [x] S6 → 3 lines (font 74→60); S3 dossier opacity lowered + text-shadow for legibility.

### Residual DECISION for Antonello (S5)

red-team recommended Option B (delete S5, replace with a constructive slide). I applied **Option A (soften)** to preserve your Tangentopoli intent. Pick:

- **A** keep softened S5 [DONE — current state]
- **B** delete S5 → constructive 7th slide (e.g. what a WNA should do when faced with pungli)
- **C** restore the sharper version, accepting the legal risk

### Still open

- [ ] Antonello: S5 decision (A / B / C).
- [ ] IG caption — drafted (§8), pending approval.
- [ ] Telegram review gate → Antonello publishes manually (Legge 5, never auto-publish).

## 8. IG caption (Bahasa Indonesia — draft)

> PUNGLINESIA — bukan oknum, ini penyakit sistemik.
>
> 4 Juni 2026: KPK menahan Wakil Menteri Imigrasi dan Pemasyarakatan Silmy Karim dan menetapkannya sebagai tersangka. Dalam operasi 2–3 Juni, 17 orang ditangkap — 8 penyelenggara negara, 9 perantara swasta — atas dugaan pemerasan pengurusan izin tinggal WNA. Menurut KPK, Rp 145,5 miliar mengalir dari Ditjen Imigrasi sepanjang 2022–2026.
>
> Pungli bukan berita baru buat kita. Ia terlanjur dianggap wajar — dan justru di situ penyakitnya. Italia pernah di titik yang sama pada 1992; mereka berhenti menyebutnya "oknum" dan mulai membersihkan sistemnya.
>
> Setiap sistem bisa dibersihkan, kalau berhenti dianggap wajar.
>
> Sumber: KPK (4 Juni 2026) — via Antara, The Jakarta Post, Jakarta Globe. Semua tuduhan masih dalam proses hukum; yang bersangkutan berstatus tersangka, belum terbukti bersalah.
