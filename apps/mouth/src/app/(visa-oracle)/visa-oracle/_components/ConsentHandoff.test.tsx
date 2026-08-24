import { StrictMode, act } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  VISA_ORACLE_CONSENT_KEY,
  VISA_ORACLE_CONSENT_TTL_MS,
} from "../_lib/consent-store";

const emitVisaOracleTelemetry = vi.hoisted(() => vi.fn());
const nonReversibleHash = vi.hoisted(() => vi.fn(async () => "a".repeat(64)));
vi.mock("../_lib/telemetry", async (importOriginal) => {
  const original = await importOriginal<typeof import("../_lib/telemetry")>();
  return { ...original, emitVisaOracleTelemetry, nonReversibleHash };
});

const requestConsultantAssignment = vi.hoisted(() =>
  vi.fn(async () => undefined),
);
vi.mock("../_lib/consultant-assignment-client", async (importOriginal) => {
  const original =
    await importOriginal<
      typeof import("../_lib/consultant-assignment-client")
    >();
  return { ...original, requestConsultantAssignment };
});

import { ConsentHandoff } from "./ConsentHandoff";

// A stable, realistic-looking evaluationId for tests that don't assert on
// the C3 emission itself — the prop is required (see module docstring on
// ConsentHandoffProps), so every render call site needs one.
const TEST_EVALUATION_ID = "11111111-1111-4111-8111-111111111111";

