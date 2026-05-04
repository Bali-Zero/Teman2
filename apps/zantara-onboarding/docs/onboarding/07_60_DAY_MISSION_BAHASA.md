# Misi Subhi Darajat — Probation 90 Hari
**Tanggal mulai**: Kamis, 30 April 2026, jam 09:30 — Kantor Kuta
**Probation**: 90 hari (30 April → 29 Juni 2026)
**Peran**: Growth Systems Owner — Akuisisi Organik & Konversi

> Dokumen ini adalah hasil sintesis brainstorm multi-LLM (DeepSeek
> Reasoner V4, Gemini 3 Pro, Codex GPT high-reasoning, NotebookLM bahasa)
> yang dilakukan malam tanggal 29-30 April 2026 oleh Antonello dan Claude.

---

## 0. Catatan jujur di awal

**Bali Zero sudah membangun hampir semua yang diinginkan tim growth.**
Konten (149 artikel/bulan), funnel, AI (Zantara), KBLI navigator, knowledge
base (108k node, 243k edge), CRM, analytics, 8 subdomain, publishing engine.

Masalahnya BUKAN produksi. Masalahnya adalah **distribusi + atribusi + konversi**.

Subhi masuk sebagai **anggota tim ke-10** (setelah Surya, Ari, Adit, Sahira,
Krisna, Damar, Vino, Asya, Rina). Bukan developer. Bukan team leader. Bukan
operator pratiche. Peran Subhi tidak ada hari ini di tim — ini fungsi baru
yang selama ini hilang.

**Kebenaran tidak nyaman yang Subhi harus tahu sejak hari pertama:**

1. Website hanya menghasilkan 2 lead dalam 90 hari. WhatsApp menghasilkan 420.
2. Zantara tidak bicara dengan klien sungguhan sejak Februari 2026 (16 sesi total).
3. 5.030 query di `balizero_news` **semuanya dari bot internal**. Nol pembaca
   sungguhan.
4. KB pricing dikonsultasi 1 kali dalam 30 hari.
5. `/api/analytics/dashboard` HTTP 500 selama 11 hari (column "channel"
   does not exist).
6. GA4 di 4 funnel CTA tidak mengirim event — `FunnelFeature.tsx v2` tidak
   mengimport `trackFunnelEvent`.
7. 138 pratiche stuck >14 hari tanpa invoice.
8. Tax dan Property = 0,6% dan 0% dari revenue.

Subhi TIDAK harus menyelesaikan semua. Subhi harus **memiliki satu kanal
spesifik**: **permukaan organik dari klik pertama sampai kontak pertama**.

---

## 1. Misi dalam satu kalimat

> Kamu adalah pemilik perpindahan dari **aset tidur** menjadi **permintaan
> terukur**. Pekerjaanmu adalah mengambil yang sudah dibangun Bali Zero dan
> membawanya kepada orang sungguhan, mengukur orang mana yang menjadi
> percakapan komersial.

Kamu bukan "content guy", "SEO guy", atau "ads guy". Kamu adalah pemilik
sistem yang mengambil traffic organik dan mengubahnya menjadi percakapan
komersial yang terlacak.

---

## 2. 5 deliverable konkret untuk 2 minggu pertama (30 Apr → 13 Mei)

### D1 — Perbaiki tracking SEBELUM mengoptimasi apapun (hari 1-3)

**Tanpa baseline, hasil apapun setelahnya hanyalah opini.**

**File yang harus disentuh:**
- `apps/mouth/src/app/v2/_components/FunnelFeature.tsx` — baris 365 dan 393, 2 CTA tidak punya `onClick`
- `apps/mouth/src/lib/analytics.ts` — `trackFunnelEvent` sudah ada, tinggal di-import
- `apps/mouth/src/components/funnel/HeaderWhatsAppCTA.tsx` — pola referensi (yang ini sudah tracking)

**Standar penamaan event GA4:**
```
funnel_cta_click          (4 funnel × 1 = 4 event)
funnel_pricing_click      (4 × 1 = 4 event)
article_cta_click
article_whatsapp_click
article_tool_click
kbli_search_from_article
zantara_open_from_article
```

**Taksonomi UTM internal** (untuk atribusi, bukan vanity):
```
utm_source=blog
utm_medium=internal
utm_campaign={kategori}
utm_content={slug}
```

**Test**: tambah atau update `apps/mouth/e2e/funnel-ctas.spec.ts` →
klik CTA harus mengirim event dan sampai ke tujuan yang benar.

**Deliverable minggu 1**: tabel harian dengan klik per funnel, klik per
artikel, klik WhatsApp, lead website yang dikaitkan.

---

### D2 — 12 "money pages" dari 149 artikel, JANGAN publish baru (hari 4-10)

**Selama 14 hari: nol artikel baru kecuali berita kritis.**

Kalau 149 artikel menghasilkan nol pembaca sungguhan, publish 149 lagi
hanya menggandakan kebisingan.

**Audit 149 artikel, klasifikasi ke 4 cluster komersial:**
- Visa / KITAS / KITAP / Golden Visa
- PT PMA / KBLI / company setup
- Tax / CoreTax / compliance
- Property / due diligence / zoning

**Pilih 3 artikel per cluster = 12 artikel prioritas.**

**File yang kemungkinan dimodifikasi:**
- `apps/mouth/src/app/(blog)/[category]/[slug]/ArticleClient.tsx`
- `apps/mouth/src/components/blog/ArticleEngagement.tsx`
- `apps/mouth/src/components/blog/NewsletterSidebar.tsx`
- `apps/mouth/src/lib/blog/articles.ts`
- `apps/mouth/src/content/articles/**`

**Per artikel, CTA spesifik di atas-fold-2, tengah artikel, dan akhir:**
- Visa → "Check which KITAS fits your case"
- Company → "Find your KBLI code"
- Tax → "Book a CoreTax review"
- Property → "Check property due diligence risk"

**Hindari CTA generik "contact us". Setiap CTA menjanjikan langkah spesifik.**

