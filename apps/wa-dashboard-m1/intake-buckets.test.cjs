"use strict";

const assert = require("node:assert/strict");

const {
  actionBucketForRow,
  buildAutocatalogPlanSummary,
  buildDirectCatalogSummary,
  buildGroupKindOperationalSummary,
  buildQwenBatchGateSummary,
  buildDirectActionSummary,
  buildQwenKnownBenchmarkSummary,
  buildQwenPlacementPreviewSummary,
  parserBucketForRow,
  workspaceBucketForDocType,
} = require("./intake-buckets.cjs");

assert.equal(workspaceBucketForDocType("passport"), "immigration");
assert.equal(workspaceBucketForDocType("npwp"), "tax");
assert.equal(workspaceBucketForDocType("unknown"), "review");

assert.equal(parserBucketForRow({ queue_status: "dead" }), "failed_pipeline");
assert.equal(parserBucketForRow({ doc_type: "unknown" }), "needs_doc_type_parser");
assert.equal(parserBucketForRow({ doc_type: "passport", type_confidence: 0.5 }), "low_confidence_review");
assert.equal(
  parserBucketForRow({ doc_type: "passport", type_confidence: 0.8, entity_decision: "AUTO_ATTACH" }),
  "workspace_review_ready",
);

assert.equal(actionBucketForRow({ queue_status: "dead", doc_type: "unknown", ocr_chars: 500 }), "failed_pipeline");
assert.equal(actionBucketForRow({ doc_type: "unknown", ocr_chars: 0 }), "needs_ocr_vision_batch");
assert.equal(actionBucketForRow({ doc_type: "unknown", ocr_chars: 99 }), "needs_manual_review_short_ocr");
assert.equal(actionBucketForRow({ doc_type: "unknown", ocr_chars: 100 }), "needs_text_parser_qwen_candidate");
assert.equal(actionBucketForRow({ doc_type: "passport", type_confidence: 0.8, routed_non_stub: true }), "workspace_review_ready");

assert.deepEqual(
  buildDirectActionSummary([
    { bucket: "needs_ocr_vision_batch", docs: 592 },
    { bucket: "needs_text_parser_qwen_candidate", docs: 306 },
    { bucket: "needs_manual_review_short_ocr", docs: 98 },
    { bucket: "workspace_review_ready", docs: 255 },
    { bucket: "failed_pipeline", docs: 5 },
  ]),
  {
    needs_ocr_vision_batch: 592,
    needs_text_parser_qwen_candidate: 306,
    needs_manual_review_short_ocr: 98,
    workspace_review_ready: 255,
    needs_routing_proposal: 0,
    low_confidence_review: 0,
    already_routed: 0,
    failed_pipeline: 5,
    immediate_batch_candidates: 898,
  },
);

assert.deepEqual(
  buildDirectCatalogSummary(
    {
      needs_ocr_vision_batch: 592,
      needs_text_parser_qwen_candidate: 306,
      needs_manual_review_short_ocr: 98,
      workspace_review_ready: 255,
      needs_routing_proposal: 49,
      low_confidence_review: 347,
      already_routed: 16,
      failed_pipeline: 4,
      immediate_batch_candidates: 898,
    },
    {
      direct_docs: 1667,
      direct_known_docs: 670,
      direct_unknown_docs: 997,
    },
    {
      sampled_docs: 50,
      kita_workspace_candidates: 25,
      review_after_qwen: 25,
    },
  ),
  {
    status: "consistent",
    direct_docs: 1667,
    bucketed_docs: 1667,
    scope_delta: 0,
    known_doc_type_docs: 670,
    unknown_doc_type_docs: 997,
    already_routed_docs: 16,
    workspace_review_ready_docs: 255,
    routing_proposal_needed_docs: 49,
    catalog_review_ready_docs: 304,
    machine_batch_candidate_docs: 898,
    qwen_text_candidate_docs: 306,
    ocr_vision_candidate_docs: 592,
    manual_review_docs: 445,
    failed_pipeline_docs: 4,
    qwen_sampled_docs: 50,
    qwen_sample_workspace_candidates: 25,
    qwen_sample_review_after_qwen: 25,
  },
);

