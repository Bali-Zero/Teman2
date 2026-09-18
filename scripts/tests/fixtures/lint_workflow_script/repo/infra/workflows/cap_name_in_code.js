// Twin of cap_name_only_in_comment.js: same shape, but maxRounds is a REAL declared
// constant, not just a comment mention — must stay clean before and after DEFECT :253.
phase("Run");
const maxRounds = A.tasks.length + 1;
let round = 0;
while (round < maxRounds) {
  round += 1;
  results[A.tasks[0].key] = true;
}
