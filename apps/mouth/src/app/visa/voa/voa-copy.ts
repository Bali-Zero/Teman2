import type { VoaLocale } from "./voa-locale";

/**
 * GARUDA VOA — the eligibility wizard's copy, in both languages it can speak.
 *
 * EN is canonical: its object literal defines the key set, and `id` is typed
 * `Record<VoaCopyKey, string>`, so a missing or extra Indonesian key is a
 * TypeScript error at build time — the same shape Visa Oracle v2 uses
 * (`(visa-oracle)/visa-oracle/_lib/i18n.ts`), reused rather than reinvented.
 * `voa-i18n.parity.guard.test.tsx` re-checks it at runtime, and additionally
 * checks the thing types cannot see: an Indonesian value left equal to its
 * English original.
 *
 * REGISTER (inherited from the Visa Oracle ID dictionary, same customer, same
 * subject): warm-formal, "Anda" never "kamu", Imigrasi's own terminology, and
 * "Visa on Arrival" kept verbatim because that is the name printed on the
 * permit — never a lowercase paraphrase (`voa-copy.guard.test.ts` convicts
 * one the day it is typed).
 *
 * This file is scanned by `voa-copy.guard.test.ts` exactly like the screens
 * themselves: moving copy OUT of `page.tsx` and into a dictionary must not
 * move it out of the banned-claims guard's sight. That is the cicatrix
 * family #3 trap (a guard that changes what it reads loses an assertion in
 * silence), and the guard's SCREEN_FILES list names this file for that reason.
 */