assert.deepEqual(
  buildGroupKindOperationalSummary([
    {
      inferred_group_kind: "small_client_group_likely",
      groups: 44,
      docs: 409,
      done_docs: 407,
      dead_docs: 0,
      unsafe_groups: 1,
      unsafe_sender_groups: 1,
      unsafe_hint_groups: 0,
      median_docs_per_group: 2,
      max_docs_per_group: 80,
      group_subject: "SHOULD_NOT_LEAK",
    },
    {
      inferred_group_kind: "team_coordination_likely",
      groups: 12,
      docs: 173,
      done_docs: 171,
      dead_docs: 2,
      unsafe_groups: 0,
      unsafe_sender_groups: 0,
      unsafe_hint_groups: 0,
      median_docs_per_group: 12,
      max_docs_per_group: 31,
    },
  ]),
  {
    status: "source_context_review",
    total_groups: 56,
    total_docs: 582,
    unsafe_groups: 1,
    auto_attach_allowed: false,
    group_kinds: [
      {
        inferred_group_kind: "small_client_group_likely",
        intake_action: "review_client_group",
        safety_status: "source_context_review",
        auto_attach_allowed: false,
        groups: 44,
        docs: 409,
        done_docs: 407,
        dead_docs: 0,
        unsafe_groups: 1,
        unsafe_sender_groups: 1,
        unsafe_hint_groups: 0,
        median_docs_per_group: 2,
        max_docs_per_group: 80,
      },
      {
        inferred_group_kind: "team_coordination_likely",
        intake_action: "exclude_team_coordination",
        safety_status: "aggregate_safe",
        auto_attach_allowed: false,
        groups: 12,
        docs: 173,
        done_docs: 171,
        dead_docs: 2,
        unsafe_groups: 0,
        unsafe_sender_groups: 0,
        unsafe_hint_groups: 0,
        median_docs_per_group: 12,
        max_docs_per_group: 31,
      },
    ],
  },
);

assert.deepEqual(
  buildQwenBatchGateSummary(
    { needs_text_parser_qwen_candidate: 306 },
    {
      generated_at: "2026-06-26T04:00:00.000Z",
      qwen_text_sample: {
        attempted: 5,
        kita_workspace_candidates: 1,
        review_after_qwen: 4,
        acceptance_gate: {
          status: "review_only",
          reason: "candidate_rate_below_threshold",
          candidate_rate: 0.2,
          min_candidate_rate: 0.25,
          classified_attempts: 5,
          min_classified_attempts: 5,
        },
      },
    },
  ),
  {
    status: "review_only",
    reason: "candidate_rate_below_threshold",
    candidate_docs: 306,
    sampled_docs: 5,
    classified_attempts: 5,
    candidate_rate: 0.2,
    min_candidate_rate: 0.25,
    kita_workspace_candidates: 1,
    review_after_qwen: 4,
    generated_at: "2026-06-26T04:00:00.000Z",
  },
);

assert.deepEqual(
  buildQwenBatchGateSummary({ needs_text_parser_qwen_candidate: 306 }, null),
  {
    status: "probe_required",
    reason: "no_qwen_probe_snapshot",
    candidate_docs: 306,
    sampled_docs: 0,
    classified_attempts: 0,
    candidate_rate: 0,
    min_candidate_rate: 0.25,
    kita_workspace_candidates: 0,
    review_after_qwen: 0,
    generated_at: null,
  },
);

assert.deepEqual(
  buildQwenPlacementPreviewSummary({
    generated_at: "2026-06-26T05:00:00.000Z",
    qwen_text_sample: {
      attempted: 50,
      classified_attempts: 50,
      still_unknown: 25,
      kita_workspace_candidates: 25,
      review_after_qwen: 25,
      acceptance_gate: {
        status: "candidate_batch_ready",
        reason: "candidate_rate_met",
      },
      workspace_buckets: [
        { bucket: "review", docs: 25 },
        { bucket: "immigration", docs: 15 },
        { bucket: "finance", docs: 10 },
      ],
      placement_preview: [
        {
          from_doc_type: "unknown",
          proposed_doc_type: "travel_ticket",
          workspace_bucket: "immigration",
          docs: 9,
        },
        {
          from_doc_type: "unknown",
          proposed_doc_type: "payment_receipt",
          workspace_bucket: "finance",
          docs: 6,
        },
      ],
      raw_ocr_text: "SHOULD_NOT_LEAK",
      sender_phone: "+6280000000000",
    },
  }),
  {
    status: "candidate_batch_ready",
    reason: "candidate_rate_met",
    sampled_docs: 50,
    classified_attempts: 50,
    kita_workspace_candidates: 25,
    review_after_qwen: 25,
    still_unknown: 25,
    generated_at: "2026-06-26T05:00:00.000Z",
    workspace_buckets: [
      { bucket: "review", docs: 25 },
      { bucket: "immigration", docs: 15 },
      { bucket: "finance", docs: 10 },
    ],
    placement_preview: [
      {
        from_doc_type: "unknown",
        proposed_doc_type: "travel_ticket",
        workspace_bucket: "immigration",
        docs: 9,
      },
      {
        from_doc_type: "unknown",
        proposed_doc_type: "payment_receipt",
        workspace_bucket: "finance",
        docs: 6,
      },
    ],
  },
);

