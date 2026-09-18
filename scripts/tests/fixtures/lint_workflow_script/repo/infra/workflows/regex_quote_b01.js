// GUILT b01 (item 1, PR3e, 2026-09-18, gate-10 obs 1, HIGH): a regex literal
// containing a quote used to be misread as a string opener, blanking comment/string
// neutralization for the REST OF THE FILE -- pre-fix, neither violation below was
// ever reported (the whole tail after this line went invisible to the scan). Both
// must be reported once the fix lands.
phase("Run");
const cleaned = raw.replace(/'/g, "");

const answer = await agent(`do the thing`, {
  label: `worker:${task.key}`,
  phase: "Run",
  schema: ANSWER,
});

while (Object.keys(results).length < A.tasks.length) {
  const ready = A.tasks.filter((t) => !results[t.key]);
  results[ready[0].key] = true;
}
