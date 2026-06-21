export type LabTone = "good" | "warn" | "danger" | "neutral";

export type LabStageStatus =
  | "live"
  | "planned"
  | "blocked"
  | "paused"
  | "designing";

export interface LabMetric {
  label: string;
  value: string;
  tone: LabTone;
}

export interface LabStageView {
  id: string;
  label: string;
  status: LabStageStatus;
  owner: string;
  gate: string;
  gate_state?: string;
  summary: string;
  artifact: string;
}

export interface LabLane {
  name: string;
  status: string;
  next: string;
  proof: string;
  tone: LabTone;
}

export interface LabAction {
  order: number;
  title: string;
  backend: string;
  ui: string;
  gate: string;
}

export interface LabRisk {
  label: string;
  control: string;
  tone: LabTone;
}

export interface LabSnapshot {
  version?: string;
  updatedAt: string;
  updated_at?: string;
  machine: string;
  machine_role?: string;
  syncState: string;
  sync_state?: string;
  doctrine: string;
  metrics: LabMetric[];
  stages: LabStageView[];
  lanes: LabLane[];
  firstBatch: LabAction[];
  first_batch?: LabAction[];
  risks: LabRisk[];
  runtime_placement?: Record<string, unknown>;
  operational_plan?: Record<string, unknown>;
}

export interface LabWorkerCheckpoint {
  order: number;
  stage: string;
  status: string;
  gate_state: string;
  artifact: string;
  summary: string;
  executed: boolean;
  external_calls: number;
}

export interface LabRunPreview {
  version: string;
  run_id: string;
  created_at: string;
  checkpoints: LabWorkerCheckpoint[];
  paused_at_stage: string;
  execution_allowed: boolean;
  manual_promotion_required: boolean;
  blocked: boolean;
}

export interface LabSchedulerStatus {
  version: string;
  updated_at: string;
  enabled: boolean;
  db_available: boolean;
  placement: {
    machine_role: string;
    can_enqueue: boolean;
    can_claim_runs: boolean;
    can_consume_outbox: boolean;
    heavy_work_destination: string;
    reason: string;
  };
  tick_interval_seconds: number;
  worker_id: string;
  state: string;
  can_tick: boolean;
  next_tick_not_before: string;
  next_action: string;
  tick_mode: string;
  autonomous_execution_allowed: boolean;
  manual_promotion_required: boolean;
  safeguards: string[];
}

export interface LabSandboxPolicy {
  version: string;
  filesystem: {
    mode: string;
    repo_read_only: boolean;
    writable_roots: string[];
    forbidden_roots: string[];
  };
  network: {
    mode: string;
    allowed_hosts: string[];
    allow_localhost: boolean;
  };
  execution_limits: {
    timeout_seconds: number;
    max_output_bytes: number;
    max_artifact_bytes: number;
    env_allowlist: string[];
  };
  require_policy_before_execution: boolean;
  production_writes_allowed: boolean;
  deploy_merge_push_allowed: boolean;
  raw_data_persistence_allowed: boolean;
  stdout_redaction_required: boolean;
  prod_like_input_contract: string;
}

export interface LabTimelineEvent {
  order: number;
  stage: string;
  status: string;
  summary: string;
  artifact: string;
  gate: string;
}

export interface LabCandidateProposal {
  candidate_id: string;
  title: string;
  implementation_area: string;
  target_paths: string[];
  technique_tags: string[];
  source_signal_ids: string[];
}

export interface LabExperimentSpec {
  version: string;
  spec_id: string;
  risk: string;
  target_paths: string[];
  accepted_command_count: number;
  rejected_command_count: number;
  manual_promotion_required: boolean;
}

export interface LabEvaluationMetric {
  name: string;
  status: "pass" | "fail" | "pending";
  detail: string;
}

export interface LabEvaluationReport {
  version: string;
  report_id: string;
  spec_id: string;
  verdict: "pass" | "fail" | "needs_review";
  metrics: LabEvaluationMetric[];
  promotion_eligible: boolean;
  manual_review_required: boolean;
  failure_count: number;
  pending_count: number;
}

export interface LabCuratorDecision {
  version: string;
  decision_id: string;
  report_id: string;
  decision: string;
  promotion_allowed: boolean;
  operator_required: boolean;
  next_action: string;
  reason_reference: string;
}

