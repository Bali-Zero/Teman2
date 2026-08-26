# Panduan Kerja Harian Damar

## Editorial Director Bali Zero — Artikel, Carousel, dan Video Zantara

**Versi:** 2.0  
**Tanggal:** 27 Agustus 2026  
**Zona waktu:** WITA  
**Status:** Panduan internal Bali Zero

---

## 1. Tujuan pekerjaan ini

Setiap hari Damar memimpin tiga jalur editorial Bali Zero:

1. memilih dan menerbitkan artikel terbaik di website;
2. membuat satu carousel harian yang relevan, jelas, dan layak disimpan atau dibagikan;
3. sedikitnya tiga kali seminggu, membuat video Zantara yang mengikuti inti cerita carousel.

Damar bukan operator yang hanya mengikuti output AI. **Damar adalah Editorial Director dan, untuk video, Damar adalah sutradara.** Agent mengerjakan riset, verifikasi, struktur, draft, image generation, packaging, dan quality control. Damar mengambil keputusan editorial dan visual. Antonello memberi approval akhir untuk carousel dan video.

### Tiga peran yang tidak boleh tertukar

| Peran         | Tanggung jawab utama                                                                                                                                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Agent**     | Mencari, membaca, membandingkan, memverifikasi, memberi rekomendasi, menulis, membuat gambar dengan ImageGen, menyiapkan SEO/caption/alt text, menyiapkan prompt Flow, menyusun paket, dan menjalankan QA. Agent tidak memicu publikasi social.         |
| **Damar**     | Memilih artikel dan posisi website, memilih topik dan angle carousel, memilih arah visual, menyempurnakan di Canva bila perlu, menyutradarai video, menyerahkan paket final pukul 15:00, dan menerbitkan carousel/video secara manual setelah approval. |
| **Antonello** | Memberi approval atau revisi untuk carousel dan video sebelum publikasi pukul 17:00.                                                                                                                                                                    |

### Prinsip utama

> Agent harus mengurangi pekerjaan mekanis Damar, bukan mengambil alih penilaian kreatif Damar.

> Cover yang kuat bukan cover yang misterius. Cover yang kuat membuat fakta konkret mustahil diabaikan.

> Tidak ada placeholder. Tidak ada gambar yang “sementara”. Tidak ada gambar cantik yang menceritakan hal berbeda dari konten.

---

# KOKPIT HARIAN DAMAR — BACA INI SETIAP PAGI

## Status operasional hari ini

**SEKARANG — yang benar-benar dapat dilakukan:**

- Agent membaca dan menilai artikel News Room, menyiapkan copy final, SEO, cover dengan ImageGen, caption, sumber, dan QA.
- **Damar menerbitkan artikel melalui News Room.** Agent kemudian memeriksa URL, cover, SEO, dan posisi yang terlihat di website live.
- **Damar menerbitkan carousel dan video secara manual pukul 17:00 hanya setelah approval eksplisit Antonello.** Bila approval belum ada, statusnya `HOLD`; diam bukan approval.
- Agent tidak boleh mengatakan `live` sebelum halaman atau post yang benar sudah dibuka dan diperiksa.

**TARGET — hanya setelah Bridge dinyatakan aktif, diuji, dan terbukti live:**

- Setelah keputusan dan konfirmasi final Damar, agent meng-update artikel, memasang cover, memilih posisi, menerbitkan, dan memverifikasi website live.
- Approval Antonello sebelum carousel/video pukul 17:00 tetap wajib. Sampai aturan dan action social-publish berubah secara resmi, tombol publish sosial tetap ditekan Damar.

> Jangan memakai mode TARGET hanya karena sebuah fitur sedang dibuat atau sebuah PR sudah ada. Agent harus dapat membuktikan action tersedia dan lolos uji live pada hari itu.

## Lima keputusan Damar

Damar hanya perlu memutuskan:

1. artikel mana yang layak terbit dan di posisi mana;
2. topik carousel mana yang paling kuat;
3. arah cover mana yang paling jelas dan kuat;
4. setting, outfit, dan regia video mana yang dipakai;
5. apakah paket pukul 15:00 sudah layak dikirim ke Antonello.

Agent mengerjakan riset, verifikasi, draft, asset, folder, penamaan file, caption, SEO, dan QA. Damar tidak perlu mengurus item ID, prompt panjang, endpoint, request key, branch, deploy, atau struktur folder teknis.

## Jadwal satu layar

| Jam       | Keputusan / hasil                                                                                   |
| --------- | --------------------------------------------------------------------------------------------------- |
| 08:30     | Damar meminta daftar artikel.                                                                       |
| 09:15     | Artikel dan posisi dipilih; yang tidak cukup kuat tidak dipaksa terbit.                             |
| 09:45     | Topik carousel dan content lock selesai.                                                            |
| 10:00     | Arah cover dipilih; pada hari video, Director Card juga dipilih.                                    |
| 11:15     | Pilot video EN/ID harus lulus atau disederhanakan satu kali.                                        |
| 13:00     | Carousel dilindungi sebagai prioritas; video yang tertinggal tidak boleh merusak deadline carousel. |
| 14:15     | QA final. Video yang belum siap dipindahkan ke hari video berikutnya.                               |
| **15:00** | Agent menyusun satu paket; Damar mengirim satu link dan satu pesan kepada Antonello.                |
| **17:00** | Damar publish manual hanya bila approval Antonello sudah eksplisit. Jika tidak: `HOLD`.             |

## Command Card — salin dan kirim

### 1 — Minta daftar artikel

> **Tampilkan lima artikel terkuat yang tersedia hari ini. Baca isi lengkap dan sumber asli setiap kandidat. Jelaskan singkat apa yang terjadi, mengapa penting sekarang, siapa audiensnya, risiko editorial, posisi website, dan ide cover. Kelompokkan sebagai PUBLISH TODAY, HOLD, atau VERIFY FIRST. Tulis juga jumlah artikel pending lainnya. Jangan publish apa pun.**

### 2 — Pilih artikel

> **Pilih artikel #1 untuk Hero Main dan #3 untuk Hero 3. Artikel #2 tetap HOLD. Siapkan preview final lengkap, SEO, cover, alt text, dan sumber untuk keputusan saya. JANGAN publish dulu.**

### 3 — Konfirmasi artikel

**Mode SEKARANG:**

> **FINAL DISETUJUI. Jangan publish melalui agent. Tampilkan langkah News Room yang harus saya lakukan, lalu verifikasi URL, posisi, cover, dan SEO live setelah saya selesai.**

**Mode TARGET, hanya setelah agent membuktikan Bridge aktif:**

> **FINAL DISETUJUI. Publikasikan artikel #1 di Hero Main dan artikel #3 di Hero 3. Jangan ubah copy atau cover. Setelah selesai, verifikasi URL, /news, homepage, OG image, desktop, dan mobile.**

### 4 — Pilih topik

> **Pilih kandidat B. Kunci audiens, fakta baru, konsekuensi, tindakan, caveat, dan semua sumber. Selesaikan UNKNOWN yang dapat mengubah cerita sebelum menulis slide. Tampilkan status LEGAL CHECK: PASS atau BLOCK.**

### 5 — Pilih cover

> **Buat tiga Direction Card cover yang benar-benar berbeda. Setiap route harus memiliki satu headline, satu empirical anchor, satu scene yang koheren, dan alasan mengapa dapat dipahami dalam satu sampai lima detik. Jangan generate image sebelum saya memilih route.**

### 6 — Bangun carousel

> **Route B disetujui. Bangun carousel final delapan slide berdasarkan content lock. Gunakan ImageGen native untuk cover dan hero. Tidak boleh ada placeholder, silent reuse, atau visual yang lebih samar daripada headline. Sertakan caption, alt text, serta daftar sumber dan klaim.**

### 7 — Mulai video

> **Hari ini adalah hari video. Gunakan content lock carousel yang sama. Berikan Director Card A/B/C untuk setting, outfit, lighting, camera rhythm, dan performance mood. Saya yang memilih direction. Jangan membuka Flow dulu.**

