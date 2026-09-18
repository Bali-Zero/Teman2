// Twin of parenthesized_object_literal.js: same wrapping-paren shape, but this call
// pins a real model: -- must stay clean.
phase("Run");
// prettier-ignore
await agent(prompt, ({ label: "solo-innocent", model: "sonnet", schema: SCHEMA }));
