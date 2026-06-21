export type LabVisualStatus =
  | "watching"
  | "running"
  | "paused"
  | "needs_review"
  | "blocked"
  | "completed"
  | "promoted"
  | "declined";

export type LabArchiveOutcome = "promoted" | "declined";

export interface LabVisualPhase {
  order: number;
  id: string;
  title: string;
  stage: string;
  summary: string;
  status: LabVisualStatus;
  accent: string;
  emphasis?: "large";
}

export interface LabVisualProcess {
  id: string;
  phaseId: string;
  title: string;
  summary: string;
  humanDetail: string;
  status: LabVisualStatus;
  progress: number;
  currentState: string;
  pros: string[];
  cons: string[];
  problems: string[];
  stimuli: string[];
  archive?: {
    outcome: LabArchiveOutcome;
    finalBoxTitle: string;
    story: string;
    movedThrough: string[];
  };
}

export const LAB_HERO_IMAGE_URL =
  "https://images.unsplash.com/photo-1580106815433-a5b1d1d53d85?auto=format&fit=crop&fm=jpg&q=80&w=2400";

export const LAB_HERO_IMAGE_SOURCE_URL = "https://unsplash.com/s/photos/server";

export const LAB_VISUAL_PHASES: LabVisualPhase[] = [
  {
    order: 1,
    id: "watch",
    title: "Watchtower",
    stage: "watch",
    summary:
      "Scans AI research, software releases, repos, MCP tools, and NotebookLM intelligence.",
    status: "watching",
    accent: "cyan",
  },
  {
    order: 2,
    id: "intake",
    title: "Intake",
    stage: "collect",
    summary:
      "Turns fresh signals into clean research envelopes with provenance and freshness.",
    status: "running",
    accent: "emerald",
  },
  {
    order: 3,
    id: "normalize",
    title: "Normalize",
    stage: "dedupe",
    summary:
      "Deduplicates, fingerprints, redacts, and keeps receipts free of raw sensitive content.",
    status: "running",
    accent: "violet",
  },
  {
    order: 4,
    id: "compose",
    title: "Compose",
    stage: "reason",
    summary:
      "Combines materials into useful hypotheses and implementation candidates.",
    status: "needs_review",
    accent: "amber",
  },
  {
    order: 5,
    id: "target",
    title: "Target",
    stage: "map",
    summary:
      "Maps each candidate onto real Nuzantara paths instead of leaving it abstract.",
    status: "running",
    accent: "lime",
  },
  {
    order: 6,
    id: "reconstruct",
    title: "Reconstruct",
    stage: "mirror",
    summary:
      "Builds a production-like context using sanitized fixtures and runtime contracts.",
    status: "paused",
    accent: "sky",
  },
  {
    order: 7,
    id: "experiment",
    title: "Experiment",
    stage: "sandbox",
    summary:
      "Plans isolated tests, bounded commands, rollback, and acceptance metrics.",
    status: "blocked",
    accent: "rose",
  },
  {
    order: 8,
    id: "verify",
    title: "Verify",
    stage: "measure",
    summary:
      "Runs evidence checks and refuses to pretend an idea worked without proof.",
    status: "needs_review",
    accent: "indigo",
  },
  {
    order: 9,
    id: "tribunal",
    title: "Tribunal",
    stage: "verify",
    summary:
      "Judges policy, command safety, receipt safety, novelty, and remaining risk.",
    status: "needs_review",
    accent: "fuchsia",
  },
  {
    order: 10,
    id: "curator",
    title: "Curator",
    stage: "decide",
    summary:
      "The human gate. It recommends promotion, rejection, or more evidence.",
    status: "paused",
    accent: "orange",
    emphasis: "large",
  },
  {
    order: 11,
    id: "archive",
    title: "Archive",
    stage: "remember",
    summary:
      "Stores the final story of completed processes: promoted, declined, and why.",
    status: "completed",
    accent: "teal",
  },
];

