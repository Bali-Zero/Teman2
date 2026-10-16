// =============================================================================
// E28 FAMILY TRUTH GUARD (mission E28-close-1015, PR D round 2).
//
// Every sentence in the E28A, Investor KITAS and Golden Visa guides must trace
// to (a) the official Imigrasi pages for E28A-E28F read on 2026-10-15
// (research/visa/2026-10-15-e28-pages/), (b) the owner rulings of that day, or
// (c) Bali Zero's 2026 price list. Untraceable text is deleted, not softened.
//
// The guides are live in five locales (en, id, it, fr, ru). Matching is done on
// the WHOLE file with newlines collapsed (a claim that wraps onto the next line
// is still a claim). Each forbidden rule is ENTITY-scoped (the number or code
// sits NEAR the thing it is wrong about), carries a guilt sample it must catch
// in EN and in at least one other locale, and innocence samples it must spare.
// =============================================================================
import crypto from "crypto";
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
const GUIDES = [...E28A, ...GOLDEN, ...INVESTOR];
const ALL = [...GUIDES, ...KITAS_PAGE];

/** Digits normalised so every locale's number format meets the same needle. */
function norm(text: string): string {
  return text
    .replace(/\*/g, "")
    .replace(/[  ]/g, " ")
    .replace(/(\d)[.,\s](?=\d{3}(?!\d))/g, "$1");
}
/** The whole file, one line, the integrity hash dropped. */
const flat = (file: string) =>
  norm(
    read(file)
      .replace(/^source_sha256:.*$/m, "")
      .replace(/\s+/g, " "),
  );

// -----------------------------------------------------------------------------
// FORBIDDEN, in every locale
// -----------------------------------------------------------------------------
interface Rule {
  id: string;
  files: { loc: Loc; file: string }[];
  re: RegExp;
  guilt: string[];
  innocence: string[];
}

