phase("Run");
while (Object.keys(results).length < A.tasks.length) {
  const ready = A.tasks.filter((t) => !results[t.key]);
  const batch = ready.slice(0, A.maxParallel);
  const outcomes = await parallel(batch.map((task) => () => run(task)));
  batch.forEach((task, i) => {
    results[task.key] = outcomes[i];
  });
}
