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
// Each rule below is ENTITY-scoped (the number or code sits NEAR the thing it
// is wrong about), has a guilt sample it must catch and an innocence sample it
// must leave alone, and is then run over the EN + ID files it applies to.
// =============================================================================
import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const IMM = path.join(process.cwd(), "src/content/articles/immigration");
const read = (p: string) => fs.readFileSync(p, "utf8");
/** Bold markers carry no meaning for these checks. */
const plain = (s: string) => s.replace(/\*/g, "");

const E28A = [
  path.join(IMM, "e28a-investor-kitas-guide.mdx"),
  path.join(IMM, "e28a-investor-kitas-guide.id.mdx"),
];
const GOLDEN = [
  path.join(IMM, "golden-visa-indonesia-complete-guide.mdx"),
  path.join(IMM, "golden-visa-indonesia-complete-guide.id.mdx"),
];
const INVESTOR = [
  path.join(IMM, "investor-kitas-guide.mdx"),
  path.join(IMM, "investor-kitas-guide.id.mdx"),
];
const KITAS_PAGE = path.join(process.cwd(), "src/content/visa/kitas/page.mdx");
const ALL = [...E28A, ...GOLDEN, ...INVESTOR, KITAS_PAGE];

interface Rule {
  id: string;
  files: string[];
  re: RegExp;
  guilt: string;
  innocence: string;
}