### 8 — Generate pilot

> **Director Card B disetujui. Kunci script EN dan ID, lalu generate Scene 1 sebagai pilot kedua bahasa dengan Character Zantara dan native Flow voice. Kedua pilot termasuk dalam baseline, bukan tambahan. Stop dan laporkan bila identity, voice, pronunciation, lipsync, framing, atau outfit gagal.**

### 9 — Paket pukul 15:00

> **Susun DAILY EDITORIAL PACKAGE hari ini dalam satu link/folder. Pastikan Canva, export, caption, subtitles, daftar sumber, dan video adalah versi yang sama. Tampilkan hanya masalah yang masih terbuka.**

## Bila agent macet atau mulai berputar-putar

Kirim salah satu perintah ini:

> **STOP. Ringkas keputusan yang sudah dikunci, masalah yang nyata, dan satu next action. Jangan ulangi riset yang sudah selesai.**

> **Jangan buat ulang seluruh carousel/video. Perbaiki hanya asset atau clip yang gagal dan pertahankan semua yang sudah lolos QA.**

> **Jika tool atau signal tidak tersedia, tulis UNAVAILABLE. Jangan menebak hasil trend, status publish, atau hasil generation.**

## Arti empat label

- `FACT`: didukung sumber yang dapat diperiksa.
- `INFERENCE`: kesimpulan logis dari fakta, tetapi tidak tertulis langsung di sumber.
- `IDEA`: angle atau interpretasi editorial Bali Zero.
- `UNKNOWN`: belum terbukti; bila mengubah inti cerita, pekerjaan berhenti sampai terselesaikan.

## Bahasa output publik

- Website article: English.
- Carousel dan caption carousel: English.
- Istilah resmi seperti KITAS, PT PMA, KBLI, hak pakai, KKPR, NPWP, Coretax, dan OSS RBA tetap ditulis verbatim; beri penjelasan English pada penggunaan pertama bila perlu.
- TikTok video: spoken Bahasa Indonesia + English translation subtitles.
- Instagram, Threads, Facebook, dan WhatsApp video: spoken English + English subtitles.

## Setup hari pertama — diperiksa sekali

- [ ] Damar masuk ke workspace Bali Zero dengan akun kerja yang benar.
- [ ] `Nuzantara — Bali Zero Desk` dapat dibuka.
- [ ] Agent dapat menampilkan artikel pending tanpa data client atau PII.
- [ ] News Room dapat dibuka dan akun Damar memiliki hak edit/upload/position/publish.
- [ ] ImageGen tersedia di agent.
- [ ] Flow dapat dibuka dan saved Character Zantara terlihat.
- [ ] Canva team, folder harian, dan channel approval Antonello dapat diakses.
- [ ] Satu artikel dummy/internal atau item aman telah dipakai untuk membuktikan alur tanpa publikasi outward.

## Yang bukan pekerjaan Damar

Damar tidak memperbaiki Bridge, tidak men-debug model, tidak mengelola deployment, tidak merakit sebelas attachment satu per satu, tidak menulis prompt panjang, dan tidak mengejar agent di loop teknis. Bila sistem gagal, agent memberi satu status jujur dan satu jalur manual yang jelas.

---

## 2. Jadwal harian

Jam mulai dapat menyesuaikan jadwal kantor. Dua deadline tidak berubah: **15:00 untuk penyerahan** dan **17:00 untuk publikasi setelah approval**.

| Waktu rekomendasi | Pekerjaan                          | Hasil yang harus ada                                                                                                                                                                   |
| ----------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 08:30–09:15       | Artikel website                    | Shortlist, keputusan Damar, paket artikel final, posisi website, dan publikasi/operasi News Room. Artikel sudah berupa draft pending; sesi ini bukan menulis artikel panjang dari nol. |
| 09:15–09:45       | Shortlist topik harian             | Maksimum lima kandidat; tiga kandidat kuat; satu keputusan Damar.                                                                                                                      |
| 09:45–10:15       | Content lock                       | Tesis, fakta, angle, audiens, struktur, dan CTA dikunci.                                                                                                                               |
| 10:15–12:30       | Produksi carousel                  | Copy, cover, slide, hero image, daftar sumber dan klaim, serta caption.                                                                                                                |
| 10:15–14:40       | Produksi video pada hari video     | Berjalan paralel segera setelah content lock.                                                                                                                                          |
| 12:30–14:15       | Canva dan finishing                | Layout final, thumbnail test, copy check, dan export.                                                                                                                                  |
| 14:15–14:50       | QA dan packaging                   | Paket lengkap dan konsisten.                                                                                                                                                           |
| **15:00**         | Penyerahan ke Antonello            | Satu paket lengkap, bukan pesan atau file terpisah-pisah.                                                                                                                              |
| 15:00–16:40       | Revisi                             | Hanya revisi yang diminta; ulangi QA pada bagian yang berubah.                                                                                                                         |
| **17:00**         | Publikasi social manual oleh Damar | Hanya deliverable yang sudah disetujui eksplisit.                                                                                                                                      |

### Hari video

Default: **Senin, Rabu, dan Jumat**. Hari dapat dipindahkan bila topik terbaik muncul pada hari lain. Yang wajib adalah sedikitnya tiga video per minggu, bukan memaksakan video lemah pada hari tertentu.

---

# BAGIAN I — ARTIKEL WEBSITE SETIAP PAGI

## 3. Langkah pertama setiap pagi

Damar membuka `Nuzantara — Bali Zero Desk` dan mengirim:

> **Tampilkan artikel yang tersedia hari ini. Untuk setiap artikel, baca isi lengkap dan sumber aslinya, lalu jelaskan dalam dua kalimat: apa yang terjadi dan mengapa penting sekarang. Urutkan dari yang paling layak dipublikasikan. Sertakan audiens, kualitas sumber, risiko editorial, posisi website yang disarankan, dan ide cover. Kelompokkan sebagai PUBLISH TODAY, HOLD, atau REJECT / VERIFY FIRST. Jangan hanya membaca judul.**

Agent harus terlebih dahulu:

1. memeriksa koneksi workspace;
2. mengambil daftar artikel pending;
3. membuka isi lengkap setiap kandidat yang dinilai;
4. memeriksa tanggal, sumber asli, klaim, dan kemungkinan duplikasi;
5. membandingkan artikel dengan kebutuhan audiens Bali Zero;
6. mengusulkan posisi berdasarkan kepentingan, bukan berdasarkan urutan masuk.

## 4. Bentuk jawaban wajib dari agent

Agent memberikan **lima artikel terkuat** pada layar pertama dan menulis `Artikel pending lainnya: N`. Damar dapat meminta halaman kedua. Tidak ada artikel yang disembunyikan atau dihapus.

| Prioritas | Artikel | Penjelasan singkat | Mengapa hari ini | Audience | Sumber | Risiko | Posisi yang disarankan | Ide cover |
| --------: | ------- | ------------------ | ---------------- | -------- | ------ | ------ | ---------------------- | --------- |

Setelah tabel, agent menulis rekomendasi singkat:

- **PUBLISH TODAY:** layak diterbitkan hari ini;
- **HOLD:** bagus tetapi belum mendesak atau slot website belum tepat;
- **REJECT / VERIFY FIRST:** lemah, usang, duplikat, atau klaim belum cukup terbukti.

Agent tidak boleh meminta Damar menyebut item ID, endpoint, branch, atau istilah teknis lain. Agent menyimpan referensi teknis tersebut sendiri.

Tidak wajib publish bila tidak ada artikel yang cukup kuat. Rutinitas tidak boleh menurunkan standar.

## 5. Cara Damar memilih artikel dan posisi

Damar cukup menjawab dengan bahasa biasa, misalnya:

> **Pilih nomor 1 sebagai Hero Main dan nomor 3 sebagai Hero 3. Nomor 2 tetap pending. Untuk nomor 1 saya ingin cover urban, serius, dan authoritative — bukan corporate stock.**

### Hero Main

Pilih hanya bila berita:

