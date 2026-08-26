# Damar — Start Here

## Kokpit Harian Bali Zero

**Versi:** 1.0  
**Tanggal:** 27 Agustus 2026  
**Zona waktu:** WITA  
**Manual lengkap:** `damar-editorial-director-playbook-id.md`

---

## Peran Damar

Damar adalah **Editorial Director**. Untuk video, Damar adalah **sutradara**.

Damar memutuskan:

1. artikel mana yang terbit dan posisinya di website;
2. topik carousel harian;
3. headline dan arah visual cover;
4. setting, outfit, lighting, camera, dan performance Zantara;
5. apakah paket final layak dikirim ke Antonello.

Agent melakukan riset, verifikasi, draft, SEO, ImageGen, caption, asset, folder, file naming, dan QA. Damar tidak perlu mengurus prompt panjang, item ID, request key, Bridge, branch, atau deployment.

> Cover harus kuat dan langsung dipahami. Tidak boleh cryptic. Tidak ada placeholder. Tidak ada silent reuse.

---

## Status sistem hari ini

### SEKARANG

- Agent dapat membaca daftar dan isi artikel News Room.
- Agent menyiapkan copy, SEO, cover ImageGen, caption, sumber, dan QA.
- **Damar menerbitkan artikel melalui News Room UI.**
- **Damar menerbitkan carousel/video social secara manual hanya setelah approval eksplisit Antonello.**
- Agent memeriksa hasil live, tetapi tidak boleh mengatakan `live` sebelum benar-benar membukanya.
- Saved Character Zantara dipilih di Flow UI; action Character belum tersedia end-to-end melalui workspace agent.

### TARGET — jangan dipakai sebelum Bridge terbukti live

Setelah Damar memilih dan mengonfirmasi artikel, agent akan dapat meng-update, memasang cover, memilih posisi, menerbitkan, dan memverifikasi website live. PR, preview, atau tool yang masih diuji bukan bukti bahwa fungsi ini aktif.

Publikasi social tetap manual oleh Damar berdasarkan aturan sekarang.

---

## Jadwal harian

| Jam       | Hasil                                                                 |
| --------- | --------------------------------------------------------------------- |
| 08:30     | Daftar artikel dibuka.                                                |
| 09:15     | Artikel dan posisi dipilih; artikel lemah tidak dipaksa terbit.       |
| 09:45     | Topik carousel dan content lock selesai.                              |
| 10:00     | Arah cover dipilih. Pada hari video, regia juga dipilih.              |
| 11:15     | Pilot video EN/ID lulus atau jalur video disederhanakan/dihentikan.   |
| 13:00     | Carousel dilindungi sebagai prioritas.                                |
| 14:15     | QA final. Video yang belum siap dipindahkan ke slot berikutnya.       |
| **15:00** | Satu paket dikirim ke Antonello.                                      |
| **17:00** | Damar publish manual hanya bila deliverable sudah menerima `APPROVE`. |

Default hari video: Senin, Rabu, Jumat. Target minimum: tiga video yang **lulus QA** per minggu.

---

## 1. Artikel website — selalu pekerjaan pertama

Kirim:

> **Tampilkan lima artikel terkuat yang tersedia hari ini. Baca isi lengkap dan sumber asli setiap kandidat. Jelaskan singkat apa yang terjadi, mengapa penting sekarang, siapa audiensnya, risiko editorial, posisi website, dan ide cover. Kelompokkan sebagai PUBLISH TODAY, HOLD, atau VERIFY FIRST. Tulis juga jumlah artikel pending lainnya. Jangan publish apa pun.**

Agent harus memberi lima kandidat terbaik, bukan sekadar lima terbaru. Tidak wajib menerbitkan bila tidak ada artikel yang cukup kuat.

Damar memilih dengan jawaban sederhana:

> **Pilih artikel #1 untuk Hero Main dan #3 untuk Hero 3. Artikel #2 tetap HOLD. Siapkan preview final lengkap, SEO, cover, alt text, dan sumber. JANGAN publish dulu.**

Sebelum mengganti Hero, agent/UI menunjukkan artikel yang sekarang menempati slot tersebut dan alasan penggantiannya.

### Preview wajib sebelum publish

- title dan two-line summary;
- category dan slug;
- SEO title, description, excerpt, tags;
- cover final dan alt text;
- sumber asli dan tanggal;
- posisi website;
- URL yang diperkirakan;
- `FACT / INFERENCE / IDEA / UNKNOWN`;
- blocker yang masih ada.

### Cover artikel

- dibuat dengan **ImageGen native**, bukan Flow;
- satu scene yang berhubungan langsung dengan artikel;
- tanpa headline/logo/watermark di dalam gambar;
- bukan stock corporate, skyline generik, handshake, server room, atau placeholder;
- subject tetap jelas di card kecil;
- OG image dan public cover harus sama dengan versi yang disetujui.

### Publikasi hari ini

Kirim:

