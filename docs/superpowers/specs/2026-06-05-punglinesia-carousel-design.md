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
- Render: `chrome-headless-shell` → `png/slide{1..6}.png` (verified 1080×1350).
- Brand compliance: Montserrat 800, palette antracite/black/white/yellow/red only, no emoji, no forbidden phrases, no CTA.

## 7. Open items

- [ ] Apply legal red-team (`devils-advocate`) findings.
- [ ] Refine S6 to ≤2 visual lines (currently 4 at 74px) — shrink font.
- [ ] Lower dossier-stamp opacity behind S3 facts for legibility.
- [ ] S5 body rhetorical question `apakah ini giliran kita?` — confirm acceptable (Art. forbidden-phrases F bans `?` on TITLES only; this is body editorial). Critic to confirm.
- [ ] Draft IG caption (Bahasa Indonesia) + source line.
- [ ] Telegram review gate → Antonello publishes manually.
