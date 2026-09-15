// second-army.js — the Gear <= 2 "second army" doctrine, made executable
// (docs/architecture/dual-consul/army-map.md §1ter).
//
// DIRECTION OF VERIFICATION — RULED by Zero 2026-09-15, and it is the opposite of the
// "cheap verifier" instinct: the INFERIOR seats BUILD, the Dux SPAWNS them and VERIFIES on
// disk. A weaker seat never grades a stronger one. Builders come from a family != the Dux's
// wherever the task allows (W100); Haiku under a Sonnet Dux is legal for Anthropic-native
// grunt ONLY, and only after every cross-family door has probed dead. Builder != verifier
// always (generator != grader). At floor 2 exactly ONE cheap cross-family refuter reads the
// FROZEN diff after push — one seat, never a council (FLUIDITÀ addendum).
//
// A Gear-3-floor mission belongs to the champions' chain of §1 (Generals/Dux/gate/release-
// owner) — this script is for everything BELOW that floor.
//
// Harness facts (verified by the Dux 2026-09-15): no filesystem/Node API here — a durable
// artifact is written by an agent() lane that owns Write, never by this script directly.
// Date.now()/new Date()/Math.random() THROW inside a Workflow script — every timestamp arrives
// through args.stamp. agent() returns null when a lane dies; every result is null-checked.
//
// HOW TO RUN:
//   Workflow({ scriptPath: "infra/workflows/second-army.js", args: {
//     mission: "…", colour: "blue" | "orange", floor: 1,
//     tasks: [ { key: "t1", prompt: "…", files: ["…"], proof: "…" } ],
//     outDir: "research/operations", stamp: "20260915T120000Z",
//     frozenRef: "origin/agent/<host>/<lane>/…",   // floor 2 only: the PUSHED ref the refuter reads
//   }})
// Returns { mission, colour, floor, promoted, built, verified, refuted, refuter, deadTiers, reportPath }.

export const meta = {
  name: "second-army",
  description:
    "Gear<=2 second-army doctrine: probe live doors, BUILD with an inferior cross-family seat, VERIFY on disk from the Dux lane, refute once at floor 2, report to disk",
  whenToUse:
    "A BLUE or ORANGE mission below Gear-3 floor whose slices can be built by an inferior seat and verified on disk by the Dux — never for a Gear-3-floor mission (those PROMOTE to the champions' chain instead of running here).",
  phases: [
    {
      title: "Eligibility",
      detail: "floor>=3 promotes to the champions' chain, no build/verify runs",
    },
    {
      title: "Probe",
      detail:
        "one live 1-token probe per bash-door seat in play; native seats are their own probe",
    },
    {
      title: "Build",
      detail:
        "the first LIVE inferior cross-family seat does the task, driven from a haiku grunt lane",
    },
    {
      title: "Verify",
      detail:
        "the DUX lane re-derives the proof on disk — never shown the builder's claim",
    },
    {
      title: "Refute",
      detail:
        "floor 2 only: ONE cheap cross-family seat reads the frozen diff after push",
    },
    {
      title: "Report",
      detail: "one Write-capable lane persists the run report to outDir",
    },
  ],
};

// ----- pure-literal constants (text-sliced by the contract test — do not add interpolation) --

const SEAT_FAMILY = {
  sonnet: "anthropic",
  haiku: "anthropic",
  terra: "openai",
  luna: "openai",
  spark: "openai",
  flash: "google",
  "deepseek-flash": "deepseek",
  "qwen-plus": "alibaba",
  ollama: "local",
};

