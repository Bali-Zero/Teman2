/**
 * Visa Status Card Component
 * Displays active visa information with expiry countdown
 *
 * Features:
 * - Active visa details (type, number, expiry)
 * - Expiry countdown with color-coded urgency
 * - Sponsor information
 * - Renewal CTA button
 * - Status indicator
 */

"use client";

import React from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Passport,
  Calendar,
  Building,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { formatDate, getDaysUntil } from "@/lib/formatters";

interface VisaRecord {
  id: number;
  visa_type: string;
  visa_number: string | null;
  issue_date: string;
  expiry_date: string;
  status: string;
  sponsor_name: string | null;
}

interface VisaStatusCardProps {
  clientId: number;
  apiUrl?: string;
  onRenew?: () => void;
}

const fetcher = (url: string) =>
  fetch(url, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem("portal_jwt")}`,
    },
  }).then((res) => {
    if (!res.ok) throw new Error("Failed to fetch visa status");
    return res.json();
  });

function getStatusColor(status: string): string {
  switch (status) {
    case "active":
      return "success";
    case "expiring_soon":
      return "warning";
    case "expired":
      return "error";
    default:
      return "secondary";
  }
}

function getExpiryUrgency(daysUntil: number): "safe" | "warning" | "critical" {
  if (daysUntil < 0) return "critical";
  if (daysUntil < 30) return "critical";
  if (daysUntil < 90) return "warning";
  return "safe";
}

export function VisaStatusCard({
  clientId,
  apiUrl = process.env.NEXT_PUBLIC_API_URL,
  onRenew,
}: VisaStatusCardProps) {
  const { data, error, isLoading } = useSWR<VisaRecord>(
    `${apiUrl}/api/portal/visa`,
    fetcher,
    {
      refreshInterval: 300000,
    },
  );

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Visa Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-3">
            <div className="h-6 bg-gray-200 rounded w-2/3"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Visa Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6">
            <Passport className="w-12 h-12 mx-auto text-gray-300 mb-2" />
            <p className="text-sm text-[var(--foreground-muted)]">
              No active visa found
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const daysUntilExpiry = getDaysUntil(data.expiry_date);
  const urgency = getExpiryUrgency(daysUntilExpiry);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Passport className="w-5 h-5" />
            Visa Status
          </CardTitle>
          <Badge variant={getStatusColor(data.status)}>
            {data.status.replace("_", " ").toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Visa Type & Number */}
        <div>
          <p className="text-xl font-bold text-[var(--foreground)]">
            {data.visa_type.replace("_", " ").toUpperCase()}
          </p>
          {data.visa_number && (
            <p className="text-sm text-[var(--foreground-muted)]">
              Visa No. {data.visa_number}
            </p>
          )}
        </div>

        {/* Expiry Countdown */}
        <div
          className={`p-4 rounded-lg border-2 ${
            urgency === "critical"
              ? "bg-red-50 border-red-200"
              : urgency === "warning"
                ? "bg-yellow-50 border-yellow-200"
                : "bg-green-50 border-green-200"
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <Calendar
              className={`w-4 h-4 ${
                urgency === "critical"
                  ? "text-red-600"
                  : urgency === "warning"
                    ? "text-yellow-600"
                    : "text-green-600"
              }`}
            />
            <p
              className={`text-sm font-medium ${
                urgency === "critical"
                  ? "text-red-800"
                  : urgency === "warning"
                    ? "text-yellow-800"
                    : "text-green-800"
              }`}
            >
              {daysUntilExpiry < 0
                ? "EXPIRED"
                : `Expires in ${daysUntilExpiry} days`}
            </p>
          </div>
          <p
            className={`text-xs ${
              urgency === "critical"
                ? "text-red-600"
                : urgency === "warning"
                  ? "text-yellow-600"
                  : "text-green-600"
            }`}
          >
            Expiry Date: {formatDate(data.expiry_date)}
          </p>
        </div>

        {/* Details */}
        <div className="space-y-2 text-sm">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-green-600 mt-0.5" />
            <div>
              <p className="font-medium text-[var(--foreground)]">Issue Date</p>
              <p className="text-[var(--foreground-muted)]">
                {formatDate(data.issue_date)}
              </p>
            </div>
          </div>

          {data.sponsor_name && (
            <div className="flex items-start gap-2">
              <Building className="w-4 h-4 text-blue-600 mt-0.5" />
              <div>
                <p className="font-medium text-[var(--foreground)]">Sponsor</p>
                <p className="text-[var(--foreground-muted)]">
                  {data.sponsor_name}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Renewal CTA */}
        {urgency !== "safe" && (
          <Button
            className="w-full"
            variant={urgency === "critical" ? "default" : "outline"}
            onClick={onRenew}
          >
            {urgency === "critical" ? "Renew Now" : "Start Renewal Process"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
