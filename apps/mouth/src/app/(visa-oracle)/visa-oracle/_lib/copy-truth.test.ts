import { describe, expect, it } from "vitest";
import { dict } from "./i18n";

// PR-C4-v3: the interview helper copy is judged against what the code does
// (spec-interview-truth-table-c4v3, pack sha256 dcbc12cd…70cf). Each row is the
// reviewed EN and ID sentence of one key. An older, false sentence fails here.
const TRUTH: readonly (readonly [string, string, string])[] = [
  [
    "framing.body",
    "Answer honestly, including “I don’t know.” Nothing here is filed; your answers decide which questions come next and which visas fit.",
    "Jawab dengan jujur, termasuk “Saya tidak tahu.” Tidak ada yang diajukan di sini; jawaban Anda menentukan pertanyaan berikutnya dan visa mana yang sesuai.",
  ],
  [
    "why.in_indonesia",
    "Where you are now decides which questions come next and which options can apply to you.",
    "Lokasi Anda saat ini menentukan pertanyaan berikutnya dan pilihan mana yang dapat berlaku bagi Anda.",
  ],
  [
    "why.permit_expiry",
    "We need the actual date to see how much time you have left. It can change which questions come next.",
    "Kami memerlukan tanggal yang sebenarnya untuk melihat sisa waktu Anda. Tanggal ini dapat mengubah pertanyaan berikutnya.",
  ],
  [
    "why.wants_onshore_conversion",
    "Your yes or no tells us how you plan to proceed. It can change the questions that follow and exclude a visa that cannot be converted inside Indonesia.",
    "Jawaban ya atau tidak Anda menunjukkan bagaimana Anda berencana melanjutkan. Jawaban ini dapat mengubah pertanyaan berikutnya dan mengecualikan visa yang tidak dapat dialihkan di dalam Indonesia.",
  ],
  [
    "q.birth_date.hint",
    "Your date of birth is checked against visa age limits and tells us whether to ask about a parent or guardian.",
    "Tanggal lahir Anda diperiksa terhadap batas usia visa dan menentukan apakah kami perlu bertanya tentang orang tua atau wali.",
  ],
  [
    "lane.urgent.notice",
    "Your permit expires today or within the next two days. We will still check your options, but please contact a Bali Zero advisor today.",
    "Izin tinggal Anda berakhir hari ini atau dalam dua hari ke depan. Kami tetap memeriksa pilihan Anda, tetapi mohon hubungi konsultan Bali Zero hari ini.",
  ],
  [
    "lane.bridging.notice",
    "The date you entered is within seven days. We will still check your options; talk to a Bali Zero advisor soon about your next step.",
    "Tanggal yang Anda masukkan tinggal tujuh hari atau kurang. Kami tetap memeriksa pilihan Anda; segera bicarakan langkah berikutnya dengan konsultan Bali Zero.",
  ],
  [
    "why.trip_scope",
    "If your purposes overlap, your result notes it so you can go through them with a Bali Zero advisor.",
    "Jika tujuan Anda tumpang tindih, hasil Anda mencatatnya agar Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "why.sponsor_category",
    "Who sponsors you can decide which follow-up questions we ask and which visas fit your situation.",
    "Siapa yang mensponsori Anda dapat menentukan pertanyaan lanjutan yang kami ajukan dan visa mana yang sesuai dengan situasi Anda.",
  ],
  [
    "q.business_activity.hint",
    "Describe the activity, not a visa name. Meetings, negotiation, conferences and exploring investment can be assessed here; training or another activity needs a Bali Zero advisor.",
    "Jelaskan kegiatannya, bukan nama visa. Rapat, negosiasi, konferensi, dan penjajakan investasi dapat dinilai di sini; pelatihan atau kegiatan lain memerlukan konsultan Bali Zero.",
  ],
  [
    "why.business_activity",
    "Exploring an investment is assessed as an investment plan, with its own questions. For training or another activity, this tool cannot name a visa; a Bali Zero advisor can help.",
    "Penjajakan investasi dinilai sebagai rencana investasi, dengan pertanyaannya sendiri. Untuk pelatihan atau kegiatan lain, alat ini tidak dapat menyebutkan visa; konsultan Bali Zero dapat membantu.",
  ],
  [
    "why.work_payer",
    "Whether an Indonesian-registered company employs and pays you decides which work or remote-work visas can fit.",
    "Apakah perusahaan yang terdaftar di Indonesia mempekerjakan dan menggaji Anda menentukan visa kerja atau visa kerja jarak jauh mana yang dapat sesuai.",
  ],
  [
    "why.work_indonesia_compensation",
    "Pay from an Indonesian source can exclude some visas, so this answer can change which visas fit. We ask where your pay comes from, not how much.",
    "Penghasilan dari sumber Indonesia dapat mengecualikan beberapa visa, jadi jawaban ini dapat mengubah visa yang sesuai. Kami menanyakan asal penghasilan Anda, bukan jumlahnya.",
  ],
  [
    "why.remote_employer_country",
    "We record the country code exactly as you enter it and do not interpret it.",
    "Kami mencatat kode negara persis seperti yang Anda masukkan dan tidak menafsirkannya.",
  ],
  [
    "why.remote_pt_pma",
    "A committed PT PMA can exclude the remote-worker visa, so this answer can change which visas fit. A yes does not mean approval.",
    "Komitmen PT PMA dapat mengecualikan visa pekerja jarak jauh, jadi jawaban ini dapat mengubah visa yang sesuai. Jawaban ya tidak berarti persetujuan.",
  ],
  [
    "why.investment_vehicle",
    "Property or a bank deposit points to the Second Home visa. Your choice decides which route we look at and which questions come next.",
    "Properti atau deposito bank mengarah ke Visa Rumah Kedua. Pilihan Anda menentukan jalur yang kami periksa dan pertanyaan berikutnya.",
  ],
  [
    "why.investment_pt_pma",
    "Your answer can decide whether the investor visa fits and which questions come next. No amount or status is assumed from it.",
    "Jawaban Anda dapat menentukan apakah visa investor sesuai dan pertanyaan apa yang berikutnya. Tidak ada jumlah atau status yang diasumsikan dari jawaban ini.",
  ],
  [
    "why.investment_amount_usd",
    "We record the amount in the currency you chose. No threshold is shown or assumed here, and nothing is converted.",
    "Kami mencatat jumlahnya dalam mata uang yang Anda pilih. Tidak ada ambang batas yang ditampilkan atau diasumsikan di sini, dan tidak ada yang dikonversi.",
  ],
  [
    "why.retirement_basis",
    "Your choice decides which questions come next and which retirement visas can fit your situation.",
    "Pilihan Anda menentukan pertanyaan berikutnya dan visa pensiun mana yang dapat sesuai dengan situasi Anda.",
  ],
  [
    "why.secondhome_property_value_usd",
    "We record the exact value you give. Ownership and tenure are not assumed.",
    "Kami mencatat nilai persis yang Anda berikan. Kepemilikan dan bentuk penguasaan tidak diasumsikan.",
  ],
  [
    "q.diaspora_connection.hint",
    "Choose the closest match. Your nationality is asked separately.",
    "Pilih yang paling sesuai. Kewarganegaraan Anda ditanyakan secara terpisah.",
  ],
  [
    "why.diaspora_connection",
    "Choosing the multiple-citizenship or ‘another connection’ answer means this tool cannot name a visa; you can discuss your situation with a Bali Zero advisor.",
    "Jika Anda memilih jawaban tentang lebih dari satu kewarganegaraan atau ‘hubungan lain’, alat ini tidak dapat menyebutkan visa; Anda dapat membahas situasi Anda dengan konsultan Bali Zero.",
  ],
  [
    "why.diaspora_documents",
    "This answer does not change which visas this tool finds for you.",
    "Jawaban ini tidak mengubah visa yang ditemukan alat ini untuk Anda.",
  ],
  [
    "q.other_purpose.hint",
    "Choose the closest activity. Transit can be assessed here; for the others, a Bali Zero advisor can assess your plan with you.",
    "Pilih kegiatan yang paling mendekati. Transit dapat dinilai di sini; untuk kegiatan lainnya, konsultan Bali Zero dapat menilai rencana Anda bersama Anda.",
  ],
  [
    "why.other_purpose",
    "Transit can be assessed here. The other activities cannot be assessed automatically, so this tool names no visa for them; a Bali Zero advisor can assess them with you.",
    "Transit dapat dinilai di sini. Kegiatan lainnya tidak dapat dinilai secara otomatis, sehingga alat ini tidak menyebutkan visa untuk kegiatan tersebut; konsultan Bali Zero dapat menilainya bersama Anda.",
  ],
  [
    "q.other_paid_activity.hint",
    "A paid activity is treated as work, so a yes changes the questions that follow.",
    "Kegiatan berbayar diperlakukan sebagai pekerjaan, jadi jawaban ya mengubah pertanyaan berikutnya.",
  ],
  [
    "why.other_paid_activity",
    "A yes is treated as work and a no as an unpaid activity; either answer decides which visas can fit.",
    "Jawaban ya diperlakukan sebagai pekerjaan dan jawaban tidak sebagai kegiatan tidak berbayar; kedua jawaban menentukan visa mana yang dapat sesuai.",
  ],
  [
    "why.category",
    "Your direction decides which questions come next and which visas can fit your plan.",
    "Arah tujuan Anda menentukan pertanyaan berikutnya dan visa mana yang dapat sesuai dengan rencana Anda.",
  ],
  [
    "q.retirement_basis.hint",
    "Pick the basis you can document today. It decides which questions come next.",
    "Pilih dasar yang dapat Anda buktikan hari ini. Pilihan ini menentukan pertanyaan berikutnya.",
  ],
  [
    "lane.expired.notice",
    "Your permit has already expired. We will still check your options; please talk to a Bali Zero advisor about your next step.",
    "Izin tinggal Anda sudah berakhir. Kami tetap memeriksa pilihan Anda; silakan bicarakan langkah berikutnya dengan konsultan Bali Zero.",
  ],
  [
    "why.holds_stay_permit",
    "Your answer decides which questions about your current permit come next.",
    "Jawaban Anda menentukan pertanyaan berikutnya tentang izin tinggal Anda saat ini.",
  ],
  [
    "q.review_gate.hint",
    "Tick everything that applies. Every item you tick is reflected in your result; some, such as a criminal record, mean this tool names no visa and a Bali Zero advisor can help.",
    "Centang semua yang berlaku. Setiap pilihan yang Anda centang tercermin dalam hasil Anda; beberapa, seperti catatan kriminal, membuat alat ini tidak menyebutkan visa apa pun dan konsultan Bali Zero dapat membantu.",
  ],
  [
    "why.guardian_consent",
    "The date of birth shows an applicant under 18, so we ask whether a parent or legal guardian is present. Without one, this tool names no visa.",
    "Tanggal lahir menunjukkan pemohon berusia di bawah 18 tahun, jadi kami menanyakan apakah orang tua atau wali sah hadir. Tanpa mereka, alat ini tidak menyebutkan visa.",
  ],
  [
    "q.current_status_code.opt.other",
    "Another code — ask a Bali Zero advisor",
    "Kode lain — tanyakan kepada konsultan Bali Zero",
  ],
  [
    "assumption.work_payer",
    "You weren’t sure who pays you, so this remains unresolved. You can discuss it with a Bali Zero advisor.",
    "Anda belum yakin siapa yang menggaji Anda, jadi hal ini belum dipastikan. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.remote_clients",
    "You weren’t sure where your clients are based, so this remains unresolved. You can discuss it with a Bali Zero advisor.",
    "Anda belum yakin di mana klien Anda berada, jadi hal ini belum dipastikan. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "question.human_context_notice",
    "This answer may affect the questions or visa options shown.",
    "Jawaban ini dapat memengaruhi pertanyaan atau pilihan visa yang ditampilkan.",
  ],
  [
    "why.review_gate",
    "Your immigration history can affect your options, and everything you select is noted in your result.",
    "Riwayat keimigrasian Anda dapat memengaruhi pilihan Anda, dan semua yang Anda pilih dicatat dalam hasil Anda.",
  ],
  [
    "assumption.in_indonesia",
    "You weren’t sure where you are, so we recorded that as unresolved instead of assuming it. You can discuss it with a Bali Zero advisor.",
    "Anda tidak yakin di mana posisi Anda, jadi kami mencatatnya sebagai hal yang belum dipastikan alih-alih menganggapnya. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_deposit_usd",
    "For this assessment, a bank-deposit amount you cannot confirm counts as zero. You can discuss it with a Bali Zero advisor.",
    "Dalam penilaian ini, jumlah deposito bank yang belum dapat Anda pastikan dihitung sebagai nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_property_value_usd",
    "For this assessment, a property value you cannot confirm counts as zero. You can discuss it with a Bali Zero advisor.",
    "Dalam penilaian ini, nilai properti yang belum dapat Anda pastikan dihitung sebagai nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_passive_income_usd",
    "For this assessment, passive monthly income you cannot confirm counts as zero. You can discuss it with a Bali Zero advisor.",
    "Dalam penilaian ini, penghasilan pasif bulanan yang belum dapat Anda pastikan dihitung sebagai nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_state_bank",
    "If you are unsure whether the deposit is at an Indonesian state-owned bank, this assessment treats that answer as “no”. You can discuss it with a Bali Zero advisor.",
    "Jika Anda belum yakin apakah deposito berada di bank BUMN Indonesia, penilaian ini memperlakukan jawaban tersebut sebagai “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_own_name",
    "If you are unsure whether the entire deposit is in your own name, this assessment treats that answer as “no”. You can discuss it with a Bali Zero advisor.",
    "Jika Anda belum yakin apakah seluruh deposito atas nama Anda sendiri, penilaian ini memperlakukan jawaban tersebut sebagai “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.study_admission_confirmed",
    "If you are unsure whether your admission is confirmed, this assessment treats that answer as “no”. You can discuss it with a Bali Zero advisor.",
    "Jika Anda belum yakin apakah penerimaan Anda sudah dikonfirmasi, penilaian ini memperlakukan jawaban tersebut sebagai “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.study_sponsor_confirmed",
    "If you are unsure whether your study sponsor has confirmed support, this assessment treats that answer as “no”. You can discuss it with a Bali Zero advisor.",
    "Jika Anda belum yakin apakah sponsor studi sudah mengonfirmasi dukungannya, penilaian ini memperlakukan jawaban tersebut sebagai “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.diaspora_documents",
    "If you are unsure whether you can document the connection, your answer is treated as “no”. You can discuss it with a Bali Zero advisor.",
    "Jika Anda belum yakin apakah Anda dapat membuktikan hubungan tersebut dengan dokumen, jawaban Anda diperlakukan sebagai “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.retirement_basis",
    "If you are unsure which basis you can document, the basis is treated as undecided. You can discuss it with a Bali Zero advisor.",
    "Jika Anda belum yakin dasar mana yang dapat Anda buktikan dengan dokumen, dasar tersebut diperlakukan sebagai belum dipilih. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "why.family_sponsor_permit_basis",
    "Some permit bases cannot have a family permit added on top of them. This tool cannot check your answer automatically; you can discuss it with a Bali Zero advisor.",
    "Beberapa dasar izin tinggal tidak dapat menjadi dasar bagi izin keluarga. Alat ini tidak dapat memeriksa jawaban Anda secara otomatis; Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "why.stay_permit_code",
    "We use the code exactly as printed on your permit. We never guess it from the permit’s name.",
    "Kami memakai kode persis seperti yang tercetak pada izin Anda. Kode ini tidak pernah ditebak dari nama izin.",
  ],
  [
    "why.family_stepchild_marriage_certificate_confirmed",
    "We ask about this document directly; your answer is recorded as its own yes or no.",
    "Kami menanyakan dokumen ini secara langsung; jawaban Anda dicatat sebagai jawaban ya atau tidak tersendiri.",
  ],
  [
    "outcome.freshness.UNKNOWN",
    "Check status unknown",
    "Status pemeriksaan tidak diketahui",
  ],
  [
    "outcome.freshness.STALE",
    "This source needs to be checked again.",
    "Sumber ini perlu diperiksa kembali.",
  ],
  [
    "why.birth_date",
    "Some visas have age limits. We check your age against them.",
    "Beberapa visa memiliki batas usia. Kami memeriksa usia Anda terhadap batas tersebut.",
  ],
];

