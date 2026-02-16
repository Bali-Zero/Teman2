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
} from "lucide-react";
import type { FileItem } from "@/lib/api/drive/drive.types";

// Department color mapping - matches the organization structure
export const DEPARTMENT_COLORS: Record<
  string,
  { primary: string; secondary: string; icon: typeof Users; label: string }
> = {
  BOARD: {
    primary: "#8B5CF6", // Violet
    secondary: "#A78BFA",
    icon: Building2,
    label: "Board",
  },
  CRM: {
    primary: "#3B82F6", // Blue
    secondary: "#60A5FA",
    icon: Users,
    label: "CRM",
  },
  MARKETING: {
    primary: "#EC4899", // Pink
    secondary: "#F472B6",
    icon: TrendingUp,
    label: "Marketing",
  },
  PERATURAN: {
    primary: "#10B981", // Emerald
    secondary: "#34D399",
    icon: Scale,
    label: "Peraturan",
  },
  "SETUP TEAM": {
    primary: "#F59E0B", // Amber
    secondary: "#FBBF24",
    icon: Settings,
    label: "Setup Team",
  },
  "TAX DEPARTMENT": {
    primary: "#EF4444", // Red
    secondary: "#F87171",
    icon: Briefcase,
    label: "Tax Department",
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
  primaryColor = "#F59E0B",
  secondaryColor = "#FBBF24",
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
            id={`folder-grad-${primaryColor.replace("#", "")}`}
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor={secondaryColor} />
            <stop offset="100%" stopColor={primaryColor} />
          </linearGradient>
          <filter
            id="folder-shadow"
            x="-20%"
            y="-20%"
            width="140%"
            height="140%"
          >
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
          fill={`url(#folder-grad-${primaryColor.replace("#", "")})`}
        />

        {/* Top shine */}
        <path
          d="M10 18H54C56.2091 18 58 19.7909 58 22V24H6V22C6 19.7909 7.79086 18 10 18Z"
          fill="white"
          opacity="0.2"
        />

        {/* Inner line detail */}
        <path
          d="M10 26H54"
          stroke={primaryColor}
          strokeWidth="1"
          opacity="0.3"
        />
      </svg>

      {/* Department icon overlay */}
      {DepartmentIcon && (
        <div className="absolute inset-0 flex items-center justify-center pt-2">
          <DepartmentIcon
            className="w-1/3 h-1/3 text-white/90 drop-shadow-sm"
            strokeWidth={1.5}
          />
        </div>
      )}
    </div>
  );
}

// Modern elegant folder icon - Soft amber/gold gradient
function ModernFolder({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 56 56"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Elegant amber gradient */}
        <linearGradient
          id="folder-front-grad"
          x1="0%"
          y1="0%"
          x2="0%"
          y2="100%"
        >
          <stop offset="0%" stopColor="#FCD34D" />
          <stop offset="100%" stopColor="#F59E0B" />
        </linearGradient>
        {/* Darker back */}
        <linearGradient id="folder-back-grad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#D97706" />
          <stop offset="100%" stopColor="#B45309" />
        </linearGradient>
        {/* Subtle shadow */}
        <filter
          id="folder-shadow-3d"
          x="-10%"
          y="-5%"
          width="120%"
          height="130%"
        >
          <feDropShadow
            dx="0"
            dy="2"
            stdDeviation="2"
            floodColor="#92400E"
            floodOpacity="0.15"
          />
        </filter>
      </defs>

      {/* Back tab */}
      <path
        d="M10 14C10 12.8954 10.8954 12 12 12H20L24 16H10V14Z"
        fill="url(#folder-back-grad)"
      />

      {/* Main folder body */}
      <path
        d="M8 18C8 16.8954 8.89543 16 10 16H46C47.1046 16 48 16.8954 48 18V42C48 43.1046 47.1046 44 46 44H10C8.89543 44 8 43.1046 8 42V18Z"
        fill="url(#folder-front-grad)"
        filter="url(#folder-shadow-3d)"
      />

      {/* Top highlight */}
      <path
        d="M8 18C8 16.8954 8.89543 16 10 16H46C47.1046 16 48 16.8954 48 18V20H8V18Z"
        fill="white"
        opacity="0.25"
      />

      {/* Subtle inner line */}
      <path
        d="M12 22H44"
        stroke="#D97706"
        strokeOpacity="0.2"
        strokeWidth="0.5"
      />
    </svg>
  );
}

// Modern 2026 file icon with glassmorphism background
interface ModernFileIconProps {
  Icon: typeof File;
  bgColor: string;
  iconColor: string;
  size: "sm" | "lg";
}

