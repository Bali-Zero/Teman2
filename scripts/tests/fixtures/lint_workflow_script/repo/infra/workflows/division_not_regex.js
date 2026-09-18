// INNOCENCE (item 1, PR3e, 2026-09-18): a chain of divisions must not misfire as a
// regex literal -- each `/` below follows an identifier, never one of
// _REGEX_OPENER_CHARS, so _regex_may_open must return False both times.
phase("Run");
const ROUNDS_CAP = 3;
let round = 0;
while (round < ROUNDS_CAP) {
  round += 1;
  const ratio = a / b / c;
}
