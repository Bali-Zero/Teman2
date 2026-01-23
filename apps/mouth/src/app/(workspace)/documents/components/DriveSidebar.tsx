'use client';

import { motion } from 'framer-motion';
import {
  Plus,
  FolderPlus,
  Upload,
  HardDrive,
  Clock,
  Star,
  Trash2,
  Cloud,
  ChevronDown,
} from 'lucide-react';
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

const navItems = [
  { id: 'my-drive' as const, label: 'Il mio Drive', icon: HardDrive },
  { id: 'recent' as const, label: 'Recenti', icon: Clock },
  { id: 'starred' as const, label: 'Speciali', icon: Star },
  { id: 'trash' as const, label: 'Cestino', icon: Trash2 },
];

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
      animate={{ width: 224, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="flex h-full flex-col border-r border-[#dadce0] bg-[#f8f9fa] dark:bg-[var(--background-subtle)]"
    >
      {/* New button */}
      <div className="p-4">
        <div className="relative">
          <Button
            onClick={(e) => {
              setShowNewMenu(!showNewMenu);
              onNewClick(e);
            }}
            className="w-full justify-start gap-3 h-12 rounded-2xl bg-white border border-[#dadce0] text-[#3c4043] shadow-md hover:bg-[#f8f9fa] hover:shadow-lg transition-all"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white">
              <Plus className="h-6 w-6 text-[#1a73e8]" />
            </div>
            <span className="font-medium">Nuovo</span>
          </Button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          const isDisabled = item.id !== 'my-drive'; // Only My Drive works for now

          return (
            <button
              key={item.id}
              onClick={() => !isDisabled && onViewChange(item.id)}
              disabled={isDisabled}
              className={`
                w-full flex items-center gap-3 px-3 py-2 rounded-full text-sm font-medium transition-all
                ${
                  isActive
                    ? 'bg-[#e8f0fe] text-[#1a73e8]'
                    : isDisabled
                      ? 'text-[#9aa0a6] cursor-not-allowed'
                      : 'text-[#5f6368] hover:bg-[#f1f3f4] hover:text-[#202124]'
                }
              `}
            >
              <item.icon className={`h-5 w-5 ${isActive ? 'text-[#1a73e8]' : ''}`} />
              <span>{item.label}</span>
              {isDisabled && (
                <span className="ml-auto text-[10px] text-[#9aa0a6] bg-[#e8eaed] px-1.5 py-0.5 rounded">
                  Presto
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Storage indicator */}
      <div className="p-4 border-t border-[#dadce0]">
        <div className="flex items-center gap-2 mb-2">
          <Cloud className="h-4 w-4 text-[#5f6368]" />
          <span className="text-xs text-[#5f6368]">Spazio di archiviazione</span>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-[#e8eaed] rounded-full overflow-hidden mb-2">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(usagePercent, 100)}%` }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className={`h-full rounded-full ${
              usagePercent > 90
                ? 'bg-[#ea4335]'
                : usagePercent > 70
                  ? 'bg-[#fbbc04]'
                  : 'bg-[#1a73e8]'
            }`}
          />
        </div>

        <p className="text-xs text-[#5f6368]">
          {formatStorage(storageUsed)} di {formatStorage(storageTotal)} utilizzati
        </p>
      </div>
    </motion.div>
  );
}
