# Perbandingan Database KBLI: File JSON vs Portal OSS

## Pendahuluan

Dalam video ini, kita akan membahas perbandingan antara dua sumber data KBLI di Indonesia: Portal resmi OSS RBA dari pemerintah, dan database JSON yang telah dikompilasi dari berbagai sumber resmi.

Pertanyaan utamanya adalah: mana yang lebih baik untuk keperluan bisnis dan riset?

Jawabannya mungkin akan mengejutkan Anda.

---

## Apa Itu KBLI?

KBLI adalah singkatan dari Klasifikasi Baku Lapangan Usaha Indonesia. Ini adalah sistem kode yang digunakan pemerintah untuk mengklasifikasikan setiap jenis usaha di Indonesia.

Setiap bisnis yang ingin beroperasi secara legal di Indonesia harus memiliki kode KBLI yang sesuai. Kode ini menentukan:
- Persyaratan perizinan yang harus dipenuhi
- Tingkat risiko usaha
- Apakah investor asing boleh berinvestasi
- Skala usaha yang diizinkan

---

## Sumber Pertama: Portal OSS RBA

OSS RBA adalah portal resmi pemerintah Indonesia untuk perizinan berusaha berbasis risiko. Alamatnya adalah oss.go.id.

### Kelebihan OSS:
- Ini adalah sumber resmi dari pemerintah
- Data selalu terupdate dengan regulasi terbaru
- Gratis dan dapat diakses oleh siapa saja

### Kekurangan OSS:
Namun, OSS memiliki beberapa keterbatasan yang sangat signifikan.

Pertama, tidak ada fitur download massal. Anda harus mencari kode KBLI satu per satu. Bayangkan jika Anda perlu menganalisis ratusan kode KBLI untuk riset bisnis.

Kedua, tidak ada API publik. Ini berarti Anda tidak bisa mengakses data secara programatik untuk aplikasi atau sistem Anda.

Ketiga, websitenya sangat bergantung pada JavaScript. Ini membuat scraping atau pengambilan data otomatis menjadi sangat sulit.

Keempat, sering terjadi error. Banyak pengguna melaporkan pesan "Data Tidak Ditemukan" padahal kode KBLI tersebut seharusnya ada.

Kelima, informasi penting seperti tingkat risiko dan status PMA tersembunyi di dalam navigasi yang rumit. Anda harus klik berkali-kali untuk menemukan informasi yang Anda butuhkan.

---

## Sumber Kedua: Database JSON Terkompilasi

Database JSON yang kami analisis adalah hasil kompilasi dari dua sumber utama: API OSS RBA dan dokumen Peraturan Pemerintah Nomor 28 Tahun 2025.

### Statistik Database JSON:

Total ada dua ribu delapan ratus delapan belas kode KBLI dalam database ini. Bandingkan dengan OSS yang hanya menampilkan sekitar seribu tiga ratus empat puluh sembilan kode yang beroperasi.

Enam puluh sembilan persen dari kode KBLI adalah kode 5 digit, yaitu klasifikasi paling detail yang tersedia.

Enam puluh satu persen data telah di-cross-reference dari kedua sumber, OSS dan PP 28/2025. Ini memberikan validasi ganda terhadap akurasi data.

---

## Perbandingan Detail

Mari kita bandingkan kedua sumber ini dari berbagai aspek.

### Aspek Pertama: Kelengkapan Data

OSS hanya menyediakan informasi dasar: kode, judul, dan deskripsi singkat.

Database JSON menyediakan informasi yang jauh lebih lengkap:
- Tingkat risiko: apakah Rendah, Sedang, atau Tinggi
- Status PMA: apakah investor asing diizinkan
- Persentase maksimum kepemilikan asing
- Skala usaha yang berlaku: Mikro, Kecil, Menengah, atau Besar
- Persyaratan yang harus dipenuhi
- Kewajiban setelah izin diperoleh
- Status Fiktif Positif: apakah izin otomatis disetujui jika tidak ada respons

### Aspek Kedua: Aksesibilitas

OSS hanya bisa diakses melalui website. Tidak ada cara untuk mengunduh data dalam jumlah besar.

Database JSON bisa langsung digunakan untuk:
- Analisis data dengan Python atau Excel
- Integrasi dengan sistem AI dan machine learning
- Pencarian cepat dengan filter kompleks
- Pembuatan laporan otomatis

### Aspek Ketiga: Kualitas Konten

Setiap entry dalam database JSON memiliki rata-rata seribu enam ratus sembilan puluh satu karakter teks deskriptif.

Empat puluh persen entry memiliki daftar persyaratan lengkap.
Lima puluh dua persen entry memiliki daftar kewajiban lengkap.
Seratus persen entry memiliki format yang konsisten dan terstruktur.

---

## Kasus Penggunaan

### Untuk Konsultan Bisnis:

