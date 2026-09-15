#!/usr/bin/env node
// run-second-army.mjs — standalone Node ESM runner for second-army.js: runs it OUTSIDE the
// Workflow tool (shell/cron), Node >=18, no deps beyond node:*. Compiles the script with the
// same AsyncFunction trick as test-second-army-contract.mjs and injects
// args/agent/log/phase/parallel/pipeline/budget bindings the harness would otherwise supply.
//
// USAGE: node infra/workflows/run-second-army.mjs --args-file <path-to-json> [--dry-run]
// stdout carries ONLY the script's JSON return value; log()/phase() and diagnostics go to
// stderr, prefixed "[second-army]". Exit 0 on a completed run (promoted:true included — a
// promotion is a correct outcome). Exit 1 on a runner error.
//
// This file also ENFORCES the model-pin rule: agent() throws if opts.model is missing,
// independent of the contract test's static/dynamic coverage.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const SCRIPT_PATH = path.resolve(__dirname, "second-army.js");

function log(...parts) {
  console.error("[second-army]", ...parts);
}
function phase(name) {
  console.error(`[second-army] phase: ${name}`);
}
const budget = { total: null, spent: () => 0, remaining: () => Infinity };

// ----- pipeline / parallel: no barrier, matches the Workflow-DSL semantics -------------------

async function pipeline(items, ...stages) {
  return Promise.all(
    items.map(async (item, index) => {
      let prev;
      for (const stage of stages) {
        try {
          prev = await stage(prev, item, index);
        } catch (e) {
          log(`pipeline stage threw for item ${index}: ${e && e.message}`);
          return null;
        }
      }
      return prev;
    }),
  );
}

function makeSemaphore(limit) {
  let active = 0;
  const queue = [];
  return {
    acquire() {
      return new Promise((resolve) => {
        const attempt = () => {
          if (active < limit) {
            active++;
            resolve();
          } else {
            queue.push(attempt);
          }
        };
        attempt();
      });
    },
    release() {
      active--;
      const next = queue.shift();
      if (next) next();
    },
  };
}

function makeParallel() {
  const sem = makeSemaphore(4);
  return async function parallel(thunks) {
    return Promise.all(
      thunks.map(async (t) => {
        await sem.acquire();
        try {
          return await t().catch(() => null);
        } finally {
          sem.release();
        }
      }),
    );
  };
}

// ----- agent(): the real claude-CLI door + the --dry-run canned door -------------------------

function toolsForLabel(label) {
  const l = label || "";
  // The VERIFY lane is the DUX and the REFUTE lane reads a frozen diff: both are read-only by
  // doctrine — a grader that can edit what it grades is not a grader (army-map.md §1ter (b)).
  if (
    l.startsWith("probe:") ||
    l.startsWith("verify:") ||
    l.startsWith("refute:")
  )
    return ["Bash", "Read", "Grep", "Glob"];
  if (l.startsWith("build:"))
    return ["Bash", "Read", "Write", "Edit", "Grep", "Glob"];
  if (l === "report") return ["Write", "Read"];
  return ["Read", "Grep", "Glob"];
}

function modelAlias(model) {
  if (model === "sonnet" || model === "haiku" || model === "opus") return model;
  throw new Error(
    `agent(): unsupported model "${model}" — only sonnet|haiku|opus map to the claude CLI`,
  );
}

function assertModelPinned(opts) {
  // THIS is the enforcement point named in the mission's DELIVERABLE 3 test 8: the runner
  // itself throws when a lane omits opts.model, independent of any static/dynamic test.
  if (!opts || !opts.model) {
    throw new Error(
      "agent(): opts.model is required — every lane must pin a model",
    );
  }
}

