import {
  Image,
  FileSpreadsheet,
  Presentation,
  FileText,
  FileCode,
  File,
  Users,
  Briefcase,
  TrendingUp,
  Scale,
  Settings,
  Building2,
} from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';

// Department color mapping - matches the organization structure
export const DEPARTMENT_COLORS: Record<
  string,
  { primary: string; secondary: string; icon: typeof Users; label: string }
> = {
  BOARD: {
    primary: '#8B5CF6', // Violet
    secondary: '#A78BFA',
    icon: Building2,
    label: 'Board',
  },
  CRM: {
    primary: '#3B82F6', // Blue
    secondary: '#60A5FA',
    icon: Users,
    label: 'CRM',
  },
  MARKETING: {
    primary: '#EC4899', // Pink
    secondary: '#F472B6',
    icon: TrendingUp,
    label: 'Marketing',
  },
  PERATURAN: {
    primary: '#10B981', // Emerald
    secondary: '#34D399',
    icon: Scale,
    label: 'Peraturan',
  },
  'SETUP TEAM': {
    primary: '#F59E0B', // Amber
    secondary: '#FBBF24',
    icon: Settings,
    label: 'Setup Team',
  },
  'TAX DEPARTMENT': {
    primary: '#EF4444', // Red
    secondary: '#F87171',
    icon: Briefcase,
    label: 'Tax Department',
  },
};

// Get department info from folder name
export function getDepartmentInfo(folderName: string) {
  const upperName = folderName.toUpperCase();
  for (const [key, value] of Object.entries(DEPARTMENT_COLORS)) {
    if (upperName.includes(key) || upperName === key) {
      return value;
    }
  }
  return null;
}

// Modern 3D folder with department colors
interface DepartmentFolderProps {
  className?: string;
  primaryColor?: string;
  secondaryColor?: string;
  DepartmentIcon?: typeof Users;
}

export function DepartmentFolder({
  className,
  primaryColor = '#F59E0B',
  secondaryColor = '#FBBF24',
  DepartmentIcon,
}: DepartmentFolderProps) {
  return (
    <div className={`relative ${className}`}>
      <svg
        viewBox="0 0 64 64"
        className="w-full h-full"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Shadow */}
        <ellipse cx="32" cy="58" rx="24" ry="4" fill="black" opacity="0.1" />

        {/* Back panel with gradient */}
        <defs>
          <linearGradient
            id={`folder-grad-${primaryColor.replace('#', '')}`}
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor={secondaryColor} />
            <stop offset="100%" stopColor={primaryColor} />
          </linearGradient>
          <filter id="folder-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.2" />
          </filter>
        </defs>

        {/* Back panel */}
        <path
          d="M6 16C6 13.7909 7.79086 12 10 12H24L30 18H54C56.2091 18 58 19.7909 58 22V50C58 52.2091 56.2091 54 54 54H10C7.79086 54 6 52.2091 6 50V16Z"
          fill={primaryColor}
          filter="url(#folder-shadow)"
        />

        {/* Front panel with gradient */}
        <path
          d="M6 22C6 19.7909 7.79086 18 10 18H54C56.2091 18 58 19.7909 58 22V50C58 52.2091 56.2091 54 54 54H10C7.79086 54 6 52.2091 6 50V22Z"
          fill={`url(#folder-grad-${primaryColor.replace('#', '')})`}
        />

        {/* Top shine */}
        <path
          d="M10 18H54C56.2091 18 58 19.7909 58 22V24H6V22C6 19.7909 7.79086 18 10 18Z"
          fill="white"
          opacity="0.2"
        />

        {/* Inner line detail */}
        <path d="M10 26H54" stroke={primaryColor} strokeWidth="1" opacity="0.3" />
      </svg>

      {/* Department icon overlay */}
      {DepartmentIcon && (
        <div className="absolute inset-0 flex items-center justify-center pt-2">
          <DepartmentIcon className="w-1/3 h-1/3 text-white/90 drop-shadow-sm" strokeWidth={1.5} />
        </div>
      )}
    </div>
  );
}

// Standard Windows-style filled folder icon
function WindowsFolder({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Shadow */}
      <ellipse cx="24" cy="42" rx="16" ry="2" fill="black" opacity="0.1" />

      {/* Back panel shadow */}
      <path
        d="M4 12C4 10.8954 4.89543 10 6 10H18L22 14H42C43.1046 14 44 14.8954 44 16V38C44 39.1046 43.1046 40 42 40H6C4.89543 40 4 39.1046 4 38V12Z"
        fill="#D97706"
      />
      {/* Front panel */}
      <path
        d="M4 16C4 14.8954 4.89543 14 6 14H42C43.1046 14 44 14.8954 44 16V38C44 39.1046 43.1046 40 42 40H6C4.89543 40 4 39.1046 4 38V16Z"
        fill="#F59E0B"
      />
      {/* Top highlight */}
      <path
        d="M6 14H18L22 10H6C4.89543 10 4 10.8954 4 12V16C4 14.8954 4.89543 14 6 14Z"
        fill="#FBBF24"
      />
      {/* Inner shadow for depth */}
      <path d="M6 18H42V20H6V18Z" fill="#D97706" opacity="0.3" />
    </svg>
  );
}

export function getFileIcon(file: FileItem, size: 'sm' | 'lg' = 'lg') {
  const mimeType = file.mime_type || '';
  const sizeClass = size === 'sm' ? 'h-5 w-5' : 'h-12 w-12';

  if (file.is_folder) {
    // Check if it's a department folder
    const deptInfo = getDepartmentInfo(file.name);
    if (deptInfo) {
      return (
        <DepartmentFolder
          className={sizeClass}
          primaryColor={deptInfo.primary}
          secondaryColor={deptInfo.secondary}
          DepartmentIcon={deptInfo.icon}
        />
      );
    }
    return <WindowsFolder className={sizeClass} />;
  }
  if (mimeType.includes('image')) {
    return <Image className={`${sizeClass} text-pink-500`} />;
  }
  if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) {
    return <FileSpreadsheet className={`${sizeClass} text-green-500`} />;
  }
  if (mimeType.includes('presentation')) {
    return <Presentation className={`${sizeClass} text-yellow-500`} />;
  }
  if (mimeType.includes('document') || mimeType.includes('word')) {
    return <FileText className={`${sizeClass} text-blue-500`} />;
  }
  if (mimeType.includes('pdf')) {
    return <FileText className={`${sizeClass} text-red-500`} />;
  }
  if (mimeType.includes('code') || mimeType.includes('javascript') || mimeType.includes('json')) {
    return <FileCode className={`${sizeClass} text-purple-500`} />;
  }
  return <File className={`${sizeClass} text-gray-400`} />;
}