const SEAT_DOOR = {
  sonnet: { kind: "native", model: "sonnet" },
  haiku: { kind: "native", model: "haiku" },
  terra: {
    kind: "bash",
    command:
      "codex exec -m gpt-5.6-terra --sandbox read-only --skip-git-repo-check",
    probe:
      'codex exec -m gpt-5.6-terra --sandbox read-only --skip-git-repo-check "reply pong" < /dev/null',
  },
  luna: {
    kind: "bash",
    command:
      "codex exec -m gpt-5.6-luna --sandbox workspace-write --skip-git-repo-check",
    probe:
      'codex exec -m gpt-5.6-luna --sandbox read-only --skip-git-repo-check "reply pong" < /dev/null',
  },
  spark: {
    kind: "bash",
    command:
      "codex exec -m gpt-5.3-codex-spark --sandbox workspace-write --skip-git-repo-check",
    probe:
      'codex exec -m gpt-5.3-codex-spark --sandbox read-only --skip-git-repo-check "reply pong" < /dev/null',
  },
  flash: {
    kind: "bash",
    command: "agy -p",
    probe: 'agy -p "reply pong" --print-timeout 4m',
    model: "gemini-3.8-flash-low",
  },
  "deepseek-flash": {
    kind: "bash",
    command: "python3 scripts/tp1_call.py --model deepseek-v4-flash-0731 -p",
    probe:
      'python3 scripts/tp1_call.py --model deepseek-v4-flash-0731 -p "reply pong"',
  },
  "qwen-plus": {
    kind: "bash",
    command: "python3 scripts/tp1_call.py --model qwen3.7-plus -p",
    probe: 'python3 scripts/tp1_call.py --model qwen3.7-plus -p "reply pong"',
  },
  ollama: {
    kind: "bash",
    command: "ollama run qwen3.5:9b",
    probe: 'ollama run qwen3.5:9b "reply pong"',
  },
};

// RULED 2026-09-15 — the builders are the INFERIOR seats; the Dux verifies them on disk.
// Roster order IS the fallthrough order: every cross-family door first, the Anthropic-native
// grunt seat LAST (and legal only under a Sonnet Dux, per HAIKU_GRUNT_SEAT below).
const CHAIN = {
  blue: {
    dux: "sonnet",
    builders: [
      "luna",
      "spark",
      "flash",
      "deepseek-flash",
      "qwen-plus",
      "haiku",
    ],
  },
  orange: {
    dux: "terra",
    builders: ["haiku", "flash", "deepseek-flash", "qwen-plus"],
  },
};

// The ONE seat allowed to build in the Dux's own family, and only as Anthropic-native grunt
// after every cross-family door has probed dead (army-map.md §1ter (b)).
const HAIKU_GRUNT_SEAT = "haiku";

// The lane model the DUX verification runs on. On ORANGE this sonnet lane is the harness-side
// driver only: it shells out to the Terra door so the Dux SEAT derives the verdict itself.
const DUX_LANE_MODEL = "sonnet";

// Floor-2 refuter: ONE cheap cross-family seat, whichever probes live first. Never a council.
const REFUTER_SEATS = ["spark", "flash"];
const REFUTER_FLOOR = 2;

const DEAD_TIERS_DECLARED = [
  "kimi",
  "qwen-cloud-code",
  "tp1-glm-5.2",
  "tp1-deepseek-v4-pro",
];

// ----- schemas -----------------------------------------------------------------------------

const PROBE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["alive", "evidence"],
  properties: {
    alive: { type: "boolean" },
    evidence: { type: "string" },
  },
};

const BUILD_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["claim", "filesTouched"],
  properties: {
    claim: {
      type: "string",
      description:
        "what the builder says it did — a CLAIM, never an observation",
    },
    filesTouched: {
      type: "string",
      description: "the files the builder says it changed",
    },
  },
};

const VERDICT_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["holds", "observation", "command"],
  properties: {
    holds: {
      type: "boolean",
      description:
        "true if the proof criterion HOLDS on disk, derived independently",
    },
    observation: {
      type: "string",
      description: "the concrete on-disk observation made THIS turn",
    },
    command: {
      type: "string",
      description: "the command actually run to make that observation",
    },
  },
};

const REFUTER_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["refuted", "reason"],
  properties: {
    refuted: {
      type: "boolean",
      description: "true if the frozen diff is wrong or unsafe",
    },
    reason: { type: "string" },
  },
};

// ----- input (args), with safe fallbacks ----------------------------------------------------

async function writeReport(reportPath, body) {
  await agent(
    `Using the Write tool, write the following markdown EXACTLY to the file path "${reportPath}" ` +
      "(create parent directories if needed), then confirm the write.\n\nCONTENT:\n\n" +
      body,
    { model: "haiku", label: "report", phase: "Report" },
  );
}

