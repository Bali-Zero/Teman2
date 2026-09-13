// The chunk-exception contract, as a pure decision.
//
// WHY THIS IS A MODULE AND NOT A BLOCK INSIDE THE GUARD.
//
// The rule it encodes has been broken twice by review, and each repair made it
// harder to test from outside. It began as `expect(guard).toContain("C4b")` in a
// unit test — which a seat proved vacuous, because this file's own prose satisfied
// it. It then moved INTO the guard, where the objects are real, which fixed the
// judgement but left the suite asserting only that a particular LINE still appeared
// in the guard's source. A rewrite that kept that line and broke the logic would
// have stayed green, and every proof that the rule worked was a manual probe
// recorded in a pack — evidence for a reader, not a regression test for the next
// commit.
//
// So the decision lives here: structures in, violations out. No process.exit, no
// console, no filesystem. The guard formats and exits; the test asserts behaviour.
// Both import THIS, so they cannot drift from each other.

/**
 * A closer must BE a reference, not merely contain one.
 *
 * Unanchored, this was `/(#\d+|\bC\d+[a-z]?\b)/`, and the gate's probe found what
 * that admits: "TODO maybe C4b someday" passed, as did "fix it in C9 probably" and
 * "see C4b for history". Only "later", "TBD" and "" were rejected — so an exception
 * could be declared with a shrug, provided the shrug named a lane. That is the same
 * substring-instead-of-entity mistake this contract exists to correct, one level
 * down: the pairing was fixed, the VALUE was not.
 *
 * Anchored, and case-sensitive on purpose: lane ids are written `C4b` in this repo,
 * and accepting `c4b` would invite two spellings of the same promise. The value is
 * trimmed first, so trailing whitespace is a typo rather than a rejection.
 */
export const CLOSER_SHAPE = /^(#\d+|C\d+[a-z]?)$/;

/**
 * Returns a list of human-readable violations. Empty means the declaration is sound.
 *
 * @param {{ prefixes: unknown, closers: unknown }} declaration
 * @returns {string[]}
 */
export function chunkExceptionViolations({ prefixes, closers }) {
  const out = [];
  if (!Array.isArray(prefixes)) {
    return ["ALLOWED_CHUNK_PREFIXES is not an array"];
  }
  if (closers === null || typeof closers !== "object") {
    return ["ALLOWED_CHUNK_PREFIX_CLOSERS is not an object"];
  }

  for (const prefix of prefixes) {
    // A blank prefix makes `startsWith` true for EVERY chunk, so the scan would be
    // skipped entirely while both structures still looked declared and paired.
    if (typeof prefix !== "string" || prefix.trim() === "") {
      out.push(
        `an allowlist entry is empty or blank (${JSON.stringify(prefix)}). ` +
          `"".startsWith() matches every chunk, so this would disable the scan.`,
      );
      continue;
    }
    // `Object.hasOwn`, not truthiness: `closers["constructor"]` inherits a truthy
    // value from Object.prototype and would otherwise wave an exception through.
    if (!Object.hasOwn(closers, prefix)) {
      out.push(
        `"${prefix}" is allowed but has no OWN entry in ALLOWED_CHUNK_PREFIX_CLOSERS. ` +
          `An exception that does not name the PR removing it is not time-boxed.`,
      );
      continue;
    }
    const closer = closers[prefix];
    if (typeof closer !== "string" || !CLOSER_SHAPE.test(closer.trim())) {
      out.push(
        `"${prefix}" names ${JSON.stringify(closer)} as its closer, which is not a PR ` +
          `reference. "TODO", "later" and "maybe C4b someday" are not closing PRs. ` +
          `Use #1234 or a lane id such as C4d.`,
      );
    }
  }

  // Both directions. A closer left behind after its prefix is removed is a stale
  // promise that the next exception could quietly reuse.
  for (const key of Object.keys(closers)) {
    if (!prefixes.includes(key)) {
      out.push(
        `ALLOWED_CHUNK_PREFIX_CLOSERS has "${key}" with no matching entry in ` +
          `ALLOWED_CHUNK_PREFIXES — a stale closing-PR claim.`,
      );
    }
  }
  return out;
}
