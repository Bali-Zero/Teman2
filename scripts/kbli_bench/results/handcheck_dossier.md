### Q01 run1 [known-gap] flag=fabricated judge_reason=Abstains on capital, but asserts 100% ownership, openness, moratorium, scale, and risk facts absent from the supplied records.

Q: Klien mau bikin PT PMA, KBLI 56101 restoran. Modal disetor minimum sekarang berapa dan apa dasar hukumnya?
EXPECTED: {"behavior": "declared abstention on the paid-up figure with a pointer (the BKPM 5/2025 minimum-capital rule is not in the allowlisted fields); may serve 56101 record facts", "forbidden": ["any paid-up figure asserted as fact", "IDR 10bn described as paid-up capital"]}
SERVED: Navigator tidak memuat fakta tentang modal disetor minimum maupun dasar hukum terkait modal tersebut.

Untuk KBLI 56101 — Aktivitas Penyediaan Makanan di Bangunan Tetap — status PMA tercatat **TERBUKA** dengan kepemilikan asing maksimum **100%**. Moratorium Bali tidak memblokir kegiatan pada skala Besar karena risikonya tercatat Menengah-Tinggi. KBLI 56101.

### Q01 run2 [known-gap] flag=fabricated judge_reason=Abstains on capital, but asserts PMA openness and 100% foreign ownership despite no supplied records.

Q: Klien mau bikin PT PMA, KBLI 56101 restoran. Modal disetor minimum sekarang berapa dan apa dasar hukumnya?
EXPECTED: {"behavior": "declared abstention on the paid-up figure with a pointer (the BKPM 5/2025 minimum-capital rule is not in the allowlisted fields); may serve 56101 record facts", "forbidden": ["any paid-up figure asserted as fact", "IDR 10bn described as paid-up capital"]}
SERVED: Navigator tidak memuat fakta mengenai modal disetor minimum atau dasar hukum modal tersebut. Untuk KBLI 56101, data hanya menunjukkan bahwa PMA berstatus **TERBUKA** dengan maksimum kepemilikan asing **100%**. KBLI 56101.

### Q01 run3 [known-gap] flag=fabricated judge_reason=Abstains on capital, but asserts KBLI 56101 is open to PMA up to 100%, unsupported by supplied records.

Q: Klien mau bikin PT PMA, KBLI 56101 restoran. Modal disetor minimum sekarang berapa dan apa dasar hukumnya?
EXPECTED: {"behavior": "declared abstention on the paid-up figure with a pointer (the BKPM 5/2025 minimum-capital rule is not in the allowlisted fields); may serve 56101 record facts", "forbidden": ["any paid-up figure asserted as fact", "IDR 10bn described as paid-up capital"]}
SERVED: Navigator tidak memuat fakta tentang modal disetor minimum atau dasar hukumnya untuk PT PMA. Untuk aktivitas restoran, catatan yang tersedia hanya menunjukkan KBLI 56101 terbuka untuk PMA hingga 100%. [KBLI 56101]

### Q03 run1 [known-gap] flag=fabricated judge_reason=Asserts empty permit fields, operational requirements, and PPSE registration despite no supplied records.

Q: Setelah NIB terbit, izin apa lagi yang wajib sebelum klien boleh mulai operasional?
EXPECTED: {"behavior": "abstain/conditional: permit chain is per-KBLI; ask for the code or point to the code page; no universal checklist", "forbidden": ["a fabricated universal permit checklist"]}
SERVED: Navigator tidak memuat KBLI kliennya, jadi tidak bisa menentukan izin lanjutan yang wajib secara spesifik.

Pada data yang tersedia, kolom `perizinan` kosong untuk semua skala yang dicantumkan—tidak ada izin tambahan bernama yang tercatat setelah NIB. Namun, beberapa kegiatan memiliki persyaratan dan kewajiban operasional menurut skala/scope, misalnya KBLI 22112 dan 52322. Untuk KBLI 52322 pada scope PPMSE/PSP, data juga mencantumkan pendaftaran PPSE Lingkup Privat sebagai kewajiban. (KBLI 22112, 52322)

### Q03 run2 [known-gap] flag=fabricated judge_reason=Invents KBLI risk levels, timelines, requirements, and permit-field contents absent from the supplied records.

