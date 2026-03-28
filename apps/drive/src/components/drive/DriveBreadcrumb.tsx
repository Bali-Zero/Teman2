'use client';

import { motion } from 'framer-motion';
import { ChevronRight, Home } from 'lucide-react';
import type { BreadcrumbItem } from '@/lib/api/drive/drive.types';
import { Button } from '@/components/ui/button';
import { getDepartmentInfo } from './file-icon';

interface DriveBreadcrumbProps {
  items: BreadcrumbItem[];
  onNavigate: (index: number) => void;
}

export function DriveBreadcrumb({ items, onNavigate }: DriveBreadcrumbProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-0.5 overflow-x-auto whitespace-nowrap py-1"
    >
      {/* Home button - Elegant minimal */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onNavigate(-1)}
        className="group h-8 gap-2 rounded-lg px-3 text-slate-500 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/60 hover:text-slate-700 dark:hover:text-slate-200"
      >
        <Home className="h-4 w-4 transition-transform duration-200 group-hover:scale-105" />
        <span className="text-[13px] font-medium">Il Mio Drive</span>
      </Button>

      {/* Breadcrumb items */}
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const deptInfo = getDepartmentInfo(item.name);

        return (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, x: -5 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.04 }}
            className="flex items-center"
          >
            <ChevronRight className="h-4 w-4 text-slate-300 dark:text-slate-600" />

            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate(index)}
              className={`
                group h-8 gap-2 rounded-lg px-3 transition-all duration-200
                ${
                  isLast
                    ? 'bg-blue-50/80 dark:bg-blue-950/40 font-semibold text-blue-600 dark:text-blue-400 pointer-events-none'
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/60 hover:text-slate-700 dark:hover:text-slate-200'
                }
              `}
              {...(isLast ? { 'aria-current': 'page' as const } : {})}
            >
              {/* Department icon if applicable */}
              {deptInfo && (
                <div
                  className="flex h-5 w-5 items-center justify-center rounded-md"
                  style={{ backgroundColor: `${deptInfo.primary}15` }}
                >
                  <deptInfo.icon className="h-3 w-3" style={{ color: deptInfo.primary }} />
                </div>
              )}

              <span className="max-w-[150px] truncate text-[13px]">{item.name}</span>

              {/* Department badge for department folders - Subtle pill */}
              {deptInfo && isLast && (
                <span
                  className="ml-1 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
                  style={{
                    backgroundColor: `${deptInfo.primary}15`,
                    color: deptInfo.primary,
                  }}
                >
                  {deptInfo.label}
                </span>
              )}
            </Button>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
