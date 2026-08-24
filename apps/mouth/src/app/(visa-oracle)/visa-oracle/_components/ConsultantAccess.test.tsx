import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forwardRef, type ReactNode } from "react";

const emitVisaOracleTelemetry = vi.hoisted(() => vi.fn());
const nonReversibleHash = vi.hoisted(() => vi.fn(async () => "a".repeat(64)));
vi.mock("../_lib/telemetry", async (importOriginal) => {
  const original = await importOriginal<typeof import("../_lib/telemetry")>();
  return { ...original, emitVisaOracleTelemetry, nonReversibleHash };
});

// framer-motion's `motion.div` starts its entrance keyframe (`initial`) at
// `opacity: 0` and only reaches `opacity: 1` after its transition runs —
// real, correct behaviour for a fade-in panel, but jsdom never ticks a real
// animation frame during a synchronous `fireEvent.click`, so the inline
// style stays frozen at the initial keyframe for the rest of the test. That
// makes jest-dom's `toBeVisible()` (which walks the full ancestor chain
// checking `opacity !== '0'`) fail on the dialog AND everything inside it —
// not a real bug in `ConsultantAccess`, an artifact of testing an
// animation-timed reveal outside a real paint loop. Stub `motion.div` down
// to a plain `div` (dropping only the framer-only animation props) and
// `AnimatePresence` down to a passthrough, so these tests exercise the
// component's actual open/close/consent logic against real, un-animated
// computed styles instead of a frozen mid-transition frame.
vi.mock("framer-motion", async (importOriginal) => {
  const original = await importOriginal<typeof import("framer-motion")>();
  const PassthroughDiv = forwardRef<
    HTMLDivElement,
    {
      children?: ReactNode;
      initial?: unknown;
      animate?: unknown;
      exit?: unknown;
      transition?: unknown;
      [key: string]: unknown;
    }
  >(function PassthroughDiv(
    {
      initial: _initial,
      animate: _animate,
      exit: _exit,
      transition: _t,
      ...rest
    },
    ref,
  ) {
    return <div ref={ref} {...rest} />;
  });
  return {
    ...original,
    AnimatePresence: ({ children }: { children?: ReactNode }) => children,
    motion: { ...original.motion, div: PassthroughDiv },
  };
});

import { ConsultantAccess } from "./ConsultantAccess";

// The trigger's accessible NAME is its `aria-label` (`consultant.trigger.aria`
// in i18n.ts), a WCAG 2.5.3 "Label in Name"-compliant superset of the
// visible `<span>` text (`consultant.trigger`) — not the visible text
// itself. Matched below as a startsWith regex, not the full aria-label
// literal, so these stay stable if the description's tail is edited without
// changing what a sighted user reads on the button.
const TRIGGER_NAME = /^Talk to a consultant/;

describe("ConsultantAccess", () => {
  beforeEach(() => {
    emitVisaOracleTelemetry.mockReset();
    nonReversibleHash.mockClear();
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a stable trigger selector, closed by default", () => {
    render(<ConsultantAccess language="en" whatsappNumber="628123456789" />);

    const trigger = screen.getByRole("button", { name: TRIGGER_NAME });
    expect(trigger).toHaveAttribute("data-oracle-consultant-trigger");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens the consent panel with an IN_PROGRESS scope when no verdict exists yet", () => {
    // No `state` prop passed — this is the mid-interview case (framing,
    // question, confirmation screens), before any evaluation has run.
    render(<ConsultantAccess language="en" whatsappNumber="628123456789" />);

    fireEvent.click(screen.getByRole("button", { name: TRIGGER_NAME }));

    expect(screen.getByRole("dialog")).toBeVisible();
    // ConsentHandoff itself is rendered inside — its consent checkbox is
    // reachable, proving the IN_PROGRESS scope did not throw inside
    // createLocalConsentReceipt (consent-store.ts's validScope gate).
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("link", { name: "Open WhatsApp" })).toBeVisible();
  });

  it("passes the real outcome state through once a verdict exists", () => {
    render(
      <ConsultantAccess
        language="en"
        state="HUMAN_REVIEW_REQUIRED"
        assessmentReference="ab12cd34ef56gh78"
        whatsappNumber="628123456789"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: TRIGGER_NAME }));
    fireEvent.click(screen.getByRole("checkbox"));

    const link = screen.getByRole("link", {
      name: "Open WhatsApp",
    }) as HTMLAnchorElement;
    const message = decodeURIComponent(link.href.split("?text=")[1] ?? "");
    expect(message).toContain("HUMAN_REVIEW_REQUIRED");
    expect(message).toContain("ab12cd34ef56gh78");
  });

  it("closes on Escape and on an outside click", () => {
    render(
      <div>
        <ConsultantAccess language="en" whatsappNumber="628123456789" />
        <button type="button">outside</button>
      </div>,
    );

    fireEvent.click(screen.getByRole("button", { name: TRIGGER_NAME }));
    expect(screen.getByRole("dialog")).toBeVisible();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: TRIGGER_NAME }));
    expect(screen.getByRole("dialog")).toBeVisible();

    fireEvent.pointerDown(screen.getByRole("button", { name: "outside" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes via its own close button without leaving the trigger stuck expanded", async () => {
    render(<ConsultantAccess language="en" whatsappNumber="628123456789" />);

    fireEvent.click(screen.getByRole("button", { name: TRIGGER_NAME }));
    fireEvent.click(
      screen.getByRole("button", { name: "Close consultant panel" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: TRIGGER_NAME }),
      ).toHaveAttribute("aria-expanded", "false"),
    );
  });

  it("renders in Bahasa Indonesia when language is id", () => {
    render(<ConsultantAccess language="id" whatsappNumber="628123456789" />);

    expect(
      screen.getByRole("button", {
        name: /^Bicara dengan konsultan/,
      }),
    ).toBeInTheDocument();
  });
});
