export const meta = {
  name: "saetta",
  description:
    "BLUE mission: bounded independent slices, exact-head gates, blocked dependencies stay closed",
  phases: [
    { title: "Run", detail: "Dux and fresh gates" },
    { title: "Close", detail: "One honest mission receipt" },
  ],
};

// Native Workflow DSL: no imports, filesystem, clock or process globals.
// scripts/saetta.py resolves host paths before this script receives its args.
const A = typeof args === "string" ? JSON.parse(args) : args;
const absolute = (p) =>
  typeof p === "string" && p.startsWith("/") && !/[\n\r\0]/.test(p);
if (
  !A ||
  A.colour !== "BLUE" ||
  !/^[A-Za-z0-9-]+$/.test(A.mission || "") ||
  !absolute(A.repo) ||
  !absolute(A.outputDir) ||
  !Array.isArray(A.tasks) ||
  A.tasks.length < 1 ||
  A.tasks.length > 12 ||
  !Number.isInteger(A.maxParallel) ||
  A.maxParallel < 1 ||
  A.maxParallel > 3
)
  throw new Error("SAETTA: invalid BLUE mission, paths, tasks or capacity");
const nodes = Object.create(null);
for (const task of A.tasks) {
  if (
    !/^[a-z0-9][a-z0-9-]*$/.test(task.key || "") ||
    nodes[task.key] ||
    !absolute(task.brief) ||
    !Array.isArray(task.dependsOn) ||
    !Array.isArray(task.scope) ||
    !task.scope.length ||
    // Scope comparison is literal: Next.js brackets/braces never expand as globs.
    task.scope.some(
      (p) =>
        typeof p !== "string" ||
        !p ||
        /[\x00-\x1f\x7f*?]/.test(p) ||
        p.startsWith("/") ||
        p
          .replace(/\/$/, "")
          .split("/")
          .some((part) => !part || part === "." || part === ".."),
    )
  )
    throw new Error("SAETTA: invalid or duplicate task");
  nodes[task.key] = task;
}
const visited = Object.create(null),
  visiting = Object.create(null);
function visit(key) {
  if (!nodes[key] || visiting[key])
    throw new Error("SAETTA: unknown or cyclic dependency");
  if (visited[key]) return;
  visiting[key] = true;
  nodes[key].dependsOn.forEach(visit);
  visiting[key] = false;
  visited[key] = true;
}
A.tasks.forEach((t) => visit(t.key));
const after = (task, key) =>
  task.dependsOn.some((d) => d === key || after(nodes[d], key));
const overlaps = (a, b) => {
  a = a.replace(/\/$/, "");
  b = b.replace(/\/$/, "");
  return a === b || a.startsWith(b + "/") || b.startsWith(a + "/");
};
for (let i = 0; i < A.tasks.length; i++)
  for (let j = i + 1; j < A.tasks.length; j++) {
    const a = A.tasks[i],
      b = A.tasks[j];
    if (
      !after(a, b.key) &&
      !after(b, a.key) &&
      a.scope.some((p) => b.scope.some((q) => overlaps(p, q)))
    )
      throw new Error("SAETTA: overlapping scopes require a dependency");
  }

