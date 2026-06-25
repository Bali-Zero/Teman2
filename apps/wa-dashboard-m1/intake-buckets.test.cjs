"use strict";

const assert = require("node:assert/strict");

const {
  actionBucketForRow,
  buildDirectActionSummary,
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
