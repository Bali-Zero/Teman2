// kbli-nav-design.js — Track A of docs/plans/2026-10-08-kbli-navigator-design-loop.md, the formation Zero
// picked in ~/BATTAGLIA-20261008/DYNAMIC-WORKFLOW-kbli-nav-design/Z-DECISIONI.md: fable-5-1's skeleton +
// astra's first move, Opus+NotebookLM independent verification, ONE bounded repair + retest, and the
// substitute rule "Sol dead -> Gemini becomes mandatory grader and never builds".
//
// It ends at the ARENA: the vote is Zero's, and synthesis -> SwiftUI spec -> build is a second script.
// The DSL has no filesystem, so every command runs in a haiku shell-courier lane whose stdout is the
// evidence; every phase gate is a PRINTED LINE compared here, never an exit code (DECISION.md).
// External seats (codex Sol, agy Gemini) run as one-shots from an empty temp dir with stdin closed and
// the material inlined (F5/F6) — scripts/kbli_design/seat_io.py does that; Anthropic seats are agent()
// lanes, i.e. the claude CLI on OAuth (C1). The kit lives outside the repo, so no mockup enters a PR (C3);
// create it before the run — seat_gate.py refuses a kit that does not exist.
//
//   Workflow({ scriptPath: "infra/workflows/kbli-nav-design.js", args: {
//     kit: "<absolute kit dir, outside the repo>", repo: "<absolute repo checkout>",
//     app: "<absolute app repo, default ~/kbli-navigator-app>", nlmNotebook: "KBLI",
//     preview: "<absolute gallery dir, e.g. ~/BATTAGLIA-<date>/PREVIEW-kbli-nav-design>" }})

export const meta = {
  name: "kbli-nav-design",
  description:
    "KBLI Navigator sealed design contest: content pack, three sealed mockup sets, calibrated probes, Opus+NotebookLM verification, one bounded repair, cross-family fact refutation, blind arena; stops before Zero's vote",
  whenToUse:
    "Track A of the 2026-10-08 KBLI Navigator design loop, after content_pack.py, seat_io.py, anti_flatness.py and arena.py exist on the checkout passed as args.repo.",
  phases: [
    {
      title: "Arsenal",
      detail:
        "kit + fail-closed seat liveness from seat_gate.py (arsenal last.json)",
    },
    {
      title: "Content pack",
      detail:
        "content_pack.py --verify must print the 3/3 line; tools present; prompt sealed",
    },
    {
      title: "Sealed mockups",
      detail: "three sets in parallel, round cap 1, counters on disk",
    },
    { title: "Probes", detail: "controls first, then anti_flatness per set" },
    {
      title: "Independent verification",
      detail: "cross-family grader per set + NotebookLM source-only witness",
    },
    {
      title: "Bounded repair",
      detail: "one repair per failing set, then the same probes",
    },
    {
      title: "Fact refutation",
      detail:
        "Sol refutes B and C, Gemini refutes A; objections only with Test:",
    },
    { title: "Arena", detail: "arena.html + mapping.json 0600, then STOP" },
  ],
};

const A = (typeof args === "string" ? JSON.parse(args) : args) || {};
const KIT = A.kit,
  REPO = A.repo,
  APP = A.app || "/Users/balizero/kbli-navigator-app",
  PREVIEW = A.preview;
// Paths are interpolated into courier shell commands, so anything beyond a plain absolute path is refused.
if (
  ![KIT, REPO, APP, PREVIEW].every(
    (p) => typeof p === "string" && /^\/[A-Za-z0-9._\/-]+$/.test(p),
  )
) {
  throw new Error(
    "kbli-nav-design: args.kit, args.repo, args.preview (and args.app) must be plain absolute paths [A-Za-z0-9._/-]",
  );
}
const NLM = String(A.nlmNotebook || "KBLI").replace(/[^A-Za-z0-9 ._-]/g, "");
const R1_ROUNDS = 1,
  REPAIR_ROUNDS = 1,
  R2_ROUNDS = 1;
const VERIFY_LINE = "3/3 byte-identical sha256=c29d6e6aea7a4fdb";
const CONTROL_LINES = [
  "calib good contrast=PASS",
  "calib bad contrast=FAIL",
  "reference variety=PASS",
  "innocence variety=FAIL content=PASS",
  "guilt content=FAIL",
];
const TOOLS = [
  "content_pack.py",
  "seat_gate.py",
  "seat_io.py",
  "anti_flatness.py",
  "arena.py",
];
const FAMILY = {
  sol: "openai",
  gemini: "google",
  sonnet: "anthropic",
  opus: "anthropic",
};
const PY = `python3 -I ${REPO}/scripts/kbli_design`;
const OUT = {
  type: "object",
  properties: { stdout: { type: "string" } },
  required: ["stdout"],
};
const lines = (s) =>
  String(s || "")
    .split("\n")
    .map((l) => l.trim());
