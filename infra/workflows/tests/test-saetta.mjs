import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const source = readFileSync(new URL("../saetta.js", import.meta.url), "utf8");
const run = new AsyncFunction(
  "args",
  "agent",
  "parallel",
  "phase",
  "log",
  source.replace(/^export const meta/m, "const meta"),
);
const sha = "a".repeat(40);
const target = { pr: 101, head: sha };
const tasks = [
  { key: "upstream", brief: "/repo/brief-a.md", scope: ["a/"], dependsOn: [] },
  {
    key: "consumer",
    brief: "/repo/brief-b.md",
    scope: ["b/"],
    dependsOn: ["upstream"],
  },
  {
    key: "independent",
    brief: "/repo/brief-c.md",
    scope: ["c/"],
    dependsOn: [],
  },
];
const config = {
  mission: "SAETTA-TEST",
  colour: "BLUE",
  repo: "/repo",
  outputDir: "/repo/output/test",
  maxParallel: 2,
  tasks,
};
const built = () => ({ status: "result", targets: [target] });
const gated = () => ({
  verdict: "PASS",
  targets: [target],
  posted: true,
  reasons: [],
  receipt: "/repo/gate.json",
});

async function simulate({
  patchGate = {},
  patchBuild = {},
  patchRelease = {},
  patchClose = {},
  fail = "",
  skipped = "",
  args = config,
  seat = async () => undefined,
} = {}) {
  const calls = [];
  let active = 0,
    peak = 0;
  const result = await run(
    args,
    async (prompt, options) => {
      calls.push(options.label);
      active++;
      peak = Math.max(peak, active);
      await Promise.resolve();
      active--;
      if (options.label === fail) throw new Error("seat unavailable");
      if (options.label === skipped) return null;
      const override = await seat(prompt, options);
      if (override !== undefined) return override;
      if (options.label === "dux:upstream")
        return { ...built(), ...patchBuild };
      if (options.label.startsWith("dux:")) return built();
      if (options.label === "gate:upstream")
        return { ...gated(), ...patchGate };
      if (options.label.startsWith("gate:")) return gated();
      if (options.label.startsWith("release:"))
        return {
          verdict: "PASS",
          targets: [target],
          merged: true,
          live_receipt: "/repo/live.json",
          ...(options.label === "release:upstream" ? patchRelease : {}),
        };
      if (options.label.startsWith("close:"))
        return {
          recorded: true,
          verdict: prompt.includes('"verdict":"BLOCK"') ? "BLOCK" : "PASS",
          receipt: "/repo/close.json",
          ...patchClose,
        };
      throw new Error(`unexpected ${options.label}`);
    },
    async (thunks) => Promise.all(thunks.map((fn) => fn().catch(() => null))),
    () => {},
    () => {},
  );
  return { result, calls, peak };
}

test("a valid exact-head PASS releases the consumer and closes once", async () => {
  const { result, calls, peak } = await simulate();
  assert.equal(result.verdict, "PASS");
  assert.ok(calls.indexOf("dux:consumer") > calls.indexOf("release:upstream"));
  assert.equal(calls.filter((x) => x.startsWith("close:")).length, 1);
  assert.ok(peak <= 2);
});

test("a signed unmerged gate hands the frozen target to the release owner", async () => {
  const { result, calls } = await simulate({ patchGate: { merged: false } });
  assert.equal(result.verdict, "PASS");
  assert.ok(calls.includes("release:upstream"));
  assert.ok(calls.indexOf("release:upstream") > calls.indexOf("gate:upstream"));
});

test("missing-gate CI recovery belongs to release before merge and consumers", async () => {
  let signed = false,
    ci = "missing-gate",
    reruns = 0,
    merged = false,
    live = false;
  const { result, calls } = await simulate({
    seat: async (prompt, options) => {
      if (options.label === "gate:upstream") {
        assert.ok(options.schema.required.includes("posted"));
        assert.ok(!options.schema.required.includes("merged"));
        assert.match(prompt, /Do not merge, re-arm, or rerun CI/);
        signed = true;
        return gated();
      }
      if (options.label === "release:upstream") {
        assert.equal(signed, true);
        assert.equal(merged, false);
        assert.equal(ci, "missing-gate");
        assert.ok(options.schema.required.includes("merged"));
        assert.match(prompt, /gh run rerun <original-run-id>/);
        assert.match(prompt, /at most ONE rerun per target/);
        assert.match(prompt, /same exact frozen head/);
        assert.match(prompt, /only failure was the absent gate verdict/);
        assert.match(prompt, /read back the matching posted PASS/);
        assert.match(prompt, /normal merge queue/);
        // The external release seat diagnoses the existing run before the one allowed rerun.
        reruns++;
        ci = "green";
        merged = true;
        live = true;
        return {
          verdict: "PASS",
          targets: [target],
          merged,
          live_receipt: "/repo/live.json",
        };
      }
      if (options.label === "dux:consumer") {
        assert.equal(ci, "green");
        assert.equal(merged, true);
        assert.equal(live, true);
      }
    },
  });
  assert.equal(result.verdict, "PASS");
  assert.equal(reruns, 1);
  assert.ok(calls.indexOf("dux:consumer") > calls.indexOf("release:upstream"));
});

