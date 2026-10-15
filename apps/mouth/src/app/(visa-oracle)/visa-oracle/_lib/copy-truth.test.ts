import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import { dict } from "./i18n";
import { SUPPORT_REASON_COPY } from "./engine-adapter";

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
    "q.sponsor_world_figure_invitation",
    "Do you have an invitation letter from an Indonesian central-government agency inviting you as a world figure — a person of international standing?",
    "Apakah Anda memiliki surat undangan dari instansi pemerintah pusat Indonesia yang mengundang Anda sebagai tokoh dunia — seseorang dengan reputasi internasional?",
  ],
  [
    "q.sponsor_world_figure_invitation.hint",
    "Answer yes only if the invitation letter is from an Indonesian central-government agency and invites you in that capacity.",
    "Jawab ya hanya jika surat undangan tersebut berasal dari instansi pemerintah pusat Indonesia dan mengundang Anda dalam kapasitas tersebut.",
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
    "why.remote_annual_income_usd",
    "The remote-worker visa (E33G) has a yearly income requirement. The amount is used exactly as you enter it.",
    "Visa pekerja jarak jauh (E33G) memiliki persyaratan penghasilan tahunan. Jumlah ini digunakan persis seperti yang Anda masukkan.",
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
    "Jawaban Anda dapat menentukan apakah visa investor sesuai dan pertanyaan apa yang muncul berikutnya. Tidak ada jumlah atau status yang diasumsikan dari jawaban ini.",
  ],
  [
    "why.investment_amount_usd",
    "We record the amount in the currency you chose. No threshold is shown or assumed here, and nothing is converted.",
    "Kami mencatat jumlahnya dalam mata uang yang Anda pilih. Tidak ada batas minimum yang ditampilkan atau diasumsikan di sini, dan tidak ada yang dikonversi.",
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
    "Dalam penilaian ini, jumlah deposito bank yang belum dapat Anda konfirmasi dihitung sebagai nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_property_value_usd",
    "For this assessment, a property value you cannot confirm counts as zero. You can discuss it with a Bali Zero advisor.",
    "Dalam penilaian ini, nilai properti yang belum dapat Anda konfirmasi dihitung sebagai nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
  ],
  [
    "assumption.secondhome_passive_income_usd",
    "For this assessment, monthly income or allowance you cannot confirm counts as zero. You can discuss it with a Bali Zero advisor.",
    "Dalam penilaian ini, penghasilan atau tunjangan bulanan yang belum dapat Anda konfirmasi dihitung sebagai nol. Anda dapat membahasnya dengan konsultan Bali Zero.",
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
  [
    "assumption.retirement_penjamin_confirmed",
    "If you are unsure whether you have a penjamin, this assessment treats that answer as “no”; Bali Zero can act as your penjamin.",
    "Jika Anda belum yakin apakah Anda sudah memiliki penjamin, penilaian ini memperlakukan jawaban tersebut sebagai “tidak”; Bali Zero dapat bertindak sebagai penjamin Anda.",
  ],
  [
    "q.retirement_basis.opt.family_sponsor",
    "A penjamin supports my application",
    "Permohonan saya didukung oleh penjamin",
  ],
  [
    "q.retirement_undecided_basis.opt.family_sponsor",
    "A penjamin supports my application",
    "Permohonan saya didukung oleh penjamin",
  ],
  [
    "q.secondhome_passive_income_usd",
    "What monthly income or allowance can you document?",
    "Berapa penghasilan atau tunjangan bulanan yang dapat Anda buktikan?",
  ],
  [
    "q.secondhome_passive_income_usd.hint",
    "Immigration asks for documentary proof of income or an allowance. Enter the exact whole-dollar monthly amount.",
    "Imigrasi meminta bukti dokumen penghasilan atau tunjangan. Masukkan jumlah bulanan dolar bulat yang tepat.",
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
  // I-M03 (2026-10-15): the Golden Visa reasons once promised an advisor
  // action ("We confirm ..."); the advisor is offered ("can"), never promised.
  /we confirm/i,
  /kami mengonfirmasi/i,
  /kami memastikan/i,
  /in front of a person/i,
  /before the assessment continues/i,
  /selalu ditangani manusia/i,
  /yang belum dapat anda pastikan/i,
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
  /sponsored by that diplomat/i,
  /diplomat tersebut sebagai penjamin/i,
  /sponsored by a government body/i,
  /penjamin instansi pemerintah/i,
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
  // The advisor is offered, never promised (see advisor-offer.test.ts).
  /we confirm the documents/i,
  /kami memastikan dokumen/i,
  /confirmed by a bali zero advisor/i,
  /dipastikan oleh konsultan/i,
];

const FALSE_SAMPLES: readonly (readonly [string, string])[] = [
  [
    "en",
    "Send it to a Bali Zero advisor on WhatsApp: we confirm the documents, the timing and the quote.",
  ],
  ["id", "Harga jalur ini dipastikan oleh konsultan Bali Zero."],
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
  [
    "en",
    "You weren’t sure whether you have a penjamin, so we assessed this plan as if the answer were “no”; Bali Zero can act as your penjamin.",
  ],
  [
    "id",
    "Anda tidak yakin apakah Anda sudah memiliki penjamin, jadi rencana ini kami nilai seolah jawabannya “tidak”; Bali Zero dapat bertindak sebagai penjamin Anda.",
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

describe("E23U / E23V support reasons restate what the visitor told us", () => {
  const E23U = SUPPORT_REASON_COPY.E23U_DIPLOMATIC_HOUSEHOLD_ELIGIBLE;
  const E23V = SUPPORT_REASON_COPY.E23V_TRADE_OFFICE_ELIGIBLE;

  it("E23U names the individual sponsor and the diplomatic household, in EN and ID", () => {
    expect(E23U.en).toBe(
      "You told us your sponsor is an individual and the role is in a foreign diplomat's household — the Working Visa — Foreign Diplomat House Assistant (E23U).",
    );
    expect(E23U.id).toBe(
      "Anda menyatakan penjamin Anda perorangan dan posisi ini berada di rumah tangga diplomat asing — Visa Kerja Asisten Rumah Tangga Diplomat Asing (E23U).",
    );
  });

  it("E23V names the government sponsor and the trade or economic office, in EN and ID", () => {
    expect(E23V.en).toBe(
      "You told us your sponsor is a government body and a foreign trade or economic representative office in Indonesia — the Working Visa — Trade and Economic Office (E23V).",
    );
    expect(E23V.id).toBe(
      "Anda menyatakan penjamin Anda instansi pemerintah dan kantor perwakilan dagang atau ekonomi asing di Indonesia — Visa Kerja Kantor Dagang dan Ekonomi (E23V).",
    );
  });

  it("neither sentence states a sponsor identity as law", () => {
    const offenders: string[] = [];
    for (const [code, copy] of [
      ["E23U", E23U],
      ["E23V", E23V],
    ] as const) {
      for (const language of ["en", "id"] as const) {
        for (const re of FALSE_CLAIMS) {
          if (re.test(copy[language]))
            offenders.push(`${code}:${language} ~ ${re}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the sponsor-as-law bans are guilty on the old sentences", () => {
    for (const old of [
      "Employment for a foreign diplomat's household, sponsored by that diplomat as an individual",
      "dengan diplomat tersebut sebagai penjamin perorangan",
      "sponsored by a government body — the Working Visa",
      "dengan penjamin instansi pemerintah",
    ]) {
      expect(FALSE_CLAIMS.some((re) => re.test(old))).toBe(true);
    }
  });
});

describe("E23U / E23V sentences follow the seq-28 rule predicates", () => {
  const PACK = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../../../../..",
    "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-028.source.json",
  );
  type Leaf = { fact?: string; value?: unknown; values?: unknown };
  const rule = (id: string) => {
    const pack = JSON.parse(fs.readFileSync(PACK, "utf-8")) as {
      rules: { rule_id: string; when: { args: Leaf[] } }[];
    };
    const found = pack.rules.find((r) => r.rule_id === id);
    if (!found) throw new Error(`rule ${id} missing from seq-28 pack`);
    return found.when.args.map(
      (a) => `${a.fact}=${JSON.stringify(a.value ?? a.values)}`,
    );
  };

  it("el.e23u.diplomatic-household checks an individual sponsor and the diplomatic household", () => {
    expect(rule("el.e23u.diplomatic-household")).toEqual([
      'intent.purposes=["EMPLOYMENT"]',
      'sponsor.type="INDIVIDUAL"',
      "sponsor.diplomatic_household=true",
    ]);
  });

  it("el.e23v.trade-office checks a government sponsor and the trade office", () => {
    expect(rule("el.e23v.trade-office")).toEqual([
      'intent.purposes=["EMPLOYMENT"]',
      'sponsor.type="GOVERNMENT"',
      "sponsor.trade_office=true",
    ]);
  });

  it("the qualifiers on the trade office are the wording of the question the visitor answered", () => {
    expect(dict.en["q.sponsor_trade_office"]).toContain(
      "foreign trade or economic representative office in Indonesia",
    );
    expect(SUPPORT_REASON_COPY.E23V_TRADE_OFFICE_ELIGIBLE.en).toContain(
      "foreign trade or economic representative office in Indonesia",
    );
  });
});

describe("the retirement basis and income questions use the official page's words", () => {
  const BASIS = [
    "q.retirement_basis.opt.family_sponsor",
    "q.retirement_undecided_basis.opt.family_sponsor",
  ] as const;
  const KEYS = [
    ...BASIS,
    "q.secondhome_passive_income_usd",
    "q.secondhome_passive_income_usd.hint",
  ] as const;

  it("the basis options say penjamin and no longer say family sponsor", () => {
    for (const key of BASIS) {
      expect(dict.en[key]).toBe("A penjamin supports my application");
      expect(dict.id[key]).toBe("Permohonan saya didukung oleh penjamin");
    }
  });

  it("the income question names income or an allowance and anchors on no figure", () => {
    expect(dict.en["q.secondhome_passive_income_usd"]).toBe(
      "What monthly income or allowance can you document?",
    );
    expect(dict.id["q.secondhome_passive_income_usd"]).toBe(
      "Berapa penghasilan atau tunjangan bulanan yang dapat Anda buktikan?",
    );
    expect(dict.en["q.secondhome_passive_income_usd.hint"]).toMatch(
      /^Immigration asks for documentary proof of income or an allowance\./,
    );
    expect(dict.id["q.secondhome_passive_income_usd.hint"]).toMatch(
      /^Imigrasi meminta bukti dokumen penghasilan atau tunjangan\./,
    );
    for (const key of KEYS) {
      expect(dict.en[key]).not.toMatch(/\d/);
      expect(dict.id[key]).not.toMatch(/\d/);
    }
  });

  it("the same journey no longer calls the income only passive", () => {
    for (const key of [
      "q.retirement_basis.opt.passive_income",
      "q.secondhome_passive_income_usd.label",
      "assumption.secondhome_passive_income_usd",
    ] as const) {
      expect(dict.en[key]).not.toMatch(/passive/i);
      expect(dict.id[key]).not.toMatch(/pasif/i);
      expect(dict.en[key]).toMatch(/allowance/);
      expect(dict.id[key]).toMatch(/tunjangan/);
    }
  });
});

// I-M03 / I-T01 / I-T03 (2026-10-15): the investor copy says what the visitor
// declared and what the official page for that code asks. Judged per ENTITY
// (reason code -> sentence), with a guilt row (the claim the code proved
// false) and an innocence row (the sentence the page does back) for each.
describe("Golden Visa reasons say what was declared and what the official page asks", () => {
  const GOLDEN = [
    "E28B_COMPANY_ESTABLISHMENT_ELIGIBLE",
    "E28C_CAPITAL_MARKET_ELIGIBLE",
    "E28D_BRANCH_OR_SUBSIDIARY_ELIGIBLE",
    "E28F_IKN_SUBSIDIARY_ELIGIBLE",
  ] as const;
  const PAGE = (code: string) =>
    `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/${code}`;

  it.each(GOLDEN)(
    "%s offers the advisor with can/dapat, promises no check, names no figure",
    (key) => {
      const { en, id } = SUPPORT_REASON_COPY[key];
      expect(en).toMatch(/A Bali Zero advisor can go through/);
      expect(id).toMatch(/Konsultan Bali Zero dapat membahas/);
      for (const re of [/we confirm/i, /we check/i, /kami mengonfirmasi/i]) {
        expect(en).not.toMatch(re);
        expect(id).not.toMatch(re);
      }
      // No amount of any currency: the pack holds no figure, the page does.
      // The product code and the 90-day deadline are the only digits allowed.
      for (const text of [en, id]) {
        const bare = text
          .replace(/E28[A-F]/g, "")
          .replace(/90 (days|hari)/, "");
        expect(bare).not.toMatch(/\d|US\$|\bUSD\b|\bIDR\b|\bRp\b/);
      }
    },
  );

  it.each([
    ["E28B_COMPANY_ESTABLISHMENT_ELIGIBLE", "E28B"],
    ["E28C_CAPITAL_MARKET_ELIGIBLE", "E28C"],
    ["E28D_BRANCH_OR_SUBSIDIARY_ELIGIBLE", "E28D"],
    ["E28F_IKN_SUBSIDIARY_ELIGIBLE", "E28F"],
  ])("%s points at its own official page, and only its own", (key, code) => {
    const { en, id } = SUPPORT_REASON_COPY[key];
    for (const text of [en, id]) {
      expect(text).toContain(PAGE(code));
      for (const other of ["E28A", "E28B", "E28C", "E28D", "E28F"]) {
        if (other !== code) expect(text).not.toContain(PAGE(other));
      }
    }
  });

  it("turnover appears on E28B only (its page asks audited turnover); E28C, E28D and E28F have none", () => {
    const turnover = /turnover|omzet/i;
    // Guilt: the E28D reason once said the advisor confirms investment AND
    // turnover figures; its page asks only the foreign company's commitment.
    for (const key of GOLDEN.filter((k) => !k.startsWith("E28B"))) {
      expect(SUPPORT_REASON_COPY[key].en).not.toMatch(turnover);
      expect(SUPPORT_REASON_COPY[key].id).not.toMatch(turnover);
    }
    // Innocence: E28B's page does ask audited proof of shareholding and turnover.
    const b = SUPPORT_REASON_COPY.E28B_COMPANY_ESTABLISHMENT_ELIGIBLE;
    expect(b.en).toMatch(
      /audited proof of shareholding .* outside Indonesia .* turnover/,
    );
    expect(b.id).toMatch(
      /bukti audit kepemilikan saham .* di luar Indonesia dan omzet/,
    );
  });

  it("E28C names Indonesian government bonds, shares of companies listed in Indonesia and mutual funds", () => {
    const c = SUPPORT_REASON_COPY.E28C_CAPITAL_MARKET_ELIGIBLE;
    expect(c.en).toContain(
      "Indonesian government bonds, shares of companies listed in Indonesia, or mutual funds",
    );
    expect(c.id).toContain(
      "obligasi pemerintah Indonesia, saham perusahaan terbuka di Indonesia, atau reksa dana",
    );
  });

  it("E28D and E28F name the foreign company's commitment within 90 days; E28F names the foreign-parent condition and Ibu Kota Nusantara", () => {
    const d = SUPPORT_REASON_COPY.E28D_BRANCH_OR_SUBSIDIARY_ELIGIBLE;
    expect(d.en).toContain("foreign company's investment commitment");
    expect(d.en).toContain("within 90 days of your entry");
    expect(d.id).toContain("komitmen investasi dari perusahaan asing");
    expect(d.id).toContain("dalam 90 hari sejak tanggal masuk Anda");
    expect(d.id).not.toContain("hal itu");
    const f = SUPPORT_REASON_COPY.E28F_IKN_SUBSIDIARY_ELIGIBLE;
    expect(f.en).toContain(
      "branch or subsidiary of a company outside Indonesia",
    );
    expect(f.id).toContain(
      "cabang atau anak perusahaan dari perusahaan di luar Indonesia",
    );
    expect(f.en).toContain("Ibu Kota Nusantara (IKN)");
    expect(f.id).toContain("Ibu Kota Nusantara (IKN)");
    // The place phrase is the official "Ibu Kota"; the pack's product name
    // after the dash stays verbatim until the pack renames it.
    expect(f.id.split(" — ")[0]).not.toContain("Ibukota");
  });
});

describe("investor interview questions say what the official pages ask, and anchor on no figure", () => {
  const INVESTOR_Q = [
    "q.investment_vehicle.opt.capital_market",
    "q.investment_capital_market_only",
    "q.investment_capital_market_only.hint",
    "q.investment_ikn_subsidiary",
    "q.investment_ikn_subsidiary.hint",
    "q.investment_establishes_company.hint",
    "q.investment_meets_threshold",
    "q.investment_meets_threshold.hint",
    "why.investment_meets_threshold",
  ] as const;

  it("no investor question or hint carries an amount of any currency (the only digits allowed are the 90-day deadline)", () => {
    for (const language of ["en", "id"] as const) {
      for (const key of INVESTOR_Q) {
        const text = dict[language][key].replace(/90 (days|hari)/, "");
        expect(text, `${language}:${key}`).not.toMatch(
          /\d|US\$|\bUSD\b|\bIDR\b|\bRp\b/,
        );
      }
    }
  });

  it("capital-market option and question name the three instruments the E28C page lists", () => {
    for (const key of [
      "q.investment_vehicle.opt.capital_market",
      "q.investment_capital_market_only",
    ] as const) {
      expect(dict.en[key]).toContain("Indonesian government bonds");
      expect(dict.en[key]).toContain("listed in Indonesia");
      expect(dict.en[key]).toContain("mutual funds");
      expect(dict.id[key]).toContain("obligasi pemerintah Indonesia");
      expect(dict.id[key]).toContain("perusahaan terbuka di Indonesia");
      expect(dict.id[key]).toContain("reksa dana");
    }
  });

  it("the IKN question asks for a branch or subsidiary of a company outside Indonesia in Ibu Kota Nusantara", () => {
    expect(dict.en["q.investment_ikn_subsidiary"]).toContain(
      "branch or subsidiary of a company outside Indonesia",
    );
    expect(dict.en["q.investment_ikn_subsidiary"]).toContain(
      "Ibu Kota Nusantara",
    );
    expect(dict.id["q.investment_ikn_subsidiary"]).toContain(
      "kantor cabang atau anak perusahaan dari perusahaan di luar Indonesia",
    );
    expect(dict.id["q.investment_ikn_subsidiary"]).toContain(
      "Ibu Kota Nusantara",
    );
    expect(dict.en["tree.investment_ikn_subsidiary"]).toMatch(
      /branch or subsidiary/i,
    );
    expect(dict.en["q.investment_establishes_company.hint"]).toMatch(
      /branch or subsidiary/,
    );
    expect(dict.id["q.investment_establishes_company.hint"]).toMatch(
      /cabang atau anak perusahaan/,
    );
  });

  it("the threshold question asks about a commitment within 90 days, with no turnover clause and no 'route you chose'", () => {
    const en = dict.en["q.investment_meets_threshold"];
    const id = dict.id["q.investment_meets_threshold"];
    expect(en).toContain("Can you commit");
    expect(en).toContain("within 90 days of entering Indonesia");
    expect(id).toContain("Dapatkah Anda berkomitmen");
    expect(id).toContain("dalam 90 hari sejak masuk ke Indonesia");
    for (const text of [
      en,
      id,
      dict.en["q.investment_meets_threshold.hint"],
      dict.id["q.investment_meets_threshold.hint"],
    ]) {
      expect(text).not.toMatch(
        /turnover|omzet|route you chose|jalur yang Anda pilih/i,
      );
    }
  });
});

describe("natural Bahasa Indonesia in the investor interview and confirmation screen (I-T03)", () => {
  const INVESTOR_ID_KEYS = Object.keys(dict.id).filter((key) =>
    /^(q|why)\.(investment_|unit\.idr)/.test(key),
  );

  it("the investor keys carry no calque the glossary retired", () => {
    expect(INVESTOR_ID_KEYS.length).toBeGreaterThan(30);
    for (const key of INVESTOR_ID_KEYS) {
      const value = dict.id[key as keyof typeof dict.id];
      expect(value, key).not.toMatch(
        /antar mata uang|mengomitmenkan|dikomitmenkan|ambang batas|utuh|yang berikutnya/,
      );
    }
  });

  it.each([
    [
      "q.investment_capital_idr.hint",
      "Masukkan jumlah rupiah bulat yang tepat dan dapat Anda dukung dengan bukti.",
    ],
    [
      "q.investment_amount_usd.hint",
      "Masukkan jumlah dolar bulat yang tepat dan dapat Anda dukung dengan bukti.",
    ],
    ["q.unit.idr", "Rp"],
    ["confirmation.group.details", "Detail rencana Anda"],
  ] as const)("%s reads %j", (key, expected) => {
    expect(dict.id[key]).toBe(expected);
  });
});
