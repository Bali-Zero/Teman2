// Twin of no_phase_uncapped_loop.js: no phase( call, but the loop IS capped — the new
// implicit leading span must not over-fire on a phase(-less file that is genuinely clean.
async function pollUntilReady(check) {
  const MAX_ITERATIONS = 20;
  let i = 0;
  while (!check() && i < MAX_ITERATIONS) {
    i += 1;
  }
}