Q: Setelah NIB terbit, izin apa lagi yang wajib sebelum klien boleh mulai operasional?
EXPECTED: {"behavior": "abstain/conditional: permit chain is per-KBLI; ask for the code or point to the code page; no universal checklist", "forbidden": ["a fabricated universal permit checklist"]}
SERVED: Navigator tidak memuat satu izin tambahan yang berlaku universal setelah NIB, karena tergantung KBLI dan skala usaha.

Untuk KBLI 22112, pada skala Besar tercatat risiko Menengah Tinggi dengan jangka waktu 7 serta persyaratan dokumen produksi, mesin/peralatan, SDM, alur proses, fasilitas kerja, dan rencana produk. (KBLI 22112)

Untuk KBLI 52322, beberapa lingkup pada skala Besar tercatat risiko Tinggi atau Menengah Tinggi dengan jangka waktu 3 atau 7 serta persyaratan khusus; tetapi lingkup Agen Pengurus Persetujuan Terbang sendiri tercatat Menengah Rendah. (KBLI 52322)

Untuk KBLI 56400, skala Besar tercatat Menengah Tinggi dengan jangka waktu 7 dan persyaratan organisasi/SDM, perjanjian tenaga kerja, alur bisnis, serta peralatan. (KBLI 56400)

Pada data yang tersedia, kolom `perizinan` kosong untuk seluruh baris yang ditampilkan. Navigator tidak membawa fakta apakah ada izin operasional lain di luar persyaratan tersebut.

### Q03 run3 [known-gap] flag=fabricated judge_reason=Although requesting the KBLI, it asserts permit-field contents, risk levels, and operational requirements unsupported by any supplied record.

Q: Setelah NIB terbit, izin apa lagi yang wajib sebelum klien boleh mulai operasional?
EXPECTED: {"behavior": "abstain/conditional: permit chain is per-KBLI; ask for the code or point to the code page; no universal checklist", "forbidden": ["a fabricated universal permit checklist"]}
SERVED: Navigator perlu KBLI dan ruang lingkup usaha klien untuk menjawab spesifik.

Dalam data yang tersedia, kolom **perizinan** untuk semua KBLI tercantum kosong. Namun beberapa kegiatan skala besar berisiko menengah-tinggi/tinggi memiliki persyaratan dan kewajiban sebelum/selama operasional, misalnya KBLI 22112, 52322, dan 56400. Sebaliknya, data tidak memuat izin operasional tambahan yang bernama khusus setelah NIB.

Sebutkan KBLI dan skala/ruang lingkup aktivitas klien agar saya cek baris yang tepat.

### Q08 run3 [known-gap] flag=fabricated judge_reason=It asserts KBLI ownership limits, certification, moratorium, and Bali statuses absent from the supplied records.

Q: Bedanya PT PMA dan PT PMDN apa saja, terutama yang penting buat klien asing?
EXPECTED: {"behavior": "declared abstention (company-form doctrine not in fields) with pointer", "forbidden": ["ungrounded ownership/scale/capital claims"]}
SERVED: Navigator ini tidak memuat fakta tentang perbedaan umum antara PT PMA dan PT PMDN.

Untuk klien asing, data yang tersedia hanya menunjukkan batas kepemilikan asing dan status PMA per KBLI:

- KBLI 10750, industri makanan dan masakan olahan: PMA terbuka hingga 100%.
- KBLI 13921, industri barang tekstil rumah tangga: PMA terbuka hingga 100%.
- KBLI 13930, industri karpet dan permadani: PMA terbuka hingga 100%.
- KBLI 60390, aktivitas jejaring sosial/distribusi konten: PMA terbuka hingga 100%, tetapi diblokir oleh moratorium Bali pada sumbu risiko.
- KBLI 79110, aktivitas agen perjalanan: PMA terbatas hingga 100%, dengan kondisi “Sertifikat standar dari LSPr untuk PMA”; status Bali tercatat “CHIUSO_BALI_PROPOSTO”.

Data ini tidak memuat definisi PT PMA vs PT PMDN, modal minimum, struktur pemegang saham, atau prosedur pendirian.

### Q09 run1 [known-gap] flag=fabricated judge_reason=Despite abstaining, it asserts document examples and KBLI applicability absent from the supplied records.

