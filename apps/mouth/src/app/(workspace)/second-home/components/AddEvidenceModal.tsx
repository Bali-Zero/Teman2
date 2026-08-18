"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Save, ShieldAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { ApiError } from "@/lib/api/error-handler";
import {
  addEvidenceSchema,
  flattenErrors,
} from "@/lib/api/secondhome/secondhome.schemas";
import type { EvidenceKind } from "@/lib/api/secondhome/secondhome.types";
import { useAddSecondHomeEvidence } from "@/hooks/useSecondHome";

const KIND_OPTIONS: { value: EvidenceKind; label: string }[] = [
  { value: "bank_confirmation", label: "Bank confirmation" },
  { value: "property_title", label: "Property title" },
  { value: "immigration_filing", label: "Immigration filing" },
  { value: "immigration_receipt", label: "Immigration receipt" },
  { value: "other", label: "Other" },
];

const inputClass =
  "w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-2)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50";
const labelClass = "text-xs font-medium text-[var(--bz-text-2)] mb-1 block";

export function AddEvidenceModal({
  caseId,
  onClose,
}: {
  caseId: string;
  onClose: () => void;
}) {
  const toast = useToast();
  const addEvidence = useAddSecondHomeEvidence(caseId);

  const [kind, setKind] = useState<EvidenceKind>("bank_confirmation");
  const [documentRef, setDocumentRef] = useState("");
  const [issuingParty, setIssuingParty] = useState("");
  const [issuedOn, setIssuedOn] = useState("");
  const [filedOn, setFiledOn] = useState("");
  const [note, setNote] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !addEvidence.isPending) onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose, addEvidence.isPending]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFieldErrors({});

    const result = addEvidenceSchema.safeParse({
      kind,
      document_ref: documentRef,
      issuing_party: issuingParty,
      issued_on: issuedOn,
      filed_on: filedOn,
      note,
    });

    if (!result.success) {
      setFieldErrors(flattenErrors(result.error));
      return;
    }

    try {
      await addEvidence.mutateAsync(result.data);
      toast.success(
        "Evidence Added",
        "Evidence reference attached to the case.",
      );
      onClose();
    } catch (error) {
      logger.error(
        "Failed to add second-home evidence",
        {
          component: "AddEvidenceModal",
          action: "addEvidence",
          itemId: caseId,
        },
        toError(error),
      );
      // Surface the backend 422 custody-violation message VERBATIM.
      const message =
        error instanceof ApiError
          ? error.detail || error.message
          : "Failed to add evidence";
      toast.error("Error", message);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => !addEvidence.isPending && onClose()}
      />
      <div className="relative bg-[var(--bz-base)] border border-[var(--bz-border)] rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col mx-4">
        <div className="flex items-center justify-between p-5 border-b border-[var(--bz-border)]">
          <h2 className="text-lg font-semibold text-[var(--bz-text-1)]">
            Add Evidence
          </h2>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            disabled={addEvidence.isPending}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="overflow-y-auto flex-1">
          <div className="p-5 space-y-4">
            <div className="flex gap-2 rounded-lg border border-[color-mix(in_srgb,var(--state-warning)_35%,transparent)] bg-[color-mix(in_srgb,var(--state-warning)_10%,transparent)] p-3 text-xs text-[var(--state-warning)]">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <p>
                Evidence references only — never account numbers, balances or
                amounts.
              </p>
            </div>

            <div>
              <label className={labelClass}>Kind</label>
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as EvidenceKind)}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                {KIND_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelClass}>Document Reference</label>
              <input
                type="text"
                value={documentRef}
                onChange={(e) => setDocumentRef(e.target.value)}
                className={inputClass}
                placeholder="Drive file id or CRM document id"
              />
              {fieldErrors.document_ref && (
                <p className="text-xs text-[var(--state-danger)] mt-1">
                  {fieldErrors.document_ref}
                </p>
              )}
            </div>

            <div>
              <label className={labelClass}>
                Issuing Party{" "}
                <span className="text-[var(--bz-text-2)] font-normal">
                  (optional)
                </span>
              </label>
              <input
                type="text"
                value={issuingParty}
                onChange={(e) => setIssuingParty(e.target.value)}
                className={inputClass}
                placeholder="e.g. Bank Mandiri, notary office"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>
                  Issued On{" "}
                  <span className="text-[var(--bz-text-2)] font-normal">
                    (optional)
                  </span>
                </label>
                <input
                  type="date"
                  value={issuedOn}
                  onChange={(e) => setIssuedOn(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>
                  Filed On{" "}
                  <span className="text-[var(--bz-text-2)] font-normal">
                    (optional)
                  </span>
                </label>
                <input
                  type="date"
                  value={filedOn}
                  onChange={(e) => setFiledOn(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <div>
              <label className={labelClass}>
                Note{" "}
                <span className="text-[var(--bz-text-2)] font-normal">
                  (optional)
                </span>
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                className={`${inputClass} resize-none`}
                placeholder="Internal context — never account/amount data"
              />
            </div>
          </div>
          <div className="flex items-center justify-end gap-3 p-5 border-t border-[var(--bz-border)] bg-[var(--bz-surface)] mt-auto">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={addEvidence.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={addEvidence.isPending || !documentRef}
              className="gap-2"
            >
              {addEvidence.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Add Evidence
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
