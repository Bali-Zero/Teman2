import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * No sibling article may claim 55201/55203/79903 (homestay, villa, tour
 * guide) or 38110 (non-hazardous waste collection) are open / 100%
 * foreign-owned, or that a PT PMA can reach a reserved code by registering
 * outside Bali.
 *
 * THE CLAIM THIS GATE KILLS. `pondok-wisata-vs-villa`, `the-villa-dream-has-a
 * -new-wall` and `open-nationally-blocked-in-bali` (EN/IT/ID) read 55201 and
 * 55203 as `TERBUKA` / "100% open to foreign ownership" on the national list,
 * framing the block as a Bali-only risk-class moratorium. It isn't: Perpres
 * 10/2021, as amended by 49/2021, Lampiran II entry 48 (p.15, "Pondok Wisata"
 * / "Vila") allocates the whole activity to Koperasi/UMKM — a new PT PMA
 * cannot enter it in Bali OR anywhere else in Indonesia. One article
 * (`the-villa-dream-has-a-new-wall`) went further and offered a live
 * workaround — register the 55203 PMA in Jakarta or Lombok "where the
 * moratorium doesn't apply" — which the source directly contradicts, since an
 * Annex II reservation is a national instrument, not a province-scoped one.
 * `kbli-2025-green-economy-waste` separately marked 38110 "100% PMA" in its
 * code table; no reservation was located for 38110 in the same annex, so the
 * correct claim is "confirm in OSS", not a number either way (not 0%, not
 * 100%). Dossier: BATTAGLIA-20260911/4-KBLI-APP/DOSSIER-no-besar-normativo-
 * 2026-09-15.md §2, §4 last paragraph (SAETTA-20260915 / W-H, lane PR-7).
 *
 * WHAT IT MATCHES, AND WHAT IT DELIBERATELY DOES NOT.
 *
 * - The three `business_regulations` siblings are each dedicated, by title,
 *   to 55201/55203/79903 — so any line carrying a percent-token ("100%",
 *   "one hundred percent", "seratus persen", "cento per cento") next to an
 *   open/foreign/ownership word, or naming Jakarta and Lombok together, is in
 *   scope UNLESS that same line names one of the genuinely open sibling
 *   codes these articles also cover (55204 apart-hotel, 55400 intermediation,
 *   56301 bar) — those really are `TERBUKA` and must stay sayable.
 * - `kbli-2025-green-economy-waste` covers ~15 unrelated codes that really
 *   are 100% PMA (38121, 38212, 39001…), so there the same percent/open
 *   pattern is only in scope on a line that also names 38110 — a bare "100%"
 *   elsewhere in that table (a different code, a match rate, a recycling
 *   yield) never fires.
 *
 * The sweep covers every locale the sibling articles are served in — EN, IT,
 * ID — because a claim retracted in one language only moves which
 * translation still says the old thing. (`.fr.mdx`/`.ru.mdx` of the waste
 * article are abridged translations that end before the code table and
 * never carry the 38110 claim — verified on disk, not swept here.)
 */

const ARTICLES_DIR = path.join(process.cwd(), "src/content/articles");

const RESERVED_FILES = [
  "business_regulations/pondok-wisata-vs-villa.mdx",
  "business_regulations/pondok-wisata-vs-villa.it.mdx",
  "business_regulations/pondok-wisata-vs-villa.id.mdx",
  "business_regulations/the-villa-dream-has-a-new-wall.mdx",
  "business_regulations/the-villa-dream-has-a-new-wall.it.mdx",
  "business_regulations/the-villa-dream-has-a-new-wall.id.mdx",
  "business_regulations/open-nationally-blocked-in-bali.mdx",
  "business_regulations/open-nationally-blocked-in-bali.it.mdx",
  "business_regulations/open-nationally-blocked-in-bali.id.mdx",
];

const WASTE_FILES = [
  "business/kbli-2025-green-economy-waste.mdx",
  "business/kbli-2025-green-economy-waste.it.mdx",
  "business/kbli-2025-green-economy-waste.id.mdx",
];

