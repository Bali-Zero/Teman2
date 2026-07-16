"use strict";

const HIGH_CONFIDENCE_THRESHOLD = 0.7;
const TEXT_PARSER_MIN_CHARS = 100;
const DEFAULT_QWEN_MODEL = "qwen3.5:9b";
const AUTOCATALOG_DRY_RUN_COMMAND =
  "cd ~/nuzantara && source apps/backend-rag/.venv/bin/activate && " +
  "python scripts/intake_reprocess_backlog.py --autocatalog-direct-unknown-text";
const AUTOCATALOG_APPLY_COMMAND = `${AUTOCATALOG_DRY_RUN_COMMAND} --apply`;

function workspaceBucketForDocType(docType) {
  const key = String(docType || "unknown").toLowerCase();
  if (["passport", "kitas", "itas", "itap", "itk", "visa", "birth_certificate", "medical_insurance", "travel_ticket"].includes(key)) {
    return "immigration";
  }
  if (["nib", "akta_pendirian", "oss", "sk_kemenkumham", "profil_perseroan", "skt"].includes(key)) {
    return "company";
  }
  if (["npwp"].includes(key)) return "tax";
  if (["bank_statement", "payment_receipt"].includes(key)) return "finance";
  if (["ktp"].includes(key)) return "identity";
  return "review";
}

function parserBucketForRow(row) {
  const docType = row.doc_type || "unknown";
  const proposalStatus = row.proposal_status || "NO_PROPOSAL";
  const decision = row.entity_decision || "NO_PROPOSAL";
  const highConfidence = Number(row.type_confidence || 0) >= HIGH_CONFIDENCE_THRESHOLD;
  const hasNonStubRoute = !!row.routed_non_stub;
  if (row.queue_status === "dead") return "failed_pipeline";
  if (docType === "unknown") return "needs_doc_type_parser";
  if (!highConfidence) return "low_confidence_review";
  if (proposalStatus === "routed") return "already_routed";
  if (decision === "AUTO_ATTACH" || decision === "LINK_CANDIDATE" || hasNonStubRoute) {
    return "workspace_review_ready";
  }
  return "needs_routing_proposal";
}

function actionBucketForRow(row) {
  if (row.queue_status === "dead") return "failed_pipeline";
  const docType = row.doc_type || "unknown";
  if (docType !== "unknown") return parserBucketForRow(row);

  const ocrChars = Number(row.ocr_chars || 0);
  if (ocrChars <= 0) return "needs_ocr_vision_batch";
  if (ocrChars < TEXT_PARSER_MIN_CHARS) return "needs_manual_review_short_ocr";
  return "needs_text_parser_qwen_candidate";
}

function buildDirectActionSummary(rows) {
  const summary = {
    needs_ocr_vision_batch: 0,
    needs_text_parser_qwen_candidate: 0,
    needs_manual_review_short_ocr: 0,
    workspace_review_ready: 0,
    needs_routing_proposal: 0,
    low_confidence_review: 0,
    already_routed: 0,
    failed_pipeline: 0,
    immediate_batch_candidates: 0,
  };

  for (const row of rows || []) {
    const bucket = row.bucket;
    const docs = Number(row.docs || 0);
    if (Object.prototype.hasOwnProperty.call(summary, bucket)) {
      summary[bucket] += docs;
    }
  }

  summary.immediate_batch_candidates =
    summary.needs_ocr_vision_batch + summary.needs_text_parser_qwen_candidate;
  return summary;
}