const RULES: Rule[] = [
  {
    id: "E28G does not exist",
    files: ALL,
    re: /E28G/,
    guilt: "### E28G: Representative of Parent Company",
    innocence: "E28F is the same route in IKN; E28E has no published details.",
  },
  {
    id: "no seven sub-variants",
    files: ALL,
    re: /\bseven (E28 )?sub-?(variants|types)|\b7 (E28 )?sub-?variants|tujuh sub-?(varian|tipe)|\b7 sub-variasi/i,
    guilt: "divides the category into seven sub-types",
    innocence: "the visa is valid for seven days after the check",
  },
  {
    id: "E28A is not strictly passive",
    files: [...E28A, ...INVESTOR],
    re: /strictly (for )?passive|passive investors|investor pasif|visa investasi pasif|pasif murni|pure passive/i,
    guilt: "No. E28A is strictly for passive investors.",
    innocence: "## Tax on dividend: Passive Investment Income Taxation",
  },
  {
    id: "passport is 6 months, not 18 or 24",
    files: [...E28A, ...INVESTOR],
    re: /passport[^.\n|;]{0,60}\b(18|24)\+? months?|\b18 months?[^.\n|;]{0,40}passport|paspor[^.\n|;]{0,60}\b(18|24)\+? bulan|\b18 bulan[^.\n|;]{0,40}paspor/i,
    guilt: "Passport - Valid for minimum 18 months from application date",
    innocence:
      "Passport - Valid for at least 6 months; 18 months of bank history",
  },
  {
    id: "visa stage is five working days, not 5-7",
    files: [...E28A, ...INVESTOR, KITAS_PAGE],
    re: /5\s?[-–]\s?7 (working days|hari kerja)/i,
    guilt: "Processing Time | 5-7 working days",
    innocence: "typically 7-10 working days with Bali Zero (indicative)",
  },
  {
    id: "no IDR 350M threshold",
    files: [...GOLDEN, ...INVESTOR],
    re: /(IDR|Rp\.?)\s?350\s?(M\b|juta|million|jt)|(IDR|Rp\.?)\s?350[.,]000[.,]000/i,
    guilt: "Golden Visa: IDR 350M+ investment",
    innocence: "E28C needs USD 350,000 in listed shares",
  },
  {
    id: "Golden Visa is an ITAS, not ITAP / permanent residence",
    files: GOLDEN,
    re: /Golden Visa \(ITAP\)|officially called ITAP|ITAP - Izin Tinggal Tetap|Golden Visa[^.\n]{0,50}\b(grants|offers|provides|gives|is)\s+(a\s+)?permanent residence|Golden Visa[^.\n]{0,30}(memberikan|adalah)\s+(izin\s+)?(tinggal tetap|tinggal permanen)/i,
    guilt: "Golden Visa (ITAP) grants permanent residence",
    innocence:
      "The Golden Visa is a limited-stay permit and does not grant permanent residence.",
  },
  {
    id: "Golden Visa has no corporate IDR tier",
    files: GOLDEN,
    re: /Corporate (5|10)-Year|IDR 2,500,000,000|IDR 2\.5 billion minimum/i,
    guilt: "| **Corporate 5-Year** | IDR 2,500,000,000 |",
    innocence: "E28B: USD 2.5M committed within 90 days of entry",
  },
  {
    id: "E28D is not a representative-office permit",
    files: [KITAS_PAGE],
    re: /KPPA|KP3A|E28D[^\n]*(Representative Office|Kantor Perwakilan)|Director KITAS \(Representative|E28D[^\n]*e25b-director-kitas-guide/i,
    guilt:
      "## E28D — Director KITAS (Representative Office) {#e28d-director-kitas}",
    innocence: "E28D — Golden Visa (Branch or Subsidiary of a Foreign Company)",
  },
  {
    id: "E28A kitas-page row: no 20-30 hari",
    files: [KITAS_PAGE],
    re: /E28A[^\n]*20\s?[–-]\s?30 hari/,
    guilt: "| E28A — Investor KITAS | PT PMA shareholders | x | 20–30 hari |",
    innocence:
      "| E28A — Investor KITAS | owners | x | 7–10 hari kerja (indicative) |",
  },
  {
    id: "the E28A test is own shareholding, not paid-in capital",
    files: [...E28A, ...INVESTOR, KITAS_PAGE],
    re: /paid[- ](in|up) capital( of)?\s+(IDR|Rp)\.?\s?10[ .,]?(000|billion|B\b|miliar)|(IDR|Rp)\.?\s?10 (billion|B\b|miliar)[^\n]{0,30}paid[- ](in|up) capital|paid-up capital\s*\|\s*(IDR|Rp)\s?10[.,]000|modal (dasar|disetor)[^\n|]*\|\s*Minimum IDR 10\.000|Paid-up capital\*\* \(modal disetor\)/i,
    guilt: "| Total company paid-up capital | IDR 10,000,000,000 minimum |",
    innocence:
      "The PT PMA itself needs at least IDR 2.5 billion paid-up capital (BKPM Regulation 5/2025).",
  },
  {
    id: "10 billion is not written IDR 10M",
    files: [...E28A, ...INVESTOR],
    re: /(shareholding|saham|investment|investasi)[^\n;]{0,60}(IDR|Rp)\.? ?10M\b|(IDR|Rp)\.? ?10M[^\n;]{0,40}(shareholding|saham|minimum)/i,
    guilt: "Kepemilikan saham minimal IDR 10M, tidak perlu RPTKA",
    innocence:
      "Rp 10 miliar of own shareholding; KITAP renewal IDR 10M per renewal",
  },
  {
    id: "price is all-inclusive, no fee split",
    files: [...E28A, ...INVESTOR],
    re: /government fees? (are |is )?(paid )?separate|biaya pemerintah terpisah|plus government fees|excluding government fees|belum termasuk biaya pemerintah/i,
    guilt: "IDR 17M; government fees are separate",
    innocence: "all-inclusive: government fees and Bali Zero service included",
  },
  {
    id: "E28A extension has no invented length",
    files: [...E28A, ...INVESTOR],
    re: /Extend E28A for Another 2 Years|Perpanjang E28A Selama 2 Tahun|Validity: 1 year \(to reach|Validitas: 1 tahun \(untuk mencapai|E28A[^\n]{0,120}renewable annually|renewable annually/i,
    guilt: "- Validity: 1 year (to reach 3-year mark)",
    innocence:
      "extended online by the sponsor; Imigrasi states no extension length",
  },
  {
    id: "E28A holder may be director or commissioner",
    files: [...E28A, ...INVESTOR],
    re: /E28A holders? cannot work|pemegang E28A tidak dapat bekerja|E28A does not grant work permission|E28A tidak memberikan izin kerja|convert (your )?visa category from E28A to E25B|mengubah kategori visa Anda dari E28A ke E25B|both shareholder AND director, which requires Working KITAS|menjadi pemegang saham SEKALIGUS direktur, yang memerlukan|sign contracts as director, you need a Working KITAS|menandatangani kontrak sebagai direktur, Anda memerlukan|Serve as company director \(Direktur\) in board meetings|Menjadi direktur perusahaan \(Direktur\) dalam rapat dewan|you need E25B Director KITAS instead|Anda memerlukan E25B Director KITAS/i,
    guilt: "However, E28A holders cannot work.",
    innocence:
      "With IDR 10 billion of own shareholding you may act as director or commissioner.",
  },
];

/** Positive facts each file group must state (checked on bold-stripped text). */
const FACTS: Record<string, { files: string[]; needles: (string | RegExp)[] }> =
  {
    "E28A EN": {
      files: [E28A[0]],
      needles: [
        "IDR 10 billion",
        "all-inclusive",
        "sponsor",
        "IDR 2.5 billion paid-up",
        "at least 6 months",
        "director or commissioner",
        "17,000,000",
        "19,000,000",
        "18,000,000",
        "7-10 working days",
        "five working days",
        "USD 350,000",
        "USD 25M",
        "price on consultation",
      ],
    },
    "E28A ID": {
      files: [E28A[1]],
      needles: [
        "Rp 10 miliar",
        "all-inclusive",
        "penjamin",
        "Rp 2,5 miliar",
        "minimal 6 bulan",
        "direktur atau komisaris",
        "17.000.000",
        "19.000.000",
        "18.000.000",
        "7-10 hari kerja",
        "lima hari kerja",
        "USD 350.000",
        "USD 25 juta",
        "harga sesuai konsultasi",
      ],
    },
    "golden EN": {
      files: [GOLDEN[0]],
      needles: [
        "USD 2.5M",
        "USD 5M",
        "USD 350,000",
        "USD 700,000",
        "USD 1,000,000",
        "USD 25M",
        "USD 50M",
        "USD 10M",
        "within 90 days of entry",
        "no sponsor needed",
        "price on consultation",
        "E28E",
        "ITAS",
        "not permanent residence",
      ],
    },
    "golden ID": {
      files: [GOLDEN[1]],
      needles: [
        "USD 2,5 juta",
        "USD 5 juta",
        "USD 350.000",
        "USD 700.000",
        "USD 1.000.000",
        "USD 25 juta",
        "USD 50 juta",
        "USD 10 juta",
        "90 hari setelah masuk",
        "tanpa sponsor",
        "harga sesuai konsultasi",
        "E28E",
        "ITAS",
        "bukan izin tinggal tetap",
      ],
    },
    "investor EN": {
      files: [INVESTOR[0]],
      needles: [
        "IDR 10 billion",
        "IDR 2,500,000,000",
        "at least 6 months",
        "USD 350,000",
        "USD 25M",
        "E28F",
        "director or commissioner",
        "all-inclusive",
      ],
    },
    "investor ID": {
      files: [INVESTOR[1]],
      needles: [
        "Rp 10 miliar",
        "Rp 2.500.000.000",
        "minimal 6 bulan",
        "USD 350.000",
        "USD 25 juta",
        "E28F",
        "direktur atau komisaris",
        "all-inclusive",
      ],
    },
    "/visa/kitas": {
      files: [KITAS_PAGE],
      needles: [
        "Rp 10 billion",
        "7–10 hari kerja",
        "USD 25",
        "USD 50",
        "price on consultation",
        "/visas/golden-visa-indonesia-complete-guide",
        "sponsoring PT PMA",
      ],
    },
  };

describe("E28 family truth guard: every rule catches its guilt and spares its innocence", () => {
  for (const rule of RULES) {
    it(`${rule.id}: guilt sample is caught`, () => {
      expect(rule.re.test(rule.guilt)).toBe(true);
    });
    it(`${rule.id}: innocence sample is left alone`, () => {
      expect(rule.re.test(rule.innocence)).toBe(false);
    });
  }
});

describe("E28 family truth guard: the articles", () => {
  for (const rule of RULES) {
    for (const file of rule.files) {
      const name = path.relative(process.cwd(), file);
      it(`${rule.id} :: ${name}`, () => {
        const lines = read(file).split("\n");
        const hits = lines
          .map((line, i) => ({ line, n: i + 1 }))
          .filter(({ line }) => rule.re.test(line))
          .map(({ n, line }) => `${n}: ${line.trim().slice(0, 120)}`);
        // Whole-text pass for the rules whose phrase may span a line break.
        expect(hits, `${rule.id} still present in ${name}`).toEqual([]);
      });
    }
  }
});

describe("E28 family truth guard: the correct sentences are present", () => {
  for (const [label, { files, needles }] of Object.entries(FACTS)) {
    for (const file of files) {
      const text = plain(read(file));
      for (const needle of needles) {
        it(`${label} states ${needle.toString()}`, () => {
          const found =
            typeof needle === "string"
              ? text.includes(needle)
              : needle.test(text);
          expect(found).toBe(true);
        });
      }
    }
  }
});
