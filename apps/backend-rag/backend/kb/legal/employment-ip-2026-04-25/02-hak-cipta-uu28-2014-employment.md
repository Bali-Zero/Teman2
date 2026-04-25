---
title: Copyright Assignment in Indonesian Employment — UU 28/2014 Pasal 35, 36, 57
domain: company
subdomain: employment_law_ip_protection
topic: copyright_assignment
collection: legal_unified_hybrid_hybrid
notebook: NB-3
language: ID + EN
priority: P0
applicable_law: UU No. 28 Tahun 2014 tentang Hak Cipta
sources:
  - https://peraturan.bpk.go.id/Download/28018/UU%20Nomor%2028%20Tahun%202014.pdf
  - https://dgip.go.id/artikel/detail-artikel-berita/hak-cipta-karya-pekerja-atau-freelancer-milik-siapa
  - https://siprconsultant.id/hak-cipta-dan-hubungan-kerja-menentukan-pemilik-sah-atas-karya-karyawan
  - https://www.kk-advocates.com/news/read/copyright-and-generative-ai-does-indonesian-copyright-law-protect-ai-generated-works
---

# Copyright Assignment — UU 28/2014 in Employment Contracts

## Three key articles (verbatim)

### Pasal 35 (Work-for-hire default)

> "Kecuali diperjanjikan lain Pemegang Hak Cipta atas Ciptaan yang dibuat oleh Pencipta dalam hubungan dinas, yang dianggap sebagai Pencipta yaitu pemberi kerja atau instansi tempat Pencipta bekerja."

**Practical translation:** Unless otherwise agreed, copyright in works created in an employment relationship vests in the **employer**, not the employee. The employer is **deemed the author** for IP purposes.

### Pasal 36 (Economic rights are assignable)

> "Kecuali diperjanjikan lain, Pencipta dan Pemegang Hak Cipta dapat mengalihkan hak ekonomi atas Ciptaannya kepada pihak lain."

**Practical translation:** Economic rights (hak ekonomi) can be assigned by written agreement.

### Pasal 57 (Moral rights are NON-assignable)

> "Hak moral Pencipta ... tidak dapat dihapuskan, dialihkan, atau dibatasi."

**Practical translation:** Moral rights (hak moral) — paternity, integrity, attribution — **cannot be alienated, transferred, or limited**. They stay with the natural-person Pencipta for life.

## The "hubungan dinas" auto-vest — and why you must NOT rely on it

### Default rule

Pasal 35 says employer **automatically** owns copyright on employee work _unless agreed otherwise_. This sounds great for employers but has critical gaps:

### Gap 1: Code written outside office hours

An ambiguous case: employee writes code at home, on weekend, on personal laptop, but for company project. Pasal 35 default may not clearly cover this.

### Gap 2: Code using employer resources but not strictly "in dinas"

Employee uses company laptop, company VPN, company credentials, company library, but for what they claim is "personal exploration." Default vesting becomes contestable.

### Gap 3: Derivative works after termination

Employee leaves, then creates derivative work based on what they learned. Default rule doesn't reach this.

### Solution: explicit fail-safe assignment clause

Always include explicit assignment in addition to relying on Pasal 35. Cover all three gaps.

## Fail-safe assignment clause (Bahasa Indonesia)

```
1. PARA PIHAK mengakui bahwa hubungan kerja yang diatur dalam Perjanjian
   ini merupakan "hubungan dinas" sebagaimana dimaksud dalam Pasal 35
   UU No. 28 Tahun 2014. Dengan demikian, kecuali diperjanjikan lain,
   PIHAK PERTAMA dianggap sebagai Pemegang Hak Cipta atas seluruh
   Ciptaan yang dibuat oleh PIHAK KEDUA dalam hubungan dinas ini.

2. Untuk menghindari setiap keraguan, PIHAK KEDUA dengan ini, secara
   terus-menerus, tidak dapat dibatalkan, eksklusif, dan bebas royalti,
   mengalihkan kepada PIHAK PERTAMA seluruh hak ekonomi sebagaimana
   diatur dalam Pasal 8 sampai Pasal 11 UU No. 28 Tahun 2014, atas
   setiap dan seluruh Ciptaan, termasuk namun tidak terbatas pada:
   (a) Kode sumber, kode biner, modul, library, skrip;
   (b) Dokumentasi teknis, README, komentar dalam kode;
   (c) AI prompts, prompt template, prompt library, system prompt;
   (d) Konfigurasi sistem, file infrastruktur, Dockerfile, file CI/CD;
   (e) Desain database, skema, migrasi, arsitektur RAG;
   (f) Konten teks, artikel, materi marketing, landing page;
   (g) Desain visual, mockup, ilustrasi, video, audio;
   (h) Dataset, basis pengetahuan, koleksi vektor, knowledge graph;
   (i) Seluruh karya turunan dan modifikasi atas Ciptaan-Ciptaan di atas.

3. Pengalihan ini berlaku terhadap setiap Ciptaan, terlepas dari:
   (a) Apakah dibuat di dalam atau di luar jam kerja;
   (b) Apakah dibuat di kantor PIHAK PERTAMA atau di tempat lain;
   (c) Apakah dibuat menggunakan perangkat PIHAK PERTAMA atau perangkat
       pribadi PIHAK KEDUA;
   sepanjang Ciptaan tersebut: (i) dibuat menggunakan fasilitas,
   perangkat, akses, akun, data, kredensial, library, atau informasi
   PIHAK PERTAMA; dan/atau (ii) berkaitan dengan ruang lingkup tugas
   PIHAK KEDUA; dan/atau (iii) dibuat berdasarkan instruksi atau
   penugasan PIHAK PERTAMA.
```