const en = {
  "frame.title": "Visa on Arrival",
  "frame.subtitle":
    "Know in 10 seconds, buy in 5 minutes, follow it like a parcel.",

  "trust.questions.label": "quick questions",
  "trust.price.label": "all-inclusive price",
  "trust.government.label": "extra to pay the government after",

  "hero.wa.line":
    "Rather ask a person first? Our visa desk answers on WhatsApp.",
  "hero.wa.cta": "Talk to us on WhatsApp",
  "hero.wa.message": "Hi Bali Zero, I'd like help with a Visa on Arrival.",

  "step.case.title": "Your case",
  "step.case.question": "What are you here for?",
  "case.issuance.label": "Get a new Visa on Arrival",
  "case.issuance.hint": "First time, or a fresh entry",
  "case.extension.label": "Extend a Visa on Arrival I already have",
  "case.extension.hint": "You're already in Indonesia",

  "step.purpose.title": "Purpose",
  "step.purpose.question": "Why are you travelling?",
  "purpose.tourism": "Tourism",
  "purpose.family": "Visiting family",
  "purpose.transit": "Transit",
  "purpose.business-meeting": "A business meeting",

  "step.trip.title": "About you",
  "trip.nationality.question": "What's your nationality?",
  "trip.nationality.aria": "Nationality",
  "trip.nationality.placeholder": "Select one…",
  "nationality.USA": "United States",
  "nationality.GBR": "United Kingdom",
  "nationality.ITA": "Italy",
  "nationality.DEU": "Germany",
  "nationality.FRA": "France",
  "nationality.AUS": "Australia",
  "nationality.CAN": "Canada",
  "nationality.NLD": "Netherlands",
  "nationality.SGP": "Singapore",
  "nationality.OTHER": "Other",
  "trip.travellers.question": "How many travellers on this application?",
  "trip.travellers.aria": "Number of travellers",
  "trip.selfPay": "I am paying for this application myself",
  "trip.summary": "{nationality} · {travellers} traveller(s)",

  "step.dates.title": "Dates",
  "step.dates.summary": "Confirmed",
  "dates.entry.question": "When do you arrive (or did you arrive)?",
  "dates.entry.aria": "Entry date",
  "dates.passport.question": "Passport expiry date",
  "dates.passport.aria": "Passport expiry date",
  "dates.voaExpiry.question": "When does your current Visa on Arrival expire?",
  "dates.voaExpiry.aria": "Current Visa on Arrival expiry date",
  "dates.extensionUsed": "I have already extended this Visa on Arrival once",
  "dates.retention":
    "I understand how my answers are stored and that I can delete this check any time.",
  "dates.retention.aria": "Storage and deletion notice acknowledgement",

  "validate.pickOne": "Pick one.",
  "validate.pickNationality": "Pick a nationality.",
  "validate.bothDates": "Both dates are needed.",
  "validate.voaExpiry": "Your current Visa on Arrival's expiry date is needed.",
  "validate.retention": "Please confirm you've read the storage notice.",

  "status.checking": "Checking…",
  "error.eligibility.lead":
    "We couldn't check eligibility right now. Please try again, or ",
  "error.eligibility.link": "message us on WhatsApp",

  "wizard.stepOf": "Step {current} of {total}",
  "wizard.back": "Back",
  "wizard.next": "Next",
  "wizard.finish": "See result",

  // --- verdict leg (ACCEPT path, Safe Clock, what happens next) -------------
  "verdict.title": "Visa on Arrival",
  "verdict.notFound":
    "We couldn't find this check. It may have expired, or the link is wrong.",
  "verdict.networkError": "Network error. Please try again.",
  "verdict.deleted.subtitle": "This check has been deleted.",
  "verdict.startAgain": "Start again →",
  "verdict.or": "or",
  "verdict.loading.subtitle": "Checking your case…",
  "verdict.loading.body": "One moment.",
  "verdict.accept.title": "Visa on Arrival — you're eligible",
  "verdict.accept.subtitle":
    "What we found, what it costs, and what happens next.",
  "verdict.accept.subtitleNoDeadline":
    "We'll confirm your exact filing deadline before you pay.",
  "verdict.accept.priceFooter":
    "One all-inclusive price. Government fees, where they apply, are never billed separately from this figure.",
  "verdict.stamp.aria": "Approved — {price}",
  "verdict.share.title": "Bali Zero — Visa on Arrival",
  "verdict.human.headline": "Prefer a human to walk you through it?",
  "verdict.human.description":
    "Same practice, same portal, same price — a consultant drives the same steps with you.",
  "verdict.human.cta": "Continue on WhatsApp →",
  "verdict.wa.priceLabel": "Price",
  "verdict.wa.deadlineMsg":
    "Hi Bali Zero, I'd like to check my Visa on Arrival filing deadline.",
  "verdict.wa.beforePayMsg":
    "Hi Bali Zero, I have a question about my Visa on Arrival before I pay.",

  "verdict.decline.subtitle":
    "This isn't a wall — here's what we found and what to do next.",
  "verdict.decline.oracle": "Try Visa Match →",
  "verdict.decline.wa": "Continue on WhatsApp →",
  "verdict.decline.wa.message":
    "Hi Bali Zero, I checked the Visa on Arrival online and would like help with my case.",
  "verdict.decline.share.title": "Bali Zero — Visa on Arrival check",
  "verdict.error.wa": "message us on WhatsApp",

  "entry.heading": "Start your application",
  "entry.sent":
    "Check your email for a link to continue — it's valid for 15 minutes. Opening it asks you to confirm which application it unlocks, and then takes you to the passport upload.",
  "entry.body":
    "We email you a one-time link — no password. It opens your upload page and expires in 15 minutes, so send it to an inbox only you read.",
  "entry.emailLabel": "Your email",
  "entry.emailPlaceholder": "you@example.com",
  "entry.sending": "Sending…",
  "entry.submit": "Email me the link →",
  "entry.error": "Something went wrong. Please try again.",

  "delete.cta": "Delete this check",
  "delete.error": "Couldn't delete this check. Please try again.",
  "delete.retry": "Try again",
  "delete.confirm": "Delete this check? This can't be undone.",
  "delete.deleting": "Deleting…",
  "delete.yes": "Yes, delete",
  "delete.cancel": "Cancel",

  "clock.aria": "Filing deadline",
  "clock.passed.word":
    "The published filing day at Ngurah Rai for this check has passed.",
  "clock.passed.date": "It was {day}.",
  "clock.passed.note":
    "A consultant can tell you what your options are from here — it depends on details this form never asked for.",
  "clock.passed.cta": "Message the visa desk",
  "clock.unit.ample": "days to file",
  "clock.unit.soon": "days left to file",
  "clock.unit.one": "day left to file",
  "clock.today": "Today",
  "clock.date.today": "is the last published filing day at Ngurah Rai — {day}.",
  "clock.date.normal":
    "{day} at Ngurah Rai — the counter's published deadline.",
  "clock.note":
    "This is the one date we publish, and it is the one Ngurah Rai publishes. Filing at another office runs on that office's own deadline.",
  "clock.handoff": "Filing somewhere else?",

  "next.heading": "What happens next",
  "next.limits.heading": "What we cannot promise",
  "next.step1":
    "Upload a photo of your passport page. We check it can actually be read before anything else happens.",
  "next.step2":
    "Pay once, the price shown above. Nothing further is collected at the counter.",
  "next.step3":
    "We prepare and file your application at the office the date above is published by.",
  "next.step3.noDeadline":
    "We prepare and file your application at the office that publishes your filing deadline.",
  "next.step4":
    "You follow it like a parcel, and the result reaches the email you gave us.",
  "next.limit1":
    "The decision is Immigration's, not ours. We prepare your application and file it correctly — we do not approve it, and nobody who says otherwise can.",
  "next.limit2":
    "We do not quote a processing time. The date above is the counter's published filing deadline, which is a different thing and the only one we can stand behind.",
  "next.limit2.noDeadline":
    "We do not quote a processing time. We confirm the counter's published filing deadline before you pay, and that date is a different thing from a processing time — it is the only one we can stand behind.",
  "next.limit3":
    "That date is scoped to one office. If you end up filing somewhere else, tell us and we will confirm yours before you rely on it.",
  "next.limit3.noDeadline":
    "A published deadline is scoped to one office. Tell us where you plan to file and we will confirm yours before you rely on it.",
  "next.ask": "Ask us anything before you pay",
  /**
   * Lead context, not customer copy: these two travel to the CRM with a
   * WhatsApp lead (`WhatsAppLeadButton`), where a Bahasa label would split
   * one funnel's leads into two spellings. English on purpose, in both
   * columns — the parity guard's `SAME_BY_DESIGN` list names them.
   */
  "lead.context.pageLabel": "Page",
  "lead.context.pageValue": "Visa on Arrival — eligibility wizard",
} as const;

