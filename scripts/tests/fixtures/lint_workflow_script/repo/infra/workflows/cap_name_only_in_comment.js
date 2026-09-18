phase("Run");
// maxRounds is documented here for the reader, but no such constant is ever declared
// below — the loop itself has no real cap (DEFECT :253, PR3d, 2026-09-18).
while (Object.keys(results).length < A.tasks.length) {
  results[A.tasks[0].key] = true;
}