assert.deepEqual(
  buildQwenPlacementPreviewSummary(null),
  {
    status: "probe_required",
    reason: "no_qwen_probe_snapshot",
    sampled_docs: 0,
    classified_attempts: 0,
    kita_workspace_candidates: 0,
    review_after_qwen: 0,
    still_unknown: 0,
    generated_at: null,
    workspace_buckets: [],
    placement_preview: [],
  },
);

assert.deepEqual(
  buildQwenKnownBenchmarkSummary({
    generated_at: "2026-06-26T04:30:00.000Z",
    qwen_known_benchmark: {
      attempted: 10,
      classified_attempts: 10,
      failed_attempts: 0,
      exact_doc_type_matches: 9,
      workspace_matches: 9,
      unknown_predictions: 1,
      exact_doc_type_accuracy: 0.9,
      workspace_accuracy: 0.9,
      benchmark_gate: {
        status: "workspace_benchmark_ready",
        reason: "workspace_accuracy_met",
        workspace_accuracy: 0.9,
        min_workspace_accuracy: 0.7,
        classified_attempts: 10,
        min_classified_attempts: 5,
      },
      confusion_preview: [
        {
          expected_doc_type: "visa",
          predicted_doc_type: "unknown",
          expected_workspace_bucket: "immigration",
          predicted_workspace_bucket: "review",
          docs: 1,
        },
      ],
      raw_ocr_text: "SHOULD_NOT_LEAK",
    },
  }),
  {
    status: "workspace_benchmark_ready",
    reason: "workspace_accuracy_met",
    sampled_docs: 10,
    classified_attempts: 10,
    failed_attempts: 0,
    exact_doc_type_matches: 9,
    workspace_matches: 9,
    unknown_predictions: 1,
    exact_doc_type_accuracy: 0.9,
    workspace_accuracy: 0.9,
    min_workspace_accuracy: 0.7,
    generated_at: "2026-06-26T04:30:00.000Z",
    confusion_preview: [
      {
        expected_doc_type: "visa",
        predicted_doc_type: "unknown",
        expected_workspace_bucket: "immigration",
        predicted_workspace_bucket: "review",
        docs: 1,
      },
    ],
  },
);

assert.deepEqual(
  buildQwenKnownBenchmarkSummary(null),
  {
    status: "benchmark_required",
    reason: "no_qwen_known_benchmark_snapshot",
    sampled_docs: 0,
    classified_attempts: 0,
    failed_attempts: 0,
    exact_doc_type_matches: 0,
    workspace_matches: 0,
    unknown_predictions: 0,
    exact_doc_type_accuracy: 0,
    workspace_accuracy: 0,
    min_workspace_accuracy: 0.7,
    generated_at: null,
    confusion_preview: [],
  },
);