const TARGET = {
  type: "object",
  required: ["pr", "head"],
  properties: {
    pr: { type: "integer" },
    head: { type: "string" },
  },
};
const DUX = {
  type: "object",
  required: ["status", "targets"],
  properties: {
    status: { type: "string", enum: ["result", "needs_input", "failed"] },
    targets: { type: "array", items: TARGET },
  },
};
const GATE = {
  type: "object",
  required: ["verdict", "targets", "posted", "merged", "receipt", "reasons"],
  properties: {
    verdict: { type: "string", enum: ["PASS", "BLOCK"] },
    targets: { type: "array", items: TARGET },
    posted: { type: "boolean" },
    merged: { type: "boolean" },
    receipt: { type: "string" },
    reasons: { type: "array", items: { type: "string" } },
  },
};
const CLOSE = {
  type: "object",
  required: ["recorded", "verdict", "receipt"],
  properties: {
    recorded: { type: "boolean" },
    verdict: { type: "string", enum: ["PASS", "BLOCK"] },
    receipt: { type: "string" },
  },
};
const RELEASE = {
  type: "object",
  required: ["verdict", "targets", "live_receipt"],
  properties: {
    verdict: { type: "string", enum: ["PASS", "BLOCK"] },
    targets: { type: "array", items: TARGET },
    live_receipt: { type: "string" },
  },
};
function targets(value) {
  if (
    !Array.isArray(value) ||
    !value.length ||
    value.length > 10 ||
    value.some(
      (t) =>
        !t ||
        !Number.isInteger(t.pr) ||
        t.pr < 1 ||
        !/^[a-f0-9]{40}$/.test(t.head || ""),
    ) ||
    new Set(value.map((t) => t.pr)).size !== value.length
  )
    return null;
  return value
    .map((t) => `${t.pr}:${t.head}`)
    .sort()
    .join(",");
}
const common = `Mission ${A.mission}, BLUE. Repo ${JSON.stringify(A.repo)}.
Read AGENTS.md and .claude/skills/modus/SKILL.md; SAETTA rules apply.
No cleartext client data or secrets in outputs. CLI OAuth only. Never weaken a guardrail.
On resume, ListAgents first; a live successor means stand down without writes.
Do not edit a running workflow or message a running writer to resume it.
No per-slice ledger PR. Record leftovers in the slice pack; one mission close.
M5 remains a thin client: route heavy execution to Pro using the documented SSH route.
Any unavailable required seat returns BLOCK/needs_input, never silently changes family.
Evidence directory: ${JSON.stringify(A.outputDir)}.`;
const results = Object.create(null);
const blocked = (key, reason, dux = null, gate = null) => ({
  key,
  verdict: "BLOCK",
  reasons: [reason],
  dux,
  gate,
});
async function run(task) {
  const dependencies = task.dependsOn.map((key) => results[key]);
  if (dependencies.some((r) => !r || r.verdict !== "PASS"))
    return blocked(task.key, "prerequisite_not_passed");
  let dux = null,
    gate = null;
  try {
    dux = await agent(
      `${common}
You are the appointed Claude Dux of slice ${task.key}, not its final grader.
Read brief ${JSON.stringify(task.brief)}. Write scope ${JSON.stringify(task.scope)}.
Create your own worktree with scripts/agent_start.py; other agents share the repository.
Predecessors have merged after an independent exact-head PASS: ${JSON.stringify(dependencies)}.
Follow the brief through tests, independent cross-family review, push and PR creation.
Read AUTONOMOUS_OPS.md fully before release. Arm auto-merge when opening the PR,
then freeze the candidate. Return the exact PR numbers and full head SHAs for the fresh gate.
Never self-sign the gate. Never deploy an unmerged candidate or bypass required checks.
State a checkpoint default; no ack in 15 minutes permits that declared default.
A harness red requires diagnosis and a harness repair, never rebuilding the candidate branch.
Keep the root active-time deadline and child caps from the brief; at a cap checkpoint and return.`,
      {
        label: `dux:${task.key}`,
        phase: "Run",
        model: "opus",
        effort: "xhigh",
        schema: DUX,
      },
    );
    const expected = dux && dux.status === "result" && targets(dux.targets);
    if (!expected) return blocked(task.key, "dux_incomplete", dux);
    gate = await agent(
      `${common}
You are a fresh independent Opus final gate, commissioned by the imperator, outside the contribution chain.
20 minute budget. Read brief ${JSON.stringify(task.brief)} and independently inspect these exact targets:
${JSON.stringify(dux.targets)}. Verify each current GitHub head matches before doing anything.
Allowed product write scope: ${JSON.stringify(task.scope)}. The only metadata exception is
the PR's own canonical evidence directory emitted by scripts/ci/evidence_paths.py;
allow its brief/pack/check receipts only. BLOCK any other out-of-scope candidate change.
Rerun the brief's real checks in a separate broker worktree. Read-only candidate; do not fix it,
arm it, or deploy it. A discrepancy in shipped code blocks; evidence prose defects are notices.
Post your independent PASS/BLOCK via gh pr comment --body-file and publish harness/fable-gate
using scripts/harness_fable_gate.py on EACH exact SHA; read back both comment and status.
Only that prescribed gate receipt is a permitted external write. Save a redacted gate receipt
under the evidence directory with verified heads, check commands, exit codes and status URLs.
If PASS, observe merge of those exact frozen candidates within the 20 minute total budget;
merged=true only when ALL merged and none acquired an unreviewed successor head.
Do not rerun red checks blindly. A harness blockage or timeout returns merged=false and reasons.
posted=true only if every required comment and status was read back on its exact SHA.
Return binary verdict plus those same targets, posted, merged, receipt path and reasons.`,
      {
        label: `gate:${task.key}`,
        phase: "Run",
        model: "opus",
        effort: "xhigh",
        schema: GATE,
      },
    );
    if (
      !gate ||
      gate.verdict !== "PASS" ||
      gate.posted !== true ||
      gate.merged !== true ||
      !absolute(gate.receipt) ||
      targets(gate.targets) !== expected
    )
      return blocked(task.key, "gate_not_accepted", dux, gate);
    const release = await agent(
      `${common}
You are the authorized Claude release owner for slice ${task.key}. Read AUTONOMOUS_OPS.md fully.
Read brief ${JSON.stringify(task.brief)} and independent gate receipt ${JSON.stringify(gate.receipt)}.
Re-read GitHub and the receipt to confirm these frozen targets merged after PASS:
${JSON.stringify(dux.targets)}. If anything differs, BLOCK without mutation.
Run ONLY the release and prove-live steps authorized in the brief. Use the existing deploy
lease and reviewed installation/deployment path. Do not edit/rebuild the candidate, bypass
checks, add a new provider or publish customer content. A missing release plan is BLOCK.
Verify the actual consumer after release, record commands, exit codes and observed version
in a redacted receipt under the evidence directory. Return PASS only after reading back
that receipt and proving every target's consumer. No live proof means BLOCK, never inferred success.`,
      {
        label: `release:${task.key}`,
        phase: "Run",
        model: "opus",
        effort: "xhigh",
        schema: RELEASE,
      },
    );
    if (
      !release ||
      release.verdict !== "PASS" ||
      !absolute(release.live_receipt) ||
      targets(release.targets) !== expected
    )
      return {
        ...blocked(task.key, "prove_live_not_accepted", dux, gate),
        release,
      };
    return { key: task.key, verdict: "PASS", reasons: [], dux, gate, release };
  } catch (_) {
    // Native parallel turns thrown branches into null: capture failure inside the branch.
    return blocked(task.key, "seat_failed", dux, gate);
  }
}