// Sentences the code proved false: a review that does not exist, a rule that
// "does not exist yet", answers that "never reach" anything, a choice that
// "only" selects questions, a direction that "only chooses".
const FALSE_CLAIMS: readonly RegExp[] = [
  /not counted in your plan/i,
  /tidak dihitung dalam rencana/i,
  /no current rule/i,
  /belum ada aturan/i,
  /context for our team/i,
  /konteks untuk tim kami/i,
  /goes to a bali zero advisor/i,
  /for review\./i,
  /may pass your case to a bali zero advisor/i,
  /tidak dipakai untuk memutuskan apa pun secara otomatis/i,
  /diteruskan ke konsultan bali zero untuk ditinjau/i,
  /kasus anda dapat diteruskan ke konsultan/i,
  /visa tidak dipilih berdasarkan/i,
  /alat ini tidak pernah memilih visa/i,
  /hanya menunjukkan proses/i,
  /hanya mencatat apakah/i,
  /always goes to a human/i,
  /only chooses the next/i,
  /only selects the next/i,
  /shorter code list/i,
  /needs human review/i,
  /in front of a person/i,
  /before the assessment continues/i,
  /selalu ditangani manusia/i,
  /more than one citizenship, or another connection/i,
  /lebih dari satu kewarganegaraan, atau hubungan lain/i,
  /being re-checked by our team/i,
  /sedang diperiksa ulang oleh tim kami/i,
  /child visa that ends at 18/i,
  /visa anak yang berakhir di usia 18/i,
  /we assessed this plan as if/i,
  /rencana ini kami nilai seolah/i,
  /code list above/i,
  /registered above/i,
  /daftar kode di atas/i,
  /pernikahan tercatat di atas/i,
  /last check date unknown/i,
  /tanggal pemeriksaan terakhir tidak diketahui/i,
  /with a criminal record, this tool names no visa/i,
  /dengan catatan kriminal, alat ini tidak menyebutkan visa/i,
  /confirms it with you/i,
  /confirms the real figure with you/i,
  /our team reviews it directly/i,
  /akan memastikannya bersama anda/i,
  /akan memastikan angka sebenarnya/i,
  /tim kami yang meninjau langsung/i,
  /kami tetap menilai semua yang bisa dinilai/i,
  /we still assessed everything we could/i,
  /1–2 days left/i,
  /confirms this point with you/i,
  /bear directly on the rules/i,
  /for our team.s context only/i,
  /tinggal 1–2 hari/i,
  /akan memastikan poin ini/i,
  /berpengaruh langsung pada aturan/i,
  /hanya untuk konteks tim kami/i,
  /hanya menentukan pertanyaan berikutnya/i,
  /hanya memilih pertanyaan faktual/i,
  /daftar kode yang lebih pendek/i,
  /perlu tinjauan manusia/i,
  /ditinjau seseorang/i,
  /sebelum penilaian dilanjutkan/i,
  /too close for an automated check/i,
  /terlalu mepet untuk pemeriksaan otomatis/i,
  /not used to decide anything automatically/i,
  /we do not pick a visa from it/i,
  /we only note whether/i,
  /does not pick a conversion path/i,
  /never chooses a visa for you/i,
  /only tells us which process/i,
  /only to check them/i,
  /hanya dipakai untuk memeriksanya/i,
];

