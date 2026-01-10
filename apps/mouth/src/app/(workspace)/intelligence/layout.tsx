"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Shield, Newspaper, Activity, BarChart3 } from "lucide-react";
import { ErrorBoundary } from "@/components/ui/error-boundary";

const tabs = [
  {
    name: "Visa Oracle",
    href: "/intelligence/visa-oracle",
    icon: Shield,
    description: "Review automated visa regulation discoveries"
  },
  {
    name: "News Room",
    href: "/intelligence/news-room",
    icon: Newspaper,
    description: "Curate immigration news articles"
  },
  {
    name: "Analytics",
    href: "/intelligence/analytics",
    icon: BarChart3,
    description: "Historical trends and performance metrics"
  },
  {
    name: "System Pulse",
    href: "/intelligence/system-pulse",
    icon: Activity,
    description: "Monitor agent health and performance"
  },
];

export default function IntelligenceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col h-full space-y-6">
      {/* Header */}
      <div className="flex flex-col space-y-3 pb-4 border-b border-[var(--border)]">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
              Intelligence Center
            </h1>
            <p className="text-[var(--foreground-muted)]">
              AI-powered monitoring of Indonesian immigration regulations
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--accent)]/10 border border-[var(--accent)]/20">
            <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
            <span className="text-sm font-medium text-[var(--accent)]">Agent Active</span>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 pb-4">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname?.startsWith(tab.href);

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200",
                "border border-[var(--border)]",
                "hover:bg-[var(--background-elevated)] hover:border-[var(--accent)]/30",
                isActive && "bg-[var(--accent)]/10 border-[var(--accent)] shadow-sm"
              )}
            >
              <Icon className={cn(
                "w-5 h-5 transition-colors",
                isActive ? "text-[var(--accent)]" : "text-[var(--foreground-muted)]"
              )} />
              <div className="flex flex-col">
                <span className={cn(
                  "text-sm font-semibold",
                  isActive ? "text-[var(--accent)]" : "text-[var(--foreground)]"
                )}>
                  {tab.name}
                </span>
                <span className="text-xs text-[var(--foreground-muted)]">
                  {tab.description}
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <ErrorBoundary
          onError={(error, errorInfo) => {
            console.error('[Intelligence] Error caught:', error.message, errorInfo.componentStack);
          }}
        >
          {children}
        </ErrorBoundary>
      </div>
    </div>
  );
}
