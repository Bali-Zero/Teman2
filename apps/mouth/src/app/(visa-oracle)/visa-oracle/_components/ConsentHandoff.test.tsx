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

import { ConsentHandoff } from "./ConsentHandoff";

describe("ConsentHandoff", () => {
  beforeEach(() => {
    emitVisaOracleTelemetry.mockReset();
    nonReversibleHash.mockClear();
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
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Pengalihan WhatsApp belum dikonfigurasi",
    );
  });
});