const find = (s, re) => lines(s).find((l) => re.test(l));
const rounds = {};
const take = (key, cap) => {
  rounds[key] = (rounds[key] || 0) + 1;
  if (rounds[key] > cap)
    throw new Error(`round cap: ${key} would be ${rounds[key]}/${cap} (C7)`);
};
const crossFamily = (author, grader) => {
  if (!grader || FAMILY[author] === FAMILY[grader])
    throw new Error(`C6 cannot hold: ${author} graded by ${grader}`);
  return grader;
};

async function sh(label, ph, cmds) {
  const r = await agent(
    `You are a shell courier. With the Bash tool (timeout 600000 ms, cwd ${REPO}) run each command below in order, ` +
      "copied byte for byte: add no flag, fix nothing, skip none, keep going if one fails. Return in `stdout` the " +
      'verbatim stdout+stderr of every command in order, each preceded by a line "$ <command>". Never summarise.\n\n' +
      cmds.map((c, i) => `${i + 1}. ${c}`).join("\n"),
    { model: "haiku", effort: "low", label: label, phase: ph, schema: OUT },
  );
  return r ? r.stdout : "";
}

// One seat, one stage. seat_io.py checks the on-disk round counter (a restart cannot buy a second round),
// assembles kit/prompts/<stage>-<slot>.md (the same bytes whichever seat answers), and for codex/agy launches
// the one-shot detached; this polls it with a literal cap. A native Anthropic seat reads that same file.
async function seat(slot, seatName, stage, ph) {
  const out = [];
  if (seatName === "sol" || seatName === "gemini") {
    out.push(
      await sh(`${stage} ${slot} via ${seatName}`, ph, [
        `${PY}/seat_io.py run --kit ${KIT} --slot ${slot} --seat ${seatName} --stage ${stage} --detach`,
      ]),
    );
    for (
      let i = 0;
      i < 6 && lines(out[out.length - 1]).includes("pending");
      i++
    ) {
      out.push(
        await sh(`wait ${stage} ${slot} #${i + 1}`, ph, [
          `${PY}/seat_io.py wait --kit ${KIT} --slot ${slot} --stage ${stage} --max-s 570`,
        ]),
      );
    }
    return out.join("\n");
  }
  out.push(
    await sh(`prepare ${stage} ${slot}`, ph, [
      `${PY}/seat_io.py prepare --kit ${KIT} --slot ${slot} --stage ${stage} --seat ${seatName}`,
    ]),
  );
  if (
    !find(
      out[0],
      new RegExp(`^granted ${stage}/${slot} 1/1 prompt=[0-9a-f]{16}$`),
    )
  )
    return out.join("\n");
  const r = await agent(
    `Your whole brief is ${KIT}/prompts/${stage}-${slot}.md, the same bytes any other seat in this role receives. ` +
      "Read all of it (offset/limit until the end) and nothing else: no other kit file, no repository file, no web. " +
      `Follow it exactly. Write your complete answer with the Write tool to ${KIT}/raw/${stage}-${slot}.md (one file). ` +
      `Then run \`${PY}/seat_io.py ingest --kit ${KIT} --slot ${slot} --stage ${stage} --seat ${seatName}\` and return its stdout verbatim in \`stdout\`.`,
    {
      model: seatName,
      label: `${stage} ${slot} (${seatName})`,
      phase: ph,
      schema: OUT,
    },
  );
  out.push(r ? r.stdout : `${slot} ${stage} dead: lane returned nothing`);
  return out.join("\n");
}

phase("Arsenal");
// Fail-closed before any dispatch. FIRST seat_gate.py empties the previous run's gallery renders
// (<PREVIEW>/mockups/**/*.png), so a run refused anywhere later never leaves sets nobody read in front of the
// vote; then the kit must answer "kit ok", and a seat is live only on an explicit "live <seat>" line
// (no report, no row, a stale report or any other status is dead).
const ars = await sh("seat gate", "Arsenal", [
  `${PY}/seat_gate.py --kit ${KIT} --preview ${PREVIEW}`,
]);
if (!lines(ars).includes(`gallery cleared ${PREVIEW}/mockups pngs=0`))
  throw new Error(
    `refused before any dispatch: the previous gallery was not cleared\n${ars}`,
  );
if (!lines(ars).includes(`kit ok ${KIT}`))
  throw new Error(
    `refused before any dispatch: ${find(ars, /^refused:/) || "seat_gate.py printed no kit line"}\n${ars}`,
  );
