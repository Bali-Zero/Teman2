phase("Run");
const ROUNDS_CAP = A.tasks.length + 1;
let round = 0;
while (round < ROUNDS_CAP && Object.keys(results).length < A.tasks.length) {
  round += 1;
  const ready = A.tasks.filter((t) => !results[t.key]);
  const batch = ready.slice(0, A.maxParallel);
  const outcomes = await parallel(
    batch.map(
      (task) => () =>
        agent(`do ${task.key}`, {
          label: `worker:${task.key}`,
          phase: "Run",
          model: "sonnet",
          schema: ANSWER,
        }),
    ),
  );
  batch.forEach((task, i) => {
    results[task.key] = outcomes[i];
  });
}
