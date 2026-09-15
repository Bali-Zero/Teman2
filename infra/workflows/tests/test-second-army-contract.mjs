#!/usr/bin/env node
// test-second-army-contract.mjs — contract test for infra/workflows/second-army.js
// (docs/architecture/dual-consul/army-map.md §1ter). Follows the
// ESTABLISHED pattern in test-kbli-certification-contract.mjs: read the real source, strip the
// ESM-only `export ` token, compile the body as an AsyncFunction, drive it with a stub agent().
// No deps beyond node:assert/fs/path/url (Node >=18). No network, no claude/codex/agy binary.
//
// Run: node infra/workflows/tests/test-second-army-contract.mjs

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SECOND_ARMY_PATH = path.resolve(__dirname, "../second-army.js");

// ---- tokenizer-aware source scanner ---------------------------------------------------------
// A naive regex (e.g. /agent\([^)]*model:/) can pass a call site with no model: of its own, as
// long as SOME other agent() call — or a stray comment — contains "model:" elsewhere in the
// file. The helpers below walk the source respecting string/template/comment boundaries, so
// bracket depth and argument splitting are computed over CODE only, then each agent() call's
// own argument text is inspected in isolation.

/** Chars to skip starting at src[i] so a comment/string/template is one atomic unit (its
 * internal punctuation never perturbs bracket-depth counting). Non-recursive on `${...}` —
 * sufficient because neither file nests a backtick inside one. */
function advanceOne(src, i) {
  const c = src[i];
  if (c === "/" && src[i + 1] === "/") {
    const j = src.indexOf("\n", i);
    return j === -1 ? src.length - i : j - i;
  }
  if (c === "/" && src[i + 1] === "*") {
    const j = src.indexOf("*/", i + 2);
    return j === -1 ? src.length - i : j + 2 - i;
  }
  if (c === '"' || c === "'" || c === "`") {
    let j = i + 1;
    while (j < src.length) {
      if (src[j] === "\\") {
        j += 2;
        continue;
      }
      if (src[j] === c) {
        j++;
        break;
      }
      j++;
    }
    return j - i;
  }
  return 1;
}

/** Balanced-paren extraction: text strictly between the '(' at openParenIdx and its matching
 * ')', skipping string/comment/template contents so a stray paren inside one can't desync it. */
function extractBalancedParens(src, openParenIdx) {
  let depth = 0;
  let i = openParenIdx;
  while (i < src.length) {
    const ch = src[i];
    const step = advanceOne(src, i);
    if (step === 1) {
      if (ch === "(") depth++;
      else if (ch === ")") {
        depth--;
        if (depth === 0) return src.slice(openParenIdx + 1, i);
      }
    }
    i += step;
  }
  throw new Error(`unbalanced parens starting at index ${openParenIdx}`);
}

/** Every REAL `agent(` call site in `src` — matched only where step===1 (actual code, not a
 * comment/string: this file's own doc comments literally say "agent()" twice, which a plain
 * regex over raw text would misfire on). Word-boundary guarded (`.agent(`/`myagent(` excluded).
 * One { index, argsText } per real call, argsText via balanced-paren scanning. */