export const LAB_VISUAL_PROCESSES: LabVisualProcess[] = [
  {
    id: "notebook-frontier-scan",
    phaseId: "watch",
    title: "NotebookLM Frontier Scan",
    summary:
      "Checks the AI research notebooks for new agent, coding, MCP, and world-model signals.",
    humanDetail:
      "The Lab asks what changed recently and keeps only the metadata needed to decide whether a new idea is worth studying.",
    status: "watching",
    progress: 42,
    currentState: "Watching for fresh sources and idle ticks.",
    pros: [
      "Keeps the Lab connected to current research.",
      "Routes overflow away from capped notebooks.",
    ],
    cons: [
      "Quality depends on notebook curation.",
      "Needs source split cleanup when a notebook is near its limit.",
    ],
    problems: ["Primary AIResearch notebook is close to the source cap."],
    stimuli: [
      "Split large notebooks by role.",
      "Promote only synthesized findings into the coding core.",
    ],
  },
  {
    id: "repo-pattern-watch",
    phaseId: "watch",
    title: "Repository Pattern Watch",
    summary:
      "Looks for useful implementation patterns in public agent and developer-tooling repos.",
    humanDetail:
      "The Lab treats repos as inspiration sources, not copy-paste targets. It extracts patterns and then maps them to Nuzantara constraints.",
    status: "watching",
    progress: 35,
    currentState: "Metadata-only scan contract is ready.",
    pros: ["Good for catching practical patterns before papers describe them."],
    cons: ["Needs license and maintenance review before reuse."],
    problems: [
      "Live repo connector is still staged behind read-only adapters.",
    ],
    stimuli: ["Rank repos by tests, release cadence, and architectural fit."],
  },
  {
    id: "sdk-changelog-watch",
    phaseId: "watch",
    title: "SDK Changelog Watch",
    summary:
      "Tracks model, framework, SDK, and MCP changes that could unlock new Lab abilities.",
    humanDetail:
      "This process watches official docs and changelogs so the Lab notices when a better API, safer sandbox, or new routing primitive appears.",
    status: "running",
    progress: 28,
    currentState: "Source adapter declared, live fetch still gated.",
    pros: ["Official docs are higher trust than social summaries."],
    cons: ["Release notes can be vague or marketing-heavy."],
    problems: ["Needs freshness windows per provider."],
    stimuli: ["Add provider-specific diff fingerprints."],
  },
  {
    id: "operator-brief-capture",
    phaseId: "watch",
    title: "Operator Brief Capture",
    summary:
      "Turns your rough instructions into a structured objective the Lab can follow.",
    humanDetail:
      "When you write in fast Italian, this process converts the intent into a precise Lab objective without losing the spirit of the request.",
    status: "completed",
    progress: 100,
    currentState: "Completed and moved into Archive.",
    pros: [
      "Makes vague prompts actionable.",
      "Keeps the Lab aligned with your actual goal.",
    ],
    cons: [
      "Can still need human correction when the desired risk level changes.",
    ],
    problems: [],
    stimuli: [
      "Keep the original human wording attached as a fingerprint, not raw leakage.",
    ],
    archive: {
      outcome: "promoted",
      finalBoxTitle: "Human brief became the Lab operating model",
      story:
        "The rough instruction became the durable rule: ingest research continuously, compose it, apply it to Nuzantara, simulate production, and surface only high-potential outputs.",
      movedThrough: ["Watchtower", "Intake", "Compose", "Curator", "Archive"],
    },
  },
  {
    id: "source-envelope-builder",
    phaseId: "intake",
    title: "Source Envelope Builder",
    summary:
      "Wraps every incoming item with source type, URI, title, timestamp, and metadata.",
    humanDetail:
      "Instead of throwing raw content into the Lab, this process gives every source a clean passport.",
    status: "running",
    progress: 58,
    currentState: "Envelope contracts are implemented for shadow watch ticks.",
    pros: [
      "Makes later audit possible.",
      "Separates source metadata from raw text.",
    ],
    cons: ["Needs live connectors to produce real envelopes continuously."],
    problems: ["NotebookLM and repo adapters are still read-contract first."],
    stimuli: ["Add source trust scores and stale-source markers."],
  },
  {
    id: "freshness-gate",
    phaseId: "intake",
    title: "Freshness Gate",
    summary: "Checks whether a signal is fresh enough to matter today.",
    humanDetail:
      "The Lab should not spend energy on stale news unless the idea is still technically important.",
    status: "needs_review",
    progress: 31,
    currentState: "Freshness windows are declared per source family.",
    pros: ["Avoids wasting cycles on old material."],
    cons: ["Some old papers become important later."],
    problems: ["Needs a reactivation rule for rediscovered ideas."],
    stimuli: ["Use novelty plus recency instead of recency alone."],
  },
  {
    id: "provenance-check",
    phaseId: "intake",
    title: "Provenance Check",
    summary: "Confirms where a signal came from before the Lab builds on it.",
    humanDetail:
      "This is the evidence label: the Lab needs to know whether it is looking at a paper, repo, docs page, notebook summary, or operator note.",
    status: "running",
    progress: 64,
    currentState: "Receipt-safe provenance is available for shadow materials.",
    pros: ["Improves trust.", "Makes bad sources easier to quarantine."],
    cons: ["Cannot yet verify every external source live."],
    problems: ["Live web verification remains a gated connector step."],
    stimuli: ["Attach confidence and source class to every claim."],
  },
  {
    id: "fingerprint-material",
    phaseId: "normalize",
    title: "Fingerprint Material",
    summary:
      "Converts raw material into stable hashes and bounded evidence references.",
    humanDetail:
      "The Lab remembers that something mattered without storing private or oversized raw text.",
    status: "running",
    progress: 78,
    currentState: "Fingerprinting is active in receipts.",
    pros: ["Keeps receipts safe.", "Makes duplicates easy to catch."],
    cons: ["Fingerprints are less readable than source excerpts."],
    problems: [],
    stimuli: ["Show human summaries beside fingerprints in the UI."],
  },
  {
    id: "dedupe-cluster",
    phaseId: "normalize",
    title: "Dedupe Cluster",
    summary:
      "Groups repeated or near-identical signals so the Lab does not overcount hype.",
    humanDetail:
      "When ten sources say the same thing, this process makes it one stronger signal instead of ten noisy ones.",
    status: "running",
    progress: 51,
    currentState: "Cluster counts appear in the shadow run.",
    pros: ["Reduces noise.", "Makes novelty easier to see."],
    cons: ["Near-duplicate detection needs richer embeddings later."],
    problems: ["Current shadow mode is deterministic and metadata-first."],
    stimuli: ["Add semantic clustering once live ingestion is safe."],
  },
  {
    id: "law-two-redaction",
    phaseId: "normalize",
    title: "Law 2 Redaction",
    summary:
      "Blocks raw private data, secrets, emails, phone-like values, and unsafe receipt fields.",
    humanDetail:
      "This is the privacy brake. It makes sure the Lab does not leak raw operational material into outputs or memory.",
    status: "completed",
    progress: 100,
    currentState: "Completed and moved into Archive.",
    pros: [
      "Protects OSINT and client material.",
      "Makes receipts persistable.",
    ],
    cons: ["Can hide details that would be useful during debugging."],
    problems: [],
    stimuli: ["Use redacted references plus local-only drilldown when needed."],
    archive: {
      outcome: "promoted",
      finalBoxTitle: "Receipt safety promoted",
      story:
        "The redaction system was promoted because it blocks raw leakage while still preserving enough fingerprints and summaries to explain a Lab decision.",
      movedThrough: ["Normalize", "Tribunal", "Curator", "Archive"],
    },
  },
  {
    id: "tag-and-claim-extract",
    phaseId: "normalize",
    title: "Tag And Claim Extract",
    summary:
      "Extracts human-readable tags and claim fingerprints from each material.",
    humanDetail:
      "This turns messy research into navigable signals: agent, coding, safety, repo, simulation, workspace, and similar tags.",
    status: "running",
    progress: 62,
    currentState: "Deterministic extraction is active.",
    pros: ["Makes the control room easier to scan."],
    cons: ["Simple tags can miss subtle research themes."],
    problems: ["Needs LLM-assisted tagging after the sandbox is fully wired."],
    stimuli: ["Let Tribunal flag weak or unsupported claims."],
  },
  {
    id: "hypothesis-builder",
    phaseId: "compose",
    title: "Hypothesis Builder",
    summary: "Turns normalized signals into implementable hypotheses.",
    humanDetail:
      "This is where the Lab asks: what could we actually build, change, or test inside Nuzantara?",
    status: "needs_review",
    progress: 49,
    currentState: "Shadow hypotheses are generated from normalized materials.",
    pros: ["Moves research toward code.", "Keeps the output decision-grade."],
    cons: ["Needs stronger ranking before it can run unattended."],
    problems: ["Some hypotheses are still too broad."],
    stimuli: ["Score by impact, reversibility, and testability."],
  },
  {
    id: "candidate-synthesis",
    phaseId: "compose",
    title: "Candidate Synthesis",
    summary: "Combines multiple signals into one candidate implementation.",
    humanDetail:
      "Instead of one source creating one patch, the Lab composes a more mature candidate from several pieces of evidence.",
    status: "running",
    progress: 46,
    currentState: "Candidate proposal appears in the shadow run.",
    pros: ["Better than source-by-source patching."],
    cons: ["Composition can blur which source caused which decision."],
    problems: ["Needs clearer source-to-candidate lineage display."],
    stimuli: ["Show source signal IDs inside each process detail."],
  },
  {
    id: "decision-grade-output-plan",
    phaseId: "compose",
    title: "Decision-Grade Output Plan",
    summary:
      "Defines what the Lab must produce before you should care about the result.",
    humanDetail:
      "The Lab should not interrupt you with half-thoughts. It prepares proposal, patch diff, tests, metrics, failure notes, and a recommendation.",
    status: "running",
    progress: 70,
    currentState: "Output contract is part of the LabRun receipt.",
    pros: ["Filters noise.", "Makes output review faster."],
    cons: ["Can delay surfacing a promising but incomplete idea."],
    problems: [],
    stimuli: [
      "Add urgency override for high-impact security or platform changes.",
    ],
  },
  {
    id: "target-path-selector",
    phaseId: "target",
    title: "Target Path Selector",
    summary:
      "Chooses the repo areas where an idea could become a concrete change.",
    humanDetail:
      "This process prevents abstract research from floating forever. It must name files or modules.",
    status: "running",
    progress: 55,
    currentState: "Target paths are validated as repo-relative safe paths.",
    pros: [
      "Keeps the Lab practical.",
      "Prevents accidental writes outside the repo.",
    ],
    cons: ["Needs code ownership and blast-radius awareness."],
    problems: ["Current selector is still prompt/planner driven."],
    stimuli: ["Add import graph and test ownership scoring."],
  },
  {
    id: "blast-radius-check",
    phaseId: "target",
    title: "Blast Radius Check",
    summary: "Estimates how risky a target area is before experimentation.",
    humanDetail:
      "A tiny UI copy change and a router dependency change should not receive the same risk treatment.",
    status: "needs_review",
    progress: 24,
    currentState: "Risk is currently inferred from blockers and commands.",
    pros: ["Protects critical backend paths."],
    cons: ["Needs richer repo graph evidence."],
    problems: ["Shared dependencies require special handling."],
    stimuli: ["Use test coverage and import fan-out to rank risk."],
  },
  {
    id: "worktree-plan",
    phaseId: "target",
    title: "Worktree Plan",
    summary:
      "Prepares the isolated worktree command for any future patch attempt.",
    humanDetail:
      "Every experiment must happen in a dedicated worktree so concurrent agents do not trample each other.",
    status: "completed",
    progress: 100,
    currentState: "Completed and moved into Archive.",
    pros: ["Protects the main checkout.", "Makes cleanup and review easier."],
    cons: ["Adds setup overhead for very small changes."],
    problems: [],
    stimuli: ["Attach worktree lease state to the UI later."],
    archive: {
      outcome: "promoted",
      finalBoxTitle: "Worktree isolation promoted",
      story:
        "The worktree plan was promoted because it matches the repository discipline: every Lab mutation needs an isolated lane before it touches code.",
      movedThrough: ["Target", "Experiment", "Tribunal", "Curator", "Archive"],
    },
  },
  {
    id: "prod-like-manifest",
    phaseId: "reconstruct",
    title: "Production-Like Manifest",
    summary:
      "Describes the runtime, fixtures, commands, and constraints needed to test realistically.",
    humanDetail:
      "The Lab should test as if the environment were real, but with sanitized data and controlled boundaries.",
    status: "paused",
    progress: 37,
    currentState: "Manifest shape is declared; live fixture builder is next.",
    pros: ["Prevents toy tests from lying."],
    cons: ["Harder to build than simple unit fixtures."],
    problems: ["Needs runtime-specific fixture packs."],
    stimuli: [
      "Start with autonomous-lab backend and admin-dashboard fixtures.",
    ],
  },
  {
    id: "secretless-context",
    phaseId: "reconstruct",
    title: "Secretless Context",
    summary:
      "Reconstructs useful environment shape without copying secret values.",
    humanDetail:
      "The Lab needs to know which keys and services exist, but not the secrets themselves.",
    status: "running",
    progress: 44,
    currentState: "Environment allowlist exists in sandbox policy.",
    pros: ["Useful and safe.", "Keeps service shape visible."],
    cons: ["Some integration failures require real auth later."],
    problems: ["Needs explicit operator approval for connected services."],
    stimuli: ["Use key names, service modes, and redacted status only."],
  },
  {
    id: "runtime-placement-check",
    phaseId: "reconstruct",
    title: "Runtime Placement Check",
    summary:
      "Decides whether a task belongs on Pro, Mini, or Air-M5 before work begins.",
    humanDetail:
      "The Lab checks machine placement so heavy jobs do not accidentally run on the thin client.",
    status: "running",
    progress: 66,
    currentState:
      "Placement receipts are visible in worker and scheduler status.",
    pros: [
      "Prevents expensive mistakes.",
      "Matches the Pro/Mini/Air routing rules.",
    ],
    cons: ["Peer reachability can be noisy."],
    problems: ["Mini peer can be unreachable during local checks."],
    stimuli: ["Show placement status beside scheduler readiness."],
  },
  {
    id: "sandbox-policy-builder",
    phaseId: "experiment",
    title: "Sandbox Policy Builder",
    summary:
      "Defines filesystem, network, command, timeout, and environment boundaries.",
    humanDetail:
      "This process decides exactly what the experiment is allowed to touch before any command runs.",
    status: "blocked",
    progress: 72,
    currentState:
      "Policy exists; real executions remain allowlisted and bounded.",
    pros: ["Strong safety foundation.", "Makes refusal reasons explicit."],
    cons: ["Strict policies can reject useful tests until allowlisted."],
    problems: ["Needs a controlled expansion path for new commands."],
    stimuli: ["Add command request queue reviewed by Curator."],
  },
  {
    id: "command-allowlist",
    phaseId: "experiment",
    title: "Command Allowlist",
    summary:
      "Accepts only known verification commands and rejects everything else.",
    humanDetail:
      "No shell improvisation. If a command is not known safe, the sandbox refuses it and records why.",
    status: "running",
    progress: 77,
    currentState: "Allowlisted commands are enforced by the sandbox runner.",
    pros: ["Very safe.", "Easy to audit."],
    cons: ["Needs maintenance as the Lab grows."],
    problems: ["Admin dashboard build is not yet a sandbox command shape."],
    stimuli: ["Add build and visual-check commands after review."],
  },
  {
    id: "patch-arena",
    phaseId: "experiment",
    title: "Patch Arena",
    summary:
      "The isolated place where a future candidate patch will be created and tested.",
    humanDetail:
      "This is where the Lab eventually changes files, but only inside the approved worktree and under the sandbox policy.",
    status: "blocked",
    progress: 18,
    currentState: "Not executing autonomous patches yet.",
    pros: ["Correct shape for future autonomy."],
    cons: ["Still needs controlled patch writer integration."],
    problems: ["Autonomous execution remains off by design."],
    stimuli: ["Start with tiny docs/UI patches before backend changes."],
  },
  {
    id: "rollback-plan",
    phaseId: "experiment",
    title: "Rollback Plan",
    summary:
      "Defines how to discard a bad experiment while preserving the learning.",
    humanDetail:
      "A failed experiment should not poison the repo. It should leave a clear failure story and then disappear cleanly.",
    status: "running",
    progress: 63,
    currentState: "Rollback plan is included in every ExperimentSpec.",
    pros: ["Makes failure acceptable.", "Keeps the Lab honest."],
    cons: ["Rollback still needs artifact cleanup when real patches begin."],
    problems: [],
    stimuli: ["Link every rollback to the exact worktree and receipt."],
  },
  {
    id: "test-runner",
    phaseId: "verify",
    title: "Test Runner",
    summary:
      "Runs approved backend, frontend, and diff checks for the candidate.",
    humanDetail:
      "This process produces empirical proof: tests passed, failed, timed out, or were refused.",
    status: "needs_review",
    progress: 57,
    currentState:
      "Backend autonomous-lab tests are green; broader command set is staged.",
    pros: ["Turns opinions into evidence."],
    cons: ["Tests can miss visual or product quality."],
    problems: ["Needs browser evidence for UI-heavy work."],
    stimuli: ["Attach screenshot checks to UI candidates."],
  },
  {
    id: "metric-delta",
    phaseId: "verify",
    title: "Metric Delta",
    summary:
      "Compares before/after behavior so the Lab knows whether the change helped.",
    humanDetail:
      "A patch should improve something measurable, or at least not degrade a protected metric.",
    status: "paused",
    progress: 22,
    currentState:
      "Metric schema is declared but not wired to live experiments.",
    pros: ["Prevents cosmetic success claims."],
    cons: ["Some UX gains are hard to quantify immediately."],
    problems: ["Needs baseline capture per experiment type."],
    stimuli: [
      "Use test runtime, failure count, UI clarity, and reviewer findings first.",
    ],
  },
  {
    id: "failure-report",
    phaseId: "verify",
    title: "Failure Report",
    summary: "Writes a clear explanation when the experiment does not pass.",
    humanDetail:
      "Failure is still useful if it tells us what broke, why, and what to try next.",
    status: "running",
    progress: 48,
    currentState: "Failure references are receipt-safe and bounded.",
    pros: ["Avoids silent failures.", "Improves the next experiment."],
    cons: ["Needs richer root-cause grouping later."],
    problems: [],
    stimuli: ["Group failures by policy, test, runtime, and design quality."],
  },
  {
    id: "policy-tribunal",
    phaseId: "tribunal",
    title: "Policy Tribunal",
    summary:
      "Judges whether the candidate violated sandbox, privacy, deploy, or workspace rules.",
    humanDetail:
      "This tribunal protects the system. If a candidate asks for dangerous behavior, it blocks promotion.",
    status: "needs_review",
    progress: 74,
    currentState: "Reviewer and evaluator both emit policy findings.",
    pros: ["Strong safety layer.", "Easy to explain to the operator."],
    cons: ["Can be conservative until the allowlist matures."],
    problems: ["Needs severity tuning as real experiments increase."],
    stimuli: ["Separate hard blockers from soft warnings in the UI."],
  },
  {
    id: "receipt-tribunal",
    phaseId: "tribunal",
    title: "Receipt Tribunal",
    summary:
      "Checks whether the recorded evidence is safe to persist and human-readable enough.",
    humanDetail:
      "The Lab must leave receipts that explain decisions without leaking private data.",
    status: "running",
    progress: 80,
    currentState: "Receipt persistence rejects unsafe values.",
    pros: ["Protects memory and logs.", "Supports long-term learning."],
    cons: ["Over-redaction can reduce clarity."],
    problems: [],
    stimuli: [
      "Add side-by-side safe summary and internal fingerprint references.",
    ],
  },
  {
    id: "novelty-tribunal",
    phaseId: "tribunal",
    title: "Novelty Tribunal",
    summary:
      "Asks whether the candidate is genuinely new or just recycled noise.",
    humanDetail:
      "This keeps the Lab from repeatedly proposing the same idea in different clothes.",
    status: "paused",
    progress: 33,
    currentState: "Novelty metric exists; richer clustering is next.",
    pros: ["Keeps the Lab interesting.", "Reduces fatigue."],
    cons: ["Novelty is contextual, not purely mathematical."],
    problems: ["Needs historical trajectory search."],
    stimuli: ["Compare against archived promoted and declined stories."],
  },
  {
    id: "promotion-recommendation",
    phaseId: "curator",
    title: "Promotion Recommendation",
    summary:
      "Says whether a process should continue toward PR, wait, or be declined.",
    humanDetail:
      "This is the big gate. The Lab can recommend, but the operator decides what gets promoted.",
    status: "paused",
    progress: 60,
    currentState: "Manual promotion remains required.",
    pros: [
      "Keeps autonomy under control.",
      "Makes the final decision visible.",
    ],
    cons: ["Still depends on operator review."],
    problems: ["Needs richer operator queue actions in the UI."],
    stimuli: [
      "Add approve, decline, ask-for-more-evidence actions per process.",
    ],
  },
  {
    id: "evidence-request",
    phaseId: "curator",
    title: "Evidence Request",
    summary: "Asks the Lab to collect missing proof before a decision.",
    humanDetail:
      "If a candidate is promising but under-tested, the curator sends it back with a clear evidence request.",
    status: "needs_review",
    progress: 45,
    currentState: "Next action appears in curator decision receipts.",
    pros: ["Prevents premature rejection.", "Turns vague doubt into a task."],
    cons: ["Can create loops without a stop condition."],
    problems: ["Needs max retry and stale decision rules."],
    stimuli: ["Add evidence-request aging and escalation."],
  },
  {
    id: "human-readable-story",
    phaseId: "curator",
    title: "Human-Readable Story",
    summary:
      "Prepares the short narrative you read before approving or declining.",
    humanDetail:
      "This process turns technical receipts into a human story: what happened, what worked, what failed, and what the Lab wants next.",
    status: "running",
    progress: 53,
    currentState: "Archive story format is now represented in the UI model.",
    pros: [
      "Makes review faster.",
      "Keeps technical proof attached without noise.",
    ],
    cons: ["Needs real completed runs to become richer."],
    problems: [],
    stimuli: [
      "Use timeline plus Tribunal verdict to auto-generate story drafts.",
    ],
  },
  {
    id: "manual-gate-controls",
    phaseId: "curator",
    title: "Manual Gate Controls",
    summary: "The operator controls that approve, cancel, or hold a candidate.",
    humanDetail:
      "This is where the UI eventually lets you move a process forward or stop it.",
    status: "blocked",
    progress: 40,
    currentState:
      "Backend decision endpoints exist; per-process visual controls are next.",
    pros: ["Gives the operator direct control."],
    cons: ["Must be very clear to avoid accidental promotion."],
    problems: ["Current controls are run-level, not visual process-level."],
    stimuli: ["Add confirm states and irreversible-action copy."],
  },
  {
    id: "declined-overbroad-agent",
    phaseId: "compose",
    title: "Overbroad Agent Idea",
    summary: "A candidate that tried to change too many systems at once.",
    humanDetail:
      "The Lab learned that broad autonomy proposals need to be split before they can be trusted.",
    status: "declined",
    progress: 100,
    currentState: "Declined and moved into Archive.",
    pros: ["The idea had strategic ambition."],
    cons: ["Too much blast radius for one experiment."],
    problems: ["No narrow acceptance metric.", "Too many unrelated modules."],
    stimuli: ["Split broad ideas into one measurable patch at a time."],
    archive: {
      outcome: "declined",
      finalBoxTitle: "Declined: broad autonomy patch",
      story:
        "The process passed through composition and targeting, but the Curator declined it because the blast radius was too large and the evidence plan was too vague.",
      movedThrough: ["Compose", "Target", "Tribunal", "Curator", "Archive"],
    },
  },
  {
    id: "visual-control-room-map",
    phaseId: "curator",
    title: "Visual Control Room Map",
    summary: "The UI map that makes the whole Lab understandable to a human.",
    humanDetail:
      "This process redesigns Step 12 as a visual lab map with phases, process boxes, details, and archive stories.",
    status: "promoted",
    progress: 100,
    currentState: "Promoted into the live admin dashboard slice.",
    pros: ["Makes the Lab legible.", "Gives every process a place to live."],
    cons: ["Still needs real-time backend process binding."],
    problems: [
      "The current version uses a visual projection layer for process stories.",
    ],
    stimuli: [
      "Bind each process box to durable runtime events as the worker becomes live.",
    ],
    archive: {
      outcome: "promoted",
      finalBoxTitle: "Promoted: visual Lab map",
      story:
        "The process became the new Step 12 interface: a futuristic Lab home, clickable phase pages, process details, and an Archive that explains promoted and declined outcomes.",
      movedThrough: ["Curator", "Archive"],
    },
  },
];

