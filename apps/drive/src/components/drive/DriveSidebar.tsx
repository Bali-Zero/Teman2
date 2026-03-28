'use client';

import { motion } from 'framer-motion';
import { Plus, HardDrive, Cloud } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface DriveSidebarProps {
  isCollapsed?: boolean;
  onNewClick: (e: React.MouseEvent) => void;
  onUploadClick: () => void;
  activeView: 'my-drive' | 'recent' | 'starred' | 'trash';
  onViewChange: (view: 'my-drive' | 'recent' | 'starred' | 'trash') => void;
  storageUsed?: number;
  storageTotal?: number;
}

const navItems = [{ id: 'my-drive' as const, label: 'Bali Zero Drive', icon: HardDrive }];

export function DriveSidebar({
  isCollapsed = false,
  onNewClick,
  onUploadClick,
  activeView,
  onViewChange,
  storageUsed = 0,
  storageTotal = 15 * 1024 * 1024 * 1024, // 15GB default
}: DriveSidebarProps) {
  const [showNewMenu, setShowNewMenu] = useState(false);

  const formatStorage = (bytes: number) => {
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  const usagePercent = (storageUsed / storageTotal) * 100;

  if (isCollapsed) {
    return (
      <motion.div
        initial={{ width: 72 }}
        animate={{ width: 72 }}
        className="flex h-full flex-col border-r border-[#dadce0] bg-[#f8f9fa] dark:bg-[var(--background-subtle)] py-4"
      >
        {/* Collapsed New button */}
        <div className="px-3 mb-4">
          <Button
            onClick={onNewClick}
            className="w-12 h-12 rounded-full bg-white border border-[#dadce0] text-[#3c4043] shadow-sm hover:bg-[#f1f3f4] hover:shadow-md transition-all p-0"
            aria-label="Nuovo file o cartella"
          >
            <Plus className="h-6 w-6 text-[#1a73e8]" />
          </Button>
        </div>

        {/* Collapsed nav items */}
        <nav className="flex-1 px-2 space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`
                w-full flex items-center justify-center p-3 rounded-full transition-colors
                ${
                  activeView === item.id
                    ? 'bg-[#e8f0fe] text-[#1a73e8]'
                    : 'text-[#5f6368] hover:bg-[#f1f3f4]'
                }
              `}
              title={item.label}
              aria-label={item.label}
            >
              <item.icon className="h-5 w-5" />
            </button>
          ))}
        </nav>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 220, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      role="navigation"
      aria-label="Navigazione Drive"
      className="flex h-full flex-col border-r border-slate-200/60 dark:border-slate-700/40 bg-slate-50/50 dark:bg-slate-900/30"
    >
      {/* New button - Clean minimal style */}
      <div className="p-3">
        <Button
          onClick={(e) => {
            setShowNewMenu(!showNewMenu);
            onNewClick(e);
          }}
          className="w-full justify-start gap-2.5 h-10 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700/60 text-slate-700 dark:text-slate-200 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 transition-all"
        >
          <Plus className="h-4 w-4 text-[#d4845a]" />
          <span className="text-sm font-medium">Nuovo</span>
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 mt-1">
        {navItems.map((item) => {
          const isActive = activeView === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`
                w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors
                ${
                  isActive
                    ? 'bg-[#d4845a]/10 text-[#d4845a]'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60'
                }
              `}
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Storage indicator - Elegant minimal */}
      <div className="p-3 mx-2 mb-2 rounded-xl bg-white/60 dark:bg-slate-800/40 border border-slate-200/40 dark:border-slate-700/30">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Cloud className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              Spazio
            </span>
          </div>
          <span className="text-[10px] text-slate-400">{formatStorage(storageTotal)}</span>
        </div>

        {/* Progress bar - Thin elegant style */}
        <div className="h-1 bg-slate-200/60 dark:bg-slate-700/40 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(usagePercent, 100)}%` }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="h-full rounded-full bg-[#d4845a]"
          />
        </div>

        <p className="mt-1.5 text-[10px] text-slate-400 dark:text-slate-500">
          {formatStorage(storageUsed)} utilizzati
        </p>
      </div>
    </motion.div>
  );
}