- berdampak luas pada expat, investor, perusahaan, employer, taxpayer, atau property owner;
- benar-benar segar atau memiliki perkembangan penting baru;
- memiliki sumber kuat;
- dapat dipahami dalam beberapa detik;
- memang pantas menggantikan berita utama saat ini.

Jangan memakai Hero Main untuk soft news, profil kecil, atau cerita yang hubungannya dengan layanan Bali Zero terlalu lemah.

### Hero 2–5

Untuk berita sekunder yang tetap penting, terutama:

- immigration dan visa;
- PT PMA, KBLI, OSS, dan business licensing;
- tax dan compliance;
- property dan hospitality operations;
- analisis praktis yang membantu audiens mengambil keputusan.

Jaga keragaman. Lima slot teratas tidak boleh berisi lima berita yang pada dasarnya sama.

Sebelum Damar mengganti slot homepage, agent/UI harus menunjukkan:

| Slot | Artikel sekarang | Artikel usulan | Mengapa perlu diganti sekarang |
| ---- | ---------------- | -------------- | ------------------------------ |

Menerbitkan artikel dan mengganti artikel homepage adalah dua keputusan editorial yang berbeda.

### Latest

Saat ini `Latest` memastikan artikel masuk ke halaman berita kronologis. **Latest tidak otomatis berarti artikel muncul di salah satu card homepage.** Jika homepage harus berubah, Damar harus memilih slot homepage yang nyata.

### Insight

Jangan gunakan slot `Insight 1–3` sampai frontend website benar-benar menampilkannya. Slot tersebut ada di data tetapi belum menjadi posisi publik yang dapat dipercaya.

## 6. Paket final artikel sebelum publish

Setelah Damar memilih, agent harus menyiapkan satu preview final untuk setiap artikel:

- title final;
- two-line summary;
- category;
- slug;
- SEO title;
- SEO description;
- excerpt;
- tags;
- cover preview;
- cover alt text;
- source dan tanggal sumber;
- posisi website;
- URL yang diperkirakan;
- label `FACT`, `INFERENCE`, `IDEA`, atau `UNKNOWN` untuk setiap hal yang berisiko;
- blocker yang masih tersisa.

Damar memeriksa paket tersebut dan menjawab:

> **FINAL DISETUJUI. Gunakan command Mode SEKARANG atau Mode TARGET pada Kokpit sesuai status Bridge yang sudah dibuktikan hari ini.**

Keputusan memilih artikel tidak sama dengan konfirmasi final publish. Konfirmasi final hanya diberikan setelah preview lengkap terlihat.

Konfirmasi bersifat satu artikel per satu instruksi dan harus menyebut artikel, posisi, versi cover, serta versi preview:

> **CONFIRM PUBLISH — [JUDUL / NOMOR ARTIKEL] → [HERO MAIN / HERO 2–5 / LATEST], COVER [VERSI], PREVIEW [VERSI].**

Agent mengulang kembali empat elemen itu sebelum action. `Oke`, `lanjut`, pemilihan artikel, atau persetujuan copy bukan konfirmasi publish. Bila judul, posisi, cover, atau preview berubah, konfirmasi lama gugur.

## 7. Standar isi artikel

Sebelum publish, agent dan Damar memeriksa:

- [ ] Berita masih aktual.
- [ ] Sumber asli dapat dibuka.
- [ ] Untuk regulation, visa, tax, company, dan property, sumber primer sudah diperiksa bila tersedia.
- [ ] Title tidak menjanjikan lebih dari bukti.
- [ ] Artikel tidak menduplikasi artikel lama dengan wording berbeda.
- [ ] Category benar.
- [ ] Pembuka langsung menjelaskan apa yang terjadi.
- [ ] Date, amount, threshold, institution, dan regulation code tepat.
- [ ] Fakta, interpretasi, dan Bali Zero take tidak tercampur.
- [ ] Ada konsekuensi atau next step yang berguna.
- [ ] Tidak ada bahasa AI generik.
- [ ] Tidak ada janji yang tidak terbukti.
- [ ] Tidak ada data client atau PII.

## 8. Cover artikel website

Cover artikel dibuat dengan **ImageGen native milik agent**, bukan Flow. Flow hanya digunakan untuk video.

Untuk setiap artikel terpilih, agent memberi **satu arah cover yang direkomendasikan**. Alternatif kedua hanya diberikan bila ada ambiguitas editorial yang nyata. Setelah Damar memilih, agent membuat cover final dengan ImageGen.

### Spesifikasi

- minimum 1200 × 675 px atau ukuran crop yang ditetapkan surface website;
- JPG atau WebP yang dioptimalkan;
- tanpa headline, caption, logo, watermark, atau teks generatif di dalam foto;
- subject utama tetap terbaca pada card kecil;
- alt text menjelaskan gambar secara natural;
- satu artikel, satu cover yang memang dibuat atau dipilih untuk artikel itu.

### Cover otomatis ditolak bila

- placeholder atau fallback lama;
- dipakai ulang dari topik lain;
- sekadar skyline, server room, laptop, handshake, atau office stock;
- metafora tidak dapat dipahami tanpa penjelasan;
- salah subject, tempat, era, atau konteks;
- wajah, tangan, object, insignia, atau teks cacat;
- cantik tetapi tidak menjelaskan cerita;
- file publik berbeda dari cover yang disetujui.

## 9. SEO artikel

Agent harus mengerjakan dan memeriksa, bukan hanya menerima metadata otomatis:

- [ ] slug singkat dan terbaca;
- [ ] SEO title idealnya tidak lebih dari 60 karakter;
- [ ] SEO description idealnya tidak lebih dari 155 karakter;
- [ ] excerpt tidak terpotong dan menjawab inti cerita;
- [ ] canonical URL benar;
- [ ] Open Graph image adalah cover yang disetujui;
- [ ] Twitter/social card benar;
- [ ] image alt text natural dan spesifik;
- [ ] category URL benar;
- [ ] tags relevan dan tidak stuffing;
- [ ] publication date dan author/source benar;
- [ ] tidak ada prompt, internal reasoning, atau label sistem yang bocor;
- [ ] preview search dapat dibaca manusia.

## 10. Dua mode publikasi artikel

### Mode sekarang — sampai Bridge lengkap aktif di production

Agent dapat membaca, menilai, menyusun paket, dan membuat cover. Damar kemudian memakai News Room di:

`https://kita.balizero.com/intelligence/news-room`

untuk:

1. edit content bila diperlukan;
2. upload cover;
3. memilih posisi;
4. menekan publish;
5. memulai pemeriksaan live bersama agent.

### Mode target — setelah Bridge lengkap aktif

Alur yang diinginkan adalah:

1. Damar memilih artikel dan posisi;
2. agent menyiapkan preview lengkap;
3. Damar memberi konfirmasi final;
4. agent meng-update artikel dan SEO;
5. agent melampirkan cover ImageGen yang disetujui;
6. agent menerbitkan satu kali dan mencegah publikasi ganda;
7. agent memantau proses publikasi secara internal;
8. agent memeriksa halaman live dan posisi homepage;
9. agent baru mengatakan **“published and verified live”** setelah semua check lulus.

Agent tidak boleh mengklaim artikel live hanya karena tombol publish atau API call berhasil.

## 11. Verifikasi live artikel

- [ ] proses publikasi internal selesai;
- [ ] versi website terbaru sudah tersedia;
- [ ] final URL memberikan HTTP 200 setelah redirect;
- [ ] title dan body lengkap;
- [ ] source link ada;
- [ ] cover memberikan HTTP 200;
- [ ] cover yang terlihat adalah cover yang disetujui;
- [ ] canonical benar;
- [ ] SEO title dan description ada;
- [ ] OG image benar;
- [ ] artikel muncul di `/news`;
- [ ] bila dipilih Hero, artikel terlihat pada slot yang tepat;
- [ ] desktop dan mobile preview baik;
- [ ] tidak ada card atau image 404.

---

# BAGIAN II — CAROUSEL HARIAN

## 12. Memulai pemilihan topik

