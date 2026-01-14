'use client';

import { motion } from 'framer-motion';
import {
  Building2, Users, TrendingUp, Scale, Settings, Briefcase,
  HardDrive, Clock, Star, FolderOpen, ChevronRight, Sparkles
} from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { DEPARTMENT_COLORS, getDepartmentInfo } from './file-icon';

interface DepartmentHomeProps {
  files: FileItem[];
  onFolderClick: (folder: FileItem) => void;
  storageUsed?: number;
  storageTotal?: number;
}

// Department order for consistent display
const DEPARTMENT_ORDER = ['BOARD', 'CRM', 'MARKETING', 'PERATURAN', 'SETUP TEAM', 'TAX DEPARTMENT'];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.9 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring' as const,
      stiffness: 200,
      damping: 20,
    },
  },
};

const heroVariants = {
  hidden: { opacity: 0, y: -20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
      ease: 'easeOut' as const,
    },
  },
};

export function DepartmentHome({ files, onFolderClick, storageUsed = 0, storageTotal = 30 * 1024 * 1024 * 1024 * 1024 }: DepartmentHomeProps) {
  // Separate department folders from other folders
  const departmentFolders = files.filter(f => f.is_folder && getDepartmentInfo(f.name));
  const otherFolders = files.filter(f => f.is_folder && !getDepartmentInfo(f.name));
  const recentFiles = files.filter(f => !f.is_folder).slice(0, 6);

  // Sort department folders by defined order
  const sortedDepartments = [...departmentFolders].sort((a, b) => {
    const aIndex = DEPARTMENT_ORDER.findIndex(d => a.name.toUpperCase().includes(d));
    const bIndex = DEPARTMENT_ORDER.findIndex(d => b.name.toUpperCase().includes(d));
    return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
  });

  const storagePercentage = (storageUsed / storageTotal) * 100;

  return (
    <div className="min-h-full bg-gradient-to-b from-[var(--background)] to-[var(--background-subtle)]">
      {/* Hero Section */}
      <motion.div
        variants={heroVariants}
        initial="hidden"
        animate="visible"
        className="relative overflow-hidden bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-500 px-8 py-12"
      >
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/20" />
          <div className="absolute -bottom-10 -left-10 h-48 w-48 rounded-full bg-white/20" />
          <div className="absolute right-1/4 top-1/2 h-32 w-32 rounded-full bg-white/10" />
        </div>

        <div className="relative mx-auto max-w-7xl">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-emerald-200" />
                <span className="text-sm font-medium text-emerald-100">Workspace Documenti</span>
              </div>
              <h1 className="text-3xl font-bold text-white md:text-4xl">
                Benvenuto nel tuo Drive
              </h1>
              <p className="mt-2 text-emerald-100">
                Accedi ai tuoi documenti organizzati per dipartimento
              </p>
            </div>

            {/* Storage indicator */}
            <div className="flex items-center gap-4 rounded-2xl bg-white/10 p-4 backdrop-blur-sm">
              <HardDrive className="h-10 w-10 text-white" />
              <div>
                <div className="mb-1 text-sm text-emerald-100">Spazio utilizzato</div>
                <div className="text-xl font-bold text-white">
                  {formatStorage(storageUsed)} / {formatStorage(storageTotal)}
                </div>
                <div className="mt-2 h-2 w-40 overflow-hidden rounded-full bg-white/20">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${storagePercentage}%` }}
                    transition={{ duration: 1, delay: 0.5 }}
                    className="h-full rounded-full bg-white"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* Department Grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="mb-12"
        >
          <h2 className="mb-6 flex items-center gap-3 text-xl font-bold text-[var(--foreground)]">
            <Building2 className="h-6 w-6 text-emerald-500" />
            Dipartimenti
          </h2>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {sortedDepartments.map((folder) => {
              const deptInfo = getDepartmentInfo(folder.name);
              if (!deptInfo) return null;

              return (
                <DepartmentCard
                  key={folder.id}
                  folder={folder}
                  deptInfo={deptInfo}
                  onClick={() => onFolderClick(folder)}
                />
              );
            })}
          </div>
        </motion.div>

        {/* Quick Access Section */}
        {(otherFolders.length > 0 || recentFiles.length > 0) && (
          <div className="grid gap-8 lg:grid-cols-2">
            {/* Other Folders */}
            {otherFolders.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 }}
              >
                <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[var(--foreground)]">
                  <FolderOpen className="h-5 w-5 text-amber-500" />
                  Altre Cartelle
                </h3>
                <div className="space-y-2">
                  {otherFolders.slice(0, 5).map((folder) => (
                    <button
                      key={folder.id}
                      onClick={() => onFolderClick(folder)}
                      className="flex w-full items-center gap-3 rounded-xl bg-[var(--background-subtle)] p-3 transition-all hover:bg-[var(--accent)] hover:shadow-md"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10">
                        <FolderOpen className="h-5 w-5 text-amber-500" />
                      </div>
                      <span className="flex-1 truncate text-left font-medium text-[var(--foreground)]">
                        {folder.name}
                      </span>
                      <ChevronRight className="h-4 w-4 text-[var(--foreground-muted)]" />
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Recent Files */}
            {recentFiles.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.7 }}
              >
                <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[var(--foreground)]">
                  <Clock className="h-5 w-5 text-blue-500" />
                  File Recenti
                </h3>
                <div className="space-y-2">
                  {recentFiles.map((file) => (
                    <button
                      key={file.id}
                      onClick={() => file.web_view_link && window.open(file.web_view_link, '_blank')}
                      className="flex w-full items-center gap-3 rounded-xl bg-[var(--background-subtle)] p-3 transition-all hover:bg-[var(--accent)] hover:shadow-md"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                        <Clock className="h-5 w-5 text-blue-500" />
                      </div>
                      <div className="flex-1 text-left">
                        <div className="truncate font-medium text-[var(--foreground)]">
                          {file.name}
                        </div>
                        <div className="text-xs text-[var(--foreground-muted)]">
                          {file.modified_time && new Date(file.modified_time).toLocaleDateString('it-IT')}
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-[var(--foreground-muted)]" />
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface DepartmentCardProps {
  folder: FileItem;
  deptInfo: typeof DEPARTMENT_COLORS[string];
  onClick: () => void;
}

function DepartmentCard({ folder, deptInfo, onClick }: DepartmentCardProps) {
  const Icon = deptInfo.icon;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onClick();
  };

  return (
    <motion.div
      variants={itemVariants}
      whileHover={{ scale: 1.02, y: -4 }}
      whileTap={{ scale: 0.98 }}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className="group relative flex cursor-pointer items-start gap-5 overflow-hidden rounded-2xl bg-[var(--background)] p-6 text-left shadow-lg transition-all hover:shadow-xl"
      style={{
        boxShadow: `0 4px 20px -4px ${deptInfo.primary}20`,
      }}
    >
      {/* Gradient background on hover */}
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: `linear-gradient(135deg, ${deptInfo.primary}10 0%, transparent 60%)`,
        }}
      />

      {/* Accent line */}
      <div
        className="pointer-events-none absolute left-0 top-0 h-full w-1 transition-all duration-300 group-hover:w-1.5"
        style={{ backgroundColor: deptInfo.primary }}
      />

      {/* Icon */}
      <div
        className="pointer-events-none relative flex h-14 w-14 shrink-0 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110"
        style={{ backgroundColor: `${deptInfo.primary}15` }}
      >
        <Icon
          className="h-7 w-7 transition-transform duration-300 group-hover:scale-110"
          style={{ color: deptInfo.primary }}
        />
      </div>

      {/* Content */}
      <div className="pointer-events-none relative flex-1">
        <h3 className="mb-1 text-lg font-bold text-[var(--foreground)]">{folder.name}</h3>
        <p className="text-sm text-[var(--foreground-muted)]">
          Accedi ai documenti del {deptInfo.label.toLowerCase()}
        </p>

        {/* Arrow indicator */}
        <div className="mt-3 flex items-center gap-1 text-sm font-medium" style={{ color: deptInfo.primary }}>
          <span>Apri cartella</span>
          <ChevronRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
        </div>
      </div>

      {/* Decorative dots */}
      <div className="pointer-events-none absolute -bottom-4 -right-4 opacity-10">
        <svg width="80" height="80" viewBox="0 0 80 80">
          {[...Array(16)].map((_, i) => (
            <circle
              key={i}
              cx={(i % 4) * 20 + 10}
              cy={Math.floor(i / 4) * 20 + 10}
              r="3"
              fill={deptInfo.primary}
            />
          ))}
        </svg>
      </div>
    </motion.div>
  );
}

function formatStorage(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}
