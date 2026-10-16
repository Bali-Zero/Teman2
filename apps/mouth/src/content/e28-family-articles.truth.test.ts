// =============================================================================
// E28 FAMILY TRUTH GUARD (mission E28-close-1015).
//
// The official Imigrasi pages for E28A-E28F (read 2026-10-15,
// research/visa/2026-10-15-e28-pages/) are the source of truth. The E28A guide,
// the Golden Visa guide, the Investor KITAS guide and /visa/kitas each stated
// things those pages contradict: an E28G that does not exist, E28A as
// "strictly passive", an 18-month passport rule, a Golden Visa that is an ITAP
// with an "IDR 350M" threshold, E28D as a representative-office permit.
//
// The three guides are live in five locales (en, id, it, fr, ru; the locale
// twin is served on ?lang=). Each rule below is ENTITY-scoped (the number or code
// sits NEAR the thing it is wrong about), carries, for every locale it covers, a
// guilt sample it must catch and an innocence sample it must leave alone, and is
// then run over every file of every locale it applies to.
// =============================================================================
import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const IMM = path.join(process.cwd(), "src/content/articles/immigration");
const read = (p: string) => fs.readFileSync(p, "utf8");

type Loc = "en" | "id" | "it" | "fr" | "ru";
const LOCS: Loc[] = ["en", "id", "it", "fr", "ru"];
const fileOf = (slug: string, loc: Loc) =>
  path.join(IMM, `${slug}${loc === "en" ? "" : `.${loc}`}.mdx`);
const group = (slug: string) =>
  LOCS.map((l) => ({ loc: l, file: fileOf(slug, l) }));

const E28A = group("e28a-investor-kitas-guide");
const GOLDEN = group("golden-visa-indonesia-complete-guide");
const INVESTOR = group("investor-kitas-guide");
const KITAS_PAGE = [
  {
    loc: "en" as Loc,
    file: path.join(process.cwd(), "src/content/visa/kitas/page.mdx"),
  },
];
const ALL = [...E28A, ...GOLDEN, ...INVESTOR, ...KITAS_PAGE];

interface Sample {
  re: RegExp;
  guilt: string;
  innocence: string;
}
interface Rule {
  id: string;
  files: { loc: Loc; file: string }[];
  /** Per-locale detector; `*` covers every locale not listed. */
  by: Partial<Record<Loc | "*", Sample>>;
}
const pick = (r: Rule, loc: Loc): Sample | undefined => r.by[loc] ?? r.by["*"];

