# Panduan Tim - NotebookLM Q&A per Golden Seeds

**Tujuan:** Menghasilkan 500-800 percakapan tervalidasi menggunakan NotebookLM + tim manual

**Alur Kerja:** NotebookLM Q&A → File .txt → Validasi Damar → Redis cache

---

## 👥 Peran Tim & Tanggung Jawab

### Orang 1: **SPESIALIS VISA**

- **Fokus:** Semua jenis visa + posisi pekerjaan Kemnaker
- **Target:** 100-120 pertanyaan basic
- **Notebook:** "Nuzantara - Visa & Immigration"
- **Direktori:** `data/notebooklm_responses/visa/`

### Orang 2: **SPESIALIS KBLI**

- **Fokus:** Kode KBLI (prioritas Tier 1 granitik) + izin usaha
- **Target:** 150-200 pertanyaan basic
- **Notebook:** "Nuzantara - KBLI & Licensing"
- **Direktori:** `data/notebooklm_responses/kbli/`

### Orang 3: **SPESIALIS PAJAK**

- **Fokus:** Semua jenis pajak (PPh, PPN, perjanjian pajak)
- **Target:** 40-50 pertanyaan basic
- **Notebook:** "Nuzantara - Tax & Compliance"
- **Direktori:** `data/notebooklm_responses/tax/`

### Orang 4: **SPESIALIS PROPERTI**

- **Fokus:** Sertifikat properti + aturan kepemilikan asing
- **Target:** 30-40 pertanyaan basic
- **Notebook:** "Nuzantara - Property & Real Estate"
- **Direktori:** `data/notebooklm_responses/property/`

### Orang 5: **KOORDINATOR LINTAS DOMAIN**

- **Fokus:** Skenario 2-topik (company+visa, visa+property, dll.)
- **Target:** 100-150 pertanyaan level 2
- **Notebook:** "Nuzantara - Cross Domain Level 2"
- **Direktori:** `data/notebooklm_responses/cross_domain/`

### Orang 6: **ARSITEK SOTA**

- **Fokus:** Skenario multi-domain kompleks (3+ topik)
- **Target:** 50-80 pertanyaan level 3
- **Notebook:** "Nuzantara - Multi-Domain SOTA"
- **Direktori:** `data/notebooklm_responses/multi_domain/`

---

## 📝 Alur Kerja Langkah-demi-Langkah (untuk setiap orang)

### Langkah 1: Setup NotebookLM Notebook

1. Buka: https://notebooklm.google.com
2. Buat notebook dengan nama spesifik (contoh: "Nuzantara - Visa & Immigration")
3. Upload dokumen untuk domain Anda (lihat di bawah)
4. Tunggu indexing (3-5 menit)

### Langkah 2: Siapkan Daftar Pertanyaan

Setiap orang memiliki file `questions_list.md` di direktorinya:

```bash
# Orang 1 (Visa)
cp data/notebooklm_responses/visa/questions_template.md \
   data/notebooklm_responses/visa/MY_QUESTIONS.md

# Edit MY_QUESTIONS.md dengan pertanyaan Anda
```

### Langkah 3: Ajukan Pertanyaan ke NotebookLM

**Untuk setiap pertanyaan:**

1. Salin pertanyaan dari `MY_QUESTIONS.md`
2. Tempel di chat NotebookLM
3. Tunggu respons (30-60 detik)
4. **PENTING:** Baca respons untuk memverifikasi kualitas
5. Salin respons lengkap

### Langkah 4: Simpan Respons dalam File

**Konvensi penamaan:**

```
data/notebooklm_responses/{domain}/{id}_{topic}.txt

Contoh:
visa/001_kitas_investor.txt
kbli/045_restaurant_56101.txt
tax/012_pph_badan_corporate.txt
```

**Format file .txt:**

```
## Query
[Pertanyaan Anda]

## Response
[Respons lengkap NotebookLM dengan kutipan]

## Metadata
- Domain: visa_immigration
- Complexity: basic
- Date: 2026-02-09
- Validated: pending
```

### Langkah 5: Mengelola Respons Panjang

**Jika respons > 1000 kata, pisahkan menjadi beberapa bagian:**

```
visa/001_kitas_investor_part1.txt  (Definisi + Persyaratan)
visa/001_kitas_investor_part2.txt  (Proses + Timeline)
visa/001_kitas_investor_part3.txt  (Biaya + FAQ)
```

**Tambahkan header di setiap bagian:**

```
## Query
[Pertanyaan lengkap]

## Response - Part 1/3: Definisi dan Persyaratan
[Konten bagian 1]

---
Lanjutan di: 001_kitas_investor_part2.txt
```

### Langkah 6: Tracking Progress

Setiap orang memelihara `PROGRESS.md`:

```markdown
# VISA Domain - Progress

**Total Questions:** 120
**Completed:** 45
**In Progress:** 10
**Pending:** 65

## Completed (45)

- [x] 001_kitas_investor.txt
- [x] 002_kitas_work.txt
- [x] 003_e33g_digital_nomad.txt
      ...

## In Progress (10)

- [ ] 046_kemnaker_job_software_engineer.txt
- [ ] 047_kemnaker_job_chef.txt
      ...

## Issues / Notes

- Proses renewal KITAS: NotebookLM mengutip PP 31/2013, verifikasi pembaruan 2024
- Timeline E-Visa: respons tidak jelas "7-14 hari", minta lebih spesifik
```

