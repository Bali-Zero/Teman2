"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { SubNav } from "@balizero/core";
import { Shield, Newspaper, PenTool } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { logger } from "@/lib/logger";

const tabs = [
  {
    label: "Visa Oracle",
    href: "/intelligence/visa-oracle",
    icon: Shield,
  },
  {
    label: "News Room",
    href: "/intelligence/news-room",
    icon: Newspaper,
  },
  {
    label: "Article Composer",
    href: "/intelligence/article-composer",
    icon: PenTool,
  },
];

export default function IntelligenceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isHomepage = pathname === "/intelligence";

  return (
    <div className="flex flex-col h-full space-y-0">
      {/* Header — only shown on sub-pages, not on the homepage itself */}
      {!isHomepage && (
        <div
          className="flex items-center justify-between px-4 py-3 mb-6 rounded-2xl border"
          style={{
            background: "rgba(255,255,255,0.03)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            borderColor: "rgba(255,255,255,0.07)",
          }}
        >
          {/* Back to Intelligence Center link */}
          <Link
            href="/intelligence"
            aria-label="Back to Intelligence Center"
            className="text-[11px] font-medium transition-colors"
            style={{ color: "var(--bz-text-3)" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.color = "var(--bz-accent)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = "var(--bz-text-3)")
            }
          >
            <span aria-hidden="true">←</span> Intelligence Center
          </Link>

          {/* Tab Pills */}
          <div
            className="flex items-center gap-1 p-1 rounded-xl"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.07)",
            }}
          >
            <SubNav
              items={tabs}
              pathname={pathname}
              variant="tabs"
              linkAs={Link}
            />
          </div>

          {/* Status indicator */}
          <div
            className="flex items-center gap-1.5"
            aria-label="Intelligence services: Active"
          >
            <div
              aria-hidden="true"
              className="w-[6px] h-[6px] rounded-full animate-pulse"
              style={{
                background: "var(--bz-green)",
                boxShadow: "0 0 5px rgba(77,184,122,0.5)",
              }}
            />
            <span className="text-[11px]" style={{ color: "var(--bz-text-3)" }}>
              Active
            </span>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <ErrorBoundary
          onError={(error, errorInfo) => {
            logger.error(
              "[Intelligence] Error caught: " + error.message,
              {
                component: "IntelligenceLayout",
                note: errorInfo.componentStack || undefined,
              },
              error,
            );
          }}
        >
          {children}
        </ErrorBoundary>
      </div>
    </div>
  );
}
