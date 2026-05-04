# Hari 2 — Codebase Tour (apps/mouth/)

**Mission ref:** §6 codebase familiarity (`07_60_DAY_MISSION_BAHASA.md`)
**Estimasi waktu:** 90 menit
**Pre-req:** Day 1 selesai (tutor jalan)

## Tujuan

Kamu paham struktur `apps/mouth/`, bisa lokalisasi 3 key file
(FunnelFeature.tsx, analytics.ts, ArticleClient.tsx), dan identifikasi
2 CTA tanpa onClick di FunnelFeature.tsx (yang akan kamu fix Day 3).

## Konteks

Day 1 kamu sudah baca dokumentasi (di `~/zantara-onboarding/`). Hari ini
kamu masuk ke real codebase di `~/Projects/nuzantara/`. Belum edit, hanya
baca + paham.

Tutor bantu kamu dari sub-agent kalau bingung.

## Pre-requisiti

- [ ] Day 1 selesai
- [ ] `~/Projects/nuzantara/` sudah cloned (verify `cd ~/Projects/nuzantara && git status`)
- [ ] Buka VSCode pointed ke `~/Projects/nuzantara/`
- [ ] Sesi Claude aktif di workspace itu

## Langkah-langkah

### 1. Eksplorasi top-level apps/mouth/

```bash
cd ~/Projects/nuzantara/apps/mouth
ls -la
```

Catat di kepala:

- `src/` — semua source code
- `public/` — assets static
- `e2e/` — Playwright tests
- `package.json` — dependencies
- `next.config.ts` — Next.js config

### 2. Tanya tutor untuk overview

```
/agent zantara-onboarding tolong jelaskan struktur apps/mouth/ secara umum, terutama src/app/ dan kenapa pakai App Router pattern (parentesis route group, _components underscore)
```

Tutor jelaskan App Router conventions: `(blog)` = route group (no
URL), `_components` = ignored from routing, `[slug]` = dynamic route.

### 3. Read 3 key files

Buka tiga file ini di VSCode:

#### File 1: `apps/mouth/src/app/v2/_components/FunnelFeature.tsx`

```bash
code apps/mouth/src/app/v2/_components/FunnelFeature.tsx
```

Browse line 350-400. Cari 4 CTA. Catat di buku catatan kamu:

- Line ~XXX: CTA "Apply Visa" — onClick? `[ya / tidak]`
- Line ~XXX: CTA "Setup Company" — onClick? `[ya / tidak]`
- Line ~XXX: CTA "Tax Help" — onClick? `[ya / tidak]`
- Line ~XXX: CTA "Property Eligibility" — onClick? `[ya / tidak]`

#### File 2: `apps/mouth/src/lib/analytics.ts`

```bash
code apps/mouth/src/lib/analytics.ts
```

Identifikasi function:

- `trackFunnelEvent` — apa parameter dan apa yang dia call?
- `trackPageView` — kapan dipakai?
- `trackWhatsAppClick` — apa unique-nya dibanding `trackFunnelEvent`?

#### File 3: `apps/mouth/src/app/(blog)/blog/[slug]/ArticleClient.tsx`

```bash
code apps/mouth/src/app/(blog)/blog/[slug]/ArticleClient.tsx
```

Browse. Cari:

- Bagaimana scroll depth ditrack?
- Di mana CTA di-inject ke article body?
- Siapa yang import `trackFunnelEvent`?

### 4. Tanya tutor untuk gap analysis

```
/agent zantara-onboarding di FunnelFeature.tsx saya lihat 2 CTA tanpa onClick. Identifikasi line-nya, apa nama CTA, dan apa fix yang harus saya lakukan? Tolong jangan kasih full code — saya mau coba sendiri Day 3.
```

Tutor balikin:

- Line numbers (dari grep)
- CTA names
- Hint fix (import + onClick handler)

JANGAN minta full code — ini latihan kamu untuk Day 3.

### 5. Cek Playwright e2e existing

```bash
code apps/mouth/e2e/funnel-ctas.spec.ts
```

Baca test yang sudah ada. Apa yang di-test? Apa yang TIDAK di-test (gap)?

Tanya tutor:

```
/agent zantara-onboarding di e2e funnel-ctas.spec.ts, test mana yang akan fail kalau onClick FunnelFeature CTA hilang? Atau memang TIDAK ada test yang assert ini?
```

Tutor analyze + jawab. Kemungkinan: existing test cek render, BUKAN
event firing. Itu sebabnya bug ini lolos sebelumnya.

## Verifikasi

Tulis catatan singkat (5-10 kalimat bahasa Indonesia kamu sendiri) di
buku catatan atau file `local/notes-day2.md`:

1. Apa beda antara `src/app/(blog)/` dan `src/app/v2/_components/`?
2. Apa fungsi `trackFunnelEvent` di analytics.ts?
3. Berapa CTA di FunnelFeature.tsx, dan berapa yang missing onClick?
4. Apa "tracking gap" yang sebabkan website cuma 2 lead/90 hari?

Verifikasi tutor:

```
/agent zantara-onboarding saya tulis catatan begini: [paste catatan kamu]. Apakah pemahaman saya benar?
```

Tutor kasih feedback (correct / clarify / extend).

## Kalau ada error / stuck

| Masalah | Fix |
| --- | --- |
| File tidak ada di path yang disebut | Update tutor — file mungkin pindah. Browse `apps/mouth/src/` manual. |
| FunnelFeature.tsx terlalu panjang, susah baca | Tutor extract section penting via grep. Tanya: "show me lines 350-400 of FunnelFeature.tsx" |
| Saya tidak paham TypeScript | OK — tutor bisa explain syntax line-by-line. Tanya. |
| Saya tidak yakin CTA mana yang missing onClick | Run grep di tutor: "grep onClick di FunnelFeature.tsx, kasih saya line numbers" |

## Selesai?

Kalau verifikasi catatan + tutor confirm pemahaman:

1. Save catatan di `~/zantara-onboarding/local/notes-day2.md` (folder
   `local/` di-exclude dari rsync, jadi catatan kamu tidak ketimpa)
2. WA ke Antonello: "Day 2 selesai, catatan tersimpan di local/. Siap
   Day 3 besok."
3. Lanjut ke `day3_first_pr.md` besok

Kalau ada blocker:

- WA Antonello dengan deskripsi spesifik (bukan "saya tidak paham" —
  tapi "saya tidak paham apa beda route group dan dynamic route")
- Tutor lanjut bantu via chat
