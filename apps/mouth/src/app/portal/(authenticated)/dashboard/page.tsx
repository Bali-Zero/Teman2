"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  User,
  CreditCard,
  FileText,
  Upload,
  AlertTriangle,
  AlertCircle,
  FolderOpen,
  Loader,
  CheckCircle,
  Plane,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { PortalProfile } from "@/lib/api/portal/portal.types";
import type { VisaInfo } from "@/lib/api/portal/portal.types";

// ============================================================================
// MOCK DATA FOR VISUAL TESTING
// ============================================================================
const MOCK_PROFILE: PortalProfile = {
  id: 123,
  fullName: "Marco Rossi",
  email: "marco.rossi@example.com",
  phone: "+39 333 123 4567",
  whatsapp: "+39 333 123 4567",
  nationality: "Italian",
  passportNumber: "YA123456",
  passportExpiry: "2026-08-15", // ~6 mesi (alert giallo)
  dateOfBirth: "1985-03-20",
  gender: "M",
  address: "Jl. Pantai Batu Bolong No. 88, Canggu, Bali",
  memberSince: "2024-01-15T00:00:00Z",
  assignedTo: {
    email: "damar@nuzantara.com",
    name: "Damar",
    avatarUrl: undefined, // Test senza avatar
  },
};

const MOCK_VISA_PROCESS: VisaInfo = {
  current: null,
  history: [],
  documents: [],
};

const MOCK_VISA_ELECTRONIC: VisaInfo = {
  current: null,
  history: [],
  documents: [
    { id: "evisa-1", name: "E-Visa Approval", type: "PDF", category: "electronic_visa", status: "verified", uploadDate: "2025-02-01", size: "245 KB" }
  ],
};

const MOCK_VISA_ACTUAL: VisaInfo = {
  current: {
    type: "KITAS (ITAS)",
    status: "active",
    issueDate: "2025-02-01",
    expiryDate: "2026-02-01", // ~11 mesi (ok)
    daysRemaining: 349,
    permitNumber: "A1234567",
    sponsor: "PT Nuzantara Solutions",
  },
  history: [
    { id: "h1", type: "B211A (Visitor Visa)", period: "2024-08 - 2025-02", status: "completed" },
  ],
  documents: [
    { id: "v1", name: "KITAS Card", type: "JPEG", category: "visa", status: "verified", uploadDate: "2025-02-05", size: "1.2 MB" },
    { id: "v2", name: "IMK (Re-entry Permit)", type: "JPEG", category: "visa", status: "verified", uploadDate: "2025-02-05", size: "890 KB" },
  ],
};

const MOCK_VISA_CRITICAL: VisaInfo = {
  current: {
    type: "KITAS (ITAS)",
    status: "active",
    issueDate: "2024-06-01",
    expiryDate: "2025-04-15", // ~2 mesi (alert critico!)
    daysRemaining: 58,
    permitNumber: "A7654321",
    sponsor: "PT Nuzantara Solutions",
  },
  history: [],
  documents: [],
};

// Cambia questo per testare stati diversi: "process" | "electronic" | "actual" | "actual_critical"
const MOCK_STATUS: "process" | "electronic" | "actual" | "actual_critical" = "actual";

interface PassportValidityInfo {
  color: string;
  label: string;
  bgClass: string;
  textClass: string;
  alertLevel: "ok" | "warning" | "critical" | "expired";
  monthsUntil: number;
}