const isLive = (s) => lines(ars).includes(`live ${s}`);
const live = {
  sol: isLive("codex"),
  gemini: isLive("agy"),
  nlm: isLive("nlm"),
};
lines(ars)
  .filter((l) => l.startsWith("dead "))
  .forEach((l) => log(l));
if (!live.sol && !live.gemini)
  throw new Error("suspended: no non-Anthropic family live, C6 cannot hold");
const SLOTS = [
  { slot: "a", builder: live.sol ? "sol" : "sonnet" },
  { slot: "b", builder: live.sol && live.gemini ? "gemini" : null },
  { slot: "c", builder: "sonnet" },
];
const declared = SLOTS.filter((s) => !s.builder).map(
  (s) =>
    `${s.slot}: ${live.gemini ? "Gemini is mandatory grader and never builds (Sol dead)" : "Gemini dead, not replaced (F8)"}`,
);
log(
  `live ${JSON.stringify(live)} · builders ${SLOTS.map((s) => `${s.slot}=${s.builder || "none"}`).join(" ")}`,
);

phase("Content pack");
const pack = await sh("content pack + tools", "Content pack", [
  `${PY}/content_pack.py --out ${KIT} --app ${APP}`,
  `${PY}/content_pack.py --verify --out ${KIT} --app ${APP}`,
  ...TOOLS.map(
    (t) =>
      `test -f ${REPO}/scripts/kbli_design/${t} && echo "present ${t}" || echo "absent ${t}"`,
  ),
]);
if (!lines(pack).includes(VERIFY_LINE))
  throw new Error(`phase 0: --verify did not print "${VERIFY_LINE}"\n${pack}`);
const absent = TOOLS.filter((t) => !lines(pack).includes(`present ${t}`));
if (absent.length)
  throw new Error(
    `phase 0: refusing, tools absent on ${REPO}: ${absent.join(", ")}`,
  );

phase("Sealed mockups");
const landed = (txt, slot, stage) =>
  find(txt, new RegExp(`^${slot} ${stage} files=\\d+ manifest=[0-9a-f]{16}$`));
const built = await parallel(
  SLOTS.filter((s) => s.builder).map((s) => async () => {
    take(`r1/${s.slot}`, R1_ROUNDS);
    const out = await seat(s.slot, s.builder, "r1", "Sealed mockups");
    const prompt = (
      find(out, /^granted r1\/\w 1\/1 prompt=[0-9a-f]{16}$/) || ""
    ).split("prompt=")[1];
    const ok = landed(out, s.slot, "r1");
    return ok
      ? { ...s, stage: "r1", prompt: prompt, manifest: ok }
      : { ...s, dead: lines(out).filter(Boolean).slice(-1)[0] || "no output" };
  }),
);
const sets = built.filter((s) => s && !s.dead);
built
  .filter((s) => s && s.dead)
  .forEach((s) =>
    declared.push(
      `${s.slot}: ${s.builder} dead at r1, not replaced (F8): ${s.dead}`,
    ),
  );
if (!sets.length)
  throw new Error(`no mockup set survived r1: ${declared.join(" | ")}`);
if (new Set(sets.map((s) => s.prompt)).size !== 1)
  throw new Error(
    `r1 prompts differ across seats: ${sets.map((s) => `${s.slot}=${s.prompt}`).join(" ")}`,
  );

phase("Probes");
const ctl = await sh("probe controls", "Probes", [
  `${PY}/anti_flatness.py --controls --kit ${KIT} --app ${APP}`,
]);
const silent = CONTROL_LINES.filter((c) => !lines(ctl).includes(c));
if (silent.length)
  throw new Error(
    `probe distrusted, controls did not print: ${silent.join(" | ")}\n${ctl}`,
  );
const probe = (xs, stage) =>
  sh(`probe ${stage}`, "Probes", [
    `${PY}/anti_flatness.py --kit ${KIT} --stage ${stage} --slots ${xs.map((s) => s.slot).join(",")}`,
  ]);
const fails = (txt, slot) =>
  Number(
    (
      find(txt, new RegExp(`^${slot} verdict=(PASS|FAIL) fails=\\d+$`)) ||
      "fails=NaN"
    ).split("fails=")[1],
  );
const p1 = await probe(sets, "r1");
sets.forEach((s) => {
  s.probeFails = fails(p1, s.slot);
});

phase("Independent verification");
const graderOf = (s) =>
  crossFamily(
    s.builder,
    FAMILY[s.builder] !== "anthropic" ? "opus" : live.sol ? "sol" : "gemini",
  );
