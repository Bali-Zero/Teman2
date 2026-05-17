"use client";

import { useEffect, useState } from "react";
import {
  Loader2,
  CheckCircle2,
  Search,
  Mail,
  Send,
  DollarSign,
  Users,
  HardDrive,
  Globe,
  Brain,
  Scale,
  ImagePlus,
  type LucideIcon,
} from "lucide-react";
import { useChatLocale } from "@/hooks/useChatLocale";
import { getToolLabel } from "./tool-labels";

const TOOL_ICON_MAP: Record<string, LucideIcon> = {
  search_emails: Mail,
  search_threads: Mail,
  send_email: Send,
  search_kbli: Search,
  get_pricing: DollarSign,
  search_service_pricing: DollarSign,
  list_clients: Users,
  get_client: Users,
  search_drive: HardDrive,
  list_drive_files: HardDrive,
  web_search: Globe,
  search_intel: Brain,
  ask_legal: Scale,
  generate_image: ImagePlus,
};

export interface ToolUseIndicatorProps {
  toolName: string;
  status: "running" | "done";
  /**
   * Override for tests. When omitted the locale is read from the same
   * `blog-language` localStorage key used by `<I18nProvider>`.
   */
  localeOverride?: string;
}

export function ToolUseIndicator({
  toolName,
  status,
  localeOverride,
}: ToolUseIndicatorProps) {
  const chatLocale = useChatLocale();
  const locale = (localeOverride as any) ?? chatLocale;
  const label = getToolLabel(toolName, locale, status);
  const Icon = TOOL_ICON_MAP[toolName] ?? Search;

  const isRunning = status === "running";
  const baseClass =
    "inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border";
  const stateClass = isRunning
    ? "bg-[var(--accent)]/10 text-[var(--accent)] border-[var(--accent)]/30"
    : "bg-[var(--success)]/10 text-[var(--success)] border-[var(--success)]/30";

  return (
    <div
      className={`${baseClass} ${stateClass}`}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <Icon className="w-3.5 h-3.5" aria-hidden="true" />
      {isRunning ? (
        <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
      ) : (
        <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
      )}
      <span>{label}</span>
    </div>
  );
}
