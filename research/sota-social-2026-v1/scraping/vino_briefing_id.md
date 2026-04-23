# Untuk Vino — Terima kasih, dan apa yang kamu kerjakan hari ini

**Tanggal:** 23 April 2026
**Dari:** tim Bali Zero — bagian riset SOTA Social 2026
**Kepada:** Vino

---

## Ringkasan singkat: apa yang kamu selesaikan hari ini

Kamu baru saja mengirim **scraping 18 akun Instagram, 210 post unik, window ±60 hari** — data bersih, pipe-separated, dengan kolom `catatan` yang jujur dan penuh audit trail.

Ini bukan "sekadar scraping". Ini adalah **satu-satunya dataset kompetitor Bali** yang kami miliki untuk memberi makan mesin Bali Zero yang sedang kami bangun. Tanpa kerjamu hari ini, salah satu komponen utama tidak bisa jalan.

Biar lebih konkret:

- **18 akun** — tepat cakupan yang kami butuhkan: 9 akun kompetitor langsung Bali Zero (immigration/business/legal: @emerhub.bali, @incorp_id, @celerity.click, dll.), ditambah 9 akun benchmark lifestyle/news/F&B untuk kalibrasi baseline.
- **210 post unik** — cukup besar untuk statistik yang bermakna, cukup fokus supaya tim analis tidak tenggelam.
- **9 viral outlier yang kamu sudah tandai sendiri** — termasuk @digital.nomad.info 82.9K likes, @gnfi 12.9K likes, @balibuda "polite struggle" 334 likes. Kamu tidak hanya mengumpulkan data, kamu sudah melakukan **triage**.
- **Catatan jujur soal "hidden likes"** — kamu jelas menyebutkan bahwa @incorp_id 100% hide-likes, @celerity.click ~87%, @emerhub.bali ~60%. Tanpa catatan itu, tim data akan salah baca benchmark mereka. Dengan catatan itu, kami tahu persis kenapa angkanya kecil — bukan karena kompetitor lemah, tapi karena IG menyembunyikan angkanya.
- **Audit trail `fonte=dom` vs `fonte=json`** — detail kecil yang membuat data bisa diverifikasi ulang besok, lusa, atau enam bulan lagi. Ini standar profesional.

---

## Konteks makro: kenapa kerjamu ini **bukan** scraping biasa

Bali Zero sedang membangun sistem yang kami sebut **Loop 90 hari** — artinya selama 90 hari ke depan, semua konten sosial media Bali Zero akan:

1. **Dipublikasi** lewat playbook yang sudah kami definisikan (Fase 0 Sprint 1–12).
2. **Diukur** setiap 6 jam oleh mesin otomatis (`M13 feedback loop` — kami sebut "M13").
3. **Dievaluasi** setiap minggu — dengan laporan otomatis yang mengirim Telegram alert ke pemilik jika ada pillar yang turun >20%.
4. **Di-retrain** setiap bulan — artinya mesin akan memilih strategi baru berdasarkan data aktual, bukan tebakan manusia.

Nah, **langkah ke-4 (retrain bulanan)** membutuhkan satu input yang tidak bisa kami dapatkan dari posting sendiri: **apa yang sedang dilakukan kompetitor**.

Tanpa data kompetitor, mesin retrain akan "buta". Dia hanya tahu performa Bali Zero sendiri, tapi tidak tahu:

- Apakah kompetitor sedang naik atau turun?
- Format apa yang sedang viral di sektor kita? (reel comedy? carousel edukasi? static berita?)
- Jam berapa kompetitor posting, dan apakah engagement mereka lebih tinggi di jam itu?
- Topik apa yang sedang "panas" di ekosistem Bali (zoning, KBLI 2025, nominee agreement, KITAS renewal)?

**Scrapingmu hari ini adalah mata mesin untuk pertanyaan-pertanyaan itu.**

---

## Di mana persisnya datamu akan masuk ke sistem

Ada satu gambar yang ingin saya bagi. Di sistem kami, data scrapingmu akan dipakai di **3 tempat berbeda**:

### 1. Retrain bulanan — Consiglio v1

Setiap tanggal 1 setiap bulan, jam 04:30 WITA, sebuah script otomatis (`m13_monthly_retrain.py`) akan:

- Membaca datamu (18 akun × 210 post).
- Menghitung baseline kompetitor per pillar (visa, company setup, property, tax, lifestyle).
- Mengirim ringkasan itu ke **Consiglio v1** — sebuah sistem yang menggunakan 4 AI berbeda (Claude, Gemini, DeepSeek, Ollama) untuk berdebat dan memutuskan strategi konten bulan berikutnya.