export interface LabShadowRun {
  version: string;
  run_id: string;
  created_at: string;
  watch_tick: {
    signal_count: number;
    external_calls: number;
  };
  normalized_batch: {
    material_count: number;
    cluster_count: number;
    duplicate_count: number;
    novelty_score: number;
  };
  candidate: LabCandidateProposal;
  experiment_spec: LabExperimentSpec;
  evaluation_report: LabEvaluationReport;
  curator_decision: LabCuratorDecision;
  timeline: LabTimelineEvent[];
  execution_allowed: boolean;
  external_calls: number;
}

export interface LabRunDetail {
  run_id: string;
  idempotency_key: string;
  status: string;
  objective_reference: string;
  receipt: Record<string, unknown>;
  target_paths: string[];
  metadata: Record<string, unknown>;
  priority: number;
  attempts: number;
  max_attempts: number;
  inserted: boolean;
}

export interface LabRunEvent {
  event_id: number;
  run_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: string;
  attempts: number;
}

export type LabRuntimeStore =
  | {
      status: "live";
      run: LabRunDetail;
      events: LabRunEvent[];
    }
  | {
      status: "unavailable";
      events: LabRunEvent[];
    };

export interface LabDecisionMutationPayload {
  decision: "approve" | "reject" | "request_changes" | "cancel";
  decision_id?: string;
  note?: string;
}

export interface LabCancelMutationPayload {
  cancel_id?: string;
  reason?: string;
}

export interface LabControlMutationResponse {
  promotion_allowed: boolean;
  decision?: {
    run_id: string;
    changed: boolean;
    idempotent_replay: boolean;
    status: string | null;
    event_id: number | null;
  };
  cancel?: {
    run_id: string;
    changed: boolean;
    idempotent_replay: boolean;
    status: string | null;
    event_id: number | null;
  };
}

export interface LabControlRoomData {
  snapshot: LabSnapshot;
  runs: LabRunPreview[];
  scheduler: LabSchedulerStatus;
  runtimeStore: LabRuntimeStore;
  sandboxPolicy: LabSandboxPolicy;
  shadowRun: LabShadowRun;
  source: "backend" | "fallback";
  backendError?: string;
}