const A = (typeof args === "string" ? JSON.parse(args) : args) || {};
const MISSION = A.mission;
const FLOOR = A.floor;
const TASKS = Array.isArray(A.tasks) ? A.tasks : [];

phase("Eligibility");

let COLOUR = A.colour;
if (COLOUR !== "blue" && COLOUR !== "orange") {
  log(
    `colour ${JSON.stringify(A.colour)} missing/unrecognised — defaulting to "blue"`,
  );
  COLOUR = "blue";
}

let STAMP = A.stamp;
if (!STAMP) {
  log(
    'stamp missing — Date is unavailable inside a Workflow script, using literal "unstamped"',
  );
  STAMP = "unstamped";
}

let OUT_DIR = A.outDir;
if (!OUT_DIR) {
  log('outDir missing — defaulting to "research/operations"');
  OUT_DIR = "research/operations";
}

const declaredDeadTiers = DEAD_TIERS_DECLARED.map((seat) => ({
  seat,
  family: SEAT_FAMILY[seat] || "unknown",
  reason: "declared-quota-dead-2026-09-15",
}));

if (typeof FLOOR === "number" && FLOOR >= 3) {
  log(
    `floor ${FLOOR} >= 3 — mission ${MISSION} PROMOTED to the champions' chain of §1 ` +
      "(docs/architecture/dual-consul/army-map.md); no build, verify or refute lane runs here",
  );
  const reportPath = `${OUT_DIR}/second-army-${MISSION}-${STAMP}.md`;
  const promotedBody =
    `# second-army run — ${MISSION}\n\n` +
    `**PROMOTED** to the champions' chain of §1 at Gear-3 floor ${FLOOR}. Colour: ${COLOUR}.\n\n` +
    "This mission's floor requires the champions' chain (Generals/Dux/gate/release-owner), " +
    "not the second army — no build, verify or refute lane was launched on this path.\n\n" +
    `Declared-dead tiers (never probed, quota-dead 2026-09-15): ${declaredDeadTiers.map((d) => d.seat).join(", ")}.\n\n` +
    "## What a reader must check on disk\n" +
    `Confirm this report exists at the path above and that no build:/verify:/refute: lane ran for mission ${MISSION}.\n`;
  await writeReport(reportPath, promotedBody);
  return {
    mission: MISSION,
    colour: COLOUR,
    floor: FLOOR,
    promoted: true,
    built: [],
    verified: [],
    refuted: [],
    refuter: null,
    deadTiers: declaredDeadTiers,
    reportPath,
  };
}

const duxSeat = CHAIN[COLOUR].dux;
const duxFamily = SEAT_FAMILY[duxSeat];
const builderRoster = CHAIN[COLOUR].builders;
const runRefuter = FLOOR === REFUTER_FLOOR;

let FROZEN_REF = A.frozenRef;
if (runRefuter && !FROZEN_REF) {
  log(
    'floor 2 with no args.frozenRef — the refuter reads "HEAD"; it is the caller\'s duty to have PUSHED first',
  );
  FROZEN_REF = "HEAD";
}

// ----- Probe ----------------------------------------------------------------------------------

phase("Probe");
log(
  `declared-dead tiers (never probed, quota-dead 2026-09-15): ${DEAD_TIERS_DECLARED.join(", ")}`,
);
log(
  `dux ${duxSeat} (family ${duxFamily}) — it VERIFIES; the builder roster below BUILDS`,
);

const seatsInPlay = [duxSeat, ...builderRoster];
if (runRefuter) seatsInPlay.push(...REFUTER_SEATS);
const candidateSeats = [...new Set(seatsInPlay)];
const bashSeats = candidateSeats.filter(
  (s) => SEAT_DOOR[s] && SEAT_DOOR[s].kind === "bash",
);
const nativeSeats = candidateSeats.filter(
  (s) => SEAT_DOOR[s] && SEAT_DOOR[s].kind === "native",
);
if (nativeSeats.length) {
  log(
    `native seat(s) ${nativeSeats.join(", ")} are not probed — the harness itself is their probe`,
  );
}

