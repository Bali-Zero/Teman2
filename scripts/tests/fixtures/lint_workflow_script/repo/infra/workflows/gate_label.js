phase("Run");
const verdict = await agent(`judge the thing`, {
  label: `gate:${task.key}`,
  phase: "Run",
  model: "opus",
  schema: VERDICT,
});
