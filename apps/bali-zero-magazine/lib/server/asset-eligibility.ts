export type AssetEligibilityState = Readonly<{
  alt_text: string;
  source: string;
  rights_basis: string;
  rights_status: string;
  usage_status: string;
  dlp_status: string;
  sanitization_status: string;
  perceptual_dedup_status: string;
  status: string;
}>;

const APPROVED_RIGHTS_BASES = [
  "internal-owned",
  "licensed",
  "public-domain",
  "official-use",
  "generated",
] as const;

const APPROVED_DEDUP_STATUSES = ["unique", "intentional-reuse"] as const;
const APPROVED_RIGHTS_BASES_SQL = APPROVED_RIGHTS_BASES.map(
  (basis) => `'${basis}'`,
).join(", ");
const APPROVED_DEDUP_STATUSES_SQL = APPROVED_DEDUP_STATUSES.map(
  (status) => `'${status}'`,
).join(", ");

export function assetEligibilitySql(alias: string): string {
  if (!/^[a-z][a-z0-9_]*$/i.test(alias)) {
    throw new TypeError("asset SQL alias is invalid");
  }
  return `length(trim(${alias}.alt_text)) > 0
    AND length(trim(${alias}.source)) > 0
    AND ${alias}.rights_basis IN (${APPROVED_RIGHTS_BASES_SQL})
    AND COALESCE((
      SELECT latest_status.status FROM asset_status_events latest_status
      WHERE latest_status.asset_id = ${alias}.asset_id
      ORDER BY latest_status.status_seq DESC LIMIT 1
    ), ${alias}.status) = 'verified'
    AND COALESCE((
      SELECT latest_rights.rights_status FROM asset_status_events latest_rights
      WHERE latest_rights.asset_id = ${alias}.asset_id
      ORDER BY latest_rights.status_seq DESC LIMIT 1
    ), ${alias}.rights_status) = 'approved'
    AND ${alias}.usage_status = 'approved'
    AND ${alias}.dlp_status = 'passed'
    AND ${alias}.sanitization_status = 'passed'
    AND ${alias}.perceptual_dedup_status IN (${APPROVED_DEDUP_STATUSES_SQL})`;
}

export function isAssetEligible(asset: AssetEligibilityState): boolean {
  return (
    asset.alt_text.trim().length > 0 &&
    asset.source.trim().length > 0 &&
    APPROVED_RIGHTS_BASES.some((basis) => basis === asset.rights_basis) &&
    asset.rights_status === "approved" &&
    asset.usage_status === "approved" &&
    asset.dlp_status === "passed" &&
    asset.sanitization_status === "passed" &&
    APPROVED_DEDUP_STATUSES.some(
      (status) => status === asset.perceptual_dedup_status,
    ) &&
    asset.status === "verified"
  );
}