function buildDirectCatalogSummary(directActionSummary, queue, qwenPlacementPreview) {
  const directDocs = Number(queue?.direct_docs || 0);
  const bucketedDocs =
    Number(directActionSummary?.needs_ocr_vision_batch || 0) +
    Number(directActionSummary?.needs_text_parser_qwen_candidate || 0) +
    Number(directActionSummary?.needs_manual_review_short_ocr || 0) +
    Number(directActionSummary?.workspace_review_ready || 0) +
    Number(directActionSummary?.needs_routing_proposal || 0) +
    Number(directActionSummary?.low_confidence_review || 0) +
    Number(directActionSummary?.already_routed || 0) +
    Number(directActionSummary?.failed_pipeline || 0);
  const scopeDelta = bucketedDocs - directDocs;
  const workspaceReviewReadyDocs = Number(directActionSummary?.workspace_review_ready || 0);
  const routingProposalNeededDocs = Number(directActionSummary?.needs_routing_proposal || 0);
  const qwenTextCandidateDocs = Number(directActionSummary?.needs_text_parser_qwen_candidate || 0);
  const ocrVisionCandidateDocs = Number(directActionSummary?.needs_ocr_vision_batch || 0);
  const manualReviewDocs =
    Number(directActionSummary?.needs_manual_review_short_ocr || 0) +
    Number(directActionSummary?.low_confidence_review || 0);

  return {
    status: scopeDelta === 0 ? "consistent" : "scope_mismatch",
    direct_docs: directDocs,
    bucketed_docs: bucketedDocs,
    scope_delta: scopeDelta,
    known_doc_type_docs: Number(queue?.direct_known_docs || 0),
    unknown_doc_type_docs: Number(queue?.direct_unknown_docs || 0),
    already_routed_docs: Number(directActionSummary?.already_routed || 0),
    workspace_review_ready_docs: workspaceReviewReadyDocs,
    routing_proposal_needed_docs: routingProposalNeededDocs,
    catalog_review_ready_docs: workspaceReviewReadyDocs + routingProposalNeededDocs,
    machine_batch_candidate_docs: ocrVisionCandidateDocs + qwenTextCandidateDocs,
    qwen_text_candidate_docs: qwenTextCandidateDocs,
    ocr_vision_candidate_docs: ocrVisionCandidateDocs,
    manual_review_docs: manualReviewDocs,
    failed_pipeline_docs: Number(directActionSummary?.failed_pipeline || 0),
    qwen_sampled_docs: Number(qwenPlacementPreview?.sampled_docs || 0),
    qwen_sample_workspace_candidates: Number(qwenPlacementPreview?.kita_workspace_candidates || 0),
    qwen_sample_review_after_qwen: Number(qwenPlacementPreview?.review_after_qwen || 0),
  };
}

function projectRows(rows, totalDocs, denominator, keyFields) {
  const safeTotal = Number(totalDocs || 0);
  const safeDenominator = Number(denominator || 0);
  if (safeTotal <= 0 || safeDenominator <= 0 || !Array.isArray(rows)) return [];
  return rows
    .map((row) => {
      const sampleDocs = Number(row.docs || 0);
      const projected = {};
      for (const field of keyFields) projected[field] = String(row[field] || "");
      projected.sample_docs = sampleDocs;
      projected.projected_docs = Math.round((safeTotal * sampleDocs) / safeDenominator);
      return projected;
    })
    .filter((row) => row.sample_docs > 0);
}

