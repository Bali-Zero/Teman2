# Runbook: Scraping Kompetitor Instagram Manual

**Untuk:** Vino (tim Bali Zero)
**Tujuan:** mengumpulkan 270 baris data (18 akun × 15 post) dalam Google Sheet
**Waktu total:** 25 jam, dibagi 5 hari kerja (5 jam per hari)
**Deadline:** akhir Hari ke-6 riset SOTA (Jumat, kalau mulai Senin)
**Google Sheet:** [link akan diberikan oleh Zero sebelum mulai]

---

## 1. Apa yang kita lakukan dan kenapa

Bali Zero sedang melakukan riset mendalam tentang media sosial untuk:
- memahami **apa yang bekerja** di akun kompetitor langsung (agensi visa/PMA)
- memahami **bagaimana engagement dibangun** oleh influencer expat di Bali
- membandingkan hasil itu dengan 25 post terakhir @balizero0 kita sendiri

Datamu akan jadi input dari **Consiglio v1** (sistem 4 AI yang berdiskusi untuk menghasilkan playbook editorial Bali Zero). Tanpa data yang kamu kumpulkan, playbook akan "mengarang" — dengan datamu, playbook jadi berbasis fakta nyata.

**Jadi: kualitas datamu = kualitas keputusan strategis untuk 90 hari ke depan.**

---

## 2. 18 akun yang harus di-scrape

### Kelompok 1 — Agensi kompetitor langsung (10 akun)
Mereka jual produk/jasa yang mirip dengan Bali Zero.

1. `@lawbali`
2. `@emerhub`
3. `@incorp_indonesia`
4. `@cekindo_official`
5. `@permitindo`
6. `@balisolutions`
7. `@bli_bali`
8. `@kiradigital`
9. `@indolegal`
10. `@bambuhijau_konsultan`

### Kelompok 2 — Influencer expat Bali (8 akun)
Mereka TIDAK jual jasa hukum/imigrasi, tapi audience mereka sama dengan kita.

11. `@solopreneur_bali`
12. `@digitalnomadworld`
13. `@nomadgate`
14. `@nomadsembassy`
15. `@balibuddha`
16. `@reneesylvestre`
17. `@thebalibible`
18. `@indoexpatcommunity`

**Catatan:** kalau salah satu akun sudah private atau tidak ditemukan, catat itu di kolom `catatan` dan lewati ke akun berikutnya. Jangan tunggu approval, jangan hubungi dulu — langsung skip.

---

## 3. Untuk setiap akun: 15 post terbaru

Urutan: dari post paling baru (paling atas di profil) ke bawah, sampai kamu mencapai **15 post**. Kalau akun punya kurang dari 15 post, ambil semua yang ada dan tulis `jumlah_kurang` di kolom catatan.

**Jangan** ambil Stories. **Jangan** ambil Highlights. **Hanya feed post dan Reel** yang muncul di grid utama.

---

## 4. Data yang harus dikumpulkan per post

Untuk setiap post, isi satu baris di Google Sheet dengan kolom berikut:

| Kolom | Tipe | Contoh | Keterangan |
|-------|------|--------|------------|
| `account_handle` | teks | `lawbali` | Tanpa tanda `@` |
| `post_url` | teks | `https://www.instagram.com/p/DXY-VQjlP9N/` | Klik "Copy link" di post |
| `posted_date` | `YYYY-MM-DD` | `2026-04-18` | Tanggal yang muncul di bawah post |
| `format` | enum | `carousel` | Salah satu: `carousel` / `reel` / `static` / `video` |
| `slide_count` | angka | `7` | Hanya kalau `format=carousel` (lihat titik-titik di bagian bawah gambar). Kosongkan untuk format lain |
| `caption_full` | teks | *(full caption)* | **Copy-paste utuh**, jangan diringkas. Termasuk emoji. Kalau ada karakter khusus, biarkan |
| `hashtags` | teks | `#kitas #visa #bali` | Daftar hashtag dipisah spasi, dengan tanda `#` |
| `hook_text` | teks | `Did you know KITAS 2 expires in 2026?` | 2 baris pertama caption (~120 karakter) |
| `likes_count` | angka | `245` | Angka "likes" yang kelihatan |
| `comments_count` | angka | `12` | Angka komentar yang kelihatan |
| `video_views_count` | angka | `3400` | Hanya kalau `format=reel` atau `video` |
| `posted_time_wita` | `HH:MM` | `19:30` | Jam post, dikonversi ke WITA (UTC+8). Lihat §6 untuk cara konversi |
| `catatan` | teks | `akun private` atau `slide_count tidak terlihat` | Opsional, hanya kalau ada masalah |