Sesudah pekerjaan artikel, Damar mengirim:

> **Siapkan shortlist editorial hari ini untuk carousel Bali Zero. Cari topik Bali/Indonesia yang baru atau memiliki perkembangan baru dalam immigration, company, tax, property, compliance, hospitality, dan business. Gunakan News Room, sumber resmi, media tepercaya, Google Trends Indonesia, TikTok Creative Center, signal social, dan arsip carousel Bali Zero. Social trend hanya signal, bukan bukti. Berikan maksimum lima kandidat dan urutkan berdasarkan potensi. Untuk setiap kandidat pisahkan FACT, INFERENCE, IDEA, dan UNKNOWN; jelaskan audiens, why now, consequence, novelty, saturation, source, save/share potential, video potential, dan risiko.**

Agent tidak boleh sekadar mencari topik yang ramai. Topik harus berada pada pertemuan empat hal:

1. **benar dan dapat dibuktikan;**
2. **penting bagi audiens Bali Zero;**
3. **tepat waktu dan belum terlalu jenuh;**
4. **dapat menjadi cerita visual yang jelas.**

## 13. Sumber yang harus dipakai agent

Agent menggunakan kekuatan yang tersedia secara berurutan:

1. News Room dan source article lengkap;
2. sumber resmi Indonesia dan primary documents;
3. NotebookLM/domain ground truth yang sesuai untuk verifikasi regulation; bila tidak tersedia untuk topik regulasi, topik tidak boleh diterbitkan hari itu;
4. web search lokal Bali/Indonesia;
5. Google Trends Indonesia — 4 jam dan 24 jam;
6. TikTok Creative Center — trends dan top creative patterns;
7. media nasional/lokal tepercaya;
8. signal Reddit, Threads, Instagram, TikTok, dan percakapan publik;
9. arsip carousel Bali Zero dan metrics untuk mendeteksi duplikasi serta format yang bekerja.

Google Trends dan social media menjawab **“orang sedang memperhatikan apa?”** Mereka tidak menjawab **“fakta ini benar atau tidak?”** Fakta tetap harus datang dari sumber yang layak.

Jika sebuah signal atau tool tidak dapat diakses, agent menulis `UNAVAILABLE`. Agent tidak boleh menebak trend atau mengubah banyaknya liputan media menjadi bukti trend.

## 14. Hard gate topik

Topic tidak boleh masuk shortlist bila gagal salah satu dari ini:

- tidak ada sumber langsung yang dapat digunakan;
- tidak ada fakta atau perkembangan baru;
- proposal, appeal, statement, atau rumor dipresentasikan sebagai keputusan final;
- audiens Bali Zero tidak dapat disebut dengan tepat;
- sudah pernah dipakai tanpa angle baru;
- tidak ada consequence, risk, decision, atau action;
- hanya menarik tetapi tidak berguna;
- visual hanya mungkin berupa gambar abstrak atau stock generik;
- `UNKNOWN` mengubah inti cerita dan belum terselesaikan.

Untuk klaim hukum, regulation, visa, tax, company, property, deadline, biaya, threshold, atau angka penting, **verifier yang berbeda dari writer** melakukan pemeriksaan kedua terhadap setiap klaim load-bearing, sumber primer, regulation code/date yang tepat, dan NotebookLM/domain ground truth yang sesuai. Hasilnya harus terlihat sebagai `LEGAL CHECK: PASS` atau `LEGAL CHECK: BLOCK`. Konflik atau sumber yang tidak tersedia menghasilkan `BLOCK`, bukan `PASS WITH ASSUMPTION`. `BLOCK` tidak boleh masuk content lock.

Jika tidak ada trend yang melewati hard gate, gunakan **evergreen reserve** yang sudah diverifikasi dan beri hook aktual yang jujur. Jangan menciptakan urgensi palsu hanya demi memenuhi kalender harian.

## 15. Kartu kandidat dan scoring

Setiap kandidat harus memiliki:

- provisional title;
- thesis satu kalimat;
- audiens;
- why now;
- what changed;
- concrete consequence;
- `FACT`;
- `INFERENCE`;
- `IDEA` editorial;
- `UNKNOWN`;
- direct sources dengan link dan tanggal;
- trend signals;
- saturation;
- similar Bali Zero content;
- cover headline;
- cover scene;
- legal/editorial risk;
- score.

### Rubrik 100 poin

| Kriteria                      | Poin | Pertanyaan                                           |
| ----------------------------- | ---: | ---------------------------------------------------- |
| Relevansi audiens Bali Zero   |   20 | Kepada siapa ini mengubah sesuatu?                   |
| Consequence dan actionability |   20 | Keputusan atau risiko apa yang menjadi lebih jelas?  |
| Why now dan momentum          |   15 | Mengapa harus terbit hari ini?                       |
| Freshness                     |   15 | Apa fakta atau perkembangan yang benar-benar baru?   |
| Editorial novelty             |   10 | Apakah angle masih segar dan tidak jenuh?            |
| Save/share potential          |   10 | Apakah orang akan menyimpan atau mengirimkannya?     |
| Visual dan video potential    |   10 | Apakah dapat diceritakan dengan scene yang spesifik? |

- **85–100:** kandidat utama;
- **75–84:** alternatif kuat;
- **65–74:** angle perlu dikembangkan;
- **di bawah 65:** tidak dipakai hari ini;
- **hard gate gagal:** parkir, berapa pun score-nya.

Agent memberikan tiga kandidat terkuat. **Damar memilih pemenang.** Score membantu keputusan; score tidak menggantikan Damar.

## 16. Content lock

Sebelum membuat slide, Damar dan agent menyelesaikan kalimat:

> **Carousel ini harus membuat [AUDIENS] memahami bahwa [FACT/CHANGE], karena [CONSEQUENCE], sehingga sekarang mereka harus [ACTION].**

Content dianggap terkunci bila sudah ada:

- audiens;
- tesis;
- fakta dan angka;
- daftar sumber dan klaim;
- angle;
- urutan cerita;
- final takeaway;
- CTA;
- daftar `UNKNOWN` kosong atau tidak memengaruhi substansi.

Bahasa publik default carousel adalah **English**, dengan istilah resmi Bahasa Indonesia dipertahankan dan diberi penjelasan English pada kemunculan pertama bila diperlukan. Jangan mencampur bahasa secara acak di dalam satu slide.

Setelah content lock, video dapat langsung dimulai. Tidak perlu menunggu semua layout Canva selesai.

## 17. Tiga route cover

Agent harus memberikan **tiga route cover lengkap**, bukan tiga judul acak. Masing-masing berisi:

- headline;
- subheadline;
- empirical anchor;
- core visual thesis;
- satu scene yang koheren;
- subject utama;
- setting;
- light dan composition;
- alasan dapat dipahami dalam satu sampai lima detik;
- ambiguity risk.

Damar memilih satu route. Elemen dari dua route hanya boleh digabung bila pesan tetap tunggal dan jelas.

## 18. Seni cover: metode yang harus dipakai

Metode ini mengikuti arahan editorial Antonello untuk “Trend News in Bali” dan prinsip yang berhasil pada percakapan image direction yang sudah diperiksa: cover harus langsung dipahami, memiliki satu visual thesis, dan tidak memakai placeholder.

1. **Core visual thesis** — tulis satu kalimat yang menjelaskan konflik atau fakta visual.
2. **One coherent location** — satu dunia, bukan collage yang malas.
3. **Visual hierarchy** — siapa/apa yang dilihat pertama, kedua, ketiga.
4. **Human consequence** — bila relevan, tunjukkan dampak pada manusia, bukan hanya simbol hukum.
5. **One strong symbol** — hanya jika dapat dibaca tanpa penjelasan panjang.
6. **Empirical anchor** — number, date, place, rule code, verdict, atau contrast yang konkret.
7. **Copy-safe composition** — ruang nyata untuk headline dan logo.
8. **Factual boundaries** — visual tidak boleh mengubah proposal menjadi law atau simbol menjadi real case.
9. **Negative prompt** — larang kesalahan yang benar-benar mungkin, bukan daftar dekoratif tanpa akhir.
10. **Thumbnail proof** — final decision dibuat pada ukuran layar ponsel, bukan hanya pada canvas besar.

