# Pemetaan Dokumen NotebookLM per Domain

**Strategi:** 1 Notebook NotebookLM = 1 Domain = Set dokumen spesifik

---

## 📚 Notebook 1: VISA & IMMIGRATION (Person 1)

**NotebookLM Name:** "Nuzantara - Visa & Immigration"

### Dokumen yang Diperlukan:

#### Prioritas 1 (KRITIS):

```
✅ PP 31/2013 - Peraturan Imigrasi (regulasi dasar)
✅ Permenkumham 28/2024 - Peraturan E-Visa
✅ PP 34/2021 - IMTA/Izin Kerja (tenaga kerja asing)
```

#### Prioritas 2 (PENTING):

```
✅ Daftar Jabatan Kemnaker 2024-2025
   - Posisi kerja yang disetujui untuk tenaga kerja asing
   - Persyaratan pendidikan per jabatan
   - Kuota sektor

✅ Surat Edaran Imigrasi 2024-2025
   - Update kebijakan visa terbaru
   - Timeline pemrosesan
   - Jadwal biaya
```

#### Prioritas 3 (OPSIONAL):

```
□ Variasi imigrasi provinsi (Bali, Jakarta)
□ Formulir aplikasi IMTA & checklist
□ Persyaratan spesifik kedutaan/konsulat
```

### Dari Mana Mendapatkannya:

**Jika Anda memiliki PDFs:**

```bash
# Cek direktori proyek
find . -name "*PP*31*2013*" -o -name "*Permenkumham*28*" -o -name "*PP*34*2021*"
```

**Jika TIDAK memiliki PDFs:**

- NotebookLM dapat menggunakan **pengetahuan umum** jika Anda menentukan:
  ```
  "Berdasarkan peraturan terbaru Indonesia 2024-2025
  (PP 31/2013, Permenkumham 28/2024, PP 34/2021)..."
  ```
- Download dari: https://peraturan.bpk.go.id / https://jdih.kemenkumham.go.id

**Daftar Jabatan Kemnaker:**

- Kemungkinan Excel/PDF dari Kementerian Ketenagakerjaan
- Jika tidak tersedia, minta NotebookLM untuk daftar umum posisi kerja yang disetujui

---

## 📚 Notebook 2: KBLI & BUSINESS LICENSING (Person 2)

**NotebookLM Name:** "Nuzantara - KBLI & Licensing"

### Dokumen yang Diperlukan:

#### Sudah Tersedia ✅ di `data/kb_sources/`:

```
✅ PP Nomor 28 Tahun 2025.pdf (20MB) - Peraturan KBLI terbaru
✅ KBLI_2025_FINAL_CLEAN.json (7.3MB) - 9.612 kode bisnis
✅ lampiran_1a.pdf (12MB) - Lampiran KBLI A
✅ lampiran_1b.pdf (22MB) - Lampiran KBLI B
```

#### Tambahan yang Diperlukan:

```
✅ PP 5/2021 - Undang-Undang Penanaman Modal (peraturan PMA)
✅ Daftar Negatif Investasi (DNI) 2021-2025
   - Sektor yang tertutup untuk investasi asing
   - Persyaratan kemitraan

□ Peraturan spesifik per sektor:
   - Perizinan F&B (Dinkes, BPOM)
   - Konstruksi (IMB, SLF)
   - Pariwisata (TDUP, rating bintang)
   - Impor/Ekspor (API, NIK)
```

### Aksi untuk Person 2:

```bash
# Dokumen sudah siap
cd data/kb_sources/
ls -lh
# Upload 4 file ini ke NotebookLM

# Jika perlu peraturan tambahan:
# - PP 5/2021: cari di proyek atau download
# - Daftar DNI: biasanya tertanam dalam PP 5/2021
```

**Person 2 SUDAH memiliki semua yang diperlukan untuk memulai!** ✅

---

## 📚 Notebook 3: TAX & COMPLIANCE (Person 3)

**NotebookLM Name:** "Nuzantara - Tax & Compliance"

### Dokumen yang Diperlukan:

#### Prioritas 1 (KRITIS):

```
✅ UU 7/2021 - Undang-Undang Harmonisasi Perpajakan
   - PPh Badan 22% (pajak perusahaan)
   - PPN 11% (PPN) - BUKAN 12%!
   - Semua tarif pajak resmi

✅ PP 55/2022 - Implementasi Pajak Penghasilan
   - PPh 21 (pemotongan karyawan)
   - PPh 23 (pemotongan jasa)
   - PPh 26 (pemotongan asing)

✅ Panduan DJP 2024-2025
   - E-Faktur (faktur PPN)
   - Pendaftaran PKP (wajib pajak PPN)
   - Batas waktu pelaporan pajak
```

