'use client';

import { ReactNode } from 'react';

interface ObsidianPanelProps {
  children: ReactNode;
  className?: string;
  width?: number | string;
}

export function ObsidianPanel({ children, className = '', width }: ObsidianPanelProps) {
  return (
    <div
      className={`obsidian-glass rounded-lg ${className}`}
      style={width ? { width } : undefined}
    >
      <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-lg">
        <div className="scan-line" />
      </div>
      <div className="relative z-10">{children}</div>
    </div>
  );
}
