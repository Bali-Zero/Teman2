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
      alertLevel: "expired",
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 9) {
    return {
      color: "red",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      alertLevel: "critical",
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 14) {
    return {
      color: "yellow",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      alertLevel: "warning",
      monthsUntil: monthsUntilExpiry,
    };
  } else {
    return {
      color: "green",
      label: `${Math.floor(monthsUntilExpiry)} months`,
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
        <Loader2
          className="w-8 h-8 animate-spin"
          style={{ color: "var(--bz-accent-warm)" }}
        />
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
        <p style={{ color: "var(--bz-text-2)" }}>
          View your personal information
        </p>
      </section>

      {/* Profile Card */}
      <section
        className="rounded-xl border p-6 space-y-6"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        {/* Avatar */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div
              className={cn(
                "w-20 h-20 rounded-full flex items-center justify-center transition-all duration-500",
                isBirthday &&
                  "bg-gradient-to-br from-yellow-300 via-amber-300 to-yellow-400 animate-pulse shadow-[0_0_30px_rgba(255,215,0,0.6)]",
              )}
              style={
                !isBirthday ? { background: "rgba(201,169,110,0.15)" } : {}
              }
            >
              <User
                className={cn(
                  "w-10 h-10 transition-colors",
                  isBirthday ? "text-yellow-700" : "",
                )}
                style={!isBirthday ? { color: "var(--bz-accent-warm)" } : {}}
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
                  "absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2",
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
            <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
              Member since{" "}
              {new Date(profile.memberSince).toLocaleDateString("en-US", {
                month: "long",
                year: "numeric",
              })}
            </p>
            {isBirthday && (
              <p
                className="text-sm font-medium mt-1 animate-pulse"
                style={{ color: "#fbbf24" }}
              >
                🎉 Happy Birthday! 🎉
              </p>
            )}
          </div>
        </div>

        {/* Info Fields */}
        <div
          className="space-y-4 pt-4 border-t"
          style={{ borderColor: "var(--bz-border)" }}
        >
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
              className="flex items-start gap-3 p-3 rounded-lg transition-all duration-500"
              style={
                isBirthday
                  ? {
                      background: "rgba(251,191,36,0.15)",
                      boxShadow: "0 0 20px rgba(255,215,0,0.3)",
                    }
                  : {}
              }
            >
              <div
                className="p-2 rounded-md"
                style={
                  isBirthday
                    ? { background: "rgba(251,191,36,0.25)" }
                    : { background: "var(--bz-surface)" }
                }
              >
                <Calendar
                  className={cn("w-4 h-4", isBirthday && "text-yellow-400")}
                  style={!isBirthday ? { color: "var(--bz-text-2)" } : {}}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className="text-xs mb-0.5"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Date of Birth
                </p>
                <p
                  className={cn(
                    "text-sm font-medium break-words",
                    isBirthday && "font-bold",
                  )}
                  style={isBirthday ? { color: "#fbbf24" } : {}}
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
                passportValidity.alertLevel === "critical" && "animate-pulse",
              )}
              style={{
                background:
                  passportValidity.alertLevel === "ok"
                    ? "rgba(16,185,129,0.06)"
                    : passportValidity.alertLevel === "warning"
                      ? "rgba(245,158,11,0.06)"
                      : "rgba(239,68,68,0.08)",
                borderColor:
                  passportValidity.alertLevel === "ok"
                    ? "rgba(16,185,129,0.25)"
                    : passportValidity.alertLevel === "warning"
                      ? "rgba(245,158,11,0.3)"
                      : "rgba(239,68,68,0.35)",
              }}
            >
              <div
                className="p-2 rounded-md"
                style={{
                  background:
                    passportValidity.alertLevel === "ok"
                      ? "rgba(16,185,129,0.12)"
                      : passportValidity.alertLevel === "warning"
                        ? "rgba(245,158,11,0.12)"
                        : "rgba(239,68,68,0.15)",
                }}
              >
                {passportValidity.alertLevel === "ok" ? (
                  <Calendar className="w-4 h-4" style={{ color: "#34d399" }} />
                ) : (
                  <AlertTriangle
                    className="w-4 h-4"
                    style={{
                      color:
                        passportValidity.alertLevel === "warning"
                          ? "#fbbf24"
                          : "#f87171",
                    }}
                  />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className="text-xs mb-0.5"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Passport Expiry
                </p>
                <p
                  className="text-sm font-medium break-words"
                  style={{
                    color:
                      passportValidity.alertLevel === "ok"
                        ? "#34d399"
                        : passportValidity.alertLevel === "warning"
                          ? "#fbbf24"
                          : "#f87171",
                  }}
                >
                  {formatDate(profile.passportExpiry)}
                  <span className="ml-2 text-xs">
                    ({passportValidity.label})
                  </span>
                </p>
                {/* Alert Messages */}
                {passportValidity.alertLevel === "warning" && (
                  <p className="mt-1 text-xs text-yellow-400">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    Your passport expires in less than 14 months. Contact your
                    embassy to begin renewal process.
                  </p>
                )}
                {passportValidity.alertLevel === "critical" && (
                  <p className="mt-1 text-xs text-red-400 font-medium">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    URGENT: Your passport expires in less than 9 months. You may
                    not be able to travel internationally. Contact your embassy
                    immediately!
                  </p>
                )}
                {passportValidity.alertLevel === "expired" && (
                  <p className="mt-1 text-xs text-red-400 font-bold">
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
      <section
        className="rounded-lg border p-4"
        style={{
          borderColor: "rgba(201,169,110,0.3)",
          background: "rgba(201,169,110,0.06)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--bz-accent-warm)" }}>
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
      <div
        className="p-2 rounded-md"
        style={{ background: "var(--bz-surface)" }}
      >
        <Icon className="w-4 h-4" style={{ color: "var(--bz-text-2)" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs mb-0.5" style={{ color: "var(--bz-text-2)" }}>
          {label}
        </p>
        <p className="text-sm font-medium break-words">{value}</p>
      </div>
    </div>
  );
}