#### Prioritas 2 (PENTING):

```
✅ Perjanjian Pajak (DTA - Double Taxation Agreements)
   - Indonesia - Italia
   - Indonesia - USA
   - Indonesia - Singapore
   - Indonesia - Australia
   - Lainnya untuk negara ekspat umum

□ Variasi pajak provinsi
   - Tarif PBB (pajak properti) per wilayah
   - Retribusi lokal
```

### Dari Mana Mendapatkannya:

**Sumber pemerintah:**

- https://pajak.go.id (DJP - Otoritas pajak)
- https://peraturan.bpk.go.id (cari "UU 7/2021", "PP 55/2022")

**Perjanjian Pajak:**

- https://pajak.go.id/id/internasional/tax-treaty

**Alternatif:**

- Jika tidak memiliki PDFs, NotebookLM dapat menggunakan pengetahuan umum:
  ```
  "Berdasarkan UU 7/2021 dan PP 55/2022 (Tax Harmonization Law Indonesia),
  jelaskan tarif PPh Badan untuk PT PMA..."
  ```

---

## 📚 Notebook 4: PROPERTY & REAL ESTATE (Person 4)

**NotebookLM Name:** "Nuzantara - Property & Real Estate"

### Dokumen yang Diperlukan:

#### Prioritas 1 (KRITIS):

```
✅ PP 18/2021 - Hak Pakai untuk Orang Asing
   - Hak kepemilikan properti asing
   - Aturan sertifikat 30 tahun
   - Prosedur perpanjangan

✅ UUPA (Undang-Undang Pokok Agraria) - Hukum Agraria Dasar
   - Hak Milik (kepemilikan - hanya warga negara)
   - Hak Guna Bangunan (hak bangunan)
   - Hak Pakai (hak penggunaan - orang asing)
   - Hak Sewa (sewa/rental)
```

#### Prioritas 2 (PENTING):

```
□ Peraturan zonasi provinsi
   - Bali: zona pariwisata, pembatasan kepemilikan asing
   - Jakarta: komersial vs residensial
   - Provinsi lainnya

□ Peraturan pajak properti
   - PBB (Pajak Bumi dan Bangunan)
   - BPHTB (Pajak transfer 5%)

□ Peraturan sewa
   - Perjanjian sewa jangka panjang
   - Sewa jangka pendek (perizinan sewa villa)
```

### Dari Mana Mendapatkannya:

**Sumber pemerintah:**

- PP 18/2021: https://peraturan.bpk.go.id
- UUPA: Hukum agraria standar (1960, diperbarui)

**Khusus Bali:**

- Perda (Peraturan Daerah) Bali tentang properti
- Persyaratan IMB (izin mendirikan bangunan)

---

## 📚 Notebook 5: CROSS-DOMAIN LEVEL 2 (Person 5)

**NotebookLM Name:** "Nuzantara - Cross Domain Level 2"

### Dokumen yang Diperlukan:

#### Strategi: **Upload SEMUA dokumen dari Notebooks 1-4**

```
Dari Notebook 1 (Visa):
✅ PP 31/2013
✅ Permenkumham 28/2024
✅ PP 34/2021
✅ Daftar Jabatan Kemnaker

Dari Notebook 2 (KBLI):
✅ PP 28/2025
✅ KBLI_2025_FINAL_CLEAN.json
✅ Lampiran 1a, 1b
✅ PP 5/2021

Dari Notebook 3 (Tax):
✅ UU 7/2021
✅ PP 55/2022
✅ Panduan DJP

Dari Notebook 4 (Property):
✅ PP 18/2021
✅ UUPA
```

**Total:** ~15-20 dokumen

**Tujuan:** NotebookLM dapat melakukan referensi silang antar domain

- Setup perusahaan + Persyaratan Visa
- Pembelian properti + Implikasi Pajak
- Skenario Bisnis + Imigrasi + Pajak

---

## 📚 Notebook 6: MULTI-DOMAIN SOTA (Person 6)

**NotebookLM Name:** "Nuzantara - Multi-Domain SOTA"

### Dokumen yang Diperlukan:

#### Strategi: **Upload SEMUANYA + tambahan**