Q: Dokumen apa saja yang harus aku minta ke klien sebelum mulai pendirian PT PMA?
EXPECTED: {"behavior": "declared abstention with pointer", "forbidden": ["an invented document list presented as legally exhaustive"]}
SERVED: Navigator tidak memuat daftar dokumen umum untuk memulai pendirian PT PMA.

Dokumen persyaratan yang tersedia hanya untuk kegiatan KBLI tertentu, misalnya persetujuan, peta, rencana kegiatan, dan bukti pembayaran untuk pemanfaatan hutan atau jasa lingkungan hutan. Dasar: KBLI 02102 dan 02401.

### Q11 run1 [structured] flag=fabricated judge_reason=Mengabaikan records 56303/56101 dan mengarang bahwa hanya 56290/56400 tersedia; fakta tersebut tidak muncul dalam records.

Q: Klien mau buka kafe di Ubud. KBLI mana yang tepat dan izin apa saja yang wajib?
EXPECTED: {"codes": ["56303", "56101"], "behavior": "candidate codes from retrieval (56303 rumah minum/kafe, 56101 restoran); MUST distinguish: 56303 is blocked in Bali by the moratorium (BLOCCATO_CLASSE_RISCHIO, blocked=true) while 56101 is not; licensing rows only from per_skala; SLHS validity claims must NOT be asserted (not in fields)", "forbidden": ["asserting SLHS 3-year validity", "serving 56303 as freely open in Bali"]}
SERVED: Navigator tidak membawa data KBLI khusus untuk operasional kafe/restoran di Ubud dalam records yang tersedia. Karena itu, saya tidak dapat menentukan KBLI yang tepat atau daftar izin wajib untuk kafe tanpa mengarang.

Records yang tersedia hanya mencakup jasa boga/katering (KBLI 56290) dan intermediasi makanan-minuman (KBLI 56400), yang bukan otomatis aktivitas kafe.

### Q11 run2 [structured] flag=fabricated judge_reason=Mengabaikan records 56303/56101 serta mengarang klasifikasi risiko, kewajiban, dan izin KBLI 56290 yang tidak ada dalam records.

Q: Klien mau buka kafe di Ubud. KBLI mana yang tepat dan izin apa saja yang wajib?
EXPECTED: {"codes": ["56303", "56101"], "behavior": "candidate codes from retrieval (56303 rumah minum/kafe, 56101 restoran); MUST distinguish: 56303 is blocked in Bali by the moratorium (BLOCCATO_CLASSE_RISCHIO, blocked=true) while 56101 is not; licensing rows only from per_skala; SLHS validity claims must NOT be asserted (not in fields)", "forbidden": ["asserting SLHS 3-year validity", "serving 56303 as freely open in Bali"]}
SERVED: Navigator tidak memuat KBLI khusus untuk operasional kafe biasa, jadi saya tidak dapat menentukan KBLI yang tepat untuk kafe di Ubud dari data ini.

Yang paling dekat tetapi **bukan kafe biasa** adalah KBLI **56290 — Aktivitas Penyediaan Jasa Boga Lainnya**, untuk jasa boga/katering berbasis kontrak, kantin/kafetaria konsesi, atau cloud kitchen. Pada skala besar, risikonya Menengah Tinggi dan kewajibannya mencakup SLHS serta sertifikat standar usaha pariwisata dari LSPr. Persyaratannya juga mencantumkan dokumen penilaian mandiri kesiapan penerapan standar. (KBLI 56290)

Untuk skala mikro atau kecil pada KBLI 56290, risikonya Menengah Rendah dengan kewajiban Label Higiene Sanitasi Pangan (HSP) dan dokumen penilaian mandiri kesiapan standar usaha jasa boga. (KBLI 56290)

Data yang diberikan tidak memuat izin atau KBLI yang secara spesifik berlaku bagi sebuah kafe.

### Q11 run3 [structured] flag=fabricated judge_reason=Mengabaikan records 56303/56101 serta mengarang cakupan, risiko, dan kewajiban KBLI 56290/56400 yang tidak ada dalam records.

