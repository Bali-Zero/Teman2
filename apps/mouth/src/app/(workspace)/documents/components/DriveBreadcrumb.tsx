'use client';

import { motion } from 'framer-motion';
import { ChevronRight, Home, Building2 } from 'lucide-react';
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
      className="flex items-center gap-1 overflow-x-auto whitespace-nowrap py-1 text-sm"
    >
      {/* Home button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onNavigate(-1)}
        className="group h-8 gap-2 rounded-md px-3 hover:bg-[#f5f5f5] text-[#5f6368] hover:text-[#202124]"
      >
        <Home className="h-4 w-4 transition-transform group-hover:scale-110" />
        <span className="font-medium">Il mio Drive</span>
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
            transition={{ delay: index * 0.05 }}
            className="flex items-center"
          >
            <ChevronRight className="h-4 w-4 text-[var(--foreground-muted)]" />

            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate(index)}
              className={`
                group h-8 gap-2 rounded-md px-3 transition-all
                ${
                  isLast
                    ? 'bg-[#e8f0fe] font-semibold text-[#1a73e8]'
                    : 'text-[#5f6368] hover:bg-[#f5f5f5] hover:text-[#202124]'
                }
              `}
            >
              {/* Department icon if applicable */}
              {deptInfo && (
                <div
                  className="flex h-5 w-5 items-center justify-center rounded"
                  style={{ backgroundColor: `${deptInfo.primary}20` }}
                >
                  <deptInfo.icon className="h-3 w-3" style={{ color: deptInfo.primary }} />
                </div>
              )}

              <span className="max-w-[150px] truncate">{item.name}</span>

              {/* Department badge for department folders */}
              {deptInfo && isLast && (
                <span
                  className="ml-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white"
                  style={{ backgroundColor: deptInfo.primary }}
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