### Contoh satu baris diisi lengkap:
```
lawbali | https://www.instagram.com/p/ABC123/ | 2026-04-15 | carousel | 7 | "3 mitos PT PMA yang..." | #ptpma #bali #business | 3 mitos PT PMA yang kebanyakan | 245 | 12 |  | 09:00 |
```

---

## 5. Langkah-langkah harian (5 jam per hari)

### Setup satu kali (15 menit, hari pertama saja)
1. Login Instagram dari akun pribadi kamu (**bukan** dari akun @balizero0, supaya algoritma IG tidak "bingung")
2. Buka browser Chrome, mode Incognito direkomendasikan
3. Buka Google Sheet di tab lain, pin tab itu
4. Siapkan minuman/snack — 5 jam butuh konsentrasi :)

### Untuk setiap akun (~80 menit per akun, 3-4 akun per hari)
1. Buka `instagram.com/<handle>/`
2. Scroll sampai post ke-15 muncul (hitung visual: 3 kolom × 5 baris = 15 post)
3. Untuk setiap post dari yang paling baru:
   - Klik post untuk buka full view
   - Copy data ke Sheet (biasanya 5 menit per post)
   - Kembali ke feed, klik post berikutnya
4. Setelah 15 post: centang akun itu di progress tracker (§8)

### Quality check setiap 5 post
Sebelum lanjut ke post ke-6, cek:
- [ ] `caption_full` > 20 karakter (bukan cuma emoji)
- [ ] `likes_count` tidak kosong
- [ ] `hashtags` ada (kalau memang ada di caption)
- [ ] `posted_time_wita` dihitung, bukan dikosongkan

---

## 6. Cara konversi jam ke WITA

Instagram menampilkan jam dalam zona lokal device kamu (kalau kamu di Bali, itu sudah WITA — tinggal copy). Tapi kalau IG menunjukkan "3 jam yang lalu" atau hanya tanggal, lakukan:

1. Klik "..." di kanan atas post
2. Pilih "View post" / "Show timestamp" (di aplikasi)
3. Atau: hover timestamp di browser → akan muncul ISO timestamp (UTC)
4. Kalau hanya UTC: tambah 8 jam untuk jadi WITA

**Contoh:** post pada "10:23 UTC" → WITA = 18:23.

Kalau tidak yakin, tulis perkiraan terbaik + `catatan: jam perkiraan`.

---

## 7. Daily check-in Telegram

Setiap hari, jam **18:00 WITA**, kirim pesan ke Zero + Claude di grup Telegram:

```
SOTA Day N: scraped X/270 baris.
Status: sesuai jadwal / lambat / cepat
Akun selesai hari ini: @akun1, @akun2, @akun3
Blocker: [tulis kalau ada, kosongkan kalau tidak ada]
Besok rencana: @akun4, @akun5
```

Contoh pesan hari pertama:
```
SOTA Day 1: scraped 42/270 baris.
Status: sesuai jadwal
Akun selesai hari ini: @lawbali, @emerhub, @incorp_indonesia (15 post each = 45, tapi 3 post di emerhub private → 42)
Blocker: tidak ada
Besok rencana: @cekindo_official, @permitindo, @balisolutions
```

---

## 8. Progress tracker di dalam Google Sheet

Sheet pertama bernama **"Progress"** — punya 18 baris, satu per akun, dengan kolom:

| account_handle | status | rows_done | started_at | finished_at | notes |
|----------------|--------|-----------|------------|-------------|-------|
| lawbali | todo / in_progress / done | 0-15 | timestamp | timestamp | opsional |

