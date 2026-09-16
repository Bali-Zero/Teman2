// fixture-model-pinned.js — a minimal, well-formed workflow script: its one lane PINS a model.
// The runner must execute it and return the lane's value. Paired with
// fixture-model-missing.js, which is identical except for the missing pin.
export const meta = {
  name: "fixture-model-pinned",
  description: "test fixture: one agent() lane that pins model",
  whenToUse: "never in production — infra/workflows/tests/ only",
  phases: [{ title: "One", detail: "a single pinned lane" }],
};

phase("One");
const answer = await agent("say anything", {
  model: "haiku",
  label: "probe:fixture",
});
log("fixture lane returned");
return { ok: true, answer };