for (const [name, patchGate] of Object.entries({
  block: { verdict: "BLOCK" },
  missingReceipt: { posted: false },
  staleHead: { targets: [{ pr: 101, head: "b".repeat(40) }] },
  otherPR: { targets: [{ pr: 102, head: sha }] },
  emptyTargets: { targets: [] },
  missingFile: { receipt: "" },
  nonBinary: { verdict: "PASS-WITH-CONDITIONS" },
}))
  test(`${name} blocks only its dependants and cannot close green`, async () => {
    const { result, calls } = await simulate({ patchGate });
    assert.equal(result.verdict, "BLOCK");
    assert.ok(!calls.includes("release:upstream"));
    assert.ok(!calls.includes("dux:consumer"));
    assert.ok(calls.includes("dux:independent"));
  });

for (const status of ["needs_input", "failed"])
  test(`Dux ${status} cannot trigger a gate or consumer`, async () => {
    const { result, calls } = await simulate({ patchBuild: { status } });
    assert.equal(result.verdict, "BLOCK");
    assert.ok(!calls.includes("gate:upstream"));
    assert.ok(!calls.includes("dux:consumer"));
  });

test("a thrown child failure remains visible although native parallel swallows throws", async () => {
  const { result, calls } = await simulate({ fail: "gate:upstream" });
  assert.equal(result.verdict, "BLOCK");
  assert.ok(!calls.includes("dux:consumer"));
  assert.ok(calls.includes("dux:independent"));
});

test("close failure is BLOCK even if all slices passed", async () => {
  assert.equal(
    (await simulate({ fail: "close:SAETTA-TEST" })).result.verdict,
    "BLOCK",
  );
});

test("failed prove-live keeps consumers closed even after an accepted gate", async () => {
  const { result, calls } = await simulate({ fail: "release:upstream" });
  assert.equal(result.verdict, "BLOCK");
  assert.ok(!calls.includes("dux:consumer"));
  assert.ok(calls.includes("dux:independent"));
});

for (const [name, patchRelease] of Object.entries({
  block: { verdict: "BLOCK" },
  staleHead: { targets: [{ pr: 101, head: "b".repeat(40) }] },
  otherPR: { targets: [{ pr: 102, head: sha }] },
  relativeReceipt: { live_receipt: "live.json" },
  unmerged: { merged: false },
  missingMerge: { merged: undefined },
  nonBooleanMerge: { merged: "true" },
}))
  test(`release ${name} cannot launch a dependent`, async () => {
    const { result, calls } = await simulate({ patchRelease });
    assert.equal(result.verdict, "BLOCK");
    assert.ok(!calls.includes("dux:consumer"));
    assert.ok(calls.includes("dux:independent"));
  });

test("close cannot upgrade a scheduler BLOCK by reporting PASS", async () => {
  const { result } = await simulate({
    patchGate: { verdict: "BLOCK" },
    patchClose: { verdict: "PASS" },
  });
  assert.equal(result.close.verdict, "PASS");
  assert.equal(result.verdict, "BLOCK");
});

for (const patchClose of [
  { recorded: false },
  { verdict: "BLOCK" },
  { receipt: "close.json" },
])
  test(`invalid close ${JSON.stringify(patchClose)} cannot report success`, async () => {
    assert.equal((await simulate({ patchClose })).result.verdict, "BLOCK");
  });

for (const stage of [
  "dux:upstream",
  "gate:upstream",
  "release:upstream",
  "close:SAETTA-TEST",
])
  test(`native null result at ${stage} stays BLOCK`, async () => {
    const { result, calls } = await simulate({ skipped: stage });
    assert.equal(result.verdict, "BLOCK");
    if (!stage.startsWith("close:")) assert.ok(!calls.includes("dux:consumer"));
    assert.ok(calls.includes("dux:independent"));
  });

