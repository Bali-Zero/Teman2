// DEFECT :184 (PR3d, 2026-09-18): a parenthesized object literal used to be skipped as
// unreadable indirection -- it is read exactly like the unwrapped form and is genuinely
// unpinned here, so it must still be flagged.
phase("Run");
// prettier-ignore
await agent(prompt, ({ label: "solo-guilty", schema: SCHEMA }));
