"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  User,
  Users,
  Globe,
  CreditCard,
  AlertCircle,
  AlertTriangle,
  Plus,
  Trash2,
  Edit2,
  Upload,
  Download,
  Eye,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import type { FamilyMember, ClientDocument } from "@/lib/api/crm/crm.types";
import { ALERT_COLORS } from "./constants";
import { extractDriveFileId } from "./utils";

// ============================================
// FAMILY MEMBER UPLOAD BUTTON (internal)
// ============================================
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
  documentType: "passport" | "visa";
  onRefresh: () => Promise<void> | void;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [ocrPolling, setOcrPolling] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ocrTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ocrAbortedRef = useRef(false);
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  // Cleanup OCR polling timers when component unmounts
  useEffect(() => {
    ocrAbortedRef.current = false;
    return () => {
      ocrAbortedRef.current = true;
      if (ocrTimerRef.current) clearTimeout(ocrTimerRef.current);
    };
  }, []);

  const pollOcrStatus = useCallback(async () => {
    setOcrPolling(true);
    let attempts = 0;
    const poll = async () => {
      if (ocrAbortedRef.current) return;
      try {
        const status = (await api.request(
          `/api/crm/clients/${clientId}/ocr-status`,
        )) as {
          pending_ocr: number;
        };
        if (status.pending_ocr === 0 || attempts >= 10) {
          if (!ocrAbortedRef.current) {
            setOcrPolling(false);
            await onRefreshRef.current();
          }
          return;
        }
        attempts++;
        ocrTimerRef.current = setTimeout(poll, 3000);
      } catch {
        if (!ocrAbortedRef.current) {
          setOcrPolling(false);
          await onRefreshRef.current();
        }
      }
    };
    ocrTimerRef.current = setTimeout(poll, 2000);
  }, [clientId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
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
      const base64 = await fileToBase64(file);
      const response = (await api.post(
        `/api/crm/clients/${clientId}/documents/upload`,
        {
          file: base64,
          file_name: file.name,
          document_type: documentType,
          mime_type: file.type,
          family_member_id: memberId,
        },
      )) as { success: boolean; message?: string };
      if (response.success) {
        toast.success(
          `${documentType === "passport" ? "Passport" : "Visa"} uploaded for ${memberName} — OCR in corso...`,
        );
        pollOcrStatus();
      } else {
        toast.error("Upload failed", { description: response.message });
      }
    } catch (err) {
      toast.error("Upload failed", { description: (err as Error).message });
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
        disabled={isUploading}
      />
      <Button
        variant="outline"
        size="sm"
        className="gap-2 text-xs w-full"
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading || ocrPolling}
      >
        {isUploading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : ocrPolling ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Upload className="w-3.5 h-3.5" />
        )}
        {isUploading
          ? "Uploading..."
          : ocrPolling
            ? "OCR in corso..."
            : `Upload ${documentType === "passport" ? "Passport" : "Visa"}`}
      </Button>
    </>
  );
}

