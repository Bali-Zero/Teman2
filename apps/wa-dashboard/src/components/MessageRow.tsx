import type { WaMessage } from "@/types/wa-message";
import { cn } from "@/lib/cn";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Users,
  AlertTriangle,
} from "lucide-react";

interface Props {
  message: WaMessage;
}

export function MessageRow({ message }: Props) {
  const isIncoming = message.direction === "incoming";
  const isGroup = message.chat_type === "group";
  const Arrow = isIncoming ? ArrowDownLeft : ArrowUpRight;
  const date = message.message_date ? new Date(message.message_date) : null;

  return (
    <div
      className={cn(
        "px-4 py-3 border-b border-neutral-800 hover:bg-neutral-900/40 transition-colors",
        isIncoming
          ? "border-l-2 border-l-blue-700"
          : "border-l-2 border-l-emerald-700",
      )}
    >
      <div className="flex items-start gap-3">
        <Arrow
          className={cn(
            "h-4 w-4 mt-1 flex-shrink-0",
            isIncoming ? "text-blue-400" : "text-emerald-400",
          )}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-neutral-500 mb-1">
            {isGroup && <Users className="h-3 w-3" />}
            <span className="font-mono">
              {message.counterpart_phone ?? "?"}
            </span>
            <span>→</span>
            <span className="font-mono">
              {message.team_member_phone ?? "?"}
            </span>
            {message.attention_priority !== null &&
              message.attention_priority > 0 && (
                <span className="ml-auto flex items-center gap-1 text-amber-400">
                  <AlertTriangle className="h-3 w-3" />P
                  {message.attention_priority}
                </span>
              )}
            {date && (
              <span className="ml-auto tabular-nums">
                {date.toLocaleTimeString("it-IT")}
              </span>
            )}
          </div>
          <div className="text-sm text-neutral-200 whitespace-pre-wrap break-words">
            {message.body || (
              <span className="text-neutral-500 italic">(no body)</span>
            )}
          </div>
          {message.media_type && (
            <div className="text-xs text-neutral-500 mt-1">
              [media: {message.media_type}]
            </div>
          )}
        </div>
        <div className="text-xs text-neutral-600 font-mono tabular-nums">
          #{message.id}
        </div>
      </div>
    </div>
  );
}
