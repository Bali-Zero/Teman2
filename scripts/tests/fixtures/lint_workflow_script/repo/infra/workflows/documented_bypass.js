// CONDITION 3 (PR3a', dw-gate-6, 2026-09-18): the wrapper exemption is a REAL, NAMED
// hole, not a hidden one. callSeat's own inner `agent(promptText, opts)` is a bare
// identifier — lexically unreadable, same as the legitimate case in exemptions.js — so
// this static lint stays silent here even though `opts` below carries NO `model:` at
// all. The compensating control is a RUNTIME guard, not this file:
// infra/workflows/run-second-army.mjs:121's assertModelPinned throws at execution time
// for exactly this shape. See test_documented_bypass_fixture_is_lexically_invisible.

async function callSeat(promptText, opts) {
  const answer = await agent(promptText, opts);
  return { answer, label: opts.label };
}

async function dispatchWithoutModel(code) {
  return callSeat(`adjudicate ${code}`, {
    label: `D1:${code}`,
    phase: "Adjudicate",
    schema: D1_SCHEMA,
  });
}
