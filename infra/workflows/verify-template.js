// verify-template.js — the generator≠grader workflow, promoted to a reusable repo artifact.
//
// Self-loop plan Anello 4 (research/operations/2026-06-23-self-loop-implementation-plan.md).
//
// TERMINOLOGY (corrected 2026-06-28): this is a RELIABILITY / self-HEALING loop — NOT the
// recursive self-improvement (RSI) Amodei describes ("models autonomously capable of building
// BETTER models"; Anthropic "When AI Builds Itself" — "we are not there yet"). Our A1-A4 rings
// raise operational reliability (catch regressions, restart dead organs, verify findings), not
// model capability. Honest framing: A4 (this adversarial gate) is a SAFETY PRIMITIVE a safe RSI
// would require FIRST — scaffolding for that future, not that future. Call it self-healing.
//
// The "never trust your own subagent + verify on fresh context" doctrine already exists
// (opus-mythos TAC + the sota-architecture-loop skill: "verifica esterna batte
// autodichiarazione · adversarialità calibrata batte consenso"). What was MISSING is a
// reusable EXECUTABLE artifact — every research/audit re-wrote the gather→verify→synthesize
// workflow ad-hoc in ephemeral session files that vanish. This is that artifact, versioned.
//
// WHAT IT ENCODES (the one principle of the whole self-loop): "judging < generating".
// A finding survives ONLY if an INDEPENDENT grader on FRESH context could not refute it.
// The grader is a different agent than the generator (no self-approval — the W65 lesson:
// even the refuter hallucinates, but a generator grading itself is strictly worse).
//
// HOW TO RUN (from the main loop, when a task is research / audit / multi-claim verification):
//   Workflow({ scriptPath: "infra/workflows/verify-template.js", args: {
//     question: "the question to answer",
//     angles: [ { key: "angleA", prompt: "research angle A …" }, … ],   // 2-6 distinct lenses
//     synthesisPrompt: "how to merge the verified findings (optional)",
//     skeptics: 1,                                                       // graders per finding (1 default; 3 for high-stakes)
//   }})
// Omit `angles` and it falls back to a single-angle pass on `question`.
//
// CALIBRATION (sota-architecture-loop §3/6): NOT pure-adversarial, NOT consensus. The default
// is one strong skeptic per finding (the "troublemaker"); set skeptics:3 for high-stakes
// (security / regulatory / client-quote) and a finding survives on majority-not-refuted.
// Heterogeneity > numerosity: give each angle a DISTINCT lens, not N copies of one.

export const meta = {
  name: "verify-template",
  description:
    "Reusable generator≠grader workflow: gather N angles → adversarially verify each → synthesize survivors",
  phases: [
    { title: "Gather", detail: "one agent per angle, structured findings" },
    {
      title: "Verify",
      detail:
        "independent skeptic(s) per finding on fresh context — refute or keep",
    },
    {
      title: "Synthesize",
      detail: "merge only findings that survived refutation",
    },
  ],
};

// ----- input (args), with safe fallbacks ------------------------------------
const A = (typeof args === "string" ? JSON.parse(args) : args) || {};
const QUESTION = A.question || "No question provided (pass args.question).";
const ANGLES =
  Array.isArray(A.angles) && A.angles.length
    ? A.angles
    : [{ key: "single", prompt: QUESTION }];
const SKEPTICS = Math.max(1, Math.min(5, A.skeptics || 1));
const SYNTH_PROMPT =
  A.synthesisPrompt ||
  `Synthesize a cited answer to: "${QUESTION}". Use ONLY findings that survived refutation. ` +
    `Be explicit about what is well-sourced vs inferred. No fluff.`;

// structured finding schema — forces each claim to carry its own evidence + self-rated confidence
const FINDING_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["angle", "findings"],
  properties: {
    angle: { type: "string" },
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["claim", "evidence", "source", "confidence"],
        properties: {
          claim: { type: "string" },
          evidence: {
            type: "string",
            description: "the concrete basis — quote/path/number",
          },
          source: {
            type: "string",
            description:
              'real URL/file:line you actually checked, or "INFERENCE"',
          },
          confidence: { type: "string", enum: ["high", "medium", "low"] },
        },
      },
    },
  },
};

const VERDICT_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["refuted", "reason"],
  properties: {
    refuted: {
      type: "boolean",
      description: "true if the claim is false/overstated/unsupported",
    },
    reason: { type: "string" },
    confidence: { type: "string", enum: ["high", "medium", "low"] },
  },
};

// ----- the pipeline: gather → verify (per finding) → collect survivors -------
phase("Gather");
const perAngle = await pipeline(
  ANGLES,
  (a) =>
    agent(
      a.prompt +
        "\n\nReturn structured findings. Cite a REAL source you actually checked; " +
        "mark INFERENCE if it is not from a source.",
      { label: `gather:${a.key}`, phase: "Gather", schema: FINDING_SCHEMA },
    ),
  // verify each finding of this angle with independent skeptic(s) on fresh context
  (res, a) => {
    if (!res || !res.findings) return { angle: a.key, verified: [] };
    return parallel(
      res.findings.map(
        (f) => () =>
          parallel(
            Array.from(
              { length: SKEPTICS },
              (_unused, i) => () =>
                agent(
                  `You are skeptic #${i + 1}, an INDEPENDENT adversarial grader. Try to REFUTE this claim. ` +
                    `It is suspect if the source is vague/invented, the evidence is hand-wavy, or it overstates. ` +
                    `Default to refuted=true when uncertain. Verify the source if you can.\n\n` +
                    `CLAIM: ${f.claim}\nEVIDENCE: ${f.evidence}\nSOURCE: ${f.source} (self-rated ${f.confidence})`,
                  {
                    label: `verify:${a.key}`,
                    phase: "Verify",
                    schema: VERDICT_SCHEMA,
                  },
                ),
            ),
          ).then((votes) => {
            const v = votes.filter(Boolean);
            const refutedCount = v.filter((x) => x.refuted).length;
            const survives = refutedCount < Math.ceil(v.length / 2); // majority-not-refuted
            return { ...f, survives, refutedCount, votes: v.length };
          }),
      ),
    ).then((checked) => ({ angle: a.key, verified: checked.filter(Boolean) }));
  },
);

phase("Synthesize");
const survivors = perAngle
  .filter(Boolean)
  .flatMap((r) =>
    (r.verified || [])
      .filter((f) => f.survives)
      .map((f) => ({ angle: r.angle, ...f })),
  );
const refuted = perAngle
  .filter(Boolean)
  .flatMap((r) => (r.verified || []).filter((f) => !f.survives));
log(`survivors: ${survivors.length} · refuted/dropped: ${refuted.length}`);

const corpus = survivors
  .map(
    (f) =>
      `### ${f.angle}\n- ${f.claim}\n  evidence: ${f.evidence} [${f.confidence}] (${f.source})`,
  )
  .join("\n\n");

const synthesis = survivors.length
  ? await agent(
      `${SYNTH_PROMPT}\n\nVERIFIED FINDINGS (survived refutation):\n${corpus}`,
      { label: "synthesize", phase: "Synthesize" },
    )
  : "No findings survived adversarial refutation — the question needs better sources or re-scoping.";

return {
  synthesis,
  survivors,
  refutedCount: refuted.length,
  anglesRun: ANGLES.length,
};
