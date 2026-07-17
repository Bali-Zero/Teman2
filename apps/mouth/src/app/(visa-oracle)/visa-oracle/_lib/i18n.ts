/**
 * Visa Oracle v2 — EN/ID copy dictionary.
 *
 * Deliberately NOT the global `src/i18n` provider (spec item 30 — avoids
 * the I18nProvider lint chain; this route is a standalone experience).
 * EN is the canonical key set; `id` is typed `Record<Keys, string>` so a
 * missing/extra key in Indonesian is a TypeScript error at build time
 * (`i18n.test.ts` re-checks this at runtime as defense-in-depth).
 *
 * ID register (design doc §3/§4): body-first, warm-formal, "Anda" never
 * "kamu", Imigrasi's own terminology natively — not machine-translated.
 */
import type { Language } from "./flow";

const en = {
  "framing.title": "A map, not an application",
  "framing.body":
    "Answer honestly, including “I don’t know.” Nothing here is filed, and nothing is decided for you — this is a demonstration with sample data.",
  "framing.cta": "Start",

  "q.in_indonesia": "Are you in Indonesia right now?",
  "q.in_indonesia.hint": "This decides which questions matter next.",
  "q.in_indonesia.opt.yes": "Yes, I’m here",
  "q.in_indonesia.opt.no": "No, I’m planning ahead",

  "q.permit_expiry": "When does your current stay permit expire?",
  "q.permit_expiry.hint":
    "The date on your visa or ITAS/KITAS — not your passport.",
  "q.permit_expiry.label": "Expiry date",
  "why.permit_expiry":
    "Bridging Visa and any conversion has a hard filing window before your permit expires.",

  "lane.expired.notice":
    "Your permit has already expired. Overstay is fixable. It is not the end of your story here — this always goes to a human, and we won’t alarm you with a number on this screen.",
  "lane.urgent.notice":
    "You have 1–2 days left. That’s too close for an automated routing — a Bali Zero advisor needs to look at this today.",
  "lane.bridging.notice":
    "Your window is close. Bridging Visa must be filed at least 3 days before expiry — keep that in mind as you answer.",
  "lane.extend.notice":
    "You have time to compare Extend and Convert side by side.",
  "lane.planning.notice": "Plenty of runway — this is planning, not urgency.",

  "q.category": "What brings you to Indonesia?",
  "q.category.hint": "Pick the closest fit — you can refine it next.",
  "why.category":
    "Indonesia’s visa index was reclassified in 2025; the category decides which document family applies.",
  "q.category.opt.tourism": "Tourism & short visit",
  "q.category.opt.business": "Business (no work)",
  "q.category.opt.work": "Work & employment",
  "q.category.opt.invest": "Invest & golden",
  "q.category.opt.remote": "Remote worker",
  "q.category.opt.family": "Family & marriage",
  "q.category.opt.retirement": "Retirement & second home",
  "q.category.opt.study": "Study",
  "q.category.opt.diaspora": "Diaspora & ex-WNI",
  "q.category.opt.other": "Something else",

  "q.work_payer":
    "Will an Indonesian-registered company employ and pay you here?",
  "q.work_payer.hint":
    "Not “do you need a work KITAS” — who actually pays you.",
  "why.work_payer":
    "The sponsor/guarantor rules changed in 2025 and hinge on who the payer is.",
  "q.work_payer.opt.yes": "Yes, an Indonesian entity pays me",
  "q.work_payer.opt.no": "No, I’m paid from abroad",

  "q.remote_clients": "Where do your clients or employer sit?",
  "q.remote_clients.hint":
    "This is what separates a remote-worker lane from a work lane.",
  "why.remote_clients":
    "Remote-worker tolerance depends on the client/employer’s location, not yours.",
  "q.remote_clients.opt.foreign": "Abroad — they pay me from outside Indonesia",
  "q.remote_clients.opt.indonesian":
    "Indonesia — I’m effectively employed here",
  "q.remote_clients.opt.mixed": "A mix of both",

  "q.remote_income": "Does your income clear the remote-worker floor?",
  "q.remote_income.hint":
    "Below the floor doesn’t rule you out — it changes what we can offer.",
  "why.remote_income":
    "The income floor is set in the same 2025 sponsor/guarantor rules.",
  "q.remote_income.opt.above": "Yes, comfortably above it",
  // Finding #6 (adversarial review 2026-07-17): the old copy folded "or
  // I'm not sure" into the "No" option, colliding with the dedicated
  // NotSure trigger this question already renders — a user unsure of
  // their income had two different, inconsistent ways to say so (a
  // silent-downgrade "below" answer vs. the human-review NotSure path).
  // "below" now means only an honest "No"; uncertainty routes through
  // NotSure, exactly like every other sensitive question.
  "q.remote_income.opt.below": "No, it doesn’t clear the floor",
  "q.remote_income.courtesy_note":
    "One thing worth knowing, not a gate: crossing about 183 days in Indonesia can change your tax status. That’s something you deserve to know before you choose — it doesn’t disqualify anything here.",

  "q.tourism_duration": "How long are you planning to stay?",
  "q.tourism_duration.hint": "A rough answer is fine.",
  "q.tourism_duration.opt.short": "Up to 30 days",
  "q.tourism_duration.opt.medium": "31–60 days",
  "q.tourism_duration.opt.extended": "60+ days",

  "q.review_gate": "A few honest questions before we show you anything",
  "q.review_gate.hint":
    "Any of these means a human reviews your case — never an automated verdict. That’s a feature, not a penalty.",
  "why.review_gate":
    "These are personal-data categories under Indonesia’s data protection law, handled with extra care and only ever by a person.",
  "q.review_gate.opt.none": "None of these apply to me",
  "q.review_gate.opt.flagged": "One or more applies",
  // Finding #5 (adversarial review 2026-07-17): "none" is now a first-class
  // checklist item (REVIEW_GATE_ITEMS[0] in tree.ts), mutually exclusive
  // with the real flags below — this is its checklist label.
  "q.review_gate.item.none": "None of these apply to me",
  "q.review_gate.item.criminal_record": "A criminal record, anywhere",
  "q.review_gate.item.health_flag":
    "A health condition immigration may ask about",
  "q.review_gate.item.prior_refusal": "A prior visa refusal or denial",
  "q.review_gate.item.overstay_or_blacklist":
    "A past overstay or blacklist entry",
  "q.review_gate.item.not_certain": "I’m not certain about any of the above",
  "q.review_gate.none_selected": "None of these apply to me",

  "notsure.trigger": "Not sure?",
  "assumption.in_indonesia":
    "You weren’t sure where you are — we assumed you’re in Indonesia, the safer read.",
  "assumption.tourism_duration":
    "You weren’t sure how long you’re staying — we assumed a short visit.",
  "assumption.work_payer":
    "You weren’t sure who pays you — we’re holding this for a Bali Zero advisor rather than guessing.",
  "assumption.remote_clients":
    "You weren’t sure where your clients sit — we’re holding this for a human rather than guessing.",
  "assumption.remote_income":
    "You weren’t sure about your income — we’re holding this for a human rather than guessing.",

  "whyweask.trigger": "Why we ask",
  "whyweask.trigger.aria": "Why we ask this question",
  "whyweask.regulation_prefix": "Source (sample): {{regulation}}",

  "back.button": "Back",
  "restart.button": "Start over",
  "verdict.edit_answers": "Edit answers",

  "tree.edit_aria": "Edit answer: {{question}}",
  "tree.framing": "Start",
  "tree.in_indonesia": "Where you are",
  "tree.permit_expiry": "Permit window",
  "tree.category": "Category",
  "tree.work_payer": "Who pays you",
  "tree.remote_clients": "Where clients sit",
  "tree.remote_income": "Income floor",
  "tree.tourism_duration": "Length of stay",
  "tree.review_gate": "Safety check",
  "tree.confirmation": "Your answers",
  "tree.verdict": "Verdict",
  "tree.sr_path_label": "Your path so far",
  "tree.sr_status.done": "answered",
  "tree.sr_status.current": "current step",
  "tree.sr_status.pending": "not yet reached",
  "tree.sr_status.pruned": "ruled out",

  "paths.counter.label": "{{count}} paths",
  "paths.counter.aria": "{{count}} paths remaining",

  "confirmation.title": "Here’s what you told us",
  "confirmation.your_answers": "Your answers",
  "confirmation.assumptions_title": "Assumptions we made",
  "confirmation.edit": "Edit",
  "confirmation.paths_remaining": "{{count}} paths remain",
  "confirmation.price_preview":
    "One all-inclusive price follows — never a fee breakdown.",
  "confirmation.cta": "See my options",

  "verdict.headline.SUPPORTED_CANDIDATES": "Here’s the strongest fit",
  "verdict.headline.HUMAN_REVIEW_REQUIRED":
    "This needs a human, not an algorithm",
  "verdict.headline.NO_SUPPORTED_PATH":
    "This exact path isn’t supported — here’s what instead",
  "verdict.headline.TEMPORARILY_UNAVAILABLE":
    "This lane isn’t modeled in the prototype yet",
  "verdict.headline.NEEDS_INPUT": "A little more to go",
  "verdict.eligibility.eligible": "Eligible",
  "verdict.eligibility.likely": "Likely",
  "verdict.eligibility.conditional": "Conditional",
  "verdict.eligibility.likely-not": "Likely not",
  // Finding #18 (adversarial review 2026-07-17): the old copy read as a
  // claim about THIS run ("a real case gets a signed, cited answer") —
  // easy to misread as "this demo's numbers are that answer". Rewritten
  // to a conditional that can never be mistaken for a claim about the
  // sample data on screen.
  "verdict.state_description.SUPPORTED_CANDIDATES":
    "Based on what you told us, sample data below. A real case, reviewed by a Bali Zero advisor, would get a signed, cited answer.",
  "verdict.state_description.HUMAN_REVIEW_REQUIRED":
    "Nothing here is guessed. A Bali Zero advisor reviews cases like yours by hand.",
  "verdict.state_description.NO_SUPPORTED_PATH":
    "We won’t force a fit that isn’t there — three alternatives worth a look.",
  "verdict.state_description.TEMPORARILY_UNAVAILABLE":
    "We’d rather say so plainly than fake a result.",
  "verdict.state_description.NEEDS_INPUT":
    "Finish the interview to see your options.",

  "outcome.comparison_title": "How the paths compare",
  "outcome.comparison_col.visa": "Path",
  "outcome.comparison_col.eligibility": "Eligibility",
  "outcome.comparison_col.timeline": "Timeline",
  "outcome.comparison_col.price": "Price",
  "outcome.timeline_title": "Timeline, from today",
  "outcome.timeline_range": "About {{min}}–{{max}} days",
  "outcome.price_label": "All-inclusive price",
  "outcome.price_all_inclusive": "One number — no PNBP-vs-fee split, ever.",
  // Finding #17 (adversarial review 2026-07-17): "Free"/WhatsApp summary
  // header were hardcoded English/Indonesian ternaries in OutcomeSheet.tsx
  // instead of dict entries — invisible to the i18n parity test and to
  // anyone editing copy without reading the component source.
  "outcome.price_free": "Free",
  "outcome.whatsapp_summary_header": "Visa Oracle summary (prototype):",
  "outcome.checklist_title": "Documents you’ll want ready",
  "outcome.next_steps_title": "Your next 3 steps",
  "outcome.next_steps.default.1":
    "Message a Bali Zero advisor with this summary",
  "outcome.next_steps.default.2": "Gather the documents listed above",
  "outcome.next_steps.default.3": "Confirm your timeline before booking travel",
  "outcome.whatsapp_cta": "Continue on WhatsApp",
  "outcome.qr_aria":
    "QR code — scan to continue this summary on WhatsApp on your phone",
  "outcome.print_cta": "Print / save as PDF",
  "outcome.copy_cta": "Copy summary",
  "outcome.copy_confirmed": "Copied to clipboard",
  "outcome.copy_failed": "Couldn't copy — try selecting the text manually",
  "outcome.assumptions_receipt_title": "Assumptions & caveats, dated",
  "outcome.assumptions_receipt_empty":
    "No assumptions were needed — every answer was given directly.",
  "outcome.freshness_stamp":
    "Sample ruleset 2026.07-prototype — evaluated {{date}}",
  "outcome.disclaimer.not_government":
    "This is a private decision-support demonstration, not a government service.",
  "outcome.disclaimer.based_on_facts":
    "The result reflects only the facts you entered and the cited sample ruleset above.",
  "outcome.disclaimer.not_approval":
    "It is not an approval, a guarantee, or a filing.",
  "outcome.disclaimer.complex_to_human":
    "Complex or flagged cases always go to a human — Ditjen Imigrasi decides, not this tool.",
  "outcome.alternatives_title": "Three paths worth a look instead",
  "outcome.alternatives_intro":
    "None of these are a downgrade — they’re simply what fits.",
  "outcome.no_path_body":
    "The combination you described doesn’t match a supported path in this prototype.",
  "outcome.temporarily_unavailable_body":
    "This duration needs a conversion lane this prototype doesn’t model yet. A Bali Zero advisor can walk you through it directly.",
  "outcome.human_review_body":
    "Your case needs a person’s judgment — nothing here was guessed on your behalf.",
  "outcome.overstay_reassurance":
    "Overstay is fixable. It is not the end of your story here.",

  "prototype.badge": "Prototype — sample data",
  "prototype.badge.detail":
    "Every figure on this page is a demonstration value, not a live quote.",

  "theme.toggle.aria": "Switch between light and dark",
  "theme.toggle.light": "Light",
  "theme.toggle.dark": "Dark",
  "language.toggle.aria": "Switch language",
  "language.option.en": "English",
  "language.option.id": "Indonesia",

  "footer.disclaimer":
    "Visa Oracle is a Bali Zero prototype with sample data. It is not a government service, not an approval, and not a filing — Ditjen Imigrasi decides. Complex cases always go to a human.",

  "req.passport_valid": "Passport valid 6+ months",
  "req.passport_photo": "Recent passport photo",
  "req.return_ticket": "Return or onward ticket",
  "req.application_form": "Completed application form",
  "req.sponsor_letter": "Sponsor letter",
  "req.proof_funds": "Proof of funds",
  "req.employment_contract": "Employment contract",
  "req.marriage_certificate": "Marriage certificate",
  "req.property_or_lease_proof": "Property or lease proof",

  "visa.A1.name": "A1 — Visa-Free (BVK)",
  "visa.A1.tagline": "Nationality-only short visit, no application needed",
  "visa.B1.name": "B1 — Visa on Arrival",
  "visa.B1.tagline": "30 days, extendable once",
  "visa.C1.name": "C1 — Tourism / Family / Medical",
  "visa.C1.tagline": "Multi-purpose visit visa",
  "visa.C2.name": "C2 — Business",
  "visa.C2.tagline": "Meetings and exploration, no local work",
  "visa.D1.name": "D1 — Multiple-Entry Business",
  "visa.D1.tagline": "Repeat business trips over a longer window",
  "visa.D2.name": "D2 — Multiple-Entry Social-Cultural",
  "visa.D2.tagline": "Repeat family or cultural visits",
  "visa.E23.name": "E23 — Work KITAS",
  "visa.E23.tagline": "Employed and paid by an Indonesian entity",
  "visa.E28A.name": "E28A — Investor / Golden Visa",
  "visa.E28A.tagline": "Investment-linked limited stay",
  "visa.E31.name": "E31 — Family ITAS",
  "visa.E31.tagline": "Spouse or family of an Indonesian or KITAS holder",
  "visa.E33F.name": "E33F — Remote Worker KITAS",
  "visa.E33F.tagline": "Foreign clients, foreign income, based in Indonesia",
  "visa.E33.name": "E33 — Second Home",
  "visa.E33.tagline": "Retirement or high-net-worth long stay",
  "visa.BRIDGING.name": "Bridging Visa",
  "visa.BRIDGING.tagline":
    "60-day onshore transition — file 3+ days before expiry",
} as const;

