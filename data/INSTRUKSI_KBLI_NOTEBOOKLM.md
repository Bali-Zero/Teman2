# INSTRUKSI: Pembuatan Presentasi KBLI dengan NotebookLM

**Target:** 36 presentasi per orang (18 KBLI × 2 presentasi)

---

## LANGKAH-LANGKAH

### PERSIAPAN

1. **Buka file assignment Anda:**
   - File: `kbli_team_assignments_full.md`
   - Cari nama Anda dan lihat daftar 18 KBLI yang ditugaskan

2. **Login ke NotebookLM:**
   - Buka: https://notebooklm.google.com/
   - Login dengan email Gmail Anda (@gmail.com)

---

### PROSES UNTUK SETIAP KBLI

#### TAHAP 1: Presentasi Teknis

1. **Copy JSON KBLI dari file assignment**
   - Pilih satu KBLI dari daftar Anda
   - Copy seluruh blok JSON (dari `{` sampai `}`)

   Contoh:
   ```json
   {
     "id": "...",
     "payload": {
       "text": "...",
       "metadata": {...}
     }
   }
   ```

2. **Buat Notebook baru di NotebookLM**
   - Klik "New Notebook"
   - Paste JSON KBLI sebagai sumber pertama

3. **Generate Presentasi Teknis**
   - Minta NotebookLM membuat presentasi
   - Prompt yang bisa digunakan:

   > "Buatkan presentasi singkat dan teknis tentang KBLI ini. Jelaskan:
   > 1. Apa jenis usaha ini
   > 2. Tingkat risiko dan persyaratan
   > 3. Apakah PMA diizinkan
   > 4. Skala usaha yang tersedia
   > 5. Kewajiban utama"

4. **Simpan Presentasi 1**
   - Nama file: `[KODE] - [JUDUL] - Teknis`
   - Contoh: `10110 - Rumah Potong & Pengepakan Daging - Teknis`

---

#### TAHAP 2: Riset Deep Think (Paralel)

**Sambil menunggu Presentasi 1 selesai:**

1. **Gunakan fitur "Deep Research" di NotebookLM**
   - Cari dokumen pemerintah tambahan tentang KBLI tersebut
   - Fokus pada:
     - Peraturan terkait (PP, Permen, dll)
     - Panduan dari Kementerian terkait
     - Studi kasus atau contoh nyata
     - Informasi perizinan OSS

2. **Kata kunci pencarian:**
   - `"[Kode KBLI] peraturan"`
   - `"[Nama usaha] izin OSS"`
   - `"[Nama usaha] persyaratan 2024 2025"`
   - `"[Kementerian terkait] [nama usaha]"`

3. **Import dokumen yang ditemukan**
   - Tambahkan ke Notebook yang sama
   - Pastikan sumber dari website resmi pemerintah (.go.id)

---

#### TAHAP 3: Presentasi Bisnis

1. **Generate Presentasi kedua (lebih kontekstual)**
   - Setelah dokumen tambahan di-import
   - Prompt yang bisa digunakan:

   > "Buatkan presentasi untuk calon pengusaha yang ingin membuka usaha ini. Jelaskan dengan bahasa yang mudah dipahami:
   > 1. Peluang bisnis dan potensi pasar
   > 2. Modal dan investasi yang dibutuhkan
   > 3. Langkah-langkah praktis untuk memulai
   > 4. Tips dan hal yang perlu diperhatikan
   > 5. Estimasi waktu pengurusan izin"

2. **Simpan Presentasi 2**
   - Nama file: `[KODE] - [JUDUL] - Bisnis`
   - Contoh: `10110 - Rumah Potong & Pengepakan Daging - Bisnis`

---

### FORMAT PENAMAAN FILE

```
[KODE KBLI] - [JUDUL KBLI] - [JENIS]
```

**Contoh lengkap untuk satu KBLI:**
- `10110 - Rumah Potong & Pengepakan Daging - Teknis`
- `10110 - Rumah Potong & Pengepakan Daging - Bisnis`

---

### UPLOAD KE GOOGLE DRIVE

1. **Folder bersama:**
   https://drive.google.com/drive/folders/14qVqcJ0N--K35KEsSeGuPNi183KYpO-l

2. **Buat subfolder dengan nama Anda**
   - Contoh: `Anton - Hospitality`
   - Contoh: `Vino - F&B Makanan`

3. **Upload semua presentasi ke subfolder Anda**

---

## CHECKLIST PER ORANG

| No | KBLI | Presentasi Teknis | Presentasi Bisnis | Upload |
|----|------|-------------------|-------------------|--------|
| 1  |      | [ ]               | [ ]               | [ ]    |
| 2  |      | [ ]               | [ ]               | [ ]    |
| 3  |      | [ ]               | [ ]               | [ ]    |
| 4  |      | [ ]               | [ ]               | [ ]    |
| 5  |      | [ ]               | [ ]               | [ ]    |
| 6  |      | [ ]               | [ ]               | [ ]    |
| 7  |      | [ ]               | [ ]               | [ ]    |
| 8  |      | [ ]               | [ ]               | [ ]    |
| 9  |      | [ ]               | [ ]               | [ ]    |
| 10 |      | [ ]               | [ ]               | [ ]    |
| 11 |      | [ ]               | [ ]               | [ ]    |
| 12 |      | [ ]               | [ ]               | [ ]    |
| 13 |      | [ ]               | [ ]               | [ ]    |
| 14 |      | [ ]               | [ ]               | [ ]    |
| 15 |      | [ ]               | [ ]               | [ ]    |
| 16 |      | [ ]               | [ ]               | [ ]    |
| 17 |      | [ ]               | [ ]               | [ ]    |
| 18 |      | [ ]               | [ ]               | [ ]    |

**Total: 36 presentasi**

---

## TIPS

1. **Kerjakan secara paralel** - Sambil menunggu satu presentasi generate, mulai riset untuk KBLI berikutnya

2. **Prioritaskan KBLI nomor 1-5** - Ini adalah KBLI paling penting dalam kategori Anda

3. **Jangan copy-paste mentah** - Review hasil NotebookLM dan pastikan informasi akurat

4. **Gunakan bahasa Indonesia** - Semua presentasi dalam Bahasa Indonesia

5. **Deadline** - Koordinasi dengan tim untuk target penyelesaian

---

## KONTAK

Jika ada pertanyaan atau kendala teknis:
- Hubungi supervisor Anda
- Atau tanyakan di grup WhatsApp tim

---

*Dokumen ini dibuat: 2025-12-23*
*File assignment: kbli_team_assignments_full.md*
