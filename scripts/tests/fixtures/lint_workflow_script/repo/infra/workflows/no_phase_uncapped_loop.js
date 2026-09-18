// DEFECT :245 (PR3d, 2026-09-18): a file with no phase( call at all used to build an
// EMPTY spans list, so this loop was never scanned no matter how uncapped it is.
async function pollUntilReady(check) {
  while (!check()) {
    // no phase(...) wrapper anywhere in this file
  }
}