export const labSnapshot: LabSnapshot = {
  updatedAt: "2026-06-16",
  machine: "Pro",
  syncState: "Pro/Mini out of sync",
  doctrine: "state + sandbox + evaluator + curator",
  metrics: [
    { label: "Governance", value: "9 gates", tone: "good" },
    { label: "Runtime", value: "claim-ready", tone: "good" },
    { label: "Worker loop", value: "contracted", tone: "warn" },
    { label: "Promotion", value: "manual only", tone: "good" },
  ],
  stages: [
    {
      id: "watch",
      label: "Watch",
      status: "designing",
      owner: "Source adapters",
      gate: "freshness + novelty",
      gate_state: "pending",
      summary:
        "Frontier signals from papers, repos, SDK docs, MCP, and notebooks.",
      artifact: "FrontierSignal",
    },
    {
      id: "intake",
      label: "Intake",
      status: "live",
      owner: "Normalizer",
      gate: "receipt-safe",
      gate_state: "passed",
      summary:
        "Metadata-first ingestion with default hashing for external refs.",
      artifact: "ResearchMaterial",
    },
    {
      id: "plan",
      label: "Plan",
      status: "live",
      owner: "Planner",
      gate: "no raw text",
      gate_state: "passed",
      summary: "Drafts LabRun receipts and bounded verification plans.",
      artifact: "LabRun",
    },
    {
      id: "worker",
      label: "Worker",
      status: "planned",
      owner: "Durable runtime",
      gate: "heartbeat",
      gate_state: "pending",
      summary: "Claims queue rows and checkpoints every stage transition.",
      artifact: "LabCheckpoint",
    },
    {
      id: "arena",
      label: "Arena",
      status: "blocked",
      owner: "Sandbox runner",
      gate: "policy before execution",
      gate_state: "blocked",
      summary:
        "Runs only inside a declared filesystem, network, env, and timeout policy.",
      artifact: "SandboxRunResult",
    },
    {
      id: "tribunal",
      label: "Tribunal",
      status: "blocked",
      owner: "Evaluator",
      gate: "Law 2 + sandbox hard fail",
      gate_state: "blocked",
      summary:
        "Judges correctness, regression, leakage, cost, latency, and novelty.",
      artifact: "EvaluationReport",
    },
    {
      id: "curator",
      label: "Curator",
      status: "paused",
      owner: "Operator gate",
      gate: "manual decision",
      gate_state: "manual",
      summary:
        "Approves, rejects, cancels, or requests changes from compact evidence.",
      artifact: "CuratorDecision",
    },
    {
      id: "archive",
      label: "Archive",
      status: "planned",
      owner: "Learning library",
      gate: "approved summaries only",
      gate_state: "pending",
      summary: "Stores reusable technique summaries and failure taxonomy.",
      artifact: "TrajectorySummary",
    },
  ],
  lanes: [
    {
      name: "Backend organism",
      status: "Phase 0",
      next: "runtime contracts, worker skeleton, stage nodes",
      proof: "queued run reaches curator pause",
      tone: "warn",
    },
    {
      name: "Visual control room",
      status: "Phase 0",
      next: "read-only status, run preview, sandbox policy",
      proof: "UI mirrors every backend gate",
      tone: "good",
    },
    {
      name: "Safety arena",
      status: "Phase 1",
      next: "sandbox timeout runner, output redaction, evaluator schema",
      proof: "no command executes without policy",
      tone: "danger",
    },
  ],
  firstBatch: [
    {
      order: 1,
      title: "Lifecycle contracts",
      backend: "runtime_contracts.py",
      ui: "stage vocabulary and status tones",
      gate: "unknown states fail closed",
    },
    {
      order: 2,
      title: "Worker skeleton",
      backend: "worker.py",
      ui: "run timeline and heartbeat strip",
      gate: "one claimed run pauses at curator",
    },
    {
      order: 3,
      title: "Stage node interface",
      backend: "stages.py",
      ui: "canonical worker lifecycle",
      gate: "stage outputs are receipt-safe",
    },
    {
      order: 4,
      title: "Receipt store unification",
      backend: "planner.py + receipt_store.py",
      ui: "append-only receipt events",
      gate: "no overwrite and no raw text",
    },
    {
      order: 5,
      title: "Sandbox runner contract",
      backend: "sandbox_runner.py",
      ui: "timeout and redacted output",
      gate: "allowlisted commands only",
    },
    {
      order: 6,
      title: "Source adapters v1",
      backend: "source_adapters.py",
      ui: "watchtower signals",
      gate: "metadata-only shadow ticks",
    },
    {
      order: 7,
      title: "Normalizer and dedupe",
      backend: "normalizer.py",
      ui: "cluster and novelty readout",
      gate: "raw material never leaves envelope",
    },
    {
      order: 8,
      title: "Experiment spec",
      backend: "experiment_spec.py",
      ui: "candidate acceptance contract",
      gate: "manual promotion required",
    },
    {
      order: 9,
      title: "Evaluator tribunal",
      backend: "evaluator.py",
      ui: "policy, command, leakage, novelty verdict",
      gate: "pending checks cannot pass silently",
    },
    {
      order: 10,
      title: "Curator gate",
      backend: "curator.py",
      ui: "operator decision record",
      gate: "promotion_allowed remains false",
    },
    {
      order: 11,
      title: "Shadow run proof",
      backend: "shadow_run.py",
      ui: "watch-to-curate timeline",
      gate: "external_calls equals zero",
    },
    {
      order: 12,
      title: "Router shadow endpoint",
      backend: "autonomous_lab.py",
      ui: "control room data feed",
      gate: "internal API only",
    },
    {
      order: 13,
      title: "Sandbox hardening",
      backend: "sandbox_runner.py",
      ui: "command and env refusal receipts",
      gate: "no shell escape",
    },
    {
      order: 14,
      title: "Visual Lab panels",
      backend: "app/autonomous-lab/page.tsx",
      ui: "candidate, evaluator, curator, timeline",
      gate: "read-only UI",
    },
    {
      order: 15,
      title: "End-to-end shadow test",
      backend: "test_shadow_run.py",
      ui: "pipeline receipt proof",
      gate: "no network or subprocess side effects",
    },
  ],
  risks: [
    {
      label: "phantom safety",
      control: "evaluator-first lifecycle",
      tone: "danger",
    },
    {
      label: "raw leakage",
      control: "default hash + receipt tests",
      tone: "danger",
    },
    {
      label: "split brain",
      control: "placement policy + claim rules",
      tone: "warn",
    },
    {
      label: "over-frameworking",
      control: "local contracts before adapters",
      tone: "neutral",
    },
  ],
};

