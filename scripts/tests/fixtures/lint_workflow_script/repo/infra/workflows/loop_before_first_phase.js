// DEFECT :245 (PR3d, 2026-09-18): this loop sits BEFORE the file's first phase( call —
// the old span-building started at phase_calls[0], so this loop was never scanned.
while (!ready) {
  poll();
}

phase("Run");
const ROUNDS_CAP = 3;
let round = 0;
while (round < ROUNDS_CAP) {
  round += 1;
}
