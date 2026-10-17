/**
 * Whole-number syntax of the interview's number questions (rupiah, dollars,
 * days, months: every one is `step: 1`). `<input type="number">` hands the
 * form its raw string with no thousand separators, so exactly ASCII digits are
 * accepted. Anything else (a decimal, an exponent, a sign, blanks) is refused
 * BEFORE conversion, because `Number("9999999999.9999999")` rounds to
 * 10000000000 and would turn an invalid figure into a valid one.
 */
export function parseWholeNumberInput(
  raw: string,
  min: number,
  max: number,
): number | null {
  if (!/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < min || value > max) return null;
  return value;
}
