// Twin of nested_model_key.js: the SAME nested schema.properties.model shape, but this
// call also pins a real TOP-LEVEL model: — must stay clean (innocence for DEFECT :229).
phase("Run");
await agent(prompt, {
  label: "solo-innocent",
  model: "sonnet",
  schema: {
    properties: {
      model: { type: "string" },
    },
  },
});
