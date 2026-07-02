// modus-bench.js — the self-refinement sweep for the modus master loop.
//
// "Il workflow potrà affinarsi e migliorarsi autonomamente grazie alle nuove scoperte ed
// esperienze sia nel nostro sistema e sia nei lavori dei sistemi nel mondo." (Zero, 2026-07-02)
//
// TERMINOLOGY (same honesty as verify-template.js): this is self-HEALING / self-REFINEMENT of an
// operating procedure — NOT recursive self-improvement of a model. The output is OPERATOR-GATED:
// this workflow proposes amendments; it never edits .claude/skills/modus/SKILL.md itself (Legge 5).
//
// WHAT IT DOES: two evidence lanes swept in parallel —
//   INTERNAL: scars + superscar families + modus AMENDMENTS/PENDING-ARMS of the last N days
//             ("which recent traumas would the current loop NOT have prevented?")
//   EXTERNAL: frontier watch — Claude Code releases, Anthropic engineering, new frontier models
//             ("which new capability should the loop exploit? which rule did the world obsolete?")
// then every raw proposal faces an adversarial refuter on fresh context (generator ≠ grader,
// verify-on-disk), and survivors are synthesized into an AMENDMENTS.md-ready block.
//
// HOW TO RUN (on demand, ~monthly, or after a major harness/model release):
//   Workflow({ scriptPath: "infra/workflows/modus-bench.js",
//              args: { today: "YYYY-MM-DD", days: 30 } })   // today REQUIRED (no Date.now in scripts)
// The main loop appends the returned amendments_block to .claude/skills/modus/AMENDMENTS.md
// and surfaces it to the operator. Nothing merges without Zero's GO.

export const meta = {
  name: "modus-bench",
  description:
    "Self-refinement sweep for the modus master loop: internal scars/memory × external frontier watch → adversarially verified, operator-gated amendment proposals",
  whenToUse:
    "On demand (~monthly, or after a major Claude Code / frontier-model release). Never scheduled as a daemon — it runs when invoked.",
  phases: [
    {
      title: "Sweep",
      detail: "internal evidence + external frontier, in parallel",
    },
    {
      title: "Refute",
      detail: "one skeptic per proposal, fresh context, verify-on-disk",
    },
    {
      title: "Synthesize",
      detail: "AMENDMENTS.md-ready block, operator-gated",
    },
  ],
};

const today = (args && args.today) || "UNKNOWN-DATE";
const days = (args && args.days) || 30;

const PROPOSALS = {
  type: "object",
  required: ["proposals"],
  properties: {
    proposals: {
      type: "array",
      items: {
        type: "object",
        required: ["title", "evidence", "change"],
        properties: {
          title: { type: "string" },
          evidence: {
            type: "string",
            description: "verifiable on disk or via URL — path/date/quote",
          },
          change: {
            type: "string",
            description: "the exact edit to .claude/skills/modus/SKILL.md",
          },
          source: { type: "string" },
        },
      },
    },
  },
};
const VERDICT = {
  type: "object",
  required: ["refuted", "reason"],
  properties: { refuted: { type: "boolean" }, reason: { type: "string" } },
};

phase("Sweep");
const SWEEPS = [
  {
    key: "scars",
    prompt: `Read .claude/rules/cicatrix-superscar.md and the tail of .claude/rules/cicatrix-scars.md (last ~${days} days of entries), then read .claude/skills/modus/SKILL.md. Question: which recent scars would the CURRENT modus loop NOT have prevented — which stage or probe was missing or too weak? Propose only changes anchored to a specific scar.`,
  },
  {
    key: "loop-misfires",
    prompt: `Read .claude/skills/modus/AMENDMENTS.md and .claude/skills/modus/PENDING-ARMS.md. Which recorded misfires or stuck arms reveal a structural weakness in .claude/skills/modus/SKILL.md (read it)? Propose the structural fix, not a restatement of the entry.`,
  },
  {
    key: "frontier-harness",
    prompt: `Web-search the Claude Code changelog/release notes and Anthropic engineering posts from the last ${days} days. Read .claude/skills/modus/SKILL.md. Which NEW harness capability (tools, hooks, workflows, memory, models) should the loop exploit, and which of its current rules did the harness obsolete? Only propose changes with a citable release/post.`,
  },
  {
    key: "frontier-models",
    prompt: `Web-search frontier model releases (Anthropic, OpenAI, Google, DeepSeek, Zhipu) from the last ${days} days. Read the arsenal routing table in .claude/skills/modus/SKILL.md. Does any seat need re-routing (better/cheaper/deprecated model)? Remember the lesson this loop was born from: opus-mythos aged the day Fable returned — model-generation events are exactly what this sweep exists to catch.`,
  },
];
const raw = (
  await parallel(
    SWEEPS.map(
      (s) => () =>
        agent(
          `${s.prompt}\nReturn ONLY proposals with concrete, verifiable evidence. No speculation, no style preferences.`,
          { label: `sweep:${s.key}`, phase: "Sweep", schema: PROPOSALS },
        ),
    ),
  )
)
  .filter(Boolean)
  .flatMap((r) => r.proposals || []);
log(`${raw.length} raw proposals from ${SWEEPS.length} sweeps`);
if (!raw.length)
  return {
    date: today,
    raw: 0,
    survived: 0,
    amendments_block: `## bench ${today} — no amendment pressure found (${SWEEPS.length} sweeps, ${days}d window)`,
  };

phase("Refute");
const judged = await parallel(
  raw.map(
    (p) => () =>
      agent(
        `Adversarially refute this proposed amendment to the modus master-loop skill (.claude/skills/modus/SKILL.md — read it first). Verify its evidence ON DISK or at the cited URL yourself; a claim you cannot re-verify is refuted by default. Also refute if the change adds ceremony without a failure mode it demonstrably prevents. Default refuted=true when uncertain.\n\nPROPOSAL:\n${JSON.stringify(p, null, 2)}`,
        {
          label: `refute:${(p.title || "?").slice(0, 40)}`,
          phase: "Refute",
          schema: VERDICT,
        },
      ).then((v) => ({ ...p, verdict: v })),
  ),
);
const survived = judged
  .filter(Boolean)
  .filter((p) => p.verdict && p.verdict.refuted === false);
log(`${survived.length}/${raw.length} proposals survived refutation`);

phase("Synthesize");
const amendments_block = await agent(
  `Synthesize OPERATOR-GATED amendment proposals for the modus master loop. Date: ${today}. These proposals survived adversarial refutation:\n${JSON.stringify(survived, null, 2)}\n\nProduce a markdown section ready to APPEND to .claude/skills/modus/AMENDMENTS.md:\n- header line: "## bench ${today}"\n- one checkbox line per proposal: "- [ ] <title> — <evidence, 1 line> — CHANGE: <exact edit>"\n- close with the reminder line that nothing merges without Zero's GO.\nDo NOT edit any file. Return the markdown only.`,
  { label: "synthesize", phase: "Synthesize" },
);
return {
  date: today,
  raw: raw.length,
  survived: survived.length,
  amendments_block,
};
