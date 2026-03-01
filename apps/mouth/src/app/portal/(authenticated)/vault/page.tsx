"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  Upload,
  FileText,
  Download,
  Filter,
  X,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import type { PortalDocument } from "@/lib/api/portal/portal.types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function VaultPage() {
  const { success, error } = useToast();
  const [documents, setDocuments] = useState<PortalDocument[]>([]);
  const [filteredDocs, setFilteredDocs] = useState<PortalDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const categories = ["all", "passport", "visa", "tax", "company", "other"];

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    filterDocuments();
  }, [documents, selectedCategory, searchQuery]);

  const loadDocuments = async () => {
    try {
      setIsLoading(true);
      const docs = await api.portal.getDocuments();
      setDocuments(docs);
    } catch (err) {
      error("Failed to load documents", "Please try again later");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const filterDocuments = () => {
    let filtered = documents;

    if (selectedCategory !== "all") {
      filtered = filtered.filter(
        (doc) => doc.category.toLowerCase() === selectedCategory.toLowerCase(),
      );
    }

    if (searchQuery) {
      filtered = filtered.filter((doc) =>
        doc.name.toLowerCase().includes(searchQuery.toLowerCase()),
      );
    }

    setFilteredDocs(filtered);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      error("File too large", "Maximum file size is 10MB");
      return;
    }

    try {
      setIsUploading(true);
      const uploadedDoc = await api.portal.uploadDocument(file, "general");
      setDocuments((prev) => [uploadedDoc, ...prev]);
      success("Document uploaded", `${file.name} was uploaded successfully`);
      e.target.value = "";
    } catch (err) {
      error("Upload failed", "Could not upload document. Please try again.");
      console.error(err);
    } finally {
      setIsUploading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "verified":
        return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";
      case "pending":
        return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
      case "expired":
        return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
      default:
        return "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400";
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Document Vault</h1>
        <p className="text-muted-foreground">Manage your important documents</p>
      </section>

      {/* Upload Section */}
      <section className="rounded-lg border border-dashed border-primary/50 bg-primary/5 p-6 text-center">
        <label
          htmlFor="file-upload"
          className="flex flex-col items-center gap-2 cursor-pointer"
        >
          {isUploading ? (
            <Loader2 className="w-10 h-10 animate-spin text-primary" />
          ) : (
            <Upload className="w-10 h-10 text-primary" />
          )}
          <div className="text-sm font-medium">
            {isUploading ? "Uploading..." : "Click to upload document"}
          </div>
          <div className="text-xs text-muted-foreground">
            PDF, JPG, PNG up to 10MB
          </div>
          <input
            id="file-upload"
            type="file"
            className="hidden"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFileUpload}
            disabled={isUploading}
          />
        </label>
      </section>

      {/* Filters */}
      <section className="space-y-3">
        <Input
          type="text"
          placeholder="Search documents..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full"
        />

        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors",
                selectedCategory === cat
                  ? "bg-primary text-primary-foreground"
                  : "bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-700",
              )}
            >
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>
      </section>

      {/* Documents List */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {filteredDocs.length} Document{filteredDocs.length !== 1 ? "s" : ""}
          </h2>
          {(searchQuery || selectedCategory !== "all") && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchQuery("");
                setSelectedCategory("all");
              }}
            >
              <X className="w-4 h-4 mr-1" />
              Clear filters
            </Button>
          )}
        </div>

        {filteredDocs.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No documents found</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredDocs.map((doc) => (
              <div
                key={doc.id}
                className="rounded-lg border bg-card p-4 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-md bg-primary/10">
                    <FileText className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-sm truncate">
                      {doc.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span
                        className={cn(
                          "text-xs px-2 py-0.5 rounded-full font-medium",
                          getStatusColor(doc.status),
                        )}
                      >
                        {doc.status}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {doc.category}
                      </span>
                      <span className="text-xs text-muted-foreground">•</span>
                      <span className="text-xs text-muted-foreground">
                        {doc.size}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Uploaded: {new Date(doc.uploadDate).toLocaleDateString()}
                    </p>
                    {doc.expiryDate && (
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                        Expires: {new Date(doc.expiryDate).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  {doc.downloadUrl && (
                    <Button variant="ghost" size="icon" asChild>
                      <a
                        href={doc.downloadUrl}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Download document"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