const FALSE_SAMPLES: readonly (readonly [string, string])[] = [
  [
    "en",
    "Your choice decides which questions come next. A basis you do not choose, such as a bank deposit, is not counted in your plan.",
  ],
  [
    "id",
    "Pilihan Anda menentukan pertanyaan berikutnya. Dasar yang tidak Anda pilih, misalnya deposito bank, tidak dihitung dalam rencana Anda.",
  ],
  [
    "en",
    "We note the kind of sponsor you have. No current rule uses it yet; this only prepares us for rules that will.",
  ],
  [
    "id",
    "Kami mencatat jenis sponsor Anda. Belum ada aturan saat ini yang memakainya; ini hanya menyiapkan data untuk aturan yang akan datang.",
  ],
  [
    "en",
    "Overlapping purposes call for a Bali Zero advisor’s judgment, so this answer is not used to decide anything automatically.",
  ],
  [
    "id",
    "Tujuan yang tumpang tindih memerlukan penilaian konsultan Bali Zero, jadi jawaban ini tidak dipakai untuk memutuskan apa pun secara otomatis.",
  ],
  [
    "en",
    "You have 1–2 days left. That’s too close for an automated check — a Bali Zero advisor needs to look at this today.",
  ],
  [
    "id",
    "Waktu Anda tinggal 1–2 hari. Ini terlalu mepet untuk pemeriksaan otomatis — konsultan Bali Zero perlu melihat kasus ini hari ini.",
  ],
  [
    "en",
    "The date you entered is within seven days. We may pass your case to a Bali Zero advisor for review, and this tool will not choose a bridging or conversion route for you.",
  ],
  [
    "id",
    "Tanggal yang Anda masukkan tinggal tujuh hari atau kurang. Kasus Anda dapat diteruskan ke konsultan Bali Zero untuk ditinjau, dan alat ini tidak memilihkan jalur bridging atau konversi untuk Anda.",
  ],
  [
    "en",
    "We only use whether the employing entity is Indonesian. We do not pick a visa from it.",
  ],
  [
    "id",
    "Kami hanya memakai apakah pemberi kerja Anda adalah entitas Indonesia. Visa tidak dipilih berdasarkan hal itu.",
  ],
  [
    "en",
    "Answer honestly, including “I don’t know.” Nothing here is filed, and this tool never chooses a visa for you.",
  ],
  [
    "id",
    "Jawab dengan jujur, termasuk “Saya tidak tahu.” Tidak ada yang diajukan di sini, dan alat ini tidak pernah memilih visa untuk Anda.",
  ],
  [
    "en",
    "Your yes or no only tells us which process you intend to follow. It does not pick a conversion path for you.",
  ],
  [
    "id",
    "Jawaban ya atau tidak Anda hanya menunjukkan proses mana yang Anda maksud. Jawaban ini tidak memilihkan jalur konversi.",
  ],
  [
    "en",
    "Some visas have age rules; we use your date of birth only to check them.",
  ],
  [
    "id",
    "Beberapa visa punya syarat usia; tanggal lahir Anda hanya dipakai untuk memeriksanya.",
  ],
  [
    "en",
    "Describe the activity, not a visa name. Meetings, negotiation, conferences and looking into investing can be assessed here; training or another activity goes to a Bali Zero advisor for review.",
  ],
  [
    "id",
    "Jelaskan kegiatannya, bukan nama visa. Rapat, negosiasi, konferensi, dan penjajakan investasi dapat dinilai di sini; pelatihan atau kegiatan lain diteruskan ke konsultan Bali Zero untuk ditinjau.",
  ],
  [
    "en",
    "We only note whether your PT PMA commitment is concrete; a yes does not mean approval.",
  ],
  [
    "id",
    "Kami hanya mencatat apakah komitmen PT PMA Anda sudah konkret; jawaban ya tidak berarti disetujui.",
  ],
  [
    "en",
    "Your direction only chooses the next questions. It doesn’t decide whether a visa path is available — your answers do.",
  ],
  [
    "id",
    "Arah yang Anda pilih hanya menentukan pertanyaan berikutnya. Arah ini tidak menentukan apakah jalur visa tersedia — jawaban Anda yang menentukan.",
  ],
  [
    "en",
    "This only selects the next factual questions; it does not choose a visa.",
  ],
  [
    "id",
    "Ini hanya memilih pertanyaan faktual berikutnya; bukan memilih visa.",
  ],
  [
    "en",
    "Your permit has already expired. Overstay is fixable. It is not the end of your story here — this always goes to a human, and we won’t alarm you with a number on this screen.",
  ],
  [
    "id",
    "Izin tinggal Anda sudah berakhir. Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini — kasus ini selalu ditangani manusia, dan kami tidak akan menampilkan angka yang menakutkan di layar ini.",
  ],
  [
    "en",
    "The E-code catalogue only applies to KITAS/KITAP holders; everyone else answers the shorter code list below.",
  ],
  [
    "id",
    "Katalog kode-E hanya berlaku untuk pemegang KITAS/KITAP; yang lain menjawab daftar kode yang lebih pendek di bawah.",
  ],
  [
    "en",
    "Tick everything that applies — an omission costs you more than a disclosure. Some of these, a criminal record among them, put your case in front of a person before any verdict; the others are attached to your result as conditions our team checks with you before submission.",
  ],
  [
    "id",
    "Centang semua yang berlaku — tidak menyebutkannya lebih merugikan Anda daripada menyebutkannya. Sebagian di antaranya, termasuk catatan kriminal, membuat kasus Anda ditinjau seseorang sebelum ada keputusan; sisanya menyertai hasil Anda sebagai kondisi tersurat yang ditelusuri tim kami bersama Anda sebelum pengajuan.",
  ],
  [
    "en",
    "An applicant under 18 cannot give this consent alone, so Bali Zero asks an adult to confirm they are present before the assessment continues.",
  ],
  [
    "id",
    "Pemohon di bawah 18 tahun tidak dapat memberikan persetujuan ini sendiri, sehingga Bali Zero meminta orang dewasa memastikan kehadirannya sebelum penilaian dilanjutkan.",
  ],
  ["en", "Another code — needs human review"],
  ["id", "Kode lain — perlu tinjauan manusia"],
  [
    "en",
    "You have 1–2 days left. We will still check your options, but please contact a Bali Zero advisor today.",
  ],
  [
    "id",
    "Waktu Anda tinggal 1–2 hari. Kami tetap memeriksa pilihan Anda, tetapi mohon hubungi konsultan Bali Zero hari ini.",
  ],
  [
    "en",
    "You weren’t sure who pays you, so we recorded that as unresolved; we still assessed everything we could, and a Bali Zero advisor confirms this point with you.",
  ],
  [
    "id",
    "Anda tidak yakin siapa yang menggaji Anda, jadi kami mencatatnya sebagai hal yang belum dipastikan; kami tetap menilai semua yang bisa dinilai, dan konsultan Bali Zero akan memastikan poin ini bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure where your clients sit, so we recorded that as unresolved; we still assessed everything we could, and a Bali Zero advisor confirms this point with you.",
  ],
  [
    "id",
    "Anda tidak yakin di mana klien Anda berada, jadi kami mencatatnya sebagai hal yang belum dipastikan; kami tetap menilai semua yang bisa dinilai, dan konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "For our team’s context only — this answer cannot select, rank, add or remove a visa for you.",
  ],
  [
    "id",
    "Hanya untuk konteks tim kami — jawaban ini tidak dapat memilih, mengurutkan, menambah, atau menghapus visa untuk Anda.",
  ],
  [
    "en",
    "Every item here is taken into account: the three immigration-history ones bear directly on the rules, and all of them must be reflected in your result.",
  ],
  [
    "id",
    "Setiap item di sini diperhitungkan: tiga item riwayat keimigrasian berpengaruh langsung pada aturan, dan semuanya harus tercermin dalam hasil Anda.",
  ],
  [
    "en",
    "You weren’t sure where you are, so we recorded that as unresolved instead of assuming it, and a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin di mana posisi Anda, jadi kami mencatatnya sebagai hal yang belum dipastikan alih-alih menganggapnya, dan konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure what bank deposit you can document, so we assessed this plan as if the deposit were zero; a Bali Zero advisor confirms the real figure with you.",
  ],
  [
    "id",
    "Anda tidak yakin berapa deposito bank yang dapat Anda buktikan, jadi rencana ini kami nilai seolah depositonya nol; konsultan Bali Zero akan memastikan angka sebenarnya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure what property value you can document, so we assessed this plan as if the property value were zero; a Bali Zero advisor confirms the real figure with you.",
  ],
  [
    "id",
    "Anda tidak yakin berapa nilai properti yang dapat Anda buktikan, jadi rencana ini kami nilai seolah nilai propertinya nol; konsultan Bali Zero akan memastikan angka sebenarnya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure what passive monthly income you can document, so we assessed this plan as if that income were zero; a Bali Zero advisor confirms the real figure with you.",
  ],
  [
    "id",
    "Anda tidak yakin berapa penghasilan pasif bulanan yang dapat Anda buktikan, jadi rencana ini kami nilai seolah penghasilan itu nol; konsultan Bali Zero akan memastikan angka sebenarnya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure whether the deposit sits at an Indonesian state-owned bank, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin apakah deposito itu ditempatkan di bank BUMN Indonesia, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure whether the full deposit is held in your own name, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin apakah seluruh deposito itu atas nama Anda sendiri, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure whether an Indonesian institution has confirmed your admission, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin apakah institusi di Indonesia sudah mengonfirmasi penerimaan Anda, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure whether the institution or study sponsor has confirmed support, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin apakah institusi atau sponsor studi sudah mengonfirmasi dukungannya, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure whether you can document that connection, so we assessed this plan as if the answer were “no”; a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin apakah Anda dapat membuktikan hubungan tersebut, jadi rencana ini kami nilai seolah jawabannya “tidak”; konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure which basis you can document today, so we assessed this plan as if you had not chosen a basis yet; a Bali Zero advisor confirms it with you.",
  ],
  [
    "id",
    "Anda tidak yakin dasar mana yang dapat Anda buktikan saat ini, jadi rencana ini kami nilai seolah Anda belum memilih dasar; konsultan Bali Zero akan memastikannya bersama Anda.",
  ],
  [
    "en",
    "Some permit bases block a family-reunification permit from being layered on top of them. We can't verify your answer automatically, so our team reviews it directly rather than the system deciding on its own.",
  ],
  [
    "id",
    "Beberapa dasar izin dapat menghalangi penerbitan izin penyatuan keluarga di atasnya. Kami tidak dapat memverifikasi jawaban Anda secara otomatis, sehingga tim kami yang meninjau langsung, bukan sistem yang memutuskan sendiri.",
  ],
  [
    "en",
    "We use the code exactly as printed, the same as in the code list above. We never guess it from the permit’s name.",
  ],
  [
    "id",
    "Kami memakai kode persis seperti yang tercetak, sama seperti pada daftar kode di atas. Kode ini tidak pernah ditebak dari nama izin.",
  ],
  [
    "en",
    "We ask about this document directly. It is not assumed from your answer about the marriage being registered above.",
  ],
  [
    "id",
    "Kami menanyakan dokumen ini secara langsung. Dokumen ini tidak diasumsikan dari jawaban pernikahan tercatat di atas.",
  ],
  [
    "en",
    "Tick everything that applies. Every item you tick is reflected in your result; with a criminal record, this tool names no visa and a Bali Zero advisor can help.",
  ],
  [
    "id",
    "Centang semua yang berlaku. Setiap item yang Anda centang tercermin dalam hasil Anda; dengan catatan kriminal, alat ini tidak menyebutkan visa dan konsultan Bali Zero dapat membantu.",
  ],
  ["en", "Last check date unknown"],
  ["id", "Tanggal pemeriksaan terakhir tidak diketahui"],
  ["en", "Being re-checked by our team"],
  ["id", "Sedang diperiksa ulang oleh tim kami"],
  [
    "en",
    "Some visas have age limits, such as a minimum age for the retirement visa or a child visa that ends at 18; we check your age against them.",
  ],
  [
    "id",
    "Beberapa visa punya batas usia, misalnya usia minimum untuk visa pensiun atau visa anak yang berakhir di usia 18; kami memeriksa usia Anda terhadap batas tersebut.",
  ],
  [
    "en",
    "More than one citizenship, or another connection, means this tool cannot name a visa; a Bali Zero advisor can assess it with you.",
  ],
  [
    "id",
    "Lebih dari satu kewarganegaraan, atau hubungan lain, berarti alat ini tidak dapat menyebutkan visa; konsultan Bali Zero dapat menilainya bersama Anda.",
  ],
  [
    "en",
    "You weren’t sure what bank deposit you can document, so we assessed this plan as if the deposit were zero. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin berapa deposito bank yang dapat Anda buktikan, jadi rencana ini kami nilai seolah depositonya nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure what property value you can document, so we assessed this plan as if the property value were zero. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin berapa nilai properti yang dapat Anda buktikan, jadi rencana ini kami nilai seolah nilai propertinya nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure what passive monthly income you can document, so we assessed this plan as if that income were zero. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin berapa penghasilan pasif bulanan yang dapat Anda buktikan, jadi rencana ini kami nilai seolah penghasilan itu nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure whether the deposit sits at an Indonesian state-owned bank, so we assessed this plan as if the answer were “no”. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin apakah deposito itu ditempatkan di bank BUMN Indonesia, jadi rencana ini kami nilai seolah jawabannya “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure whether the full deposit is held in your own name, so we assessed this plan as if the answer were “no”. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin apakah seluruh deposito itu atas nama Anda sendiri, jadi rencana ini kami nilai seolah jawabannya “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure whether an Indonesian institution has confirmed your admission, so we assessed this plan as if the answer were “no”. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin apakah institusi di Indonesia sudah mengonfirmasi penerimaan Anda, jadi rencana ini kami nilai seolah jawabannya “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure whether the institution or study sponsor has confirmed support, so we assessed this plan as if the answer were “no”. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin apakah institusi atau sponsor studi sudah mengonfirmasi dukungannya, jadi rencana ini kami nilai seolah jawabannya “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure whether you can document that connection, so we assessed this plan as if the answer were “no”. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin apakah Anda dapat membuktikan hubungan tersebut, jadi rencana ini kami nilai seolah jawabannya “tidak”. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "en",
    "You weren’t sure which basis you can document today, so we assessed this plan as if you had not chosen a basis yet. You can discuss it with a Bali Zero advisor.",
  ],
  [
    "id",
    "Anda tidak yakin dasar mana yang dapat Anda buktikan saat ini, jadi rencana ini kami nilai seolah Anda belum memilih dasar. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
];

describe("interview helper copy tells the truth about what an answer does", () => {
  it.each(TRUTH)(
    "%s carries the reviewed EN and ID sentences",
    (key, en, id) => {
      expect(dict.en[key as keyof typeof dict.en]).toBe(en);
      expect(dict.id[key as keyof typeof dict.id]).toBe(id);
    },
  );

  it("no helper key carries a sentence the code proved false", () => {
    const offenders: string[] = [];
    for (const language of ["en", "id"] as const) {
      for (const [key, value] of Object.entries(dict[language])) {
        if (!/^(q|why|lane|framing|assumption)\./.test(key)) continue;
        for (const re of FALSE_CLAIMS) {
          // Verified TRUE by the truth table: the unchosen Second Home basis is zeroed.
          // Not in the sweep: the penjamin note keeps its own past-tense wording.
          if (
            key === "assumption.retirement_penjamin_confirmed" &&
            /assessed this plan|nilai seolah/.test(String(re))
          )
            continue;
          if (
            key === "why.secondhome_basis" &&
            /counted|dihitung/.test(String(re))
          )
            continue;
          if (re.test(value)) offenders.push(`${language}:${key} ~ ${re}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the false-claim list is guilty on the old sentences (it would have failed the old copy)", () => {
    for (const [, sample] of FALSE_SAMPLES) {
      expect(FALSE_CLAIMS.some((re) => re.test(sample))).toBe(true);
    }
  });
});