function makeRealAgent() {
  return function agent(prompt, opts) {
    assertModelPinned(opts);
    const alias = modelAlias(opts.model);
    const tools = toolsForLabel(opts.label);
    const argv = [
      "-p",
      prompt,
      "--model",
      alias,
      "--output-format",
      "json",
      "--permission-mode",
      "acceptEdits",
      "--allowedTools",
      ...tools,
    ];
    if (opts.schema) {
      argv.push("--json-schema", JSON.stringify(opts.schema));
    }
    const timeoutS = Number(process.env.SECOND_ARMY_LANE_TIMEOUT_S) || 900;
    return new Promise((resolve) => {
      let child;
      try {
        // Never a credential on argv — the claude CLI carries its own OAuth; nothing here
        // reads or prints an env value.
        child = spawn("claude", argv, {
          cwd: REPO_ROOT,
          stdio: ["ignore", "pipe", "pipe"],
        });
      } catch (e) {
        log(`agent(${opts.label || "?"}) spawn failed: ${e.message}`);
        resolve(null);
        return;
      }
      let stdout = "";
      let stderr = "";
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        child.kill("SIGTERM");
      }, timeoutS * 1000);
      child.stdout.on("data", (d) => {
        stdout += d;
      });
      child.stderr.on("data", (d) => {
        stderr += d;
      });
      child.on("error", (err) => {
        clearTimeout(timer);
        log(`agent(${opts.label || "?"}) spawn error: ${err.message}`);
        resolve(null);
      });
      child.on("close", (code) => {
        clearTimeout(timer);
        if (timedOut) {
          log(`agent(${opts.label || "?"}) timed out after ${timeoutS}s`);
          resolve(null);
          return;
        }
        if (code !== 0) {
          log(
            `agent(${opts.label || "?"}) exited ${code}: ${stderr.slice(0, 500)}`,
          );
          resolve(null);
          return;
        }
        try {
          const envelope = JSON.parse(stdout);
          resolve(opts.schema ? JSON.parse(envelope.result) : envelope.result);
        } catch (e) {
          log(`agent(${opts.label || "?"}) parse failure: ${e.message}`);
          resolve(null);
        }
      });
    });
  };
}

function makeDryRunAgent() {
  return async function agent(_prompt, opts) {
    assertModelPinned(opts);
    modelAlias(opts.model);
    const label = opts.label || "";
    if (label.startsWith("probe:"))
      return {
        alive: true,
        evidence: "dry-run: canned alive, nothing spawned",
      };
    if (label.startsWith("build:"))
      return {
        claim: "dry-run canned build claim",
        filesTouched: "dry-run: nothing touched",
      };
    if (label.startsWith("verify:"))
      return {
        holds: true,
        observation: "dry-run: no real check performed",
        command: "dry-run: nothing run",
      };
    if (label.startsWith("refute:"))
      return { refuted: false, reason: "dry-run canned refuter verdict" };
    if (label === "report") return "dry-run: report not actually written";
    return "dry-run canned response";
  };
}

// ----- main -----------------------------------------------------------------------------------

async function main() {
  const argv = process.argv.slice(2);
  const argsFileIdx = argv.indexOf("--args-file");
  if (argsFileIdx === -1 || !argv[argsFileIdx + 1]) {
    log(
      "usage: node run-second-army.mjs --args-file <path-to-json> [--dry-run]",
    );
    process.exitCode = 1;
    return;
  }
  const argsFilePath = argv[argsFileIdx + 1];
  const dryRun = argv.includes("--dry-run");

  let scriptArgs;
  try {
    scriptArgs = JSON.parse(readFileSync(argsFilePath, "utf8"));
  } catch (e) {
    log(`failed to read/parse --args-file ${argsFilePath}: ${e.message}`);
    process.exitCode = 1;
    return;
  }

  let src;
  try {
    src = readFileSync(SCRIPT_PATH, "utf8");
  } catch (e) {
    log(`failed to read second-army.js: ${e.message}`);
    process.exitCode = 1;
    return;
  }
  // The real harness handles `export const meta` specially; a standalone compile only needs
  // the executable body (same trick as test-second-army-contract.mjs / test-kbli-*-contract.mjs).
  src = src.replace(/^export const meta/m, "const meta");

  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  let runner;
  try {
    runner = new AsyncFunction(
      "args",
      "agent",
      "log",
      "phase",
      "parallel",
      "pipeline",
      "budget",
      src,
    );
  } catch (e) {
    log(`failed to compile second-army.js: ${e.message}`);
    process.exitCode = 1;
    return;
  }

  const agentFn = dryRun ? makeDryRunAgent() : makeRealAgent();
  const parallelFn = makeParallel();

  let result;
  try {
    result = await runner(
      scriptArgs,
      agentFn,
      log,
      phase,
      parallelFn,
      pipeline,
      budget,
    );
  } catch (e) {
    log(`runner threw: ${e && e.stack ? e.stack : e}`);
    process.exitCode = 1;
    return;
  }

  process.stdout.write(JSON.stringify(result) + "\n");
  process.exitCode = 0;
}

main();
