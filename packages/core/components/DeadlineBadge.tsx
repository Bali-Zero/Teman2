import type { FC } from "react";
import { ProgressRing } from "./ProgressRing";

export interface DeadlineBadgeProps {
  date: Date;
  windowDays?: number;
}

export const DeadlineBadge: FC<DeadlineBadgeProps> = ({
  date,
  windowDays = 30,
}) => {
  const now = Date.now();
  const diffMs = date.getTime() - now;
  const daysLeft = Math.ceil(diffMs / 86400_000);

  let status: "ok" | "warn" | "danger";
  let label: string;
  let percent: number;

  if (daysLeft < 0) {
    status = "danger";
    label = "overdue";
    percent = 0;
  } else if (daysLeft <= 3) {
    status = "danger";
    label = `in ${daysLeft}d`;
    percent = (daysLeft / windowDays) * 100;
  } else if (daysLeft <= 14) {
    status = "warn";
    label = `in ${daysLeft}d`;
    percent = (daysLeft / windowDays) * 100;
  } else {
    status = "ok";
    label = `in ${daysLeft}d`;
    percent = Math.min(100, (daysLeft / windowDays) * 100);
  }

  return (
    <ProgressRing percent={percent} status={status} label={label} size={56} />
  );
};