test("capacity two is enforced with more than two initially ready slices", async () => {
  const extra = {
    key: "fourth",
    brief: "/repo/d.md",
    scope: ["d/"],
    dependsOn: [],
  };
  const { result, peak, calls } = await simulate({
    args: { ...config, tasks: [...tasks, extra] },
  });
  assert.equal(result.verdict, "PASS");
  assert.ok(calls.includes("dux:fourth"));
  assert.equal(peak, 2);
});

test("unordered overlapping directory scopes are rejected before any write", async () => {
  await assert.rejects(
    simulate({
      args: {
        ...config,
        tasks: [tasks[0], { ...tasks[2], scope: ["a/nested/file.py"] }],
      },
    }),
    /overlapping/,
  );
});

test("overlap is allowed only when dependencies serialize both scopes", async () => {
  const ordered = [
    tasks[0],
    { ...tasks[1], scope: ["a/file.py"] },
    { ...tasks[2], scope: ["a/"], dependsOn: ["consumer"] },
  ];
  assert.equal(
    (await simulate({ args: { ...config, tasks: ordered } })).result.verdict,
    "PASS",
  );
});

test("literal Next.js route brackets and braces are accepted without glob expansion", async () => {
  for (const scope of [
    "apps/mouth/src/app/(workspace)/clients/[id]/ClientDetailClient.tsx",
    "apps/mouth/src/app/[...slug]/page.tsx",
    "apps/example/{literal}/page.tsx",
  ]) {
    const args = { ...config, tasks: [{ ...tasks[0], scope: [scope] }] };
    assert.equal((await simulate({ args })).result.verdict, "PASS");
  }
});

for (const scope of [
  "apps/*/page.tsx",
  "apps/?/page.tsx",
  "apps/../private",
  "apps/./page.tsx",
  "apps//page.tsx",
  "apps/\tpage.tsx",
  "apps/\u007fpage.tsx",
])
  test(`unsafe scope ${JSON.stringify(scope)} is rejected before dispatch`, async () => {
    await assert.rejects(
      simulate({
        args: { ...config, tasks: [{ ...tasks[0], scope: [scope] }] },
      }),
      /invalid/,
    );
  });

test(
  "frozen Kita pilot manifest completes scheduler validation with mocked PASS seats",
  { skip: !process.env.SAETTA_PILOT_MANIFEST },
  async () => {
    const manifestPath = resolve(process.env.SAETTA_PILOT_MANIFEST);
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    assert.equal(manifest.mission, "KITA-TAX-LEADS");
    const args = {
      ...config,
      ...manifest,
      tasks: manifest.tasks.map((task) => ({
        ...task,
        brief: resolve(dirname(manifestPath), task.brief),
      })),
    };
    const { result, calls, peak } = await simulate({ args });
    assert.equal(result.verdict, "PASS");
    assert.equal(result.results.length, 4);
    assert.ok(peak <= 2);
    for (const task of manifest.tasks)
      for (const dep of task.dependsOn)
        assert.ok(
          calls.indexOf(`dux:${task.key}`) > calls.indexOf(`release:${dep}`),
        );
  },
);

test("valid task names never collide with object prototypes", async () => {
  assert.equal(
    (
      await simulate({
        args: { ...config, tasks: [{ ...tasks[0], key: "constructor" }] },
      })
    ).result.verdict,
    "PASS",
  );
});

for (const [name, changes] of Object.entries({
  cycle: { tasks: [{ ...tasks[0], dependsOn: ["consumer"] }, tasks[1]] },
  unknown: { tasks: [{ ...tasks[0], dependsOn: ["absent"] }] },
  duplicate: { tasks: [tasks[0], tasks[0]] },
  colour: { colour: "ORANGE" },
  relative: { repo: "repo" },
  fanout: { maxParallel: 4 },
  empty: { tasks: [] },
}))
  test(`rejects ${name} before dispatch`, async () => {
    await assert.rejects(simulate({ args: { ...config, ...changes } }));
  });

test("same runner accepts host-resolved paths and serialized native args", async () => {
  for (const home of ["/Users/balizero", "/Users/nuzantara"]) {
    const args = {
      ...config,
      repo: `${home}/nuzantara`,
      outputDir: `${home}/out`,
    };
    assert.equal(
      (await simulate({ args: JSON.stringify(args) })).result.verdict,
      "PASS",
    );
  }
});