Update status begitu mulai dan begitu selesai satu akun.

---

## 9. Kalau ada masalah

### Instagram membatasi scroll atau minta CAPTCHA
- Istirahat 15-30 menit
- Ganti ke mobile kalau desktop ter-throttle
- Kalau sering terjadi: kasih tahu Zero, mungkin perlu VPN Indonesia

### Akun sudah private / suspended / rebrand
- Tulis di kolom `catatan`: `akun private` atau `akun tidak ditemukan 2026-04-XX`
- Skip, lanjut akun berikutnya
- Kamu tidak perlu cari pengganti — 17 akun sudah cukup

### Post terlihat sponsored atau viral outlier (likes > 10x rata-rata)
- Tetap record, tambah kolom catatan: `viral outlier — likes >> avg`
- Ini penting! Kita mau tahu distribusi, bukan cuma "normal" post

### Video tanpa `video_views_count`
- Kadang IG sembunyikan views
- Kosongkan kolom, tulis `catatan: views tidak terlihat`

### Carousel tanpa slide count jelas
- Hitung titik-titik di bawah gambar
- Kalau tidak ada titik: itu static post, bukan carousel. Ubah `format=static`

### Caption terlalu panjang untuk Sheet
- Google Sheet handle sampai 50,000 karakter per cell — tidak akan masalah
- Copy-paste lengkap

### Post dalam bahasa Indonesia vs Inggris
- Catat caption dalam bahasa asli (jangan translate)
- Kolom `catatan: bahasa=id` atau `bahasa=en`

---

## 10. Kalau tidak selesai Hari ke-5

Kalau Jumat sore belum sampai 270 baris:
- Kirim pesan ke Zero saat itu juga (**jangan tunggu Sabtu**)
- Minimal target untuk passing Gate 3: **243 baris** (= 270 - 10% toleransi)
- Kalau antara 200-243: OK, mungkin diterima
- Kalau < 200: Claude akan aktifkan fallback (Playwright automation) untuk akun yang missing

---

## 11. Tips untuk lebih cepat (bukan wajib)

- **Keyboard shortcut**: setelah klik post, pakai `Esc` untuk tutup modal, `→` untuk post berikutnya di grid
- **Firefox Multi-Account Containers** atau Chrome profile baru = sesi terpisah, tidak ter-throttle
- **Copy-paste lebih cepat dari mengetik** — always copy caption dan hashtags
- **Template spreadsheet**: bikin row template lengkap sekali, lalu duplicate + ubah nilai
- **Istirahat 10 menit setiap 25 menit** (Pomodoro) — mata cepat capek di IG

---

## 12. Setelah selesai

1. Dari Google Sheet: **File → Download → Comma-separated values (.csv)**
2. Nama file: `competitor_raw.csv`
3. Kirim ke Zero via Telegram (atau Drive share)
4. Zero akan simpan ke `research/sota-social-2026-v1/competitor_raw.csv`
5. Claude akan jalankan `scripts/sota_ingest_competitors.py` yang mengubah CSV jadi JSON terstruktur
6. Kamu akan dapat konfirmasi Telegram: **"SOTA competitor scrape selesai — Gate 3 OK"**

---

## 13. Catatan penting

- **Data yang kamu kumpulkan bersifat RAHASIA**. Jangan share sheet dengan siapa pun di luar Zero + Claude + kamu
- **Jangan scrape dengan bot/script** — itu melanggar ToS Instagram. Manual saja
- **Jangan login ke akun yang sedang di-scrape** — kamu hanya sebagai penonton public
- Jam kerja fleksibel — yang penting tercapai 270 baris sebelum akhir Hari ke-6

---

## 14. Kontak cepat

- **Pertanyaan teknis** (Sheet, Instagram, format): Telegram Zero
- **Pertanyaan strategis** ("kenapa akun ini? kenapa 15 post?"): baca spec di `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`
- **Panggilan darurat** (IG ban akun, Sheet hilang, dll): Telegram Zero langsung

---

**Semoga lancar, Vino. Kerjamu adalah fondasi dari semua keputusan editorial Bali Zero 90 hari ke depan.**

Claude + Zero