export function activeLabProcessesForPhase(
  phaseId: string,
): LabVisualProcess[] {
  if (phaseId === "archive") {
    return archivedLabProcesses();
  }
  return LAB_VISUAL_PROCESSES.filter(
    (process) => process.phaseId === phaseId && process.archive === undefined,
  );
}

export function archivedLabProcesses(): LabVisualProcess[] {
  return LAB_VISUAL_PROCESSES.filter(
    (process) => process.archive !== undefined,
  );
}

export function labPhaseById(phaseId: string): LabVisualPhase | undefined {
  return LAB_VISUAL_PHASES.find((phase) => phase.id === phaseId);
}

export function labProcessByRoute(
  phaseId: string,
  processId: string,
): LabVisualProcess | undefined {
  const process = LAB_VISUAL_PROCESSES.find((item) => item.id === processId);
  if (!process) {
    return undefined;
  }
  if (phaseId === "archive") {
    return process.archive ? process : undefined;
  }
  if (process.archive) {
    return undefined;
  }
  return process.phaseId === phaseId ? process : undefined;
}

export function labProcessCountForPhase(phaseId: string): number {
  return activeLabProcessesForPhase(phaseId).length;
}

export function labStatusLabel(status: string): string {
  return status.replaceAll("_", " ");
}