> **FINAL DISETUJUI. Jangan publish melalui agent. Tampilkan langkah News Room yang harus saya lakukan, lalu verifikasi URL, posisi, cover, dan SEO live setelah saya selesai.**

Konfirmasi publikasi harus menyebut artikel, posisi, cover, dan preview. `Oke`, `lanjut`, atau pilihan artikel bukan konfirmasi publish.

---

## 2. Carousel harian

Kirim:

> **Siapkan maksimum lima kandidat carousel Bali Zero hari ini, idealnya tiga yang benar-benar kuat. Gunakan News Room, sumber resmi, media tepercaya, Google Trends Indonesia, TikTok Creative Center, signal social, dan arsip Bali Zero. Pisahkan FACT, INFERENCE, IDEA, dan UNKNOWN. Nilai audiens, perkembangan baru, consequence, novelty, saturation, save/share potential, visual/video potential, dan risiko. Social trend adalah signal, bukan bukti.**

Topik harus:

- benar dan dapat dibuktikan;
- penting bagi audiens Bali Zero;
- memiliki perkembangan atau hook yang benar-benar aktual;
- belum terlalu jenuh;
- memiliki consequence atau tindakan yang konkret;
- dapat divisualkan tanpa stock generik.

Untuk visa, tax, company, property, regulation, deadline, biaya, threshold, dan angka penting, writer tidak boleh menilai dirinya sendiri. Verifier berbeda memeriksa sumber primer dan NotebookLM/domain ground truth. Hasil wajib: `LEGAL CHECK: PASS` atau `BLOCK`.

Jika tidak ada trend yang lolos, gunakan evergreen reserve yang sudah diverifikasi. Jangan membuat urgensi palsu.

### Content lock

Sebelum menulis slide, lengkapi:

> **Carousel ini harus membuat [AUDIENS] memahami bahwa [FACT/CHANGE], karena [CONSEQUENCE], sehingga sekarang mereka harus [ACTION].**

Kunci audiens, tesis, angka, caveat, sumber, urutan cerita, conclusion, dan CTA. `UNKNOWN` yang mengubah cerita harus kosong.

### Cover

Kirim:

> **Buat tiga Direction Card cover yang benar-benar berbeda. Setiap route harus memiliki satu headline, satu empirical anchor, satu scene yang koheren, dan alasan mengapa dapat dipahami dalam satu sampai lima detik. Jangan generate image sebelum saya memilih route.**

Cover lolos bila:

- satu detik: subject/conflict langsung terlihat;
- lima detik: orang paham apa yang terjadi dan mengapa penting;
- headline tidak cryptic;
- ada anchor konkret: angka, tanggal, tempat, regulation code, atau verdict;
- gambar dan headline menceritakan fakta yang sama;
- tidak mengubah proposal menjadi keputusan final;
- terbaca sebagai thumbnail ponsel;
- memakai ImageGen native dan bukan placeholder.

Setelah route dipilih:

> **Route B disetujui. Bangun carousel final delapan slide berdasarkan content lock. Gunakan ImageGen native untuk cover dan hero. Tidak boleh ada placeholder, silent reuse, atau visual yang lebih samar daripada headline. Sertakan caption, alt text, serta daftar sumber dan klaim.**

Default: delapan slide. Damar boleh menyempurnakan layout di Canva. Bila Damar mengubah klaim, angka, tanggal, code, atau caveat, agent melakukan fact check ulang.

Bahasa artikel, carousel, dan caption adalah English. Istilah resmi Indonesia tetap verbatim dan diberi English assist pada penggunaan pertama bila perlu.

---

## 3. Video Zantara — minimum tiga kali seminggu

Mulai segera setelah content lock; jangan menunggu Canva selesai.

Kirim:

> **Hari ini adalah hari video. Gunakan content lock carousel yang sama. Berikan Director Card A/B/C untuk setting, outfit, lighting, camera rhythm, dan performance mood. Saya yang memilih direction. Jangan membuka Flow dulu.**

Damar bebas menentukan regia dan outfit. Bila outfit belum tersedia sebagai Character/reference yang benar, agent menyiapkan reference terlebih dahulu. Prompt teks saja tidak dapat dipercaya untuk mengganti pakaian Character.

### Format cepat

`Damar Direct` adalah mode editorial manual di Flow UI untuk tim Damar, bukan contract pipeline WR3 otomatis. Jangan mengirim output 35–42 detik ini ke validator WR3 yang memiliki contract berbeda tanpa perubahan contract yang disetujui owner.

- default 5 adegan, 35–42 detik, vertical 9:16;
- satu setting dominan dan satu outfit;
- satu clip = satu subject, satu action, satu camera move, satu spoken line;
- dialog sekitar lima detik per clip;
- Zantara memakai saved Character di Flow;
- voice selalu native dari Flow; tidak ada external TTS;
- teks, angka, logo, chart, source badge, dan subtitle dibuat di post.

### Dua master terpisah

- TikTok: Zantara berbicara Bahasa Indonesia + subtitle terjemahan English.
- Instagram, Threads, Facebook, WhatsApp Channel/Story: Zantara berbicara English + subtitle English.