const RULES: Rule[] = [
  {
    id: "no KITAP pathway or KITAP timeline",
    files: GUIDES,
    re: /KITAP (pathway|path|route|timeline)|(pathway|path|route)s? (to|for) (the )?(KITAP|permanent)|Investor KITAP\b|(percorso|jalur|parcours|chemin|путь|пути)[^.|]{0,30}(KITAP|permanent|постоян)|(after|dopo|setelah|après|через) \d+ [^.|]{0,60}KITAP/i,
    guilt: [
      "After 3 consecutive years on E28A you can apply for Investor KITAP.",
      "The KITAP pathway for E28A holders",
      "Dopo 3 anni consecutivi con E28A puoi chiedere il KITAP",
      "Jalur menuju KITAP setelah 3 tahun",
      "Le parcours vers le KITAP pour les investisseurs",
      "Путь к KITAP после трёх лет",
    ],
    innocence: [
      "It is not ITAP or KITAP and it does not replace KITAP.",
      "Read the KITAP Permanent Residence Guide for permanent residence.",
      "children or dependent family members of a primary KITAS/KITAP holder",
    ],
  },
  {
    id: "no embassy Telex, visa sticker or 7-day conversion",
    files: GUIDES,
    re: /Telex|sticker|stiker|autocollant|adesiv|наклейк|embassy|ambasciata|kedutaan|ambassade|посольств|within 7 days|7[- ]day (conversion|window)|entro 7 giorni|dalam 7 hari|sous 7 jours|в течение 7 дней/i,
    guilt: [
      "Collect the visa sticker at the embassy within 7 days",
      "Telex approval is sent to the embassy",
      "Ritira l'adesivo del visto in ambasciata entro 7 giorni",
      "Ambil stiker visa di kedutaan dalam 7 hari",
      "Récupérez l'autocollant du visa à l'ambassade",
      "Получите наклейку визы в посольстве в течение 7 дней",
    ],
    innocence: [
      "Bali Zero typically takes 7-10 working days (indicative).",
      "di norma 7-10 giorni lavorativi",
      "The visa stage takes five working days after the visa fee is paid.",
    ],
  },
  {
    id: "no tax percentages or 183-day advice",
    files: GUIDES,
    re: /183[- ]?(day|hari|giorni|jours|дн)|tax resident|residente fiscale|resident pajak|résident fiscal|налоговый резидент|worldwide income|redditi mondiali|penghasilan global|\d+(\.\d+)? ?% ?(tax|pph|income tax|di imposta|d'impôt|налог)|PPh ?\d/i,
    guilt: [
      "Stay over 183 days and you become a tax resident",
      "Oltre 183 giorni diventi residente fiscale",
      "Tinggal lebih dari 183 hari menjadi resident pajak",
      "Plus de 183 jours : résident fiscal",
      "Более 183 дней - налоговый резидент",
      "Dividend income is taxed at 20% tax",
    ],
    innocence: [
      "Bali Zero's prices are all-inclusive: government fees and Bali Zero service are included.",
      "The visa is valid for 90 days from issuance.",
    ],
  },
  {
    id: "no E25B / RPTKA / DKP-TKA prices",
    files: GUIDES,
    re: /(RPTKA|DKP[- ]?TKA|E25B)[^.|]{0,60}((IDR|Rp|USD) ?\d|\d{3,} ?(IDR|USD|dollars|juta|million))|(IDR|Rp) ?\d[\d]*[^.|]{0,40}(RPTKA|DKP[- ]?TKA)/i,
    guilt: [
      "E25B costs IDR 34,500,000 including RPTKA",
      "An RPTKA fee of USD 1,200 applies",
      "E25B costa IDR 34.500.000 con RPTKA",
      "RPTKA Rp 10.000.000 per tahun",
      "Le RPTKA coûte 1 200 USD",
      "DKP-TKA 1200 USD в год",
    ],
    innocence: [
      "E25B Director KITAS Guide E23 Employee KITAS Guide KBLI 2025 Capital Requirements",
      "No RPTKA is needed for the E28A.",
    ],
  },
  {
    id: "no 'pure investor' and no passive-investment visa",
    files: GUIDES,
    re: /pure investor|pure[- ]invest|passive[- ]invest(ment|or)s? visa|investitore puro|investisseur pur|investor murni|чистый инвестор|visto (per |di )?investimento passivo|visa investasi pasif|visa d'investissement passif|пассивн[а-яё]+ инвестиционн[а-яё]+ виз/i,
    guilt: [
      "E28A is for the pure investor",
      "E28A is a passive investment visa",
      "L'E28A è un visto per investimento passivo",
      "E28A adalah visa investasi pasif",
      "Le visa d'investissement passif E28A",
      "Это пассивная инвестиционная виза E28A",
    ],
    innocence: [
      "E28A admits passive shareholders with sufficient own shareholding.",
      "L'E28A ammette i soci passivi con una partecipazione personale sufficiente.",
      "E28A menerima pemegang saham pasif dengan kepemilikan saham sendiri yang cukup.",
    ],
  },
  {
    id: "no denial of directorship, supervision or signing on E28A",
    files: [...E28A, ...INVESTOR, ...GOLDEN],
    re: /(cannot|can't|may not|must not|not allowed to|not permitted to) (work|supervise|sign|act|serve)[^.|]{0,60}(director|commissioner|contract)|(non puoi|non possono)[^.|]{0,60}(amministrator|commissari|firmare|supervision)|(tidak dapat|tidak boleh|dilarang)[^.|]{0,40}(menjadi |bertindak sebagai |menandatangani )(direktur|komisaris|kontrak)|(ne pouvez pas|ne peuvent pas)[^.|]{0,60}(directeur|commissaire|signer|superviser)|(нельзя|не можете|не могут)[^.|]{0,60}(директор|комиссар|подписыва|контролиров)|E28A holders? cannot|pemegang E28A tidak dapat|titolari di E28A non possono|titulaires de l'E28A ne peuvent pas|держател[а-яё]+ E28A[^.|]{0,30}не могут/i,
    guilt: [
      "You cannot sign contracts as director on an E28A",
      "E28A holders cannot work.",
      "Non puoi firmare come amministratore con l'E28A",
      "Pemegang E28A tidak dapat bekerja",
      "Vous ne pouvez pas signer comme directeur",
      "Нельзя подписывать договоры как директор",
    ],
    innocence: [
      "The E28A lets you act as a member of the board of directors or the board of commissioners.",
      "Prohibited: staying beyond the stay permit, work that does not match the stay permit.",
      "You may act as director or commissioner of the company you invested in.",
    ],
  },
  {
    id: "no E28A price other than 17/19/18M, no fee split, no PNBP",
    files: [...E28A, ...INVESTOR],
    re: /PNBP|verification fees?|biaya verifikasi|frais de vérification|tassa di verifica|сбор за верификац|government fees? (of|:|is|are separate|are paid separately)|biaya pemerintah (sebesar|terpisah|belum termasuk)|plus government fees|excluding government fees|belum termasuk biaya pemerintah|tasse governative (di|sono separate)|escluse le tasse governative|più tasse governative|frais gouvernementaux (de|sont séparés)|hors frais gouvernementaux|государственные сборы (оплачиваются )?отдельно|без учета государственных сборов|service fee (of|:)/i,
    guilt: [
      "IDR 17M; government fees are separate",
      "PNBP visa fee of IDR 2,000,000",
      "Rp 17 juta; biaya pemerintah terpisah",
      "Tasse governative di IDR 2.000.000 più servizio",
      "Frais de vérification de 500 000 IDR",
      "Государственные сборы оплачиваются отдельно",
    ],
    innocence: [
      "Bali Zero's prices are all-inclusive: government fees and Bali Zero service are included.",
      "Investor KITAS 2 Years (Extend)",
      "The visa stage takes five working days after the visa fee is paid.",
    ],
  },
  {
    id: "no 90-day commitment on E28C",
    files: [...GOLDEN, ...INVESTOR, ...E28A],
    re: /E28C[^|.]{0,200}(90[- ]?(day|hari|giorni|jours)|90 дн)/i,
    guilt: [
      "E28C requires a commitment fulfilled within 90 days after entry",
      "E28C richiede un impegno entro 90 giorni dall'ingresso",
      "E28C memerlukan komitmen dalam 90 hari",
      "E28C exige un engagement dans les 90 jours",
    ],
    innocence: [
      "| E28C | Proof of ownership of at least USD 350,000 | ... | E28D | within 90 days after entry |",
      "For E28B, E28D and E28F the investment must be fulfilled within 90 days after entry.",
    ],
  },
  {
    id: "no 'commits within 90 days' wording",
    files: [...GOLDEN, ...INVESTOR, ...E28A, ...KITAS_PAGE],
    re: /\bcommit(s|ted|ment)?\b[^.|,]{0,25}\bwithin 90 days|si impegna[^.|,]{0,20}entro 90|s'engage[^.|,]{0,40}90 jours|berkomitmen[^.|,]{0,40}(dalam|selama) (waktu )?90 hari|обязуется[^.|,]{0,40}90 дн/i,
    guilt: [
      "The foreign company commits USD 25M within 90 days of entry",
      "The foreign company must commit to invest within 90 days",
      "La società estera si impegna entro 90 giorni dall'ingresso",
      "Perusahaan asing berkomitmen dalam waktu 90 hari",
      "La société s'engage à investir dans les 90 jours",
    ],
    innocence: [
      "The foreign company, not you, is the party that commits to the investment, and it must fulfil it within 90 days after your entry.",
      "L'investimento deve essere realizzato entro 90 giorni dall'ingresso.",
      "the statement of commitment goes with the application, and the investment must be fulfilled within 90 days after entry",
    ],
  },
  {
    id: "E28G is not a route",
    files: ALL,
    re: /E28G(?! (is not|isn't|bukan|non è|non esiste|n'est pas|n'existe pas|не является|не существует|does not exist|tidak ada))/i,
    guilt: [
      "### E28G: Representative of Parent Company",
      "E28G (rappresentante della capogruppo)",
      "E28G untuk perwakilan perusahaan induk",
    ],
    innocence: [
      "E28G is not a current visa.",
      "E28G non è un visto attuale.",
      "E28F is the same route in IKN; E28E has no published details.",
    ],
  },
  {
    id: "no IDR 350M tier, no USD 23,333",
    files: [...GOLDEN, ...INVESTOR],
    re: /(IDR|Rp\.?) ?350 ?(M\b|juta|milioni|millions?|млн|million)|(IDR|Rp\.?) ?350000000|350000000 ?IDR|USD 23333/i,
    guilt: [
      "Golden Visa: IDR 350M+ investment",
      "Golden Visa: Rp 350.000.000 investasi",
      "Golden Visa : 350 000 000 IDR",
    ],
    innocence: [
      "E28C needs USD 350,000 in Indonesian government bonds",
      "E28C richiede USD 350.000 in titoli di Stato indonesiani",
    ],
  },
  {
    id: "Golden Visa is an ITAS, not ITAP / permanent residence",
    files: GOLDEN,
    re: /\(ITAP\)|\bITAP -|ITAP card|carta ITAP|called ITAP|chiamat\w+ (ufficialmente )?ITAP|appelé( officiellement)? ITAP|Golden Visa[^.|]{0,50}\b(grants|offers|provides|gives|is)\s+(a\s+)?permanent residence/i,
    guilt: [
      "Golden Visa (ITAP) grants permanent residence",
      "Golden Visa ITAP card for five years",
      "Golden Visa offers permanent residence",
      "La carta ITAP del Golden Visa",
    ],
    innocence: [
      "The Golden Visa is a limited-stay visa (ITAS). It is not ITAP or KITAP and it does not replace KITAP.",
      "Golden Visa - не постоянное проживание",
    ],
  },
  {
    id: "the E28A test is own shareholding, not the company's paid-up capital",
    files: [...E28A, ...INVESTOR, ...KITAS_PAGE],
    re: /(paid[- ](in|up) capital|modal (dasar|disetor)|capitale (sociale )?versato|capital (social )?libéré|оплаченн[а-яё]+ капитал)[^.|+()]{0,40}(10 (billion|miliar|miliardi|milliards|млрд|миллиард)|10000000000)/i,
    guilt: [
      "Total company paid-up capital of IDR 10 billion minimum",
      "Modal disetor perusahaan minimal Rp 10 miliar",
      "Capitale versato della società di almeno IDR 10 miliardi",
      "Capital libéré d'au moins 10 milliards IDR",
    ],
    innocence: [
      "The PT PMA's own paid-up capital of IDR 2.5 billion (BKPM Regulation 5/2025) is the company's threshold.",
      "Modal disetor PT PMA sendiri sebesar Rp 2,5 miliar",
      "Собственный оплаченный капитал самой PT PMA в размере IDR 2,5 миллиарда",
    ],
  },
  {
    id: "the passport rule is 6 months",
    files: [...E28A, ...INVESTOR],
    re: /(passport|paspor|passaporto|passeport|паспорт)[^.|;]{0,60}\b(18|24)\+? (months?|bulan|mesi|mois|месяц)/i,
    guilt: [
      "Passport valid for minimum 18 months",
      "Paspor berlaku minimal 18 bulan",
      "Passaporto valido per minimo 18 mesi",
    ],
    innocence: [
      "National passport valid for at least 6 months before it expires",
      "Passport at least 6 months; bank history 18 months",
    ],
  },
  {
    id: "the visa stage is five working days, not 5-7",
    files: [...E28A, ...INVESTOR, ...KITAS_PAGE],
    re: /5 ?[-–] ?7 (working days|hari kerja|giorni lavorativi|jours ouvrables|рабочих дней)/i,
    guilt: [
      "Processing Time | 5-7 working days",
      "Waktu Pemrosesan | 5-7 hari kerja",
      "Tempistica: 5-7 giorni lavorativi",
    ],
    innocence: [
      "typically 7-10 working days with Bali Zero (indicative)",
      "7-10 hari kerja bersama Bali Zero (indikatif)",
    ],
  },
  {
    id: "E28D is not a representative-office permit",
    files: KITAS_PAGE,
    re: /KPPA|KP3A|E28D[^\n]*(Representative Office|Kantor Perwakilan)|Director KITAS \(Representative/i,
    guilt: [
      "## E28D — Director KITAS (Representative Office)",
      "E28D Kantor Perwakilan",
    ],
    innocence: [
      "E28D — Golden Visa (Branch or Subsidiary of a Foreign Company)",
    ],
  },
  {
    id: "E28A kitas-page row: no 20-30 hari",
    files: KITAS_PAGE,
    re: /E28A[^\n]*20 ?[–-] ?30 hari/,
    guilt: [
      "| E28A — Investor KITAS | PT PMA shareholders | x | 20–30 hari |",
      "| E28A — Investor KITAS | owners | x | 20-30 hari |",
    ],
    innocence: [
      "| E28A — Investor KITAS | owners | x | 7–10 hari kerja (indicative) |",
    ],
  },
  {
    id: "no hands-on-work claim hung on the E23",
    files: [...E28A, ...INVESTOR, ...KITAS_PAGE],
    re: /hands-on (operational )?work|lavoro operativo|pekerjaan operasional|travail opérationnel|операционн[а-яё]+ работ/i,
    guilt: [
      "hands-on operational work requires a Working KITAS (E23)",
      "il lavoro operativo richiede un KITAS Lavorativo",
    ],
    innocence: [
      "Supervise the production of goods or services at the company you established",
    ],
  },
];

describe("E28 family truth guard: every forbidden rule catches its guilt and spares its innocence", () => {
  for (const rule of RULES) {
    rule.guilt.forEach((g, i) =>
      it(`${rule.id}: guilt sample ${i + 1} is caught`, () => {
        expect(rule.re.test(norm(g))).toBe(true);
      }),
    );
    rule.innocence.forEach((n, i) =>
      it(`${rule.id}: innocence sample ${i + 1} is left alone`, () => {
        expect(rule.re.test(norm(n))).toBe(false);
      }),
    );
    it(`${rule.id}: guilt is shown in EN and in another locale`, () => {
      expect(rule.guilt.length).toBeGreaterThanOrEqual(2);
    });
  }
  it("number normaliser: the same figure meets one needle in every format", () => {
    expect(norm("USD 350.000")).toContain("USD 350000");
    expect(norm("350 000 USD")).toContain("350000 USD");
    expect(norm("USD 2,5 juta")).toContain("USD 2,5 juta");
    expect(norm("IDR 17,000,000")).toContain("IDR 17000000");
    expect(norm("Rp 10.000.000.000")).toContain("Rp 10000000000");
  });
});

describe("E28 family truth guard: no forbidden claim survives in any article", () => {
  for (const rule of RULES) {
    for (const { file } of rule.files) {
      const name = path.relative(process.cwd(), file);
      it(`${rule.id} :: ${name}`, () => {
        const text = flat(file);
        const m = rule.re.exec(text);
        expect(
          m ? text.slice(Math.max(0, m.index - 60), m.index + 120) : null,
          `${rule.id} still present in ${name}`,
        ).toBeNull();
      });
    }
  }
});

// -----------------------------------------------------------------------------
// Prices: every figure of 1,000,000 or more must be one the sources give
// -----------------------------------------------------------------------------
const E28A_FIGURES = new Set([
  "17000000",
  "19000000",
  "18000000", // E28A, all-inclusive (ruling 4)
  "11000000",
  "13500000",
  "9000000",
  "15000000", // Dependent KITAS rows
  "10000000000", // IDR 10 billion own shareholding (ruling 1)
]);
const GOLDEN_FIGURES = new Set([
  "1000000",
  "2500000",
  "5000000",
  "10000000",
  "25000000",
  "50000000", // USD, official pages
  "17000000",
  "10000000000", // the E28A comparison row
]);
const strayFigures = (text: string, ok: Set<string>) =>
  (norm(text).match(/\d{7,}/g) ?? []).filter((n) => !ok.has(n));

describe("E28 family truth guard: no stray price", () => {
  it("catches a price the sources do not give, in EN and ID", () => {
    expect(strayFigures("IDR 20,000,000 offshore", E28A_FIGURES)).toEqual([
      "20000000",
    ]);
    expect(strayFigures("Rp 20.000.000 offshore", E28A_FIGURES)).toEqual([
      "20000000",
    ]);
  });
  it("spares the sourced prices", () => {
    expect(
      strayFigures(
        "IDR 17,000,000 / Rp 19.000.000 / 18 000 000 IDR / Rp 10.000.000.000",
        E28A_FIGURES,
      ),
    ).toEqual([]);
  });
  for (const { file } of [...E28A, ...INVESTOR]) {
    it(`E28A / Investor figures :: ${path.relative(process.cwd(), file)}`, () => {
      expect(
        strayFigures(
          read(file).replace(/^source_sha256:.*$/m, ""),
          E28A_FIGURES,
        ),
      ).toEqual([]);
    });
  }
  for (const { file } of GOLDEN) {
    it(`Golden figures :: ${path.relative(process.cwd(), file)}`, () => {
      expect(
        strayFigures(
          read(file).replace(/^source_sha256:.*$/m, ""),
          GOLDEN_FIGURES,
        ),
      ).toEqual([]);
    });
  }
});

// -----------------------------------------------------------------------------
// REQUIRED, in every locale
// -----------------------------------------------------------------------------
const GOLDEN_DIGITS = [
  /2500000/,
  /5000000/,
  /350000/,
  /700000/,
  /1000000/,
  /25000000/,
  /50000000/,
  /10000000/,
];
const E28A_FIGS = [/17000000/, /19000000/, /18000000/];

const E28A_NEEDLES: Record<Loc, RegExp[]> = {
  en: [
    /own shareholding of at least IDR 10 billion/i,
    /ITAS and the re-entry permit are issued automatically/i,
    /Visa application letter/i,
    /valid for at least 6 months/i,
    /at least USD 2000/i,
    /Recent colour photo/i,
    /Curriculum vitae/i,
    /Itinerary/i,
    /Proof of shareholding/i,
    /Ministry of Law decision/i,
    /current-account \(giro\) statements for the last 2 months/i,
    /up to 90 days after the ITAS is issued/i,
    /all-inclusive: government fees and Bali Zero service are included/i,
    /Investor KITAS 2 Years \(Extend\)/,
  ],
  id: [
    /kepemilikan saham sendiri minimal Rp 10 miliar/i,
    /ITAS dan Izin Masuk Kembali terbit secara otomatis/i,
    /Surat permohonan penerbitan visa/i,
    /masih berlaku paling singkat 6 bulan/i,
    /minimal USD 2000/i,
    /Pasfoto berwarna terbaru/i,
    /Daftar riwayat hidup/i,
    /Rincian perjalanan/i,
    /Bukti kepemilikan saham/i,
    /Keputusan Kementerian Hukum/i,
    /Rekening giro perusahaan 2 bulan terakhir/i,
    /90 hari setelah ITAS terbit/i,
    /all-inclusive: biaya pemerintah dan jasa Bali Zero termasuk/i,
    /Investor KITAS 2 Years \(Extend\)/,
  ],
  it: [
    /partecipazione personale di almeno IDR 10 miliardi/i,
    /ITAS e il permesso di rientro vengono emessi automaticamente/i,
    /Lettera di richiesta del visto/i,
    /valido per almeno 6 mesi/i,
    /almeno USD 2000/i,
    /Fototessera a colori recente/i,
    /Curriculum vitae/i,
    /Itinerario/i,
    /Prova di una partecipazione/i,
    /decisione del Ministero della Giustizia/i,
    /estratti del conto corrente \(giro\) della società degli ultimi 2 mesi/i,
    /entro 90 giorni dall'emissione dell'ITAS/i,
    /tutto incluso: tasse governative e servizio Bali Zero compresi/i,
    /Investor KITAS 2 Years \(Extend\)/,
  ],
  fr: [
    /participation personnelle d'au moins 10 milliards IDR/i,
    /ITAS et le permis de réadmission sont délivrés automatiquement/i,
    /Lettre de demande de visa/i,
    /valide au moins 6 mois/i,
    /au moins 2000 USD/i,
    /Photo couleur récente/i,
    /Curriculum vitae/i,
    /Itinéraire/i,
    /Preuve d'une participation/i,
    /décision du ministère de la Justice/i,
    /relevés du compte courant \(giro\) de la société des 2 derniers mois/i,
    /jusqu'à 90 jours après la délivrance de l'ITAS/i,
    /tout compris : frais gouvernementaux et service Bali Zero inclus/i,
    /Investor KITAS 2 Years \(Extend\)/,
  ],
  ru: [
    /личное долевое участие не менее IDR 10 миллиардов/i,
    /ITAS и разрешение на повторный въезд выдаются автоматически/i,
    /Заявление на выдачу визы/i,
    /действительный не менее 6 месяцев/i,
    /не менее USD 2000/i,
    /Недавняя цветная фотография/i,
    /Резюме \(CV\)/i,
    /Маршрут поездки/i,
    /Подтверждение владения долями/i,
    /Решение Министерства юстиции/i,
    /Выписки по текущему счёту \(giro\) компании за последние 2 месяца/i,
    /не позднее 90 дней после выдачи ITAS/i,
    /включают всё: государственные сборы и услуги Bali Zero/i,
    /Investor KITAS 2 Years \(Extend\)/,
  ],
};

const GOLDEN_NEEDLES: Record<Loc, RegExp[]> = {
  en: [
    /fulfilled within 90 days after entry/i,
    /appointed as a director or commissioner/i,
    /foreign company, not you, is the party that commits/i,
    /re-entry permit are issued automatically/i,
    /international public accounting firm/i,
    /Rangkap Kegiatan Izin Tinggal/,
    /price on consultation/i,
  ],
  id: [
    /dipenuhi dalam waktu 90 hari setelah masuk/i,
    /diangkat sebagai direksi atau komisaris/i,
    /Perusahaan asing, bukan Anda, yang berkomitmen/i,
    /Izin Masuk Kembali terbit secara otomatis/i,
    /kantor akuntan publik internasional/i,
    /Rangkap Kegiatan Izin Tinggal/,
    /harga sesuai konsultasi/i,
  ],
  it: [
    /realizzato entro 90 giorni dall'ingresso/i,
    /nominato amministratore o commissario/i,
    /La società estera, non tu, è la parte che si impegna/i,
    /permesso di rientro vengono emessi automaticamente/i,
    /società di revisione internazionale/i,
    /Rangkap Kegiatan Izin Tinggal/,
    /prezzo su richiesta/i,
  ],
  fr: [
    /réalisé dans les 90 jours suivant l'entrée/i,
    /nommé directeur ou commissaire/i,
    /La société étrangère, et non vous, est la partie qui s'engage/i,
    /permis de réadmission sont délivrés automatiquement/i,
    /cabinet d'audit international/i,
    /Rangkap Kegiatan Izin Tinggal/,
    /sur devis/i,
  ],
  ru: [
    /осуществлена в течение 90 дней после въезда/i,
    /назначить директором или комиссаром/i,
    /берёт на себя иностранная компания, а не вы/i,
    /разрешение на повторный въезд выдаются автоматически/i,
    /международной аудиторской фирмы/i,
    /Rangkap Kegiatan Izin Tinggal/,
    /цена по запросу/i,
  ],
};

const INVESTOR_NEEDLES: Record<Loc, RegExp[]> = {
  en: [
    /Own shareholding of at least IDR 10 billion/i,
    /re-entry permit are issued automatically/i,
    /all-inclusive: government fees and Bali Zero service are included/i,
    /\(\/immigration\/e28a-investor-kitas-guide\)/,
  ],
  id: [
    /Kepemilikan saham sendiri minimal Rp 10 miliar/i,
    /Izin Masuk Kembali terbit otomatis/i,
    /all-inclusive: biaya pemerintah dan jasa Bali Zero termasuk/i,
    /\(\/immigration\/e28a-investor-kitas-guide\)/,
  ],
  it: [
    /Partecipazione personale di almeno IDR 10 miliardi/i,
    /permesso di rientro vengono emessi automaticamente/i,
    /tutto incluso: tasse governative e servizio Bali Zero compresi/i,
    /\(\/immigration\/e28a-investor-kitas-guide\)/,
  ],
  fr: [
    /Participation personnelle d'au moins 10 milliards IDR/i,
    /permis de réadmission sont délivrés automatiquement/i,
    /tout compris : frais gouvernementaux et service Bali Zero inclus/i,
    /\(\/immigration\/e28a-investor-kitas-guide\)/,
  ],
  ru: [
    /Личное долевое участие не менее IDR 10 миллиардов/i,
    /разрешение на повторный въезд выдаются автоматически/i,
    /включают всё: государственные сборы и услуги Bali Zero/i,
    /\(\/immigration\/e28a-investor-kitas-guide\)/,
  ],
};

describe("E28 family truth guard: the correct sentences are present in every locale", () => {
  const run = (
    label: string,
    files: { loc: Loc; file: string }[],
    needles: Record<Loc, RegExp[]>,
    extra: RegExp[],
  ) => {
    for (const { loc, file } of files) {
      const text = flat(file);
      for (const n of [...needles[loc], ...extra]) {
        it(`${label} [${loc}] states ${n.source}`, () => {
          expect(n.test(text)).toBe(true);
        });
      }
    }
  };
  run("E28A guide", E28A, E28A_NEEDLES, E28A_FIGS);
  run("Golden guide", GOLDEN, GOLDEN_NEEDLES, GOLDEN_DIGITS);
  run("Investor KITAS guide", INVESTOR, INVESTOR_NEEDLES, E28A_FIGS);
  for (const { file } of KITAS_PAGE) {
    const text = flat(file);
    for (const n of [
      /Rp 10 billion/,
      /7–10 hari kerja/,
      /USD 25/,
      /USD 50/,
      /price on consultation/,
      /\/visas\/golden-visa-indonesia-complete-guide/,
      /sponsoring PT PMA/,
    ]) {
      it(`/visa/kitas states ${n.source}`, () => {
        expect(n.test(text)).toBe(true);
      });
    }
  }
});

// -----------------------------------------------------------------------------
// Structure: a twin is the same article, complete
// -----------------------------------------------------------------------------
const FM = /^---\s*\n([\s\S]*?)\n---\s*\n/;
const bodyOf = (file: string) => read(file).replace(FM, "");
const words = (s: string) =>
  (s.replace(/^import .*?;\n/gm, "").match(/\S+/g) ?? []).length;
const headings = (s: string) => (s.match(/^## /gm) ?? []).length;
const USER_FIELD =
  /^\s*(title|description|excerpt|coverImageAlt|seoTitle|seoDescription|primaryQuestion|answerSnippet|question|answer|alt):\s*"(.*)"\s*$/;
const userFields = (file: string) =>
  (read(file).match(FM)?.[1] ?? "")
    .split("\n")
    .map((l) => USER_FIELD.exec(l))
    .filter((m): m is RegExpExecArray => m !== null)
    .map((m) => `${m[1]}=${m[2]}`);

describe("E28 family truth guard: every twin is complete", () => {
  for (const g of [E28A, GOLDEN, INVESTOR]) {
    const en = g.find((x) => x.loc === "en")!;
    const enBody = bodyOf(en.file);
    const enFields = userFields(en.file);
    const digest = crypto
      .createHash("sha256")
      .update(enBody, "utf8")
      .digest("hex");
    for (const { loc, file } of g.filter((x) => x.loc !== "en")) {
      const name = path.relative(process.cwd(), file);
      it(`${name} has the same number of ## sections as EN`, () => {
        expect(headings(bodyOf(file))).toBe(headings(enBody));
      });
      it(`${name} body is 0.6x to 1.6x of EN in words`, () => {
        const ratio = words(bodyOf(file)) / words(enBody);
        expect(ratio).toBeGreaterThanOrEqual(0.6);
        expect(ratio).toBeLessThanOrEqual(1.6);
      });
      it(`${name} translates every user-visible frontmatter field`, () => {
        const own = userFields(file);
        expect(own.length).toBe(enFields.length);
        const same = own.filter((f, i) => f === enFields[i]);
        expect(same).toEqual([]);
      });
      it(`${name} carries the digest of the EN body (${loc})`, () => {
        expect(read(file)).toContain(`source_sha256: "${digest}"`);
      });
    }
    for (const { loc, file } of g) {
      const name = path.relative(process.cwd(), file);
      it(`${name} readingTime is ceil(words/200)`, () => {
        const m = /^readingTime: (\d+)$/m.exec(read(file));
        expect(Number(m?.[1])).toBe(Math.ceil(words(bodyOf(file)) / 200));
      });
      it(`${name} imports only what it renders (${loc})`, () => {
        const body = bodyOf(file);
        for (const m of body.matchAll(/^import \{ (\w+) \} from/gm)) {
          expect(body.split(`<${m[1]}`).length - 1, m[1]).toBeGreaterThan(0);
        }
      });
    }
  }
  it("the structural checks catch a truncated twin (guilt) and spare a full one (innocence)", () => {
    const full = "## a\nx x x x x x x x x x\n## b\nx x x x x x x x x x\n";
    const cut = "## a\nx x x x x x x x x x\n";
    expect(headings(cut)).not.toBe(headings(full));
    expect(headings(full)).toBe(headings(full));
    expect(words(cut) / words(full)).toBeLessThan(0.6 + 0.0001 + 0.0);
  });
});
