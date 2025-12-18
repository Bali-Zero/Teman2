"use client";

import React from "react";
import { Menu, Bell, Search, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface HeaderProps {
  onMenuClick: () => void;
  title?: string;
}

export function Header({ onMenuClick, title = "Dashboard" }: HeaderProps) {
  return (
    <header className="h-14 border-b border-[var(--border)] bg-[var(--background)] flex items-center justify-between px-4 sticky top-0 z-30">
      {/* Left side */}
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 rounded-lg hover:bg-[var(--background-secondary)] transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-semibold text-[var(--foreground)]">
          {title}
        </h1>
      </div>

      {/* Center - Search (hidden on mobile) */}
      <div className="hidden md:flex flex-1 max-w-md mx-4">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <Input
            placeholder="Search content, signals, assets..."
            className="pl-9 bg-[var(--background-secondary)] border-transparent focus:border-[var(--border)]"
          />
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-[var(--accent)] rounded-full" />
        </Button>
        <Button size="sm" className="hidden sm:flex gap-2">
          <Plus className="w-4 h-4" />
          New Content
        </Button>
        <Button size="icon" className="sm:hidden">
          <Plus className="w-5 h-5" />
        </Button>
      </div>
    </header>
  );
}