const getPassportValidityColor = (
  expiryDate: string | undefined,
): PassportValidityInfo => {
  if (!expiryDate) {
    return {
      color: "gray",
      label: "No expiry",
      bgClass: "bg-gray-100 dark:bg-gray-800",
      textClass: "text-gray-600 dark:text-gray-400",
      alertLevel: "ok",
      monthsUntil: 999,
    };
  }

  const now = new Date();
  const expiry = new Date(expiryDate);
  const monthsUntilExpiry =
    (expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24 * 30);

  if (monthsUntilExpiry <= 0) {
    return {
      color: "red",
      label: "EXPIRED",
      bgClass: "bg-red-100 dark:bg-red-900/30",
      textClass: "text-red-700 dark:text-red-400",
      alertLevel: "expired",
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 9) {
    return {
      color: "red",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: "bg-red-50 dark:bg-red-900/20",
      textClass: "text-red-600 dark:text-red-400",
      alertLevel: "critical",
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 14) {
    return {
      color: "yellow",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: "bg-yellow-50 dark:bg-yellow-900/20",
      textClass: "text-yellow-700 dark:text-yellow-400",
      alertLevel: "warning",
      monthsUntil: monthsUntilExpiry,
    };
  } else {
    return {
      color: "green",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: "bg-green-50 dark:bg-green-900/20",
      textClass: "text-green-600 dark:text-green-400",
      alertLevel: "ok",
      monthsUntil: monthsUntilExpiry,
    };
  }
};

const isBirthdayToday = (dateOfBirth: string | undefined): boolean => {
  if (!dateOfBirth) return false;
  const today = new Date();
  const dob = new Date(dateOfBirth);
  return (
    today.getDate() === dob.getDate() && today.getMonth() === dob.getMonth()
  );
};

const formatDate = (dateStr: string | undefined): string => {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
};

export default function PortalDashboardPage() {
  const { error } = useToast();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [visaInfo, setVisaInfo] = useState<VisaInfo | null>(null);
  const [processStatus, setProcessStatus] = useState<"process" | "electronic" | "actual">("process");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // SIMULAZIONE: Carica mock data invece di chiamare API
    const timer = setTimeout(() => {
      setProfile(MOCK_PROFILE);
      
      // Determina quale mock visa usare
      if (MOCK_STATUS === "process") {
        setVisaInfo(MOCK_VISA_PROCESS);
        setProcessStatus("process");
      } else if (MOCK_STATUS === "electronic") {
        setVisaInfo(MOCK_VISA_ELECTRONIC);
        setProcessStatus("electronic");
      } else if (MOCK_STATUS === "actual_critical") {
        setVisaInfo(MOCK_VISA_CRITICAL);
        setProcessStatus("actual");
      } else {
        setVisaInfo(MOCK_VISA_ACTUAL);
        setProcessStatus("actual");
      }
      
      setIsLoading(false);
    }, 500);

    return () => clearTimeout(timer);
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!profile) return null;

  const passportValidity = getPassportValidityColor(profile.passportExpiry);
  const isBirthday = isBirthdayToday(profile.dateOfBirth);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">My Overview</h1>
        <p className="text-muted-foreground">Your personal information and documents</p>
      </section>

      {/* Main Grid - 3 columns on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Column 1: Team Member + Client Data */}
        <TeamMemberCard profile={profile} isBirthday={isBirthday} />

        {/* Column 2: Passport (with OCR data) */}
        <PassportCard
          profile={profile}
          passportValidity={passportValidity}
        />

        {/* Column 3: Process → Electronic Visa → Actual Visa */}
        <VisaProcessCard 
          status={processStatus} 
          visaInfo={visaInfo}
        />
      </div>
    </div>
  );
}