```
Semua dokumen dari Notebooks 1-5 PLUS:

✅ Studi kasus (jika tersedia)
   - Contoh setup PT PMA nyata
   - Skenario relokasi keluarga
   - Struktur bisnis kompleks

✅ Variasi provinsi
   - Peraturan khusus Bali
   - Peraturan Jakarta
   - Aturan zona pariwisata

✅ Interpretasi ahli
   - Opini hukum
   - Klarifikasi BKPM
   - Memo kantor imigrasi

✅ Indeks referensi silang
   - Bagaimana domain berinteraksi
   - Kesalahan umum
   - Praktik terbaik
```

**Total:** 20-30+ dokumen

**Tujuan:** Basis pengetahuan paling komprehensif untuk query SOTA

---

## 🗂️ Checklist Persiapan Dokumen

### Untuk ANDA (Setup):

```bash
# 1. Cek dokumen yang sudah ada
cd /Users/antonellosiano/Projects/nuzantara
find . -name "*.pdf" | grep -E "(PP|UU|Permen)" | head -20

# 2. Organisir per domain
mkdir -p data/notebooklm_docs/{visa,kbli,tax,property,cross,multi}

# 3. Copy dokumen KBLI (sudah selesai)
ls data/kb_sources/
# ✅ PP 28/2025, KBLI JSON, Lampiran 1a/1b

# 4. Cari peraturan lainnya
# Person 1 perlu: PP 31/2013, Permenkumham 28/2024, PP 34/2021
# Person 3 perlu: UU 7/2021, PP 55/2022
# Person 4 perlu: PP 18/2021, UUPA
```

### Untuk TIM:

**Opsi A: Anda menyediakan semua PDFs**

- Tim hanya upload ke NotebookLM
- Tercepat, paling konsisten

**Opsi B: Tim mencari dokumen sendiri**

- Anda menyediakan daftar + sumber
- Setiap orang download untuk domain mereka
- Lebih fleksibel tapi lebih lambat

**Opsi C: Hybrid (DIREKOMENDASIKAN)**

- Anda menyediakan dokumen kritis (PP 28/2025, dll.) ✅ Sudah selesai
- Tim menggunakan pengetahuan umum NotebookLM untuk peraturan lainnya
- Tentukan nomor peraturan dalam prompt

---

## 📋 Matriks Status Dokumen

| Domain       | Dokumen Kritis          | Status  | Lokasi             |
| ------------ | ----------------------- | ------- | ------------------ |
| **KBLI**     | PP 28/2025 + JSON       | ✅ SIAP | `data/kb_sources/` |
| **KBLI**     | Lampiran 1a, 1b         | ✅ SIAP | `data/kb_sources/` |
| **Visa**     | PP 31/2013              | ⚠️ CARI | TBD                |
| **Visa**     | Permenkumham 28/2024    | ⚠️ CARI | TBD                |
| **Visa**     | PP 34/2021              | ⚠️ CARI | TBD                |
| **Visa**     | Daftar Jabatan Kemnaker | ⚠️ CARI | TBD                |
| **Tax**      | UU 7/2021               | ⚠️ CARI | TBD                |
| **Tax**      | PP 55/2022              | ⚠️ CARI | TBD                |
| **Property** | PP 18/2021              | ⚠️ CARI | TBD                |
| **Property** | UUPA                    | ⚠️ CARI | TBD                |

---

## 🎯 Aksi Selanjutnya

### Segera:

1. **Cari PDFs yang hilang:**

```bash
# Cari peraturan di proyek
find . -type f -name "*.pdf" | xargs grep -l "PP.*2013\|PP.*2021\|UU.*2021" 2>/dev/null

# Atau cek apakah Anda memiliki repositori peraturan
ls ~/Documents/Indonesia_Regulations/ 2>/dev/null || echo "Buat folder peraturan"
```

2. **Titik Keputusan:**

**A) Punya PDFs?**
→ Organisir di `data/notebooklm_docs/{domain}/`
→ Tim melakukan upload

**B) TIDAK punya PDFs?**
→ Tim menggunakan pengetahuan umum NotebookLM
→ Tentukan nomor peraturan di setiap prompt
→ Contoh: "Berdasarkan PP 31/2013..."

**C) Hybrid?** (DIREKOMENDASIKAN)
→ Domain KBLI: Gunakan PDFs (sudah siap) ✅
→ Domain lainnya: Pengetahuan umum NotebookLM
→ Kualitas tetap optimal dengan kutipan peraturan

### Pertanyaan untuk Anda:

**Apakah Anda ingin:**

A) **Saya mencari PDFs yang hilang** di proyek/online?
B) **Lanjutkan tanpa PDFs** (pengetahuan umum NotebookLM)?
C) **Tim mencari PDFs mereka sendiri** (saya hanya beri link sumber)?

Beri tahu dan saya akan mengorganisir!
