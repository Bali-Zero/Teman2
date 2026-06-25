"use strict";

const assert = require("node:assert/strict");

const {
  actionBucketForRow,
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
    failed_pipeline: 5,
    immediate_batch_candidates: 898,
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
