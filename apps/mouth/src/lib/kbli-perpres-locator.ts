import fs from "fs";
import path from "path";

/**
 * The article of the Daftar Positif Investasi that names a KBLI code.
 *
 * Until 2026-08-02 every one of the 1,559 records carried
 * `pma_source: "Perpres 10/2021, 49/2021"` — the instrument, with no article.
 * A blanket attribution is not a citation, and the navigator's north star is
 * that a rendered PMA fact is either government-sourced with a locator or an
 * honest declared gap.
 *
 * This module does NOT derive the citation. The precedence that produces it
 * (body → restricting annex → priority listing → residual) is a legal reading
 * with its own guilt/innocence corpus in
 * `scripts/kbli_filiera/perpres_body_default_relation.py`, and re-implementing
 * it here would make two writers of one field, which is how the two of them
 * start disagreeing. That script emits `data/perpres-locators.json`; its
 * `--check-artifact` mode recomputes the join from the vaulted instrument and
 * fails if this file has drifted, so the artifact cannot go stale in silence.
 *
 * Missing or unreadable file ⇒ every code returns `null` and the page simply
 * shows no citation. A citation is additive: its absence costs a reader
 * context, whereas a fabricated or stale one would tell them the law says
 * something it does not.
 */
export interface PerpresLocator {
  /** Which instrument names the code — the bucket the compiler assigned. */
  bucket: string;
  /** The article, verbatim from the compiler. */
  basis: string;
  /** The one-sentence citation, written to be read by a client. */
  cite: string;
  /** OSS scale data, carried but NOT part of the citation (see below). */
  besar: "observed" | "absent" | "unobserved";
}

const LOCATORS_PATH = path.join(process.cwd(), "data", "perpres-locators.json");

let _cache: Record<string, PerpresLocator> | null = null;

function load(): Record<string, PerpresLocator> {
  if (_cache) return _cache;
  try {
    const parsed = JSON.parse(fs.readFileSync(LOCATORS_PATH, "utf-8"));
    _cache = parsed.locators ?? {};
  } catch {
    process.stderr.write(
      `[kbli] no Perpres locators at ${LOCATORS_PATH} — pages render without a citation\n`,
    );
    _cache = {};
  }
  return _cache!;
}

export function getPerpresLocator(code: string): PerpresLocator | null {
  return load()[code] ?? null;
}

/**
 * The citation as the page shows it, or `null`.
 *
 * Deliberately ignores `besar`. `Pasal 7(1)` conditions the INVESTOR — a PT PMA
 * must reach Usaha Besar — and the absence of a Besar row in OSS licensing data
 * is not a determination that the activity cannot be run at that scale. Folding
 * it into a citation would print a bar the instrument does not state. It stays
 * a verification queue for the team, off the page.
 */
export function perpresCitation(code: string): string | null {
  return getPerpresLocator(code)?.cite ?? null;
}