function buildAutocatalogPlanSummary(
  directActionSummary,
  qwenBatchGate,
  qwenKnownBenchmark,
  qwenPlacementPreview,
) {
  const qwenTextDocs = Number(directActionSummary?.needs_text_parser_qwen_candidate || 0);
  const visionDocs = Number(directActionSummary?.needs_ocr_vision_batch || 0);
  const shortOcrDocs = Number(directActionSummary?.needs_manual_review_short_ocr || 0);
  const lowConfidenceDocs = Number(directActionSummary?.low_confidence_review || 0);
  const routingDocs = Number(directActionSummary?.needs_routing_proposal || 0);
  const workspaceReviewDocs = Number(directActionSummary?.workspace_review_ready || 0);
  const alreadyRoutedDocs = Number(directActionSummary?.already_routed || 0);
  const failedDocs = Number(directActionSummary?.failed_pipeline || 0);
  const qwenStatus = String(qwenBatchGate?.status || "probe_required");
  const benchmarkStatus = String(qwenKnownBenchmark?.status || "benchmark_required");

  let status = "needs_more_sampling";
  let reason = "qwen_gates_inconclusive";
  if (qwenTextDocs <= 0) {
    status = "no_text_candidates";
    reason = "no_unknown_direct_docs_with_enough_saved_ocr";
  } else if (qwenStatus === "candidate_batch_ready" && benchmarkStatus === "workspace_benchmark_ready") {
    status = "ready_for_staged_autocatalog";
    reason = "qwen_text_gate_and_known_doc_benchmark_passed";
  } else if (qwenStatus === "probe_required") {
    status = "needs_qwen_text_probe";
    reason = "qwen_text_probe_missing";
  } else if (benchmarkStatus === "benchmark_required") {
    status = "needs_known_doc_benchmark";
    reason = "known_doc_benchmark_missing";
  } else if (qwenStatus === "insufficient_sample" || qwenStatus === "review_only") {
    status = "text_batch_review_only";
    reason = String(qwenBatchGate?.reason || "qwen_text_gate_not_ready");
  } else if (benchmarkStatus !== "workspace_benchmark_ready") {
    status = "benchmark_review";
    reason = String(qwenKnownBenchmark?.reason || "qwen_known_doc_benchmark_not_ready");
  }

  const denominator = Number(qwenBatchGate?.classified_attempts || qwenPlacementPreview?.classified_attempts || 0);
  const candidateRate = Number(qwenBatchGate?.candidate_rate || 0);
  const projectedKitaDocs = denominator > 0 ? Math.round(qwenTextDocs * candidateRate) : 0;
  const projectedReviewDocs = denominator > 0 ? Math.max(qwenTextDocs - projectedKitaDocs, 0) : qwenTextDocs;

  return {
    status,
    reason,
    scope: "direct_whatsapp_docs_only_groups_excluded",
    write_mode: "proposal_only_no_crm_mutation",
    worker_required_env: {
      INTAKE_TEXT_LLM_CLASSIFY_ENABLED: "1",
      INTAKE_TEXT_LLM_MODEL: DEFAULT_QWEN_MODEL,
      INTAKE_TEXT_LLM_MIN_CHARS: String(TEXT_PARSER_MIN_CHARS),
      INTAKE_TEXT_LLM_TIMEOUT_SECONDS: "45",
    },
    dry_run_command: AUTOCATALOG_DRY_RUN_COMMAND,
    apply_command: AUTOCATALOG_APPLY_COMMAND,
    safe_to_apply_without_existing_gate: false,
    can_create_kita_proposals: status === "ready_for_staged_autocatalog",
    can_auto_attach_without_review: false,
    qwen_text_gate_status: qwenStatus,
    known_doc_benchmark_status: benchmarkStatus,
    totals: {
      qwen_text_candidate_docs: qwenTextDocs,
      ocr_vision_candidate_docs: visionDocs,
      short_ocr_review_docs: shortOcrDocs,
      low_confidence_review_docs: lowConfidenceDocs,
      routing_proposal_needed_docs: routingDocs,
      workspace_review_ready_docs: workspaceReviewDocs,
      already_routed_docs: alreadyRoutedDocs,
      failed_pipeline_docs: failedDocs,
      projected_qwen_text_to_kita_docs: projectedKitaDocs,
      projected_qwen_text_to_review_docs: projectedReviewDocs,
    },
    projected_qwen_workspace_buckets: projectRows(
      qwenPlacementPreview?.workspace_buckets || [],
      qwenTextDocs,
      denominator,
      ["bucket"],
    ),
    projected_qwen_placements: projectRows(
      qwenPlacementPreview?.placement_preview || [],
      qwenTextDocs,
      denominator,
      ["from_doc_type", "proposed_doc_type", "workspace_bucket"],
    ),
    stages: [
      {
        stage: "qwen_text_autocatalog",
        docs: qwenTextDocs,
        source_bucket: "needs_text_parser_qwen_candidate",
        llm: DEFAULT_QWEN_MODEL,
        destination: "document_routing_proposal_then_kita_workspace_by_doc_type",
        allowed_when: "candidate_batch_ready_and_workspace_benchmark_ready",
        expected_kita_docs: projectedKitaDocs,
        expected_review_docs: projectedReviewDocs,
        auto_attach_allowed: false,
      },
      {
        stage: "vision_ocr_autocatalog",
        docs: visionDocs,
        source_bucket: "needs_ocr_vision_batch",
        llm: "qwen2.5vl_local_ocr_then_qwen_text_router",
        destination: "same_proposal_path_after_ocr",
        allowed_when: "local_vision_ocr_available_on_pro",
        expected_kita_docs: 0,
        expected_review_docs: visionDocs,
        auto_attach_allowed: false,
      },
      {
        stage: "short_ocr_resolution",
        docs: shortOcrDocs,
        source_bucket: "needs_manual_review_short_ocr",
        llm: "vision_retry_or_manual_review",
        destination: "review_or_same_proposal_path_after_better_ocr",
        allowed_when: "ocr_text_below_threshold",
        expected_kita_docs: 0,
        expected_review_docs: shortOcrDocs,
        auto_attach_allowed: false,
      },
      {
        stage: "known_doc_routing",
        docs: routingDocs,
        source_bucket: "needs_routing_proposal",
        llm: "none",
        destination: "document_routing_proposal_review_pending",
        allowed_when: "known_doc_type_high_confidence",
        expected_kita_docs: routingDocs,
        expected_review_docs: 0,
        auto_attach_allowed: false,
      },
      {
        stage: "workspace_operator_review",
        docs: workspaceReviewDocs + lowConfidenceDocs,
        source_bucket: "workspace_review_ready_or_low_confidence_review",
        llm: "none",
        destination: "kita_review_queue",
        allowed_when: "operator_or_existing_auto_attach_gate",
        expected_kita_docs: workspaceReviewDocs,
        expected_review_docs: lowConfidenceDocs,
        auto_attach_allowed: false,
      },
    ],
  };
}