const kept = (txt, stage, slot) =>
  Number(
    (
      find(
        txt,
        new RegExp(`^${stage} ${slot} by \\w+ kept=\\d+ rejected=\\d+$`),
      ) || "kept=NaN "
    )
      .split("kept=")[1]
      .split(" ")[0],
  );
const verified = await parallel([
  ...sets.map((s) => async () => {
    s.grader = graderOf(s);
    s.graderKept = kept(
      await seat(s.slot, s.grader, "grade", "Independent verification"),
      "grade",
      s.slot,
    );
    return s.graderKept;
  }),
  async () => {
    if (!live.nlm) {
      declared.push("nlm: witness dead, not replaced (F8)");
      return "nlm dead";
    }
    const r = await agent(
      `You are a source-only witness courier for NotebookLM: you relay, you never synthesise. Load the NotebookLM MCP tools with ToolSearch, pick with notebook_list the notebook whose id or title contains "${NLM}", and for each KBLI 2025 code 55203, 51101, 56101 ask exactly: "From the sources only: for KBLI 2025 code <code>, what is the foreign-ownership (PMA) status, the maximum foreign share, and the instrument and annex row that is the basis? Quote the source." Write the three answers VERBATIM with their citations to ${KIT}/verify/nlm.md, one heading per code. Then compare each answer with the verdict, cap and basis of that code in ${KIT}/content-pack.json and return three lines "<code> nlm-vs-pack: agrees|differs|silent — <the differing words>" in \`stdout\`.`,
      {
        model: "haiku",
        label: "nlm witness",
        phase: "Independent verification",
        schema: OUT,
      },
    );
    return r ? r.stdout : "nlm lane died";
  },
]);
const witness = verified[verified.length - 1];

phase("Bounded repair");
const toRepair = sets.filter(
  (s) => !(s.probeFails === 0 && s.graderKept === 0),
);
await parallel(
  toRepair.map((s) => async () => {
    take(`repair/${s.slot}`, REPAIR_ROUNDS);
    const ok = landed(
      await seat(s.slot, s.builder, "repair", "Bounded repair"),
      s.slot,
      "repair",
    );
    if (ok) {
      s.stage = "repair";
      s.repair = ok;
    } else s.repair = "repair dead, r1 stands";
  }),
);
const repaired = sets.filter((s) => s.stage === "repair");
const p2 = repaired.length ? await probe(repaired, "repair") : "";
repaired.forEach((s) => {
  s.retestFails = fails(p2, s.slot);
});
log(
  `repair: ${toRepair.length} attempted, ${repaired.length} landed; retest ${repaired.map((s) => `${s.slot}=${s.retestFails}`).join(" ")}`,
);

phase("Fact refutation");
const refuterOf = (s) =>
  crossFamily(
    s.builder,
    s.builder === "sol"
      ? live.gemini
        ? "gemini"
        : "sonnet"
      : live.sol
        ? "sol"
        : "gemini",
  );
await parallel(
  sets.map((s) => async () => {
    take(`refute/${s.slot}`, R2_ROUNDS);
    s.refuter = refuterOf(s);
    const out = await seat(s.slot, s.refuter, "refute", "Fact refutation");
    s.refutation =
      find(
        out,
        new RegExp(`^refute ${s.slot} by \\w+ kept=\\d+ rejected=\\d+$`),
      ) || `refuter ${s.refuter} returned no count`;
  }),
);

phase("Arena");
// --preview drops the renders where the gallery's build_preview.py collects them (PREVIEW/mockups/<letter>/).
const arena = await sh("arena", "Arena", [
  `${PY}/arena.py --kit ${KIT} --preview ${PREVIEW}`,
]);
const arenaLine = find(arena, /^arena \S+ sets=\d+$/);
if (!arenaLine) throw new Error(`arena not written:\n${arena}`);
log(
  `${arenaLine} — STOP: the vote is Zero's (Legge 5); nothing is built before it`,
);
return {
  arena: arenaLine.split(" ")[1],
  // arena.py writes <PREVIEW>/mockups/<letter>/<screen>.png, the folder build_preview.py scans
  gallery: `${PREVIEW}/mockups`,
  declared: declared,
  witness: witness,
  controls: CONTROL_LINES,
  rounds: rounds,
  sets: sets.map((s) => ({
    slot: s.slot,
    builder: s.builder,
    stage: s.stage,
    probeFails: s.probeFails,
    grader: s.grader,
    graderKept: s.graderKept,
    repair: s.repair || null,
    retestFails: s.retestFails ?? null,
    refuter: s.refuter,
    refutation: s.refutation,
  })),
};
