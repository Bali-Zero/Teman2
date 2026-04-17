import type { FC, ReactNode } from "react";
import { ProgressRing } from "./ProgressRing";
import { DeadlineBadge } from "./DeadlineBadge";

export type MatterType = "visa" | "company" | "tax" | "property" | "other";

export interface MatterCardProps {
  title: string;
  type: MatterType;
  progressPercent: number;
  pendingDocs?: string[];
  nextDeadline?: Date;
  nextStep?: string;
  action?: ReactNode;
}

const TYPE_LABEL: Record<MatterType, string> = {
  visa: "Visa",
  company: "Company",
  tax: "Tax",
  property: "Property",
  other: "Other",
};

export const MatterCard: FC<MatterCardProps> = ({
  title,
  type,
  progressPercent,
  pendingDocs = [],
  nextDeadline,
  nextStep,
  action,
}) => (
  <article
    style={{
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      gap: "var(--space-4)",
      alignItems: "center",
      padding: "var(--space-4)",
      borderRadius: "var(--radius-lg)",
      background: "var(--surface-raised)",
      border: "1px solid var(--color-border-subtle)",
    }}
  >
    <ProgressRing percent={progressPercent} size={64} />
    <div>
      <header
        style={{
          display: "flex",
          gap: "var(--space-2)",
          alignItems: "baseline",
        }}
      >
        <h3 style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>{title}</h3>
        <span
          style={{
            color: "var(--color-text-secondary)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          {TYPE_LABEL[type]}
        </span>
      </header>
      {pendingDocs.length > 0 ? (
        <p
          style={{
            margin: "var(--space-1) 0 0",
            color: "var(--color-status-warn)",
          }}
        >
          {pendingDocs.length} document{pendingDocs.length === 1 ? "" : "s"}{" "}
          pending
        </p>
      ) : null}
      {nextStep ? (
        <p
          style={{
            margin: "var(--space-1) 0 0",
            color: "var(--color-text-secondary)",
          }}
        >
          Prossimo: {nextStep}
        </p>
      ) : null}
    </div>
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: "var(--space-2)",
      }}
    >
      {nextDeadline ? <DeadlineBadge date={nextDeadline} /> : null}
      {action}
    </div>
  </article>
);
