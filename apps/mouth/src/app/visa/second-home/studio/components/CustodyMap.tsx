"use client";

import { useState } from "react";

import { getCopy } from "@/lib/secondhome-studio/copy";

const STEPS = ["step1", "step2", "step3"] as const;

type Step = (typeof STEPS)[number];

function NodeIcon({ step }: { step: Step }) {
  const commonProps = {
    "aria-hidden": true,
    fill: "none",
    height: 28,
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.5,
    viewBox: "0 0 28 28",
    width: 28,
  };

  if (step === "step1") {
    return (
      <svg {...commonProps}>
        <circle cx="14" cy="8" r="3.5" />
        <path d="M6.5 22c.8-4.6 3.3-7 7.5-7s6.7 2.4 7.5 7" />
        <path d="M9 23h10" />
      </svg>
    );
  }

  if (step === "step2") {
    return (
      <svg {...commonProps}>
        <path d="M4.5 10.5 14 5l9.5 5.5" />
        <path d="M6.5 11.5h15M7.5 21.5h13M9 12v7.5M14 12v7.5M19 12v7.5" />
        <path d="M5 23h18" />
      </svg>
    );
  }

  return (
    <svg {...commonProps}>
      <path d="M8 3.5h8l5 5v16H8z" />
      <path d="M16 3.5v5h5M11.5 13h6M11.5 17h6" />
      <circle cx="18.5" cy="21" r="3" />
    </svg>
  );
}

/** Three-stage, interactive view of the deposit evidence path. All visible
 * copy comes from copy.ts so the Studio claim guard remains comprehensive. */