const probeResults = await parallel(
  bashSeats.map((seat) => async () => {
    const door = SEAT_DOOR[seat];
    const result = await agent(
      `Run exactly this shell command via the Bash tool and report whether its stdout contains a ` +
        `live reply (not an error, not empty, not a timeout): \`${door.probe}\`. ` +
        "Return alive:true only if you observed a genuine reply; alive:false otherwise, with evidence " +
        "describing exactly what you saw (stdout/stderr/exit code).",
      {
        model: "haiku",
        label: `probe:${seat}`,
        phase: "Probe",
        schema: PROBE_SCHEMA,
      },
    );
    return { seat, result };
  }),
);

const probedDeadTiers = probeResults
  .filter(Boolean)
  .filter(({ result }) => !result || result.alive !== true)
  .map(({ seat, result }) => ({
    seat,
    family: SEAT_FAMILY[seat] || "unknown",
    reason: result ? "probe-reported-not-alive" : "probe-lane-died",
    evidence: result ? result.evidence : null,
  }));

const deadTiers = [...declaredDeadTiers, ...probedDeadTiers];
const isDead = (seat) => deadTiers.some((d) => d.seat === seat);

// The first LIVE builder in roster order. A seat of the Dux's OWN family is skipped outright
// unless it is the sanctioned Anthropic-native grunt seat — which sits last in the roster, so
// it is only ever reached after every cross-family door has probed dead.
function chooseBuilder() {
  for (const seat of builderRoster) {
    if (isDead(seat)) continue;
    if (SEAT_FAMILY[seat] === duxFamily && seat !== HAIKU_GRUNT_SEAT) {
      log(
        `builder ${seat} shares family ${duxFamily} with dux ${duxSeat} and is not the grunt seat — skipped`,
      );
      continue;
    }
    return seat;
  }
  return null;
}

// ----- Build / Verify (one pipeline, no barrier) -----------------------------------------------

const buildStage = async (_prev, t) => {
  const builderSeat = chooseBuilder();
  if (!builderSeat) {
    log(`no live builder left for task ${t.key} — every roster seat is dead`);
    return { key: t.key, builderSeat: null, claim: null };
  }
  if (SEAT_FAMILY[builderSeat] === duxFamily) {
    log(
      `builder ${builderSeat} is the Anthropic-native GRUNT fallback under dux ${duxSeat} — ` +
        "every cross-family door probed dead this run; declared, not hidden",
    );
  }
  const promptBody =
    `TASK: ${t.prompt}\nOWNED FILES: ${JSON.stringify(t.files)}\nPROOF CRITERION: ${t.proof}\n\n` +
    "Do the work. Report what you changed. You are the BUILDER: you do NOT grade your own work — " +
    "the Dux re-derives the proof on disk after you.";
  const door = SEAT_DOOR[builderSeat];
  const isNative = door.kind === "native";
  const prompt = isNative
    ? promptBody
    : `Shell out via the Bash tool to \`${door.command}\` carrying this task verbatim, let that seat do ` +
      `the work, then report its answer structurally.\n\n${promptBody}`;
  // Every build lane is driven from a model:"haiku" GRUNT lane: either haiku does the work
  // itself (it is the chosen builder), or haiku is only the shell that reaches the door.
  const claim = await agent(prompt, {
    model: "haiku",
    label: `build:${t.key}`,
    phase: "Build",
    schema: BUILD_SCHEMA,
  });
  if (!claim)
    return {
      key: t.key,
      builderSeat,
      family: SEAT_FAMILY[builderSeat],
      claim: null,
    };
  return { key: t.key, builderSeat, family: SEAT_FAMILY[builderSeat], claim };
};

