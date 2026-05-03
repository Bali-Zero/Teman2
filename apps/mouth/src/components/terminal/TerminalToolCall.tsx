/**
 * TerminalToolCall — collapsible pill rendering a single backend tool call.
 *
 * Running state: copper border + pulse icon.
 * Complete state: green accent + check icon.
 * Error state: red accent + alert icon.
 * Click toggles an expanded view with args JSON and result string.
 */

"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  Cog,
  Wrench,
} from "lucide-react";
import type { ToolCall } from "./types";

interface TerminalToolCallProps {
  toolCall: ToolCall;
}

function formatDuration(ms?: number): string {
  if (!ms || ms <= 0) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function TerminalToolCall({ toolCall }: TerminalToolCallProps) {
  const [expanded, setExpanded] = useState(false);

  const running = toolCall.status === "running";
  const errored = toolCall.status === "error";

  const borderColour = errored
    ? "border-[var(--bz-red)]/60"
    : running
      ? "border-[var(--bz-accent)]/80 animate-pulse"
      : "border-[var(--bz-green)]/60";

  const iconTint = errored
    ? "text-[var(--bz-red)]"
    : running
      ? "text-[var(--bz-accent)]"
      : "text-[var(--bz-green)]";

  const Icon = errored ? AlertTriangle : running ? Cog : CircleCheck;
  const ChevIcon = expanded ? ChevronDown : ChevronRight;

  const hasDetails =
    (toolCall.args && Object.keys(toolCall.args).length > 0) ||
    Boolean(toolCall.result);

  return (
    <div
      className={`inline-flex flex-col max-w-full rounded-full ${expanded ? "rounded-xl" : ""} border ${borderColour} bg-black/30 transition-all`}
    >
      <button
        type="button"
        onClick={() => hasDetails && setExpanded((e) => !e)}
        className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-white/85 disabled:cursor-default"
        disabled={!hasDetails}
        aria-expanded={expanded}
        aria-label={`Tool call ${toolCall.name} ${toolCall.status}`}
      >
        <Icon
          size={11}
          className={`${iconTint} ${running ? "animate-spin" : ""} flex-shrink-0`}
        />
        <Wrench size={10} className="text-white/40 flex-shrink-0" />
        <span className="font-medium">{toolCall.name}</span>
        {toolCall.duration !== undefined && (
          <span className="text-white/40">· {formatDuration(toolCall.duration)}</span>
        )}
        {hasDetails && (
          <ChevIcon size={11} className="text-white/40 ml-0.5 flex-shrink-0" />
        )}
      </button>
      {expanded && hasDetails && (
        <div className="px-3 pb-2 pt-1 border-t border-white/10 mt-0.5 font-mono text-[11px] text-white/75 space-y-2">
          {toolCall.args && Object.keys(toolCall.args).length > 0 && (
            <div>
              <div className="text-[9.5px] uppercase tracking-[1px] text-white/40 mb-0.5">
                args
              </div>
              <pre className="whitespace-pre-wrap break-all text-white/75">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </div>
          )}
          {toolCall.result && (
            <div>
              <div className="text-[9.5px] uppercase tracking-[1px] text-white/40 mb-0.5">
                result
              </div>
              <pre className="whitespace-pre-wrap break-all text-white/75 max-h-48 overflow-y-auto">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