assert.deepEqual(
  buildAutocatalogPlanSummary(
    {
      needs_ocr_vision_batch: 592,
      needs_text_parser_qwen_candidate: 306,
      needs_manual_review_short_ocr: 98,
      workspace_review_ready: 255,
      needs_routing_proposal: 48,
      low_confidence_review: 347,
      already_routed: 16,
      failed_pipeline: 5,
    },
    {
      status: "candidate_batch_ready",
      reason: "candidate_rate_met",
      candidate_docs: 306,
      sampled_docs: 50,
      classified_attempts: 50,
      candidate_rate: 0.5,
      kita_workspace_candidates: 25,
      review_after_qwen: 25,
    },
    {
      status: "workspace_benchmark_ready",
      reason: "workspace_accuracy_met",
      classified_attempts: 10,
      workspace_accuracy: 0.9,
    },
    {
      classified_attempts: 50,
      workspace_buckets: [
        { bucket: "review", docs: 25 },
        { bucket: "immigration", docs: 15 },
        { bucket: "finance", docs: 10 },
      ],
      placement_preview: [
        {
          from_doc_type: "unknown",
          proposed_doc_type: "travel_ticket",
          workspace_bucket: "immigration",
          docs: 9,
        },
        {
          from_doc_type: "unknown",
          proposed_doc_type: "payment_receipt",
          workspace_bucket: "finance",
          docs: 6,
        },
      ],
      raw_ocr_text: "SHOULD_NOT_LEAK",
      sender_phone: "+6280000000000",
    },
  ),
  {
    status: "ready_for_staged_autocatalog",
    reason: "qwen_text_gate_and_known_doc_benchmark_passed",
    scope: "direct_whatsapp_docs_only_groups_excluded",
    write_mode: "proposal_only_no_crm_mutation",
    worker_required_env: {
      INTAKE_TEXT_LLM_CLASSIFY_ENABLED: "1",
      INTAKE_TEXT_LLM_MODEL: "qwen3.5:9b",
      INTAKE_TEXT_LLM_MIN_CHARS: "100",
      INTAKE_TEXT_LLM_TIMEOUT_SECONDS: "45",
    },
    dry_run_command:
      "cd ~/nuzantara && source apps/backend-rag/.venv/bin/activate && " +
      "python scripts/intake_reprocess_backlog.py --autocatalog-direct-unknown-text",
    apply_command:
      "cd ~/nuzantara && source apps/backend-rag/.venv/bin/activate && " +
      "python scripts/intake_reprocess_backlog.py --autocatalog-direct-unknown-text --apply",
    safe_to_apply_without_existing_gate: false,
    can_create_kita_proposals: true,
    can_auto_attach_without_review: false,
    qwen_text_gate_status: "candidate_batch_ready",
    known_doc_benchmark_status: "workspace_benchmark_ready",
    totals: {
      qwen_text_candidate_docs: 306,
      ocr_vision_candidate_docs: 592,
      short_ocr_review_docs: 98,
      low_confidence_review_docs: 347,
      routing_proposal_needed_docs: 48,
      workspace_review_ready_docs: 255,
      already_routed_docs: 16,
      failed_pipeline_docs: 5,
      projected_qwen_text_to_kita_docs: 153,
      projected_qwen_text_to_review_docs: 153,
    },
    projected_qwen_workspace_buckets: [
      { bucket: "review", sample_docs: 25, projected_docs: 153 },
      { bucket: "immigration", sample_docs: 15, projected_docs: 92 },
      { bucket: "finance", sample_docs: 10, projected_docs: 61 },
    ],
    projected_qwen_placements: [
      {
        from_doc_type: "unknown",
        proposed_doc_type: "travel_ticket",
        workspace_bucket: "immigration",
        sample_docs: 9,
        projected_docs: 55,
      },
      {
        from_doc_type: "unknown",
        proposed_doc_type: "payment_receipt",
        workspace_bucket: "finance",
        sample_docs: 6,
        projected_docs: 37,
      },
    ],
    stages: [
      {
        stage: "qwen_text_autocatalog",
        docs: 306,
        source_bucket: "needs_text_parser_qwen_candidate",
        llm: "qwen3.5:9b",
        destination: "document_routing_proposal_then_kita_workspace_by_doc_type",
        allowed_when: "candidate_batch_ready_and_workspace_benchmark_ready",
        expected_kita_docs: 153,
        expected_review_docs: 153,
        auto_attach_allowed: false,
      },
      {
        stage: "vision_ocr_autocatalog",
        docs: 592,
        source_bucket: "needs_ocr_vision_batch",
        llm: "qwen2.5vl_local_ocr_then_qwen_text_router",
        destination: "same_proposal_path_after_ocr",
        allowed_when: "local_vision_ocr_available_on_pro",
        expected_kita_docs: 0,
        expected_review_docs: 592,
        auto_attach_allowed: false,
      },
      {
        stage: "short_ocr_resolution",
        docs: 98,
        source_bucket: "needs_manual_review_short_ocr",
        llm: "vision_retry_or_manual_review",
        destination: "review_or_same_proposal_path_after_better_ocr",
        allowed_when: "ocr_text_below_threshold",
        expected_kita_docs: 0,
        expected_review_docs: 98,
        auto_attach_allowed: false,
      },
      {
        stage: "known_doc_routing",
        docs: 48,
        source_bucket: "needs_routing_proposal",
        llm: "none",
        destination: "document_routing_proposal_review_pending",
        allowed_when: "known_doc_type_high_confidence",
        expected_kita_docs: 48,
        expected_review_docs: 0,
        auto_attach_allowed: false,
      },
      {
        stage: "workspace_operator_review",
        docs: 602,
        source_bucket: "workspace_review_ready_or_low_confidence_review",
        llm: "none",
        destination: "kita_review_queue",
        allowed_when: "operator_or_existing_auto_attach_gate",
        expected_kita_docs: 255,
        expected_review_docs: 347,
        auto_attach_allowed: false,
      },
    ],
  },
);

assert.equal(
  buildAutocatalogPlanSummary(
    { needs_text_parser_qwen_candidate: 10 },
    { status: "candidate_batch_ready", candidate_rate: 0.8, classified_attempts: 5 },
    { status: "benchmark_required" },
    { classified_attempts: 5 },
  ).status,
  "needs_known_doc_benchmark",
);