// Codes these same articles legitimately describe as open — a line naming
// one of these is never an offender, even if it also carries a percent word.
const OPEN_SIBLING_CODES = /\b(55204|55400|56301)\b/;

const RESERVED_TERM =
  /\b(55201|55203|79903|villa|homestay|pondok\s*wisata|pramuwisata)\b/i;
// A generic "the printout says open" hook (no code named at all, anywhere
// nearby) is a different, out-of-scope claim — see open-nationally-
// blocked-in-bali's intro/excerpt, which never names 55201/55203/79903.
const CONTEXT_WINDOW_LINES = 8;

const WASTE_TERM = /\b38110\b/;

const PCT = String.raw`(?:100\s?%|one\s+hundred\s+percent|seratus\s+persen|cento\s+per\s+cento)`;
const OPENWORD = String.raw`(?:open|aperto|aperti|terbuka|foreign|straniera|asing|kepemilikan|propriet[aà]|pemilikan|PMA)`;

const BANNED_OWNERSHIP = new RegExp(
  `${PCT}[^.\\n]{0,40}${OPENWORD}|${OPENWORD}[^.\\n]{0,40}${PCT}`,
  "i",
);

const BANNED_LOOPHOLE = /jakarta[^.\n]{0,80}lombok|lombok[^.\n]{0,80}jakarta/i;

const isOffendingLine = (line: string) =>
  !OPEN_SIBLING_CODES.test(line) &&
  (BANNED_OWNERSHIP.test(line) || BANNED_LOOPHOLE.test(line));

function scanReserved(files: string[]): string[] {
  const offenders: string[] = [];
  for (const rel of files) {
    const lines = fs
      .readFileSync(path.join(ARTICLES_DIR, rel), "utf-8")
      .split("\n");
    lines.forEach((line, i) => {
      if (!isOffendingLine(line)) return;
      const from = Math.max(0, i - CONTEXT_WINDOW_LINES);
      const to = Math.min(lines.length, i + CONTEXT_WINDOW_LINES + 1);
      const nearby = lines.slice(from, to).join("\n");
      if (RESERVED_TERM.test(nearby)) offenders.push(`${rel}:${i + 1}`);
    });
  }
  return offenders;
}

function scanWaste(files: string[]): string[] {
  const offenders: string[] = [];
  for (const rel of files) {
    const lines = fs
      .readFileSync(path.join(ARTICLES_DIR, rel), "utf-8")
      .split("\n");
    lines.forEach((line, i) => {
      if (!WASTE_TERM.test(line)) return;
      if (BANNED_OWNERSHIP.test(line) || BANNED_LOOPHOLE.test(line)) {
        offenders.push(`${rel}:${i + 1}`);
      }
    });
  }
  return offenders;
}