type Keys = keyof typeof en;

const id: Record<Keys, string> = {
  "framing.title": "Peta, bukan permohonan",
  "framing.body":
    "Jawab dengan jujur, termasuk “Saya tidak tahu.” Tidak ada yang diajukan di sini, dan tidak ada yang diputuskan untuk Anda — ini demonstrasi dengan data contoh.",
  "framing.cta": "Mulai",

  "q.in_indonesia": "Apakah Anda sedang berada di Indonesia sekarang?",
  "q.in_indonesia.hint":
    "Ini menentukan pertanyaan mana yang relevan selanjutnya.",
  "q.in_indonesia.opt.yes": "Ya, saya di sini",
  "q.in_indonesia.opt.no": "Belum, saya sedang merencanakan",

  "q.permit_expiry": "Kapan izin tinggal Anda saat ini berakhir?",
  "q.permit_expiry.hint":
    "Tanggal pada visa atau ITAS/KITAS Anda — bukan paspor.",
  "q.permit_expiry.label": "Tanggal berakhir",
  "why.permit_expiry":
    "Bridging Visa dan konversi apa pun punya jendela pengajuan yang ketat sebelum izin Anda berakhir.",

  "lane.expired.notice":
    "Izin tinggal Anda sudah berakhir. Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini — kasus ini selalu ditangani manusia, dan kami tidak akan menampilkan angka yang menakutkan di layar ini.",
  "lane.urgent.notice":
    "Waktu Anda tinggal 1–2 hari. Ini terlalu mepet untuk penelusuran otomatis — konsultan Bali Zero perlu melihat kasus ini hari ini.",
  "lane.bridging.notice":
    "Jendela waktu Anda semakin sempit. Bridging Visa harus diajukan minimal 3 hari sebelum berakhir — ingat ini saat menjawab.",
  "lane.extend.notice":
    "Anda masih punya waktu untuk membandingkan Extend dan Convert.",
  "lane.planning.notice":
    "Waktu masih longgar — ini perencanaan, bukan hal mendesak.",

  "q.category": "Apa tujuan Anda ke Indonesia?",
  "q.category.hint":
    "Pilih yang paling mendekati — bisa diperjelas berikutnya.",
  "why.category":
    "Indeks visa Indonesia direklasifikasi pada 2025; kategori ini menentukan kelompok dokumen yang berlaku.",
  "q.category.opt.tourism": "Wisata & kunjungan singkat",
  "q.category.opt.business": "Bisnis (tanpa bekerja)",
  "q.category.opt.work": "Kerja & ketenagakerjaan",
  "q.category.opt.invest": "Investasi & golden visa",
  "q.category.opt.remote": "Pekerja remote",
  "q.category.opt.family": "Keluarga & pernikahan",
  "q.category.opt.retirement": "Pensiun & second home",
  "q.category.opt.study": "Studi",
  "q.category.opt.diaspora": "Diaspora & eks-WNI",
  "q.category.opt.other": "Lainnya",

  "q.work_payer":
    "Apakah perusahaan berbadan hukum Indonesia yang mempekerjakan dan menggaji Anda di sini?",
  "q.work_payer.hint":
    "Bukan “apakah Anda butuh KITAS kerja” — tapi siapa yang benar-benar menggaji Anda.",
  "why.work_payer":
    "Aturan penjamin berubah pada 2025 dan bergantung pada siapa pemberi gaji.",
  "q.work_payer.opt.yes": "Ya, entitas Indonesia yang menggaji saya",
  "q.work_payer.opt.no": "Tidak, saya digaji dari luar negeri",

  "q.remote_clients": "Di mana klien atau pemberi kerja Anda berada?",
  "q.remote_clients.hint":
    "Ini yang membedakan jalur pekerja remote dari jalur kerja biasa.",
  "why.remote_clients":
    "Kelonggaran pekerja remote bergantung pada lokasi klien/pemberi kerja, bukan lokasi Anda.",
  "q.remote_clients.opt.foreign":
    "Luar negeri — mereka menggaji saya dari luar Indonesia",
  "q.remote_clients.opt.indonesian":
    "Indonesia — saya secara efektif bekerja di sini",
  "q.remote_clients.opt.mixed": "Campuran keduanya",

  "q.remote_income":
    "Apakah penghasilan Anda memenuhi ambang batas pekerja remote?",
  "q.remote_income.hint":
    "Di bawah ambang batas tidak otomatis gagal — hanya mengubah opsi yang bisa kami tawarkan.",
  "why.remote_income":
    "Ambang batas penghasilan diatur dalam aturan penjamin 2025 yang sama.",
  "q.remote_income.opt.above": "Ya, jauh di atasnya",
  "q.remote_income.opt.below": "Tidak, belum memenuhi ambang batas",
  "q.remote_income.courtesy_note":
    "Satu hal yang perlu Anda tahu, bukan syarat gugur: melewati sekitar 183 hari di Indonesia bisa mengubah status pajak Anda. Ini layak Anda ketahui sebelum memutuskan — tidak menggugurkan apa pun di sini.",

  "q.tourism_duration": "Berapa lama Anda berencana tinggal?",
  "q.tourism_duration.hint": "Perkiraan kasar tidak masalah.",
  "q.tourism_duration.opt.short": "Sampai 30 hari",
  "q.tourism_duration.opt.medium": "31–60 hari",
  "q.tourism_duration.opt.extended": "60+ hari",

  "q.review_gate": "Beberapa pertanyaan jujur sebelum kami tunjukkan hasilnya",
  "q.review_gate.hint":
    "Salah satu dari ini berarti kasus Anda ditinjau manusia — bukan keputusan otomatis. Ini fitur, bukan hukuman.",
  "why.review_gate":
    "Ini termasuk kategori data pribadi menurut UU Pelindungan Data Pribadi, ditangani dengan hati-hati dan hanya oleh manusia.",
  "q.review_gate.opt.none": "Tidak ada yang berlaku bagi saya",
  "q.review_gate.opt.flagged": "Satu atau lebih berlaku",
  "q.review_gate.item.none": "Tidak ada yang berlaku bagi saya",
  "q.review_gate.item.criminal_record": "Catatan kriminal, di mana pun",
  "q.review_gate.item.health_flag":
    "Kondisi kesehatan yang mungkin ditanyakan imigrasi",
  "q.review_gate.item.prior_refusal": "Penolakan visa sebelumnya",
  "q.review_gate.item.overstay_or_blacklist":
    "Riwayat overstay atau masuk daftar hitam",
  "q.review_gate.item.not_certain": "Saya tidak yakin soal semua di atas",
  "q.review_gate.none_selected": "Tidak ada yang berlaku bagi saya",

  "notsure.trigger": "Tidak yakin?",
  "assumption.in_indonesia":
    "Anda tidak yakin di mana posisi Anda — kami menganggap Anda di Indonesia, opsi yang lebih aman.",
  "assumption.tourism_duration":
    "Anda tidak yakin berapa lama akan tinggal — kami menganggap kunjungan singkat.",
  "assumption.work_payer":
    "Anda tidak yakin siapa yang menggaji Anda — kami menahan ini untuk konsultan Bali Zero, bukan menebak.",
  "assumption.remote_clients":
    "Anda tidak yakin di mana klien Anda berada — kami menahan ini untuk manusia, bukan menebak.",
  "assumption.remote_income":
    "Anda tidak yakin soal penghasilan Anda — kami menahan ini untuk manusia, bukan menebak.",

  "whyweask.trigger": "Mengapa kami tanyakan ini",
  "whyweask.trigger.aria": "Mengapa kami menanyakan pertanyaan ini",
  "whyweask.regulation_prefix": "Sumber (contoh): {{regulation}}",

  "back.button": "Kembali",
  "restart.button": "Mulai ulang",
  "verdict.edit_answers": "Ubah jawaban",

  "tree.edit_aria": "Ubah jawaban: {{question}}",
  "tree.framing": "Mulai",
  "tree.in_indonesia": "Posisi Anda",
  "tree.permit_expiry": "Jendela izin tinggal",
  "tree.category": "Kategori",
  "tree.work_payer": "Siapa yang menggaji",
  "tree.remote_clients": "Lokasi klien",
  "tree.remote_income": "Ambang penghasilan",
  "tree.tourism_duration": "Lama tinggal",
  "tree.review_gate": "Pemeriksaan keamanan",
  "tree.confirmation": "Jawaban Anda",
  "tree.verdict": "Hasil",
  "tree.sr_path_label": "Jalur Anda sejauh ini",
  "tree.sr_status.done": "sudah dijawab",
  "tree.sr_status.current": "langkah saat ini",
  "tree.sr_status.pending": "belum tercapai",
  "tree.sr_status.pruned": "tersingkir",

  "paths.counter.label": "{{count}} jalur",
  "paths.counter.aria": "{{count}} jalur tersisa",

  "confirmation.title": "Berikut yang Anda sampaikan",
  "confirmation.your_answers": "Jawaban Anda",
  "confirmation.assumptions_title": "Asumsi yang kami buat",
  "confirmation.edit": "Ubah",
  "confirmation.paths_remaining": "{{count}} jalur tersisa",
  "confirmation.price_preview":
    "Satu harga all-inclusive akan menyusul — tanpa rincian biaya, selalu.",
  "confirmation.cta": "Lihat opsi saya",

  "verdict.headline.SUPPORTED_CANDIDATES": "Ini opsi yang paling sesuai",
  "verdict.headline.HUMAN_REVIEW_REQUIRED":
    "Ini butuh manusia, bukan algoritma",
  "verdict.headline.NO_SUPPORTED_PATH":
    "Jalur persis ini belum didukung — ini alternatifnya",
  "verdict.headline.TEMPORARILY_UNAVAILABLE":
    "Jalur ini belum dimodelkan di prototipe",
  "verdict.headline.NEEDS_INPUT": "Sedikit lagi",
  "verdict.eligibility.eligible": "Memenuhi syarat",
  "verdict.eligibility.likely": "Kemungkinan besar",
  "verdict.eligibility.conditional": "Bersyarat",
  "verdict.eligibility.likely-not": "Kemungkinan tidak",
  "verdict.state_description.SUPPORTED_CANDIDATES":
    "Berdasarkan yang Anda sampaikan, data contoh di bawah. Kasus nyata yang ditinjau konsultan Bali Zero akan mendapat jawaban bertanda tangan dan bersumber.",
  "verdict.state_description.HUMAN_REVIEW_REQUIRED":
    "Tidak ada yang ditebak di sini. Konsultan Bali Zero meninjau kasus seperti ini secara langsung.",
  "verdict.state_description.NO_SUPPORTED_PATH":
    "Kami tidak akan memaksakan jalur yang tidak cocok — tiga alternatif yang layak dilihat.",
  "verdict.state_description.TEMPORARILY_UNAVAILABLE":
    "Kami lebih memilih berterus terang daripada memalsukan hasil.",
  "verdict.state_description.NEEDS_INPUT":
    "Selesaikan wawancara untuk melihat opsi Anda.",

  "outcome.comparison_title": "Perbandingan jalur",
  "outcome.comparison_col.visa": "Jalur",
  "outcome.comparison_col.eligibility": "Kelayakan",
  "outcome.comparison_col.timeline": "Linimasa",
  "outcome.comparison_col.price": "Harga",
  "outcome.timeline_title": "Linimasa, mulai hari ini",
  "outcome.timeline_range": "Sekitar {{min}}–{{max}} hari",
  "outcome.price_label": "Harga all-inclusive",
  "outcome.price_all_inclusive":
    "Satu angka — tanpa pemisahan PNBP vs. biaya jasa, selalu.",
  "outcome.price_free": "Gratis",
  "outcome.whatsapp_summary_header": "Ringkasan Visa Oracle (prototipe):",
  "outcome.checklist_title": "Dokumen yang perlu Anda siapkan",
  "outcome.next_steps_title": "3 langkah berikutnya",
  "outcome.next_steps.default.1":
    "Hubungi konsultan Bali Zero dengan ringkasan ini",
  "outcome.next_steps.default.2": "Siapkan dokumen yang tercantum di atas",
  "outcome.next_steps.default.3":
    "Pastikan linimasa Anda sebelum memesan perjalanan",
  "outcome.whatsapp_cta": "Lanjutkan di WhatsApp",
  "outcome.qr_aria":
    "Kode QR — pindai untuk melanjutkan ringkasan ini di WhatsApp lewat ponsel Anda",
  "outcome.print_cta": "Cetak / simpan sebagai PDF",
  "outcome.copy_cta": "Salin ringkasan",
  "outcome.copy_confirmed": "Disalin ke papan klip",
  "outcome.copy_failed": "Gagal menyalin — coba pilih teksnya secara manual",
  "outcome.assumptions_receipt_title": "Asumsi & catatan, bertanggal",
  "outcome.assumptions_receipt_empty":
    "Tidak ada asumsi yang diperlukan — semua jawaban diberikan langsung.",
  "outcome.freshness_stamp":
    "Aturan contoh 2026.07-prototype — dievaluasi {{date}}",
  "outcome.disclaimer.not_government":
    "Ini demonstrasi alat bantu keputusan privat, bukan layanan pemerintah.",
  "outcome.disclaimer.based_on_facts":
    "Hasil ini hanya mencerminkan data yang Anda masukkan dan aturan contoh yang dikutip di atas.",
  "outcome.disclaimer.not_approval":
    "Ini bukan persetujuan, jaminan, atau pengajuan resmi.",
  "outcome.disclaimer.complex_to_human":
    "Kasus kompleks atau ditandai selalu diteruskan ke manusia — Ditjen Imigrasi yang memutuskan, bukan alat ini.",
  "outcome.alternatives_title": "Tiga jalur alternatif yang layak dilihat",
  "outcome.alternatives_intro":
    "Ini bukan penurunan kelas — hanya yang paling sesuai.",
  "outcome.no_path_body":
    "Kombinasi yang Anda sebutkan belum cocok dengan jalur yang didukung di prototipe ini.",
  "outcome.temporarily_unavailable_body":
    "Durasi ini butuh jalur konversi yang belum dimodelkan di prototipe. Konsultan Bali Zero dapat membantu langsung.",
  "outcome.human_review_body":
    "Kasus Anda butuh penilaian manusia — tidak ada yang ditebak atas nama Anda.",
  "outcome.overstay_reassurance":
    "Overstay bisa diselesaikan. Ini bukan akhir cerita Anda di sini.",

  "prototype.badge": "Prototipe — data contoh",
  "prototype.badge.detail":
    "Setiap angka di halaman ini adalah nilai demonstrasi, bukan penawaran nyata.",

  "theme.toggle.aria": "Ganti antara mode terang dan gelap",
  "theme.toggle.light": "Terang",
  "theme.toggle.dark": "Gelap",
  "language.toggle.aria": "Ganti bahasa",
  "language.option.en": "English",
  "language.option.id": "Indonesia",

  "footer.disclaimer":
    "Visa Oracle adalah prototipe Bali Zero dengan data contoh. Bukan layanan pemerintah, bukan persetujuan, dan bukan pengajuan — Ditjen Imigrasi yang memutuskan. Kasus kompleks selalu diteruskan ke manusia.",

  "req.passport_valid": "Paspor berlaku 6+ bulan",
  "req.passport_photo": "Foto paspor terbaru",
  "req.return_ticket": "Tiket pulang atau lanjutan",
  "req.application_form": "Formulir permohonan lengkap",
  "req.sponsor_letter": "Surat sponsor",
  "req.proof_funds": "Bukti dana",
  "req.employment_contract": "Kontrak kerja",
  "req.marriage_certificate": "Akta nikah",
  "req.property_or_lease_proof": "Bukti properti atau sewa",

  "visa.A1.name": "A1 — Bebas Visa (BVK)",
  "visa.A1.tagline":
    "Kunjungan singkat berbasis kewarganegaraan, tanpa permohonan",
  "visa.B1.name": "B1 — Visa on Arrival",
  "visa.B1.tagline": "30 hari, dapat diperpanjang satu kali",
  "visa.C1.name": "C1 — Wisata / Keluarga / Medis",
  "visa.C1.tagline": "Visa kunjungan serbaguna",
  "visa.C2.name": "C2 — Bisnis",
  "visa.C2.tagline": "Rapat dan eksplorasi, tanpa bekerja di lokal",
  "visa.D1.name": "D1 — Kunjungan Bisnis Multi-Entry",
  "visa.D1.tagline": "Perjalanan bisnis berulang dalam jendela lebih lama",
  "visa.D2.name": "D2 — Kunjungan Sosial-Budaya Multi-Entry",
  "visa.D2.tagline": "Kunjungan keluarga atau budaya berulang",
  "visa.E23.name": "E23 — KITAS Kerja",
  "visa.E23.tagline": "Dipekerjakan dan digaji oleh entitas Indonesia",
  "visa.E28A.name": "E28A — Investor / Golden Visa",
  "visa.E28A.tagline": "Izin tinggal terbatas berbasis investasi",
  "visa.E31.name": "E31 — ITAS Keluarga",
  "visa.E31.tagline": "Pasangan atau keluarga WNI atau pemegang KITAS",
  "visa.E33F.name": "E33F — KITAS Pekerja Remote",
  "visa.E33F.tagline": "Klien asing, penghasilan asing, tinggal di Indonesia",
  "visa.E33.name": "E33 — Second Home",
  "visa.E33.tagline":
    "Tinggal jangka panjang untuk pensiun atau berkekayaan tinggi",
  "visa.BRIDGING.name": "Bridging Visa",
  "visa.BRIDGING.tagline":
    "Transisi onshore 60 hari — ajukan 3+ hari sebelum berakhir",
};

export const dict = { en, id };

/** Finding #16 (adversarial review 2026-07-17): design doc §3's ID register
 * rule is "body-first, warm-formal" — Indonesian readers of this register
 * expect the explanatory sentence before the terse headline, the reverse
 * of the EN "headline, then body" convention this route was built with
 * throughout. Consumers that render a heading+body pair (VerdictReveal)
 * read this flag to swap the render order per language rather than
 * hardcoding the EN ordering everywhere. */
export const BODY_FIRST: Record<Language, boolean> = { en: false, id: true };

/** Simple `{{var}}` interpolation — no ICU pluralization needed at this
 * scale. Missing keys return the raw key (visibly broken, never silent). */
export function translate(
  language: Language,
  key: Keys,
  vars?: Record<string, string | number>,
): string {
  const table = dict[language];
  let value: string = table[key] ?? key;
  if (vars) {
    for (const [name, v] of Object.entries(vars)) {
      value = value.replaceAll(`{{${name}}}`, String(v));
    }
  }
  return value;
}

export type { Keys as I18nKey };