Agent boleh menulis prompt ImageGen yang detail di belakang layar. Damar harus menerima **Direction Card yang singkat dan dapat diputuskan**, bukan dipaksa membaca prompt ribuan kata.

### Contoh route yang diterima

**Headline:** `BALI VILLAS FACE A NEW CHECK`  
**Anchor:** tanggal pemeriksaan atau nama keputusan yang benar-benar ada di sumber  
**Scene:** satu villa nyata dilihat dari gerbang saat petugas memeriksa satu dokumen; ruang headline jelas; tidak ada collage  
**Mengapa bekerja:** viewer langsung memahami tempat, tindakan, dan konsekuensi. Visual tidak mengklaim penutupan bila sumber hanya menyebut pemeriksaan.

### Contoh route yang ditolak karena samar

**Headline:** `THE DOOR IS CLOSING`  
**Scene:** siluet memegang kunci di depan matahari terbenam  
**Mengapa gagal:** tidak menjelaskan pintu apa, siapa yang terdampak, fakta baru apa, atau mengapa terjadi sekarang. Gambar dapat dipakai untuk puluhan topik dan bukan bukti pemahaman.

### Test satu detik

Dalam satu detik, viewer harus dapat mengenali subject atau conflict utama.

### Test lima detik

Setelah lima detik, orang yang tidak mengikuti riset harus dapat menjawab:

- apa yang terjadi;
- di mana atau kapan;
- mengapa hal itu penting.

Jika jawabannya hanya “kelihatan menarik”, cover masih terlalu cryptic.

### Headline

- target aman sampai sekitar 37 karakter untuk tiga baris;
- target bersih sampai sekitar 25 karakter untuk dua baris;
- gunakan lima atau enam kata bila memungkinkan;
- jangan mengecilkan font sampai tidak terbaca demi mempertahankan kalimat panjang;
- selalu cek grid thumbnail di ponsel.

### Cover harus memiliki minimal satu anchor

- number;
- date;
- regulation code;
- place;
- categorical verdict;
- editorial contrast;
- time-specific event.

### Gambar yang disukai

- documentary atau cinematic event photo;
- provocation photo yang konkret;
- location yang benar-benar terkait;
- subject yang spesifik;
- action atau consequence yang terlihat;
- 35mm atmosphere, chiaroscuro, dan Bali Zero palette yang terkendali.

### Gambar yang ditolak

- placeholder apa pun;
- beach, palm, sunset, dan boho lifestyle yang tidak relevan;
- skyline generik;
- document pile generik;
- laptop dissolving, server room, atau futuristic HUD;
- handshake dan smiling corporate team;
- wax seal, parchment, flat icon, clipart;
- surreal metaphor yang memerlukan penjelasan;
- split screen atau collage tanpa alasan editorial;
- wajah, tangan, text, flag, uniform, atau insignia yang salah;
- image yang indah tetapi tidak mendukung headline.

Cover dan hero image carousel dibuat dengan **ImageGen native agent**, bukan Flow.

## 19. Struktur carousel

Default adalah **8 slide**. Gunakan 7–10 hanya bila cerita benar-benar memerlukannya.

1. **Cover** — fact/verdict, empirical anchor, dan image yang spesifik.
2. **Why it matters** — siapa yang terkena dan mengapa harus terus membaca.
3. **What changed** — sebelum/sekarang atau fakta/persepsi.
4. **How it works** — mechanism, process, rule, atau number example.
5. **Concrete consequence** — cost, risk, obligation, block, deadline, atau decision.
6. **The trap** — exception, threshold, ambiguity, atau hal yang sering tidak terlihat.
7. **What to do** — checklist atau decision path.
8. **Evidence/summary** — hanya bila membantu keputusan.
9. **Statement-bomb close** — kuat, jelas, dan tidak mengubah opini menjadi fakta.

Jangan memanjangkan berita sederhana menjadi sepuluh slide hanya karena template tersedia.

## 20. Aturan copy setiap slide

- satu slide, satu fungsi;
- body biasanya 25–50 kata;
- bila seluruhnya uppercase, maksimum sekitar 35 kata;
- bila heading menjanjikan “3 rules”, body wajib memberikan tepat tiga item yang terpisah;
- angka, tanggal, threshold, rate, dan regulation code harus konkret;
- slide informasi idealnya memiliki rule/fact, consequence, lalu action/implication;
- slide 2 selalu menjawab “why it matters”;
- tidak ada emoji;
- tidak ada corporate disclaimer sebagai pengisi;
- Bahasa Indonesia terms dan official acronyms dipertahankan bila diperlukan;
- daftar sumber mengikuti setiap klaim load-bearing;
- background gelap harus tetap memiliki atmosphere, grain, gradient, photo, atau structure — bukan hitam kosong seperti placeholder;
- gunakan maksimal lima layout family dan jangan ganti style tanpa alasan.

## 21. Hero image carousel

- cover selalu memiliki hero;
- target 4–6 hero yang relevan dalam carousel;
- setiap hero dibuat/dipilih untuk fungsi slide itu;
- style anchor adalah referensi, bukan final image yang boleh dipakai ulang;
- tidak ada silent reuse;
- hero antar-slide tidak boleh identik;
- agent dan Damar melihat semua image, bukan hanya memeriksa nama file.

## 22. Canva

Agent menyiapkan:

- slide copy;
- hierarchy;
- layout recommendation;
- image assets;
- citation/source note;
- visual do/don't;
- caption dan alt text.

Damar bebas menyelesaikan layout di Canva. Saat mengedit, Damar tidak boleh mengubah klaim, nominal, tanggal, regulation code, atau caveat tanpa meminta agent memeriksa ulang.

## 23. Caption

Caption tidak mengulang slide secara mekanis.

Struktur:

1. sekitar 125 karakter pertama: searchable keyword + perkembangan baru;
2. paragraph 1: fakta dan konteks;
3. paragraf 2: implication untuk audiens;
4. paragraph 3: action, caveat, atau distinction yang menentukan;
5. source/regulation/date penting;
6. CTA editorial: save atau share kepada orang yang terdampak;
7. CTA bisnis hanya bila relevan;
8. sekitar lima hashtag yang benar-benar spesifik;
9. alt text untuk setiap slide.

Caveat penting harus tetap sama dari source ke brief, dari brief ke slide, dan dari slide ke caption.

## 24. Paket carousel pukul 15:00

Agent menyusun satu folder/link yang berisi seluruh paket di bawah ini. Damar tidak merakit atau mengirim sebelas attachment satu per satu; Damar hanya mengirim link paket dan pesan ringkas pada Bagian IV.

- Canva editable link;
- PNG final 1080 × 1350;
- PDF atau contact sheet;
- final cover;
- caption final;
- hashtags;
- alt text per slide;
- lembar `FACT / INFERENCE / IDEA / UNKNOWN`;
- sources dengan URL dan tanggal;
- QA checklist;
- issue terbuka, yang idealnya kosong;
- pada hari video, paket video pada Bagian III.

### QA carousel

#### Topic

- [ ] Fakta atau development cukup fresh.
- [ ] Angle benar-benar baru.
- [ ] Audience jelas.
- [ ] Consequence konkret.
- [ ] Setiap klaim penting memiliki sumber.

#### Cover

- [ ] Dapat dipahami dalam satu hingga lima detik.
- [ ] Terbaca sebagai thumbnail.
- [ ] Memiliki empirical anchor.
- [ ] Image dan headline menceritakan hal yang sama.
- [ ] Image baru, bukan placeholder.
- [ ] Tidak ada defect AI.

#### Slide

- [ ] 7–10 slide.
- [ ] Setiap slide memiliki satu fungsi.
- [ ] Slide 2 menjelaskan why it matters.
- [ ] Setiap numbered promise dipenuhi.
- [ ] Visual gelap tetap memiliki atmosphere.
- [ ] Hero benar-benar relevan.
- [ ] Closing kuat tetapi jujur terhadap tingkat kepastian.
- [ ] Copy, angka, dan sumber sudah dibaca ulang.

