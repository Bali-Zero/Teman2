#!/usr/bin/env node
// test-run-second-army.mjs — BEHAVIOURAL contract test for infra/workflows/run-second-army.mjs.
//
// WHY THIS FILE EXISTS, and why it is not a source scan. The first cut of this work asserted the
// runner's model-pin guard with a regex over the runner's own source. An independent gate proved
// that was not a test at all: rewriting the guard as `if (!opts?.model)` — identical behaviour —
// made it FAIL, and commenting out both call sites of assertModelPinned() — a real hole — still
// let it PASS. A guard is a behaviour, so it has to be measured as one.
//
// These tests therefore SPAWN the runner as a child process against two fixture scripts that
// differ in exactly one thing (one pins model:, one does not) and assert on what the runner
// actually does. Remove the guard and test 2 goes red, whatever the source looks like.
//
// No deps beyond node:*. No network. --dry-run everywhere, so no claude/codex/agy binary is
// ever spawned by the runner itself.
//
// Run: node infra/workflows/tests/test-run-second-army.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RUNNER = path.resolve(__dirname, "../run-second-army.mjs");
const FIXTURES = path.resolve(__dirname, "fixtures");

/** Run the runner as a real child process; never in-process (importing it executes main()). */
function runRunner(args) {
  return spawnSync(process.execPath, [RUNNER, ...args], {
    encoding: "utf8",
    timeout: 60_000,
  });
}

function argsFile(name, body) {
  const p = path.join(tmpdir(), name);
  writeFileSync(p, JSON.stringify(body));
  return p;
}

const TRIVIAL_ARGS = argsFile("run-second-army-test-args.json", {
  mission: "runner-test",
  colour: "blue",
  floor: 1,
  stamp: "19700101T000000Z",
  outDir: tmpdir(),
  tasks: [],
});

// Test 1 — a fixture whose lane PINS a model runs to completion and its return value reaches
// stdout as JSON. This is the control: it proves the harness works, so test 2's failure can
// only be the missing pin.
function test_pinned_fixture_runs() {
  const r = runRunner([
    "--script",
    path.join(FIXTURES, "fixture-model-pinned.js"),
    "--args-file",
    TRIVIAL_ARGS,
    "--dry-run",
  ]);
  assert.equal(
    r.status,
    0,
    `expected exit 0, got ${r.status}. stderr:\n${r.stderr}`,
  );
  const out = JSON.parse(r.stdout);
  assert.equal(
    out.ok,
    true,
    "the pinned fixture's return value must reach stdout",
  );
  console.log(
    "PASS: a fixture lane that pins model: runs, and its return value reaches stdout",
  );
}

// Test 2 — THE ONE THAT MATTERS. The same fixture with the pin removed must be REFUSED: the
// runner exits non-zero and says why. Comment out assertModelPinned() and this goes red.
function test_unpinned_fixture_is_refused() {
  const r = runRunner([
    "--script",
    path.join(FIXTURES, "fixture-model-missing.js"),
    "--args-file",
    TRIVIAL_ARGS,
    "--dry-run",
  ]);
  assert.notEqual(
    r.status,
    0,
    `a lane without model: must NOT run to completion (exit was ${r.status}, stdout: ${r.stdout})`,
  );
  assert.match(
    r.stderr,
    /opts\.model is required|must pin a model/,
    `the runner must SAY why it refused. stderr:\n${r.stderr}`,
  );
  assert.doesNotMatch(
    r.stdout,
    /"ok"\s*:\s*true/,
    "the refused fixture must not emit a success return value",
  );
  console.log(
    "PASS: a fixture lane that omits model: is refused — non-zero exit, and the runner says why",
  );
}

// Test 3 — an unsupported model alias is refused too. "sonnet"/"haiku"/"opus" are the aliases
// the claude CLI accepts here; anything else is a typo or a seat that does not belong in a lane.
function test_unsupported_model_alias_is_refused() {
  const p = path.join(tmpdir(), "fixture-bad-alias.js");
  writeFileSync(
    p,
    'export const meta = { name: "x", description: "x", whenToUse: "x", phases: [] };\n' +
      'phase("One");\n' +
      'const a = await agent("say anything", { model: "gpt-5.6-terra", label: "probe:x" });\n' +
      "return { ok: true, a };\n",
  );
  const r = runRunner([
    "--script",
    p,
    "--args-file",
    TRIVIAL_ARGS,
    "--dry-run",
  ]);
  assert.notEqual(
    r.status,
    0,
    `an unsupported model alias must be refused (exit was ${r.status})`,
  );
  assert.match(
    r.stderr,
    /unsupported model/,
    `the runner must name the unsupported alias. stderr:\n${r.stderr}`,
  );
  console.log("PASS: an unsupported model alias is refused, and named");
}

// Test 4 — a missing --args-file is a usage error, not a crash or a silent success.
function test_missing_args_file_is_a_usage_error() {
  const r = runRunner(["--dry-run"]);
  assert.equal(
    r.status,
    1,
    `expected exit 1 on missing --args-file, got ${r.status}`,
  );
  assert.match(
    r.stderr,
    /usage:/,
    "the runner must print usage when --args-file is absent",
  );
  console.log("PASS: a missing --args-file is a usage error with a usage line");
}

// Test 5 — stdout carries ONLY the JSON return value; every diagnostic goes to stderr. A caller
// that pipes stdout into jq must never get a log line in the stream.
function test_stdout_is_json_only() {
  const r = runRunner([
    "--script",
    path.join(FIXTURES, "fixture-model-pinned.js"),
    "--args-file",
    TRIVIAL_ARGS,
    "--dry-run",
  ]);
  assert.equal(
    r.status,
    0,
    `expected exit 0, got ${r.status}. stderr:\n${r.stderr}`,
  );
  assert.doesNotThrow(
    () => JSON.parse(r.stdout),
    "stdout must parse as JSON with nothing else in it",
  );
  assert.match(
    r.stderr,
    /\[second-army\]/,
    "diagnostics must go to stderr, prefixed",
  );
  console.log(
    "PASS: stdout is the JSON return value alone; diagnostics go to stderr",
  );
}

const tests = [
  test_pinned_fixture_runs,
  test_unpinned_fixture_is_refused,
  test_unsupported_model_alias_is_refused,
  test_missing_args_file_is_a_usage_error,
  test_stdout_is_json_only,
];

let failed = 0;
for (const t of tests) {
  try {
    t();
  } catch (e) {
    failed++;
    console.error(`FAIL: ${t.name}: ${e && e.stack ? e.stack : e}`);
  }
}
if (failed > 0) {
  console.error(
    `SUMMARY: ${tests.length - failed}/${tests.length} passed, ${failed} FAILED`,
  );
  process.exit(1);
}
console.log(
  `PASS SUMMARY: ${tests.length}/${tests.length} run-second-army behavioural tests passed`,
);
process.exit(0);