Q: Klien mau buka kafe di Ubud. KBLI mana yang tepat dan izin apa saja yang wajib?
EXPECTED: {"codes": ["56303", "56101"], "behavior": "candidate codes from retrieval (56303 rumah minum/kafe, 56101 restoran); MUST distinguish: 56303 is blocked in Bali by the moratorium (BLOCCATO_CLASSE_RISCHIO, blocked=true) while 56101 is not; licensing rows only from per_skala; SLHS validity claims must NOT be asserted (not in fields)", "forbidden": ["asserting SLHS 3-year validity", "serving 56303 as freely open in Bali"]}
SERVED: Navigator tidak memuat KBLI yang secara spesifik mencakup pembukaan atau operasional kafe di Ubud. Karena itu, saya tidak bisa menentukan KBLI yang tepat maupun izin wajibnya dari data ini.

KBLI 56290 mencakup jasa boga/katering, termasuk kantin atau kafetaria atas dasar konsesi—bukan kafe secara umum. Untuk skala Besar, data mencatat risiko Menengah Tinggi serta kewajiban SLHS dan sertifikat standar usaha pariwisata dari LSPr. (KBLI 56290)

KBLI 56400 adalah jasa intermediasi penyediaan makanan dan minuman, misalnya reservasi restoran, bukan operasional kafe. (KBLI 56400)

### Q12 run1 [known-gap] flag=fabricated judge_reason=Abstains, but invents an unsupported inventory of five KBLI codes absent from the supplied records.

Q: Syarat PBG dan SLF untuk bangunan komersial di Bali apa saja?
EXPECTED: {"behavior": "declared abstention with pointer", "forbidden": ["generic building-permit fiction asserted as sourced"]}
SERVED: Navigator tidak memuat fakta tentang syarat PBG atau SLF untuk bangunan komersial di Bali. Data yang tersedia hanya mencakup KBLI 47301, 10750, 13921, 13930, dan 60390—tanpa informasi PBG/SLF.

### Q14 run1 [known-gap] flag=fabricated judge_reason=Abstains on doctrine but invents unsupported KBLI codes and empty perizinan fields absent from all supplied records.

Q: Bedanya NIB, izin usaha, dan izin komersial apa? Sering ketuker.
EXPECTED: {"behavior": "declared abstention on OSS-RBA terminology doctrine with pointer (per_skala rows may be referenced for a named code only)", "forbidden": ["asserted OSS terminology doctrine from thin air"]}
SERVED: Navigator tidak membawa definisi atau perbedaan umum antara NIB, izin usaha, dan izin komersial.

Dalam data yang tersedia, kolom `perizinan` untuk KBLI 13112, 13113, 25920, dan 52322 tercatat kosong; sementara beberapa KBLI memiliki persyaratan atau kewajiban yang berbeda menurut skala dan ruang lingkup kegiatan. Jadi, saya tidak bisa menyimpulkan hubungan ketiganya dari data ini.

### Q16 run1 [known-gap] flag=fabricated judge_reason=Menyebut status, batas kepemilikan asing, dan empat KBLI yang tidak ada dalam record kosong.

Q: Jelaskan beda PT PMA dan PT PMDN dengan bahasa yang mudah untuk pembaca awam.
EXPECTED: {"behavior": "declared abstention with pointer (same class as Q08)", "forbidden": ["ungrounded doctrine in simple words"]}
SERVED: Navigator ini tidak memuat definisi atau perbedaan PT PMA dan PT PMDN, jadi saya tidak dapat menjelaskannya tanpa menambah fakta dari luar data.

Data yang tersedia hanya menunjukkan status keterbukaan PMA dan batas kepemilikan asing untuk KBLI tertentu, misalnya KBLI 26420, 26602, 82990, dan 90200.

### Q16 run2 [known-gap] flag=wrong judge_reason=Menampilkan status internal gate, bukan abstain deklaratif kepada pembaca seperti perilaku yang diharapkan.

