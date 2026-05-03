/**
 * Custom hook for managing chat sidebar state
 *
 * Handles:
 * - Sidebar open/close state
 * - Search docs modal state
 * - Sidebar interactions
 *
 * @returns Sidebar state and handlers
 */

import { useState, useCallback } from "react";
import { logger } from "@/lib/logger";
import { chatMetrics } from "@/lib/metrics";
import { trackEvent } from "@/lib/analytics";
import { api } from "@/lib/api";

export interface UseChatSidebarReturn {
  // State
  sidebarOpen: boolean;
  isSearchDocsOpen: boolean;

  // Handlers
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  openSearchDocs: () => void;
  closeSearchDocs: () => void;
}

export function useChatSidebar(): UseChatSidebarReturn {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSearchDocsOpen, setIsSearchDocsOpen] = useState(false);

  const openSidebar = useCallback(() => {
    logger.debug("Sidebar opened", {
      component: "useChatSidebar",
      action: "openSidebar",
    });

    // Track metrics
    chatMetrics.sidebarOpened();

    const userProfile = api.getUserProfile();
    trackEvent("chat_sidebar_opened", {}, userProfile?.email);

    setSidebarOpen(true);
  }, []);

  const closeSidebar = useCallback(() => {
    logger.debug("Sidebar closed", {
      component: "useChatSidebar",
      action: "closeSidebar",
    });

    // Track metrics
    chatMetrics.sidebarClosed();

    const userProfile = api.getUserProfile();
    trackEvent("chat_sidebar_closed", {}, userProfile?.email);

    setSidebarOpen(false);
  }, []);

  const toggleSidebar = useCallback(() => {
    if (sidebarOpen) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }, [sidebarOpen, openSidebar, closeSidebar]);

  const openSearchDocs = useCallback(() => {
    logger.info("Search docs opened", {
      component: "useChatSidebar",
      action: "openSearchDocs",
    });

    const userProfile = api.getUserProfile();
    trackEvent("chat_search_docs_opened", {}, userProfile?.email);

    setIsSearchDocsOpen(true);
  }, []);

  const closeSearchDocs = useCallback(() => {
    logger.debug("Search docs closed", {
      component: "useChatSidebar",
      action: "closeSearchDocs",
    });

    setIsSearchDocsOpen(false);
  }, []);

  return {
    sidebarOpen,
    isSearchDocsOpen,
    openSidebar,
    closeSidebar,
    toggleSidebar,
    openSearchDocs,
    closeSearchDocs,
  };
}