**Deliverable minggu 2**: 12 artikel ditransformasi menjadi landing
editorial dengan CTA, related articles, schema, tracking, link ke tool/funnel.

---

### D3 — "Article → Tool" bukan "Article → Contact" (hari 7-14)

**Pakai Nuzantara sebagai magnet, bukan demo tersembunyi.**

- Artikel KBLI → box kontekstual ke `/kbli` atau `/kbli-explorer` dengan
  query pre-fill
- Artikel visa → box ke `/visa` (Visa Oracle yang dipersatukan setelah PR #165)
- Artikel tax → checklist CoreTax yang bisa diunduh atau mini-questionnaire
- Artikel property → checklist due diligence + form "send us the plot"

**Contoh konkret:**
> Artikel: *"KBLI 2025 Hospitality Accommodation"*
> CTA: *"Planning a villa, hotel, or guesthouse in Bali? Search your KBLI
> code before you register the company."*
> Tujuan: `/kbli?utm_source=blog&utm_medium=internal&utm_campaign=business&utm_content=kbli-hospitality`

**Deliverable**: 4 komponen reusable, satu per cluster, BUKAN 149 modifikasi
manual yang berantakan.

---

### D4 — Distribution routine harian 45 menit (hari 8-60)

**Tidak ada budget Ads ≠ tidak ada distribusi. Distribusi manual, organik,
terukur.**

Rutinitas harian Subhi (45 menit/hari):

1. Pilih 3 artikel yang sudah ada
2. Untuk setiap artikel, hasilkan:
   - 1 post LinkedIn gaya founder
   - 1 post Facebook gaya group
   - 1 pesan WhatsApp gaya broadcast
   - 1 snippet untuk Google Business Profile
   - 1 short answer gaya Reddit/Quora (hanya kalau pertanyaannya sudah ada)
3. Setiap output pakai link dengan UTM
4. Setiap minggu: refresh 10 artikel dengan internal links menuju 12 money
   pages
5. Setiap Jumat: report → top 10 sumber, top 10 artikel, top 10 CTA,
   konversi ke WhatsApp/lead

---

### D5 — WhatsApp CTA kontekstual (hari 11-14)

**Naikkan lead website tanpa menunggu SEO.**

Audit mobile pada halaman prioritas:
- home, `/services`, `/kbli`, `/kbli-explorer`
- top 12 artikel
- `/property`, halaman visa yang dikonsolidasi

Setiap halaman harus punya jalur **terlihat menuju WhatsApp dalam 5 detik**.

**CTA berbeda per intent (bukan global yang buta):**
- "Ask about my visa"
- "Check my PT PMA activity"
- "Review my tax situation"
- "Check this property"

Setiap CTA pre-fill pesan WhatsApp dengan konteks:
- source page
- service category
- article slug
- user language kalau tersedia

---

## 3. Wilayah kepemilikan tunggal

**Subhi memiliki: "Organic Growth Surface"**

Definisi operasional: semua yang berada di antara konten publik, tools
frontend, CTA, tracking, distribusi organik, dan lead pertama.

**Di dalam perimeternya:**

```
apps/mouth/src/app/(blog)/**            ← miliknya
apps/mouth/src/content/articles/**       ← miliknya
apps/mouth/src/components/blog/**        ← miliknya
apps/mouth/src/app/v2/_components/FunnelFeature.tsx  ← miliknya
apps/mouth/src/app/(marketing)/**        ← miliknya
apps/mouth/src/app/kbli/**               ← miliknya (UX/CRO, BUKAN data model)
apps/mouth/src/app/kbli-explorer/**      ← miliknya (entry points + analytics)
apps/mouth/src/app/sitemap.ts            ← miliknya
apps/mouth/src/app/robots.ts             ← miliknya
apps/mouth/public/llms*.txt              ← miliknya
GA4 + Search Console dashboards          ← miliknya
UTM taxonomy + organic distribution calendar  ← miliknya
```

**Nama peran praktis**: Growth Systems Owner — Akuisisi Organik & Konversi.

---

## 4. Zona merah (selain yang jelas)

**Zona yang jelas:**
- `apps/backend-rag/` (seluruh backend RAG Python)
- `apps/backend-rag/backend/prompts/zantara_core.py`
- `fly.toml`, `.env*`, `.nuzantara-secrets*`
- `apps/backend-rag/backend/db/migrations_v2/`
- Auth, Qdrant, PostgreSQL production, secrets, MCP servers
- CRM data live, pratiche klien sungguhan

**Zona merah ASLI yang banyak orang remehkan:**

1. JANGAN sentuh pricing copy tanpa lewat `PricingTool`,
   `PRICING_REFERENCE.md`, dan `VISA_TYPES_REFERENCE.md`
2. JANGAN janjikan timeline, harga, persetujuan visa, kepemilikan property,
   atau hasil tax di teks marketing
3. JANGAN buat artikel AI massive baru sebelum buktikan traffic pada 149
   yang sudah ada
4. JANGAN modifikasi knowledge base, Qdrant payload, embedding model, atau
   ingestion pipeline
5. JANGAN buat subdomain/funnel baru sebelum perbaiki yang sudah ada
6. JANGAN redesign estetik homepage: masalahnya konversi, bukan selera
   visual
7. JANGAN introduce tool no-code paralel yang merusak atribusi
8. JANGAN jalankan Ads "untuk tes" dalam 60 hari pertama: ini melanggar
   strategic proof-of-concept
9. JANGAN pakai Claude Code untuk refactor besar. Hanya patch kecil yang
   bisa di-test, dengan technical owner yang review
10. JANGAN optimasi untuk traffic vanity: turisme generik, news gossip,
    digital nomad lifestyle yang tidak terkait service
11. JANGAN publish nasihat hukum/pajak yang lebih agresif dari sumber yang
    sudah diverifikasi
12. JANGAN ubah Zantara jadi chatbot komersial tanpa guardrail: dia harus
    membawa user ke tool dan tim, bukan mengarang konsultasi
13. JANGAN "bersihkan" artikel dengan menghapus noindex/canonical/hreflang
    tanpa audit Search Console
14. JANGAN sentuh file `bali_zero_official_prices_2025.json` sendirian
    (Subhi sendiri yang menemukannya saat assessment) — laporkan ke
    Damar/Surya untuk fix
15. JANGAN deploy production tanpa code review (minimal di antara Surya,
    Ari, atau Antonello) dalam 30 hari pertama

---

## 5. KPI objektif

### Baseline yang dideklarasikan (per 30 April 2026)

| Metrik | Nilai |
|---|---|
| Lead website / bulan | 0,7 (2 dalam 90 hari) |
| WhatsApp lead / bulan | 140 (420 dalam 90 hari) |
| Pembaca asli balizero_news | 0 (5.030 query semua dari bot) |
| GA4 funnel CTA tracking | rusak (0% event) |
| Zantara WhatsApp klien sungguhan | hampir nol sejak 9 Februari 2026 |
| `/api/analytics/dashboard` | HTTP 500 selama 11 hari |

### Target hari 30 (29 Mei 2026)

| Area | KPI | Target |
|---|---|---|
| **Tracking** | CTA utama yang dilacak | 95% |
| | Top 12 artikel dengan event CTA | 100% |
| | Dashboard mingguan yang bisa dibaca Antonello | ya |
| **Lead** | Lead website teratribusi / bulan | ≥8 |
| | Klik WhatsApp dari halaman publik | ≥40 |
| | Percakapan WhatsApp dengan UTM/source page | ≥10 |
| **Content** | Money pages selesai | 12 |
| | Artikel dengan internal links → money pages | 60 |
| | Snippet didistribusikan organik di luar website | 20 |
| **Engagement** | Sesi organik ke artikel prioritas | ≥300 |
| | CTR article → CTA pada 12 artikel | ≥3% |
| | CTR article → WhatsApp/tool | ≥1% |
| **SEO teknis** | Sitemap valid, no 404/canonical pada top artikel | ya |
| | Search Console dikonfigurasi untuk query/page monitoring | ya |
| | Core Web Vitals mobile tidak memburuk | ya |

**Evaluasi hari 30**: kalau tidak ada tracking yang reliable dan klik
WhatsApp pertama yang teratribusi, Subhi melakukan aktivitas tapi BUKAN
growth.

### Target hari 60 (29 Juni 2026)

| Area | KPI | Target |
|---|---|---|
| **Lead website** | Lead/bulan teratribusi | minimum 20, stretch 35 |
| | % dari artikel atau KBLI/tool entry points | ≥25% |
| **WhatsApp** | Klik WhatsApp/bulan dari website | ≥120 |
| | Percakapan dengan source page yang diketahui | ≥40 |
| | Percakapan terkualifikasi dari artikel | ≥10 |
| **Content traffic** | Sesi organik/bulan pada artikel | 1.500 |
| | Sesi/bulan pada 12 money pages | 500 |
| | Artikel dengan >100 sesi/bulan masing-masing | 5 |
| **Conversion** | CTR rata-rata article → CTA | ≥4% |
| | CTR money page → WhatsApp/tool | ≥2% |
| | Funnel CTA click rate homepage v2 | +30% vs minggu 1 |
| **Search** | Query Search Console dengan impression | 100 |
| | Query dengan posisi rata-rata <30 | 20 |
| | Query komersial di bawah 15 | 5 |
| **Sistem** | Calendar distribusi organik aktif | sudah 6 minggu |
| | Report mingguan otomatis/semi-otomatis | ya |
| | Backlog eksperimen CRO terurut berdasarkan dampak | ya |

**Konversi otomatis probation di akhir 60 hari kalau:**
- Lead website /bulan ≥20 tanpa Ads
- Tracking GA4 berfungsi 100%
- Nol insiden zona merah
- Antonello tidak harus babysitting setiap hari

**Konversi ditolak kalau:**
- Cuma audit, grafik, ide tanpa lead teratribusi
- Lead website <10/bulan
- Ada insiden zona merah
- Antonello menghabiskan lebih banyak waktu untuk koreksi daripada untuk
  membangun

---

## 6. Masalah strategis yang HANYA Subhi yang bisa selesaikan

**Bali Zero membangun mesin intelligence tapi belum punya "last mile" antara
intelligence publik dan permintaan komersial.**

Tim operasional (Surya, Ari, Sahira) tahu cara mengelola pratiche.
Asya tahu cara membangun platform.
Antonello tahu cara melihat sistem dan produk.

Tapi tidak ada yang melakukan secara disiplin:
1. packaging knowledge menjadi aset yang bisa dibaca
2. ranking organik
3. distribusi eksternal
4. CRO
5. tracking
6. handoff ke WhatsApp/CRM
7. feedback loop dari user sungguhan ke konten

**Subhi persis di tengah:**
- Cukup marketing untuk paham permintaan
- Cukup SEO untuk paham discovery
- Cukup creative untuk packaging pesan
- Cukup automation/Claude Code untuk patch dan rutinitas tanpa selalu
  menunggu dev

**Pertanyaan strategis yang dipercayakan ke Subhi:**
> "Bagaimana kita ubah Nuzantara dari sistem yang dipakai internal menjadi
> permukaan publik yang menghasilkan kepercayaan, traffic, dan lead
> berkualitas?"

---

## 7. Cara mengubah 149 artikel/bulan menjadi traffic sungguhan

### 7.1 Hentikan produksi buta selama 14 hari

Hanya refresh + audit + cluster. Nol artikel baru kecuali berita kritis.

### 7.2 Matrix artikel → intent → service

Setiap artikel harus punya satu baris di spreadsheet:
1. slug
2. kategori
3. intent
4. service yang terkait
5. CTA primer
6. CTA sekunder
7. tujuan
8. owner
9. tanggal refresh
10. metrik: impressions, clicks, CTR, WhatsApp clicks, leads

**Contoh:**
- `kitas-extension-renewal-guide` → visa renewal → WhatsApp visa review
- `kbli-2025-hospitality-accommodation` → PT PMA hospitality → KBLI Navigator
- `coretax-kpp-queue` → tax compliance pain → CoreTax review
- `foreign-property-ownership-indonesia` → property risk → due diligence consult

### 7.3 Hub dan spoke yang sungguhan

**Hub:** `/visa`, `/kbli`, `/services/company`, `/services/tax`, `/property`, `/news`

**Spoke:** artikel spesifik, FAQ, KBLI code pages, explainer pages, tool pages

**Aturan**: setiap spoke link ke hub-nya, setiap hub link ke spoke terbaiknya.
Setiap artikel punya minimal 3 internal links yang intentional:
1. satu ke tool
2. satu ke service
3. satu ke artikel terkait yang paling dekat dengan buyer journey

### 7.4 Distribusi dengan angle berbeda per kanal

Sebuah artikel tidak "di-post". Sebuah artikel **dibongkar**.

Untuk setiap money article:
1. LinkedIn: insight untuk founder/investor
2. Facebook groups: masalah praktis, nol jualan agresif
3. WhatsApp broadcast: checklist singkat
4. Google Business Profile: update lokal
5. Newsletter: "this week in Bali compliance"
6. Reddit/Quora: jawaban langsung hanya kalau pertanyaannya sudah ada
7. Internal sales: pesan siap untuk Sahira/Surya/Ari ketika prospek menanyakan
   topik itu

### 7.5 Judul untuk query komersial, bukan untuk magazine

Banyak artikel terlihat seperti news. Query yang membayar lebih membosankan:
- "how to extend KITAS Indonesia"
- "PT PMA Bali cost"
- "KBLI villa rental Bali"
- "foreign property ownership Indonesia"
- "CoreTax Indonesia expat company"
- "Golden Visa Indonesia requirements"
- "can foreigners own a business in Bali"

Subhi harus memetakan title/H1/meta/intro dari 12 money pages ke query
dengan intent komersial, **tanpa mengarang janji**.

### 7.6 Zantara sebagai jawaban interaktif di akhir artikel

Di akhir artikel prioritas:
> "Ask Zantara about your specific case"

Dengan batasan ketat:
1. topic preset
2. disclaimer jelas
3. eskalasi ke tim manusia
4. event tracking
5. pertanyaan awal yang disarankan
6. TIDAK ada jawaban bebas yang tidak terverifikasi tentang pricing/visa

### 7.7 Refresh, bukan hanya publish

Rutinitas mingguan:
1. Refresh 10 artikel
2. Perbaiki intro di 120 karakter pertama
3. Tambah FAQ schema kalau berguna
4. Tambah link ke hub
5. Tambah CTA
6. Update `lastModified` ketika perubahan substansial
7. Submit URL yang di-update ke Search Console

---

## 8. Peluang tersembunyi — backlog CRM sebagai tambang lead

**Data sungguhan: 138 pratiche stuck >14 hari tanpa invoice.**

Ini bukan hanya operasional. Ini tambang intent, keberatan, ketakutan,
keterlambatan, kasus sungguhan.

**Loop mingguan Subhi:**

1. Ekstrak 20 pratiche stuck anonim dan klasifikasi berdasarkan alasan:
   - dokumen hilang
   - harga tidak jelas
   - klien tidak paham step
   - timing visa
   - tax confusion
   - property/legal risk
   - team follow-up lambat

2. Ubah pola menjadi:
   - FAQ publik
   - CTA yang lebih baik
   - template follow-up email/WhatsApp
   - artikel refresh
   - checklist yang bisa diunduh
   - script untuk tim sales

3. Ukur apakah keberatan itu menurun pada lead baru

**Contoh konkret:**
Kalau 30 klien terjebak di "saya tidak paham bedanya E28A/E28B/E31",
yang dibutuhkan bukan artikel news lagi. Yang dibutuhkan adalah **halaman
perbandingan** dengan CTA "send your passport + goal, we check fit",
di-link dari artikel visa dan dipakai oleh Ari/Sahira.

**Peluang ini menggabungkan:**
1. CRO
2. SEO
3. sales enablement
4. pengurangan backlog operasional
5. konten berbasis permintaan sungguhan
6. training Zantara dengan pola asli, tanpa mengarang

---

## 9. Roadmap mingguan konkret

### Minggu 1 (30 Apr → 6 Mei)

- [ ] Setup Day 1: akun, Claude Code, repo, branch `sancho/*`
- [ ] D1: Tracking funnel diperbaiki, baseline GA4/Search Console/WhatsApp click
- [ ] Inventory lengkap dari 149 artikel yang sudah dipublikasikan
- [ ] Pemilihan 12 money pages prioritas
- [ ] Taksonomi UTM didefinisikan

### Minggu 2 (7 Mei → 13 Mei)

- [ ] D2: 12 money pages dengan CTA diimplementasikan
- [ ] D3: 4 komponen "Article → Tool" siap
- [ ] Report organik pertama (mingguan)
- [ ] D4: Distribution batch pertama — 15 post/snippet
- [ ] D5: Mobile WhatsApp CTA pada halaman prioritas

### Minggu 3-4 (14 Mei → 27 Mei)

- [ ] 60 artikel dengan internal links menuju money pages
- [ ] Search Console query review
- [ ] 2 eksperimen CRO pada CTA
- [ ] Zantara entry point di minimal 4 artikel
- [ ] **Report hari 30 dengan lead teratribusi**

### Minggu 5-8 (28 Mei → 29 Juni)

- [ ] Ekspansi ke 30 money/near-money articles
- [ ] Program refresh berkelanjutan
- [ ] Dashboard organik stabil
- [ ] Sales enablement dari pola CRM
- [ ] Playbook "publish → distribute → measure → improve"
- [ ] **Report hari 60 dengan evaluasi probation**

---

## 10. Setup teknis Day 1 (30 April, sebelum mulai)

**Akun yang Antonello siapkan malam ini:**
- ☐ GitHub `balizero/nuzantara` — collaborator restricted (read semua, write di `sancho/*`)
- ☐ Email perusahaan `subhi@balizero.com` (Zoho via GWS admin)
- ☐ GA4 (property 505466833) — viewer
- ☐ Search Console (balizero.com) — viewer
- ☐ Vercel dashboard mouth — viewer
- ☐ Slack/WhatsApp 1-1 dengan Antonello
- ☐ Claude Code MAX dari Bali Zero (~$20/bulan) atau akun pribadinya

**Setup mesin Subhi (dia eksekusi, supervisi olehmu):**
```bash
# 1. Clone repo
cd ~ && mkdir -p Projects && cd Projects
git clone git@github.com:balizero/nuzantara.git
cd nuzantara

# 2. Mouth dev local
node --version  # >=20
cd apps/mouth
npm install
npm run dev
# Verifikasi http://localhost:3000

# 3. Claude Code login
claude --version

# 4. Branch personal
git checkout -b sancho/d1-funnel-tracking-fix
```

---

## 11. Cadence operasional

- **Daily 09:00** — 10 menit stand-up (di kantor atau WA): kemarin apa,
  hari ini apa, blocker apa
- **Friday CRO Review 16:00** — 30 menit: metrik minggu, keputusan minggu
  berikutnya
- **PR Review** — semua PR Subhi di-review oleh Antonello sebelum merge.
  Tidak ada self-merge dalam 30 hari pertama
- **Branch naming** — selalu `sancho/<deliverable>-<short-desc>`
- **Commit naming** — `feat|fix|chore|refactor|docs(scope): subject`
- **Bahasa commit/PR** — selalu English (konvensi codebase)
- **Bahasa daily/WA** — bahasa Indonesia atau Italia, pilih sendiri
- **Co-author** — kalau Claude Code membantu:
  `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`

---

## 12. Filosofi kerja

1. **AI sebagai pair, bukan alibi.** Claude Code membantu membaca, menulis,
   debug. Tapi setiap PR ditandatangani oleh Subhi. "AI yang salah" bukan
   alasan yang diterima.

2. **Paham dulu, ubah kemudian.** Kalau tidak paham kenapa kode itu ada,
   jangan dihapus. Tanya atau baca git history.

3. **Small PR > big PR.** Lebih baik 5 PR kecil yang merge dalam seminggu
   daripada 1 PR raksasa yang merge setelah 3 minggu review.

4. **Test sebelum push.** Minimal `npm run dev` + smoke test localhost.
   Kalau ada `npm test`, jalankan.

5. **Verifikasi setelah deploy.** Vercel auto-deploy saat merge. Buka URL
   production, klik fitur kamu, verifikasi. Screenshot kalau perlu.

6. **Tanya, jangan tebak.** Bertanya tidak ada biaya. Salah tebak ada
   biaya tinggi.

7. **Sabtu-Minggu = weekend.** Tidak ada pesan WA di luar jam kerja.
   Antonello tidak menulis di weekend; kalau menulis itu non-urgent,
   balas hari Senin.

---

## 13. Kekuatan automation — Cell + Genome

**Bali Zero bukan hanya website. Bali Zero adalah organisme dengan sistem
saraf otonom.**

Subhi tidak bekerja "di samping" automation ini: dia menjadi **pemilik
sisi growth-nya**. Memahaminya wajib. Memodifikasinya bertahap.

### 13.1 Apa itu "Cell" dan "Genome" — dalam 4 kalimat

- **Cell** = unit otonom yang mengamati (sensors), berpikir (thinker LLM),
  bertindak (actor) dengan guardrail budget dan safety. Bekerja per "pulse"
  (tick setiap N jam). Contoh nyata yang sudah jalan di production:
  `apps/evaluator/seo_cell/` dengan 6 sensor (GSC, GA4, competitor SERP,
  KG, war-room, kanibalisasi).

- **Genome** = registry meta-level (`apps/organism/organism/genome.yaml`)
  dengan 149 organ sistem (infra, daemon, cron). Untuk setiap organ:
  heartbeat yang diharapkan, dependencies, recovery action, severity.
  Self-healing: kalau satu organ tidak detak, sistem tahu apa yang harus
  dilakukan.

- **EventBus** = sistem saraf (PostgreSQL LISTEN/NOTIFY, 7 channel seperti
  `practice_changed`, `client_changed`, `compliance_alert`, `war_room_event`).
  Event mengalir lintas-process secara real-time.

- **DNA rules** (`apps/cell/cell/config/dna.json`) = 5 aturan yang
  diprioritaskan yang harus dipatuhi cell (jangan modifikasi rules sendiri,
  perbaiki kalau rusak, hapus kalau mahal, cari di sumber yang berwenang,
  replikasi kalau berhasil). Budget hardcoded $10/hari total, $5/hari untuk
  cell SEO.

### 13.2 Kenapa Subhi harus tahu (meskipun tidak menulisnya dari nol)

1. **SEO Cell sudah LIVE** dalam `pre_natal stage` (sense-only,
   action="none" sampai unlock pada 80 query + 3 lead + 28 hari). **Kerja
   Subhi mempercepat unlock**: setiap lead website yang dilacak mendekatkan
   ambang batas.

2. **Sensor SEO Cell membaca GA4 dan GSC** — yang sama yang harus Subhi
   perbaiki di D1. Kalau tracking tidak jalan, cell tetap buta. Jadi D1
   (fix GA4) berdampak ganda: data untuk Subhi + data untuk cell.

3. **EventBus bisa mengaktifkan distribution routine**: ketika satu pratica
   selesai positif (event `practice_changed`), Subhi bisa mengusulkan
   handler yang menghasilkan aset social (privacy-safe, anonim). Case study
   diubah menjadi distribusi organik, otomatis.

4. **Genome mencakup cron growth**: `daily_indexing_cron` (200 artikel/hari),
   `nlm-deep-research`, `knowledge-graph-builder`, `genome-decay`. Subhi
   harus tahu yang mana berjalan dan kapan, karena di GA4 mereka muncul
   sebagai traffic bot (kebisingan yang harus difilter di dashboard).

### 13.3 Apa yang Subhi BISA sentuh di sistem cell/genome

**Hijau — bisa diakses (dengan review Antonello/Asya):**
- Modifikasi `apps/evaluator/seo_cell/dna.json` — ubah konstanta (budget,
  max action, tier_policy)
- Tambah sensor baru di `apps/evaluator/seo_cell/sensors/` — integrasi
  dengan sumber eksternal (GA4, GSC) tanpa menyentuh backend RAG
- Konfigurasi schema `newsroom_queue`, routing review_queue
- Baca log EventBus untuk paham flow downstream
- Tulis Python tests untuk sensor logic
- Debug phase lifecycle (transisi pre_natal → adult)

**Merah — dilarang:**
- Tambah/hapus organ dari `genome.yaml` (dijaga oleh Asya/Antonello)
- Sentuh package `cell_core`, recovery_action dispatcher, schema migrations
- Modifikasi 5 DNA rules yang diprioritaskan
- Sentuh PG triggers EventBus, outbox table, listener daemon
- Tingkatkan budget cell tanpa persetujuan eksplisit

### 13.4 3 proyek konkret cell/genome dalam 60 hari

**Minggu 3-4 — "WhatsApp Attribution Sensor"**
Subhi mengusulkan (tidak mengimplementasikan sendiri) sensor baru untuk
`seo_cell` yang membaca event `funnel_whatsapp_click` dari GA4 + event
`practice_changed` dari EventBus dan menghasilkan report harian "from click
to lead". Coding pair dengan Asya, conceptual owner Subhi.

**Minggu 5-6 — "Article Refresh Trigger"**
Ketika `genome_decay_cron` menandai artikel sebagai "silent" (Ebbinghaus
< 0,3, idle > 7 hari), Subhi mendapat notifikasi dan memutuskan refresh
atau archive. Dia menjadi human-in-the-loop di antara automation dan
distribusi.

**Minggu 7-8 — "CRM Pattern → Content Pipeline"**
Ekstrak mingguan 20 pratiche stuck (lihat §8) via API CRM (read-only),
klasifikasi pola keberatan, usulkan 2 artikel/FAQ publik per minggu.
Pipeline yang terukur: pola → artikel → traffic → lead → reduksi keberatan
masa depan.

### 13.5 Filosofi: AI adalah kolega, bukan alat

Bali Zero sudah berinvestasi di sistem di mana automation **berpikir, bukan
hanya mengeksekusi**. SEO Cell bukan cron bodoh yang melakukan search-replace:
dia adalah thinker LLM yang mengamati 6 sumber dan mengusulkan tindakan.

Peran Subhi ganda:
1. **Memberi makan** sistem dengan data bersih (tracking GA4 yang jujur,
   artikel yang terstruktur, UTM yang konsisten)
2. **Menerjemahkan** tindakan yang diusulkan cell menjadi distribusi manusia
   (post LinkedIn, broadcast WhatsApp, FB groups), karena cell tidak
   mendistribusikan — hanya mengamati dan menyarankan

> "AI mengusulkan, manusia memutuskan, cell mengukur." — inilah loop yang
> ingin ditutup Bali Zero. Subhi menutupnya di sisi growth.

---

## 14. Mengubah 4 funnel menjadi alat yang menarik untuk user

**Status SAAT INI dari 4 funnel** (audit codebase 30 April 2026):

| Funnel | Komponen | UX saat ini | Tingkat interaktivitas |
|---|---|---|---|
| **Visa Oracle** | `apps/mouth/src/app/visa/page.tsx` + backend `visa_oracle_service.py` | Quiz 4 pertanyaan → match 3 visa types → CTA WhatsApp | Sedang: scoring deterministik, tidak ada chat post-match |
| **KBLI Navigator** | `apps/mouth/src/app/kbli/page.tsx` + 1.563 SSG pages | Search + grid 22 sektor + Zantara chat generik | Tinggi: chat AI tapi tidak KBLI-specific |
| **Property Eligibility** | `apps/mouth/src/app/property/eligibility/` + `PropertyEligibilityBody.tsx` (384 baris) | Form koordinat → verdict GREEN/YELLOW/RED + risk matrix | Rendah: form statis → tabel → diam |
| **Tax Calendar** | `apps/mouth/src/app/(tax-calendar)/tax-calendar/page.tsx` | Calendar read-only yang bisa difilter per regency | Nol: hanya informasional, tidak ada CTA |

**Verdict codebase**: blok teknis semua sudah ada. Yang kurang adalah
**orkestrasi konversasional post-CTA**. Mereka adalah "fire-and-forget",
bukan "engagement loops".

### 14.1 Prinsip transformasi: dari "kalkulator" ke "teman"

Hari ini funnel menjawab satu pertanyaan dan diam.
Besok mereka harus **mengajukan pertanyaan balik**, menyarankan langkah
berikutnya, mengingat user, membuat user merasa di belakangnya ada tim
yang paham.

Tiga kata kerja memandu transformasi:
1. **Berbicara** — setelah hasil, user bisa bertanya "kenapa?"
2. **Menghubungkan** — hasil dari satu funnel membuka pintu masuk ke yang
   lain (visa → kbli untuk jenis bisnis)
3. **Mengingat** — sesi persisten: kalau saya kembali 3 hari kemudian,
   saya menemukan kembali quiz visa saya dengan hasil saya

### 14.2 Rencana evolusi 4 funnel (minggu 5-8, setelah money pages)

#### VISA Oracle 2.0 — "After the match, the conversation"

**Status:** Quiz → 3 visa match → tombol WhatsApp.
**Masalah:** User tidak paham *kenapa* match itu yang keluar. WhatsApp
dimulai tanpa konteks, Sahira/Ari menerima "halo" tanpa data.

**Evolusi (Subhi mengusulkan, dev mengimplementasikan):**
- Setelah match, **chat box dedicated** (bukan Zantara generik) dengan
  prompt pre-built: "Ask me why these visas, or what documents you need"
- Link WhatsApp **pre-filled** dengan: nasionalitas, durasi, tujuan, top
  match → Sahira sudah menerima 80% briefing
- "Save your match" — email opsional → lanjut dari tempat berhenti
- Tracking spesifik: `visa_match_completed`, `visa_chat_opened`,
  `visa_whatsapp_with_context`
- Internal link dari artikel visa: setiap artikel "KITAS extension"
  link ke quiz pre-filled (`/visa/match?intent=extension`)

**File kunci:** `apps/mouth/src/app/visa/match/[hash]/page.tsx` (state result
sudah ada), `backend/services/visa_oracle/` (tambah endpoint
`/visa-oracle/explain`).

#### KBLI Navigator 2.0 — "From browse to wizard"

**Status:** 1.563 kode yang bisa dicari + AI chat generik.
**Masalah:** User bahkan tidak tahu *kategori mana* yang harus dicari.
Mereka buka chat dan bertanya "I want to open a villa" — Zantara menjawab
generik.

**Evolusi:**
- **KBLI Wizard** (3-step funnel pre-search):
  1. "What do you want to do?" → 12 makro-kategori yang bisa diklik
     (hospitality, consulting, F&B, e-commerce, real estate, education, dll.)
  2. "How big?" → micro/small/medium (filter `skala_usaha`)
  3. "Foreign or local ownership?" → filter `pma_status`
- Output: 5-10 kandidat KBLI dengan penjelasan "kenapa ini cocok"
- Chat **domain-specific KBLI** dengan prompt system: "You are a KBLI
  advisor. You only answer about KBLI codes and PT PMA setup. Refuse
  off-topic."
- CTA akhir: "Talk to our company team" → WhatsApp dengan KBLI yang dipilih
  sudah ada di pesan
- Artikel "KBLI 2025 Hospitality" → tombol "Open the wizard with hospitality
  preselected"

**File kunci:** `apps/mouth/src/app/kbli/page.tsx` (tambah entry
`/kbli/wizard`), `backend/app/routers/kbli_notebook.py` (endpoint
`/kbli-notebook/wizard?category=...&size=...&pma=...`).

#### PROPERTY Eligibility 2.0 — "After the verdict, the next step"

**Status:** Form koordinat → verdict GREEN/YELLOW/RED → tabel.
**Masalah:** Verdict ditampilkan dan kemudian *diam*. User tidak tahu apa
yang harus dilakukan.

**Evolusi:**
- Setelah verdict, **3 next-step cards** dinamis berdasarkan warna:
  - GREEN → "Book a notary verification" + "Calculate full purchase cost"
  - YELLOW → "Talk to our property team about mitigation"
  - RED → "See safer zones nearby" + "Read why this is risky"
- **Comparator struktur legal**: Hak Pakai vs HGB vs Lease 30y → tabel
  samping dengan pro/kontra untuk kasus spesifik
- **PDF report yang bisa diunduh**: "Get this analysis as PDF" → email
  gate (Gated Lead Magnet ala brainstorm Gemini)
- Artikel property → tombol "Check this exact zone" → form pre-filled
  dengan koordinat yang disarankan (mis. artikel "Canggu zoning")

**File kunci:** `apps/mouth/src/components/funnel/PropertyEligibilityBody.tsx`
(384 baris, untuk diperluas), backend ❓ untuk dijelaskan (router tidak
ditemukan, harus diverifikasi dengan Asya apakah ada di `property.balizero.com`
atau perlu dibuat).

#### TAX Calendar 2.0 — "From calendar to planner"

**Status:** Calendar tahunan read-only yang bisa difilter per regency.
**Nol CTA.**
**Masalah:** Bagus tapi tidak menghasilkan apa-apa. Ini SEO content, bukan
growth tool.

**Evolusi:**
- **Tax Profile Quiz** (3 pertanyaan):
  1. "What's your structure?" (PT PMA / KITAS individual / KITAP / freelance)
  2. "Estimated monthly revenue?" (range)
  3. "Bali region?" (Badung/Denpasar/Gianyar/...)
- Output: **calendar yang dipersonalisasi** dengan HANYA deadline yang
  relevan untuk KAMU + estimasi amount + checklist dokumen
- "Add to Google Calendar" / "Get reminders by WhatsApp" → email/phone gate
- "Talk to a CoreTax expert" → WhatsApp pre-filled dengan profil tax
- Artikel tax → "Check your tax calendar" pre-filled untuk jenis pembayar
  pajak itu
- **Sensor cell**: setiap bulan, deadline kritis menghasilkan post LinkedIn
  otomatis (mis. "PPh 21 deadline tomorrow — here's the checklist")

**File kunci:** `apps/mouth/src/components/funnel/TaxCalendarBody.tsx`
(156 baris, untuk diperluas dengan quiz),
`backend/app/routers/portal_taxes.py` (pindahkan logic dari authenticated
ke versi public).

### 14.3 Prioritas realistis dalam 60 hari

Subhi TIDAK membangun keempat tool ini sendirian dalam 60 hari. Itu bunuh
diri. Dalam 60 hari pertama:

- **Minggu 1-4**: D1-D5 (tracking + 12 money pages + distribusi + WhatsApp
  CTA). Funnel tetap seperti sekarang tapi dengan tracking yang berfungsi
  dan link dari artikel.
- **Minggu 5-6**: **VISA Oracle 2.0** (paling sederhana, backend sudah
  siap, dampak tinggi pada lead — visa adalah funnel #1 Bali Zero)
- **Minggu 7-8**: pilih antara **KBLI Wizard** atau **Property Next-Step
  Cards** berdasarkan data yang dikumpulkan (kategori artikel mana yang
  konversi terbaik?)
- **Tax Calendar 2.0**: dijadwalkan untuk **hari 60-90** (post-probation),
  karena ini funnel paling tidak kritis untuk lead dan butuh design lebih
  luas

### 14.4 Pola bersama — "Funnel Conversation Layer"

Untuk menghindari 4 implementasi terpisah, Subhi mengusulkan (dengan Asya)
**komponen bersama** `<FunnelConversation>` yang setiap funnel bisa mount
setelah hasilnya:

```
<FunnelConversation
  funnel="visa"
  context={{ nationality, purpose, match }}
  prompt="Ask Zantara about your visa case"
  whatsappTemplate="visa-followup"
  trackingPrefix="visa_chat_"
  maxTurns={5}
/>
```

Keuntungan:
1. **Satu implementasi**, 4 mount-point
2. **Tracking seragam** di semua funnel
3. **WhatsApp handoff koheren** (semua context tiba ke Sahira dalam format
   yang sama)
4. **Reusable** juga di dalam artikel ("ask about this article")

**File yang dibuat:**
`apps/mouth/src/components/funnel/FunnelConversation.tsx`
(dengan hook `useFunnelChat`, `useFunnelHandoff`).

### 14.5 KPI spesifik untuk tool 2.0

Dalam tiga target hari 60 (§5), 4 funnel yang berevolusi harus berkontribusi:
- ≥40% dari lead website teratribusi berasal dari salah satu dari 4 funnel
  (vs 0% saat ini)
- Tingkat "match completed" pada Visa Oracle ≥30% (user yang menyelesaikan
  quiz)
- Tingkat "wizard completed" pada KBLI ≥20% (kalau wizard di-unlock)
- Tingkat "PDF report requested" pada Property ≥10%
- Minimal 1 funnel dengan feedback loop aktif menuju seo_cell sensors

### 14.6 Batasan yang harus dihormati (penting)

1. **Pricing copy HANYA dari `PricingTool`** — jangan pernah mengarang
   angka (batasan §4 zona merah #1)
2. **Backend changes dengan Asya** — Subhi tidak menulis endpoint sendirian.
   Frontend ya, backend pair.
3. **Tidak ada subdomain baru** sebelum perbaiki 4 yang ada (zona merah #5)
4. **A/B test sebelum rollout penuh** — setiap perubahan funnel melalui
   eksperimen yang terukur (canary 20% traffic)
5. **Mobile-first** — 70% traffic Bali Zero adalah mobile. Setiap tool
   2.0 harus berfungsi dengan jempol di iPhone SE sebelum di laptop

---

## 15. Verdict akhir dari brainstorm multi-LLM

**Keempat LLM (DeepSeek + Gemini + Codex + NotebookLM) konvergen pada satu
poin:**

> Subhi bukan "satu lagi yang melakukan SEO". Dia adalah **pemilik
> sungguhan pertama dari kanal organik** di Bali Zero. Kalau di hari 60
> website naik dari 0,7 lead/bulan ke 20+ lead/bulan **tanpa membakar
> satu rupiah pun di Ads**, dia sudah menemukan tempatnya. Kalau dia
> tetap pada audit, grafik, dan artikel yang tidak didistribusikan, dia
> belum menyelesaikan masalah yang membenarkan peran ini.

---

## 16. Pesan WhatsApp selamat datang (Kamis 30 April jam 07:00)

```
Selamat pagi Subhi 🌅

Hari ini kita mulai. Saya senang Anda bergabung.

Tiga hal sebelum berangkat:

1. Datang santai jam 09:30. Tidak perlu buru-buru.
2. Bawa laptop. Hari pertama untuk setup, baca, mengerti — tidak ada
   coding hari ini.
3. Jangan khawatir tentang "membuktikan diri" hari ini. Hari pertama
   untuk merasa tempat ini, bukan menunjukkan apapun. Saya sudah tahu
   Anda mampu — itu sebabnya kita di sini.

Wilayah kerja Anda: organic growth surface dari klik pertama Google
sampai lead WhatsApp pertama. Akan saya jelaskan semuanya hari ini.

Sampai jumpa.

Antonello
```

---

## 17. Lampiran — file sumber brainstorm

4 brainstorm asli disimpan di:
- `/tmp/brainstorm_deepseek.md` (14KB) — DeepSeek Reasoner V4
- `/tmp/brainstorm_gemini.md` (5KB) — Gemini 3 Pro
- `/tmp/brainstorm_codex.md` (18KB) — Codex GPT high-reasoning
- `/tmp/brainstorm_nlm.md` (6KB) — NotebookLM bahasa Indonesia

NotebookLM ID notebook: `764cef0c-cb89-4a6f-a007-aa0ba10868a0`

**Konvergensi 4 LLM:**
- 4/4 setuju: D1 = fix tracking GA4 di FunnelFeature.tsx
- 4/4 setuju: wilayah = `apps/mouth/` frontend + website publik
- 4/4 setuju: KPI primer = lead website /bulan tanpa Ads
- 4/4 setuju: masalah strategis adalah "Content-to-Conversion Gap"
- 3/4 (DeepSeek + Gemini + NLM): menyebut perbaikan bridge WhatsApp Zantara
- 2/4 (DeepSeek + Codex): menyebut backlog CRM (138 pratiche stuck) sebagai
  peluang
- 1/4 (Gemini): menambahkan "Zantara sebagai Gated Lead Magnet" — peluang unik

**Disonansi yang berguna:**
- DeepSeek ingin segera melibatkan Subhi di fix backend
  (`/api/analytics/dashboard` 500) — Codex dan Gemini bilang biarkan ke Damar
- DeepSeek mengusulkan `my.balizero.com` (portal klien) sebagai wilayah —
  Codex dan Gemini bilang frontend publik (`apps/mouth/`)
- **Resolusi**: dokumen di atas mengambil posisi Codex (lebih konservatif,
  lebih jelas, lebih growth-focused) dan menggunakan peluang CRM
  (DeepSeek+Codex) sebagai bonus.

---

**Dokumen dibuat tanggal 30 April 2026 jam 03:30 WITA oleh Antonello + Claude.**
**Sintesis multi-LLM: DeepSeek V4 + Gemini 3 Pro + Codex GPT + NotebookLM bahasa.**
