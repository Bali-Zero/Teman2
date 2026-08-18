import type {
  EvidenceRefView,
  GuaranteeBasis,
} from "@/lib/api/secondhome/secondhome.types";

/**
 * Mirrors `E33Case.guarantee_evidence_complete` in e33_lifecycle.py: basis
 * proof collected (bank_confirmation for deposit / property_title for
 * property) AND filed to Immigration (an immigration_filing entry with a
 * filed date).
 *
 * UI-only convenience — the backend is authoritative and rejects
 * guarantee_proof_due → annual_maintenance with 409 when this is false
 * (2026-08-19 hardening). Used only to proactively disable that transition
 * option instead of letting the user hit the 409.
 */
export function isGuaranteeEvidenceComplete(
  basis: GuaranteeBasis,
  evidence: EvidenceRefView[],
): boolean {
  const basisKind =
    basis === "deposit" ? "bank_confirmation" : "property_title";
  const hasBasisProof = evidence.some((e) => e.kind === basisKind);
  const hasFiledProof = evidence.some(
    (e) => e.kind === "immigration_filing" && Boolean(e.filed_date),
  );
  return hasBasisProof && hasFiledProof;
}
