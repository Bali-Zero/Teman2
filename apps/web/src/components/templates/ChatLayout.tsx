/**
 * ChatLayout — page layout wrapper with header.
 */

"use client";

import { MessageSquare, Plus } from "lucide-react";
import { Button } from "@/components/atoms/Button";

interface ChatLayoutProps {
  children: React.ReactNode;
  onNewChat?: () => void;
}

export function ChatLayout({ children, onNewChat }: ChatLayoutProps) {
  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-accent" />
          <span className="text-sm font-semibold">Nuzantara V6</span>
        </div>
        {onNewChat && (
          <Button
            variant="ghost"
            onClick={onNewChat}
            aria-label="Nuova chat"
            className="h-8 gap-1.5 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            New Chat
          </Button>
        )}
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
