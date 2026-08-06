# SYSTEM_INVENTORY — daftar isi sistem Nuzantara

**Owner:** Subhi Darajat · **Lokasi wajib:** `/docs/SYSTEM_INVENTORY.md` di repo `Teman2` (bukan hanya project knowledge — CI dan AI agent harus bisa membacanya)
**Menutup:** LAWS.md K0 · 10 salah diagnosa periode Apr–Jun 2026
**Aturan hidup:** setiap PR yang menambah `source`, event, hook, atau komponen wajib update file ini **di PR yang sama**. Review tiap Jumat 14:00.

> Fungsi file ini satu: menjawab _"apakah ini sudah ada?"_ tanpa bertanya ke Antonello.
> Status yang dipakai: `LIVE` · `ORPHAN` (kode ada, surface belum) · `PLANNED` (enum siap, FE belum) · `DEPRECATED` · `UNVERIFIED`.

---

## Cara mengisi — jalankan dari root `Teman2`

Jangan tebak. Setiap tabel di bawah punya perintahnya sendiri. Yang belum dijalankan tetap `UNVERIFIED`.

```bash
# A — event yang benar-benar dikirim frontend
grep -rn "trackFunnelEvent\|trackLead\|gtag(" apps/mouth/src packages/core \
  --include=*.ts --include=*.tsx | grep -v ".test." | sed 's/:.*(/  ->  /' | sort -u

# A2 — registry event resmi
grep -n "" packages/core/analytics/funnel-view.ts | sed -n '1,120p'

# B — SSOT enum LeadSource (backend)
grep -n "= \"" apps/backend-rag/backend/services/lead_capture/source.py

# B2 — semua source="..." yang dipakai frontend (harus subset dari B)
grep -rhno 'source="[a-z_]*"' apps/mouth/src --include=*.tsx | sort -u

# C — komponen wajib pakai-ulang: cek siapa yang melanggar
grep -rn "buildWhatsAppLink(" apps/mouth/src --include=*.tsx    # harus 0 di CTA baru
grep -rn "<img " apps/mouth/src --include=*.tsx                  # harus 0
grep -rn "wa.me/\|62822" apps/mouth/src --include=*.tsx          # nomor hardcode, harus 0

# D — required vs advisory check (pakai PR mana pun yang masih terbuka)
gh pr checks <N>
gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks 2>/dev/null

# F — kontrak lintas sistem
grep -rn "usePricingData(" apps/mouth/src --include=*.ts*
grep -rn "allowlist\|ALLOWED_EVENTS" apps/backend-rag/backend --include=*.py
```

---

## A. Analytics Events

Sumber pre-fill: MASTER_CONTEXT §12.6 (dokumen). **Belum diverifikasi ulang terhadap repo** — jalankan perintah A & A2.

| Event                    | Surface / komponen pemanggil | Status     | Catatan                                                                               |
| ------------------------ | ---------------------------- | ---------- | ------------------------------------------------------------------------------------- |
| `lead_whatsapp_cta`      | `WhatsAppLeadButton.tsx`     | LIVE       | Satu event, dibedakan lewat param `source`. **Bukan** event terpisah per halaman      |
| `kbli_chat_question`     | ZantaraChat (KBLI)           | LIVE       |                                                                                       |
| `visa_chat_question`     | VisaChat                     | LIVE       |                                                                                       |
| `property_chat_question` | —                            | ORPHAN     | Dispatcher ada, surface belum dibangun. Drop dari baseline                            |
| `home_whatsapp_cta`      | —                            | DEPRECATED | Diganti `lead_whatsapp_cta` + `source=homepage_hero`. **Jangan dipakai di audit GA4** |

> Kasus 18 Jun: dilaporkan _"event `article_whatsapp_cta` tidak ada"_. Realitanya datanya sudah ada sejak awal, hanya bernama `lead_whatsapp_cta` + `source=article`. Ini kelas error paling sering — cek tabel ini sebelum bilang "belum ada tracking".

---

## B. LeadSource enum

**SSOT:** `apps/backend-rag/backend/services/lead_capture/source.py`
**Aturan permanen:** setiap `source="..."` di frontend WAJIB ada di enum ini. CTA baru = dua perubahan (FE + BE enum), satu PR atau dua PR terkoordinasi.