const RULES: Rule[] = [
  {
    id: "E28G does not exist",
    files: ALL,
    by: {
      "*": {
        re: /E28G/,
        guilt: "### E28G: Representative of Parent Company",
        innocence:
          "E28F is the same route in IKN; E28E has no published details.",
      },
    },
  },
  {
    id: "no seven sub-variants",
    files: ALL,
    by: {
      en: {
        re: /\bseven (E28 )?sub-?(variants|types)|\b7 (E28 )?sub-?variants/i,
        guilt: "divides the category into seven sub-types",
        innocence: "the visa is valid for seven days after the check",
      },
      id: {
        re: /tujuh sub-?(varian|tipe)|\b7 sub-variasi/i,
        guilt: "membagi kategori menjadi tujuh sub-tipe",
        innocence: "visa berlaku tujuh hari setelah pemeriksaan",
      },
      it: {
        re: /\bsette sott(ovarianti|otipi)|\b7 sottovarianti/i,
        guilt: "le sette sottovarianti (da E28A a E28G)",
        innocence: "il visto vale sette giorni dopo il controllo",
      },
      fr: {
        re: /\bsept sous-(variantes|types)|\b7 sous-variantes/i,
        guilt: "les sept sous-variantes (E28A à E28G)",
        innocence: "le visa est valable sept jours après le contrôle",
      },
      ru: {
        re: /сем[ьи] (под)?(вариантов|типов)|\b7 подвариантов/i,
        guilt: "семь подвариантов (от E28A до E28G)",
        innocence: "виза действует семь дней после проверки",
      },
    },
  },
  {
    id: "E28A is not strictly passive",
    files: [...E28A, ...INVESTOR],
    by: {
      en: {
        re: /strictly (for )?passive|passive investors|pure passive/i,
        guilt: "No. E28A is strictly for passive investors.",
        innocence: "## Tax on dividend: Passive Investment Income Taxation",
      },
      id: {
        re: /investor pasif|visa investasi pasif|pasif murni/i,
        guilt: "E28A khusus untuk investor pasif.",
        innocence: "## Implikasi Pajak Investasi Pasif E28A",
      },
      it: {
        re: /investitori passivi|visto (per )?investimento passivo|investitore passivo puro/i,
        guilt: "L'E28A è strettamente per investitori passivi.",
        innocence: "## Implicazioni Fiscali dell'Investimento Passivo E28A",
      },
      fr: {
        re: /investisseurs? passifs?|visa d'investissement passif|purement passif/i,
        guilt: "L'E28A est strictement pour les investisseurs passifs.",
        innocence: "## Implications Fiscales de l'Investissement Passif E28A",
      },
      ru: {
        re: /пассивн[а-яё]+ инвестор|виз[а-яё]+ пассивного инвестора|чистый пассивный/i,
        guilt: "Виза пассивного инвестора для Индонезии",
        innocence: "## Налоговые последствия пассивных инвестиций E28A",
      },
    },
  },
  {
    id: "passport is 6 months, not 18 or 24",
    files: [...E28A, ...INVESTOR],
    by: {
      en: {
        re: /passport[^.\n|;]{0,60}\b(18|24)\+? months?|\b18 months?[^.\n|;]{0,40}passport/i,
        guilt: "Passport - Valid for minimum 18 months from application date",
        innocence:
          "Passport - Valid for at least 6 months; 18 months of bank history",
      },
      id: {
        re: /paspor[^.\n|;]{0,60}\b(18|24)\+? bulan|\b18 bulan[^.\n|;]{0,40}paspor/i,
        guilt: "Paspor - Berlaku minimal 18 bulan dari tanggal pengajuan",
        innocence: "Paspor - Berlaku minimal 6 bulan; riwayat bank 18 bulan",
      },
      it: {
        re: /passaporto[^.\n|;]{0,60}\b(18|24)\+? mesi|\b18 mesi[^.\n|;]{0,40}passaporto/i,
        guilt: "Passaporto - Valido per minimo 18 mesi dalla data di richiesta",
        innocence:
          "Passaporto - Valido per almeno 6 mesi; storico bancario di 18 mesi",
      },
      fr: {
        re: /passeport[^.\n|;]{0,60}\b(18|24)\+? mois|\b18 mois[^.\n|;]{0,40}passeport/i,
        guilt:
          "Passeport - Valide au minimum 18 mois à compter de la date de la demande",
        innocence:
          "Passeport - Valide au moins 6 mois ; historique bancaire de 18 mois",
      },
      ru: {
        re: /паспорт[^.\n|;]{0,60}\b(18|24)\+? месяц|\b18 месяц[^.\n|;]{0,40}паспорт/i,
        guilt:
          "Паспорт - Действителен не менее 18 месяцев с даты подачи заявки",
        innocence:
          "Паспорт - Действителен не менее 6 месяцев; история счёта 18 месяцев",
      },
    },
  },
  {
    id: "visa stage is five working days, not 5-7",
    files: [...E28A, ...INVESTOR, ...KITAS_PAGE],
    by: {
      en: {
        re: /5\s?[-–]\s?7 (working days|hari kerja)/i,
        guilt: "Processing Time | 5-7 working days",
        innocence: "typically 7-10 working days with Bali Zero (indicative)",
      },
      id: {
        re: /5\s?[-–]\s?7 hari kerja/i,
        guilt: "Waktu Pemrosesan | 5-7 hari kerja",
        innocence: "7-10 hari kerja bersama Bali Zero (indikatif)",
      },
      it: {
        re: /5\s?[-–]\s?7 giorni lavorativi/i,
        guilt: "Tempistica: 5-7 giorni lavorativi",
        innocence: "di norma 7-10 giorni lavorativi con Bali Zero (indicativo)",
      },
      fr: {
        re: /5\s?[-–]\s?7 jours ouvrables/i,
        guilt: "Délai : 5-7 jours ouvrables",
        innocence:
          "généralement 7-10 jours ouvrables avec Bali Zero (indicatif)",
      },
      ru: {
        re: /5\s?[-–]\s?7 рабочих дней/i,
        guilt: "Срок: 5-7 рабочих дней",
        innocence: "обычно 7-10 рабочих дней с Bali Zero (ориентировочно)",
      },
    },
  },
  {
    id: "no IDR 350M threshold, no USD 23,333",
    files: [...GOLDEN, ...INVESTOR],
    by: {
      "*": {
        re: /(IDR|Rp\.?)\s?350\s?(M\b|juta|milioni|millions?|млн|million)|(IDR|Rp\.?)\s?350[.,\s]000[.,\s]000|350[.,\s]000[.,\s]000\s?IDR|USD 23[.,\s]333/i,
        guilt: "Golden Visa: IDR 350M+ investment",
        innocence: "E28C needs USD 350,000 in listed shares",
      },
    },
  },
  {
    id: "Golden Visa is an ITAS, not ITAP / permanent residence",
    files: GOLDEN,
    by: {
      "*": {
        re: /\(ITAP\)|\bITAP -|ITAP card|carta ITAP|called ITAP|chiamat\w+ (ufficialmente )?ITAP|appelé( officiellement)? ITAP|Golden Visa[^.\n]{0,50}\b(grants|offers|provides|gives|is)\s+(a\s+)?permanent residence/i,
        guilt: "Golden Visa (ITAP) grants permanent residence",
        innocence:
          "The Golden Visa is a limited-stay permit and does not grant permanent residence.",
      },
    },
  },
  {
    id: "Golden Visa has no corporate IDR tier",
    files: GOLDEN,
    by: {
      "*": {
        re: /Corporate (5|10)-Year|(IDR|Rp\.?)\s?2[.,]5\s?(billion|miliar|miliardi|milliards?|млрд)|(IDR|Rp\.?)\s?2[.,]500[.,]000[.,]000/i,
        guilt: "| **Corporate 5-Year** | IDR 2,500,000,000 |",
        innocence: "E28B: USD 2.5M committed within 90 days of entry",
      },
    },
  },
  {
    id: "E28D is not a representative-office permit",
    files: KITAS_PAGE,
    by: {
      "*": {
        re: /KPPA|KP3A|E28D[^\n]*(Representative Office|Kantor Perwakilan)|Director KITAS \(Representative|E28D[^\n]*e25b-director-kitas-guide/i,
        guilt:
          "## E28D — Director KITAS (Representative Office) {#e28d-director-kitas}",
        innocence:
          "E28D — Golden Visa (Branch or Subsidiary of a Foreign Company)",
      },
    },
  },
  {
    id: "E28A kitas-page row: no 20-30 hari",
    files: KITAS_PAGE,
    by: {
      "*": {
        re: /E28A[^\n]*20\s?[–-]\s?30 hari/,
        guilt:
          "| E28A — Investor KITAS | PT PMA shareholders | x | 20–30 hari |",
        innocence:
          "| E28A — Investor KITAS | owners | x | 7–10 hari kerja (indicative) |",
      },
    },
  },
  {
    id: "the E28A test is own shareholding, not paid-in capital",
    files: [...E28A, ...INVESTOR, ...KITAS_PAGE],
    by: {
      en: {
        re: /paid[- ](in|up) capital( of)?\s+(IDR|Rp)\.?\s?10[ .,]?(000|billion|B\b|miliar)|(IDR|Rp)\.?\s?10 (billion|B\b|miliar)[^\n]{0,30}paid[- ](in|up) capital|paid-up capital\s*\|\s*(IDR|Rp)\s?10[.,]000|Paid-up capital\*\* \(modal disetor\)/i,
        guilt: "| Total company paid-up capital | IDR 10,000,000,000 minimum |",
        innocence:
          "The PT PMA itself needs at least IDR 2.5 billion paid-up capital (BKPM Regulation 5/2025).",
      },
      id: {
        re: /modal (dasar|disetor)[^\n|]*\|\s*Minimum IDR 10\.000|Modal disetor\*\* \(paid-up capital\)/i,
        guilt: "| Total modal dasar perusahaan | Minimum IDR 10.000.000.000 |",
        innocence: "PT PMA memerlukan modal disetor minimal Rp 2,5 miliar",
      },
      it: {
        re: /Capitale (sociale totale )?versato[^|\n]*\|\s*Minimo IDR 10\.000|Capitale versato\*\* \(modal disetor\)/i,
        guilt:
          "| Capitale sociale totale versato | Minimo IDR 10.000.000.000 |",
        innocence:
          "almeno IDR 2,5 miliardi di capitale versato (Regolamento BKPM 5/2025)",
      },
      fr: {
        re: /Capital (social )?libéré[^|\n]*\|\s*10 000 000 000 IDR|Capital libéré\*\* \(modal disetor\)/i,
        guilt:
          "| Capital social libéré total de l'entreprise | 10 000 000 000 IDR minimum |",
        innocence:
          "au moins 2,5 milliards IDR de capital libéré (Règlement BKPM 5/2025)",
      },
      ru: {
        re: /оплаченный капитал[^|\n]*\|\s*Минимум IDR 10,000|Оплаченный капитал\*\* \(modal disetor\)/i,
        guilt:
          "| Общий оплаченный капитал компании | Минимум IDR 10,000,000,000 |",
        innocence:
          "оплаченный капитал не менее 2,5 миллиарда IDR (Положение BKPM 5/2025)",
      },
    },
  },
  {
    id: "10 billion is not written IDR 10M",
    files: [...E28A, ...INVESTOR],
    by: {
      "*": {
        re: /(shareholding|saham|investment|investasi|partecipazione|participation|долев)[^\n;]{0,60}(IDR|Rp)\.? ?10M\b|(IDR|Rp)\.? ?10M[^\n;]{0,40}(shareholding|saham|minimum|minimo|minimale)/i,
        guilt: "Kepemilikan saham minimal IDR 10M, tidak perlu RPTKA",
        innocence:
          "Rp 10 miliar of own shareholding; KITAP renewal IDR 10M per renewal",
      },
    },
  },
  {
    id: "price is all-inclusive, no fee split",
    files: [...E28A, ...INVESTOR],
    by: {
      en: {
        re: /government fees? (are |is )?(paid )?separate|biaya pemerintah terpisah|plus government fees|excluding government fees|belum termasuk biaya pemerintah/i,
        guilt: "IDR 17M; government fees are separate",
        innocence:
          "all-inclusive: government fees and Bali Zero service included",
      },
      id: {
        re: /biaya pemerintah terpisah|belum termasuk biaya pemerintah|ditambah biaya pemerintah/i,
        guilt: "Rp 17 juta; biaya pemerintah terpisah",
        innocence:
          "all-inclusive (biaya pemerintah dan jasa Bali Zero sudah termasuk)",
      },
      it: {
        re: /tasse governative (sono )?separate|escluse le tasse governative|più tasse governative/i,
        guilt: "IDR 17M; le tasse governative sono separate",
        innocence:
          "tutto incluso: tasse governative e servizio Bali Zero compresi",
      },
      fr: {
        re: /frais gouvernementaux (sont )?séparés|hors frais gouvernementaux|plus frais gouvernementaux/i,
        guilt: "17M IDR ; les frais gouvernementaux sont séparés",
        innocence:
          "tout compris : frais gouvernementaux et service Bali Zero inclus",
      },
      ru: {
        re: /государственные сборы (оплачиваются )?отдельно|без учета государственных сборов/i,
        guilt: "IDR 17M; государственные сборы оплачиваются отдельно",
        innocence: "все включено: государственные сборы и услуги Bali Zero",
      },
    },
  },
  {
    id: "E28A extension has no invented length",
    files: [...E28A, ...INVESTOR],
    by: {
      en: {
        re: /Extend E28A for Another 2 Years|Validity: 1 year \(to reach|renewable annually/i,
        guilt: "- Validity: 1 year (to reach 3-year mark)",
        innocence:
          "extended online by the sponsor; Imigrasi states no extension length",
      },
      id: {
        re: /Perpanjang E28A Selama 2 Tahun|Validitas: 1 tahun \(untuk mencapai/i,
        guilt: "- Validitas: 1 tahun (untuk mencapai tanda 3 tahun)",
        innocence: "diperpanjang secara online oleh sponsor",
      },
      it: {
        re: /Rinnova l'E28A per Altri 2 Anni|Validità: 1 anno \(per raggiungere/i,
        guilt: "- Validità: 1 anno (per raggiungere il traguardo dei 3 anni)",
        innocence: "prorogato online dallo sponsor",
      },
      fr: {
        re: /Prolonger l'E28A pour 2 ans supplémentaires|Validité : 1 an \(pour atteindre/i,
        guilt: "- Validité : 1 an (pour atteindre la marque des 3 ans)",
        innocence: "prolongé en ligne par le sponsor",
      },
      ru: {
        re: /Продлить E28A еще на 2 года|Срок действия: 1 год \(для достижения/i,
        guilt: "- Срок действия: 1 год (для достижения отметки в 3 года)",
        innocence: "продлевается онлайн спонсором",
      },
    },
  },
  {
    id: "E28A holder may be director or commissioner",
    files: [...E28A, ...INVESTOR],
    by: {
      en: {
        re: /E28A holders? cannot work|E28A does not grant work permission|convert (your )?visa category from E28A to E25B|both shareholder AND director, which requires Working KITAS|sign contracts as director, you need a Working KITAS|Serve as company director \(Direktur\) in board meetings|you need E25B Director KITAS instead/i,
        guilt: "However, E28A holders cannot work.",
        innocence:
          "With IDR 10 billion of own shareholding you may act as director or commissioner.",
      },
      id: {
        re: /pemegang E28A tidak dapat bekerja|E28A tidak memberikan izin kerja|mengubah kategori visa Anda dari E28A ke E25B|menjadi pemegang saham SEKALIGUS direktur, yang memerlukan|menandatangani kontrak sebagai direktur, Anda memerlukan|Menjadi direktur perusahaan \(Direktur\) dalam rapat dewan|Anda memerlukan E25B Director KITAS/i,
        guilt: "Namun, pemegang E28A tidak dapat bekerja.",
        innocence:
          "Anda boleh menjadi direktur atau komisaris PT PMA tempat Anda berinvestasi.",
      },
      it: {
        re: /titolari di E28A \**non possono lavorare|convertire la tua categoria di visto da E28A|sia azionista CHE direttore, il che richiede|firmare contratti come direttore, hai bisogno|Servire come direttore \(Direktur\) in riunioni|hai bisogno dell'E25B Director KITAS invece/i,
        guilt: "Tuttavia, i titolari di E28A non possono lavorare.",
        innocence:
          "puoi essere amministratore o commissario della PT PMA in cui hai investito",
      },
      fr: {
        re: /titulaires de l'E28A ne peuvent pas travailler|convertir (votre )?catégorie de visa de l'E28A|à la fois actionnaire ET directeur, ce qui nécessite|Occuper le poste de directeur de l'entreprise \(Direktur\)|vous avez besoin du KITAS Directeur E25B à la place/i,
        guilt: "Cependant, les titulaires de l'E28A ne peuvent pas travailler.",
        innocence:
          "vous pouvez être directeur ou commissaire de la PT PMA dans laquelle vous avez investi",
      },
      ru: {
        re: /держател[а-яё]+ E28A[^.\n]{0,30}не могут работать|одновременно акционером и директором, что требует|Выступать в качестве директора компании \(Direktur\)|вам нужен E25B Director KITAS вместо/i,
        guilt: "Однако держатели E28A не могут работать.",
        innocence:
          "вы можете быть директором или комиссаром PT PMA, в которую вы инвестировали",
      },
    },
  },
];

/** Count rule: the Golden guides may name ITAP once, to say the Golden Visa is not it. */
const ITAP_MAX = 1;
const countItap = (text: string) => (text.match(/\bITAP\b/g) ?? []).length;

/** Digits normalised so every locale's number format meets the same needle. */
function norm(text: string): string {
  let t = text.replace(/\*/g, "").replace(/[  ]/g, " ");
  let prev = "";
  while (prev !== t) {
    prev = t;
    t = t.replace(/(\d)[.,\s](?=\d{3}(?!\d))/g, "$1");
  }
  return t.replace(/(\d),(\d)/g, "$1.$2");
}

/** Positive facts every locale must state (checked on the normalised text). */
const FACTS: Record<string, { file: string; needles: RegExp[] }> = {};
function facts(label: string, file: string, needles: RegExp[]) {
  FACTS[label] = { file, needles };
}
const e28a = (loc: Loc) => fileOf("e28a-investor-kitas-guide", loc);
const golden = (loc: Loc) =>
  fileOf("golden-visa-indonesia-complete-guide", loc);
const investor = (loc: Loc) => fileOf("investor-kitas-guide", loc);

facts("E28A en", e28a("en"), [
  /IDR 10 billion/,
  /all-inclusive/,
  /sponsor/,
  /IDR 2\.5 billion paid-up/,
  /at least 6 months/,
  /director or commissioner/,
  /IDR 17000000/,
  /IDR 19000000/,
  /IDR 18000000/,
  /7-10 working days/,
  /five working days/,
  /USD 350000/,
  /USD 25M/,
  /price on consultation/,
]);
facts("E28A id", e28a("id"), [
  /Rp 10 miliar/,
  /all-inclusive/,
  /penjamin/,
  /Rp 2\.5 miliar/,
  /minimal 6 bulan/,
  /direktur atau komisaris/,
  /17000000/,
  /19000000/,
  /18000000/,
  /7-10 hari kerja/,
  /lima hari kerja/,
  /USD 350000/,
  /USD 25 juta/,
  /harga sesuai konsultasi/,
]);
facts("E28A it", e28a("it"), [
  /IDR 10 miliardi/,
  /tutto incluso/,
  /sponsor/,
  /IDR 2\.5 miliardi di capitale versato/,
  /almeno 6 mesi/,
  /amministratore o commissario/,
  /17000000/,
  /19000000/,
  /18000000/,
  /7-10 giorni lavorativi/,
  /cinque giorni lavorativi/,
  /USD 350000/,
  /USD 25M/,
  /prezzo su consulenza/,
]);
facts("E28A fr", e28a("fr"), [
  /10 milliards IDR/,
  /tout compris/,
  /sponsor/,
  /2\.5 milliards IDR de capital libéré/,
  /au moins 6 mois/,
  /directeur ou commissaire/,
  /17000000/,
  /19000000/,
  /18000000/,
  /7-10 jours ouvrables/,
  /cinq jours ouvrables/,
  /350000 USD/,
  /25 M USD/,
  /sur devis/,
]);
facts("E28A ru", e28a("ru"), [
  /10 миллиардов IDR/,
  /все включено/,
  /спонсор/,
  /2\.5 миллиарда IDR/,
  /не менее 6 месяцев/,
  /директором или комиссаром/,
  /17000000/,
  /19000000/,
  /18000000/,
  /7-10 рабочих дней/,
  /пять рабочих дней/,
  /USD 350000/,
  /USD 25 млн/,
  /по цене после консультации/,
]);

facts("golden en", golden("en"), [
  /USD 2\.5M/,
  /USD 5M/,
  /USD 350000/,
  /USD 700000/,
  /USD 1000000/,
  /USD 25M/,
  /USD 50M/,
  /USD 10M/,
  /within 90 days of entry/,
  /no sponsor needed/,
  /price on consultation/,
  /E28E/,
  /ITAS/,
  /not permanent residence/,
]);
facts("golden id", golden("id"), [
  /USD 2\.5 juta/,
  /USD 5 juta/,
  /USD 350000/,
  /USD 700000/,
  /USD 1000000/,
  /USD 25 juta/,
  /USD 50 juta/,
  /USD 10 juta/,
  /90 hari setelah masuk/,
  /tanpa sponsor/,
  /harga sesuai konsultasi/,
  /E28E/,
  /ITAS/,
  /bukan izin tinggal tetap/,
]);
facts("golden it", golden("it"), [
  /USD 2\.5M/,
  /USD 5M/,
  /USD 350000/,
  /USD 700000/,
  /USD 1000000/,
  /USD 25M/,
  /USD 50M/,
  /USD 10M/,
  /90 giorni/,
  /senza sponsor/,
  /prezzo su consulenza/,
  /E28E/,
  /ITAS/,
  /Non è una residenza permanente/,
]);
facts("golden fr", golden("fr"), [
  /2\.5 M USD/,
  /5 M USD/,
  /350000 USD/,
  /700000 USD/,
  /1000000 USD/,
  /25 M USD/,
  /50 M USD/,
  /10 M USD/,
  /90 jours/,
  /sans sponsor/,
  /sur devis/,
  /E28E/,
  /ITAS/,
  /ne s'agit pas d'une résidence permanente/,
]);
facts("golden ru", golden("ru"), [
  /USD 2\.5 млн/,
  /USD 5 млн/,
  /USD 350000/,
  /USD 700000/,
  /USD 1000000/,
  /USD 25 млн/,
  /USD 50 млн/,
  /USD 10 млн/,
  /90 дней/,
  /без спонсора/,
  /по цене после консультации/,
  /E28E/,
  /ITAS/,
  /не постоянное проживание/,
]);

facts("investor en", investor("en"), [
  /IDR 10 billion/,
  /IDR 2500000000/,
  /at least 6 months/,
  /USD 350000/,
  /USD 25M/,
  /E28F/,
  /director or commissioner/,
  /all-inclusive/,
]);
facts("investor id", investor("id"), [
  /Rp 10 miliar/,
  /Rp 2500000000/,
  /minimal 6 bulan/,
  /USD 350000/,
  /USD 25 juta/,
  /E28F/,
  /direktur atau komisaris/,
  /all-inclusive/,
]);
facts("investor it", investor("it"), [
  /IDR 10 miliardi/,
  /IDR 2500000000/,
  /almeno 6 mesi/,
  /USD 350000/,
  /USD 25M/,
  /E28F/,
  /amministratore o commissario/,
  /tutto incluso/,
]);
facts("investor fr", investor("fr"), [
  /10 milliards IDR/,
  /2500000000 IDR/,
  /au moins 6 mois/,
  /350000 USD/,
  /25 M USD/,
  /E28F/,
  /directeur ou commissaire/,
  /tout compris/,
]);
facts("investor ru", investor("ru"), [
  /IDR 10B/,
  /IDR 2500000000/,
  /не менее 6 месяцев/,
  /USD 350000/,
  /USD 25 млн/,
  /E28F/,
  /директором или комиссаром/,
  /Цены на Investor KITAS включают всё/,
]);

facts("/visa/kitas", KITAS_PAGE[0].file, [
  /Rp 10 billion/,
  /7–10 hari kerja/,
  /USD 25/,
  /USD 50/,
  /price on consultation/,
  /\/visas\/golden-visa-indonesia-complete-guide/,
  /sponsoring PT PMA/,
]);

describe("E28 family truth guard: every rule catches its guilt and spares its innocence", () => {
  for (const rule of RULES) {
    for (const [loc, sample] of Object.entries(rule.by)) {
      it(`${rule.id} [${loc}]: guilt sample is caught`, () => {
        expect(sample!.re.test(sample!.guilt)).toBe(true);
      });
      it(`${rule.id} [${loc}]: innocence sample is left alone`, () => {
        expect(sample!.re.test(sample!.innocence)).toBe(false);
      });
    }
  }
  it("ITAP counter: one negating mention passes, a card or a (ITAP) label does not", () => {
    expect(countItap("it is not ITAP or KITAP")).toBe(1);
    expect(countItap("Golden Visa ITAP grants ITAP card")).toBeGreaterThan(
      ITAP_MAX,
    );
    expect(countItap("see the KITAP guide")).toBe(0);
  });
  it("number normaliser: the same figure meets one needle in every format", () => {
    expect(norm("USD 350.000")).toContain("USD 350000");
    expect(norm("350 000 USD")).toContain("350000 USD");
    expect(norm("USD 2,5 juta")).toContain("USD 2.5 juta");
    expect(norm("IDR 17,000,000")).toContain("IDR 17000000");
  });
});

describe("E28 family truth guard: the articles", () => {
  for (const rule of RULES) {
    for (const { loc, file } of rule.files) {
      const sample = pick(rule, loc);
      if (!sample) continue;
      const name = path.relative(process.cwd(), file);
      it(`${rule.id} :: ${name}`, () => {
        const hits = read(file)
          .split("\n")
          .map((line, i) => ({ line, n: i + 1 }))
          .filter(({ line }) => sample.re.test(line))
          .map(({ n, line }) => `${n}: ${line.trim().slice(0, 120)}`);
        expect(hits, `${rule.id} still present in ${name}`).toEqual([]);
      });
    }
  }
  for (const { file } of GOLDEN) {
    const name = path.relative(process.cwd(), file);
    it(`Golden Visa names ITAP at most once (to deny it) :: ${name}`, () => {
      expect(countItap(read(file))).toBeLessThanOrEqual(ITAP_MAX);
    });
  }
});

describe("E28 family truth guard: the correct sentences are present in every locale", () => {
  for (const [label, { file, needles }] of Object.entries(FACTS)) {
    const text = norm(read(file));
    for (const needle of needles) {
      it(`${label} states ${needle.source}`, () => {
        expect(needle.test(text)).toBe(true);
      });
    }
  }
});
