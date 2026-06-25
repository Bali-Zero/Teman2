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

module.exports = {
  HIGH_CONFIDENCE_THRESHOLD,
  TEXT_PARSER_MIN_CHARS,
  actionBucketForRow,
  buildDirectActionSummary,
  parserBucketForRow,
  workspaceBucketForDocType,
};