const fallbackRunPreview: LabRunPreview = {
  version: "autonomous-lab-v1-worker-skeleton",
  run_id: "lab-control-room-preview",
  created_at: "2026-06-16T00:00:00+00:00",
  paused_at_stage: "curate",
  execution_allowed: false,
  manual_promotion_required: true,
  blocked: false,
  checkpoints: [
    {
      order: 1,
      stage: "watch",
      status: "checkpointed",
      gate_state: "pending",
      artifact: "FrontierSignal",
      summary: "watch signal envelope accepted for planning",
      executed: false,
      external_calls: 0,
    },
    {
      order: 2,
      stage: "intake",
      status: "checkpointed",
      gate_state: "passed",
      artifact: "ResearchMaterial",
      summary: "materials normalized into receipt-safe fingerprints",
      executed: false,
      external_calls: 0,
    },
    {
      order: 3,
      stage: "compose",
      status: "checkpointed",
      gate_state: "passed",
      artifact: "LabRun",
      summary: "LabRun receipt drafted with verification plan",
      executed: false,
      external_calls: 0,
    },
    {
      order: 4,
      stage: "experiment",
      status: "planned",
      gate_state: "pending",
      artifact: "SandboxRunResult",
      summary: "sandbox runner waits for explicit policy-bound execution",
      executed: false,
      external_calls: 0,
    },
    {
      order: 5,
      stage: "curate",
      status: "paused",
      gate_state: "manual",
      artifact: "CuratorDecision",
      summary: "operator decision required before promotion",
      executed: false,
      external_calls: 0,
    },
  ],
};

const fallbackSchedulerStatus: LabSchedulerStatus = {
  version: "autonomous-lab-v1-h24-scheduler",
  updated_at: "2026-06-16T00:00:00+00:00",
  enabled: false,
  db_available: false,
  placement: {
    machine_role: "unknown",
    can_enqueue: false,
    can_claim_runs: false,
    can_consume_outbox: false,
    heavy_work_destination: "operator decision required",
    reason: "fallback control room data; backend scheduler status unavailable",
  },
  tick_interval_seconds: 60,
  worker_id: "lab-worker:fallback",
  state: "db_unavailable",
  can_tick: false,
  next_tick_not_before: "2026-06-16T00:01:00+00:00",
  next_action: "attach the runtime database before ticking the worker",
  tick_mode: "bounded_single_tick",
  autonomous_execution_allowed: false,
  manual_promotion_required: true,
  safeguards: [
    "single_tick_only",
    "internal_api_only",
    "db_required",
    "pro_run_execution_only",
    "manual_promotion_required",
    "no_deploy_merge_push",
  ],
};

const fallbackSandboxPolicy: LabSandboxPolicy = {
  version: "autonomous-lab-v1-sandbox-policy",
  filesystem: {
    mode: "read_only_repo_plus_artifacts",
    repo_read_only: true,
    writable_roots: [
      ".worktrees/<lane>-<task>/",
      "artifacts/autonomous_lab/",
      "tmp/autonomous_lab/",
    ],
    forbidden_roots: [
      "~/.ssh/",
      "~/.config/",
      "~/.claude/",
      "~/.codex/",
      "apps/backend-rag/.env",
      "apps/mouth/.env",
    ],
  },
  network: {
    mode: "deny_all",
    allowed_hosts: [],
    allow_localhost: false,
  },
  execution_limits: {
    timeout_seconds: 600,
    max_output_bytes: 1_000_000,
    max_artifact_bytes: 10_000_000,
    env_allowlist: ["CI", "NODE_ENV", "PATH", "PYTHONPATH"],
  },
  require_policy_before_execution: true,
  production_writes_allowed: false,
  deploy_merge_push_allowed: false,
  raw_data_persistence_allowed: false,
  stdout_redaction_required: true,
  prod_like_input_contract: "synthetic_or_redacted_fixtures_only",
};