export function CustodyMap() {
  const [expandedStep, setExpandedStep] = useState<Step | null>(null);

  return (
    <section className="custody-map" aria-labelledby="custody-map-title">
      <header className="custody-header">
        <h2 id="custody-map-title">{getCopy("custody.eyebrow")}</h2>
      </header>

      <div
        className="custody-layout"
        role="group"
        aria-label={getCopy("custody.eyebrow")}
        aria-describedby="custody-map-intro"
      >
        <ol className="custody-flow">
          {STEPS.map((step, index) => {
            const isExpanded = expandedStep === step;
            const detailId = `custody-${step}-detail`;

            return (
              <li className="custody-flow-item" key={step}>
                <div className="custody-node" data-account={step === "step1"}>
                  <button
                    type="button"
                    aria-controls={detailId}
                    aria-expanded={isExpanded}
                    onClick={() => setExpandedStep(isExpanded ? null : step)}
                  >
                    <span className="custody-icon">
                      <NodeIcon step={step} />
                    </span>
                    <strong>{getCopy(`custody.steps.${step}.title`)}</strong>
                    <svg
                      aria-hidden
                      className="custody-chevron"
                      viewBox="0 0 16 16"
                    >
                      <path d="m4 6 4 4 4-4" />
                    </svg>
                  </button>
                  <p id={detailId} data-collapsed={!isExpanded}>
                    {getCopy(`custody.steps.${step}.body`)}
                  </p>
                </div>
                {index < STEPS.length - 1 ? (
                  <svg
                    aria-hidden
                    className="custody-arrow"
                    viewBox="0 0 40 18"
                  >
                    <path d="M2 9h33M29 3l6 6-6 6" />
                  </svg>
                ) : null}
              </li>
            );
          })}
        </ol>

        <aside className="custody-outside" id="custody-map-intro">
          <p>{getCopy("custody.intro")}</p>
        </aside>
      </div>

      <p className="custody-disclaimer">{getCopy("custody.disclaimer")}</p>

      <style jsx>{`
        .custody-map {
          display: grid;
          gap: 1.5rem;
          min-width: 0;
          padding: clamp(1.25rem, 3vw, 2rem);
          overflow: hidden;
          background: var(--surface-raised);
          border: 1px solid var(--color-border-subtle);
          border-radius: 12px;
          color: var(--text-primary);
          font-variant-numeric: tabular-nums;
        }

        .custody-header {
          padding-left: 1rem;
          border-left: 2px solid var(--color-border-subtle);
        }

        h2 {
          margin: 0;
          font-size: clamp(1.35rem, 3vw, 1.75rem);
          line-height: 1.2;
        }

        .custody-layout {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(12rem, 0.3fr);
          align-items: center;
          gap: clamp(2rem, 4vw, 3.5rem);
          min-width: 0;
        }

        .custody-flow {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 2.5rem;
          min-width: 0;
          margin: 0;
          padding: 0;
          list-style: none;
        }

        .custody-flow-item {
          position: relative;
          min-width: 0;
        }

        .custody-node {
          height: 100%;
          min-width: 0;
          background: var(--surface-raised);
          border: 1px solid var(--color-border-subtle);
          border-radius: 10px;
        }

        button {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          align-items: center;
          gap: 0.75rem;
          width: 100%;
          min-height: 6rem;
          padding: 1rem;
          color: var(--text-primary);
          text-align: left;
          background: transparent;
          border: 0;
          border-radius: 10px;
          cursor: pointer;
        }

        button:focus-visible {
          outline: 2px solid var(--text-primary);
          outline-offset: 3px;
        }

        .custody-icon {
          display: inline-grid;
          place-items: center;
          color: var(--color-text-muted);
        }

        .custody-node[data-account="true"] .custody-icon {
          color: var(--accent-funnel);
        }

        strong {
          min-width: 0;
          line-height: 1.35;
        }

        .custody-chevron {
          width: 16px;
          height: 16px;
          fill: none;
          stroke: var(--color-text-muted);
          stroke-linecap: round;
          stroke-linejoin: round;
          stroke-width: 1.5;
          transition: transform 180ms ease;
        }

        button[aria-expanded="true"] .custody-chevron {
          transform: rotate(180deg);
        }

        .custody-node > p {
          margin: 0;
          padding: 0 1rem 1rem;
          color: var(--color-text-muted);
          line-height: 1.6;
        }

        .custody-node > p[data-collapsed="true"] {
          display: none;
        }

        .custody-arrow {
          position: absolute;
          top: 3rem;
          left: calc(100% + 0.25rem);
          width: 2rem;
          height: 1.125rem;
          overflow: visible;
          fill: none;
          stroke: var(--color-text-muted);
          stroke-linecap: round;
          stroke-linejoin: round;
          stroke-width: 1.5;
        }

        .custody-outside {
          position: relative;
          padding: 1rem;
          border: 1px dashed var(--color-border-subtle);
          border-radius: 10px;
        }

        .custody-outside::before {
          position: absolute;
          top: 50%;
          right: 100%;
          width: clamp(2rem, 4vw, 3.5rem);
          border-top: 1px dashed var(--color-border-subtle);
          content: "";
        }

        .custody-outside p,
        .custody-disclaimer {
          margin: 0;
          color: var(--color-text-muted);
          line-height: 1.6;
        }

        .custody-disclaimer {
          font-size: 0.82rem;
          font-style: italic;
        }

        @media print {
          .custody-node > p[data-collapsed="true"] {
            display: block !important;
          }

          .custody-chevron {
            display: none !important;
          }
        }

        @media (max-width: 760px) {
          .custody-layout,
          .custody-flow {
            grid-template-columns: minmax(0, 1fr);
          }

          .custody-layout {
            gap: 2.5rem;
          }

          .custody-flow {
            gap: 2.25rem;
          }

          .custody-arrow {
            top: calc(100% + 0.55rem);
            left: 50%;
            transform: translateX(-50%) rotate(90deg);
          }

          .custody-outside::before {
            top: 1.5rem;
            right: 100%;
            bottom: auto;
            left: auto;
            width: 2rem;
            height: 0;
            border-top: 1px dashed var(--color-border-subtle);
            border-left: 0;
          }

          .custody-outside {
            width: calc(100% - 2rem);
            margin-left: 2rem;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .custody-chevron {
            transition: none;
          }
        }
      `}</style>
    </section>
  );
}