function findAgentCalls(src) {
  const calls = [];
  let i = 0;
  while (i < src.length) {
    const step = advanceOne(src, i);
    if (step === 1) {
      const prev = i === 0 ? "" : src[i - 1];
      if (!/[\w$.]/.test(prev) && /^agent\s*\(/.test(src.slice(i, i + 20))) {
        const openParenIdx = src.indexOf("(", i);
        calls.push({
          index: openParenIdx,
          argsText: extractBalancedParens(src, openParenIdx),
        });
      }
    }
    i += step;
  }
  return calls;
}

/** Splits a call's argument text into top-level arguments (commas inside nested brackets,
 * strings, comments and templates are not split points). */
function splitTopLevelArgs(argsText) {
  const parts = [];
  let depth = 0;
  let start = 0;
  let i = 0;
  while (i < argsText.length) {
    const ch = argsText[i];
    const step = advanceOne(argsText, i);
    if (step === 1) {
      if ("([{".includes(ch)) depth++;
      else if (")]}".includes(ch)) depth--;
      else if (ch === "," && depth === 0) {
        parts.push(argsText.slice(start, i));
        start = i + 1;
      }
    }
    i += step;
  }
  parts.push(argsText.slice(start));
  return parts.map((p) => p.trim()).filter((p) => p.length > 0);
}

/** True only if `model:` appears DIRECTLY inside the outer `{` of objText (depth 1) — not
 * inside a nested object (e.g. a `schema:` value), and not inside a string/comment. */
function hasTopLevelModelKey(objText) {
  let depth = 0;
  let i = 0;
  while (i < objText.length) {
    const ch = objText[i];
    const step = advanceOne(objText, i);
    if (step === 1) {
      if (ch === "{" || ch === "[" || ch === "(") depth++;
      else if (ch === "}" || ch === "]" || ch === ")") depth--;
      else if (depth === 1 && /model\s*:/.test(objText.slice(i, i + 8)))
        return true;
    }
    i += step;
  }
  return false;
}

/** Text-slices a top-level `const NAME = <literal>;` out of `src` via balanced-bracket scanning
 * (same trick test-kbli-certification-contract.mjs uses for sha256Hex) so it can be compiled
 * standalone with `new Function`. */
function extractConstLiteral(src, name) {
  const marker = `const ${name} = `;
  const idx = src.indexOf(marker);
  assert.ok(idx !== -1, `could not find "${marker}" in source`);
  const startBrace = idx + marker.length;
  const openChar = src[startBrace];
  assert.ok(
    openChar === "{" || openChar === "[",
    `const ${name} must start with an object/array literal`,
  );
  const closeChar = openChar === "{" ? "}" : "]";
  let depth = 0;
  let i = startBrace;
  while (i < src.length) {
    const ch = src[i];
    const step = advanceOne(src, i);
    if (step === 1) {
      if (ch === openChar) depth++;
      else if (ch === closeChar) {
        depth--;
        if (depth === 0) return src.slice(startBrace, i + 1);
      }
    }
    i += step;
  }
  throw new Error(`unbalanced literal for const ${name}`);
}

// ---- dynamic driver: compile second-army.js the way the harness does -----------------------

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function compileSecondArmy() {
  let src = readFileSync(SECOND_ARMY_PATH, "utf8");
  src = src.replace(/^export const meta/m, "const meta");
  return new AsyncFunction(
    "args",
    "agent",
    "log",
    "phase",
    "parallel",
    "pipeline",
    src,
  );
}

async function pipelineStub(items, ...stages) {
  return Promise.all(
    items.map(async (item, index) => {
      let prev;
      for (const stage of stages) prev = await stage(prev, item, index);
      return prev;
    }),
  );
}

async function parallelStub(thunks) {
  return Promise.all(thunks.map((t) => t().catch(() => null)));
}

function makeAgentStub(responder) {
  const calls = [];
  const agent = async (prompt, opts) => {
    calls.push({ prompt, opts });
    return responder(prompt, opts, calls);
  };
  return { agent, calls };
}

function defaultResponder(_prompt, opts) {
  const label = opts.label || "";
  if (label.startsWith("probe:"))
    return { alive: true, evidence: "stub: alive" };
  if (label.startsWith("build:"))
    return { claim: `stub claim for ${label}`, filesTouched: "stub file list" };
  if (label.startsWith("verify:"))
    return {
      holds: true,
      observation: "stub: criterion observed",
      command: "stub --proof",
    };
  if (label.startsWith("refute:"))
    return { refuted: false, reason: "stub: nothing to refute" };
  if (label === "report") return "stub: report written";
  return "stub: generic";
}

function baseArgs(overrides = {}) {
  return {
    mission: "m-test",
    colour: "blue",
    floor: 1,
    stamp: "20260915T000000Z",
    outDir: "/tmp",
    tasks: [
      {
        key: "t1",
        prompt: "do the thing",
        files: ["infra/workflows/README.md"],
        proof: "the thing was done",
      },
    ],
    ...overrides,
  };
}

async function runSecondArmy(args, responder) {
  const runner = compileSecondArmy();
  const { agent, calls } = makeAgentStub(responder);
  const result = await runner(
    args,
    agent,
    () => {},
    () => {},
    parallelStub,
    pipelineStub,
  );
  return { result, calls };
}

/** The script's own doctrine constants, text-sliced and evaluated standalone. */
function doctrine() {
  const src = readFileSync(SECOND_ARMY_PATH, "utf8");
  const ev = (name) =>
    new Function(
      `"use strict";\nreturn (${extractConstLiteral(src, name)});`,
    )(); // eslint-disable-line no-new-func
  const scalar = (name) => {
    const m = new RegExp(`const ${name} = ("[^"]*"|\\d+);`).exec(src);
    assert.ok(m, `could not find scalar const ${name}`);
    return JSON.parse(m[1]);
  };
  return {
    SEAT_FAMILY: ev("SEAT_FAMILY"),
    SEAT_DOOR: ev("SEAT_DOOR"),
    CHAIN: ev("CHAIN"),
    REFUTER_SEATS: ev("REFUTER_SEATS"),
    HAIKU_GRUNT_SEAT: scalar("HAIKU_GRUNT_SEAT"),
    DUX_LANE_MODEL: scalar("DUX_LANE_MODEL"),
    REFUTER_FLOOR: scalar("REFUTER_FLOOR"),
  };
}

// ---- tests -------------------------------------------------------------------------------

// Test 1 — STATIC: every agent() call in second-army.js pins model:.
function test_static_every_agent_call_pins_model() {
  const src = readFileSync(SECOND_ARMY_PATH, "utf8");
  const calls = findAgentCalls(src);
  assert.ok(
    calls.length > 0,
    "static scan must find at least one agent() call site (finding nothing must fail)",
  );
  const missing = [];
  for (const call of calls) {
    const argParts = splitTopLevelArgs(call.argsText);
    const optionsArg = argParts[argParts.length - 1];
    const ok =
      optionsArg &&
      optionsArg.startsWith("{") &&
      hasTopLevelModelKey(optionsArg);
    if (!ok) missing.push(call.argsText.slice(0, 80).replace(/\n/g, " "));
  }
  assert.equal(
    missing.length,
    0,
    `agent() call(s) missing a top-level model: key: ${JSON.stringify(missing)}`,
  );
  console.log(
    `PASS: static scan found ${calls.length} agent() call site(s) in second-army.js, all pin model:`,
  );
}

// Test 2 — DYNAMIC: every recorded agent() call carries model in {sonnet, haiku, opus}.
async function test_dynamic_every_call_pins_valid_model() {
  const { calls } = await runSecondArmy(baseArgs(), defaultResponder);
  assert.ok(calls.length > 0, "dynamic run must invoke agent() at least once");
  for (const c of calls) {
    const model = c.opts && c.opts.model;
    assert.ok(
      ["sonnet", "haiku", "opus"].includes(model),
      `call ${c.opts && c.opts.label} has invalid/missing model: ${model}`,
    );
  }
  console.log(
    `PASS: dynamic run recorded ${calls.length} agent() call(s), all pin a valid model`,
  );
}

// Test 3 — RULED 2026-09-15: the builder roster carries no seat of the Dux's OWN family except
// the Anthropic-native grunt seat, and that one sits LAST so it is reached only after every
// cross-family door has died.
function test_builder_roster_excludes_dux_family_except_grunt() {
  const { SEAT_FAMILY, CHAIN, HAIKU_GRUNT_SEAT } = doctrine();
  const colours = Object.keys(CHAIN);
  assert.ok(colours.length > 0, "CHAIN must name at least one colour");
  for (const colour of colours) {
    const { dux, builders } = CHAIN[colour];
    assert.ok(
      dux in SEAT_FAMILY,
      `${colour}: dux "${dux}" must exist in SEAT_FAMILY`,
    );
    assert.ok(
      Array.isArray(builders) && builders.length > 0,
      `${colour}: builder roster must be non-empty`,
    );
    const duxFamily = SEAT_FAMILY[dux];
    for (const [i, b] of builders.entries()) {
      assert.ok(
        b in SEAT_FAMILY,
        `${colour}: builder "${b}" must exist in SEAT_FAMILY`,
      );
      if (SEAT_FAMILY[b] !== duxFamily) continue;
      assert.equal(
        b,
        HAIKU_GRUNT_SEAT,
        `${colour}: builder "${b}" shares the dux family ${duxFamily} and is not the grunt seat`,
      );
      assert.equal(
        i,
        builders.length - 1,
        `${colour}: the grunt seat "${b}" must be LAST in the roster, not position ${i}`,
      );
    }
  }
  console.log(
    "PASS: no builder shares the dux's family except the grunt seat, which is always last",
  );
}

// Test 4 — generator != grader: the Dux is the verifier, and the Dux is never in its own
// builder roster, for any colour.
function test_no_builder_is_its_own_verifier() {
  const { CHAIN } = doctrine();
  for (const colour of Object.keys(CHAIN)) {
    const { dux, builders } = CHAIN[colour];
    assert.ok(
      !builders.includes(dux),
      `${colour}: the dux "${dux}" must not appear in its own builder roster`,
    );
  }
  console.log(
    "PASS: the dux never appears in its own builder roster — builder != verifier, every colour",
  );
}

// Test 5 — the VERIFY lane runs on the Dux lane model, statically and dynamically.
async function test_verify_lane_runs_on_the_dux_lane_model() {
  const { DUX_LANE_MODEL } = doctrine();
  assert.equal(
    DUX_LANE_MODEL,
    "sonnet",
    "the dux verification lane must run on sonnet",
  );
  const { calls } = await runSecondArmy(baseArgs(), defaultResponder);
  const verifyCalls = calls.filter((c) =>
    (c.opts.label || "").startsWith("verify:"),
  );
  assert.ok(verifyCalls.length > 0, "expected at least one verify: lane");
  for (const c of verifyCalls)
    assert.equal(
      c.opts.model,
      "sonnet",
      `verify lane ${c.opts.label} must be model:"sonnet"`,
    );
  const buildCalls = calls.filter((c) =>
    (c.opts.label || "").startsWith("build:"),
  );
  assert.ok(buildCalls.length > 0, "expected at least one build: lane");
  for (const c of buildCalls)
    assert.equal(
      c.opts.model,
      "haiku",
      `build lane ${c.opts.label} must be driven from the haiku grunt lane`,
    );
  console.log(
    'PASS: verify lanes run model:"sonnet" (the dux); build lanes are driven from model:"haiku"',
  );
}

// Test 6 — a simulated dead BUILDER lands in deadTiers and the next live builder is used.
async function test_simulated_dead_builder_falls_through() {
  const { CHAIN } = doctrine();
  const [first, second] = CHAIN.blue.builders;
  const responder = (_p, opts) =>
    opts.label === `probe:${first}`
      ? { alive: false, evidence: "simulated dead" }
      : defaultResponder(_p, opts);
  const { result } = await runSecondArmy(baseArgs(), responder);

  const dead = result.deadTiers.find((d) => d.seat === first);
  assert.ok(
    dead && dead.reason,
    `simulated-dead builder ${first} must appear in deadTiers with a reason`,
  );
  assert.equal(
    result.built.length,
    1,
    "the task must still build, via the next live builder",
  );
  assert.equal(
    result.built[0].seat,
    second,
    `the next live builder must be ${second}, got ${result.built[0].seat}`,
  );
  assert.equal(
    result.verified.length,
    1,
    "the dux must still verify the surviving build",
  );
  console.log(
    `PASS: dead builder "${first}" declared in deadTiers; build fell through to "${second}"`,
  );
}

// Test 7 — every cross-family door dead => the Anthropic-native grunt seat builds, and it is
// the ONLY circumstance in which a same-family builder is legal.
async function test_all_cross_family_dead_falls_back_to_grunt() {
  const { HAIKU_GRUNT_SEAT } = doctrine();
  const responder = (_p, opts) =>
    (opts.label || "").startsWith("probe:")
      ? { alive: false, evidence: "simulated dead" }
      : defaultResponder(_p, opts);
  const { result } = await runSecondArmy(baseArgs(), responder);
  assert.equal(
    result.built.length,
    1,
    "the grunt fallback must still produce a build",
  );
  assert.equal(
    result.built[0].seat,
    HAIKU_GRUNT_SEAT,
    "with every cross-family door dead the grunt seat must build",
  );
  console.log(
    `PASS: every cross-family door dead => grunt seat "${HAIKU_GRUNT_SEAT}" builds, declared`,
  );
}

// Test 8 — floor: 3 promotes: no build/verify/refute lane, declared-dead seats still reported.
async function test_floor_3_promotes() {
  const { result, calls } = await runSecondArmy(
    baseArgs({ floor: 3 }),
    defaultResponder,
  );

  assert.equal(result.promoted, true, "floor 3 must promote");
  assert.equal(result.built.length, 0, "no build on the promoted path");
  assert.equal(result.verified.length, 0, "no verify on the promoted path");

  const forbidden = calls.find((c) => {
    const l = (c.opts && c.opts.label) || "";
    return (
      l.startsWith("build:") ||
      l.startsWith("verify:") ||
      l.startsWith("refute:")
    );
  });
  assert.equal(
    forbidden,
    undefined,
    "no build:/verify:/refute: lane may run on a promoted mission",
  );

  const deadSeats = result.deadTiers.map((d) => d.seat).sort();
  assert.deepEqual(
    deadSeats,
    ["kimi", "qwen-cloud-code", "tp1-deepseek-v4-pro", "tp1-glm-5.2"].sort(),
  );
  console.log(
    "PASS: floor 3 promotes — no build/verify/refute lane, declared-dead seats still reported",
  );
}

// Test 9 — the floor-2 cross-family refuter exists at floor 2 and NOWHERE else.
async function test_refuter_lane_only_at_floor_2() {
  const { REFUTER_SEATS, SEAT_FAMILY, CHAIN, REFUTER_FLOOR } = doctrine();
  assert.equal(REFUTER_FLOOR, 2, "the refuter floor must be 2");
  for (const s of REFUTER_SEATS) {
    assert.notEqual(
      SEAT_FAMILY[s],
      SEAT_FAMILY[CHAIN.blue.dux],
      `refuter "${s}" must be cross-family from the blue dux`,
    );
  }

  const one = await runSecondArmy(baseArgs({ floor: 1 }), defaultResponder);
  assert.ok(
    !one.calls.some((c) => (c.opts.label || "").startsWith("refute:")),
    "floor 1 must launch no refuter lane",
  );
  assert.equal(one.result.refuter, null, "floor 1 must return refuter:null");

  const two = await runSecondArmy(
    baseArgs({ floor: 2, frozenRef: "origin/agent/test/frozen" }),
    defaultResponder,
  );
  const refuteCall = two.calls.find((c) =>
    (c.opts.label || "").startsWith("refute:"),
  );
  assert.ok(refuteCall, "floor 2 must launch exactly one refuter lane");
  assert.equal(
    two.calls.filter((c) => (c.opts.label || "").startsWith("refute:")).length,
    1,
    "ONE refuter, never a council",
  );
  assert.ok(
    REFUTER_SEATS.includes(two.result.refuter.seat),
    "the refuter seat must come from REFUTER_SEATS",
  );
  assert.ok(
    refuteCall.prompt.includes("origin/agent/test/frozen"),
    "the refuter must read the FROZEN ref it was given",
  );
  console.log(
    "PASS: the cross-family refuter runs at floor 2 only, exactly once, on the frozen ref",
  );
}

// Test 10 — the declared dead tiers are never probed.
async function test_declared_dead_tiers_never_probed() {
  const { calls } = await runSecondArmy(baseArgs(), defaultResponder);
  const banned = [
    "probe:kimi",
    "probe:qwen-cloud-code",
    "probe:tp1-glm-5.2",
    "probe:tp1-deepseek-v4-pro",
  ];
  for (const label of banned) {
    assert.ok(
      !calls.some((c) => c.opts && c.opts.label === label),
      `declared-dead seat was probed: ${label}`,
    );
  }
  console.log(
    "PASS: declared-dead tiers (kimi/qwen-cloud-code/tp1-glm-5.2/tp1-deepseek-v4-pro) are never probed",
  );
}

// Test 11 — the DUX verify lane never sees the builder's claim.
async function test_verifier_never_sees_builder_answer() {
  const sentinel = "SENTINEL-XYZZY-42-DO-NOT-LEAK";
  const responder = (_prompt, opts) =>
    (opts.label || "").startsWith("build:")
      ? { claim: sentinel, filesTouched: sentinel }
      : defaultResponder(_prompt, opts);
  const { calls } = await runSecondArmy(baseArgs(), responder);
  const verifyCall = calls.find((c) => c.opts && c.opts.label === "verify:t1");
  assert.ok(verifyCall, "expected a verify:t1 call");
  assert.ok(
    !verifyCall.prompt.includes(sentinel),
    "the verify: lane prompt must not contain the builder's claim sentinel",
  );
  console.log(
    "PASS: the dux verify lane prompt never contains the builder's claim",
  );
}

// Test 12 — every seat the doctrine names has a door, and every bash door has a probe.
function test_every_named_seat_has_a_door_and_a_probe() {
  const { SEAT_DOOR, CHAIN, REFUTER_SEATS } = doctrine();
  const named = new Set(REFUTER_SEATS);
  for (const colour of Object.keys(CHAIN)) {
    named.add(CHAIN[colour].dux);
    for (const b of CHAIN[colour].builders) named.add(b);
  }
  for (const seat of named) {
    const door = SEAT_DOOR[seat];
    assert.ok(
      door,
      `seat "${seat}" is named by the doctrine but has no SEAT_DOOR entry`,
    );
    if (door.kind === "bash")
      assert.ok(
        door.probe,
        `bash-door seat "${seat}" must carry a 1-token probe command`,
      );
    else
      assert.equal(
        door.kind,
        "native",
        `seat "${seat}" has an unknown door kind ${door.kind}`,
      );
  }
  console.log(
    `PASS: all ${named.size} doctrine-named seats resolve to a door; every bash door carries a probe`,
  );
}

const tests = [
  test_static_every_agent_call_pins_model,
  test_dynamic_every_call_pins_valid_model,
  test_builder_roster_excludes_dux_family_except_grunt,
  test_no_builder_is_its_own_verifier,
  test_verify_lane_runs_on_the_dux_lane_model,
  test_simulated_dead_builder_falls_through,
  test_all_cross_family_dead_falls_back_to_grunt,
  test_floor_3_promotes,
  test_refuter_lane_only_at_floor_2,
  test_declared_dead_tiers_never_probed,
  test_verifier_never_sees_builder_answer,
  test_every_named_seat_has_a_door_and_a_probe,
];

async function main() {
  let failed = 0;
  for (const t of tests) {
    try {
      await t();
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
    `PASS SUMMARY: ${tests.length}/${tests.length} second-army contract tests passed`,
  );
  process.exit(0);
}

main();
