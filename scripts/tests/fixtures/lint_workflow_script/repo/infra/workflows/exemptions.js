// Regression guard for two false positives found against the real repo (2026-09-18):
// kbli-batch-a-lot.js's callSeat(promptText, opts) provenance wrapper, and
// second-army.js's `for (const seat of builderRoster)` roster scan.

async function callSeat(promptText, opts) {
  const answer = await agent(promptText, opts);
  return { answer, label: opts.label };
}

async function dispatch(code) {
  return callSeat(`adjudicate ${code}`, {
    label: `D1:${code}`,
    phase: "Adjudicate",
    model: "sonnet",
    schema: D1_SCHEMA,
  });
}

phase("Probe");
function chooseBuilder(roster, isDead) {
  for (const seat of roster) {
    if (isDead(seat)) continue;
    return seat;
  }
  return null;
}