## Hak Moral — what to do about non-assignable rights

You can't transfer them, but you CAN obtain advance permanent waiver of enforcement.

### Sample moral rights waiver (Bahasa Indonesia)

```
PARA PIHAK mengakui bahwa berdasarkan Pasal 5 dan Pasal 57 UU No. 28
Tahun 2014, Hak Moral PIHAK KEDUA sebagai Pencipta tidak dapat
dihapuskan, dialihkan, atau dibatasi selama PIHAK KEDUA masih hidup.
Namun demikian, PIHAK KEDUA dengan ini secara tegas:

(a) Memberikan persetujuan permanen dan tidak dapat dibatalkan kepada
    PIHAK PERTAMA untuk:
    (i)   tidak mencantumkan nama PIHAK KEDUA pada Ciptaan apabila
          PIHAK PERTAMA menganggap perlu;
    (ii)  menggunakan nama samaran atau nama Perusahaan untuk Ciptaan;
    (iii) melakukan modifikasi, penyesuaian, dan turunan terhadap
          Ciptaan tanpa kewajiban memberi tahu atau meminta persetujuan;

(b) Berjanji tidak akan menggunakan Hak Moralnya untuk menghalangi,
    membatasi, atau mengganggu pemanfaatan Ciptaan oleh PIHAK PERTAMA.
```

This works because Pasal 57 prohibits **transfer** but not **advance contractual undertaking not to enforce**. It's a common drafting pattern in Indonesian IP contracts.

## Warranty clauses (employee guarantees)

Critical for protecting against open-source contamination + third-party IP claims:

```
PIHAK KEDUA menjamin bahwa:
(a) seluruh Ciptaan yang dihasilkan adalah karya orisinal PIHAK KEDUA
    atau yang sah secara hukum dapat digunakannya;
(b) tidak melanggar Hak Cipta, paten, merek, atau hak kekayaan
    intelektual pihak ketiga lainnya;
(c) tidak mengandung kode open-source dengan lisensi copyleft yang
    tidak kompatibel (mis. GPL) tanpa persetujuan tertulis dari
    PIHAK PERTAMA;
(d) tidak mengandung backdoor, malware, atau kode yang dapat
    membahayakan sistem PIHAK PERTAMA.
```

## AI prompts — special framing

AI system prompts are a novel area. Indonesian copyright law has **not yet established clear precedent** that AI prompts qualify as "karya tulis" (literary work). Best practice:

### Dual protection strategy

1. **Primary: Trade Secret** under UU 30/2000 — prompts kept secret, marked as confidential, restricted access
2. **Secondary: Copyright assignment** under UU 28/2014 — include prompts explicitly in the Pasal 35 + Pasal 36 assignment language

### Why both?

- If prompt qualifies as karya tulis → covered by copyright (~70 years protection)
- If prompt does NOT qualify (insufficient human originality) → still covered by trade secret (perpetual while secret)

### Sample prompt-specific language

```
Termasuk dalam Ciptaan yang dialihkan adalah:
- AI prompts, prompt template, prompt library, system prompt
- Termasuk file di apps/backend-rag/backend/prompts/ (zantara_core.py
  dan turunannya), agent prompts, prompt orkestrasi RAG, dan seluruh
  prompt yang digunakan untuk mengarahkan model bahasa (LLM).
```

## Criminal sanctions — UU 28/2014 Pasal 113-116

For commercial-purpose infringement (kepentingan komersial):

- **Pasal 113 ayat (3):** distribusi/penjualan ciptaan tanpa hak — max **4 tahun penjara dan/atau denda max Rp 1 miliar**
- **Pasal 116 ayat (3):** pelanggaran hak terkait (related rights) untuk komersial — max **4 tahun + Rp 1 miliar**

## Common drafting mistakes (avoid)

| Mistake                                 | Fix                                                         |
| --------------------------------------- | ----------------------------------------------------------- |
| Relying only on Pasal 35 default        | Add explicit fail-safe Pasal 36 assignment                  |
| Vague scope ("works during employment") | Triple-condition coverage: time / place / device irrelevant |
| Forgetting AI prompts                   | Explicitly enumerate prompt types                           |
| No moral rights waiver of enforcement   | Add advance non-enforcement undertaking                     |
| No open-source warranty                 | Add GPL/copyleft incompatibility warranty                   |

## Cross-references

- Trade secret: `01-rahasia-dagang-uu30-2000.md`
- Pasal templates: `05-pasal-templates-ready-bahasa-indonesia.md`
