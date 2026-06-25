"use strict";

const HIGH_CONFIDENCE_THRESHOLD = 0.7;
const TEXT_PARSER_MIN_CHARS = 100;

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
  buildDirectActionSummary,
  buildGroupKindOperationalSummary,
  buildQwenKnownBenchmarkSummary,
  buildQwenBatchGateSummary,
  buildQwenPlacementPreviewSummary,
  parserBucketForRow,
  workspaceBucketForDocType,
};
