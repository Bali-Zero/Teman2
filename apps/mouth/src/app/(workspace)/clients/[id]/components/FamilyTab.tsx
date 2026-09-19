"use client";

import React, { useRef, useState } from "react";
import {
  Download,
  Edit2,
  Eye,
  Loader2,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  CellStack,
  EmptyState,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  LedgerSection,
  Numeral,
  StatePill,
} from "@/components/workspace/r19";
import { useOcrPolling } from "@/hooks/useOcrPolling";
import { api } from "@/lib/api";
import type { ClientDocument, FamilyMember } from "@/lib/api/crm/crm.types";
import { fileToBase64 } from "@/lib/utils";
import { extractDriveFileId } from "./utils";

type DocumentKind = "passport" | "visa";

function FamilyMemberUploadButton({
  clientId,
  memberId,
  memberName,
  documentType,
  onRefresh,
}: {
  clientId: number;
  memberId: number;
  memberName: string;
  documentType: DocumentKind;
  onRefresh: () => Promise<void> | void;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { ocrPolling, pollOcrStatus } = useOcrPolling({
    clientId,
    onDone: onRefresh,
  });
  const label = `${documentType === "passport" ? "Passport" : "Visa"}`;
  // The old button's visible word changed with the request state (OLD:126-129
  // — "Uploading..." / "OCR in corso...") and the icon-only rebuild dropped
  // it silently, leaving a spinner with a static accessible name (r19 law:
  // a state never travels without a word). Restored here on the name itself
  // rather than as new visible copy, so the control stays icon-only.
  const statusLabel = isUploading
    ? `Uploading ${documentType} for ${memberName}`
    : ocrPolling
      ? `OCR in corso for ${memberName}`
      : `Upload ${documentType} for ${memberName}`;

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const allowedTypes = [
      "image/jpeg",
      "image/jpg",
      "image/png",
      "application/pdf",
    ];
    if (!allowedTypes.includes(file.type)) {
      toast.error("Invalid file type", {
        description: "Please upload JPG, PNG, or PDF",
      });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File too large", { description: "Maximum 10MB" });
      return;
    }

    setIsUploading(true);
    try {
      const response = (await api.post(
        `/api/crm/clients/${clientId}/documents/upload`,
        {
          file: await fileToBase64(file),
          file_name: file.name,
          document_type: documentType,
          mime_type: file.type,
          family_member_id: memberId,
        },
      )) as { success: boolean; message?: string };
      if (response.success) {
        toast.success(`${label} uploaded for ${memberName} — OCR in corso...`);
        pollOcrStatus();
      } else {
        toast.error("Upload failed", { description: response.message });
      }
    } catch (error) {
      toast.error("Upload failed", { description: (error as Error).message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.pdf"
        className="hidden"
        onChange={handleUpload}
        disabled={isUploading || ocrPolling}
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]"
        aria-label={statusLabel}
        title={statusLabel}
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading || ocrPolling}
      >
        {isUploading || ocrPolling ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Upload className="h-4 w-4" />
        )}
      </Button>
    </>
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function ageAtPresent(dateOfBirth: string) {
  return Math.floor(
    (Date.now() - new Date(dateOfBirth).getTime()) / (365.25 * 86400000),
  );
}

/** The old file's exact word for each alert level (FamilyTab.tsx@HEAD~2
 * lines 411-415 passport / 565-569 visa, identical wording both fields) —
 * every enum value the old file distinguished stays distinguishable. */
function alertWord(alert: "yellow" | "red" | "expired") {
  if (alert === "expired") return "Expired";
  if (alert === "red") return "Expiring soon";
  return "Renewal recommended";
}

/**
 * The visa pill is sourced from the server-computed `visa_alert` enum, not
 * from a client-side day-count — the enum already decides expiring-vs-valid
 * (r19 law #1: copper is never derived from a raw status string, and where
 * ownership is not derivable the tone is `wait`; there is no ownership
 * signal on a family member, so this never returns `you`).
 */
function visaPill(alert: FamilyMember["visa_alert"], hasType: boolean) {
  if (alert === "green") return { tone: "ok" as const, label: "Valid" };
  if (alert === "yellow" || alert === "red" || alert === "expired")
    return { tone: "wait" as const, label: alertWord(alert) };
  return {
    tone: "wait" as const,
    label: hasType ? "Visa on file" : "No visa",
  };
}

/**
 * Passport has no pill in this grid, so its urgency lives on the date cell
 * itself (word + weight, never a copper tone) — same mechanism as
 * `ObligationsTable`'s `isDueSoon`. When the expiry date is known the
 * countdown wording can only come from the date (the enum still gates
 * whether it is urgent); when it is not known — mirroring the old file's
 * own fallback — the enum's own word carries the state instead.
 */
function passportUrgency(
  expiry: string | undefined,
  alert: FamilyMember["passport_alert"],
  hasData: boolean,
) {
  if (expiry) {
    const daysLeft = Math.ceil(
      (new Date(expiry).getTime() - Date.now()) / 86400000,
    );
    const label =
      daysLeft < 0
        ? `Expired ${Math.abs(daysLeft)}d ago`
        : daysLeft === 0
          ? "Expires today"
          : daysLeft <= 365
            ? `⏰ ${daysLeft}d left`
            : `${Math.floor(daysLeft / 30)}mo left`;
    const urgent = alert ? alert !== "green" : daysLeft <= 180;
    return { label, urgent };
  }
  if (hasData && alert && alert !== "green") {
    return { label: alertWord(alert), urgent: true };
  }
  return undefined;
}

function DocumentActionButton({
  action,
  documentType,
  memberName,
  url,
}: {
  action: "view" | "download";
  documentType: DocumentKind;
  memberName: string;
  url: string;
}) {
  const label = `${action === "view" ? "View" : "Download"} ${documentType} for ${memberName}`;
  const Icon = action === "view" ? Eye : Download;

  const onClick = () => {
    const fileId = extractDriveFileId(url);
    if (!fileId) return;
    const proxyUrl = `/api/documents/proxy/${fileId}`;
    if (action === "view") {
      window.open(proxyUrl, "_blank", "noopener,noreferrer");
      return;
    }
    const link = document.createElement("a");
    link.href = proxyUrl;
    link.download = `${documentType}_${memberName.replace(/\s+/g, "_")}.jpg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="h-8 w-8 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]"
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}

function MemberActions({
  clientId,
  member,
  passportDocument,
  visaDocument,
  onEditClick,
  onRefresh,
  onDelete,
}: {
  clientId: number;
  member: FamilyMember;
  passportDocument?: ClientDocument;
  visaDocument?: ClientDocument;
  onEditClick: (member: FamilyMember) => void;
  onRefresh: () => Promise<void> | void;
  onDelete: (id: number, name: string) => void;
}) {
  const documentControls = (
    documentType: DocumentKind,
    document?: ClientDocument,
  ) => (
    <React.Fragment key={documentType}>
      {document?.google_drive_file_url ? (
        <>
          <DocumentActionButton
            action="view"
            documentType={documentType}
            memberName={member.full_name}
            url={document.google_drive_file_url}
          />
          <DocumentActionButton
            action="download"
            documentType={documentType}
            memberName={member.full_name}
            url={document.google_drive_file_url}
          />
        </>
      ) : null}
      <FamilyMemberUploadButton
        clientId={clientId}
        memberId={member.id}
        memberName={member.full_name}
        documentType={documentType}
        onRefresh={onRefresh}
      />
    </React.Fragment>
  );

  return (
    <div className="flex min-h-11 items-center justify-end gap-0.5 px-2.5 max-[640px]:justify-start">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]"
        aria-label={`Edit ${member.full_name}`}
        title={`Edit ${member.full_name}`}
        onClick={() => onEditClick(member)}
      >
        <Edit2 className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]"
        aria-label={`Remove ${member.full_name}`}
        title={`Remove ${member.full_name}`}
        onClick={() => onDelete(member.id, member.full_name)}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
      {documentControls("passport", passportDocument)}
      {documentControls("visa", visaDocument)}
    </div>
  );
}

export function FamilyTab({
  clientId,
  familyMembers,
  documents,
  formatDate,
  onAddClick,
  onEditClick,
  onRefresh,
}: {
  clientId: number;
  familyMembers: FamilyMember[];
  documents: ClientDocument[];
  formatDate: (date: string) => string;
  onAddClick: () => void;
  onEditClick: (member: FamilyMember) => void;
  onRefresh: () => Promise<void> | void;
}) {
  const handleDelete = (id: number, name: string) => {
    toast(`Remove ${name} from family members?`, {
      action: {
        label: "Remove",
        onClick: async () => {
          try {
            await api.crm.deleteFamilyMember(clientId, id);
            toast.success("Family member removed");
            await onRefresh();
          } catch (error) {
            toast.error("Error", { description: (error as Error).message });
          }
        },
      },
      cancel: { label: "Cancel", onClick: () => toast.dismiss() },
    });
  };

  const addAction = (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="gap-2 border-[var(--line-control)] text-[var(--tx-pure)] hover:bg-[var(--bz-card)]"
      aria-label="Add family member"
      onClick={onAddClick}
    >
      <Plus className="h-4 w-4" />
      Add family member
    </Button>
  );

  return (
    <LedgerSection
      n={6}
      title={
        <span className="flex items-baseline gap-2">
          Family <Numeral n={familyMembers.length} size="count" />
        </span>
      }
      actions={addAction}
    >
      {familyMembers.length === 0 ? (
        <EmptyState>No family members on file.</EmptyState>
      ) : (
        <HairlineGrid
          cols="minmax(16rem, 1.8fr) minmax(9rem, 1fr) minmax(10rem, 0.9fr) minmax(18rem, auto)"
          // `colsCollapsed` + `collapseAt` + `id` is inert on this primitive
          // (#6520, see ObligationsTable ~471-487): the collapse stylesheet
          // sets `--cols` under a media query, and an inline style already
          // sets `--cols` on the same element, so the rule never wins
          // without `!important`. This overrides the template on the rows
          // themselves instead, which does win.
          className="max-[640px]:[&_.grid]:!grid-cols-[minmax(0,1fr)]"
        >
          <HairlineHead className="max-[640px]:hidden">
            <span>Member</span>
            <span>Visa</span>
            <span>Expires</span>
            <span>Actions</span>
          </HairlineHead>
          <HairlineBody>
            {familyMembers.map((member) => {
              const memberDocuments = documents.filter(
                (document) => document.family_member_id === member.id,
              );
              const passportDocument = memberDocuments.find((document) =>
                document.document_type?.toLowerCase().includes("passport"),
              );
              const visaDocument = memberDocuments.find((document) => {
                const type = document.document_type?.toLowerCase();
                return type?.includes("kitas") || type?.includes("visa");
              });
              const visaExpiry =
                member.visa_expiry ?? visaDocument?.expiry_date;
              const passportExpiry =
                member.passport_expiry ?? passportDocument?.expiry_date;
              // No `?? visaDocument?.document_type` fallback: a document on
              // file with nothing extracted yet is not a visa TYPE, it is
              // OCR pending — see the note rendered below.
              const visaType = member.current_visa_type;
              const pill = visaPill(member.visa_alert, Boolean(visaType));
              const passportUrgencyInfo = passportUrgency(
                passportExpiry,
                member.passport_alert,
                Boolean(member.passport_number || passportDocument),
              );
              const personalDetails = [
                member.date_of_birth
                  ? `Born ${formatDate(member.date_of_birth)} · ${ageAtPresent(member.date_of_birth)}y`
                  : undefined,
                member.email,
                member.phone,
                member.passport_number
                  ? `Passport ${member.passport_number}`
                  : undefined,
              ].filter(Boolean);

              return (
                <HairlineRow
                  key={member.id}
                  data-testid={`family-member-row-${member.id}`}
                >
                  <div className="min-w-0 px-2.5 py-3">
                    <CellStack
                      primary={
                        <span className="flex min-w-0 items-center gap-3">
                          <span
                            aria-hidden="true"
                            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] bg-[var(--bz-card)] text-sm text-[var(--tx-pure)]"
                          >
                            {initials(member.full_name)}
                          </span>
                          <span className="truncate">{member.full_name}</span>
                        </span>
                      }
                      secondary={[member.relationship, member.nationality]
                        .filter(Boolean)
                        .join(" · ")}
                    />
                    {personalDetails.length > 0 || member.notes ? (
                      <div className="mt-2 space-y-1 text-xs text-[var(--tx-secondary)]">
                        {personalDetails.length > 0 ? (
                          <p>{personalDetails.join(" · ")}</p>
                        ) : null}
                        {member.notes ? <p>Notes: {member.notes}</p> : null}
                      </div>
                    ) : null}
                  </div>
                  <div className="px-2.5 py-3">
                    <CellStack
                      primary={
                        visaType ?? (visaDocument ? "—" : "No visa on file")
                      }
                      secondary={
                        <StatePill tone={pill.tone} label={pill.label} />
                      }
                    />
                    {visaDocument && !visaType ? (
                      <p className="mt-1 text-xs text-[var(--tx-secondary)]">
                        Document on file — upload to extract data via OCR
                      </p>
                    ) : null}
                  </div>
                  <div className="space-y-1 px-2.5 py-3 text-[13px] text-[var(--tx-pure)]">
                    {visaExpiry ? <p>{formatDate(visaExpiry)}</p> : <p>—</p>}
                    {passportUrgencyInfo ? (
                      <p
                        className="text-xs"
                        style={{
                          color: passportUrgencyInfo.urgent
                            ? "var(--state-warning)"
                            : "var(--tx-secondary)",
                        }}
                      >
                        Passport: {passportUrgencyInfo.label}
                      </p>
                    ) : null}
                    {passportDocument && !member.passport_number ? (
                      <p className="text-xs text-[var(--tx-secondary)]">
                        Document on file — upload to extract data via OCR
                      </p>
                    ) : null}
                  </div>
                  <MemberActions
                    clientId={clientId}
                    member={member}
                    passportDocument={passportDocument}
                    visaDocument={visaDocument}
                    onEditClick={onEditClick}
                    onRefresh={onRefresh}
                    onDelete={handleDelete}
                  />
                </HairlineRow>
              );
            })}
          </HairlineBody>
        </HairlineGrid>
      )}
    </LedgerSection>
  );
}