phase("Run");
while (Object.keys(results).length < A.tasks.length) {
  const ready = A.tasks.filter(
    (t) => !results[t.key] && t.dependsOn.every((d) => results[d]),
  );
  const batch = ready.slice(0, A.maxParallel);
  const outcomes = await parallel(batch.map((task) => () => run(task)));
  batch.forEach((task, i) => {
    results[task.key] =
      outcomes[i] || blocked(task.key, "workflow_branch_failed");
    log(`${task.key}: ${results[task.key].verdict}`);
  });
}
const ordered = A.tasks.map((t) => results[t.key]);
const verdict = ordered.every((r) => r.verdict === "PASS") ? "PASS" : "BLOCK";
phase("Close");
let close = null;
try {
  close = await agent(
    `${common}
Close this mission ONCE. The scheduler verdict is authoritative and cannot be upgraded:
${JSON.stringify({ verdict, results: ordered })}
Save a redacted mission receipt under the evidence directory naming passed and blocked slices,
unlaunched dependants, exact target SHAs, gate receipts, remaining release/prove-live work.
A passed gate is not prove-live. Read back receipts and merged heads; a discrepancy downgrades to BLOCK.
Do not launch a new builder, fix code, deploy, publish, or create a ledger PR.
Return recorded=true only after reading back the saved receipt. Return its absolute path.
The imperator consumes this single receipt to rule on BLOCK and record the mission close.`,
    {
      label: `close:${A.mission}`,
      phase: "Close",
      model: "sonnet",
      effort: "high",
      schema: CLOSE,
    },
  );
} catch (_) {
  /* The return value must not disguise a failed close. */
}
return {
  mission: A.mission,
  verdict:
    verdict === "PASS" &&
    close &&
    close.recorded === true &&
    close.verdict === "PASS" &&
    absolute(close.receipt)
      ? "PASS"
      : "BLOCK",
  results: ordered,
  close,
};
