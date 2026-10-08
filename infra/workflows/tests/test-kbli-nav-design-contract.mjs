// kbli-nav-design.js, run with stubbed DSL hooks: a path carrying shell metacharacters is refused before ANY
// agent() call (paths are interpolated into courier shells), and seat liveness is read fail-closed from
// seat_gate.py — no explicit "live <seat>" line means dead, and a dead seat is never dispatched.
import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const source = readFileSync(
  new URL("../kbli-nav-design.js", import.meta.url),
  "utf8",
);
const script = new AsyncFunction(
  "args",
  "agent",
  "parallel",
  "phase",
  "log",
  source.replace(/^export const meta/m, "const meta"),
);
const KIT = "/kits/kbli-nav";
const PREVIEW = "/previews/kbli-nav";
const ARGS = { kit: KIT, repo: "/repo", app: "/app", preview: PREVIEW };
const G = `gallery cleared ${PREVIEW}/mockups pngs=0`;
const TOOLS = [
  "content_pack.py",
  "seat_gate.py",
  "seat_io.py",
  "anti_flatness.py",
  "arena.py",
];

// Answers every courier command the way the real tools print on a clean run (used by the happy path only).
const ok = (slot, stage, seat) =>
  ["r1", "repair"].includes(stage)
    ? `${slot} ${stage} files=12 manifest=${"0".repeat(16)}`
    : `${stage} ${slot} by ${seat} kept=0 rejected=0`;
