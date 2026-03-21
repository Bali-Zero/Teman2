/**
 * Tax Summary Card Component
 * Displays aggregated tax obligation metrics for a client
 *
 * Features:
 * - Total obligations count
 * - Total amount due
 * - Upcoming/Critical/Overdue counts
 * - Color-coded urgency indicators
 * - Auto-refresh every 5 minutes
 */

"use client";

import React from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, FileText, DollarSign } from "lucide-react";
import { formatCurrency } from "@/lib/formatters";

interface TaxSummary {
  total_obligations: number;
  total_amount: number;
  upcoming_count: number;
  critical_count: number;
  overdue_count: number;
}

interface TaxSummaryCardProps {
  clientId: number;
  apiUrl?: string;
}

const fetcher = (url: string) =>
  fetch(url, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem("portal_jwt")}`,
    },
  }).then((res) => {
    if (!res.ok) throw new Error("Failed to fetch tax summary");
    return res.json();
  });

export function TaxSummaryCard({
  clientId,
  apiUrl = process.env.NEXT_PUBLIC_API_URL,
}: TaxSummaryCardProps) {
  const { data, error, isLoading } = useSWR<TaxSummary>(
    `${apiUrl}/api/portal/taxes/summary`,
    fetcher,
    { refreshInterval: 300000 }, // 5 minutes
  );

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tax Obligations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-3">
            <div className="h-8 bg-gray-200 rounded w-1/2"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tax Obligations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-red-600">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">Failed to load tax summary</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Tax Obligations
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Total Amount */}
        <div>
          <p className="text-2xl font-bold text-[var(--foreground)]">
            {formatCurrency(data.total_amount, "IDR")}
          </p>
          <p className="text-sm text-[var(--foreground-muted)]">
            {data.total_obligations} obligation
            {data.total_obligations !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Status Breakdown */}
        <div className="flex flex-wrap gap-2">
          {data.upcoming_count > 0 && (
            <Badge variant="success" className="flex items-center gap-1">
              {data.upcoming_count} Upcoming
            </Badge>
          )}
          {data.critical_count > 0 && (
            <Badge variant="warning" className="flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {data.critical_count} Critical
            </Badge>
          )}
          {data.overdue_count > 0 && (
            <Badge variant="error" className="flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {data.overdue_count} Overdue
            </Badge>
          )}
        </div>

        {/* Urgency Indicator */}
        {data.overdue_count > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-800 font-medium">
              Action Required: {data.overdue_count} overdue obligation
              {data.overdue_count !== 1 ? "s" : ""}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
