"use client";

import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronRight } from "lucide-react";

export interface QuestionCardProps {
  heading: string;
  body: string;

  why: string;

  options?: ReactNode;

  headingRef?: Ref<HTMLHeadingElement>;
  children: ReactNode;
}

function handleRadioGroupKeyDown(event: KeyboardEvent<HTMLDivElement>) {
  const target = event.target;
  if (!(target instanceof Element)) return;

  const currentRadio = target.closest<HTMLButtonElement>('[role="radio"]');
  if (!currentRadio || !event.currentTarget.contains(currentRadio)) return;

  const radios = Array.from(
    event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]'),
  );
  const currentIndex = radios.indexOf(currentRadio);
  if (currentIndex < 0 || radios.length === 0) return;

  let nextIndex: number;
  switch (event.key) {
    case "ArrowDown":
    case "ArrowRight":
      nextIndex = (currentIndex + 1) % radios.length;
      break;
    case "ArrowUp":
    case "ArrowLeft":
      nextIndex = (currentIndex - 1 + radios.length) % radios.length;
      break;
    case "Home":
      nextIndex = 0;
      break;
    case "End":
      nextIndex = radios.length - 1;
      break;
    default:
      return;
  }

  event.preventDefault();
  const nextRadio = radios[nextIndex];
  nextRadio.focus();
  nextRadio.click();
}

export function QuestionCard({
  heading,
  body,
  why,
  options,
  headingRef,
  children,
}: QuestionCardProps) {
  const headingId = useId();
  const optionNodes = Children.toArray(options);
  const radioIndexes = optionNodes.flatMap((option, index) =>
    isValidElement<OptionButtonProps>(option) &&
    option.type === OptionButton &&
    option.props.variant === "radio"
      ? [index]
      : [],
  );
  const selectedRadioIndex = radioIndexes.find((index) => {
    const option = optionNodes[index];
    return isValidElement<OptionButtonProps>(option) && option.props.selected;
  });
  const tabbableRadioIndex = selectedRadioIndex ?? radioIndexes[0];
  const radioOptions = optionNodes.map((option, index) =>
    isValidElement<OptionButtonProps>(option) &&
    option.type === OptionButton &&
    option.props.variant === "radio"
      ? cloneElement(option, {
          tabIndex: index === tabbableRadioIndex ? 0 : -1,
        })
      : option,
  );

  return (
    <div
      style={{
        display: "grid",
        gap: "var(--space-3, 1rem)",
        background: "var(--surface-raised)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: "var(--space-4, 1.5rem)",
      }}
    >
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        style={{
          margin: 0,
          fontFamily: "var(--font-serif, Georgia, serif)",
          fontSize: "clamp(1.5rem, 3vw, 1.6rem)",
          color: "var(--text-primary)",
        }}
      >
        {heading}
      </h2>
      <p style={{ margin: 0, lineHeight: 1.6, color: "var(--text-primary)" }}>
        {body}
      </p>
      <details
        className="bz-shs-why"
        style={{ fontSize: "var(--text-sm, 0.88rem)" }}
      >
        <summary
          className="bz-shs-why-summary"
          style={{
            cursor: "pointer",
            color: "var(--color-text-muted)",
            fontWeight: 600,
            listStyle: "none",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-1, 0.35rem)",
          }}
        >
          <ChevronRight
            size={14}
            aria-hidden
            className="bz-shs-why-chevron"
            style={{ flexShrink: 0 }}
          />
          Why we ask
        </summary>
        <p
          style={{
            margin: "var(--space-2, 0.5rem) 0 0",
            color: "var(--color-text-muted)",
            lineHeight: 1.5,
          }}
        >
          {why}
        </p>
      </details>
      {options ? (
        <div
          role="radiogroup"
          aria-labelledby={headingId}
          onKeyDown={handleRadioGroupKeyDown}
          style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}
        >
          {radioOptions}
        </div>
      ) : null}
      <div style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}>
        {children}
      </div>

      <style>{`
        .bz-shs-why-summary::-webkit-details-marker {
          display: none;
        }
        .bz-shs-why-chevron {
          transition: transform 150ms ease-out;
        }
        .bz-shs-why[open] > .bz-shs-why-summary .bz-shs-why-chevron {
          transform: rotate(90deg);
        }

        .bz-shs-option {
          border: 1px solid var(--border-strong);
          background: transparent;
          box-shadow: inset 0 0 0 0 transparent;
          transition:
            border-color 150ms ease-out,
            background-color 150ms ease-out,
            box-shadow 150ms ease-out;
        }
        .bz-shs-option:hover {
          border-color: var(--accent-funnel);
          background: color-mix(in srgb, var(--accent-funnel) 6%, transparent);
        }

        .bz-shs-option[data-selected="true"] {
          border-color: var(--text-primary);
          background: color-mix(in srgb, var(--text-primary) 6%, transparent);
          box-shadow: inset 0 0 0 2px var(--text-primary);
        }
        .bz-shs-option[data-selected="true"]:hover {
          background: color-mix(in srgb, var(--text-primary) 9%, transparent);
        }
        .bz-shs-option:focus-visible {
          outline: 3px solid var(--text-primary);
          outline-offset: 3px;
        }
        @media (prefers-reduced-motion: reduce) {
          .bz-shs-why-chevron,
          .bz-shs-option {
            transition: none !important;
          }
        }
      `}</style>
    </div>
  );
}

export interface OptionButtonProps {
  label: string;
  selected: boolean;
  onSelect: () => void;

  variant?: "radio" | "toggle";

  icon?: LucideIcon;

  tabIndex?: 0 | -1;
}

function RadioAffordance({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        width: 20,
        height: 20,
        borderRadius: "50%",
        border: selected
          ? "2px solid var(--text-primary)"
          : "1.5px solid var(--border-strong)",
      }}
    >
      {selected ? (
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: "var(--text-primary)",
          }}
        />
      ) : null}
    </span>
  );
}

function CheckAffordance({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        width: 20,
        height: 20,
        borderRadius: 5,
        border: selected
          ? "2px solid var(--text-primary)"
          : "1.5px solid var(--border-strong)",
        background: selected ? "var(--text-primary)" : "transparent",
        color: "#ffffff",
        fontSize: 13,
        lineHeight: 1,
      }}
    >
      {selected ? "✓" : null}
    </span>
  );
}

export function OptionButton({
  label,
  selected,
  onSelect,
  variant = "toggle",
  icon: Icon,
  tabIndex,
}: OptionButtonProps) {
  const isRadio = variant === "radio";
  return (
    <button
      type="button"
      onClick={onSelect}
      role={isRadio ? "radio" : undefined}
      aria-checked={isRadio ? selected : undefined}
      aria-pressed={isRadio ? undefined : selected}
      tabIndex={isRadio ? (tabIndex ?? 0) : undefined}
      className="bz-shs-option"
      data-selected={selected ? "true" : "false"}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3, 0.75rem)",
        padding: "var(--space-3, 0.85rem) var(--space-4, 1.1rem)",
        borderRadius: 12,
        color: "var(--text-primary)",
        textAlign: "left",
        cursor: "pointer",
        minHeight: 44,
        fontSize: "1rem",
        fontFamily: "inherit",
      }}
    >
      {isRadio ? (
        <RadioAffordance selected={selected} />
      ) : (
        <CheckAffordance selected={selected} />
      )}
      {Icon ? (
        <Icon
          size={18}
          strokeWidth={1.5}
          aria-hidden
          style={{
            flexShrink: 0,
            color: "var(--color-text-muted)",
          }}
        />
      ) : null}
      <span>{label}</span>
    </button>
  );
}
