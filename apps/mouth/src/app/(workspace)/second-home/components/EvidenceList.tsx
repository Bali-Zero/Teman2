import { FileText } from "lucide-react";
import type { EvidenceRefView } from "@/lib/api/secondhome/secondhome.types";

const KIND_LABELS: Record<string, string> = {
  bank_confirmation: "Bank confirmation",
  property_title: "Property title",
  immigration_filing: "Immigration filing",
  immigration_receipt: "Immigration receipt",
  other: "Other",
};

export function EvidenceList({ evidence }: { evidence: EvidenceRefView[] }) {
  if (evidence.length === 0) {
    return (
      <p className="text-xs text-[var(--bz-text-2)] py-2">
        No evidence recorded yet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {evidence.map((item) => (
        <div
          key={item.evidence_id}
          className="flex items-start gap-2 p-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)]/40"
        >
          <FileText className="w-3.5 h-3.5 text-[var(--bz-text-2)] mt-0.5 shrink-0" />
          <div className="min-w-0 text-xs">
            <p className="font-medium text-[var(--bz-text-1)]">
              {KIND_LABELS[item.kind] || item.kind}
            </p>
            <p className="text-[var(--bz-text-2)] truncate">
              {item.document_ref}
            </p>
            <p className="text-[10px] text-[var(--bz-text-2)]">
              {item.issued_date ? `Issued ${item.issued_date}` : ""}
              {item.filed_date ? ` · Filed ${item.filed_date}` : ""}
              {item.confirmed_by ? ` · Verified by ${item.confirmed_by}` : ""}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
