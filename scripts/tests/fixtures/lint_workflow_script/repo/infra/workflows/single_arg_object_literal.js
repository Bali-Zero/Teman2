// OBSERVATION 4 (PR3a', 2026-09-18): a single-argument agent({...}) call is a real,
// checkable object literal — not indirection — and must be scanned the same as the
// last argument of a multi-argument call. This fixture pins both sides: guilty (no
// model:) and innocent (model: present) single-argument calls.

phase("Probe");

async function guilty() {
  return agent({
    label: "solo-guilty",
    schema: SCHEMA,
  });
}

async function innocent() {
  return agent({
    label: "solo-innocent",
    model: "sonnet",
    schema: SCHEMA,
  });
}
