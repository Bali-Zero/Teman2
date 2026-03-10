"use client";

import Link from "next/link";
import {
  Shield,
  Newspaper,
  PenTool,
  BarChart3,
  Activity,
  ArrowRight,
} from "lucide-react";

const tools = [
  {
    name: "Visa Oracle",
    href: "/intelligence/visa-oracle",
    icon: Shield,
    description: "Review automated visa regulation discoveries",
    color: "from-blue-500/20 to-blue-600/10",
    iconColor: "text-blue-400",
  },
  {
    name: "News Room",
    href: "/intelligence/news-room",
    icon: Newspaper,
    description: "Curate immigration news articles",
    color: "from-emerald-500/20 to-emerald-600/10",
    iconColor: "text-emerald-400",
  },
  {
    name: "Article Composer",
    href: "/intelligence/article-composer",
    icon: PenTool,
    description:
      "Transform raw content into Bali Zero style Executive Briefs with AI",
    color: "from-purple-500/20 to-purple-600/10",
    iconColor: "text-purple-400",
    badge: "NEW",
  },
  {
    name: "Analytics",
    href: "/intelligence/analytics",
    icon: BarChart3,
    description: "Historical trends and performance metrics",
    color: "from-amber-500/20 to-amber-600/10",
    iconColor: "text-amber-400",
  },
  {
    name: "System Pulse",
    href: "/intelligence/system-pulse",
    icon: Activity,
    description: "Monitor agent health and performance",
    color: "from-red-500/20 to-red-600/10",
    iconColor: "text-red-400",
  },
];

export default function IntelligencePage() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Hero Section */}
      <div className="text-center py-8">
        <h1 className="text-4xl font-bold mb-3" style={{ color: "var(--bz-text-1)" }}>
          Intelligence Center
        </h1>
        <p className="text-lg max-w-2xl mx-auto" style={{ color: "var(--bz-text-2)" }}>
          AI-powered tools for monitoring Indonesian immigration regulations,
          curating news, and creating expert content.
        </p>
      </div>

      {/* Tools Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tools.map((tool) => {
          const Icon = tool.icon;
          return (
            <Link
              key={tool.href}
              href={tool.href}
              className={`
                group relative overflow-hidden rounded-2xl
                bg-gradient-to-br ${tool.color}
                p-6 transition-all duration-300
                hover:-translate-y-1
              `}
            style={{ border: "1px solid var(--bz-border)" }}
            >
              {/* Badge */}
              {tool.badge && (
                <span className="absolute top-4 right-4 px-2 py-0.5 text-xs font-bold rounded-full text-white" style={{ background: "var(--bz-accent)" }}>
                  {tool.badge}
                </span>
              )}

              {/* Icon */}
              <div className={`mb-4 ${tool.iconColor}`}>
                <Icon className="w-10 h-10" />
              </div>

              {/* Content */}
              <h3 className="text-xl font-semibold mb-2 transition-colors group-hover:opacity-80" style={{ color: "var(--bz-text-1)" }}>
                {tool.name}
              </h3>
              <p className="text-sm mb-4" style={{ color: "var(--bz-text-2)" }}>
                {tool.description}
              </p>

              {/* Arrow */}
              <div className="flex items-center text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: "var(--bz-accent)" }}>
                Open tool
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          );
        })}
      </div>

      {/* Quick Stats */}
      <div className="mt-12 p-6 rounded-2xl" style={{ border: "1px solid var(--bz-border)", background: "var(--bz-card)" }}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold" style={{ color: "var(--bz-text-1)" }}>
              System Status
            </h3>
            <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
              All intelligence agents are operational
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-sm font-medium text-emerald-500">Online</span>
          </div>
        </div>
      </div>
    </div>
  );
}