export type VoaCopyKey = keyof typeof en;

const id: Record<VoaCopyKey, string> = {
  "frame.title": "Visa on Arrival",
  "frame.subtitle":
    "Tahu hasilnya dalam 10 detik, beli dalam 5 menit, pantau seperti paket kiriman.",

  "trust.questions.label": "pertanyaan singkat",
  "trust.price.label": "harga sudah termasuk semua biaya",
  "trust.government.label": "biaya tambahan ke pemerintah setelahnya",

  "hero.wa.line":
    "Ingin bertanya kepada orang dulu? Tim visa kami menjawab di WhatsApp.",
  "hero.wa.cta": "Hubungi kami di WhatsApp",
  "hero.wa.message":
    "Halo Bali Zero, saya ingin dibantu untuk Visa on Arrival.",

  "step.case.title": "Keperluan Anda",
  "step.case.question": "Apa yang Anda perlukan?",
  "case.issuance.label": "Mengurus Visa on Arrival baru",
  "case.issuance.hint": "Pertama kali, atau kedatangan baru",
  "case.extension.label":
    "Memperpanjang Visa on Arrival yang sudah saya miliki",
  "case.extension.hint": "Anda sudah berada di Indonesia",

  "step.purpose.title": "Tujuan",
  "step.purpose.question": "Apa tujuan perjalanan Anda?",
  "purpose.tourism": "Wisata",
  "purpose.family": "Mengunjungi keluarga",
  "purpose.transit": "Transit",
  "purpose.business-meeting": "Rapat bisnis",

  "step.trip.title": "Tentang Anda",
  "trip.nationality.question": "Apa kewarganegaraan Anda?",
  "trip.nationality.aria": "Kewarganegaraan",
  "trip.nationality.placeholder": "Pilih salah satu…",
  "nationality.USA": "Amerika Serikat",
  "nationality.GBR": "Inggris",
  "nationality.ITA": "Italia",
  "nationality.DEU": "Jerman",
  "nationality.FRA": "Prancis",
  "nationality.AUS": "Australia",
  "nationality.CAN": "Kanada",
  "nationality.NLD": "Belanda",
  "nationality.SGP": "Singapura",
  "nationality.OTHER": "Lainnya",
  "trip.travellers.question": "Berapa orang dalam permohonan ini?",
  "trip.travellers.aria": "Jumlah pemohon",
  "trip.selfPay": "Saya membayar permohonan ini sendiri",
  "trip.summary": "{nationality} · {travellers} orang",

  "step.dates.title": "Tanggal",
  "step.dates.summary": "Terkonfirmasi",
  "dates.entry.question": "Kapan Anda tiba (atau sudah tiba)?",
  "dates.entry.aria": "Tanggal kedatangan",
  "dates.passport.question": "Masa berlaku paspor",
  "dates.passport.aria": "Masa berlaku paspor",
  "dates.voaExpiry.question":
    "Kapan masa berlaku Visa on Arrival Anda saat ini habis?",
  "dates.voaExpiry.aria": "Masa berlaku Visa on Arrival saat ini",
  "dates.extensionUsed":
    "Saya sudah pernah memperpanjang Visa on Arrival ini satu kali",
  "dates.retention":
    "Saya memahami cara jawaban saya disimpan dan bahwa saya dapat menghapus data pengecekan ini kapan saja.",
  "dates.retention.aria":
    "Persetujuan pemberitahuan penyimpanan dan penghapusan",

  "validate.pickOne": "Pilih salah satu.",
  "validate.pickNationality": "Pilih kewarganegaraan.",
  "validate.bothDates": "Kedua tanggal harus diisi.",
  "validate.voaExpiry":
    "Masa berlaku Visa on Arrival Anda saat ini harus diisi.",
  "validate.retention":
    "Mohon konfirmasi bahwa Anda sudah membaca pemberitahuan penyimpanan.",

  "status.checking": "Memeriksa…",
  "error.eligibility.lead":
    "Kami belum dapat memeriksa kelayakan saat ini. Silakan coba lagi, atau ",
  "error.eligibility.link": "hubungi kami di WhatsApp",

  "wizard.stepOf": "Langkah {current} dari {total}",
  "wizard.back": "Kembali",
  "wizard.next": "Lanjut",
  "wizard.finish": "Lihat hasil",

  // --- verdict leg ----------------------------------------------------------
  "verdict.title": "Visa on Arrival",
  "verdict.notFound":
    "Kami tidak dapat menemukan pengecekan ini. Mungkin sudah kedaluwarsa, atau tautannya keliru.",
  "verdict.networkError": "Gangguan jaringan. Silakan coba lagi.",
  "verdict.deleted.subtitle": "Pengecekan ini sudah dihapus.",
  "verdict.startAgain": "Mulai lagi →",
  "verdict.or": "atau",
  "verdict.loading.subtitle": "Memeriksa kasus Anda…",
  "verdict.loading.body": "Sebentar ya.",
  "verdict.accept.title": "Visa on Arrival — Anda memenuhi syarat",
  "verdict.accept.subtitle":
    "Apa yang kami temukan, berapa biayanya, dan apa yang terjadi selanjutnya.",
  "verdict.accept.subtitleNoDeadline":
    "Kami akan memastikan batas akhir pengajuan Anda sebelum Anda membayar.",
  "verdict.accept.priceFooter":
    "Satu harga yang sudah termasuk semua. Biaya pemerintah, jika berlaku, tidak pernah ditagih terpisah dari angka ini.",
  // "Approved" here is the ELIGIBILITY verdict, not an immigration decision.
  // "Disetujui" would read as the second in Bahasa, on a screen whose whole
  // job is to say Immigration decides — so the stamp says "memenuhi syarat".
  "verdict.stamp.aria": "Memenuhi syarat — {price}",
  "verdict.share.title": "Bali Zero — Visa on Arrival",
  "verdict.human.headline": "Lebih suka ada orang yang memandu Anda?",
  "verdict.human.description":
    "Praktik yang sama, portal yang sama, harga yang sama — konsultan menjalankan langkah yang sama bersama Anda.",
  "verdict.human.cta": "Lanjut di WhatsApp →",
  "verdict.wa.priceLabel": "Price",
  "verdict.wa.deadlineMsg":
    "Halo Bali Zero, saya ingin memastikan batas akhir pengajuan Visa on Arrival saya.",
  "verdict.wa.beforePayMsg":
    "Halo Bali Zero, saya ada pertanyaan tentang Visa on Arrival saya sebelum membayar.",

  "verdict.decline.subtitle":
    "Ini bukan jalan buntu — berikut yang kami temukan dan apa langkah berikutnya.",
  "verdict.decline.oracle": "Coba Visa Match →",
  "verdict.decline.wa": "Lanjut di WhatsApp →",
  "verdict.decline.wa.message":
    "Halo Bali Zero, saya sudah mengecek Visa on Arrival secara online dan ingin dibantu untuk kasus saya.",
  "verdict.decline.share.title": "Bali Zero — pengecekan Visa on Arrival",
  "verdict.error.wa": "hubungi kami di WhatsApp",

  "entry.heading": "Mulai permohonan Anda",
  "entry.sent":
    "Cek email Anda untuk tautan lanjutan — berlaku 15 menit. Saat dibuka, Anda diminta memastikan permohonan mana yang dibuka, lalu dibawa ke halaman unggah paspor.",
  "entry.body":
    "Kami mengirim tautan sekali pakai lewat email — tanpa kata sandi. Tautan itu membuka halaman unggah Anda dan kedaluwarsa dalam 15 menit, jadi kirim ke kotak masuk yang hanya Anda baca.",
  "entry.emailLabel": "Email Anda",
  "entry.emailPlaceholder": "you@example.com",
  "entry.sending": "Mengirim…",
  "entry.submit": "Kirimkan tautannya →",
  "entry.error": "Terjadi kesalahan. Silakan coba lagi.",

  "delete.cta": "Hapus pengecekan ini",
  "delete.error": "Tidak bisa menghapus pengecekan ini. Silakan coba lagi.",
  "delete.retry": "Coba lagi",
  "delete.confirm": "Hapus pengecekan ini? Tindakan ini tidak bisa dibatalkan.",
  "delete.deleting": "Menghapus…",
  "delete.yes": "Ya, hapus",
  "delete.cancel": "Batal",

  "clock.aria": "Batas akhir pengajuan",
  "clock.passed.word":
    "Hari pengajuan yang dipublikasikan di Ngurah Rai untuk pengecekan ini sudah lewat.",
  "clock.passed.date": "Yaitu {day}.",
  "clock.passed.note":
    "Konsultan dapat menjelaskan pilihan Anda dari titik ini — itu bergantung pada detail yang tidak pernah ditanyakan formulir ini.",
  "clock.passed.cta": "Hubungi tim visa",
  "clock.unit.ample": "hari untuk mengajukan",
  "clock.unit.soon": "hari tersisa untuk mengajukan",
  "clock.unit.one": "hari tersisa untuk mengajukan",
  "clock.today": "Hari ini",
  "clock.date.today":
    "adalah hari pengajuan terakhir yang dipublikasikan di Ngurah Rai — {day}.",
  "clock.date.normal":
    "{day} di Ngurah Rai — batas akhir yang dipublikasikan loket.",
  "clock.note":
    "Ini satu-satunya tanggal yang kami publikasikan, dan itu tanggal yang dipublikasikan Ngurah Rai. Pengajuan di kantor lain mengikuti batas akhir kantor tersebut.",
  "clock.handoff": "Mengajukan di tempat lain?",

  "next.heading": "Yang terjadi selanjutnya",
  "next.limits.heading": "Yang tidak bisa kami janjikan",
  "next.step1":
    "Unggah foto halaman paspor Anda. Kami memeriksa bahwa foto itu benar-benar terbaca sebelum hal lain berjalan.",
  "next.step2":
    "Bayar satu kali, sesuai harga di atas. Tidak ada biaya lain yang dipungut di loket.",
  "next.step3":
    "Kami menyiapkan dan mengajukan permohonan Anda di kantor yang mempublikasikan tanggal di atas.",
  "next.step3.noDeadline":
    "Kami menyiapkan dan mengajukan permohonan Anda di kantor yang mempublikasikan batas akhir pengajuan Anda.",
  "next.step4":
    "Anda memantaunya seperti paket kiriman, dan hasilnya dikirim ke email yang Anda berikan.",
  "next.limit1":
    "Keputusan ada di tangan Imigrasi, bukan kami. Kami menyiapkan permohonan Anda dan mengajukannya dengan benar — kami tidak menyetujuinya, dan siapa pun yang mengatakan sebaliknya juga tidak bisa.",
  "next.limit2":
    "Kami tidak menyebutkan lama proses. Tanggal di atas adalah batas akhir pengajuan yang dipublikasikan loket — itu hal yang berbeda, dan satu-satunya yang bisa kami pertanggungjawabkan.",
  "next.limit2.noDeadline":
    "Kami tidak menyebutkan lama proses. Kami memastikan batas akhir pengajuan yang dipublikasikan loket sebelum Anda membayar; tanggal itu berbeda dari lama proses, dan hanya tanggal itu yang bisa kami pertanggungjawabkan.",
  "next.limit3":
    "Tanggal itu berlaku untuk satu kantor saja. Jika Anda akhirnya mengajukan di tempat lain, beri tahu kami dan kami akan memastikan tanggal Anda sebelum Anda mengandalkannya.",
  "next.limit3.noDeadline":
    "Batas akhir yang dipublikasikan berlaku untuk satu kantor saja. Beri tahu kami di mana Anda berencana mengajukan dan kami akan memastikan tanggal Anda sebelum Anda mengandalkannya.",
  "next.ask": "Tanyakan apa saja sebelum Anda membayar",
  "lead.context.pageLabel": "Page",
  "lead.context.pageValue": "Visa on Arrival — eligibility wizard",
};

export const VOA_COPY: Record<VoaLocale, Record<VoaCopyKey, string>> = {
  en,
  id,
};

/**
 * `{name}` placeholders only — no nesting, no pluralisation rules. An unknown
 * placeholder is left standing rather than blanked, so a missing parameter is
 * visible in a screenshot instead of silently rendering a hole.
 */
export function fill(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, key: string) =>
    key in params ? String(params[key]) : whole,
  );
}

export type VoaCopyFn = (
  key: VoaCopyKey,
  params?: Record<string, string | number>,
) => string;

export function voaCopy(locale: VoaLocale): VoaCopyFn {
  const table = VOA_COPY[locale] ?? VOA_COPY.en;
  return (key, params) => fill(table[key] ?? en[key], params);
}
