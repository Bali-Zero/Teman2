"use client";

import * as React from "react";
import { SearchModal } from "@/components/blog/SearchBar";
import { ErrorBoundary } from "@/components/optimization";
import { ZantaraWidget } from "@/components/ZantaraWidget";
import { I18nProvider } from "@/i18n";
import { LocaleHead } from "@/i18n/LocaleHead";
import { PublicNav } from "@/components/nav/PublicNav";
import { PublicFooter } from "@/components/nav/PublicFooter";
import { api } from "@/lib/api";

/**
 * Blog Layout - "The Chronicle"
 * McKinsey-inspired layout with PublicNav + PublicFooter
 */
export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <I18nProvider>
      <BlogLayoutInner>{children}</BlogLayoutInner>
    </I18nProvider>
  );
}

function BlogLayoutInner({ children }: { children: React.ReactNode }) {
  const [isSearchOpen, setIsSearchOpen] = React.useState(false);
  const [pendingNewsCount, setPendingNewsCount] = React.useState(0);
  const [isAdmin, setIsAdmin] = React.useState(false);

  // Check admin status and fetch pending news count
  React.useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const adminMode =
      urlParams.get("admin") === "true" ||
      sessionStorage.getItem("balizero-admin") === "true";
    setIsAdmin(adminMode);
    if (adminMode) {
      sessionStorage.setItem("balizero-admin", "true");
    }

    const fetchPendingCount = async () => {
      try {
        const data = await api.blog.getPendingNews();
        if (data.success) {
          setPendingNewsCount(data.data?.length || 0);
        }
      } catch {
        // silently ignore fetch errors for pending count
      }
    };

    if (adminMode) {
      fetchPendingCount();
      const interval = setInterval(fetchPendingCount, 30000);
      return () => clearInterval(interval);
    }
  }, []);

  // Global keyboard shortcut for search (Cmd/Ctrl + K)
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="min-h-screen bg-[#0c1f3a] text-white">
      <LocaleHead />

      <PublicNav
        variant="full"
        showSearch
        showLangSwitcher
        onSearchOpen={() => setIsSearchOpen(true)}
      />

      {/* Admin pending badge */}
      {isAdmin && pendingNewsCount > 0 && (
        <div className="bg-[rgba(212,132,90,0.1)] border-b border-[rgba(212,132,90,0.2)] px-4 py-2 text-center">
          <a
            href="/news?admin=true&status=pending"
            className="text-sm text-[#d4845a] hover:underline"
          >
            {pendingNewsCount} pending article{pendingNewsCount !== 1 ? "s" : ""} to review
          </a>
        </div>
      )}

      <main>
        <ErrorBoundary
          fallback={
            <div className="p-8 text-center text-white">
              Something went wrong. Please refresh the page.
            </div>
          }
        >
          {children}
        </ErrorBoundary>
      </main>

      <SearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
      />

      <PublicFooter />
      <ZantaraWidget />
    </div>
  );
}