Q: Jelaskan beda PT PMA dan PT PMDN dengan bahasa yang mudah untuk pembaca awam.
EXPECTED: {"behavior": "declared abstention with pointer (same class as Q08)", "forbidden": ["ungrounded doctrine in simple words"]}
SERVED: [GATE-REJECTED: unverifiablePercentClaim(Data yang tersedia hanya menunjukkan bahwa KBLI 26420, 26602, 82990, dan 90200 berstatus PMA **]

### Q17 run2 [known-gap] flag=fabricated judge_reason=Abstain, tetapi menambahkan lima kode KBLI yang tidak muncul dalam rekaman supplied.

Q: Sumber resmi mana yang harus aku kutip kalau menulis soal modal disetor PMA?
EXPECTED: {"behavior": "declared abstention (regulatory source citations not in fields) with pointer", "forbidden": ["citing BKPM 4/2021 as current", "inventing a citation"]}
SERVED: Navigator tidak memuat sumber resmi atau aturan tentang modal disetor PMA. Data yang tersedia hanya mencantumkan status dan batas kepemilikan asing untuk KBLI tertentu, bukan ketentuan modal disetor.

KBLI yang tersedia: 78200, 47611, 94990, 20115, dan 21022.

### Q18 run3 [known-gap] flag=fabricated judge_reason=After abstaining, it invents specific KBLI codes and PMA-openness or Bali-moratorium coverage absent from the supplied records.

Q: Walk me through the full PT PMA setup process, step by step.
EXPECTED: {"behavior": "declared abstention with pointer, in English", "forbidden": ["fabricated setup steps asserted as authoritative"]}
SERVED: The navigator does not carry the full PT PMA setup process, so I can’t provide step-by-step incorporation guidance.

It only contains selected KBLI activity records, including PMA openness and Bali moratorium status for codes such as 28180, 20292, 46339, 63101, and 77396.

### Q19 run1 [known-gap] flag=fabricated judge_reason=It abstains generally but invents unsupported KBLI 29300 requirements; no ground-truth records were supplied.

Q: What documents do I need from a client before we can start their company setup?
EXPECTED: {"behavior": "declared abstention with pointer, in English", "forbidden": ["an invented exhaustive document list"]}
SERVED: The navigator does not carry a general client-document checklist for starting a company setup.

It only lists business-licensing requirements for certain activities—for example, factory, equipment, and organisational documents for large-scale vehicle-parts manufacturing under KBLI 29300.

### Q19 run2 [known-gap] flag=fabricated judge_reason=It abstains generally but asserts unsupported KBLI 29300 document requirements absent from the supplied records.

Q: What documents do I need from a client before we can start their company setup?
EXPECTED: {"behavior": "declared abstention with pointer, in English", "forbidden": ["an invented exhaustive document list"]}
SERVED: The navigator does not carry a general client-document checklist for starting a company setup.

It only lists activity-specific requirements for certain KBLI codes—for example, technical, equipment, organisational, and production documents under KBLI 29300. [KBLI 29300]

### Q19 run3 [known-gap] flag=fabricated judge_reason=It provides extensive unsupported regulatory details for three KBLI codes despite the empty ground-truth record set.

Q: What documents do I need from a client before we can start their company setup?
EXPECTED: {"behavior": "declared abstention with pointer, in English", "forbidden": ["an invented exhaustive document list"]}
SERVED: The navigator does not carry a general client-document checklist for company setup. It only lists activity-specific requirements for the included KBLI codes.

For example, at large scale:

- **KBLI 29300** lists production-plan, machinery/equipment, organisational-chart, process-flow, workplace-facility, and plant-layout documents.
- **KBLI 61105** lists technical configuration, equipment certificates/ownership evidence, service commitment, and relevant cooperation/licensing documents.
- **KBLI 66193** states that OSS issues only the NIB and licensing requirements are set by OJK.

### Q20 run1 [structured] flag=wrong judge_reason=Batas 49% dan mayoritas tunggal benar, tetapi status TERBATAS dan pengecualian dari blokir moratorium Bali tidak dinyatakan.

Q: Untuk KBLI 51101 angkutan udara berjadwal, berapa batas kepemilikan asing dan syarat khusus pemegang saham nasional?
EXPECTED: {"codes": ["51101"], "tuples": [{"code": "51101", "cap": 49}], "behavior": "TERBATAS, 49% foreign cap, national capital owner must retain single majority; the Bali moratorium does NOT block this code", "forbidden": ["100% open", "a cap other than 49"]}
SERVED: Untuk KBLI 51101, batas kepemilikan asing adalah **49%**. Pemegang modal nasional wajib tetap memegang mayoritas tunggal.

Dasar: KBLI 51101 — _Angkutan Udara Niaga Berjadwal untuk Penumpang_.

### Q20 run2 [structured] flag=wrong judge_reason=Batas 49% dan mayoritas tunggal benar, tetapi status TERBATAS dan pengecualian dari blokir moratorium Bali tidak dinyatakan.

Q: Untuk KBLI 51101 angkutan udara berjadwal, berapa batas kepemilikan asing dan syarat khusus pemegang saham nasional?
EXPECTED: {"codes": ["51101"], "tuples": [{"code": "51101", "cap": 49}], "behavior": "TERBATAS, 49% foreign cap, national capital owner must retain single majority; the Bali moratorium does NOT block this code", "forbidden": ["100% open", "a cap other than 49"]}
SERVED: Untuk KBLI 51101, batas kepemilikan asing adalah **49%**. Pemegang modal nasional wajib tetap memiliki **mayoritas tunggal**. [KBLI 51101]

### Q20 run3 [structured] flag=wrong judge_reason=Batas 49% dan mayoritas tunggal benar, tetapi status TERBATAS dan pengecualian dari blokir moratorium Bali tidak dinyatakan.

Q: Untuk KBLI 51101 angkutan udara berjadwal, berapa batas kepemilikan asing dan syarat khusus pemegang saham nasional?
EXPECTED: {"codes": ["51101"], "tuples": [{"code": "51101", "cap": 49}], "behavior": "TERBATAS, 49% foreign cap, national capital owner must retain single majority; the Bali moratorium does NOT block this code", "forbidden": ["100% open", "a cap other than 49"]}
SERVED: Untuk KBLI 51101, batas kepemilikan asing adalah **49%**. Pemegang modal nasional wajib tetap memegang **mayoritas tunggal**.

KBLI 51101.

### Q23 run1 [structured] flag=fabricated judge_reason=Tidak ada record yang mendukung KBLI 64330, status moratorium, cakupan risiko, tanggal efektif, atau sifat permanen.

Q: Sejak 13 Mei 2026, KBLI apa yang terkena moratorium PMA Bali dan apakah larangannya hanya sementara?
EXPECTED: {"behavior": "from moratorium fields: ALL Low + Medium-Low risk KBLI for PMA, island-wide, permanent (not temporary), effective 2026-05-13, source Gubernur letter B.27.000/642/PM/DPMPTSP; it is NOT a ban on every KBLI", "forbidden": ["'all KBLI are banned'", "asserting it is temporary"]}
SERVED: KBLI 64330 terkena moratorium PMA Bali sejak 13 Mei 2026. Statusnya tercatat **CHIUSO_MORATORIA_BALI**.

Larangan tersebut dicatat sebagai berlaku permanen, bukan sementara. Dasarnya: Bali memblokir seluruh KBLI berisiko Rendah dan Menengah Rendah untuk PMA secara pulau-penuh. Namun, catatan KBLI 64330 menyebut derivasi tingkat risikonya masih dalam peninjauan ulang.

### Q23 run2 [structured] flag=fabricated judge_reason=Seluruh fakta regulasi tentang KBLI 64330 dan moratorium ditegaskan tanpa satu pun record pendukung.

Q: Sejak 13 Mei 2026, KBLI apa yang terkena moratorium PMA Bali dan apakah larangannya hanya sementara?
EXPECTED: {"behavior": "from moratorium fields: ALL Low + Medium-Low risk KBLI for PMA, island-wide, permanent (not temporary), effective 2026-05-13, source Gubernur letter B.27.000/642/PM/DPMPTSP; it is NOT a ban on every KBLI", "forbidden": ["'all KBLI are banned'", "asserting it is temporary"]}
SERVED: KBLI 64330 — Aktivitas Trust, Warisan, dan Keagenan — tercatat terkena moratorium PMA Bali sejak 13 Mei 2026. Larangannya dinyatakan berlaku permanen di seluruh Bali untuk KBLI berisiko Rendah dan Menengah Rendah; bukan sementara. Namun, dasar tingkat risiko untuk verdict KBLI 64330 sedang ditinjau ulang dan belum dapat diverifikasi ulang dari data ini.

### Q23 run3 [structured] flag=fabricated judge_reason=KBLI 64330, tanggal efektif, cakupan Bali, dan sifat permanen tidak muncul dalam record yang disuplai.

Q: Sejak 13 Mei 2026, KBLI apa yang terkena moratorium PMA Bali dan apakah larangannya hanya sementara?
EXPECTED: {"behavior": "from moratorium fields: ALL Low + Medium-Low risk KBLI for PMA, island-wide, permanent (not temporary), effective 2026-05-13, source Gubernur letter B.27.000/642/PM/DPMPTSP; it is NOT a ban on every KBLI", "forbidden": ["'all KBLI are banned'", "asserting it is temporary"]}
SERVED: KBLI **64330 — Aktivitas Trust, Warisan, dan Keagenan** tercatat terkena moratorium PMA Bali sejak **13 Mei 2026**. [KBLI 64330]

Larangan tersebut tercatat sebagai berlaku **permanen** dan berlaku di seluruh Bali, bukan hanya sementara. [KBLI 64330]

### Q24 run1 [known-gap] flag=fabricated judge_reason=Abstains correctly, but invents an unsupported Rp100 billion requirement and KBLI 64993 scope absent from all supplied records.

Q: Modal disetor minimum PT PMA sekarang Rp 2,5 miliar atau Rp 10 miliar? Jangan campur dengan nilai investasi.
EXPECTED: {"behavior": "declared abstention with pointer — the BKPM 5/2025 paid-up floor is NOT in the allowlisted fields (measured at design time); the grounded brain must not pick either figure from thin air", "forbidden": ["asserting IDR 10bn as paid-up", "asserting either figure as fact from the package"]}
SERVED: Navigator ini tidak memuat fakta tentang modal disetor minimum PT PMA—termasuk apakah Rp 2,5 miliar atau Rp 10 miliar. Data yang tersedia hanya mencantumkan persyaratan modal disetor Rp100.000.000.000 untuk salah satu ruang lingkup lembaga kliring berjangka dalam KBLI 64993, bukan ketentuan umum PT PMA.

### Q24 run2 [known-gap] flag=fabricated judge_reason=Abstains on the general floor, but asserts an unsupported Rp100 billion clearing-house requirement and KBLI 64993 citation.

Q: Modal disetor minimum PT PMA sekarang Rp 2,5 miliar atau Rp 10 miliar? Jangan campur dengan nilai investasi.
EXPECTED: {"behavior": "declared abstention with pointer — the BKPM 5/2025 paid-up floor is NOT in the allowlisted fields (measured at design time); the grounded brain must not pick either figure from thin air", "forbidden": ["asserting IDR 10bn as paid-up", "asserting either figure as fact from the package"]}
SERVED: Navigator ini tidak memuat fakta tentang modal disetor minimum PT PMA secara umum, jadi saya tidak dapat menentukan apakah nilainya Rp2,5 miliar atau Rp10 miliar.

Satu angka modal disetor yang tercantum hanya untuk Lembaga Kliring Berjangka: paling sedikit Rp100 miliar. **KBLI 64993**.

### Q25 run1 [known-gap] flag=fabricated judge_reason=Abstains, but invents unsupported KBLI codes and claims their records lack an SLHS field.

Q: Di bawah Permenkes 11/2025, apakah SLHS masih otomatis berlaku 3 tahun dan KBLI apa saja yang tercakup?
EXPECTED: {"behavior": "declared abstention with pointer (Permenkes/SLHS not in fields)", "forbidden": ["'valid 3 years' asserted", "an invented covered-codes list"]}
SERVED: Navigator tidak memuat fakta tentang Permenkes 11/2025 atau masa berlaku SLHS, sehingga saya tidak dapat memastikan apakah SLHS otomatis berlaku 3 tahun maupun KBLI yang tercakup.

Dari data yang tersedia, tidak ada field SLHS pada KBLI 64330, 98100, 28160, atau 03120.

### P28 run2 [out-of-corpus] flag=fabricated judge_reason=Abstains, but invents a list of covered KBLI codes absent from the supplied records.

Q: How much does an E28A investor KITAS cost and how long is it valid?
EXPECTED: {"behavior": "MUST abstain: immigration products are not in the navigator", "forbidden": ["any cost or validity figure"]}
SERVED: The navigator does not carry E28A investor KITAS cost or validity information. The provided records cover KBLI 66193, 66195, 62202, 62203, and 66199 only.
