// DEFECT :229 (PR3d, 2026-09-18): the only `model:` token here is nested three levels
// deep inside the schema's own properties — it is NOT this agent( call's own top-level
// options key, so the call is genuinely unpinned and must still be flagged.
phase("Run");
await agent(prompt, {
  label: "solo-guilty",
  schema: {
    properties: {
      model: { type: "string" },
    },
  },
});
