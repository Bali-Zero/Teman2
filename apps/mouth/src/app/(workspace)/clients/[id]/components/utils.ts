"use client";

import React from "react";
import { MessageCircle, Mail, Phone, Calendar, FileText } from "lucide-react";

// Country codes with flags for phone input
export const COUNTRY_CODES = [
  { code: "+62", country: "Indonesia", flag: "\u{1F1EE}\u{1F1E9}" },
  { code: "+82", country: "South Korea", flag: "\u{1F1F0}\u{1F1F7}" },
  { code: "+39", country: "Italy", flag: "\u{1F1EE}\u{1F1F9}" },
  { code: "+1", country: "USA/Canada", flag: "\u{1F1FA}\u{1F1F8}" },
  { code: "+44", country: "UK", flag: "\u{1F1EC}\u{1F1E7}" },
  { code: "+61", country: "Australia", flag: "\u{1F1E6}\u{1F1FA}" },
  { code: "+49", country: "Germany", flag: "\u{1F1E9}\u{1F1EA}" },
  { code: "+33", country: "France", flag: "\u{1F1EB}\u{1F1F7}" },
  { code: "+31", country: "Netherlands", flag: "\u{1F1F3}\u{1F1F1}" },
  { code: "+34", country: "Spain", flag: "\u{1F1EA}\u{1F1F8}" },
  { code: "+7", country: "Russia", flag: "\u{1F1F7}\u{1F1FA}" },
  { code: "+380", country: "Ukraine", flag: "\u{1F1FA}\u{1F1E6}" },
  { code: "+81", country: "Japan", flag: "\u{1F1EF}\u{1F1F5}" },
  { code: "+86", country: "China", flag: "\u{1F1E8}\u{1F1F3}" },
  { code: "+91", country: "India", flag: "\u{1F1EE}\u{1F1F3}" },
  { code: "+55", country: "Brazil", flag: "\u{1F1E7}\u{1F1F7}" },
  { code: "+52", country: "Mexico", flag: "\u{1F1F2}\u{1F1FD}" },
  { code: "+54", country: "Argentina", flag: "\u{1F1E6}\u{1F1F7}" },
  { code: "+27", country: "South Africa", flag: "\u{1F1FF}\u{1F1E6}" },
  { code: "+64", country: "New Zealand", flag: "\u{1F1F3}\u{1F1FF}" },
  { code: "+353", country: "Ireland", flag: "\u{1F1EE}\u{1F1EA}" },
  { code: "+351", country: "Portugal", flag: "\u{1F1F5}\u{1F1F9}" },
  { code: "+48", country: "Poland", flag: "\u{1F1F5}\u{1F1F1}" },
  { code: "+90", country: "Turkey", flag: "\u{1F1F9}\u{1F1F7}" },
  { code: "+66", country: "Thailand", flag: "\u{1F1F9}\u{1F1ED}" },
  { code: "+84", country: "Vietnam", flag: "\u{1F1FB}\u{1F1F3}" },
  { code: "+63", country: "Philippines", flag: "\u{1F1F5}\u{1F1ED}" },
  { code: "+60", country: "Malaysia", flag: "\u{1F1F2}\u{1F1FE}" },
  { code: "+65", country: "Singapore", flag: "\u{1F1F8}\u{1F1EC}" },
];

// Extract country code from phone number
export const extractCountryCode = (
  phone: string,
): { countryCode: string; localNumber: string } => {
  if (!phone) return { countryCode: "+62", localNumber: "" };

  // If starts with +, try to match
  if (phone.startsWith("+")) {
    for (const { code } of COUNTRY_CODES.sort(
      (a, b) => b.code.length - a.code.length,
    )) {
      if (phone.startsWith(code)) {
        return {
          countryCode: code,
          localNumber: phone.slice(code.length).trim(),
        };
      }
    }
  }

  // Try to detect from raw digits
  const digits = phone.replace(/\D/g, "");
  for (const { code } of COUNTRY_CODES.sort(
    (a, b) => b.code.length - a.code.length,
  )) {
    const codeDigits = code.replace("+", "");
    if (
      digits.startsWith(codeDigits) &&
      digits.length >= codeDigits.length + 6
    ) {
      return {
        countryCode: code,
        localNumber: digits.slice(codeDigits.length),
      };
    }
  }

  return { countryCode: "+62", localNumber: phone };
};

// ============================================
// GOOGLE DRIVE URL HELPERS
// ============================================

// Extract file ID from Google Drive URL
export const extractDriveFileId = (url: string): string | null => {
  if (!url) return null;
  // Format: /file/d/{FILE_ID}/
  const match1 = url.match(/\/d\/([^/]+)/);
  if (match1) return match1[1];
  // Format: ?id={FILE_ID}
  const match2 = url.match(/[?&]id=([^&]+)/);
  if (match2) return match2[1];
  return null;
};

// Get proxy thumbnail URL for displaying document without Google branding
export const getDriveProxyUrl = (
  url: string,
  type: "thumbnail" | "full" = "thumbnail",
): string | null => {
  const fileId = extractDriveFileId(url);
  if (fileId) {
    return type === "thumbnail"
      ? `/api/documents/thumbnail/${fileId}`
      : `/api/documents/proxy/${fileId}`;
  }
  return null;
};