function clean(cmd) {
  const arg = (k) => (cmd.match(new RegExp(`--${k} (\\S+)`)) || [])[1];
  if (/content_pack\.py --verify/.test(cmd))
    return "3/3 byte-identical sha256=c29d6e6aea7a4fdb";
  if (/echo "present /.test(cmd))
    return `present ${cmd.match(/present ([^"\s]+)/)[1]}`;
  if (/anti_flatness\.py --controls/.test(cmd))
    return [
      "calib good contrast=PASS",
      "calib bad contrast=FAIL",
      "reference variety=PASS",
      "innocence variety=FAIL content=PASS",
      "guilt content=FAIL",
    ].join("\n");
  if (/anti_flatness\.py/.test(cmd))
    return arg("slots")
      .split(",")
      .map((s) => `${s} verdict=PASS fails=0`)
      .join("\n");
  if (/seat_io\.py (run|prepare)/.test(cmd)) {
    const granted = `granted ${arg("stage")}/${arg("slot")} 1/1 prompt=${"a".repeat(16)}`;
    return / run /.test(cmd)
      ? `${granted}\n${ok(arg("slot"), arg("stage"), arg("seat"))}`
      : granted;
  }
  if (/arena\.py/.test(cmd)) return `arena ${KIT}/arena.html sets=3`;
  return "";
}

async function simulate(args, gateOut, full = false, override = () => null) {
  const calls = [];
  const logs = [];
  const agent = async (prompt, opts = {}) => {
    calls.push({ prompt, label: opts.label, model: opts.model });
    if (opts.label === "seat gate")
      return {
        stdout: typeof gateOut === "function" ? gateOut(prompt) : gateOut,
      };
    if (full && opts.label === "nlm witness")
      return { stdout: "55203 nlm-vs-pack: agrees" };
    if (full && opts.model !== "haiku") {
      const m = prompt.match(
        /ingest --kit \S+ --slot (\w) --stage (\w+) --seat (\w+)/,
      );
      return { stdout: m ? ok(m[1], m[2], m[3]) : "" };
    }
    if (full)
      return {
        stdout: [...prompt.matchAll(/^\d+\. (.*)$/gm)]
          .map((m) => override(m[1]) ?? clean(m[1]))
          .join("\n"),
      };
    if (opts.label === "content pack + tools")
      return {
        stdout: [
          "3/3 byte-identical sha256=c29d6e6aea7a4fdb",
          ...TOOLS.map((t) => `present ${t}`),
        ].join("\n"),
      };
    return opts.schema ? { stdout: "" } : "";
  };
  const parallel = (thunks) =>
    Promise.all(thunks.map((t) => t().catch(() => null)));
  let error = null;
  let result = null;
  try {
    result = await script(
      args,
      agent,
      parallel,
      () => {},
      (m) => logs.push(m),
    );
  } catch (e) {
    error = e;
  }
  const dispatched = calls
    .flatMap((c) => [
      ...[...String(c.prompt).matchAll(/--seat (\w+)/g)].map((m) => m[1]),
      ...(c.model && c.model !== "haiku" ? [c.model] : []),
    ])
    .sort();
  return { calls, logs, error, dispatched, result };
}

test("a path with shell metacharacters is refused before any agent() call", async () => {
  for (const field of ["kit", "repo", "app", "preview"])
    for (const bad of [
      "/tmp/k;touch /tmp/pwned",
      "/tmp/$(id)",
      "/tmp/`id`",
      "/tmp/k && id",
      "/tmp/k\n",
      "relative/kit",
    ]) {
      const r = await simulate({ ...ARGS, [field]: bad }, "");
      assert.match(
        String(r.error),
        /must be plain absolute paths/,
        `${field}=${bad}`,
      );
      assert.equal(r.calls.length, 0, `${field}=${bad} reached a courier`);
    }
});

test("a refused or silent kit stops the run before any dispatch", async () => {
  for (const out of [
    `${G}\nrefused: kit ${KIT} does not exist`,
    `gallery cleared ${PREVIEW}/mockups pngs=2\nkit ok ${KIT}\nlive codex\nlive agy`,
    `kit ok ${KIT}\nlive codex\nlive agy`,
    "",
  ]) {
    const r = await simulate(ARGS, out);
    assert.match(String(r.error), /refused before any dispatch/);
    assert.deepEqual(
      r.calls.map((c) => c.label),
      ["seat gate"],
    );
  }
});

test("no report, a stale report or missing seat lines read every external seat dead", async () => {
  for (const out of [
    `${G}\nkit ok ${KIT}\ndead codex: no arsenal report (NEVER_RAN)\ndead agy: no arsenal report (NEVER_RAN)\ndead nlm: no arsenal report (NEVER_RAN)`,
    `${G}\nkit ok ${KIT}\ndead codex: arsenal report is 13.0h old, bound 12h\ndead agy: arsenal report is 13.0h old, bound 12h`,
    `${G}\nkit ok ${KIT}`,
    `${G}\nkit ok ${KIT}\n{"findings": []}`,
  ]) {
    const r = await simulate(ARGS, out);
    assert.match(String(r.error), /no non-Anthropic family live/);
    assert.deepEqual(r.dispatched, []);
  }
});

test("a seat without a live line is never dispatched; the live ones are", async () => {
  const r = await simulate(
    ARGS,
    `${G}\nkit ok ${KIT}\nlive codex\ndead agy: no row in the arsenal report\nlive nlm`,
  );
  assert.ok(
    r.logs.includes("dead agy: no row in the arsenal report"),
    r.logs.join("\n"),
  );
  assert.ok(
    r.logs.some((l) =>
      l.startsWith(
        'live {"sol":true,"gemini":false,"nlm":true} · builders a=sol b=none c=sonnet',
      ),
    ),
    r.logs.join("\n"),
  );
  // sol through its run courier, sonnet through its prepare courier (the stub grants nothing, so no lane follows)
  assert.deepEqual(r.dispatched, ["sol", "sonnet"]);
  assert.match(String(r.error), /no mockup set survived r1/);
});

test("a clean run with every seat live reaches the arena and hands it --preview", async () => {
  const r = await simulate(
    ARGS,
    `${G}\nkit ok ${KIT}\nlive codex\nlive agy\nlive nlm`,
    true,
  );
  assert.equal(r.error, null, String(r.error));
  const arena = r.calls.find((c) => c.label === "arena");
  assert.match(
    arena.prompt,
    new RegExp(
      `^1\\. python3 -I /repo/scripts/kbli_design/arena\\.py --kit ${KIT} --preview ${PREVIEW}$`,
      "m",
    ),
  );
  assert.equal(r.result.arena, `${KIT}/arena.html`);
  // args.preview is the gallery ROOT: arena.py appends mockups/<letter>/, where build_preview.py looks
  assert.equal(r.result.gallery, `${PREVIEW}/mockups`);
  assert.deepEqual([...new Set(r.dispatched)].sort(), [
    "gemini",
    "opus",
    "sol",
    "sonnet",
  ]);
});

test("a run whose arena refuses leaves the gallery's mockups/ empty (the real seat_gate.py clears it first)", async () => {
  const base = /^\/[A-Za-z0-9._\/-]+$/.test(tmpdir()) ? tmpdir() : "/tmp";
  const root = mkdtempSync(join(base, "kbli-nav-"));
  const kit = join(root, "kit");
  const preview = join(root, "preview");
  mkdirSync(kit);
  mkdirSync(join(preview, "mockups", "A"), { recursive: true });
  writeFileSync(join(preview, "mockups", "A", "chat-day.png"), "old run");
  const repo = new URL("../../..", import.meta.url).pathname.replace(/\/$/, "");
  // the courier runs the real seat_gate.py command; CI has no arsenal report, so the seat lines are stubbed
  const gate = (prompt) => {
    const cmd = prompt.match(/^1\. (.*)$/m)[1];
    const real = execSync(cmd, { encoding: "utf8" }).split("\n");
    return [
      ...real.filter((l) => /^(gallery|kit) /.test(l)),
      "live codex",
      "live agy",
      "live nlm",
    ].join("\n");
  };
  const r = await simulate(
    { ...ARGS, kit, repo, preview },
    gate,
    true,
    (cmd) =>
      /arena\.py --kit/.test(cmd)
        ? "refused: no set has both a grader and a refuter VERDICT; nothing reaches the arena"
        : null,
  );
  assert.match(String(r.error), /arena not written/);
  assert.ok(existsSync(join(preview, "mockups")));
  assert.deepEqual(
    readdirSync(join(preview, "mockups"), { recursive: true }),
    [],
  );
});
