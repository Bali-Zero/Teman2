export type ExpiryStatus = "expired" | "critical" | "warning" | "ok";

export interface ExpiryResult {
  status: ExpiryStatus;
  daysRemaining: number;
  label: string;
  color: string;
}

/**
 * Unified expiry status calculator.
 * Thresholds: expired (<=0), critical (<=30d), warning (<=90d), ok (>90d).
 */
export function getExpiryStatus(
  expiryDate: string | Date | null | undefined,
): ExpiryResult {
  if (!expiryDate) {
    return {
      status: "ok",
      daysRemaining: Infinity,
      label: "No expiry",
      color: "var(--bz-text-2)",
    };
  }

  const expiry =
    typeof expiryDate === "string" ? new Date(expiryDate) : expiryDate;
  const now = new Date();
  const diffMs = expiry.getTime() - now.getTime();
  const daysRemaining = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (daysRemaining <= 0) {
    return {
      status: "expired",
      daysRemaining,
      label: "Expired",
      color: "#ef4444",
    };
  }
  if (daysRemaining <= 30) {
    return {
      status: "critical",
      daysRemaining,
      label: `${daysRemaining}d left`,
      color: "#ef4444",
    };
  }
  if (daysRemaining <= 90) {
    return {
      status: "warning",
      daysRemaining,
      label: `${daysRemaining}d left`,
      color: "#f59e0b",
    };
  }
  return {
    status: "ok",
    daysRemaining,
    label: `${daysRemaining}d left`,
    color: "#22c55e",
  };
}

export function isBirthdayToday(
  dateOfBirth: string | null | undefined,
): boolean {
  if (!dateOfBirth) return false;
  const dob = new Date(dateOfBirth);
  const today = new Date();
  return (
    dob.getMonth() === today.getMonth() && dob.getDate() === today.getDate()
  );
}