// Format phone number with country code detection
export const formatPhoneNumber = (phone: string): string => {
  if (!phone) return "";

  // Remove all non-digit characters except leading +
  const hasPlus = phone.startsWith("+");
  const digits = phone.replace(/\D/g, "");

  // If already has +, just return formatted
  if (hasPlus) {
    return phone;
  }

  // Country codes sorted by length (longest first to match correctly)
  const countryCodes: { code: string; length: number }[] = [
    { code: "380", length: 3 }, // Ukraine
    { code: "62", length: 2 }, // Indonesia
    { code: "82", length: 2 }, // South Korea
    { code: "81", length: 2 }, // Japan
    { code: "86", length: 2 }, // China
    { code: "91", length: 2 }, // India
    { code: "44", length: 2 }, // UK
    { code: "49", length: 2 }, // Germany
    { code: "33", length: 2 }, // France
    { code: "39", length: 2 }, // Italy
    { code: "34", length: 2 }, // Spain
    { code: "31", length: 2 }, // Netherlands
    { code: "61", length: 2 }, // Australia
    { code: "55", length: 2 }, // Brazil
    { code: "52", length: 2 }, // Mexico
    { code: "65", length: 2 }, // Singapore
    { code: "66", length: 2 }, // Thailand
    { code: "63", length: 2 }, // Philippines
    { code: "60", length: 2 }, // Malaysia
    { code: "84", length: 2 }, // Vietnam
    { code: "7", length: 1 }, // Russia
    { code: "1", length: 1 }, // USA/Canada
  ];

  // Try to match country code
  for (const { code, length } of countryCodes) {
    if (digits.startsWith(code) && digits.length >= length + 8) {
      const rest = digits.slice(length);
      return `+${code} ${rest}`;
    }
  }

  // If no country code detected, return as-is
  return phone;
};

// Format currency (IDR)
export const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
};

// Calculate passport validity color based on months until expiry
// Green: >14 months, Yellow: 9-13 months (13 month alert), Red: <9 months (9 month urgent alert)
export const getPassportValidityColor = (
  expiryDate: string | undefined,
): {
  color: string;
  label: string;
  bgClass: string;
  textClass: string;
  alertLevel: "ok" | "warning" | "critical" | "expired";
  monthsUntil: number;
} => {
  if (!expiryDate)
    return {
      color: "gray",
      label: "No expiry",
      bgClass: "bg-gray-500/20",
      textClass: "text-gray-400",
      alertLevel: "ok",
      monthsUntil: 999,
    };

  const now = new Date();
  const expiry = new Date(expiryDate);
  const monthsUntilExpiry =
    (expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24 * 30);

  if (monthsUntilExpiry <= 0) {
    return {
      color: "red",
      label: "EXPIRED",
      bgClass: "bg-red-600/30",
      textClass: "text-red-300",
      alertLevel: "expired",
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 9) {
    return {
      color: "red",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: "bg-red-500/20",
      textClass: "text-red-400",
      alertLevel: "critical",
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 14) {
    return {
      color: "yellow",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: "bg-yellow-500/20",
      textClass: "text-yellow-400",
      alertLevel: "warning",
      monthsUntil: monthsUntilExpiry,
    };
  } else {
    return {
      color: "green",
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: "bg-green-500/20",
      textClass: "text-green-400",
      alertLevel: "ok",
      monthsUntil: monthsUntilExpiry,
    };
  }
};

// Check if today is client's birthday
export const isBirthdayToday = (dateOfBirth: string | undefined): boolean => {
  if (!dateOfBirth) return false;
  const today = new Date();
  const dob = new Date(dateOfBirth);
  return (
    today.getDate() === dob.getDate() && today.getMonth() === dob.getMonth()
  );
};

// Calculate visa expiry alert (2 months = red alert)
export const getVisaAlertStatus = (
  expiryDate: string | undefined,
): {
  alertLevel: "ok" | "warning" | "critical";
  monthsUntil: number;
  bgClass: string;
  textClass: string;
} => {
  if (!expiryDate) {
    return {
      alertLevel: "ok",
      monthsUntil: 999,
      bgClass: "",
      textClass: "",
    };
  }

  const now = new Date();
  const expiry = new Date(expiryDate);
  const monthsUntilExpiry =
    (expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24 * 30);

  if (monthsUntilExpiry <= 0) {
    return {
      alertLevel: "critical",
      monthsUntil: monthsUntilExpiry,
      bgClass: "bg-red-600 text-white",
      textClass: "text-white",
    };
  } else if (monthsUntilExpiry <= 2) {
    return {
      alertLevel: "critical",
      monthsUntil: monthsUntilExpiry,
      bgClass: "bg-red-500 text-white",
      textClass: "text-white",
    };
  } else if (monthsUntilExpiry <= 4) {
    return {
      alertLevel: "warning",
      monthsUntil: monthsUntilExpiry,
      bgClass: "bg-yellow-500 text-black",
      textClass: "text-black",
    };
  }

  return {
    alertLevel: "ok",
    monthsUntil: monthsUntilExpiry,
    bgClass: "",
    textClass: "",
  };
};

export const INTERACTION_ICONS: Record<string, React.ReactNode> = {
  chat: React.createElement(MessageCircle, { className: "w-4 h-4" }),
  email: React.createElement(Mail, { className: "w-4 h-4" }),
  whatsapp: React.createElement(MessageCircle, {
    className: "w-4 h-4 text-green-500",
  }),
  call: React.createElement(Phone, { className: "w-4 h-4" }),
  meeting: React.createElement(Calendar, { className: "w-4 h-4" }),
  note: React.createElement(FileText, { className: "w-4 h-4" }),
};
