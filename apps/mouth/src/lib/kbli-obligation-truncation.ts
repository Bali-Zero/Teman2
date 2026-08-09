/**
 * Obligations whose SOURCE TEXT stops mid-sentence, and how to say so.
 *
 * The KBLI corpus carries obligation strings that end on a bare conjunction:
 * `"Melaporkan ikan hasil tangkapan dan"` ("Report caught fish and"),
 * `"...sesuai peraturan perundang-undangan di"` ("...in accordance with the
 * regulations in"), and one that is literally `". Produk yang"`. They are
 * artefacts of extraction from the source instrument, not of our storage.
 *
 * Measured 2026-08-05, whole corpus, no sampling:
 *   canonical `KBLI_2025_FINAL_CLEAN.json` — 63,624 obligation strings over
 *   1,457 codes, of which **1,241 are cut off over 229 codes** (`dan` 1,233 /
 *   `yang` 4 / `di` 4);
 *   the knowledge graph the inspect endpoint reads — 10,293 rendered rows, of
 *   which **234 are cut off over 104 codes**, 39 distinct strings. The largest
 *   single string sits on 35 codes.
 *
 * WHY THIS EXISTS AND NOT A TRIM. Deleting the trailing `dan` from
 * `"Report caught fish and [its origin]"` yields `"Report caught fish"` — a
 * sentence that is grammatical, plausible, and **understates a legal duty**.
 * That is changing what a client is told to do, on a guess about text we do
 * not hold. The dangling word at least signals incompleteness to a careful
 * reader; a tidy sentence hides it from everyone. So the text is never
 * altered — it is LABELLED.
 *
 * The defect being cured is therefore not the truncation (that needs
 * re-extraction from PP 28/2021, and the canonical dataset may only be written
 * through `scripts/kbli_filiera/` compilers). It is that all three surfaces
 * rendered a cut-off instruction as though it were a COMPLETE one — the same
 * shape as the `Licenses: None` defect cured the same day, where an empty list
 * became an assertion. An honest gap beats a plausible-but-wrong assertion.
 *
 * DETECTION IS DATA-DERIVED, NOT IMAGINED. A first draft guarded eight further
 * prepositions (`serta`, `untuk`, `dari`, `pada`, `dengan`, `dalam`, `oleh`,
 * `ke`); measured against both stores, every one of them matched **zero**
 * strings, so they are not here. `atau` is kept as the lawful twin of `dan`
 * even though it currently matches zero — declared rather than silently
 * included.
 *
 * THE INNOCENCE CASE IS THE WHOLE DESIGN. Indonesian legal drafting enumerates
 * items `a. ...; b. ...; dan c. ...`, so an obligation ending `"; dan"` is
 * item N of a list and is NOT damaged — 149 such strings exist in canonical.
 * Flagging those would put a false warning on correct data, which is the
 * mirror of the defect. The list-style test therefore runs FIRST and wins.
 */

/** Shown next to an obligation whose source text is incomplete. */
export const TRUNCATION_NOTE = "cut off in the official source";

/**
 * Long-form explanation, for a `title`/tooltip. Says what to do about it,
 * because a warning a reader cannot act on is just noise.
 */
export const TRUNCATION_HINT =
  "The official source text for this requirement is incomplete. Confirm the full wording at oss.go.id or with the Bali Zero team before acting on it.";

/**
 * `"...; dan"` / `"...; atau"` — item N of an enumerated list, not damage.
 * Tested before the dangling check and allowed to win.
 */
const LIST_STYLE = /;\s*(?:dan|atau)\s*$/i;

/**
 * A bare trailing conjunction or preposition. Anchored to end-of-string with a
 * preceding whitespace boundary, so this matches the WORD and never a
 * substring — `"...pendapatan"` does not end in `dan`.
 */
const DANGLING = /\s(?:dan|atau|yang|di)\s*$/i;

/** True when the obligation's source text stops mid-sentence. */
export function isSourceTruncated(text: string | null | undefined): boolean {
  const trimmed = (text ?? "").trim();
  if (!trimmed) return false;
  if (LIST_STYLE.test(trimmed)) return false;
  return DANGLING.test(trimmed);
}

export interface ObligationDisplay {
  /** The source text, NEVER altered — no trim of the dangling word. */
  text: string;
  /** Whether the reader must be told the sentence is incomplete. */
  truncated: boolean;
}

/**
 * What a surface should render for one obligation. Returns the text unchanged
 * plus the flag; the caller owns the visual treatment, so the three surfaces
 * can differ in styling without ever differing on the JUDGEMENT.
 */
export function describeObligation(
  text: string | null | undefined,
): ObligationDisplay {
  const value = (text ?? "").trim();
  return { text: value, truncated: isSourceTruncated(value) };
}