const fallbackShadowRun: LabShadowRun = {
  version: "autonomous-lab-v1-shadow-run",
  run_id: "shadow-control-room-preview",
  created_at: "2026-06-16T00:00:00+00:00",
  watch_tick: {
    signal_count: 3,
    external_calls: 0,
  },
  normalized_batch: {
    material_count: 3,
    cluster_count: 3,
    duplicate_count: 0,
    novelty_score: 1,
  },
  candidate: {
    candidate_id: "shadow-control-room-preview-candidate",
    title: "title_fingerprint:sha256:control-room-preview",
    implementation_area:
      "agent-engineering-synthesis + codebase-pattern-mining + research-to-evaluator",
    target_paths: [
      "apps/backend-rag/backend/services/autonomous_lab",
      "apps/admin-dashboard/app/autonomous-lab",
    ],
    technique_tags: ["ai_frontier", "repo", "research", "software_frontier"],
    source_signal_ids: [
      "signal-1-preview",
      "signal-2-preview",
      "signal-3-preview",
    ],
  },
  experiment_spec: {
    version: "autonomous-lab-v1-experiment-spec",
    spec_id: "shadow-control-room-preview-spec",
    risk: "medium",
    target_paths: [
      "apps/backend-rag/backend/services/autonomous_lab",
      "apps/admin-dashboard/app/autonomous-lab",
    ],
    accepted_command_count: 1,
    rejected_command_count: 0,
    manual_promotion_required: true,
  },
  evaluation_report: {
    version: "autonomous-lab-v1-evaluator",
    report_id: "shadow-control-room-preview-spec-eval",
    spec_id: "shadow-control-room-preview-spec",
    verdict: "needs_review",
    metrics: [
      {
        name: "sandbox_policy",
        status: "pass",
        detail: "prod writes, deploy, push, and raw persistence are blocked",
      },
      {
        name: "sandbox_execution",
        status: "pending",
        detail: "shadow run has not executed commands",
      },
    ],
    promotion_eligible: false,
    manual_review_required: true,
    failure_count: 0,
    pending_count: 1,
  },
  curator_decision: {
    version: "autonomous-lab-v1-curator",
    decision_id: "shadow-control-room-preview-spec-eval-curator",
    report_id: "shadow-control-room-preview-spec-eval",
    decision: "request_changes",
    promotion_allowed: false,
    operator_required: true,
    next_action: "execute allowed sandbox checks or add missing evidence",
    reason_reference: "evaluator_verdict:needs_review",
  },
  timeline: [
    {
      order: 1,
      stage: "watch",
      status: "checkpointed",
      summary: "3 frontier signal(s), external_calls=0",
      artifact: "WatchtowerTick",
      gate: "freshness + novelty",
    },
    {
      order: 2,
      stage: "normalize",
      status: "checkpointed",
      summary: "3 cluster(s), duplicates=0",
      artifact: "NormalizedMaterialBatch",
      gate: "no raw receipt",
    },
    {
      order: 3,
      stage: "experiment",
      status: "planned",
      summary: "1 allowed command(s), 0 rejected",
      artifact: "ExperimentSpec",
      gate: "sandbox policy",
    },
    {
      order: 4,
      stage: "verify",
      status: "needs_review",
      summary: "failures=0, pending=1",
      artifact: "EvaluationReport",
      gate: "tribunal",
    },
    {
      order: 5,
      stage: "curate",
      status: "manual",
      summary: "execute allowed sandbox checks or add missing evidence",
      artifact: "CuratorDecision",
      gate: "operator decision",
    },
  ],
  execution_allowed: false,
  external_calls: 0,
};