Jika Anda seorang konsultan yang membantu klien membuka usaha, database JSON memungkinkan Anda dengan cepat mencari semua KBLI dengan risiko rendah yang mengizinkan PMA. Dengan OSS, Anda harus membuka ratusan halaman satu per satu.

### Untuk Developer Aplikasi:

Jika Anda membangun aplikasi perizinan, database JSON bisa langsung diintegrasikan. OSS tidak menyediakan API, jadi integrasi tidak mungkin dilakukan.

### Untuk Riset dan Analisis:

Jika Anda melakukan riset tentang regulasi bisnis Indonesia, database JSON memungkinkan analisis statistik. Misalnya: berapa persen KBLI di sektor pariwisata yang berisiko tinggi? Dengan OSS, analisis seperti ini hampir tidak mungkin.

### Untuk Training Tim:

Jika Anda melatih tim tentang KBLI, database JSON bisa digunakan untuk membuat materi training yang komprehensif. Data terstruktur memudahkan pembuatan presentasi dan quiz.

---

## Temuan Menarik dari Database JSON

Berikut beberapa statistik menarik yang hanya bisa ditemukan dengan menganalisis database JSON:

Dua ratus lima puluh lima kode KBLI termasuk dalam mekanisme Fiktif Positif. Ini berarti jika instansi pemerintah tidak merespons dalam batas waktu SLA, izin dianggap otomatis disetujui.

Tiga puluh empat persen kode KBLI memiliki tingkat risiko Rendah.
Tujuh belas persen memiliki tingkat risiko Sedang.
Lima belas persen memiliki tingkat risiko Tinggi.

Lima puluh sembilan persen kode KBLI mengizinkan investasi asing dengan kepemilikan hingga seratus persen.

Sektor dengan KBLI terbanyak adalah Industri dengan dua puluh delapan persen, diikuti Perdagangan dengan tiga belas persen.

---

## Rekomendasi Penggunaan

Berdasarkan analisis kami, berikut rekomendasi penggunaan kedua sumber:

### Gunakan OSS untuk:
- Verifikasi final sebelum pengajuan izin resmi
- Mengecek update regulasi terbaru
- Kasus-kasus individual yang memerlukan kepastian hukum

### Gunakan Database JSON untuk:
- Semua kebutuhan analisis dan riset
- Integrasi dengan sistem dan aplikasi
- Training dan edukasi tim
- Konsultasi bisnis yang memerlukan perbandingan banyak KBLI
- Pembuatan laporan dan presentasi

---

## Cara Menjaga Database Tetap Update

Database JSON perlu diperbarui secara berkala untuk memastikan akurasi. Berikut workflow yang direkomendasikan:

Pertama, monitor pengumuman dari BKPM dan BPS tentang perubahan regulasi KBLI.

Kedua, unduh dokumen PDF terbaru dari peraturan pemerintah yang relevan.

Ketiga, jalankan script ekstraksi untuk memproses PDF menjadi data terstruktur.

Keempat, lakukan validasi silang dengan portal OSS untuk kode-kode kritis.

Kelima, update database JSON dan catat perubahan yang terjadi.

Frekuensi yang direkomendasikan adalah setiap tiga bulan atau segera setelah ada peraturan baru yang signifikan.

---

## Kesimpulan

Jadi, mana yang lebih baik: OSS atau Database JSON?

Untuk penggunaan resmi dan verifikasi final, OSS tetap penting sebagai sumber otoritatif pemerintah.

Namun, untuk semua kebutuhan praktis lainnya - analisis, integrasi, riset, training, dan konsultasi - database JSON jauh lebih superior.

Database JSON adalah satu-satunya sumber data KBLI yang terstruktur, lengkap, dan siap pakai untuk keperluan programatik di Indonesia.

Faktanya, informasi yang tersedia dalam database JSON ini tidak bisa diperoleh dengan cara lain, kecuali dengan membuka ribuan halaman di OSS satu per satu dan mencatat semuanya secara manual.

Ini adalah contoh bagaimana teknologi dapat membuat data pemerintah menjadi lebih accessible dan useful untuk para pelaku bisnis dan profesional di Indonesia.

---

## Penutup

Terima kasih telah menyimak video ini tentang perbandingan sumber data KBLI di Indonesia.

Jika Anda tertarik untuk menggunakan database JSON untuk keperluan bisnis Anda, atau ingin mempelajari lebih lanjut tentang sistem perizinan di Indonesia, silakan hubungi tim Bali Zero.

Sampai jumpa di video berikutnya.

---

*Sumber Data:*
- Portal OSS RBA: oss.go.id
- Peraturan Pemerintah Nomor 28 Tahun 2025
- Badan Pusat Statistik: klasifikasi.web.bps.go.id
- Database kbli_unified_export.json (2,818 KBLI entries)