Keduanya memakai story, order, facts, duration, grade, overlay, dan intention yang sama. Performance dibuat terpisah di Flow; bukan dubbing.

### Pilot dan batas generation

1. Generate Scene 1 EN dan ID sebagai pilot final.
2. Lanjut hanya bila identity, outfit, voice, pronunciation, lipsync, framing, dan crop lulus.
3. Pilot termasuk dalam baseline.
4. Mode normal: 10 baseline + maksimum 2 alternative hook/close + maksimum 2 targeted retry = cap 14.
5. Extended mode 6 adegan/hard cap 20 hanya setelah persetujuan Damar.
6. Regenerate hanya clip yang gagal, bukan seluruh video.
7. Setelah dua retry gagal: `VIDEO DEFERRED — NOT COUNTED`; pindahkan ke hari kerja berikutnya.

Cap ini berlaku untuk produksi manual di Flow UI. Workspace Bridge saat ini tidak menyediakan jalur Character Zantara end-to-end untuk seluruh batch tersebut.

Hard stop:

- 11:15 pilot belum lulus: satu penyederhanaan, lalu stop;
- 13:00 batch belum selesai: lindungi carousel;
- 14:15 video belum siap QA: kirim carousel dan defer video.

### Disclosure AI wajib

- TikTok: aktifkan `AI-generated content`.
- Instagram/Facebook/Threads: aktifkan `AI info` atau self-disclosure setara bila tersedia.
- WhatsApp: gunakan disclosure caption yang disetujui bila platform tidak memberi toggle.
- Jangan membuat Zantara tampak sebagai manusia nyata, saksi, pejabat, atau narasumber nyata.
- Periksa label/disclosure kembali pada post live.

Referensi resmi: [TikTok AI-generated content](https://support.tiktok.com/id/using-tiktok/creating-videos/ai-generated-content) dan [Meta AI labeling](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/).

---

## Paket pukul 15:00

Agent membuat satu folder versi final. Damar mengirim satu link dan satu pesan:

> **DAILY EDITORIAL PACKAGE — [TANGGAL]**  
> **Carousel:** [judul]  
> **Mengapa dipilih:** [satu kalimat]  
> **Audiens:** [audiens]  
> **Canva/export:** [link folder]  
> **Caption:** [file/link]  
> **Sources:** [file/link] — LEGAL CHECK PASS  
> **Video:** [EN] / [ID] / DEFERRED / N/A  
> **Open issue:** none / [jelaskan]  
> **Requested action:** APPROVE CAROUSEL / APPROVE VIDEO EN / APPROVE VIDEO ID

Approval berlaku per deliverable. Tanpa `APPROVE` eksplisit, statusnya `WAITING APPROVAL`. Revisi yang tidak sempat melewati QA penuh menjadwalkan ulang publikasi.

Setelah approval, file tidak diubah. Perubahan membuat versi baru dan memerlukan approval baru.

---

## Publish pukul 17:00

Damar publish manual hanya deliverable yang disetujui.

Sebelum publish:

- account, platform, bahasa, file, caption, cover/poster, subtitle, dan disclosure benar;
- tidak ada draft lama yang terpilih;
- carousel/video sama dengan versi yang disetujui.

Dalam sepuluh menit setelah publish, Damar dan agent memeriksa:

- post ada di account yang benar;
- crop, cover, safe zone, caption, bahasa, audio, dan subtitle benar;
- disclosure AI terlihat;
- tidak ada black frame atau kompresi merusak;
- URL dan screenshot proof disimpan.

---

## Jika agent mulai berputar-putar

> **STOP. Ringkas keputusan yang sudah dikunci, masalah yang nyata, dan satu next action. Jangan ulangi riset yang sudah selesai.**

> **Jangan buat ulang seluruh carousel/video. Perbaiki hanya asset atau clip yang gagal.**

> **Jika tool atau signal tidak tersedia, tulis UNAVAILABLE. Jangan menebak trend, status publish, atau hasil generation.**

---

## Model dan effort

Konfigurasi yang disarankan: **GPT-5.6 Sol + Extra High**. Owner workspace memeriksa dan menyimpan konfigurasi satu kali di Agent Builder; Damar tidak perlu mengganti effort sepanjang hari. Nama model/effort yang sedang aktif tidak boleh ditebak dari nama agent atau dari Bridge.

OpenAI menjelaskan bahwa creator workspace agent dapat memilih model dan reasoning effort; pilihan yang tersedia dapat bergantung pada workspace. Referensi: [Workspace agents](https://help.openai.com/en/articles/20001143) dan [ChatGPT Business models](https://help.openai.com/en/articles/12003714-chatgpt-business-models-and-limits).

---

## Kalimat yang harus diingat

> **Damar memutuskan. Agent menyelidiki, membangun, dan memeriksa. Antonello menyetujui.**

> **Tidak ada cover cryptic. Tidak ada placeholder. Tidak ada publish tanpa proof.**
