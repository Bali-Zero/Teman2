"use client";

/**
 * Required Documents Hook
 *
 * Manages required documents for practice workflows with optimized caching
 * and TypeScript safety.
 *
 * @ai_onboarding - Strict TypeScript, useMemo for stats, proper error handling
 */

import { useState, useCallback, useEffect, useMemo } from "react";
import { api } from "@/lib/api";
import {
  RequiredDocument,
  RequiredDocumentCreate,
  RequiredDocumentUpdate,
  ClientDocumentUpload,
  ClientRequiredDocument,
} from "@/lib/types/required-documents";

interface UseRequiredDocumentsOptions {
  practiceId?: number;
  clientId?: number;
}

export function useRequiredDocuments(
  options: UseRequiredDocumentsOptions = {},
) {
  const { practiceId, clientId } = options;
  const [documents, setDocuments] = useState<RequiredDocument[]>([]);
  const [clientDocuments, setClientDocuments] = useState<
    ClientRequiredDocument[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch required documents for a practice (CRM view)
  const fetchPracticeDocuments = useCallback(async () => {
    if (!practiceId) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await api.get<RequiredDocument[]>(
        `/api/crm/practices/${practiceId}/required-documents`,
      );
      setDocuments(result || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setIsLoading(false);
    }
  }, [practiceId]);

  // Fetch client's required documents across all practices (Portal view)
  const fetchClientDocuments = useCallback(async () => {
    if (!clientId) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await api.get<ClientRequiredDocument[]>(
        `/api/crm/clients/client/${clientId}/required-documents`,
      );
      setClientDocuments(result || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setIsLoading(false);
    }
  }, [clientId]);

  // Add a required document (team member)
  const addDocument = useCallback(
    async (data: RequiredDocumentCreate) => {
      if (!practiceId) throw new Error("Practice ID required");

      setIsLoading(true);
      try {
        await api.post<RequiredDocument>(
          `/api/crm/practices/${practiceId}/required-documents`,
          data,
        );
        await fetchPracticeDocuments();
      } catch (err) {
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [practiceId, fetchPracticeDocuments],
  );

  // Update a required document (team member review)
  const updateDocument = useCallback(
    async (docId: number, data: RequiredDocumentUpdate) => {
      if (!practiceId) throw new Error("Practice ID required");

      setIsLoading(true);
      try {
        await api.patch<RequiredDocument>(
          `/api/crm/practices/${practiceId}/required-documents/${docId}`,
          data,
        );
        await fetchPracticeDocuments();
      } catch (err) {
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [practiceId, fetchPracticeDocuments],
  );

  // Delete a required document
  const deleteDocument = useCallback(
    async (docId: number) => {
      if (!practiceId) throw new Error("Practice ID required");

      setIsLoading(true);
      try {
        await api.delete<void>(
          `/api/crm/practices/${practiceId}/required-documents/${docId}`,
        );
        await fetchPracticeDocuments();
      } catch (err) {
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [practiceId, fetchPracticeDocuments],
  );

  // Client uploads a document
  const uploadClientDocument = useCallback(
    async (data: ClientDocumentUpload) => {
      if (!practiceId) throw new Error("Practice ID required");

      setIsLoading(true);
      try {
        await api.post<RequiredDocument>(
          `/api/crm/practices/${practiceId}/upload-client-document`,
          data,
        );
        await fetchPracticeDocuments();
      } catch (err) {
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [practiceId, fetchPracticeDocuments],
  );

  // Auto-fetch on mount
  useEffect(() => {
    if (practiceId) {
      fetchPracticeDocuments();
    }
  }, [practiceId, fetchPracticeDocuments]);

  useEffect(() => {
    if (clientId) {
      fetchClientDocuments();
    }
  }, [clientId, fetchClientDocuments]);

  // Stats - optimized with useMemo
  const stats = useMemo(
    () => ({
      total: documents.length,
      required: documents.filter((d) => d.is_required).length,
      uploaded: documents.filter((d) => d.uploaded_by_client).length,
      verified: documents.filter((d) => d.status === "verified").length,
      pending: documents.filter((d) => d.status === "pending").length,
      completionPercentage:
        documents.length > 0
          ? Math.round(
              (documents.filter((d) => d.status === "verified").length /
                documents.length) *
                100,
            )
          : 0,
    }),
    [documents],
  );

  return {
    documents,
    clientDocuments,
    isLoading,
    error,
    stats,
    addDocument,
    updateDocument,
    deleteDocument,
    uploadClientDocument,
    refetch: fetchPracticeDocuments,
    refetchClient: fetchClientDocuments,
  };
}