function groupKindAction(kind) {
  switch (kind) {
    case "small_client_group_likely":
      return "review_client_group";
    case "multi_party_case_likely":
      return "review_case_group";
    case "large_or_broadcast_group":
      return "quarantine_broadcast_group";
    case "team_coordination_likely":
      return "exclude_team_coordination";
    default:
      return "manual_group_review";
  }
}

function buildGroupKindOperationalSummary(rows) {
  const groupKinds = (rows || []).map((row) => {
    const unsafeGroups = Number(
      row.unsafe_groups ?? Math.max(Number(row.unsafe_sender_groups || 0), Number(row.unsafe_hint_groups || 0)),
    );
    return {
      inferred_group_kind: String(row.inferred_group_kind || "unknown"),
      intake_action: groupKindAction(row.inferred_group_kind),
      safety_status: unsafeGroups > 0 ? "source_context_review" : "aggregate_safe",
      auto_attach_allowed: false,
      groups: Number(row.groups || 0),
      docs: Number(row.docs || 0),
      done_docs: Number(row.done_docs || 0),
      dead_docs: Number(row.dead_docs || 0),
      unsafe_groups: unsafeGroups,
      unsafe_sender_groups: Number(row.unsafe_sender_groups || 0),
      unsafe_hint_groups: Number(row.unsafe_hint_groups || 0),
      median_docs_per_group: Number(row.median_docs_per_group || 0),
      max_docs_per_group: Number(row.max_docs_per_group || 0),
    };
  });

  const totals = groupKinds.reduce(
    (acc, row) => {
      acc.total_groups += row.groups;
      acc.total_docs += row.docs;
      acc.unsafe_groups += row.unsafe_groups;
      return acc;
    },
    { total_groups: 0, total_docs: 0, unsafe_groups: 0 },
  );

  return {
    status: totals.unsafe_groups > 0 ? "source_context_review" : "aggregate_safe",
    total_groups: totals.total_groups,
    total_docs: totals.total_docs,
    unsafe_groups: totals.unsafe_groups,
    auto_attach_allowed: false,
    group_kinds: groupKinds,
  };
}

function buildQwenBatchGateSummary(directActionSummary, probeSnapshot) {
  const candidateDocs = Number(directActionSummary?.needs_text_parser_qwen_candidate || 0);
  const qwenSample = probeSnapshot?.qwen_text_sample || probeSnapshot || null;
  const gate = qwenSample?.acceptance_gate || null;
  const generatedAt = probeSnapshot?.generated_at || null;

  if (!candidateDocs) {
    return {
      status: "no_candidates",
      reason: "no_text_parser_candidates",
      candidate_docs: 0,
      sampled_docs: Number(qwenSample?.attempted || 0),
      classified_attempts: Number(gate?.classified_attempts || qwenSample?.classified_attempts || 0),
      candidate_rate: Number(gate?.candidate_rate || 0),
      min_candidate_rate: Number(gate?.min_candidate_rate || 0.25),
      kita_workspace_candidates: Number(qwenSample?.kita_workspace_candidates || 0),
      review_after_qwen: Number(qwenSample?.review_after_qwen || 0),
      generated_at: generatedAt,
    };
  }

  if (!gate) {
    return {
      status: "probe_required",
      reason: "no_qwen_probe_snapshot",
      candidate_docs: candidateDocs,
      sampled_docs: 0,
      classified_attempts: 0,
      candidate_rate: 0,
      min_candidate_rate: 0.25,
      kita_workspace_candidates: 0,
      review_after_qwen: 0,
      generated_at: null,
    };
  }

  return {
    status: String(gate.status || "probe_required"),
    reason: String(gate.reason || "unknown"),
    candidate_docs: candidateDocs,
    sampled_docs: Number(qwenSample.attempted || 0),
    classified_attempts: Number(gate.classified_attempts || qwenSample.classified_attempts || 0),
    candidate_rate: Number(gate.candidate_rate || 0),
    min_candidate_rate: Number(gate.min_candidate_rate || 0.25),
    kita_workspace_candidates: Number(qwenSample.kita_workspace_candidates || 0),
    review_after_qwen: Number(qwenSample.review_after_qwen || 0),
    generated_at: generatedAt,
  };
}