export async function loadAutonomousLabControlRoomData(): Promise<LabControlRoomData> {
  const backendBase = autonomousLabBackendBase();
  const apiKey =
    process.env.AUTONOMOUS_LAB_API_KEY ?? process.env.INTERNAL_API_KEY;
  if (!backendBase || !apiKey) {
    return fallbackControlRoomData();
  }

  try {
    const [snapshot, runsResponse, scheduler, sandboxPolicy, shadowRun] =
      await Promise.all([
        fetchBackendJson<LabSnapshot>(backendBase, apiKey, "status"),
        fetchBackendJson<{ runs: LabRunPreview[] }>(
          backendBase,
          apiKey,
          "runs",
        ),
        fetchBackendJson<LabSchedulerStatus>(backendBase, apiKey, "scheduler"),
        fetchBackendJson<LabSandboxPolicy>(
          backendBase,
          apiKey,
          "sandbox-policy",
        ),
        fetchBackendJson<LabShadowRun>(backendBase, apiKey, "shadow-run"),
      ]);

    if (
      !snapshot ||
      !runsResponse ||
      !scheduler ||
      !sandboxPolicy ||
      !shadowRun
    ) {
      return fallbackControlRoomData(
        "backend returned an incomplete lab snapshot",
      );
    }
    if (!Array.isArray(runsResponse.runs) || runsResponse.runs.length === 0) {
      return fallbackControlRoomData("backend returned no lab run previews");
    }

    const runtimeStore = await loadRuntimeStore(
      backendBase,
      apiKey,
      runsResponse.runs[0]?.run_id,
    );

    return {
      snapshot,
      runs: runsResponse.runs,
      scheduler,
      runtimeStore,
      sandboxPolicy,
      shadowRun,
      source: "backend",
    };
  } catch (error) {
    return fallbackControlRoomData(
      error instanceof Error ? error.message : String(error),
    );
  }
}

function fallbackControlRoomData(backendError?: string): LabControlRoomData {
  return {
    snapshot: labSnapshot,
    runs: [fallbackRunPreview],
    scheduler: fallbackSchedulerStatus,
    runtimeStore: { status: "unavailable", events: [] },
    sandboxPolicy: fallbackSandboxPolicy,
    shadowRun: fallbackShadowRun,
    source: "fallback",
    backendError,
  };
}

async function loadRuntimeStore(
  backendBase: string,
  apiKey: string,
  runId: string | undefined,
): Promise<LabRuntimeStore> {
  if (!runId) {
    return { status: "unavailable", events: [] };
  }

  const encodedRunId = encodeURIComponent(runId);
  const [runResponse, eventsResponse] = await Promise.all([
    fetchBackendJson<{ run: LabRunDetail }>(
      backendBase,
      apiKey,
      `runs/${encodedRunId}`,
    ),
    fetchBackendJson<{ events: LabRunEvent[] }>(
      backendBase,
      apiKey,
      `runs/${encodedRunId}/events?limit=80`,
    ),
  ]);

  if (!runResponse?.run) {
    return { status: "unavailable", events: [] };
  }

  return {
    status: "live",
    run: runResponse.run,
    events: Array.isArray(eventsResponse?.events) ? eventsResponse.events : [],
  };
}

async function fetchBackendJson<T>(
  backendBase: string,
  apiKey: string,
  endpoint: string,
): Promise<T | null> {
  const response = await fetch(
    `${backendBase}/api/autonomous-lab/${endpoint}`,
    {
      headers: { "X-API-Key": apiKey },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as T;
}

export async function postAutonomousLabDecision(
  runId: string,
  payload: LabDecisionMutationPayload,
): Promise<LabControlMutationResponse> {
  return await postBackendJson<LabControlMutationResponse>(
    `runs/${encodeURIComponent(runId)}/decision`,
    payload,
  );
}

export async function postAutonomousLabCancel(
  runId: string,
  payload: LabCancelMutationPayload,
): Promise<LabControlMutationResponse> {
  return await postBackendJson<LabControlMutationResponse>(
    `runs/${encodeURIComponent(runId)}/cancel`,
    payload,
  );
}

async function postBackendJson<T>(
  endpoint: string,
  payload: unknown,
): Promise<T> {
  const config = autonomousLabBackendConfig();
  if (!config) {
    throw new Error("autonomous lab backend is not configured");
  }

  const response = await fetch(
    `${config.backendBase}/api/autonomous-lab/${endpoint}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": config.apiKey,
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(`autonomous lab backend returned ${response.status}`);
  }

  return (await response.json()) as T;
}

function autonomousLabBackendConfig():
  | { backendBase: string; apiKey: string }
  | undefined {
  const backendBase = autonomousLabBackendBase();
  const apiKey =
    process.env.AUTONOMOUS_LAB_API_KEY ?? process.env.INTERNAL_API_KEY;
  if (!backendBase || !apiKey) {
    return undefined;
  }
  return { backendBase, apiKey };
}

function autonomousLabBackendBase(): string | undefined {
  const raw =
    process.env.AUTONOMOUS_LAB_BACKEND_URL ??
    process.env.BACKEND_RAG_URL ??
    process.env.NUZANTARA_RAG_URL;
  return raw?.replace(/\/+$/, "");
}