// ============================================
// FAMILY TAB
// ============================================
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
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onEditClick: (member: FamilyMember) => void;
  onRefresh: () => Promise<void> | void;
}) {
  const handleDelete = async (id: number, name: string) => {
    if (confirm(`Remove ${name} from family members?`)) {
      try {
        await api.crm.deleteFamilyMember(clientId, id);
        toast.success("Family member removed");
        onRefresh();
      } catch (err) {
        toast.error("Error", { description: (err as Error).message });
      }
    }
  };

  // Find documents linked to a family member
  const getMemberDocuments = (memberId: number) =>
    documents.filter((d) => d.family_member_id === memberId);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">
          Family Members
        </h3>
        <Button size="sm" className="gap-2" onClick={onAddClick}>
          <Plus className="w-4 h-4" />
          Add Member
        </Button>
      </div>

      {familyMembers.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
          <Users className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">No family members added yet</p>
          <p className="text-sm text-[var(--bz-text-2)] mt-1">
            Add spouse, children, or dependents
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {familyMembers.map((member) => {
            const memberDocs = getMemberDocuments(member.id);
            const memberPassportDoc = memberDocs.find((d) =>
              d.document_type?.toLowerCase().includes("passport"),
            );
            const memberVisaDoc = memberDocs.find(
              (d) =>
                d.document_type?.toLowerCase().includes("kitas") ||
                d.document_type?.toLowerCase().includes("visa"),
            );

            return (
              <div
                key={member.id}
                className="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(32,32,36,0.6)] backdrop-blur-md shadow-2xl overflow-hidden group"
              >
                {/* Header with relationship badge */}
                <div className="flex items-center justify-between px-5 py-3 border-b border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.8)] backdrop-blur-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[var(--bz-accent)]/20 flex items-center justify-center">
                      <User className="w-5 h-5 text-[var(--bz-accent)]" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-[var(--bz-text-1)]">
                        {member.full_name}
                      </h4>
                      <span className="inline-block px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-xs capitalize">
                        {member.relationship}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-[var(--bz-text-2)] hover:text-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/10"
                      onClick={() => onEditClick(member)}
                    >
                      <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-400 hover:text-red-500 hover:bg-red-500/10"
                      onClick={() => handleDelete(member.id, member.full_name)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Full overview — 3 columns like main overview */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 p-5">
                  {/* COL 1: Personal Info */}
                  <div className="space-y-3">
                    <h5 className="text-xs uppercase tracking-wider text-[var(--bz-text-2)] font-medium">
                      Personal Info
                    </h5>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                      {member.nationality && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                            Nationality
                          </p>
                          <p className="text-sm font-medium">
                            {member.nationality}
                          </p>
                        </div>
                      )}
                      {member.date_of_birth && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                            Date of Birth
                          </p>
                          <p className="text-sm font-medium">
                            {formatDate(member.date_of_birth)}
                          </p>
                        </div>
                      )}
                      {member.email && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                            Email
                          </p>
                          <p className="text-sm font-medium truncate">
                            {member.email}
                          </p>
                        </div>
                      )}
                      {member.phone && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                            Phone
                          </p>
                          <p className="text-sm font-medium">{member.phone}</p>
                        </div>
                      )}
                    </div>
                    {member.notes && (
                      <div className="mt-2 p-2 rounded-lg bg-[var(--bz-base)]/50 border border-[var(--bz-border)]">
                        <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1">
                          Notes
                        </p>
                        <p className="text-xs text-[var(--bz-text-2)]">
                          {member.notes}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* COL 2: Passport */}
                  <div className="space-y-3">
                    <h5 className="text-xs uppercase tracking-wider text-[var(--bz-text-2)] font-medium">
                      Passport
                    </h5>
                    {member.passport_number || memberPassportDoc ? (
                      <div className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] p-3 space-y-2">
                        {member.passport_number && (
                          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                            <div>
                              <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                                Number
                              </p>
                              <p className="text-sm font-semibold font-mono">
                                {member.passport_number}
                              </p>
                            </div>
                            {member.passport_expiry && (
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                                  Expiry
                                </p>
                                <p
                                  className={`text-sm font-medium ${
                                    new Date(member.passport_expiry) <
                                    new Date()
                                      ? "text-red-500"
                                      : new Date(member.passport_expiry) <
                                          new Date(Date.now() + 365 * 86400000)
                                        ? "text-yellow-500"
                                        : "text-green-500"
                                  }`}
                                >
                                  {formatDate(member.passport_expiry)}
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                        {!member.passport_number && memberPassportDoc && (
                          <p className="text-xs text-yellow-400 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            Document on file — upload to extract data via OCR
                          </p>
                        )}
                        {member.passport_alert &&
                          member.passport_alert !== "green" && (
                            <div
                              className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${ALERT_COLORS[member.passport_alert]}`}
                            >
                              <AlertTriangle className="w-3 h-3" />
                              {member.passport_alert === "expired"
                                ? "Expired"
                                : member.passport_alert === "red"
                                  ? "Expiring soon"
                                  : "Renewal recommended"}
                            </div>
                          )}
                        {memberPassportDoc?.google_drive_file_url && (
                          <div className="flex gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="gap-1.5 text-xs h-7 px-2"
                              onClick={() => {
                                const fileId = extractDriveFileId(
                                  memberPassportDoc.google_drive_file_url!,
                                );
                                if (fileId)
                                  window.open(
                                    `/api/documents/proxy/${fileId}`,
                                    "_blank",
                                  );
                              }}
                            >
                              <Eye className="w-3 h-3" />
                              View
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="gap-1.5 text-xs h-7 px-2"
                              onClick={() => {
                                const fileId = extractDriveFileId(
                                  memberPassportDoc.google_drive_file_url!,
                                );
                                if (fileId) {
                                  const link = document.createElement("a");
                                  link.href = `/api/documents/proxy/${fileId}`;
                                  link.download = `passport_${member.full_name.replace(/\s+/g, "_")}.jpg`;
                                  document.body.appendChild(link);
                                  link.click();
                                  document.body.removeChild(link);
                                }
                              }}
                            >
                              <Download className="w-3 h-3" />
                              Download
                            </Button>
                          </div>
                        )}
                        <FamilyMemberUploadButton
                          clientId={clientId}
                          memberId={member.id}
                          memberName={member.full_name}
                          documentType="passport"
                          onRefresh={onRefresh}
                        />
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-[var(--bz-border)] bg-[var(--bz-base)]/30 p-4 text-center space-y-3">
                        <CreditCard className="w-6 h-6 mx-auto text-[var(--bz-text-2)] opacity-30 mb-1" />
                        <p className="text-xs text-[var(--bz-text-2)]">
                          No passport data
                        </p>
                        <FamilyMemberUploadButton
                          clientId={clientId}
                          memberId={member.id}
                          memberName={member.full_name}
                          documentType="passport"
                          onRefresh={onRefresh}
                        />
                      </div>
                    )}
                  </div>

                  {/* COL 3: Visa */}
                  <div className="space-y-3">
                    <h5 className="text-xs uppercase tracking-wider text-[var(--bz-text-2)] font-medium">
                      Actual Visa
                    </h5>
                    {member.current_visa_type || memberVisaDoc ? (
                      <div className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] p-3 space-y-2">
                        {member.current_visa_type && (
                          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                            <div>
                              <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                                Type
                              </p>
                              <p className="text-sm font-semibold uppercase">
                                {member.current_visa_type}
                              </p>
                            </div>
                            {member.visa_expiry && (
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                                  Expiry
                                </p>
                                <p
                                  className={`text-sm font-medium ${
                                    new Date(member.visa_expiry) < new Date()
                                      ? "text-red-500"
                                      : new Date(member.visa_expiry) <
                                          new Date(Date.now() + 90 * 86400000)
                                        ? "text-yellow-500"
                                        : "text-green-500"
                                  }`}
                                >
                                  {formatDate(member.visa_expiry)}
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                        {!member.current_visa_type && memberVisaDoc && (
                          <p className="text-xs text-yellow-400 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            Document on file — upload to extract data via OCR
                          </p>
                        )}
                        {member.visa_alert && member.visa_alert !== "green" && (
                          <div
                            className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${ALERT_COLORS[member.visa_alert]}`}
                          >
                            <AlertTriangle className="w-3 h-3" />
                            {member.visa_alert === "expired"
                              ? "Expired"
                              : member.visa_alert === "red"
                                ? "Expiring soon"
                                : "Renewal recommended"}
                          </div>
                        )}
                        {memberVisaDoc?.google_drive_file_url && (
                          <div className="flex gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="gap-1.5 text-xs h-7 px-2"
                              onClick={() => {
                                const fileId = extractDriveFileId(
                                  memberVisaDoc.google_drive_file_url!,
                                );
                                if (fileId)
                                  window.open(
                                    `/api/documents/proxy/${fileId}`,
                                    "_blank",
                                  );
                              }}
                            >
                              <Eye className="w-3 h-3" />
                              View
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="gap-1.5 text-xs h-7 px-2"
                              onClick={() => {
                                const fileId = extractDriveFileId(
                                  memberVisaDoc.google_drive_file_url!,
                                );
                                if (fileId) {
                                  const link = document.createElement("a");
                                  link.href = `/api/documents/proxy/${fileId}`;
                                  link.download = `visa_${member.full_name.replace(/\s+/g, "_")}.jpg`;
                                  document.body.appendChild(link);
                                  link.click();
                                  document.body.removeChild(link);
                                }
                              }}
                            >
                              <Download className="w-3 h-3" />
                              Download
                            </Button>
                          </div>
                        )}
                        <FamilyMemberUploadButton
                          clientId={clientId}
                          memberId={member.id}
                          memberName={member.full_name}
                          documentType="visa"
                          onRefresh={onRefresh}
                        />
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-[var(--bz-border)] bg-[var(--bz-base)]/30 p-4 text-center space-y-3">
                        <Globe className="w-6 h-6 mx-auto text-[var(--bz-text-2)] opacity-30 mb-1" />
                        <p className="text-xs text-[var(--bz-text-2)]">
                          No visa data
                        </p>
                        <FamilyMemberUploadButton
                          clientId={clientId}
                          memberId={member.id}
                          memberName={member.full_name}
                          documentType="visa"
                          onRefresh={onRefresh}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