function buildQwenKnownBenchmarkSummary(probeSnapshot) {
  const benchmark = probeSnapshot?.qwen_known_benchmark || null;
  const gate = benchmark?.benchmark_gate || null;
  const generatedAt = probeSnapshot?.generated_at || null;

  if (!gate) {
    return {
      status: "benchmark_required",
      reason: "no_qwen_known_benchmark_snapshot",
      sampled_docs: Number(benchmark?.attempted || 0),
      classified_attempts: Number(benchmark?.classified_attempts || 0),
      failed_attempts: Number(benchmark?.failed_attempts || 0),
      exact_doc_type_matches: Number(benchmark?.exact_doc_type_matches || 0),
      workspace_matches: Number(benchmark?.workspace_matches || 0),
      unknown_predictions: Number(benchmark?.unknown_predictions || 0),
      exact_doc_type_accuracy: Number(benchmark?.exact_doc_type_accuracy || 0),
      workspace_accuracy: Number(benchmark?.workspace_accuracy || 0),
      min_workspace_accuracy: 0.7,
      generated_at: generatedAt,
      confusion_preview: [],
    };
  }

  return {
    status: String(gate.status || "benchmark_required"),
    reason: String(gate.reason || "unknown"),
    sampled_docs: Number(benchmark.attempted || 0),
    classified_attempts: Number(gate.classified_attempts || benchmark.classified_attempts || 0),
    failed_attempts: Number(benchmark.failed_attempts || 0),
    exact_doc_type_matches: Number(benchmark.exact_doc_type_matches || 0),
    workspace_matches: Number(benchmark.workspace_matches || 0),
    unknown_predictions: Number(benchmark.unknown_predictions || 0),
    exact_doc_type_accuracy: Number(benchmark.exact_doc_type_accuracy || 0),
    workspace_accuracy: Number(gate.workspace_accuracy || benchmark.workspace_accuracy || 0),
    min_workspace_accuracy: Number(gate.min_workspace_accuracy || 0.7),
    generated_at: generatedAt,
    confusion_preview: Array.isArray(benchmark.confusion_preview) ? benchmark.confusion_preview : [],
  };
}

function sanitizeWorkspaceBuckets(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    bucket: String(row.bucket || "review"),
    docs: Number(row.docs || 0),
  }));
}

function sanitizePlacementPreview(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => ({
    from_doc_type: String(row.from_doc_type || "unknown"),
    proposed_doc_type: String(row.proposed_doc_type || "unknown"),
    workspace_bucket: String(row.workspace_bucket || workspaceBucketForDocType(row.proposed_doc_type)),
    docs: Number(row.docs || 0),
  }));
}

function buildQwenPlacementPreviewSummary(probeSnapshot) {
  const qwenSample = probeSnapshot?.qwen_text_sample || probeSnapshot || null;
  const gate = qwenSample?.acceptance_gate || null;
  const generatedAt = probeSnapshot?.generated_at || null;

  if (!gate) {
    return {
      status: "probe_required",
      reason: "no_qwen_probe_snapshot",
      sampled_docs: Number(qwenSample?.attempted || 0),
      classified_attempts: Number(qwenSample?.classified_attempts || 0),
      kita_workspace_candidates: Number(qwenSample?.kita_workspace_candidates || 0),
      review_after_qwen: Number(qwenSample?.review_after_qwen || 0),
      still_unknown: Number(qwenSample?.still_unknown || 0),
      generated_at: generatedAt,
      workspace_buckets: sanitizeWorkspaceBuckets(qwenSample?.workspace_buckets),
      placement_preview: sanitizePlacementPreview(qwenSample?.placement_preview),
    };
  }

  return {
    status: String(gate.status || "probe_required"),
    reason: String(gate.reason || "unknown"),
    sampled_docs: Number(qwenSample.attempted || 0),
    classified_attempts: Number(gate.classified_attempts || qwenSample.classified_attempts || 0),
    kita_workspace_candidates: Number(qwenSample.kita_workspace_candidates || 0),
    review_after_qwen: Number(qwenSample.review_after_qwen || 0),
    still_unknown: Number(qwenSample.still_unknown || 0),
    generated_at: generatedAt,
    workspace_buckets: sanitizeWorkspaceBuckets(qwenSample.workspace_buckets),
    placement_preview: sanitizePlacementPreview(qwenSample.placement_preview),
  };
}

module.exports = {
  HIGH_CONFIDENCE_THRESHOLD,
  TEXT_PARSER_MIN_CHARS,
  actionBucketForRow,
  buildDirectCatalogSummary,
  buildAutocatalogPlanSummary,
  buildDirectActionSummary,
  buildGroupKindOperationalSummary,
  buildQwenKnownBenchmarkSummary,
  buildQwenBatchGateSummary,
  buildQwenPlacementPreviewSummary,
  parserBucketForRow,
  workspaceBucketForDocType,
};
