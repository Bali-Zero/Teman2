"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  Globe,
  AlertTriangle,
  AlertCircle,
  CreditCard,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type { PortalProfile } from "@/lib/api/portal/portal.types";

// ============================================================================
// ALERT UTILITIES (same as workspace)
// ============================================================================

type PassportAlertLevel = "ok" | "warning" | "critical" | "expired";

interface PassportValidityInfo {
  color: string;
  label: string;
  bgClass: string;
  textClass: string;
  alertLevel: PassportAlertLevel;
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

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function ProfilePage() {
  const { error } = useToast();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getProfile();
      setProfile(data);
    } catch (err) {
      error("Failed to load profile", "Please try again later");
      logger.error("Failed to load portal profile", {}, err as Error);
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

  // Calculate alerts
  const passportValidity = getPassportValidityColor(profile.passportExpiry);
  const isBirthday = isBirthdayToday(profile.dateOfBirth);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Your Profile</h1>
        <p className="text-muted-foreground">View your personal information</p>
      </section>

      {/* Profile Card */}
      <section className="rounded-xl border bg-card p-6 space-y-6">
        {/* Avatar */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div
              className={cn(
                "w-20 h-20 rounded-full flex items-center justify-center transition-all duration-500",
                isBirthday
                  ? "bg-gradient-to-br from-yellow-300 via-amber-300 to-yellow-400 animate-pulse shadow-[0_0_30px_rgba(255,215,0,0.6)]"
                  : "bg-primary/10",
              )}
            >
              <User
                className={cn(
                  "w-10 h-10 transition-colors",
                  isBirthday ? "text-yellow-700" : "text-primary",
                )}
              />
            </div>
            {/* Birthday Badge */}
            {isBirthday && (
              <div className="absolute -top-1 -right-1 w-8 h-8 bg-red-500 rounded-full flex items-center justify-center text-white text-lg animate-bounce">
                🎂
              </div>
            )}
            {/* Gender Badge */}
            {profile.gender && (
              <div
                className={cn(
                  "absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 border-white dark:border-card",
                  profile.gender === "M"
                    ? "bg-blue-500 text-white"
                    : "bg-pink-500 text-white",
                )}
              >
                {profile.gender}
              </div>
            )}
          </div>
          <div className="text-center">
            <h2 className="text-xl font-bold">{profile.fullName}</h2>
            <p className="text-sm text-muted-foreground">
              Member since{" "}
              {new Date(profile.memberSince).toLocaleDateString("en-US", {
                month: "long",
                year: "numeric",
              })}
            </p>
            {isBirthday && (
              <p className="text-sm font-medium text-yellow-600 dark:text-yellow-400 mt-1 animate-pulse">
                🎉 Happy Birthday! 🎉
              </p>
            )}
          </div>
        </div>

        {/* Info Fields */}
        <div className="space-y-4 pt-4 border-t">
          <ProfileField icon={Mail} label="Email" value={profile.email} />

          {profile.phone && (
            <ProfileField icon={Phone} label="Phone" value={profile.phone} />
          )}

          {profile.whatsapp && (
            <ProfileField
              icon={Phone}
              label="WhatsApp"
              value={profile.whatsapp}
            />
          )}

          {profile.nationality && (
            <ProfileField
              icon={Globe}
              label="Nationality"
              value={profile.nationality}
            />
          )}

          {/* Date of Birth with Birthday Glow */}
          {profile.dateOfBirth && (
            <div
              className={cn(
                "flex items-start gap-3 p-3 rounded-lg transition-all duration-500",
                isBirthday
                  ? "bg-gradient-to-r from-yellow-100 via-amber-100 to-yellow-100 dark:from-yellow-900/30 dark:via-amber-900/30 dark:to-yellow-900/30 shadow-[0_0_20px_rgba(255,215,0,0.3)]"
                  : "",
              )}
            >
              <div
                className={cn(
                  "p-2 rounded-md",
                  isBirthday
                    ? "bg-yellow-200 dark:bg-yellow-800"
                    : "bg-neutral-100 dark:bg-neutral-800",
                )}
              >
                <Calendar
                  className={cn(
                    "w-4 h-4",
                    isBirthday
                      ? "text-yellow-700 dark:text-yellow-300"
                      : "text-neutral-600 dark:text-neutral-400",
                  )}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted-foreground mb-0.5">
                  Date of Birth
                </p>
                <p
                  className={cn(
                    "text-sm font-medium break-words",
                    isBirthday &&
                      "text-yellow-700 dark:text-yellow-400 font-bold",
                  )}
                >
                  {formatDate(profile.dateOfBirth)}
                  {isBirthday && " 🎂 (Today!)"}
                </p>
              </div>
            </div>
          )}

          {/* Passport Number */}
          {profile.passportNumber && (
            <ProfileField
              icon={CreditCard}
              label="Passport Number"
              value={profile.passportNumber}
            />
          )}

          {/* Passport Expiry with Alert */}
          {profile.passportExpiry && (
            <div
              className={cn(
                "flex items-start gap-3 p-3 rounded-lg border",
                passportValidity.bgClass,
                passportValidity.alertLevel === "critical" &&
                  "border-red-300 dark:border-red-700 animate-pulse",
                passportValidity.alertLevel === "warning" &&
                  "border-yellow-300 dark:border-yellow-700",
                passportValidity.alertLevel === "ok" &&
                  "border-green-200 dark:border-green-800",
              )}
            >
              <div
                className={cn(
                  "p-2 rounded-md",
                  passportValidity.alertLevel === "critical" &&
                    "bg-red-200 dark:bg-red-800",
                  passportValidity.alertLevel === "warning" &&
                    "bg-yellow-200 dark:bg-yellow-800",
                  passportValidity.alertLevel === "ok" &&
                    "bg-green-200 dark:bg-green-800",
                  passportValidity.alertLevel === "expired" &&
                    "bg-red-300 dark:bg-red-700",
                )}
              >
                {passportValidity.alertLevel === "ok" ? (
                  <Calendar className="w-4 h-4 text-green-700 dark:text-green-300" />
                ) : (
                  <AlertTriangle
                    className={cn("w-4 h-4", passportValidity.textClass)}
                  />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted-foreground mb-0.5">
                  Passport Expiry
                </p>
                <p
                  className={cn(
                    "text-sm font-medium break-words",
                    passportValidity.textClass,
                  )}
                >
                  {formatDate(profile.passportExpiry)}
                  <span className="ml-2 text-xs">
                    ({passportValidity.label})
                  </span>
                </p>
                {/* Alert Messages */}
                {passportValidity.alertLevel === "warning" && (
                  <p className="mt-1 text-xs text-yellow-700 dark:text-yellow-400">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    Your passport expires in less than 14 months. Contact your
                    embassy to begin renewal process.
                  </p>
                )}
                {passportValidity.alertLevel === "critical" && (
                  <p className="mt-1 text-xs text-red-700 dark:text-red-400 font-medium">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    URGENT: Your passport expires in less than 9 months. You may
                    not be able to travel internationally. Contact your embassy
                    immediately!
                  </p>
                )}
                {passportValidity.alertLevel === "expired" && (
                  <p className="mt-1 text-xs text-red-700 dark:text-red-400 font-bold">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    Your passport has EXPIRED! Contact your embassy immediately
                    for emergency renewal.
                  </p>
                )}
              </div>
            </div>
          )}

          {profile.address && (
            <ProfileField
              icon={MapPin}
              label="Address"
              value={profile.address}
            />
          )}
        </div>
      </section>

      {/* Info Notice */}
      <section className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
        <p className="text-sm text-amber-800 dark:text-amber-400">
          To update your profile information, please contact your account
          manager or send us a message through the Chat.
        </p>
      </section>
    </div>
  );
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

function ProfileField({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="p-2 rounded-md bg-neutral-100 dark:bg-neutral-800">
        <Icon className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
        <p className="text-sm font-medium break-words">{value}</p>
      </div>
    </div>
  );
}