---

## 📚 Dokumen untuk NotebookLM (per domain)

**STRATEGI HYBRID (DIREKOMENDASIKAN):**

- **Domain KBLI (Orang 2):** Gunakan PDF yang sudah siap di `data/kb_sources/` ✅
- **Domain lainnya (Orang 1, 3, 4):** Gunakan pengetahuan umum NotebookLM + kutipan regulasi
- **Cross/Multi-domain (Orang 5, 6):** Kombinasikan PDF KBLI + pengetahuan umum domain lainnya

**Mengapa hybrid?**

- Spesialis KBLI dapat mulai SEGERA dengan dokumen lengkap
- Spesialis lainnya tidak terhambat mencari PDF
- Pengetahuan umum NotebookLM akurat jika Anda menentukan nomor regulasi
- Jika PDF tersedia kemudian, dapat ditambahkan

---

### SPESIALIS VISA (Orang 1)

**PENDEKATAN:** Pengetahuan umum + kutipan regulasi

Dalam setiap pertanyaan, tentukan regulasi:

```
"Berdasarkan PP 31/2013 (Immigration Law),
Permenkumham 28/2024 (E-Visa), dan PP 34/2021 (IMTA),
jelaskan apa itu KITAS Investor dan persyaratan lengkapnya..."
```

**PDF Opsional** (jika tersedia):

- PP 31/2013 (Immigration Law)
- Permenkumham 28/2024 (E-Visa)
- PP 34/2021 (IMTA/Work Permits)
- Daftar Posisi Pekerjaan Kemnaker

**Jika menemukan PDF:** Upload ke NotebookLM untuk kutipan yang lebih presisi

### SPESIALIS KBLI (Orang 2)

**PENDEKATAN:** ✅ PDF lengkap SIAP DIGUNAKAN

Upload 4 file ini (sudah ada di `data/kb_sources/`):

```
✅ PP Nomor 28 Tahun 2025.pdf (20MB)
✅ KBLI_2025_FINAL_CLEAN.json (7.3MB)
✅ lampiran_1a.pdf (12MB)
✅ lampiran_1b.pdf (22MB)
```

**Orang 2 dapat mulai SEGERA!** 🚀

**Untuk KBLI Tier 2 (menunggu BKPM):**

Tambahkan akhiran prompt ini:

```
Jika kode KBLI ini masih menunggu klarifikasi dari BKPM,
tunjukkan dengan jelas:

"⚠️ PERHATIAN: KBLI [code] SEDANG MENUNGGU klarifikasi resmi dari BKPM.
Respons berikut berdasarkan interpretasi awal PP 28/2025
dan dapat berubah.

[Respons sementara dengan kutipan yang tersedia]

Saran: Verifikasi dengan BKPM sebelum melanjutkan pendaftaran usaha."
```

### SPESIALIS PAJAK (Orang 3)

**PENDEKATAN:** Pengetahuan umum + kutipan regulasi

Dalam setiap pertanyaan, tentukan:

```
"Berdasarkan UU 7/2021 (Tax Harmonization Law)
dan PP 55/2022 (Income Tax Implementation),
jelaskan tarif PPh Badan untuk PT PMA..."
```

**KRITIS:** Selalu verifikasi:

- Tarif PPN: 11% (BUKAN 12%)
- PPh Badan: 22%
- Kutip UU 7/2021 di setiap respons

**PDF Opsional** (jika tersedia):

- UU 7/2021 (Tax Harmonization)
- PP 55/2022 (Income Tax)
- Panduan DJP 2024-2025

### SPESIALIS PROPERTI (Orang 4)

**PENDEKATAN:** Pengetahuan umum + kutipan regulasi

Dalam setiap pertanyaan, tentukan:

```
"Berdasarkan PP 18/2021 (Hak Pakai untuk asing)
dan UUPA (Undang-Undang Pokok Agraria),
jelaskan persyaratan untuk orang asing membeli properti..."
```

**KRITIS:** Selalu sebutkan:

- Hak Pakai (asing) vs Hak Milik (hanya WNI)
- Persyaratan KITAS
- Minimum provinsi (Bali Rp 1-2M, Jakarta Rp 3-5M)
- Risiko nominee (ILEGAL)

**PDF Opsional** (jika tersedia):

- PP 18/2021 (Hak Pakai)
- UUPA (Undang-Undang Agraria 1960)

### LINTAS DOMAIN (Orang 5)

Upload:

```
✅ SEMUA dokumen dari Orang 1-4
```

### MULTI-DOMAIN (Orang 6)

Upload:

```
✅ SEMUA dokumen yang tersedia
✅ Studi kasus jika tersedia
```

---

## ✅ Quality Gates (pemeriksaan mandiri)

Sebelum menyimpan respons, verifikasi:

### Checklist Minimal:

- [ ] **Kutipan:** Minimal 2 kutipan `[Source: PP XX/YEAR, Article Y]`
- [ ] **Panjang:** 200-600 kata (basic), 800-1200 (complex)
- [ ] **Struktur:** Headings (##) dan bullet points ada
- [ ] **Akurasi:** Angka dan tanggal terlihat benar
- [ ] **Peringatan:** KBLI Tier 2 memiliki disclaimer yang sesuai

### Red Flags (yang harus diperiksa):

- ❌ "Sekitar", "kurang lebih" tanpa kutipan
- ❌ Angka sangat umum ("10-20 juta IDR")
- ❌ "Menurut peraturan" (peraturan mana?)
- ❌ Kontradiksi internal

### Jika menemukan Red Flags:

**Opsi A:** Lakukan follow-up ke NotebookLM:

```
"Dalam respons sebelumnya Anda menyebutkan 'sekitar 10 juta IDR'.
Bisakah Anda mengutip sumber pasti dengan nomor pasal?"
```

**Opsi B:** Catat di `PROGRESS.md` untuk review selanjutnya

---

## 🔄 Template Alur Kerja Harian

### Pagi (2 jam):

1. Review `PROGRESS.md`
2. Prioritaskan 10-15 pertanyaan untuk hari ini
3. Buka notebook NotebookLM
4. Batch Q&A (10-15 pertanyaan)
5. Simpan respons ke file `.txt`

### Siang (1 jam):

6. Periksa sendiri respons (quality gates)
7. Pisahkan respons panjang jika perlu
8. Update `PROGRESS.md`
9. Tandai masalah untuk review tim

### Estimasi Output:

- **Per orang per hari:** 10-15 respons tervalidasi
- **Per orang per minggu:** 50-75 respons
- **Tim penuh per minggu:** 300-450 respons
- **Timeline ke 800 total:** ~2-3 minggu

---

## 🚨 Masalah Umum & Solusi

### Masalah 1: Respons NotebookLM terlalu umum

**Solusi:** Reformulasi pertanyaan dengan lebih banyak konteks:

```
Daripada:
"Apa itu KITAS Investor?"

Gunakan:
"Apa itu KITAS Investor untuk orang asing yang membuka PT PMA di Indonesia?
Sertakan persyaratan investasi minimum, durasi, proses aplikasi,
dan perbedaan vs KITAS Work. Kutip pasal-pasal relevan PP 31/2013."
```

### Masalah 2: NotebookLM tidak mengutip dokumen yang diupload

**Solusi:** Eksplisit dalam pertanyaan:

```
"Berdasarkan dokumen yang diupload (PP 28/2025 dan KBLI 2025 JSON),
jelaskan kode KBLI mana yang mengizinkan investasi asing di sektor F&B."
```

### Masalah 3: Respons kontradiktif atau usang

**Solusi:** Tandai di `PROGRESS.md`:

```
## Issues / Notes
- 023_vitas_211.txt: NotebookLM menyebutkan VITAS 211, tapi itu USANG sejak 2022
  → Digantikan oleh E-Visa. Regenerasi pertanyaan dengan konteks terbaru.
```

### Masalah 4: Respons terlalu panjang (>2000 kata)

**Solusi:** Pisahkan dan tentukan scope:

```
Pertanyaan 1: "KITAS Investor - Bagian 1: Definisi dan persyaratan dasar"
Pertanyaan 2: "KITAS Investor - Bagian 2: Proses aplikasi langkah-demi-langkah"
Pertanyaan 3: "KITAS Investor - Bagian 3: Renewal dan FAQ umum"
```

---

## 📊 Konsolidasi (setelah Phase 1)

**Ketika tim menyelesaikan pertanyaan basic:**

Setiap orang menyerahkan file `.txt` mereka ke koordinator yang:

1. Validasi konsistensi format
2. Periksa quality gates
3. Konsolidasikan ke `data/golden_seeds.json`
4. Serahkan ke Damar untuk validasi final

**Skrip konsolidasi:**

```bash
python scripts/caching/consolidate_team_responses.py \
  --input data/notebooklm_responses/ \
  --output data/golden_seeds_all.json
```

---

## 🎯 Metrik Keberhasilan

**Per Orang:**

- [ ] 100% pertanyaan yang ditugaskan selesai
- [ ] 90%+ lulus pemeriksaan kualitas mandiri
- [ ] `PROGRESS.md` diupdate setiap hari

**Per Tim:**

- [ ] 500-800 respons total
- [ ] 80%+ tingkat kelulusan validasi Damar
- [ ] Timeline: 2-3 minggu

---

## 📞 Komunikasi Tim

**Daily Standup (15 menit):**

- Masing-masing: "Kemarin: X selesai, Hari ini: Y direncanakan, Masalah: Z"
- Sinkronisasi dependensi lintas domain

**Weekly Review:**

- Pemeriksaan kualitas sampel acak (10%)
- Sesuaikan template jika diperlukan
- Rayakan progres! 🎉

---

**Siap untuk mulai!** 🚀

Setiap orang mulai dengan Langkah 1: Setup NotebookLM untuk domain masing-masing.
