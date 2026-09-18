// OBSERVATION 5 (PR3a', 2026-09-18): LOOP_RE must recognise `for await (` as a loop.
// A declared `for await (const x of y)` stays exempt — bounded by its own async
// iterable, same reasoning as a plain for...of. A `for await` onto an ALREADY-DECLARED
// variable has no const/let/var for _is_bounded_for_of_in to match, so — like any other
// for(...) shape — it needs a numeric cap or *Cap constant in its phase(...) span.

phase("Probe");
async function bounded(seats) {
  for await (const seat of seats) {
    if (!seat.ok) continue;
  }
}

phase("Sweep");
async function uncapped(streamResult, resultStream) {
  for await (streamResult of resultStream) {
    if (streamResult.done) break;
  }
}
