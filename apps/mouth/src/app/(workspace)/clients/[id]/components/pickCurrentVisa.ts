import type { ClientDocument } from "@/lib/api/crm/crm.types";

const VISA_TYPE_MARKERS = ["visa", "kitas", "kitap", "e-visa", "evisa"];

const isVisaDocument = (doc: ClientDocument): boolean =>
  doc.document_category === "immigration" &&
  VISA_TYPE_MARKERS.some((marker) =>
    doc.document_type?.toLowerCase().includes(marker),
  );

const toTime = (value?: string | null): number =>
  value ? Date.parse(value) || 0 : 0;

// The client's current visa/KITAS for the Overview card.
//
// Candidates: the client's own immigration visa/KITAS/KITAP documents (no
// family member), not removed by the client in the portal (deleted_at) and
// not archived by the team.
//
// Among dated documents the farthest expiry wins, as before. A document with
// no expiry_date yet wins only when it was uploaded AFTER that one: a new
// KITAS whose dates are not filled in is the current permit, and selecting it
// lets the card's auto-OCR fill its dates. Before this, an undated document
// always sorted last, so a new KITAS stayed hidden behind the old visa and was
// never sent to OCR (client 10247, 6 Oct).
export const pickCurrentVisa = (
  documents: ClientDocument[],
): ClientDocument | undefined => {
  const candidates = documents.filter(
    (doc) =>
      isVisaDocument(doc) &&
      !doc.family_member_id &&
      !doc.deleted_at &&
      !doc.is_archived,
  );

  let dated: ClientDocument | undefined;
  let undated: ClientDocument | undefined;
  for (const doc of candidates) {
    if (doc.expiry_date) {
      const diff = dated
        ? toTime(doc.expiry_date) - toTime(dated.expiry_date)
        : 1;
      if (diff > 0 || (diff === 0 && dated && doc.id > dated.id)) dated = doc;
    } else {
      const diff = undated
        ? toTime(doc.created_at) - toTime(undated.created_at)
        : 1;
      if (diff > 0 || (diff === 0 && undated && doc.id > undated.id))
        undated = doc;
    }
  }

  if (!dated) return undated;
  if (undated && toTime(undated.created_at) > toTime(dated.created_at)) {
    return undated;
  }
  return dated;
};