| source                          | Frontend trigger             | Status                        |
| ------------------------------- | ---------------------------- | ----------------------------- |
| `kbli_navigator`                | KBLIConsultationCTA          | LIVE                          |
| `homepage_hero`                 | hero CTA                     | LIVE (PR #2495)               |
| `article`                       | ArticleClient                | LIVE                          |
| `zantara_widget_handoff`        | Zantara widget               | LIVE                          |
| `visa_match` / `visa_clock`     | `/visa/match`, `/visa/clock` | LIVE                          |
| `pricing_modal`                 | pricing modal                | LIVE                          |
| `kbli_decoder` / `kbli_builder` | —                            | PLANNED — enum siap, FE belum |
| `tax_gap` / `zoning_check`      | —                            | PLANNED — enum siap, FE belum |

> Hero bug 422 hidup **10 hari** karena kontrak ini tidak terlihat dari sisi frontend. Sekarang dijaga CI parity check.

---

## C. Hook & Komponen Wajib Pakai Ulang

| Kebutuhan            | Pakai ini                                                            | JANGAN bikin / pakai                                                |
| -------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------- |
| CTA WhatsApp apa pun | `WhatsAppLeadButton.tsx` (props: `source`, `whatsappContext`, `utm`) | `buildWhatsAppLink()` polos, `<a href="wa.me/...">`, nomor hardcode |
| Harga apa pun        | `usePricingData` / `ServicePricingCard.tsx` / `ServicePricing.tsx`   | Angka hardcode di MDX atau komponen                                 |
| Gambar apa pun       | `BZImage.tsx` / `next/image`                                         | `<img>` mentah                                                      |
| Title & canonical    | `layout.tsx` (server component)                                      | `page.tsx` yang punya `"use client"` — tidak bisa export metadata   |

> Kasus 22 Jun: Subhi minta pair dengan Asya untuk pricing. Jawaban Antonello: pattern-nya sudah live — _"jangan bikin baru"_. Cek tabel ini sebelum minta koordinasi.

---

## D. CI Checks — REQUIRED vs ADVISORY

**Status: UNVERIFIED.** Isi setelah menjalankan perintah D atau setelah konfirmasi Antonello.

| Check                      | Required?                    | Kalau merah artinya                                                          |
| -------------------------- | ---------------------------- | ---------------------------------------------------------------------------- |
| Frontend Tests             | UNVERIFIED                   |                                                                              |
| source parity (LeadSource) | UNVERIFIED                   | FE/BE tidak sync                                                             |
| actionlint                 | UNVERIFIED                   |                                                                              |
| adversarial-review gate    | UNVERIFIED                   | `research/*.md` kurang frontmatter                                           |
| Snyk                       | UNVERIFIED — diduga advisory |                                                                              |
| SonarQube                  | UNVERIFIED — diduga advisory |                                                                              |
| CodeQL                     | UNVERIFIED                   | Gagal dengan runtime ~4 detik = pola yang sudah dikenal, bukan failure nyata |

> Ingat: `mergeStateStatus` BLOCKED sementara semua check hijau → cari required check yang CANCELLED atau tidak pernah melapor. Fix: `gh pr update-branch <N>`.

---

## E. Perilaku By-Design yang Sering Dikira Bug

| Gejala                                  | Penjelasan                                                        | Sumber           |
| --------------------------------------- | ----------------------------------------------------------------- | ---------------- |
| Clients list kosong di dashboard        | RBAC by design — role `team`, filter `assigned_to`                | Antonello 22 Jun |
| GA4 custom dimension "No data"          | Delay processing 24–48 jam                                        | memory           |
| GA4 DebugView "No devices"              | GA Debugger extension belum aktif di Brave                        | memory           |
| JSON-LD tidak terdeteksi `curl \| grep` | RSC Flight chunks meng-escape quotes                              | Antonello 8 Jun  |
| `app_*` data sebelum 11 Jun 2026        | Undercount (session_id hilang, 422) — jangan jadi baseline        | Antonello 11 Jun |
| HTTP 200 di route yang tidak ada        | `(blog)/[category]` menangkap semua root path tanpa route sendiri | Antonello 30 Jul |
| Funnel tax/property 0 event             | Funnel-nya memang belum dibangun — bukan bug tracking             | Antonello 17 Jul |
| Beacon GA4 hilang di Network tab        | Browser clear log saat unload — aktifkan Preserve Log             | memory           |

---

## F. Kontrak Lintas-Sistem — sumber kelas bug tersembunyi

Setiap baris bertanda **RAWAN** adalah bug yang belum terjadi. Ini daftar kandidat CI check berikutnya untuk diusulkan ke Antonello.

| Kontrak            | Sisi A                             | Sisi B                                      | Penjaga                                                     |
| ------------------ | ---------------------------------- | ------------------------------------------- | ----------------------------------------------------------- |
| `source` string    | FE `source="..."`                  | BE enum `LeadSource`                        | ✅ CI parity check                                          |
| Nama event         | `trackFunnelEvent()`               | Backend allowlist analytics                 | ⚠️ **manual — RAWAN**                                       |
| Pricing key        | `usePricingData(service)`          | `/api/pricing/calculate`                    | ⚠️ **manual — RAWAN**                                       |
| Title template     | Root `layout.tsx` `title.template` | Child `layout.tsx`                          | ⚠️ **manual — RAWAN** (sudah menyebabkan PR #3618 gagal CI) |
| Route ↔ sitemap    | `app/**/page.tsx`                  | `sitemap.ts`                                | UNVERIFIED                                                  |
| Deeplink WA number | CTA `wa.me/<nomor>`                | Nomor yang menulis ke `meta_inbox_messages` | ⚠️ **manual — RAWAN** (penyebab 110 lead_intents 0 match)   |

> Ini satu-satunya bagian yang layak jadi pertanyaan ke Antonello, karena menyangkut CI dan backend allowlist. Kirim sebagai **satu email**, bukan tiga ping.

---

## Ritual perawatan

| Kapan                                              | Aksi                                                                     |
| -------------------------------------------------- | ------------------------------------------------------------------------ |
| Setiap PR yang menambah source/event/hook/komponen | Update tabel terkait **di PR yang sama** — bukan menyusul                |
| Jumat 14:00                                        | Jalankan blok perintah di atas, bandingkan dengan tabel. Selisih = drift |
| Sebelum eskalasi ke Antonello                      | Baca tabel A, B, E. Kalau jawabannya ada di sini — jangan kirim          |
| Kalau 30 hari tidak pernah dibuka                  | Hapus file ini. Jangan dipelihara karena rasa bersalah                   |

---

_Bagian dari LAWS.md v3.1 — Kelas K0. Nol dari 10 eskalasi periode Apr–Jun benar-benar butuh keputusan Antonello._
