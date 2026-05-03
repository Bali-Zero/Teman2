'use client';

/**
 * ContextPanel — collapsible right-side pane for authenticated chat users.
 *
 * Tabs:
 *   - Info: about the current chat
 *   - Matters: the user's active matters, pulled from /api/portal/matters
 */

import { useState } from 'react';
import { usePortalMatters } from '@/hooks';
import { ChevronLeft, ChevronRight, Info, Briefcase } from 'lucide-react';

type Tab = 'info' | 'matters';

export function ContextPanel() {
  const [tab, setTab] = useState<Tab>('info');
  const [collapsed, setCollapsed] = useState(false);
  const { data } = usePortalMatters();

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="sticky top-0 w-8 h-full flex items-start justify-center pt-4 border-l border-[var(--glass-rim)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
        aria-label="Expand context panel"
      >
        <ChevronLeft className="w-4 h-4 text-[var(--tx-secondary)]" />
      </button>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between p-3 border-b border-[var(--glass-rim)]">
        <nav className="flex gap-1" role="tablist">
          <TabButton
            active={tab === 'info'}
            onClick={() => setTab('info')}
            label="Info"
            icon={<Info className="w-3 h-3" />}
          />
          <TabButton
            active={tab === 'matters'}
            onClick={() => setTab('matters')}
            label={`Matters${data ? ` (${data.matters.length})` : ''}`}
            icon={<Briefcase className="w-3 h-3" />}
          />
        </nav>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse context panel"
          className="p-1 rounded hover:bg-[rgba(255,255,255,0.04)]"
        >
          <ChevronRight className="w-4 h-4 text-[var(--tx-secondary)]" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'info' && <InfoTab />}
        {tab === 'matters' && <MattersTab matters={data?.matters ?? []} />}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-widest font-semibold rounded transition-colors ${
        active
          ? 'bg-[rgba(255,255,255,0.05)] text-[var(--tx-primary)]'
          : 'text-[var(--tx-secondary)] hover:text-[var(--tx-primary)]'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function InfoTab() {
  return (
    <div className="space-y-2 text-xs text-[var(--tx-secondary)]">
      <p>
        You're chatting with <strong className="text-[var(--tx-primary)]">Zantara</strong>, the
        Bali Zero business assistant.
      </p>
      <p>
        Ask about visas, company setup, tax, KBLI codes. I'll escalate to the human team when
        something needs official sign-off.
      </p>
    </div>
  );
}

function MattersTab({
  matters,
}: {
  matters: Array<{
    id: number;
    title: string;
    type: string;
    progress: number;
    next_deadline: string | null;
  }>;
}) {
  if (matters.length === 0) {
    return (
      <p className="text-xs text-[var(--tx-secondary)] italic">
        No active matters. When the team starts something for you, it will show here.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {matters.map((m) => (
        <li
          key={m.id}
          className="p-3 rounded-lg border border-[var(--glass-rim)] bg-[rgba(255,255,255,0.01)]"
        >
          <div className="flex justify-between items-baseline gap-2">
            <a
              href={`/portal/matters/${m.id}`}
              className="text-sm font-medium text-[var(--tx-primary)] hover:text-[var(--bz-copper)] transition-colors truncate"
            >
              {m.title}
            </a>
            <span className="text-[9px] uppercase tracking-widest text-[var(--tx-secondary)]">
              {m.type}
            </span>
          </div>
          <div className="text-xs text-[var(--tx-secondary)] mt-1">
            {m.progress}% {m.next_deadline ? `· due ${new Date(m.next_deadline).toLocaleDateString()}` : ''}
          </div>
        </li>
      ))}
    </ul>
  );
}