const verifyStage = async (built, t) => {
  if (!built || !built.claim) {
    return {
      key: t.key,
      status: "refuted",
      reason:
        built && built.builderSeat
          ? "build-lane-died-no-claim"
          : "no-live-builder",
      built,
    };
  }
  // THE DUX VERIFIES. The prompt carries the task and the proof criterion only — never the
  // builder's claim (generator != grader, and a grader shown the answer stops deriving one).
  const duxDoor = SEAT_DOOR[duxSeat];
  const shellClause =
    duxDoor.kind === "bash"
      ? `You are the harness-side driver for the DUX seat: shell out via the Bash tool to \`${duxDoor.command}\` ` +
        "so that seat derives the verdict, and carry its answer back verbatim. "
      : "";
  const verdict = await agent(
    `${shellClause}Independently determine, ON DISK, whether this proof criterion holds. Derive your own ` +
      "answer THIS turn: run the proof command with Bash, read the files, read the diff. You have NOT " +
      "been told what anyone claims to have done, and you must not assume anything was built correctly.\n\n" +
      "DERIVE, NEVER REPAIR. You are the grader, not a second builder. Run only commands that OBSERVE — " +
      "reading, listing, hashing, diffing, running a read-only check. Never run a command that writes, " +
      "stamps, formats, installs, stages or reverts anything, even when the fix is obvious and even when " +
      "the proof command itself would write. If the criterion does not hold, return holds:false and say " +
      "what you saw — a grader that repairs the artefact has destroyed the measurement it was asked for.\n\n" +
      `TASK: ${t.prompt}\nOWNED FILES: ${JSON.stringify(t.files)}\nPROOF CRITERION: ${t.proof}\n\n` +
      "Return holds:true only if you OBSERVED the criterion holding, with the command you ran and what it printed.",
    {
      model: DUX_LANE_MODEL,
      label: `verify:${t.key}`,
      phase: "Verify",
      schema: VERDICT_SCHEMA,
    },
  );
  if (!verdict) {
    return { key: t.key, status: "refuted", reason: "verify-lane-died", built };
  }
  if (!verdict.holds) {
    return {
      key: t.key,
      status: "refuted",
      reason: "dux-verification-failed-on-disk",
      evidence: `${verdict.command} -> ${verdict.observation}`,
      built,
    };
  }
  return {
    key: t.key,
    status: "verified",
    verifier: duxSeat,
    family: duxFamily,
    verdict,
    built,
  };
};

phase("Build");
phase("Verify");
const stageResults = (await pipeline(TASKS, buildStage, verifyStage)).filter(
  Boolean,
);

const built = stageResults
  .filter((r) => r.built && r.built.claim)
  .map((r) => ({
    key: r.key,
    seat: r.built.builderSeat,
    family: r.built.family,
    claim: r.built.claim,
  }));
const verified = stageResults
  .filter((r) => r.status === "verified")
  .map((r) => ({
    key: r.key,
    verifier: r.verifier,
    family: r.family,
    verdict: r.verdict,
  }));
const refuted = stageResults
  .filter((r) => r.status === "refuted")
  .map((r) => ({ key: r.key, reason: r.reason, evidence: r.evidence || null }));

// ----- Refute (floor 2 only) --------------------------------------------------------------------

let refuter = null;
if (runRefuter) {
  phase("Refute");
  const refuterSeat = REFUTER_SEATS.find(
    (s) => !isDead(s) && SEAT_FAMILY[s] !== duxFamily,
  );
  if (!refuterSeat) {
    log(
      "floor 2 but no live cross-family refuter seat — DECLARED, the Dux owes the refutation itself",
    );
    refuter = {
      seat: null,
      reason: "no-live-cross-family-refuter",
      refuted: null,
    };
  } else {
    const door = SEAT_DOOR[refuterSeat];
    const verdict = await agent(
      `Shell out via the Bash tool to \`${door.command}\` carrying this review request, then report the ` +
        "seat's answer structurally. The diff is FROZEN — you read it, you never edit it.\n\n" +
        `Run \`git diff origin/main...${FROZEN_REF}\` and try to REFUTE that change: name a concrete way it ` +
        "is wrong, unsafe, or does not do what its own commit message says. If you cannot refute it, say so.",
      {
        model: "haiku",
        label: `refute:${MISSION}`,
        phase: "Refute",
        schema: REFUTER_SCHEMA,
      },
    );
    refuter = verdict
      ? {
          seat: refuterSeat,
          family: SEAT_FAMILY[refuterSeat],
          ref: FROZEN_REF,
          refuted: verdict.refuted,
          reason: verdict.reason,
        }
      : {
          seat: refuterSeat,
          ref: FROZEN_REF,
          refuted: null,
          reason: "refuter-lane-died",
        };
  }
}

