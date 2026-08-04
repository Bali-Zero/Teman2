import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * No published article may explain a Bali block by the absence of an OSS
 * "Usaha Besar" scale row.
 *
 * THE CLAIM THIS GATE KILLS. For months the article corpus argued: *the OSS
 * system offers no large-scale registration row for this code, so the activity
 * is reserved for UMKM, so a PT PMA — large-scale by law — cannot register it.*
 * Permeninves/BKPM 5/2025 Pasal 26(1) inverts it: being Usaha Besar is a
 * CONSEQUENCE of holding PMA status, not a precondition for registering, so the
 * absence of that row says nothing about foreign ownership. The inference was
 * withdrawn from the canonical layer and the 1,559 code pages on 2026-08-03.
 *
 * WHY IT NEEDS ITS OWN GATE HERE. The Python guard written that same day
 * (`scripts/kbli_filiera/tests/test_withdrawn_umkm_inference_absent.py`) states
 * its own scope: it reads the canonical record and the macOS app overlay, and
 * it is "a floor, not a ceiling". The article corpus was outside it — and that
 * is exactly where the claim was still live, in seven article families across
 * three locales, telling readers that a PT PMA cannot register a villa, a
 * beauty salon, a tourism consultancy or a design studio. A surface with no
 * guardian is where a withdrawn claim goes to keep living.
 *
 * WHAT IT MATCHES, AND WHAT IT DELIBERATELY DOES NOT. The trigger is the
 * ARGUMENT — a missing large-scale ROW or SLOT — never the conclusion and never
 * the words "reserved for UMKM" on their own. Seven KBLI codes really are
 * allocated to Koperasi/UMKM by Perpres 10/2021 (as amended by 49/2021) Annex
 * II, and articles must stay free to say so; a guard that fired on "UMKM" would
 * be satisfied by deleting the true reservations along with the false ones.
 * That distinction is the whole lesson: the first version of the Python guard
 * matched the shared CONCLUSION ("cannot register it anywhere in Indonesia")
 * and convicted eight codes for telling the truth.
 *
 * The sweep covers every locale, because the corpus is served in English,
 * Italian and Indonesian and a withdrawal enforced in one language only moves
 * which translation still says the old thing.
 */

const CONTENT_ROOT = path.join(process.cwd(), "src/content");

const WITHDRAWN_ROW_ABSENCE = new RegExp(
  [
    // EN — "no large-scale registration row", "offers no **Usaha Besar** row",
    //      "no Usaha Besar slot", "no large-scale OSS row"
    String.raw`no\s+(?:\*\*)?(?:Usaha Besar|large-scale)(?:\*\*)?[^.\n]{0,40}?\b(?:row|slot)\b`,
    // IT — "non offre alcuna riga di registrazione Usaha Besar",
    //      "nessuna riga/fila su larga scala", "non ha una voce per registrazioni su larga scala"
    String.raw`(?:non\s+offre\s+alcun[ao]|non\s+ha\s+un[ao]|nessun[ao]?)\s+(?:riga|fila|voce|slot)[^.\n]{0,60}?(?:larga scala|Usaha Besar)`,
    // ID — "tidak memiliki/menawarkan/menyediakan baris ... skala besar",
    //      "tidak ada slot Usaha Besar", "tidak ada skala besar"
    String.raw`tidak\s+(?:ada|memiliki|menawarkan|menyediakan)\s+(?:baris|slot)[^.\n]{0,60}?(?:skala besar|Usaha Besar)`,
    String.raw`tidak\s+ada\s+(?:slot\s+Usaha Besar|skala besar)`,
  ].join("|"),
  "i",
);

function walkMdx(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkMdx(full));
    else if (entry.name.endsWith(".mdx")) out.push(full);
  }
  return out;
}

describe("the withdrawn no-Usaha-Besar inference is absent from the article corpus", () => {
  it("reads a corpus that is actually there", () => {
    // A sweep that silently reads nothing reports a clean world. Fail loudly
    // instead, and pin the population so a truncated checkout cannot pass by
    // being small.
    expect(fs.existsSync(CONTENT_ROOT)).toBe(true);
    expect(walkMdx(CONTENT_ROOT).length).toBeGreaterThan(200);
  });

  it("no article in any locale explains a block by a missing large-scale row", () => {
    const offenders: string[] = [];
    for (const file of walkMdx(CONTENT_ROOT)) {
      const lines = fs.readFileSync(file, "utf-8").split("\n");
      lines.forEach((line, i) => {
        if (WITHDRAWN_ROW_ABSENCE.test(line)) {
          offenders.push(`${path.relative(CONTENT_ROOT, file)}:${i + 1}`);
        }
      });
    }
    expect(
      offenders,
      `These published passages re-assert the no-Usaha-Besar inference withdrawn on ` +
        `2026-08-03. A block must be attributed to what actually closes the code: the ` +
        `Perpres 49/2021 Annex II allocation to Koperasi/UMKM, the Bali moratorium's ` +
        `risk tier, or a national TERTUTUP.\n${offenders.join("\n")}`,
    ).toEqual([]);
  });

  // GUILT — the wordings that were actually live on the site until this commit,
  // in the three locales the corpus is served in. Not sentences written to match
  // the pattern that was just written.
  it.each([
    "the OSS system has no large-scale registration row, so the activity is reserved for UMKM",
    "the OSS system offers no **Usaha Besar** registration row for 96220",
    'blocked by "no large-scale row" (`CHIUSO_PMA_NO_BESAR`): reserved for UMKM, no Usaha Besar slot',
    "the OSS system offers no large-scale row, so it's reserved for local UMKM",
    "il sistema OSS non offre alcuna riga di registrazione **Usaha Besar** per il 96220",
    "il sistema OSS non ha una voce per registrazioni su larga scala",
    'bloccati da "nessuna fila su larga scala"',
    "sistem OSS tidak memiliki baris pendaftaran skala besar",
    'sistem OSS tidak menawarkan baris pendaftaran "Usaha Besar"',
    'diblokir oleh "tidak ada skala besar"',
  ])("catches the historical wording: %s", (sentence) => {
    expect(WITHDRAWN_ROW_ABSENCE.test(sentence)).toBe(true);
  });

  // INNOCENCE — every one of these is TRUE and must stay sayable. Seven codes
  // really are reserved; the micro/small scale rule really exists; and an
  // article about the 0.5% UMKM flat tax has nothing to do with any of it.
  it.each([
    "Annex II of Perpres 10/2021, as amended by 49/2021, allocates the *Vila* line of business to cooperatives and MSMEs",
    "7 — reserved for cooperatives and MSMEs (`CHIUSO_PMA_NO_BESAR`): allocated in Annex II",
    "micro and small scale operations remain reserved for Indonesian UMKM",
    "is the activity low/medium-low risk, or reserved-for-UMKM?",
    "Small retail (reserved for MSME)",
    "influencers and content creators now fall outside the 0.5% UMKM flat-tax regime",
    "blocked in Bali by the moratorium, on its *Rendah* risk tier, not by any ownership reservation",
    "la riserva dell'Allegato II è scritta contro attività nominate, non contro il lavoro cosmetico come categoria",
    "dicadangkan bagi koperasi dan UMKM dalam Lampiran II Perpres 10/2021",
  ])("does not fire on legitimate prose: %s", (sentence) => {
    expect(WITHDRAWN_ROW_ABSENCE.test(sentence)).toBe(false);
  });
});
