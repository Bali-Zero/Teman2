export type GenderCode = "M" | "F";

/**
 * The `clients.gender` column holds two spellings of the same value:
 * passport OCR writes "M" / "F" (crm_enhanced.py, crm_clients_documents.py),
 * while PATCH /api/crm/clients/{id} normalises its input to "male" / "female"
 * (ClientUpdate.normalize_gender in crm_clients.py). Every reader goes through
 * this function so both spellings display the same way. Anything else
 * (empty, "other", unknown) is treated as not set.
 */
export function genderCode(value?: string | null): GenderCode | null {
  const v = value?.trim().toLowerCase();
  if (v === "m" || v === "male") return "M";
  if (v === "f" || v === "female") return "F";
  return null;
}
