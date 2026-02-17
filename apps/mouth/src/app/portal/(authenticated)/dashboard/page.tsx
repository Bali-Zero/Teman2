"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  User,
  CreditCard,
  FileText,
  Upload,
  Calendar,
  AlertTriangle,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { PortalProfile } from "@/lib/api/portal/portal.types";
import type { VisaInfo } from "@/lib/api/portal/portal.types";

// Alert utilities (same as workspace)
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
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [profileData, visaData] = await Promise.all([
        api.portal.getProfile(),
        api.portal.getVisaStatus(),
      ]);
      setProfile(profileData);
      setVisaInfo(visaData);
    } catch (err) {
      error("Failed to load data", "Please try again later");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

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
        <p className="text-muted-foreground">
          Your personal information and documents
        </p>
      </section>

      {/* Main Grid - 3 columns on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Column 1: Team Member */}
        <TeamMemberCard />

        {/* Column 2: Passport */}
        <PassportCard
          profile={profile}
          passportValidity={passportValidity}
          isBirthday={isBirthday}
        />

        {/* Column 3: Visa */}
        <VisaCard visaInfo={visaInfo} />
      </div>

      {/* Contact Info Section */}
      <ContactInfoCard profile={profile} />
    </div>
  );
}

// ============================================================================
// TEAM MEMBER CARD (Left)
// ============================================================================
function TeamMemberCard() {
  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <User className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Team Member</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Team Member Info */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center">
            <User className="w-6 h-6 text-primary" />
          </div>
          <div>
            <p className="font-medium">Damar</p>
            <p className="text-xs text-muted-foreground">Case Manager</p>
          </div>
        </div>

        {/* Pastel Art Placeholder */}
        <div className="relative rounded-xl overflow-hidden flex-1 min-h-[200px] bg-gradient-to-br from-purple-900/40 via-pink-900/30 to-blue-900/40">
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-yellow-300/60 to-pink-400/60 flex items-center justify-center mb-2">
              <span className="text-2xl">🌴</span>
            </div>
            <p className="text-xs text-white/60">Pastel Bali Landscape</p>
            <p className="text-[10px] text-white/40 mt-1">400×320px • WEBP/AVIF</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// PASSPORT CARD (Center)
// ============================================================================
function PassportCard({
  profile,
  passportValidity,
  isBirthday,
}: {
  profile: PortalProfile;
  passportValidity: PassportValidityInfo;
  isBirthday: boolean;
}) {
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
        {/* Passport Image/Upload Area */}
        <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-border bg-muted/50 flex flex-col items-center justify-center">
          <CreditCard className="w-10 h-10 text-muted-foreground/50 mb-2" />
          <span className="text-sm text-muted-foreground">No passport</span>
        </div>

        {/* Upload Button */}
        <Button variant="outline" className="w-full gap-2">
          <Upload className="w-4 h-4" />
          Upload Passport
        </Button>

        {/* Passport Data with Alerts */}
        <div className="space-y-2 flex-1">
          {/* Passport Number */}
          {profile.passportNumber && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Number:</span>
              <span className="font-mono">{profile.passportNumber}</span>
            </div>
          )}

          {/* Expiry with Alert */}
          {profile.passportExpiry && (
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
                <span className="text-xs uppercase opacity-80">Expiry:</span>
                <span
                  className={cn(
                    "font-semibold",
                    passportValidity.textClass,
                  )}
                >
                  {formatDate(profile.passportExpiry)}
                </span>
              </div>
              {passportValidity.alertLevel === "warning" && (
                <p className="mt-1 text-xs text-yellow-700 dark:text-yellow-400">
                  <AlertCircle className="w-3 h-3 inline mr-1" />
                  Contact embassy to begin renewal
                </p>
              )}
              {passportValidity.alertLevel === "critical" && (
                <p className="mt-1 text-xs text-red-700 dark:text-red-400 font-bold">
                  <AlertTriangle className="w-3 h-3 inline mr-1" />
                  URGENT: Contact embassy immediately!
                </p>
              )}
            </div>
          )}

          {/* Date of Birth with Birthday Glow */}
          {profile.dateOfBirth && (
            <div
              className={cn(
                "flex items-center justify-between text-sm p-2 rounded-lg",
                isBirthday &&
                  "bg-gradient-to-r from-yellow-100 via-amber-100 to-yellow-100 dark:from-yellow-900/30 dark:via-amber-900/30 dark:to-yellow-900/30 animate-pulse",
              )}
            >
              <span className={cn(isBirthday && "font-semibold")}>
                {isBirthday ? "🎂 DOB:" : "DOB:"}
              </span>
              <span className={cn(isBirthday && "font-bold")}>
                {formatDate(profile.dateOfBirth)}
                {isBirthday && " (Today!)"}
              </span>
            </div>
          )}
        </div>

        {/* Caption */}
        <p className="text-xs text-muted-foreground text-center">
          Upload passport (JPG, PNG, PDF - max 10MB)
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// VISA CARD (Right)
// ============================================================================
function VisaCard({ visaInfo }: { visaInfo: VisaInfo | null }) {
  const currentVisa = visaInfo?.current;
  const daysRemaining = currentVisa?.daysRemaining;
  const isCritical = daysRemaining !== null && daysRemaining <= 60;

  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <FileText className="w-5 h-5 text-primary" />
        <h3 className="font-semibold">Actual Visa</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Visa Image/Upload Area */}
        <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-border bg-muted/50 flex flex-col items-center justify-center">
          <FileText className="w-10 h-10 text-muted-foreground/50 mb-2" />
          <span className="text-sm text-muted-foreground">No visa</span>
        </div>

        {/* Upload Button */}
        <Button variant="outline" className="w-full gap-2">
          <Upload className="w-4 h-4" />
          Upload Visa
        </Button>

        {/* Visa Data */}
        <div className="space-y-2 flex-1">
          {currentVisa ? (
            <>
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
                  <span
                    className={cn(
                      "text-xs uppercase",
                      isCritical && "font-bold",
                    )}
                  >
                    Exp Visa:
                  </span>
                  <span
                    className={cn(
                      "font-semibold",
                      isCritical && "text-red-700 dark:text-red-400",
                    )}
                  >
                    {formatDate(currentVisa.expiryDate)}
                  </span>
                </div>
                {isCritical && (
                  <p className="mt-1 text-xs text-red-700 dark:text-red-400 font-medium">
                    <AlertTriangle className="w-3 h-3 inline mr-1" />
                    URGENT: Plan renewal or communicate departure!
                  </p>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              No visa information available
            </p>
          )}
        </div>

        {/* Caption */}
        <p className="text-xs text-muted-foreground text-center">
          Upload visa (JPG, PNG, PDF - max 10MB)
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// CONTACT INFO CARD (Bottom)
// ============================================================================
function ContactInfoCard({ profile }: { profile: PortalProfile }) {
  return (
    <div className="rounded-xl border bg-card p-6">
      <h3 className="font-semibold mb-4">Contact Information</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <InfoRow label="Email" value={profile.email} />
          {profile.phone && <InfoRow label="Phone" value={profile.phone} />}
          {profile.whatsapp && (
            <InfoRow label="WhatsApp" value={profile.whatsapp} />
          )}
        </div>
        <div className="space-y-3">
          {profile.nationality && (
            <InfoRow label="Nationality" value={profile.nationality} />
          )}
          {profile.address && <InfoRow label="Address" value={profile.address} />}
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="p-2 rounded-md bg-muted">
        <User className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
        <p className="text-sm font-medium break-words">{value}</p>
      </div>
    </div>
  );
}
