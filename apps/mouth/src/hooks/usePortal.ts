/**
 * usePortal Hooks
 *
 * Hooks ottimizzati per il client portal con React Query
 */

import { useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  PortalDashboard,
  PortalProfile,
  VisaInfo,
  PortalCompany,
  TaxOverview,
  PortalDocument,
  MessagesResponse,
  PortalMessage,
  SendMessageRequest,
  PortalPreferences,
  PortalMatterDetail,
} from "@/lib/api/portal/portal.types";

// ============================================================================
// DASHBOARD
// ============================================================================

export function usePortalDashboard() {
  return useQuery({
    queryKey: ["portal", "dashboard"],
    queryFn: async (): Promise<PortalDashboard> => {
      return api.portal.getDashboard();
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 5 * 60 * 1000, // Auto refresh every 5 minutes
  });
}

export function usePortalDashboardSummary() {
  return useQuery({
    queryKey: ["portal", "dashboard", "summary"],
    queryFn: async () => api.portal.getDashboardSummary(),
    staleTime: 60 * 1000,
    refetchInterval: 2 * 60 * 1000,
  });
}

export function usePortalMatters() {
  return useQuery({
    queryKey: ["portal", "matters"],
    queryFn: async () => api.portal.listMatters(),
    staleTime: 60 * 1000,
  });
}

export function usePortalMatter(matterId: number | null) {
  return useQuery({
    queryKey: ["portal", "matters", matterId],
    queryFn: async (): Promise<PortalMatterDetail> => {
      if (!matterId) throw new Error("Matter ID required");
      return api.portal.getMatterDetail(matterId);
    },
    enabled: !!matterId,
    staleTime: 60 * 1000,
  });
}

export function usePortalTimeline(limit: number = 50) {
  return useQuery({
    queryKey: ["portal", "timeline", limit],
    queryFn: async () => {
      return api.portal.getTimeline(limit);
    },
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================================================
// PROFILE
// ============================================================================

export function usePortalProfile() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["portal", "profile"],
    queryFn: async (): Promise<PortalProfile> => {
      return api.portal.getProfile();
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - profile rarely changes
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["portal", "profile"] });
  }, [queryClient]);

  return { ...query, invalidate };
}

// ============================================================================
// VISA
// ============================================================================