// ============================================================================
// TEAM MEMBER CARD (Left) - Small avatar + Client Data
// ============================================================================
function TeamMemberCard({ 
  profile, 
  isBirthday 
}: { 
  profile: PortalProfile;
  isBirthday: boolean;
}) {
  const assignedTo = profile.assignedTo;
  
  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <User className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Team Member</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Team Member - Small Avatar */}
        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
          {assignedTo?.avatarUrl ? (
            <img 
              src={assignedTo.avatarUrl} 
              alt={assignedTo.name}
              className="w-10 h-10 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-primary" />
            </div>
          )}
          <div className="min-w-0">
            <p className="font-medium text-sm truncate">{assignedTo?.name || "Not assigned"}</p>
            <p className="text-xs text-muted-foreground">Case Manager</p>
          </div>
        </div>

        {/* Client Data Section */}
        <div className="space-y-3 flex-1">
          <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
            Your Information
          </h4>
          
          {/* Client Name */}
          <div className="flex items-start gap-2">
            <User className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Full Name</p>
              <p className="text-sm font-medium truncate">{profile.fullName}</p>
            </div>
          </div>

          {/* Email */}
          <div className="flex items-start gap-2">
            <div className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0 text-xs">@</div>
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Email</p>
              <p className="text-sm truncate">{profile.email}</p>
            </div>
          </div>

          {/* Phone */}
          {profile.phone && (
            <div className="flex items-start gap-2">
              <div className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0 text-xs">📞</div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Phone</p>
                <p className="text-sm">{profile.phone}</p>
              </div>
            </div>
          )}

          {/* Nationality */}
          {profile.nationality && (
            <div className="flex items-start gap-2">
              <div className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0 text-xs">🌍</div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Nationality</p>
                <p className="text-sm">{profile.nationality}</p>
              </div>
            </div>
          )}

          {/* Date of Birth with Birthday Highlight */}
          {profile.dateOfBirth && (
            <div 
              className={cn(
                "flex items-start gap-2 p-2 rounded-lg",
                isBirthday && "bg-gradient-to-r from-yellow-100 via-amber-100 to-yellow-100 dark:from-yellow-900/30 dark:via-amber-900/30 dark:to-yellow-900/30 animate-pulse"
              )}
            >
              <div className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0 text-xs">
                {isBirthday ? "🎂" : "📅"}
              </div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Date of Birth</p>
                <p className={cn("text-sm font-medium", isBirthday && "text-amber-700 dark:text-amber-400")}>
                  {formatDate(profile.dateOfBirth)}
                  {isBirthday && " (Today!)"}
                </p>
              </div>
            </div>
          )}

          {/* Address */}
          {profile.address && (
            <div className="flex items-start gap-2">
              <div className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0 text-xs">📍</div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Address</p>
                <p className="text-sm">{profile.address}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// PASSPORT CARD (Center) - Upload + OCR Data
// ============================================================================
function PassportCard({
  profile,
  passportValidity,
}: {
  profile: PortalProfile;
  passportValidity: PassportValidityInfo;
}) {
  const hasPassport = !!profile.passportNumber;

  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <CreditCard className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Passport</h3>
        {profile.gender && (
          <span
            className={cn(
              "ml-auto px-2 py-0.5 rounded-full text-xs font-bold",
              profile.gender === "M"
                ? "bg-blue-500/20 text-blue-400"
                : "bg-pink-500/20 text-pink-400",
            )}
          >
            {profile.gender}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Passport Image Preview */}
        {hasPassport ? (
          <div className="aspect-[3/2] rounded-lg border bg-muted/50 flex items-center justify-center overflow-hidden">
            {/* TODO: Show actual passport image from Google Drive */}
            <div className="text-center">
              <CreditCard className="w-12 h-12 text-muted-foreground/50 mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">Passport document</p>
            </div>
          </div>
        ) : (
          <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-border bg-muted/50 flex flex-col items-center justify-center">
            <CreditCard className="w-10 h-10 text-muted-foreground/50 mb-2" />
            <span className="text-sm text-muted-foreground">No passport uploaded</span>
          </div>
        )}

        {/* Upload Button (if no passport) */}
        {!hasPassport && (
          <Button variant="outline" className="w-full gap-2">
            <Upload className="w-4 h-4" />
            Upload Passport
          </Button>
        )}

        {/* OCR Data - Automatically extracted */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider flex items-center gap-1">
            <span>Extracted Data (OCR)</span>
          </h4>
          
          {/* Passport Number */}
          <div className="flex items-center justify-between p-2 bg-muted/50 rounded-lg">
            <span className="text-xs text-muted-foreground">Passport No.</span>
            <span className="font-mono text-sm font-medium">
              {profile.passportNumber || "—"}
            </span>
          </div>

          {/* Expiry with Alert */}
          {profile.passportExpiry ? (
            <div
              className={cn(
                "rounded-lg p-2 text-sm",
                passportValidity.bgClass,
                passportValidity.alertLevel === "critical" &&
                  "border border-red-300 animate-pulse",
                passportValidity.alertLevel === "warning" &&
                  "border border-yellow-300",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase opacity-80">Expiry Date</span>
                <span className={cn("font-semibold", passportValidity.textClass)}>
                  {formatDate(profile.passportExpiry)}
                </span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs opacity-70">Time remaining</span>
                <span className={cn("text-xs font-medium", passportValidity.textClass)}>
                  {passportValidity.label}
                </span>
              </div>
              {passportValidity.alertLevel === "warning" && (
                <p className="mt-2 text-xs text-yellow-700 dark:text-yellow-400 flex items-start gap-1">
                  <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>Your passport expires in less than 14 months. Contact your embassy to begin renewal process.</span>
                </p>
              )}
              {passportValidity.alertLevel === "critical" && (
                <p className="mt-2 text-xs text-red-700 dark:text-red-400 font-medium flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>URGENT: Your passport expires in less than 9 months. You may not be able to travel internationally. Contact your embassy immediately!</span>
                </p>
              )}
              {passportValidity.alertLevel === "expired" && (
                <p className="mt-2 text-xs text-red-700 dark:text-red-400 font-bold flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>Your passport has EXPIRED! Contact your embassy immediately for emergency renewal.</span>
                </p>
              )}
            </div>
          ) : (
            <div className="p-2 bg-muted/50 rounded-lg text-center">
              <span className="text-xs text-muted-foreground">No expiry date detected</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// VISA PROCESS CARD (Right) - Process → Electronic → Actual
// ============================================================================
function VisaProcessCard({ 
  status, 
  visaInfo 
}: { 
  status: "process" | "electronic" | "actual";
  visaInfo: VisaInfo | null;
}) {
  const currentVisa = visaInfo?.current;
  const daysRemaining = currentVisa?.daysRemaining;
  const isCritical = daysRemaining !== null && daysRemaining <= 60;

  // Render based on status
  if (status === "process") {
    return <ProcessCard />;
  }
  
  if (status === "electronic") {
    return <ElectronicVisaCard />;
  }

  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <FileText className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Actual Visa</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Visa Image */}
        <div className="aspect-[3/2] rounded-lg border bg-muted/50 flex items-center justify-center">
          {currentVisa ? (
            <div className="text-center">
              <Plane className="w-12 h-12 text-muted-foreground/50 mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">{currentVisa.type}</p>
            </div>
          ) : (
            <>
              <FileText className="w-10 h-10 text-muted-foreground/50 mb-2" />
              <span className="text-sm text-muted-foreground">No visa</span>
            </>
          )}
        </div>

        {/* Visa Data */}
        {currentVisa && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Type:</span>
              <span className="font-medium">{currentVisa.type}</span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Start:</span>
              <span>{formatDate(currentVisa.issueDate)}</span>
            </div>

            {/* Expiry with Alert */}
            <div
              className={cn(
                "rounded-lg p-2 text-sm",
                isCritical
                  ? "bg-red-100 dark:bg-red-900/30 border-2 border-red-300 animate-pulse"
                  : "bg-muted",
              )}
            >
              <div className="flex items-center justify-between">
                <span className={cn("text-xs uppercase", isCritical && "font-bold")}>
                  Exp Visa:
                </span>
                <span className={cn("font-semibold", isCritical && "text-red-700 dark:text-red-400")}>
                  {formatDate(currentVisa.expiryDate)}
                </span>
              </div>
              {isCritical && (
                <p className="mt-1 text-xs text-red-700 dark:text-red-400 font-medium flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>URGENT: Your visa expires in less than 2 months. Contact us immediately to plan renewal or communicate your departure!</span>
                </p>
              )}
            </div>

            {/* Days remaining indicator */}
            {daysRemaining !== null && (
              <div className={cn(
                "flex items-center justify-between p-2 rounded-lg text-sm",
                isCritical ? "bg-red-50 dark:bg-red-900/20" : "bg-green-50 dark:bg-green-900/20"
              )}>
                <span className="text-muted-foreground">Days remaining:</span>
                <span className={cn(
                  "font-semibold",
                  isCritical ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400"
                )}>
                  {daysRemaining} days
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Process Status Card (Initial state)
function ProcessCard() {
  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <FolderOpen className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Process</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col items-center justify-center space-y-4 min-h-[300px]">
        <div className="w-20 h-20 rounded-full bg-blue-500/10 flex items-center justify-center">
          <Loader className="w-10 h-10 text-blue-500 animate-spin" />
        </div>
        
        <div className="text-center">
          <p className="text-lg font-semibold text-blue-500">Visa on process</p>
          <p className="text-sm text-muted-foreground mt-1">
            Your application is being processed
          </p>
        </div>

        <div className="w-full space-y-2 pt-4">
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span>Documents received</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span>Application submitted</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Loader className="w-4 h-4 text-blue-500 animate-spin" />
            <span>Under review</span>
          </div>
        </div>

        <p className="text-xs text-muted-foreground text-center pt-4">
          You will be notified when your visa is ready
        </p>
      </div>
    </div>
  );
}

// Electronic Visa Card (Intermediate state)
function ElectronicVisaCard() {
  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <FileText className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Electronic Visa</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        <div className="aspect-[3/2] rounded-lg border bg-muted/50 flex items-center justify-center">
          <div className="text-center">
            <FileText className="w-12 h-12 text-green-500/70 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">E-Visa document</p>
          </div>
        </div>

        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <p className="text-sm text-green-700 dark:text-green-400 flex items-center gap-2">
            <CheckCircle className="w-4 h-4" />
            <span>Electronic visa approved</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Your physical visa card (KITAS/IMK) will be processed next
          </p>
        </div>

        <Button variant="outline" className="w-full gap-2">
          <Upload className="w-4 h-4" />
          Download E-Visa
        </Button>
      </div>
    </div>
  );
}
