"use client";

import React, { useState } from "react";
import { FileText, FolderOpen, X } from "lucide-react";
import {
  usePortalDriveFiles,
  usePortalDriveSubfolder,
} from "@/hooks/usePortalDriveFiles";
import { VaultLayout } from "@/components/portal/vault/VaultLayout";

export default function VaultPage() {
  const { data: driveData, isLoading: isLoadingDrive } = usePortalDriveFiles();
  const [activeTab, setActiveTab] = useState<"uploaded" | "drive">("uploaded");
  const [openFolderId, setOpenFolderId] = useState<string | null>(null);
  const [openFolderName, setOpenFolderName] = useState<string>("");
  const { data: subfolderData, isLoading: isLoadingSubfolder } =
    usePortalDriveSubfolder(openFolderId);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Document Vault</h1>
        <p style={{ color: "var(--bz-text-2)" }}>
          Manage your important documents
        </p>
      </section>

      {/* Tab Switcher */}
      <section
        className="flex gap-1 p-1 rounded-lg"
        style={{ background: "rgba(255,255,255,0.03)" }}
      >
        <button
          onClick={() => setActiveTab("uploaded")}
          className="flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors"
          style={
            activeTab === "uploaded"
              ? {
                  background: "rgba(201,169,110,0.15)",
                  color: "var(--bz-accent-warm)",
                }
              : {
                  color: "var(--bz-text-2)",
                }
          }
        >
          Uploaded
        </button>
        <button
          onClick={() => setActiveTab("drive")}
          className="flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors"
          style={
            activeTab === "drive"
              ? {
                  background: "rgba(201,169,110,0.15)",
                  color: "var(--bz-accent-warm)",
                }
              : {
                  color: "var(--bz-text-2)",
                }
          }
        >
          Drive Files ({driveData?.total_files ?? 0})
        </button>
      </section>

      {activeTab === "uploaded" ? (
        <VaultLayout />
      ) : (
        /* Drive Files Tab */
        <section className="space-y-3">
          {isLoadingDrive ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-lg border p-4 h-16 animate-pulse"
                  style={{
                    background: "rgba(30,30,35,0.7)",
                    borderColor: "rgba(255,255,255,0.05)",
                  }}
                />
              ))}
            </div>
          ) : !driveData?.folders?.length && !driveData?.total_files ? (
            <div
              className="text-center py-12"
              style={{ color: "var(--bz-text-2)" }}
            >
              <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No Drive folder linked to your account</p>
              <p className="text-sm mt-1" style={{ color: "var(--bz-text-3)" }}>
                Contact your case manager to set up document sharing.
              </p>
            </div>
          ) : openFolderId ? (
            /* Subfolder view */
            <div className="space-y-2">
              <button
                onClick={() => {
                  setOpenFolderId(null);
                  setOpenFolderName("");
                }}
                className="flex items-center gap-1.5 text-xs font-medium mb-2 transition-colors hover:opacity-80"
                style={{ color: "var(--bz-accent-warm)" }}
              >
                <X className="w-3 h-3" /> Back to folders
              </button>
              <p
                className="text-sm font-medium mb-3"
                style={{ color: "var(--bz-text-1)" }}
              >
                {openFolderName}
              </p>
              {isLoadingSubfolder ? (
                <div className="space-y-2">
                  {[1, 2].map((i) => (
                    <div
                      key={i}
                      className="rounded-lg border p-4 h-16 animate-pulse"
                      style={{
                        background: "rgba(30,30,35,0.7)",
                        borderColor: "rgba(255,255,255,0.05)",
                      }}
                    />
                  ))}
                </div>
              ) : !subfolderData?.folders?.length ? (
                <div
                  className="text-center py-8"
                  style={{ color: "var(--bz-text-3)" }}
                >
                  <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No files in this folder</p>
                </div>
              ) : (
                subfolderData.folders.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      setOpenFolderId(item.id);
                      setOpenFolderName(item.name);
                    }}
                    className="w-full rounded-lg border p-4 flex items-center gap-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg cursor-pointer text-left"
                    style={{
                      background: "rgba(30,30,35,0.7)",
                      borderColor: "rgba(255,255,255,0.05)",
                    }}
                  >
                    <div
                      className="p-2 rounded-md"
                      style={{ background: "rgba(201,169,110,0.12)" }}
                    >
                      <FolderOpen
                        className="w-5 h-5"
                        style={{ color: "var(--bz-accent-warm)" }}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {item.name}
                      </p>
                    </div>
                  </button>
                ))
              )}
            </div>
          ) : (
            /* Root folders view */
            <div className="space-y-2">
              {driveData?.folders?.map((folder) => (
                <button
                  key={folder.id}
                  onClick={() => {
                    setOpenFolderId(folder.id);
                    setOpenFolderName(folder.name);
                  }}
                  className="w-full rounded-lg border p-4 flex items-center gap-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg cursor-pointer text-left"
                  style={{
                    background: "rgba(30,30,35,0.7)",
                    borderColor: "rgba(255,255,255,0.05)",
                  }}
                >
                  <div
                    className="p-2 rounded-md"
                    style={{ background: "rgba(201,169,110,0.12)" }}
                  >
                    <FolderOpen
                      className="w-5 h-5"
                      style={{ color: "var(--bz-accent-warm)" }}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {folder.name}
                    </p>
                  </div>
                </button>
              ))}
              <p
                className="text-xs text-center pt-2"
                style={{ color: "var(--bz-text-3)" }}
              >
                {driveData?.total_files ?? 0} files &bull;{" "}
                {driveData?.root_name ?? "Drive"}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