export function useVisaStatus() {
  return useQuery({
    queryKey: ["portal", "visa"],
    queryFn: async (): Promise<VisaInfo> => {
      return api.portal.getVisaStatus();
    },
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================================================
// COMPANIES
// ============================================================================

export function usePortalCompanies() {
  return useQuery({
    queryKey: ["portal", "companies"],
    queryFn: async (): Promise<PortalCompany[]> => {
      return api.portal.getCompanies();
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function usePortalCompany(companyId: number | null) {
  return useQuery({
    queryKey: ["portal", "companies", companyId],
    queryFn: async (): Promise<PortalCompany> => {
      if (!companyId) throw new Error("Company ID required");
      return api.portal.getCompanyDetail(companyId);
    },
    enabled: !!companyId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSetPrimaryCompany() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (companyId: number) => {
      return api.portal.setPrimaryCompany(companyId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal", "companies"] });
      queryClient.invalidateQueries({ queryKey: ["portal", "dashboard"] });
    },
  });
}

// ============================================================================
// TAXES
// ============================================================================

export function useTaxOverview() {
  return useQuery({
    queryKey: ["portal", "taxes"],
    queryFn: async (): Promise<TaxOverview> => {
      return api.portal.getTaxOverview();
    },
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================================================
// DOCUMENTS
// ============================================================================

export function usePortalDocuments(documentType?: string) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["portal", "documents", documentType],
    queryFn: async (): Promise<PortalDocument[]> => {
      return api.portal.getDocuments(documentType);
    },
    staleTime: 2 * 60 * 1000,
  });

  const uploadMutation = useMutation({
    mutationFn: async ({
      file,
      documentType,
      practiceId,
    }: {
      file: File;
      documentType: string;
      practiceId?: number;
    }) => {
      return api.portal.uploadDocument(file, documentType, practiceId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal", "documents"] });
      queryClient.invalidateQueries({ queryKey: ["portal", "dashboard"] });
    },
  });

  return {
    ...query,
    uploadDocument: uploadMutation.mutate,
    isUploading: uploadMutation.isPending,
  };
}

// ============================================================================
// MESSAGES
// ============================================================================

interface UsePortalMessagesOptions {
  limit?: number;
  offset?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function usePortalMessages(options: UsePortalMessagesOptions = {}) {
  const {
    limit = 50,
    offset = 0,
    autoRefresh = true,
    refreshInterval = 30000,
  } = options;
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["portal", "messages", { limit, offset }],
    queryFn: async (): Promise<MessagesResponse> => {
      return api.portal.getMessages(limit, offset);
    },
    staleTime: 10 * 1000, // 10 seconds - messages change frequently
    refetchInterval: autoRefresh ? refreshInterval : false,
  });

  const sendMutation = useMutation({
    mutationFn: async (request: SendMessageRequest) => {
      return api.portal.sendMessage(request);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal", "messages"] });
    },
  });

  const markReadMutation = useMutation({
    mutationFn: async (messageId: number) => {
      return api.portal.markMessageRead(messageId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal", "messages"] });
    },
  });

  return {
    ...query,
    sendMessage: sendMutation.mutate,
    isSending: sendMutation.isPending,
    markAsRead: markReadMutation.mutate,
  };
}

// ============================================================================
// SETTINGS
// ============================================================================

export function usePortalPreferences() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["portal", "preferences"],
    queryFn: async (): Promise<PortalPreferences> => {
      return api.portal.getPreferences();
    },
    staleTime: 10 * 60 * 1000,
  });

  const updateMutation = useMutation({
    mutationFn: async (preferences: Partial<PortalPreferences>) => {
      return api.portal.updatePreferences(preferences);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["portal", "preferences"], updated);
    },
  });

  return {
    ...query,
    updatePreferences: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
  };
}

// ============================================================================
// INVITATION FLOW (Registration)
// ============================================================================

export function useValidateInviteToken(token: string | null) {
  return useQuery({
    queryKey: ["portal", "invite", token],
    queryFn: async () => {
      if (!token) throw new Error("Token required");
      return api.portal.validateInviteToken(token);
    },
    enabled: !!token,
    retry: false,
  });
}

export function useCompleteRegistration() {
  return useMutation({
    mutationFn: async ({ token, pin }: { token: string; pin: string }) => {
      return api.portal.completeRegistration({ token, pin });
    },
  });
}

// ============================================================================
// NOTIFICATIONS AGGREGATOR
// ============================================================================

interface PortalNotification {
  id: string;
  type: "visa" | "document" | "tax" | "message" | "action";
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
  href?: string;
  createdAt: string;
}

export function usePortalNotifications() {
  const { data: dashboard } = usePortalDashboard();

  const notifications: PortalNotification[] = [];

  if (dashboard) {
    // Visa notifications
    if (dashboard.visa.status === "expired") {
      notifications.push({
        id: "visa-expired",
        type: "visa",
        title: "Visa Expired",
        message: "Your visa has expired. Please contact us immediately.",
        severity: "critical",
        href: "/portal/visa",
        createdAt: new Date().toISOString(),
      });
    } else if (
      dashboard.visa.status === "warning" &&
      dashboard.visa.daysRemaining
    ) {
      notifications.push({
        id: "visa-expiring",
        type: "visa",
        title: "Visa Expiring Soon",
        message: `Your visa expires in ${dashboard.visa.daysRemaining} days.`,
        severity: "warning",
        href: "/portal/visa",
        createdAt: new Date().toISOString(),
      });
    }

    // Tax notifications
    if (dashboard.taxes.status === "overdue") {
      notifications.push({
        id: "tax-overdue",
        type: "tax",
        title: "Tax Overdue",
        message: "You have overdue tax obligations.",
        severity: "critical",
        href: "/portal/taxes",
        createdAt: new Date().toISOString(),
      });
    } else if (
      dashboard.taxes.status === "attention" &&
      dashboard.taxes.daysToDeadline
    ) {
      notifications.push({
        id: "tax-due",
        type: "tax",
        title: "Tax Due Soon",
        message: `Tax deadline in ${dashboard.taxes.daysToDeadline} days.`,
        severity: "warning",
        href: "/portal/taxes",
        createdAt: new Date().toISOString(),
      });
    }

    // Document notifications
    if (dashboard.documents.pending > 0) {
      notifications.push({
        id: "documents-pending",
        type: "document",
        title: "Pending Documents",
        message: `${dashboard.documents.pending} document${dashboard.documents.pending > 1 ? "s" : ""} pending verification.`,
        severity: "info",
        href: "/portal/vault",
        createdAt: new Date().toISOString(),
      });
    }

    // Message notifications
    if (dashboard.messages.unread > 0) {
      notifications.push({
        id: "messages-unread",
        type: "message",
        title: "Unread Messages",
        message: `${dashboard.messages.unread} unread message${dashboard.messages.unread > 1 ? "s" : ""}.`,
        severity: "info",
        href: "/portal/messages",
        createdAt: new Date().toISOString(),
      });
    }

    // Action items
    dashboard.actions.forEach((action, index) => {
      notifications.push({
        id: `action-${index}`,
        type: "action",
        title: action.title,
        message: action.description,
        severity:
          action.priority === "high"
            ? "critical"
            : action.priority === "medium"
              ? "warning"
              : "info",
        href: action.href,
        createdAt: new Date().toISOString(),
      });
    });
  }

  return {
    notifications,
    unreadCount: notifications.length,
    criticalCount: notifications.filter((n) => n.severity === "critical")
      .length,
    warningCount: notifications.filter((n) => n.severity === "warning").length,
  };
}
