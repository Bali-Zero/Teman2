import type { FC } from "react";
import { ProgressRing } from "./ProgressRing";

export interface DeadlineBadgeProps {
  date: Date;
  windowDays?: number;
}

const MS_DAY = 86_400_000;
// Asia/Makassar, UTC+8, no DST. Deadlines are calendar-day concepts, so
// "days left" is a WITA calendar-day count, not a raw millisecond diff — a
// badge checked before 08:00 WITA must not read one day earlier than after.
const WITA_OFFSET_MS = 8 * 60 * 60 * 1000;

function witaCalendarDate(instant: Date): number {
  const shifted = new Date(instant.getTime() + WITA_OFFSET_MS);
  return Date.UTC(
    shifted.getUTCFullYear(),
    shifted.getUTCMonth(),
    shifted.getUTCDate(),
  );
}

export const DeadlineBadge: FC<DeadlineBadgeProps> = ({
  date,
  windowDays = 30,
}) => {
  const daysLeft = Math.round(
    (witaCalendarDate(date) - witaCalendarDate(new Date())) / MS_DAY,
  );

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