#### Packaging

- [ ] Caption memperluas cerita.
- [ ] Caveat tidak hilang.
- [ ] Hashtag tidak stuffing.
- [ ] Alt text ada.
- [ ] Canva, export, caption, dan daftar sumber adalah versi yang sama.

---

# BAGIAN III — VIDEO ZANTARA, MINIMAL TIGA KALI SEMINGGU

## 25. Damar adalah sutradara

Untuk video, agent adalah researcher, script editor, prompt writer, producer, dan QA partner. **Damar memilih setting, outfit, lighting, blocking, camera movement, dan performance mood.**

Agent hanya boleh memblokir pilihan Damar bila ada:

- factual error;
- identity drift risk;
- technical impossibility;
- strong visual cliché;
- poor readability;
- safety atau platform problem.

## 26. Kapan video dimulai

Video dimulai segera setelah content lock carousel:

- fakta sudah benar;
- angka sudah benar;
- narrative order sudah benar;
- final takeaway dan CTA sudah jelas.

Jangan menunggu seluruh desain Canva selesai.

## 27. Director Card A/B/C

Agent memberikan tiga pilihan ringkas:

| Elemen           | Route A | Route B | Route C |
| ---------------- | ------- | ------- | ------- |
| Setting          |         |         |         |
| Outfit/reference |         |         |         |
| Light/grade      |         |         |         |
| Camera rhythm    |         |         |         |
| Performance mood |         |         |         |
| Mengapa cocok    |         |         |         |
| Risiko           |         |         |         |

Damar memilih satu.

### Outfit

Damar bebas menentukan outfit Zantara. Jika outfit tersebut belum tersedia sebagai Character/reference yang disetujui, agent terlebih dahulu menyiapkan reference yang benar. Jangan mengandalkan prompt teks saja untuk mengganti pakaian Character. Gunakan satu outfit utama dan satu lokasi dominan per episode; lokasi kedua hanya bila benar-benar membantu cerita.

## 28. Format video Damar Direct

`Damar Direct` adalah mode editorial manual di Flow UI untuk tim Damar, bukan contract pipeline WR3 otomatis. Jangan mengirim output 35–42 detik ini ke validator WR3 yang memiliki duration contract berbeda tanpa perubahan contract yang disetujui owner.

Default — bukan kewajiban bila cerita yang lebih sederhana akan lebih kuat:

- vertical 9:16;
- 5 scene dan total 35–42 detik;
- gunakan 6 scene dan 42–48 detik hanya bila fakta cerita memang memerlukannya;
- Zantara hadir pada 4–6 scene;
- maksimum 1–2 evidence/B-roll insert bila diperlukan;
- satu lokasi dominan;
- satu visual language;
- satu music bed di post bila diperlukan.

### Narrative map

1. clear hook;
2. what happened;
3. why it matters;
4. mechanism, number, atau decisive fact;
5. practical implication;
6. authoritative close dan CTA.

### Satu clip harus sederhana

- satu subject;
- satu camera move;
- satu action;
- satu spoken line;
- maksimum sekitar lima detik dialog;
- sekitar 12–15 kata untuk English;
- Bahasa Indonesia harus dibaca keras untuk memastikan durasi.

## 29. Dua versi bahasa

Jangan dub English clip ke Bahasa Indonesia. Voice harus tetap native dari Flow.

### TikTok

- Zantara berbicara dalam Bahasa Indonesia;
- subtitle English berupa terjemahan yang sudah diperiksa, bukan transkrip Bahasa Indonesia;
- caption Bahasa Indonesia.

### Instagram, Threads, Facebook, WhatsApp Channel, dan WhatsApp Story

- Zantara berbicara dalam English;
- subtitle English;
- caption English yang disesuaikan per platform bila perlu.

Kedua master memiliki:

- scene order yang sama;
- fact dan conclusion yang sama;
- duration yang setara;
- overlay, grade, transition, dan music yang sama;
- creative intention yang sama.

Performance dibuat terpisah. Micro-expression dan gerakan tidak akan frame-identical. “Video yang sama” berarti konsep dan direction yang sama, bukan pixel yang sama.

## 30. Flow: cara paling sederhana

Gunakan saved **Character Zantara** di Flow dan voice yang dihasilkan langsung oleh Flow. Tidak ada external TTS.

### Preflight

- [ ] Flow login dan health baik.
- [ ] Character Zantara dipilih.
- [ ] Outfit/reference disetujui Damar.
- [ ] Portrait 9:16.
- [ ] Fact dan script sudah locked.
- [ ] Tidak ada PII.
- [ ] Agent sudah memisahkan EN dan ID script.
- [ ] Generation cap hari itu sudah ditetapkan.

### Pilot dulu

Generate scene yang sama dua kali:

1. pilot English;
2. pilot Bahasa Indonesia.

Lanjutkan hanya bila kedua pilot lulus:

- identity;
- outfit;
- voice;
- pronunciation;
- lipsync;
- framing;
- no black bars.

### Lean batch

- Mode normal: 10 baseline generation = 5 scene × 2 bahasa.
- Pilot EN dan ID adalah Scene 1 final dan **sudah termasuk** dalam baseline.
- Setelah kedua pilot lulus, generate 8 clip baseline yang tersisa.
- Second option hanya untuk hook atau close: maksimum 2 generation.
- Retry hanya untuk clip yang gagal: maksimum 2 generation.
- **Cap normal: 14 generation, termasuk pilot.**
- Extended mode 6 scene boleh mencapai hard cap 20 hanya bila Damar menyetujuinya sebelum generation dimulai.
- jangan regenerate seluruh video karena satu scene rusak;
- download setiap take yang lolos segera.

Cap ini berlaku untuk produksi manual di Flow UI. Workspace Bridge saat ini tidak menyediakan jalur Character Zantara end-to-end untuk seluruh batch tersebut.

Setelah dua retry yang sudah disederhanakan tetap gagal pada clip yang sama, berhenti. Tandai `VIDEO DEFERRED — NOT COUNTED`, update weekly tracker, dan pindahkan slot ke hari kerja berikutnya. Kirim carousel tepat waktu tanpa video. Video yang gagal QA tidak dihitung sebagai salah satu dari tiga video mingguan. Jangan pernah mengirim versi “paling tidak buruk”.

## 31. Template prompt Flow per clip

```text
Use the saved Flow Character Zantara and the approved [OUTFIT] Character/reference.

Vertical 9:16, [SHOT SIZE], [LENS], [ONE CAMERA MOVE].
Zantara is alone in [SETTING], [LIGHTING]. She [ONE ACTION].

She says in [English / natural Bahasa Indonesia], exactly:
“[LINE THAT FITS WITHIN FIVE SECONDS].”

After speaking, she remains composed with no further dialogue for 0.75 seconds.

Dialogue and [ROOM TONE OR AMBIENCE] only. Music: none.

Blank surfaces; no subtitles, captions, labels, numbers, readable text,
generated logo, official insignia, extra person, duplicate or reflection.
```

Jangan menambahkan:

- banyak action dalam satu clip;
- lebih dari satu camera movement;
- beberapa location;
- prompt negatif yang sangat panjang;
- text, number, atau graph yang harus dibuat Flow;
- external voice instruction.

Flow tidak dapat dipercaya untuk merender text, number, code, table, atau official insignia. Semua itu ditambahkan di post.

## 32. Audio dan post-production

Flow menghasilkan:

- spoken dialogue;
- natural ambience;
- `Music: none`.

Jangan mengganti voice dengan TTS eksternal. Bila memakai music, tambahkan satu bed original atau licensed di post, bukan enam musik berbeda dari enam clip.

### Subtitle

- selalu English;
- Montserrat;
- maksimum dua baris;
- idealnya sekitar 32 karakter per baris;
- sekitar 17 karakter per detik atau kurang;
- dibagi menurut makna dan napas;
- number, regulation code, atau unit tidak boleh terpisah;
- tidak menutupi wajah, logo, atau platform UI.