describe("ConsentHandoff", () => {
  beforeEach(() => {
    emitVisaOracleTelemetry.mockReset();
    nonReversibleHash.mockClear();
    requestConsultantAssignment.mockClear();
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders no WhatsApp link or QR until consent is explicit", () => {
    render(
      <ConsentHandoff
        language="en"
        state="SUPPORTED_CANDIDATES"
        whatsappNumber="628123456789"
        evaluationId={TEST_EVALUATION_ID}
        tier="T2"
        originScreen="verdict"
      />,
    );

    expect(screen.queryByRole("link", { name: "Open WhatsApp" })).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();

    fireEvent.click(screen.getByRole("checkbox"));

    expect(screen.getByRole("link", { name: "Open WhatsApp" })).toBeVisible();
    expect(screen.getByRole("img")).toBeVisible();
  });

  it("requires separate guardian confirmation before a minor handoff", () => {
    render(
      <ConsentHandoff
        language="en"
        state="HUMAN_REVIEW_REQUIRED"
        whatsappNumber="628123456789"
        guardianConsentRequired
        evaluationId={TEST_EVALUATION_ID}
        tier="T3"
        originScreen="verdict"
      />,
    );

    const [guardian, whatsapp] = screen.getAllByRole("checkbox");
    expect(guardian).not.toBeChecked();
    expect(whatsapp).toBeDisabled();
    expect(
      screen.getByText(
        "Confirm parent or guardian authority before WhatsApp consent.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(guardian);
    expect(whatsapp).toBeEnabled();
    expect(screen.queryByRole("link", { name: "Open WhatsApp" })).toBeNull();

    fireEvent.click(whatsapp);
    expect(screen.getByRole("link", { name: "Open WhatsApp" })).toBeVisible();

    fireEvent.click(guardian);
    expect(whatsapp).toBeDisabled();
    expect(screen.queryByRole("link", { name: "Open WhatsApp" })).toBeNull();
  });

  it("revokes active consent at its wall-clock expiry without a remount", () => {
    vi.useFakeTimers();
    const grantedAt = new Date("2026-08-03T12:00:00.000Z");
    vi.setSystemTime(grantedAt);
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    };
    render(
      <StrictMode>
        <ConsentHandoff
          language="en"
          state="SUPPORTED_CANDIDATES"
          whatsappNumber="628123456789"
          storage={storage}
          createReceiptId={() => "receipt-expiring"}
          evaluationId={TEST_EVALUATION_ID}
          tier="T2"
          originScreen="verdict"
        />
      </StrictMode>,
    );

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    expect(screen.getByRole("link", { name: "Open WhatsApp" })).toBeVisible();
    expect(screen.getByRole("img")).toBeVisible();
    expect(values.has(VISA_ORACLE_CONSENT_KEY)).toBe(true);

    act(() => {
      vi.advanceTimersByTime(VISA_ORACLE_CONSENT_TTL_MS - 1);
    });
    expect(checkbox).toBeChecked();
    expect(values.has(VISA_ORACLE_CONSENT_KEY)).toBe(true);

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(checkbox).not.toBeChecked();
    expect(screen.queryByRole("link", { name: "Open WhatsApp" })).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
    expect(values.has(VISA_ORACLE_CONSENT_KEY)).toBe(false);
  });

  it("uses a minimal receipt and never serializes interview facts into WhatsApp", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    };
    render(
      <ConsentHandoff
        language="en"
        state="NEEDS_INPUT"
        assessmentReference="abcdef1234567890"
        whatsappNumber="+628123456789"
        storage={storage}
        now={() => new Date("2026-08-03T12:00:00.000Z")}
        createReceiptId={() => "receipt-1"}
        evaluationId={TEST_EVALUATION_ID}
        tier="T3"
        originScreen="verdict"
      />,
    );

    fireEvent.click(screen.getByRole("checkbox"));
    const href = screen
      .getByRole("link", { name: "Open WhatsApp" })
      .getAttribute("href");
    expect(href).toContain("https://wa.me/628123456789?text=");
    const message = decodeURIComponent(href?.split("?text=")[1] ?? "");
    expect(message).toContain("Result state: NEEDS_INPUT");
    expect(message).toContain("Assessment reference: abcdef1234567890");
    expect(message).not.toMatch(/nationality|passport|family|answers?:\s*\{/i);

    const receipt = JSON.parse(Array.from(values.values())[0]);
    expect(receipt).toEqual({
      schemaVersion: 2,
      receiptId: "receipt-1",
      policyVersion: "visa-oracle-whatsapp-v2",
      purpose: "WHATSAPP_HANDOFF",
      channel: "WHATSAPP",
      scope: {
        state: "NEEDS_INPUT",
        assessmentReference: "abcdef1234567890",
      },
      grantedAtIso: "2026-08-03T12:00:00.000Z",
      expiresAtIso: "2026-08-03T14:00:00.000Z",
    });
    expect(JSON.stringify(receipt)).not.toMatch(
      /nationality|passport|family|candidate|facts/i,
    );
  });

  it("requires fresh consent when the decision scope changes and restores only the same scope", async () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    };
    const props = {
      language: "en" as const,
      state: "SUPPORTED_CANDIDATES" as const,
      assessmentReference: "aaaaaaaaaaaaaaaa",
      whatsappNumber: "628123456789",
      storage,
      now: () => new Date("2026-08-03T12:00:00.000Z"),
      createReceiptId: () => "receipt-scoped",
      evaluationId: TEST_EVALUATION_ID,
      tier: "T2" as const,
      originScreen: "verdict" as const,
    };
    const first = render(<ConsentHandoff {...props} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("link", { name: "Open WhatsApp" })).toBeVisible();

    first.unmount();
    const reload = render(<ConsentHandoff {...props} />);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Open WhatsApp" })).toBeVisible(),
    );

    reload.rerender(
      <ConsentHandoff {...props} assessmentReference="bbbbbbbbbbbbbbbb" />,
    );
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "Open WhatsApp" })).toBeNull(),
    );
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(values.size).toBe(0);
  });

  it("omits an unvalidated assessment reference and clears consent on revocation", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    };
    render(
      <ConsentHandoff
        language="en"
        state="SUPPORTED_CANDIDATES"
        assessmentReference="assessment-opaque-123"
        whatsappNumber="628123456789"
        storage={storage}
        now={() => new Date("2026-08-03T12:00:00.000Z")}
        createReceiptId={() => "receipt-revocable"}
        evaluationId={TEST_EVALUATION_ID}
        tier="T2"
        originScreen="verdict"
      />,
    );

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    const href = screen
      .getByRole("link", { name: "Open WhatsApp" })
      .getAttribute("href");
    expect(decodeURIComponent(href ?? "")).not.toContain(
      "Assessment reference",
    );
    expect(values.size).toBe(1);

    fireEvent.click(checkbox);
    expect(screen.queryByRole("link", { name: "Open WhatsApp" })).toBeNull();
    expect(values.size).toBe(0);
  });

  it("records only hashed consent/open telemetry", async () => {
    render(
      <ConsentHandoff
        language="id"
        state="HUMAN_REVIEW_REQUIRED"
        whatsappNumber="628123456789"
        createReceiptId={() => "receipt-sensitive"}
        evaluationId={TEST_EVALUATION_ID}
        tier="T3"
        originScreen="verdict"
      />,
    );

    fireEvent.click(screen.getByRole("checkbox"));
    await act(async () => Promise.resolve());
    fireEvent.click(screen.getByRole("link", { name: "Buka WhatsApp" }));
    await act(async () => Promise.resolve());

    expect(nonReversibleHash).toHaveBeenCalledWith("receipt-sensitive");
    expect(emitVisaOracleTelemetry).toHaveBeenNthCalledWith(1, {
      event: "visa_oracle_v2_consent_granted",
      state: "HUMAN_REVIEW_REQUIRED",
      correlationHash: "a".repeat(64),
    });
    expect(emitVisaOracleTelemetry).toHaveBeenNthCalledWith(2, {
      event: "visa_oracle_v2_handoff_opened",
      state: "HUMAN_REVIEW_REQUIRED",
      correlationHash: "a".repeat(64),
    });
  });

  it("fails closed when the configured WhatsApp number is missing or invalid", () => {
    const { rerender } = render(
      <ConsentHandoff
        language="en"
        state="TEMPORARILY_UNAVAILABLE"
        whatsappNumber="not-a-phone"
        evaluationId={TEST_EVALUATION_ID}
        tier="T3"
        originScreen="verdict"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "WhatsApp handoff is not configured",
    );
    expect(screen.queryByRole("checkbox")).toBeNull();

    rerender(
      <ConsentHandoff
        language="id"
        state="TEMPORARILY_UNAVAILABLE"
        whatsappNumber=""
        evaluationId={TEST_EVALUATION_ID}
        tier="T3"
        originScreen="verdict"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Pengalihan WhatsApp belum dikonfigurasi",
    );
  });

  // ---------------------------------------------------------------------
  // C3 wiring (V3/unit-2) — the event actually fires, with the right shape,
  // at the moment consent is granted.
  // ---------------------------------------------------------------------

  it("emits the C3 consultant-assignment event when consent is granted", async () => {
    render(
      <ConsentHandoff
        language="id"
        state="SUPPORTED_CANDIDATES"
        whatsappNumber="628123456789"
        createReceiptId={() => "receipt-c3"}
        evaluationId={TEST_EVALUATION_ID}
        tier="T2"
        originScreen="verdict"
        clientId="22222222-2222-4222-8222-222222222222"
        productVersionId="33333333-3333-4333-8333-333333333333"
      />,
    );

    expect(requestConsultantAssignment).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox"));
    await act(async () => Promise.resolve());

    expect(requestConsultantAssignment).toHaveBeenCalledTimes(1);
    expect(requestConsultantAssignment).toHaveBeenCalledWith({
      evaluationId: TEST_EVALUATION_ID,
      clientId: "22222222-2222-4222-8222-222222222222",
      originScreen: "verdict",
      tier: "T2",
      productVersionId: "33333333-3333-4333-8333-333333333333",
      locale: "id",
    });
  });

  it("does not emit on revocation, and emits again on a fresh grant", async () => {
    render(
      <ConsentHandoff
        language="en"
        state="NO_SUPPORTED_PATH"
        whatsappNumber="628123456789"
        createReceiptId={() => "receipt-c3-toggle"}
        evaluationId={TEST_EVALUATION_ID}
        tier="T3"
        originScreen="verdict"
      />,
    );

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox); // grant
    await act(async () => Promise.resolve());
    expect(requestConsultantAssignment).toHaveBeenCalledTimes(1);

    fireEvent.click(checkbox); // revoke
    await act(async () => Promise.resolve());
    expect(requestConsultantAssignment).toHaveBeenCalledTimes(1);

    fireEvent.click(checkbox); // grant again
    await act(async () => Promise.resolve());
    expect(requestConsultantAssignment).toHaveBeenCalledTimes(2);
  });

  it("never emits when consent is never granted", () => {
    render(
      <ConsentHandoff
        language="en"
        state="SUPPORTED_CANDIDATES"
        whatsappNumber="628123456789"
        evaluationId={TEST_EVALUATION_ID}
        tier="T2"
        originScreen="verdict"
      />,
    );

    expect(requestConsultantAssignment).not.toHaveBeenCalled();
  });
});