describe("KBLI sibling articles do not reassert an open/100% claim on a reserved code", () => {
  it("reads a corpus that is actually there", () => {
    for (const rel of [...RESERVED_FILES, ...WASTE_FILES]) {
      expect(
        fs.existsSync(path.join(ARTICLES_DIR, rel)),
        `missing: ${rel}`,
      ).toBe(true);
    }
  });

  it("no sentence in the villa/homestay/tour-guide siblings pairs a reserved code with 100% / open-to-foreign, or offers a Jakarta/Lombok route around the reservation", () => {
    const offenders = scanReserved(RESERVED_FILES);
    expect(
      offenders,
      `These lines still frame a Lampiran II-reserved code (55201/55203/79903) as ` +
        `open or 100% foreign-owned, or offer a route around the reservation outside ` +
        `Bali. The sourced verdict is: allocated to Koperasi/UMKM by Perpres 10/2021 ` +
        `as amended by 49/2021 Lampiran II — a new PT PMA cannot enter, in Bali or ` +
        `anywhere else in Indonesia.\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  it("no sentence pairs 38110 with 100% / open-to-foreign", () => {
    const offenders = scanWaste(WASTE_FILES);
    expect(
      offenders,
      `These lines still claim 38110 is 100% PMA. No reservation or cap was located ` +
        `for 38110 in Perpres 10/2021 as amended by 49/2021 — the correct claim is ` +
        `"confirm in OSS", not a number either way (not 0%, not 100%).\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  // GUILT — the wordings that were actually live in these articles until this
  // commit (SAETTA-20260915 / W-H, lane PR-7), one per file/locale.
  it.each([
    "Both of these codes read `TERBUKA` — 100% open — on the national investment list.",
    "Entrambi questi codici appaiono come `TERBUKA` — 100% aperti — nella lista nazionale degli investimenti.",
    "Kedua kode ini tercantum sebagai `TERBUKA` — 100% terbuka — dalam daftar investasi nasional.",
    "**KBLI 55203 — Aktivitas Vila** — is listed as `TERBUKA`, one hundred percent open to foreign ownership.",
    "**KBLI 55203 — Aktivitas Vila** — è elencato come `TERBUKA`, aperto al 100% alla proprietà straniera.",
    "**KBLI 55203 — Aktivitas Vila** — tercantum sebagai `TERBUKA`, seratus persen terbuka untuk kepemilikan asing.",
    "There is a third route that lives outside Bali entirely: register the 55203 PMA in a province where the moratorium doesn't apply (Jakarta, Lombok, elsewhere)",
    "C'è un terzo percorso che vive completamente fuori da Bali: registrare la PMA 55203 in una provincia dove il moratorium non si applica (Jakarta, Lombok, altrove)",
    "Ada jalur ketiga yang berada di luar Bali sama sekali: daftarkan PMA 55203 di provinsi di mana moratorium tidak berlaku (Jakarta, Lombok, tempat lain)",
    "**KBLI 55203 (Aktivitas Vila)** is `TERBUKA` — 100% open — on the national list.",
    "**KBLI 55203 (Aktivitas Vila)** è `TERBUKA` — al 100% aperto — nell'elenco nazionale.",
    "**KBLI 55203 (Aktivitas Vila)** adalah `TERBUKA` — 100% terbuka — dalam daftar nasional.",
  ])("catches the historical wording (reserved-codes rule): %s", (sentence) => {
    expect(isOffendingLine(sentence)).toBe(true);
  });

  it("catches the historical wording (38110 rule): 100% PMA table row", () => {
    const sentence =
      "| **38110** | Pengumpulan Limbah atau Sampah Tidak Berbahaya | Non-Hazardous Waste Collection | **Menengah Rendah** (Medium-Low) | **100% PMA** |";
    expect(WASTE_TERM.test(sentence)).toBe(true);
    expect(
      BANNED_OWNERSHIP.test(sentence) || BANNED_LOOPHOLE.test(sentence),
    ).toBe(true);
  });

  // INNOCENCE — the rewritten sentences (must stay sayable), a "100%
  // match"-style non-ownership use, and the genuinely open sibling codes.
  it.each([
    "Both of these codes are allocated to cooperatives and MSMEs by the *same* line of the same annex — a new PT PMA cannot enter either line of business, in Bali or anywhere else in Indonesia.",
    "The villa code looks like the textbook case, and isn't. **KBLI 55203 (Aktivitas Vila)** is reserved nationally by Lampiran II, not a Bali-only block.",
    "There is no route around this one: because the closure is a national annex reservation, not a provincial moratorium, registering the 55203 PMA in a different province does not open a path.",
    "The KBLI Navigator's crosswalk found a 100% match between the 2020 and 2025 villa codes, confirming the same activity.",
    "**55204 — Aktivitas Apartemen Hotel (Apart-Hotel).** National: open. Bali: **REGISTRABLE.**",
  ])("does not fire on legitimate prose: %s", (sentence) => {
    expect(isOffendingLine(sentence)).toBe(false);
  });

  it("does not fire on legitimate prose (38110 rule)", () => {
    const sentence =
      "| **38110** | Pengumpulan Limbah atau Sampah Tidak Berbahaya | Non-Hazardous Waste Collection | **Menengah Rendah** (Medium-Low) | **Unverified — confirm in OSS** |";
    expect(WASTE_TERM.test(sentence)).toBe(true);
    expect(
      BANNED_OWNERSHIP.test(sentence) || BANNED_LOOPHOLE.test(sentence),
    ).toBe(false);
  });
});