Logo, number, code, chart, source badge, dan CTA ditambahkan di post.

## 33. Timeline hari video

| Waktu     | Pekerjaan                                                                                                                      |
| --------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 09:45     | Content lock carousel.                                                                                                         |
| 10:00     | Director Card A/B/C.                                                                                                           |
| 10:15     | Script EN dan ID.                                                                                                              |
| 10:30     | Flow/Character/reference preflight.                                                                                            |
| 10:45     | Pilot EN dan ID.                                                                                                               |
| 11:15     | Bila pilot lulus, mulai batch. Bila belum lulus, lakukan satu penyederhanaan; jika tetap gagal, hentikan jalur video hari itu. |
| 12:30     | Select dan download takes.                                                                                                     |
| 13:00     | Assembly dan subtitle. Jika batch belum selesai, lindungi carousel lebih dahulu.                                               |
| 14:00     | Full QA.                                                                                                                       |
| 14:15     | Jika video belum siap QA, tandai DEFERRED dan kirim carousel tepat waktu.                                                      |
| 14:40     | Export, poster, caption, dan packaging.                                                                                        |
| **15:00** | Penyerahan ke Antonello.                                                                                                       |
| **17:00** | Publikasi hanya setelah approval.                                                                                              |

## 34. QA video

### Facts

- [ ] Setiap number, code, dan claim sama dengan source ledger carousel.
- [ ] Tidak ada line yang dibuat-buat.

### Identity dan direction

- [ ] Zantara yang sama pada semua scene.
- [ ] Face, age, hair, skin tone, dan body konsisten.
- [ ] Tidak ada duplicate, reflection, atau identity asing.
- [ ] Outfit dan setting sesuai keputusan Damar.
- [ ] Direction terasa intentional, bukan corporate stock.

### Speech dan audio

- [ ] Bahasa benar.
- [ ] Line diucapkan tepat.
- [ ] Tidak ada kata tambahan seperti “pal”, “mate”, atau “guys”.
- [ ] Bahasa Indonesia diperiksa oleh native speaker.
- [ ] Native audio ada di file.
- [ ] Lipsync benar.
- [ ] Tidak ada clipping, warble, click, atau phoneme terpotong.
- [ ] Jelas melalui headphone dan speaker ponsel.

### Visual dan subtitles

- [ ] Face, hand, dan movement normal pada 1× dan 0.5×.
- [ ] Tidak ada generated text di scene.
- [ ] Tidak ada black bars.
- [ ] Subtitle tepat dan sinkron.
- [ ] Tidak menabrak face/logo/platform UI.

### Master

- [ ] 1080 × 1920 atau upscale yang dikontrol.
- [ ] H.264 video dan AAC audio.
- [ ] Loudness sekitar -14 LUFS.
- [ ] Tidak ada black frame.
- [ ] Dua master memiliki scene map dan duration yang setara.
- [ ] Disclosure/label AI-generated sudah disiapkan sesuai platform.

## 35. Paket video pukul 15:00

- `master_tiktok_id.mp4`;
- `master_social_en.mp4`;
- `poster.jpg`;
- `tiktok_id_to_en.srt` untuk terjemahan TikTok;
- `social_en_transcript.srt` untuk master English;
- caption Bahasa Indonesia;
- caption English;
- source dan claim ledger;
- Director Card;
- prompt/take log;
- disclosure/label AI-generated untuk setiap platform;
- issue terbuka, yang idealnya kosong.

### Disclosure AI wajib

Zantara adalah karakter sintetis dengan video dan voice yang dibuat oleh AI. Karena hasilnya realistis, sebelum publish:

- TikTok: aktifkan pengaturan `AI-generated content` pada layar posting;
- Instagram, Threads, dan Facebook: lakukan self-disclosure `AI info` atau label setara pada composer bila tersedia dan pertahankan metadata/content credentials;
- caption tidak boleh membuat viewer percaya bahwa footage menunjukkan peristiwa dokumenter nyata;
- Character, voice, outfit reference, music, dan footage harus memiliki hak penggunaan yang tercatat;
- periksa kembali bahwa disclosure terlihat setelah post live.

Kebijakan platform dapat berubah. Agent memeriksa halaman kebijakan resmi pada hari publish bila UI atau persyaratan berubah.

