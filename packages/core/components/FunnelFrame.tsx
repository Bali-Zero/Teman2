import type { FC, ReactNode } from "react";
import { TrustBand, type TrustBandProps } from "./TrustBand";
import { CTAHandoff, type CTAHandoffProps } from "./CTAHandoff";
import type { Funnel } from "./ThemeProvider";

export interface FunnelFrameProps {
  funnel: NonNullable<Funnel>;
  sessionId: string;
  step?: { current: number; total: number };
  trust?: TrustBandProps;
  handoff?: Partial<Omit<CTAHandoffProps, "source" | "sessionId">>;
  children: ReactNode;
}

export const FunnelFrame: FC<FunnelFrameProps> = ({
  funnel,
  sessionId,
  step,
  trust,
  handoff,
  children,
}) => (
  <div
    data-funnel={funnel}
    style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}
  >
    {step ? (
      <div
        role="progressbar"
        aria-valuenow={step.current}
        aria-valuemax={step.total}
        style={{
          height: 4,
          background: "var(--color-border-subtle)",
        }}
      >
        <div
          style={{
            width: `${(step.current / step.total) * 100}%`,
            height: "100%",
            background: "var(--accent-funnel)",
          }}
        />
      </div>
    ) : null}
    <main style={{ flex: 1, padding: "var(--space-6)" }}>{children}</main>
    {trust ? <TrustBand {...trust} /> : null}
    <CTAHandoff
      source={`funnel-${funnel}`}
      sessionId={sessionId}
      {...handoff}
    />
  </div>
);