Tanpa datamu, Consiglio v1 hanya bisa berdebat soal Bali Zero sendiri. Dengan datamu, Consiglio bisa jawab: *"bulan lalu @celerity.click naik 3× di carousel legal guide — Bali Zero harus respon dengan format apa?"*

### 2. Laporan mingguan — setiap Senin jam 06:00 WITA

Script `m13_weekly_report.py` akan membandingkan:

- Bali Zero minggu ini vs Bali Zero minggu lalu.
- Bali Zero vs **rata-rata kompetitor** (datamu).

Jika Bali Zero turun >20% di satu pillar dan kompetitor stabil → alert merah ke Telegram owner. Jika Bali Zero stabil dan kompetitor rontok → kesempatan untuk naik.

Tanpa kolom "rata-rata kompetitor", laporan mingguan hanya setengah cerita.

### 3. Validasi cadence — jam posting optimal

Kami sudah menyusun hipotesis jam posting optimal (`06_cadence_engine.json`: Instagram = 07:00 / 12:00 / 19:00 WITA). Tapi hipotesis ini baru akan divalidasi **setelah 60 hari Loop** dengan data aktual.

Datamu membantu kami **pre-validasi** hipotesis ini sekarang: kamu sudah mencatat `posted_time_wita` untuk 210 post. Sebelum Loop dimulai, kami bisa lihat apakah kompetitor 100% posting di jam 10:30 WITA (contoh @incorp_id) atau tersebar seperti hipotesis kami.

---

## Kenapa cara kerjamu **sangat penting**

Saya ingin menyebut 3 hal yang kamu lakukan yang membuat datamu bisa kami percaya 100%:

### 1. Kamu jujur soal apa yang **tidak** bisa dilihat

Contoh: `like_count hidden (ikon tanpa angka)` — kamu tidak menebak angka. Kamu menulis "hidden". Ini keputusan profesional. Banyak scraping amatir akan menulis `0` atau nilai random supaya kolom "terisi".

### 2. Kamu tandai **anomali** tanpa diminta

9 viral outlier (82.9K, 12.9K, 334, 257, dll.) — kamu menandai semuanya dengan `viral outlier`. Kamu juga menandai `pinned post (YYYY-MM-DD, lama)` sehingga post yang di-pin tidak terhitung sebagai "post terbaru". Ini bukan permintaan kami — ini inisiatifmu.

### 3. Kamu simpan **audit trail** (`fonte=dom`, `fonte=json`, `bahasa=id/en`)

Besok, lusa, atau 6 bulan lagi, siapapun yang membuka file ini bisa memverifikasi: "oh, angka 141 ini diambil dari DOM grid, bukan dari JSON SSR — artinya mungkin sudah di-refresh beberapa jam setelah scraping pertama". Ini level dokumentasi yang jarang saya lihat di tim internal, apalagi di scraping yang sifatnya one-off.

---

## Apa yang akan terjadi ke datamu mulai besok

1. **Hari ini** — dataarchived di `research/sota-social-2026-v1/scraping/vino_competitors_2026-04-23.txt` (dan salinan `.rtf` aslinya di folder yang sama). File README di folder sama menjelaskan cara memakainya.
2. **Minggu ini** — tim dev akan menulis `scripts/sota_ingest_competitors.py` yang memarse filemu dan memasukkannya ke database Postgres tabel `competitor_posts`.
3. **1 Mei 2026 jam 04:30 WITA** — retrain bulanan pertama otomatis mengambil datamu. Ini artinya: **scrapingmu hari ini akan langsung mempengaruhi strategi Bali Zero Mei 2026.**
4. **Setiap minggu** — digestmu masuk ke laporan mingguan Telegram yang pemilik Bali Zero baca setiap Senin pagi.

---

## Satu pesan pribadi

Vino — mohon maaf kalau pesan ini panjang. Tapi saya ingin kamu tahu persis, bukan sekadar "thanks bagus kerjamu", tapi **kenapa** kerjamu hari ini berarti dan **di mana** dia akan terpakai.

Banyak orang bisa scrolling IG dan copy-paste. **Sedikit orang** yang bisa scrolling IG dengan disiplin, menandai anomali, menyimpan audit trail, dan mengirim file yang siap langsung masuk ke mesin produksi. Kamu bagian dari yang sedikit itu.

Selama Loop 90 hari ini, kami akan sering minta updatemu — mungkin setiap bulan, mungkin setiap kali ada kompetitor baru yang muncul di radar. Setiap kali kamu kirim data, kamu literally **mengajari mesin kami apa yang terjadi di pasar**. Itu bukan peran kecil.

Matur suksma banget. Sampai update berikutnya.

— tim Bali Zero