Referensi kebijakan: [TikTok — Konten yang dihasilkan AI](https://support.tiktok.com/id/using-tiktok/creating-videos/ai-generated-content) dan [Meta — AI-generated content labeling](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/).

### Tracker tiga video mingguan

| Slot | Planned | Delivered | Deferred | Replacement date |
| ---- | ------- | --------- | -------- | ---------------- |
| 1    |         |           |          |                  |
| 2    |         |           |          |                  |
| 3    |         |           |          |                  |

---

# BAGIAN IV — APPROVAL, PUBLIKASI, DAN BELAJAR

## 36. Handoff pukul 15:00

Agent membuat folder kanonik untuk hari itu dengan format `YYYY-MM-DD_topic-slug/`, menaruh semua file final di dalamnya, dan memberi nomor versi. Damar mengirim satu link dan satu pesan ringkas:

> **DAILY EDITORIAL PACKAGE — [TANGGAL]**  
> **Carousel topic:** [judul]  
> **Mengapa dipilih:** [satu kalimat]  
> **Audience:** [audience]  
> **Canva:** [link]  
> **Final export:** [link/folder]  
> **Caption:** [link/text]  
> **Sources/claim sheet:** [link]  
> **Video:** [EN link] / [ID link] / N/A  
> **Open issue:** none / [jelaskan]  
> **Requested action:** APPROVE / REVISE / REJECT

Jangan mengirim draft melalui banyak chat tanpa satu paket final.

Contoh yang sudah diisi:

> **DAILY EDITORIAL PACKAGE — 27 AUG 2026**  
> **Carousel topic:** What Bali Villa Owners Must Verify Now  
> **Mengapa dipilih:** ada perkembangan resmi baru, konsekuensinya konkret, dan audiens dapat mengambil tindakan hari ini  
> **Audiens:** villa owners dan hospitality operators  
> **Canva:** [satu link editable]  
> **Final export:** [satu folder versi v03]  
> **Caption:** `caption_v03.txt`  
> **Sources/claim sheet:** `sources_v03.md` — LEGAL CHECK PASS  
> **Video:** `master_social_en_v02.mp4` / `master_tiktok_id_v02.mp4`  
> **Open issue:** none  
> **Requested action:** APPROVE CAROUSEL / APPROVE VIDEO EN / APPROVE VIDEO ID

Setelah approval, file menjadi immutable. Perubahan apa pun membuat versi baru dan memerlukan approval baru.

## 37. Revisi setelah 15:00

1. baca revisi secara penuh;
2. ubah hanya bagian yang diminta;
3. bila claim, number, atau headline berubah, agent mengulang fact check;
4. bila cover berubah, ulangi one-second, five-second, dan thumbnail test;
5. pastikan Canva, export, caption, subtitles, dan source ledger memiliki versi yang sama;
6. kirim versi revisi dengan label yang jelas.

## 38. Publikasi pukul 17:00

**Publikasi social selalu dilakukan manual oleh Damar. Agent tidak pernah menekan publish untuk Instagram, TikTok, Threads, Facebook, WhatsApp Channel, atau WhatsApp Story.**

Approval berlaku per deliverable: `CAROUSEL`, `VIDEO ID`, dan `VIDEO EN`. Tidak ada jawaban bukan approval. Bila sebuah deliverable belum menerima `APPROVE` eksplisit pada pukul 17:00, statusnya `WAITING APPROVAL` dan tidak diterbitkan. Bila revisi datang terlalu dekat dengan pukul 17:00 untuk menjalankan QA penuh, publikasi dijadwalkan ulang.

Sebelum publish:

- [ ] final file sama dengan file yang disetujui;
- [ ] caption sama dengan caption yang disetujui;
- [ ] platform dan bahasa benar;
- [ ] cover/poster benar;
- [ ] subtitles aktif dan tidak terpotong;
- [ ] TikTok `AI-generated content` aktif untuk video Zantara;
- [ ] Meta/Threads `AI info` atau disclosure setara aktif untuk video Zantara;
- [ ] tidak ada draft lama terpilih;
- [ ] link final dicatat.

Dalam sepuluh menit setelah publish, Damar dan agent memeriksa post live:

- [ ] account benar;
- [ ] cover frame/poster dan crop benar;
- [ ] caption lengkap dan bahasa benar;
- [ ] audio ada dan subtitle sinkron;
- [ ] disclosure AI terlihat;
- [ ] tidak ada kompresi, black frame, atau safe-zone collision yang merusak;
- [ ] URL dan screenshot proof disimpan di folder paket.

## 39. Belajar dari hasil

Ketika metrics tersedia, catat:

- reach;
- likes;
- saves;
- shares;
- follows;
- save/like;
- share/like;
- kekuatan cover pada detik pertama;
- drop-off video per adegan;
- perbedaan retention versi ID dan EN;
- perubahan yang dibuat Damar atau Antonello sebelum publish.

Pertanyaan evaluasi utama:

> **Apakah follower akan mengirim konten ini kepada accountant, business partner, lawyer, colleague, atau teman yang benar-benar terdampak?**

Metrics membantu Damar melihat pola. Metrics tidak boleh memilih topic secara otomatis dari sample kecil.

---

# BAGIAN V — KONTRAK KERJA AGENT

## 40. Cara agent harus bekerja

Untuk setiap pekerjaan editorial, agent wajib:

1. mencari source, bukan mengandalkan memory;
2. membaca isi, bukan hanya headline;
3. memisahkan `FACT`, `INFERENCE`, `IDEA`, dan `UNKNOWN`;
4. memberikan maksimum lima pilihan yang sudah disaring;
5. menjelaskan alasan, risiko, dan trade-off;
6. memberi rekomendasi tetapi menyerahkan keputusan kreatif kepada Damar;
7. menggunakan ImageGen native untuk still image;
8. menggunakan Flow hanya untuk video;
9. tidak memakai placeholder atau silent fallback;
10. tidak menyebut sesuatu live sebelum memeriksa live state;
11. tidak pernah memicu publikasi social; Damar menerbitkan manual hanya setelah approval Antonello;
12. menyimpan output harian dalam satu paket yang mudah diperiksa.

## 41. Effort model yang disarankan

Untuk menjaga workflow sederhana:

- **Extra High:** morning article ranking, trend/topic research, fact conflict, carousel thesis, cover direction, dan video concept;
- **High:** slide writing, caption, SEO review, script bilingual, dan QA;
- **Medium:** formatting, alt text draft, file naming, checklist, dan mechanical packaging.

Jika agent workspace dikunci pada satu effort, pilih **Extra High**. Damar tidak perlu memikirkan pergantian model setiap langkah. Agent harus otomatis mengalokasikan perhatian lebih pada keputusan editorial dan lebih sedikit pada pekerjaan mekanis.

### Konfigurasi agent sekarang

- Nama agent live: `Nuzantara — Bali Zero Desk`.
- Model aktif di Agent Builder: **belum diverifikasi dalam panduan ini**.
- Effort aktif di Agent Builder: **belum diverifikasi dalam panduan ini**.
- Default yang disarankan untuk pekerjaan ini: **GPT-5.6 Sol, Extra High**.

Sebelum onboarding Damar, owner workspace memeriksa dan menyimpan konfigurasi tersebut satu kali di Agent Builder. Damar tidak perlu mengubah model atau effort sepanjang hari.

## 42. Status teknis yang harus dipahami

Panduan ini menjelaskan tujuan operasional lengkap, tetapi tidak boleh menyembunyikan kondisi sistem.

Agent Damar sudah tersedia untuk digunakan di workspace. Ini **tidak berarti** fungsi website publishing sudah live.

| Kemampuan                                 | Status        | Surface      | Operator hari ini                                          |
| ----------------------------------------- | ------------- | ------------ | ---------------------------------------------------------- |
| Membaca daftar artikel pending            | `LIVE`        | Damar agent  | Agent                                                      |
| Membaca detail artikel                    | `LIVE`        | Damar agent  | Agent                                                      |
| Menulis arah cover dengan ImageGen        | `LIVE`        | Damar agent  | Agent                                                      |
| Edit artikel dan SEO                      | `MANUAL ONLY` | News Room UI | Damar, dipandu agent                                       |
| Attach cover ImageGen                     | `MANUAL ONLY` | News Room UI | Damar                                                      |
| Memilih posisi homepage                   | `MANUAL ONLY` | News Room UI | Damar                                                      |
| Agent publish artikel                     | `NOT LIVE`    | Bridge       | Tidak ada                                                  |
| Agent live verification end-to-end        | `NOT BUILT`   | Bridge       | Agent melakukan browser check manual setelah Damar publish |
| Saved Character Zantara + native voice    | `MANUAL FLOW` | Flow UI      | Damar + agent guidance                                     |
| Character Zantara melalui workspace agent | `NOT BUILT`   | Bridge       | Tidak ada                                                  |

Sampai fungsi target dinyatakan `LIVE IN PRODUCTION` dan dibuktikan, Damar memakai UI News Room dan Flow. Agent tetap mempersiapkan dan memeriksa seluruh pekerjaan. PR, preview, atau tool yang masih diuji bukan bukti fungsi live.

### Target minimum Bridge berikutnya

- `newsroom_update_article`;
- `newsroom_attach_cover`;
- `newsroom_publish(position=...)`;
- post-deploy live verification;
- `flow_generate_zantara_character_video` dengan Character Zantara fixed, EN/ID, confirmation, call cap, dan automatic download.

Setelah target tersebut live, pengalaman Damar seharusnya tetap sama: memilih, mengarahkan, dan mengonfirmasi. Kompleksitas teknis tetap ditangani agent.

---

## 43. Indeks cepat

Gunakan **Kokpit Harian Damar** di awal dokumen untuk operasi sehari-hari. Bagian di bawah Kokpit adalah manual referensi saat agent atau Damar memerlukan aturan rinci.

### Mode sekarang — website

1. Agent memberi shortlist artikel.
2. Damar memilih artikel dan posisi.
3. Agent menyiapkan preview, SEO, cover, dan sumber.
4. Damar menerbitkan melalui News Room UI.
5. Agent memeriksa hasil live.

### Mode target — website, hanya setelah Bridge live

1. Agent memberi shortlist artikel.
2. Damar memilih dan memberi konfirmasi presisi per artikel.
3. Agent meng-update, memasang cover, menerbitkan, dan memverifikasi live.

### Carousel harian

1. Agent memberi maksimum lima kandidat, idealnya tiga yang kuat.
2. Damar memilih satu topik.
3. Independent Fact Gate harus `PASS`.
4. Content lock mengunci audiens, fakta, konsekuensi, tindakan, caveat, dan sumber.
5. Damar memilih route cover; agent membangun carousel; Damar menyelesaikan di Canva bila perlu.

### Tiga kali seminggu

1. mulai video setelah content lock;
2. pilih Director Card;
3. gunakan Character Zantara dan native Flow voice;
4. buat EN+sub EN dan ID+sub EN;
5. default lima adegan, 35–42 detik, cap normal 14 generasi; extended mode maksimal 20 hanya dengan persetujuan Damar;
6. subtitle, logo, number, dan chart di post;
7. QA identity, speech, audio, facts, dan export.

### Deadline

- **15:00:** carousel dan video diserahkan dalam satu paket;
- **17:00:** Damar publish manual hanya setelah approval eksplisit per deliverable; tanpa approval = `WAITING APPROVAL`.

### Kalimat yang harus diingat

> **Damar memutuskan. Agent menyelidiki, membangun, dan memeriksa. Antonello menyetujui.**

> **Tidak ada cover cryptic. Tidak ada placeholder. Tidak ada publish tanpa proof.**