function ModernFileIcon({
  Icon,
  bgColor,
  iconColor,
  size,
}: ModernFileIconProps) {
  const containerSize = size === "sm" ? "h-6 w-6" : "h-14 w-14";
  const iconSize = size === "sm" ? "h-3 w-3" : "h-7 w-7";
  const borderRadius = size === "sm" ? "rounded-md" : "rounded-xl";

  return (
    <div
      className={`${containerSize} ${borderRadius} flex items-center justify-center backdrop-blur-sm`}
      style={{
        background: `linear-gradient(135deg, ${bgColor}20, ${bgColor}40)`,
        boxShadow: `0 4px 16px ${bgColor}25, inset 0 1px 0 rgba(255,255,255,0.2)`,
        border: `1px solid ${bgColor}30`,
      }}
    >
      <Icon
        className={iconSize}
        style={{ color: iconColor }}
        strokeWidth={1.5}
      />
    </div>
  );
}

// Modern PDF icon with document styling
function ModernPDFIcon({ size }: { size: "sm" | "lg" }) {
  const containerSize = size === "sm" ? "h-6 w-6" : "h-14 w-14";

  return (
    <div className={`${containerSize} relative`}>
      <svg viewBox="0 0 56 56" className="w-full h-full" fill="none">
        <defs>
          <linearGradient id="pdf-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#F87171" />
            <stop offset="100%" stopColor="#DC2626" />
          </linearGradient>
          <filter id="pdf-shadow" x="-20%" y="-10%" width="140%" height="150%">
            <feDropShadow
              dx="0"
              dy="3"
              stdDeviation="3"
              floodColor="#DC2626"
              floodOpacity="0.2"
            />
          </filter>
        </defs>
        {/* Document body */}
        <path
          d="M14 6C14 4.89543 14.8954 4 16 4H32L44 16V50C44 51.1046 43.1046 52 42 52H16C14.8954 52 14 51.1046 14 50V6Z"
          fill="url(#pdf-grad)"
          filter="url(#pdf-shadow)"
        />
        {/* Folded corner */}
        <path
          d="M32 4V14C32 15.1046 32.8954 16 34 16H44L32 4Z"
          fill="#FCA5A5"
        />
        {/* Glass shine */}
        <path
          d="M14 6C14 4.89543 14.8954 4 16 4H32L14 22V6Z"
          fill="white"
          opacity="0.15"
        />
        {/* PDF text */}
        <text
          x="28"
          y="38"
          textAnchor="middle"
          fill="white"
          fontSize="10"
          fontWeight="bold"
          fontFamily="system-ui"
        >
          PDF
        </text>
      </svg>
    </div>
  );
}

export function getFileIcon(file: FileItem, size: "sm" | "lg" = "lg") {
  const mimeType = file.mime_type || "";

  if (file.is_folder) {
    const sizeClass = size === "sm" ? "h-6 w-6" : "h-14 w-14";
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
    return <ModernFolder className={sizeClass} />;
  }

  // File type icons with modern glassmorphism style
  if (mimeType.includes("pdf")) {
    return <ModernPDFIcon size={size} />;
  }
  if (mimeType.includes("image")) {
    return (
      <ModernFileIcon
        Icon={Image}
        bgColor="#EC4899"
        iconColor="#DB2777"
        size={size}
      />
    );
  }
  if (mimeType.includes("spreadsheet") || mimeType.includes("excel")) {
    return (
      <ModernFileIcon
        Icon={FileSpreadsheet}
        bgColor="#10B981"
        iconColor="#059669"
        size={size}
      />
    );
  }
  if (mimeType.includes("presentation")) {
    return (
      <ModernFileIcon
        Icon={Presentation}
        bgColor="#F59E0B"
        iconColor="#D97706"
        size={size}
      />
    );
  }
  if (mimeType.includes("document") || mimeType.includes("word")) {
    return (
      <ModernFileIcon
        Icon={FileText}
        bgColor="#3B82F6"
        iconColor="#2563EB"
        size={size}
      />
    );
  }
  if (
    mimeType.includes("code") ||
    mimeType.includes("javascript") ||
    mimeType.includes("json")
  ) {
    return (
      <ModernFileIcon
        Icon={FileCode}
        bgColor="#8B5CF6"
        iconColor="#7C3AED"
        size={size}
      />
    );
  }
  if (mimeType.includes("text")) {
    return (
      <ModernFileIcon
        Icon={FileText}
        bgColor="#6B7280"
        iconColor="#4B5563"
        size={size}
      />
    );
  }
  return (
    <ModernFileIcon
      Icon={File}
      bgColor="#9CA3AF"
      iconColor="#6B7280"
      size={size}
    />
  );
}