// ----- Report -----------------------------------------------------------------------------------

phase("Report");

const duxDoorIsBash = SEAT_DOOR[duxSeat] && SEAT_DOOR[duxSeat].kind === "bash";
const rosterLines = [
  `- dux (VERIFIES on disk): ${duxSeat} (family ${duxFamily}, lane model ${DUX_LANE_MODEL}${duxDoorIsBash ? " shelling to the dux door" : ""})`,
  `- builder roster (BUILDS, in fallthrough order): ${builderRoster.map((s) => `${s} (${SEAT_FAMILY[s]})`).join(", ")}`,
  `- anthropic-native grunt seat, legal last only: ${HAIKU_GRUNT_SEAT}`,
  runRefuter
    ? `- floor-2 refuter candidates: ${REFUTER_SEATS.join(", ")} (one seat, on the frozen ref ${FROZEN_REF})`
    : "- floor-2 refuter: not applicable at this floor",
];

const probeLines = probeResults.length
  ? probeResults.map(
      ({ seat, result }) =>
        `- ${seat}: ${result ? (result.alive ? "alive" : "not alive") : "lane died"} — ${result ? result.evidence : "no evidence (lane returned null)"}`,
    )
  : ["- (no bash-door seats in play for this colour)"];
const deadLines = deadTiers.map(
  (d) =>
    `- ${d.seat} (${d.family}): ${d.reason}${d.evidence ? " — " + d.evidence : ""}`,
);
const taskLines = stageResults.map((r) => {
  const seatText =
    r.built && r.built.builderSeat
      ? `${r.built.builderSeat} (${r.built.family})`
      : "(none — no live builder)";
  const claimText =
    r.built && r.built.claim
      ? r.built.claim.claim
      : "(no claim — build failed)";
  const verdictText =
    r.status === "verified"
      ? `VERIFIED by the dux ${r.verifier} on disk: \`${r.verdict.command}\` -> ${r.verdict.observation}`
      : `NOT verified: ${r.reason}${r.evidence ? " — " + r.evidence : ""}`;
  return `### ${r.key}\n- builder seat: ${seatText}\n- builder claim (NOT evidence): ${claimText}\n- dux verdict: ${verdictText}`;
});
const refuterLines = refuter
  ? [
      `- seat: ${refuter.seat || "(none live)"}`,
      `- frozen ref: ${refuter.ref || "(n/a)"}`,
      `- refuted: ${refuter.refuted === null ? "unknown" : refuter.refuted}`,
      `- reason: ${refuter.reason}`,
    ]
  : ["- not run (this floor does not carry a refuter)"];

const reportPath = `${OUT_DIR}/second-army-${MISSION}-${STAMP}.md`;
const reportBody =
  "# second-army run report\n\n" +
  `- mission: ${MISSION}\n- colour: ${COLOUR}\n- floor: ${FLOOR}\n- promoted: false\n- stamp: ${STAMP}\n\n` +
  "## Direction of verification (RULED 2026-09-15)\n" +
  "The inferior seats BUILD; the Dux VERIFIES on disk. A builder never grades its own output, and " +
  "the Dux lane is never shown a builder's claim before deriving its own answer.\n\n" +
  "## Chain used\n" +
  rosterLines.join("\n") +
  "\n\n## Probe results\n" +
  probeLines.join("\n") +
  "\n\n## Dead tiers\n" +
  deadLines.join("\n") +
  "\n\n## Tasks\n" +
  taskLines.join("\n\n") +
  "\n\n## Floor-2 cross-family refuter\n" +
  refuterLines.join("\n") +
  "\n\n## What a reader must check on disk\n" +
  `Confirm this file exists at the path above, that every owned file listed per task exists with the ` +
  `claimed content, and that every VERIFIED verdict above names a command the dux (${duxSeat}) actually ran ` +
  `— the builder's claim is never the evidence.\n`;

await writeReport(reportPath, reportBody);

return {
  mission: MISSION,
  colour: COLOUR,
  floor: FLOOR,
  promoted: false,
  built,
  verified,
  refuted,
  refuter,
  deadTiers,
  reportPath,
};
