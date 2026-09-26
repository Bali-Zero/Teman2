/**
 * Plain wording for the "Why we ask" line printed under every question
 * (WhyWeAsk, variant="inline" — always visible, not a collapsed disclosure).
 * The frozen `why.*` strings said "the engine receives…", "decision fact",
 * "closed-enum", "interview branch"; the MEANING is kept line by line — what
 * is sent, that it is sent unchanged, what is never inferred — only the
 * engine's vocabulary goes (MV:2167, council CRITIQUE-v2 Oracle #1).
 * Merged into PLAIN_COPY; parity and the vocabulary guard live in
 * plain-copy.test.ts.
 */
export const PLAIN_WHY = {
  en: {
    "why.in_indonesia":
      "Where you are now tells the check whether this is about a stay already under way or a plan for later.",
    "why.permit_expiry":
      "The check needs the date itself to judge timing; this page does not work out a filing route from it.",
    "why.current_status_code":
      "The printed status code is sent unchanged; this page never guesses it from the permit name.",
    "why.stay_permit_code":
      "The printed code is sent unchanged, the same as the code list above — this page never guesses it from the permit name.",
    "why.overstay_days":
      "Days of active overstay are asked on their own because they matter for safety. They are never worked out from the expiry date in your browser.",
    "why.wants_onshore_conversion":
      "Your yes or no is sent as given; no conversion route is chosen for you.",
    "why.application_channel":
      "The option you pick is sent unchanged. This page never picks a channel from your dates.",
    "why.nationalities":
      "Nationality is checked exactly as you give it. Several nationalities stay separate and are never guessed.",
    "why.category":
      "This only chooses which questions come next. Only the check of your answers against the dated rules can say whether a visa path fits.",
    "why.trip_scope":
      "Overlapping purposes need a person to read them. This answer is kept as context and is not turned into anything else.",
    "why.entry_pattern":
      "One entry or multiple entries is sent exactly as you choose it.",
    "why.sponsor_category":
      "The sponsor category is recorded on its own. No rule in the current set reads it yet — it only prepares the ground for rules that will.",
    "why.sponsor_government_invitation":
      "Only your yes or no about a government invitation is sent.",
    "why.sponsor_government_collaboration":
      "Only your yes or no about a confirmed government collaboration is sent.",
    "why.sponsor_world_figure_invitation":
      "Only your yes or no about a world-figure invitation is sent.",
    "why.sponsor_diplomatic_household":
      "Only your yes or no about a role in a diplomatic household is sent.",
    "why.sponsor_trade_office":
      "Only your yes or no about the sponsor being a trade office is sent.",
    "why.business_activity":
      "Only one answer changes what is checked: exploring whether to invest or open a business is checked as an investment purpose, and we then ask the few questions that settle it. Otherwise this detail only decides whether a person has to look at your trip — training and “another business activity” do, the other answers do not.",
    "why.business_sponsor_confirmed":
      "Sponsor confirmation is sent as its own yes or no.",
    "why.work_payer":
      "Only whether the employer is an Indonesian entity is sent; this page does not work out a visa from it.",
    "why.work_indonesia_compensation":
      "This is sent as where your pay comes from; no amount and no eligibility are worked out from it.",
    "why.work_sponsor_confirmed":
      "Only your yes or no about sponsor confirmation is sent.",
    "why.remote_clients":
      "Whether you serve clients in Indonesia is sent as you answer it; it is not worked out from where you live.",
    "why.remote_employer_country":
      "The country code is sent exactly as entered; this page does not sort it into a category.",
    "why.investment_vehicle":
      "This only chooses which questions come next. It never chooses a visa path.",
    "why.investment_pt_pma":
      "Your commitment is sent as a yes or no, with no amount or status assumed.",
    "why.investment_capital_idr":
      "The amount is sent as you enter it. No threshold is shown or assumed here.",
    "why.investment_amount_usd":
      "The amount is sent as you enter it, in the currency you chose. No threshold is shown or assumed here, and nothing is converted.",
    "why.investment_paid_up_capital_idr":
      "The exact amount is sent separately from the capital you plan to invest.",
    "why.investment_role": "The role you pick is sent unchanged.",
    "why.investment_establishes_company":
      "Only your yes or no about setting up a company is sent.",
    "why.investment_foreign_branch":
      "Only your yes or no about a branch or subsidiary of a foreign company is sent.",
    "why.investment_ikn_subsidiary":
      "Only your yes or no about a subsidiary in IKN is sent.",
    "why.investment_capital_market_only":
      "Only your yes or no about an investment made only through the capital market is sent.",
    "why.investment_meets_threshold":
      "Only your yes or no is sent. No amount is shown or assumed here.",
    "why.family_relation": "The relationship you pick is sent unchanged.",
    "why.marital_status": "Your marital status is sent exactly as you pick it.",
    "why.family_sponsor_nationalities":
      "The sponsor’s nationality is asked on its own and is never copied from your own passports.",
    "why.family_marriage_registered":
      "Yes, no or not sure is sent as you choose it; no registration status is assumed.",
    "why.family_stepchild_marriage_certificate_confirmed":
      "This proof is checked directly; it is not assumed from your answer about the marriage being registered.",
    "why.family_stepchild_birth_certificate_confirmed":
      "Birth-certificate proof is sent as its own yes or no.",
    "why.family_sponsor_confirmed":
      "Sponsor confirmation is sent as its own yes or no.",
    "why.retirement_basis":
      "This label is not checked on its own. It only chooses which exact questions come next.",
    "why.retirement_undecided_basis":
      "This label is not checked on its own either. It only chooses which exact questions come next, as in the question above.",
    "why.secondhome_basis":
      "This only decides which proof questions follow; the proof itself is what is checked, never this label.",
    "why.secondhome_property_value_usd":
      "The exact value is sent; ownership and tenure are not assumed.",
    "why.secondhome_passive_income_usd":
      "The monthly amount is sent as you enter it and is never estimated from your assets.",
    "why.study_level": "The study level you pick is sent unchanged.",
    "why.study_admission_confirmed":
      "Admission confirmation is sent as its own yes or no.",
    "why.diaspora_connection":
      "This is not part of the check. It is kept only as context for a person to read.",
    "why.other_purpose":
      "None of these labels maps to one checked answer, so this stays as context for a person.",
    "why.other_paid_activity":
      "This broad question has no exact match in the rules, so the answer cannot on its own support a visa path.",
    "why.stay_days":
      "The check reads the exact number of days you plan, instead of guessing from a broad range.",
    "why.review_gate":
      "Every item here is part of the check: the three about immigration history are read by the signed rules, and all of them are disclosures your result must account for.",
  },
  id: {
    "why.in_indonesia":
      "Lokasi Anda saat ini memberi tahu pemeriksaan apakah ini tentang masa tinggal yang sedang berjalan atau rencana mendatang.",
    "why.permit_expiry":
      "Pemeriksaan membutuhkan tanggalnya untuk menilai waktu; halaman ini tidak menentukan jalur pengajuan darinya.",
    "why.current_status_code":
      "Kode status yang tercetak dikirim tanpa perubahan; halaman ini tidak pernah menebaknya dari nama izin.",
    "why.stay_permit_code":
      "Kode yang tercetak dikirim tanpa perubahan, sama seperti daftar kode di atas — halaman ini tidak pernah menebaknya dari nama izin.",
    "why.overstay_days":
      "Jumlah hari overstay aktif ditanyakan tersendiri karena penting untuk keselamatan. Nilai ini tidak pernah dihitung dari tanggal berakhir di browser Anda.",
    "why.wants_onshore_conversion":
      "Jawaban ya atau tidak Anda dikirim apa adanya; tidak ada jalur konversi yang dipilihkan untuk Anda.",
    "why.application_channel":
      "Pilihan Anda dikirim tanpa perubahan. Halaman ini tidak pernah memilih kanal dari tanggal Anda.",
    "why.nationalities":
      "Kewarganegaraan diperiksa persis seperti yang Anda berikan. Beberapa kewarganegaraan tetap terpisah dan tidak pernah ditebak.",
    "why.category":
      "Ini hanya menentukan pertanyaan berikutnya. Hanya pemeriksaan jawaban Anda terhadap aturan bertanggal yang dapat menyatakan apakah suatu jalur visa sesuai.",
    "why.trip_scope":
      "Tujuan yang tumpang tindih perlu dibaca oleh seseorang. Jawaban ini disimpan sebagai konteks dan tidak diubah menjadi hal lain.",
    "why.entry_pattern":
      "Satu kali masuk atau beberapa kali masuk dikirim persis seperti pilihan Anda.",
    "why.sponsor_category":
      "Kategori sponsor dicatat tersendiri. Belum ada aturan dalam kumpulan saat ini yang membacanya — ini hanya menyiapkan data untuk aturan yang akan datang.",
    "why.sponsor_government_invitation":
      "Hanya jawaban ya atau tidak tentang undangan pemerintah yang dikirim.",
    "why.sponsor_government_collaboration":
      "Hanya jawaban ya atau tidak tentang kolaborasi pemerintah yang terkonfirmasi yang dikirim.",
    "why.sponsor_world_figure_invitation":
      "Hanya jawaban ya atau tidak tentang undangan sebagai tokoh dunia yang dikirim.",
    "why.sponsor_diplomatic_household":
      "Hanya jawaban ya atau tidak tentang posisi di rumah tangga diplomat yang dikirim.",
    "why.sponsor_trade_office":
      "Hanya jawaban ya atau tidak tentang penjamin berupa kantor perwakilan dagang yang dikirim.",
    "why.business_activity":
      "Hanya satu jawaban yang mengubah apa yang diperiksa: menjajaki peluang berinvestasi atau membuka usaha diperiksa sebagai tujuan investasi, lalu kami menanyakan beberapa pertanyaan yang menentukannya. Selain itu, rincian ini hanya menentukan apakah seseorang perlu melihat perjalanan Anda — pelatihan dan “kegiatan bisnis lainnya” perlu, jawaban lainnya tidak.",
    "why.business_sponsor_confirmed":
      "Konfirmasi sponsor dikirim sebagai jawaban ya atau tidak tersendiri.",
    "why.work_payer":
      "Hanya apakah pemberi kerja merupakan entitas Indonesia yang dikirim; halaman ini tidak menentukan visa darinya.",
    "why.work_indonesia_compensation":
      "Ini dikirim sebagai sumber gaji Anda; jumlah dan kelayakan tidak disimpulkan darinya.",
    "why.work_sponsor_confirmed":
      "Hanya jawaban ya atau tidak tentang konfirmasi sponsor yang dikirim.",
    "why.remote_clients":
      "Apakah Anda melayani klien di Indonesia dikirim sesuai jawaban Anda; hal ini tidak disimpulkan dari tempat tinggal Anda.",
    "why.remote_employer_country":
      "Kode negara dikirim persis seperti yang dimasukkan; halaman ini tidak mengelompokkannya.",
    "why.investment_vehicle":
      "Ini hanya menentukan pertanyaan berikutnya. Ini tidak pernah memilih jalur visa.",
    "why.investment_pt_pma":
      "Komitmen Anda dikirim sebagai ya atau tidak, tanpa mengandaikan jumlah atau status.",
    "why.investment_capital_idr":
      "Jumlah dikirim sesuai yang Anda masukkan. Tidak ada ambang yang ditampilkan atau diandaikan di sini.",
    "why.investment_amount_usd":
      "Jumlah dikirim sesuai yang Anda masukkan, dalam mata uang yang Anda pilih. Tidak ada ambang yang ditampilkan atau diandaikan di sini, dan tidak ada yang dikonversi.",
    "why.investment_paid_up_capital_idr":
      "Jumlah persis dikirim terpisah dari modal yang Anda rencanakan untuk diinvestasikan.",
    "why.investment_role": "Peran yang Anda pilih dikirim tanpa perubahan.",
    "why.investment_establishes_company":
      "Hanya jawaban ya atau tidak tentang pendirian perusahaan yang dikirim.",
    "why.investment_foreign_branch":
      "Hanya jawaban ya atau tidak tentang kantor cabang atau anak perusahaan dari perusahaan asing yang dikirim.",
    "why.investment_ikn_subsidiary":
      "Hanya jawaban ya atau tidak tentang anak perusahaan di IKN yang dikirim.",
    "why.investment_capital_market_only":
      "Hanya jawaban ya atau tidak tentang investasi yang hanya melalui pasar modal yang dikirim.",
    "why.investment_meets_threshold":
      "Hanya jawaban ya atau tidak yang dikirim. Tidak ada jumlah yang ditampilkan atau diandaikan di sini.",
    "why.family_relation": "Hubungan yang Anda pilih dikirim tanpa perubahan.",
    "why.marital_status":
      "Status perkawinan Anda dikirim persis seperti yang Anda pilih.",
    "why.family_sponsor_nationalities":
      "Kewarganegaraan sponsor ditanyakan tersendiri dan tidak pernah disalin dari paspor Anda.",
    "why.family_marriage_registered":
      "Ya, tidak, atau belum yakin dikirim sesuai pilihan Anda; status pencatatan tidak diandaikan.",
    "why.family_stepchild_marriage_certificate_confirmed":
      "Bukti ini diperiksa langsung; tidak diandaikan dari jawaban Anda tentang pernikahan yang tercatat.",
    "why.family_stepchild_birth_certificate_confirmed":
      "Bukti akta lahir dikirim sebagai jawaban ya atau tidak tersendiri.",
    "why.family_sponsor_confirmed":
      "Konfirmasi sponsor dikirim sebagai jawaban ya atau tidak tersendiri.",
    "why.retirement_basis":
      "Label ini tidak diperiksa tersendiri. Label ini hanya menentukan pertanyaan persis berikutnya.",
    "why.retirement_undecided_basis":
      "Label ini juga tidak diperiksa tersendiri. Label ini hanya menentukan pertanyaan persis berikutnya, sama seperti pertanyaan di atas.",
    "why.secondhome_basis":
      "Ini hanya menentukan pertanyaan bukti berikutnya; buktinya sendiri yang diperiksa, bukan label ini.",
    "why.secondhome_property_value_usd":
      "Nilai persis dikirim; kepemilikan dan bentuk penguasaan tidak diandaikan.",
    "why.secondhome_passive_income_usd":
      "Jumlah bulanan dikirim sesuai yang Anda masukkan dan tidak pernah diperkirakan dari aset Anda.",
    "why.study_level": "Tingkat studi yang Anda pilih dikirim tanpa perubahan.",
    "why.study_admission_confirmed":
      "Konfirmasi penerimaan dikirim sebagai jawaban ya atau tidak tersendiri.",
    "why.diaspora_connection":
      "Ini bukan bagian dari pemeriksaan. Jawaban ini hanya disimpan sebagai konteks untuk dibaca seseorang.",
    "why.other_purpose":
      "Tidak ada label di sini yang sesuai dengan satu jawaban yang diperiksa, sehingga ini tetap menjadi konteks untuk seseorang.",
    "why.other_paid_activity":
      "Pertanyaan luas ini tidak memiliki padanan persis dalam aturan, sehingga jawabannya sendiri tidak dapat mendukung suatu jalur visa.",
    "why.stay_days":
      "Pemeriksaan membaca jumlah hari persis yang Anda rencanakan, bukan menebak dari rentang yang luas.",
    "why.review_gate":
      "Setiap item di sini adalah bagian dari pemeriksaan: tiga item tentang riwayat keimigrasian dibaca oleh aturan yang telah disahkan, dan semuanya merupakan pengungkapan yang harus diperhitungkan dalam hasil Anda.",
  },
} as const;
