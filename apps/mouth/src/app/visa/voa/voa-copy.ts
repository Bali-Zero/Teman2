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
