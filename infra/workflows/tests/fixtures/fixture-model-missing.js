// fixture-model-missing.js — identical to fixture-model-pinned.js EXCEPT that its one lane
// omits `model:`. The runner must REFUSE to execute it: every lane pins a model, and the
// runner is the enforcement point. If the runner ever runs this fixture to completion, the
// model-pin guard is gone, whatever the source still looks like.
export const meta = {
  name: "fixture-model-missing",
  description: "test fixture: one agent() lane that does NOT pin model",
  whenToUse: "never in production — infra/workflows/tests/ only",
  phases: [{ title: "One", detail: "a single unpinned lane" }],
};

phase("One");
const answer = await agent("say anything", { label: "probe:fixture" });
log("fixture lane returned — the runner should never have got here");
return { ok: true, answer };
